"""
app/routers/allocations.py — TruckAllocation API endpoints.

POST   /api/allocations                          — Create allocation for a schedule (DRAFT)
GET    /api/allocations                          — List allocations (filter: status, schedule_id)
GET    /api/allocations/{id}                     — Detail with items + schedule info
POST   /api/allocations/{id}/items               — Add an order line item
DELETE /api/allocations/{id}/items/{item_id}     — Remove an order line item
PATCH  /api/allocations/{id}/load                — Set status=WAITING_LOADING (load plan ready)
PATCH  /api/allocations/{id}/release             — Legacy alias for /load
PATCH  /api/allocations/{id}/loaded              — Set status=LOADED (truck cleared for loading)
PATCH  /api/allocations/{id}/revert              — Revert allocation to DRAFT
PATCH  /api/allocations/{id}/remarks             — Set/update remarks text
GET    /api/allocations/export/final-status      — Export allocations as Excel with Nyati branding
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AllocationStatus, TruckSchedule
from app.models.truck_allocation import AllocationItem, TruckAllocation, TruckAllocationStatus
from app.schemas.truck_allocation import (
    AllocationItemCreate,
    AllocationItemRead,
    ReleaseRequest,
    RemarksRequest,
    TruckAllocationCreate,
    TruckAllocationListItem,
    TruckAllocationRead,
)
from app.services.excel_export import generate_final_status_report

router = APIRouter(prefix="/api/allocations", tags=["allocations"])

WAITING_LOADING_STATUSES = (
    TruckAllocationStatus.WAITING_LOADING,
    TruckAllocationStatus.RELEASED,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_read(alloc: TruckAllocation) -> TruckAllocationRead:
    """Build TruckAllocationRead safely — items + schedule must be eagerly loaded."""
    read = TruckAllocationRead(
        id=alloc.id,
        schedule_id=alloc.schedule_id,
        status=alloc.status,
        remarks=alloc.remarks,
        released_at=alloc.released_at,
        loaded_at=alloc.loaded_at,
        released_by=alloc.released_by,
        created_at=alloc.created_at,
        total_tonnes=sum(i.quantity_tonnes for i in alloc.items),
        items=[AllocationItemRead.model_validate(i) for i in alloc.items],
    )
    if alloc.schedule:
        _enrich(read, alloc.schedule)
    return read


def _enrich(item: TruckAllocationListItem | TruckAllocationRead, s: TruckSchedule) -> None:
    item.schedule_ref           = s.schedule_ref
    item.odoo_po_name           = s.odoo_po_name
    item.truck_plate            = s.truck_plate
    item.transporter_name       = s.transporter_name
    item.driver_name            = s.driver_name
    item.driver_license_no      = s.driver_license_no
    item.dealer_number          = s.dealer_number
    item.origin_region          = s.origin_region
    item.expected_arrival_dt    = s.expected_arrival_dt
    item.effective_capacity_tonnes = s.effective_capacity_tonnes


async def _get_or_404(
    allocation_id: int,
    db: AsyncSession,
    load_items: bool = False,
) -> TruckAllocation:
    q = select(TruckAllocation).where(TruckAllocation.id == allocation_id)
    if load_items:
        q = q.options(
            selectinload(TruckAllocation.items),
            selectinload(TruckAllocation.schedule),
        )
    result = await db.execute(q)
    alloc = result.scalar_one_or_none()
    if not alloc:
        raise HTTPException(status_code=404, detail=f"Allocation {allocation_id} not found")
    return alloc


# ── POST /api/allocations ─────────────────────────────────────────────────────

@router.post("", response_model=TruckAllocationRead)
async def create_allocation(body: TruckAllocationCreate, db: AsyncSession = Depends(get_db)):
    # Prevent duplicate allocations for the same schedule
    existing = await db.execute(
        select(TruckAllocation)
        .where(TruckAllocation.schedule_id == body.schedule_id)
        .options(selectinload(TruckAllocation.items), selectinload(TruckAllocation.schedule))
    )
    alloc = existing.scalar_one_or_none()
    if alloc:
        return _build_read(alloc)

    # Verify schedule exists
    sched = await db.get(TruckSchedule, body.schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule {body.schedule_id} not found")

    alloc = TruckAllocation(
        schedule_id=body.schedule_id,
        released_by=body.released_by,
        status=TruckAllocationStatus.DRAFT,
    )
    db.add(alloc)
    await db.commit()

    # Re-query with all relationships eager-loaded to avoid async lazy-load errors
    result = await db.execute(
        select(TruckAllocation)
        .where(TruckAllocation.schedule_id == body.schedule_id)
        .options(selectinload(TruckAllocation.items), selectinload(TruckAllocation.schedule))
    )
    alloc = result.scalar_one()
    return _build_read(alloc)


# ── GET /api/allocations ──────────────────────────────────────────────────────

@router.get("", response_model=list[TruckAllocationListItem])
async def list_allocations(
    status: str | None = Query(None, description="draft | waiting_loading | loaded | released"),
    schedule_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(TruckAllocation).options(
        selectinload(TruckAllocation.items),
        selectinload(TruckAllocation.schedule),
    )
    if status:
        normalized_status = status.upper()
        if normalized_status in ("WAITING_LOADING", "RELEASED"):
            q = q.where(TruckAllocation.status.in_(WAITING_LOADING_STATUSES))
        else:
            q = q.where(TruckAllocation.status == normalized_status)
    if schedule_id:
        q = q.where(TruckAllocation.schedule_id == schedule_id)
    q = q.order_by(TruckAllocation.created_at.desc())

    result = await db.execute(q)
    allocs = result.scalars().all()

    out = []
    for a in allocs:
        item = TruckAllocationListItem.model_validate(a)
        item.total_tonnes = a.total_tonnes
        item.item_count = len(a.items)
        if a.schedule:
            _enrich(item, a.schedule)
        out.append(item)
    return out


# ── GET /api/allocations/{id} ─────────────────────────────────────────────────

@router.get("/{allocation_id}", response_model=TruckAllocationRead)
async def get_allocation(allocation_id: int, db: AsyncSession = Depends(get_db)):
    alloc = await _get_or_404(allocation_id, db, load_items=True)
    return _build_read(alloc)


# ── POST /api/allocations/{id}/items ─────────────────────────────────────────

@router.post("/{allocation_id}/items", response_model=AllocationItemRead)
async def add_item(
    allocation_id: int,
    body: AllocationItemCreate,
    db: AsyncSession = Depends(get_db),
):
    alloc = await _get_or_404(allocation_id, db, load_items=True)

    next_seq = max((i.sequence for i in alloc.items), default=0) + 1
    item = AllocationItem(
        allocation_id=allocation_id,
        customer_name=body.customer_name,
        order_ref=body.order_ref,
        order_date=body.order_date,
        product=body.product,
        quantity_tonnes=body.quantity_tonnes,
        destination_location=body.destination_location,
        region=body.region,
        sequence=next_seq,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return AllocationItemRead.model_validate(item)


# ── DELETE /api/allocations/{id}/items/{item_id} ─────────────────────────────

@router.delete("/{allocation_id}/items/{item_id}", status_code=204)
async def remove_item(
    allocation_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    alloc = await _get_or_404(allocation_id, db)

    result = await db.execute(
        select(AllocationItem).where(
            AllocationItem.id == item_id,
            AllocationItem.allocation_id == allocation_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    await db.delete(item)
    await db.commit()


# ── PATCH /api/allocations/{id}/load ─────────────────────────────────────────

@router.patch("/{allocation_id}/load")
@router.patch("/{allocation_id}/release")
async def release_allocation(
    allocation_id: int,
    body: ReleaseRequest,
    db: AsyncSession = Depends(get_db),
):
    alloc = await _get_or_404(allocation_id, db, load_items=True)

    if alloc.status == TruckAllocationStatus.LOADED:
        return {"ok": True, "message": "Already loaded", "status": alloc.status}

    if not alloc.items:
        raise HTTPException(status_code=400, detail="Cannot mark a load plan ready with no order items")

    now = datetime.now(timezone.utc)
    alloc.status      = TruckAllocationStatus.WAITING_LOADING
    alloc.released_at = now
    alloc.released_by = body.released_by

    # Update the parent TruckSchedule allocation_status
    sched = await db.get(TruckSchedule, alloc.schedule_id)
    if sched:
        sched.allocation_status = AllocationStatus.WAITING_LOADING

    await db.commit()

    # Broadcast SSE
    from app.routers.schedules import broadcast_sse
    broadcast_sse("truck_allocated", {
        "schedule_id": alloc.schedule_id,
        "schedule_ref": sched.schedule_ref if sched else "",
        "allocation_id": allocation_id,
        "status": "WAITING_LOADING",
    })

    return {
        "ok": True,
        "allocation_id": allocation_id,
        "status": "WAITING_LOADING",
        "released_at": now.isoformat(),
        "item_count": len(alloc.items),
        "total_tonnes": alloc.total_tonnes,
    }


# ── PATCH /api/allocations/{id}/loaded ───────────────────────────────────────

@router.patch("/{allocation_id}/loaded")
async def mark_loaded(allocation_id: int, db: AsyncSession = Depends(get_db)):
    alloc = await _get_or_404(allocation_id, db)

    if alloc.status not in WAITING_LOADING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Allocation must be WAITING_LOADING before marking LOADED (current: {alloc.status})",
        )

    now = datetime.now(timezone.utc)
    alloc.status    = TruckAllocationStatus.LOADED
    alloc.loaded_at = now

    # Update TruckSchedule
    sched = await db.get(TruckSchedule, alloc.schedule_id)
    if sched:
        sched.allocation_status = AllocationStatus.LOADED

    await db.commit()

    from app.routers.schedules import broadcast_sse
    broadcast_sse("truck_dispatched", {
        "schedule_id": alloc.schedule_id,
        "schedule_ref": sched.schedule_ref if sched else "",
        "allocation_id": allocation_id,
        "status": "LOADED",
    })

    return {
        "ok": True,
        "allocation_id": allocation_id,
        "status": "LOADED",
        "loaded_at": now.isoformat(),
    }


# ── PATCH /api/allocations/{id}/revert ───────────────────────────────────────

@router.patch("/{allocation_id}/revert")
async def revert_to_draft(allocation_id: int, db: AsyncSession = Depends(get_db)):
    """Revert any allocation back to DRAFT so the dispatcher can edit it freely."""
    alloc = await _get_or_404(allocation_id, db)

    alloc.status      = TruckAllocationStatus.DRAFT
    alloc.released_at = None
    alloc.loaded_at   = None

    sched = await db.get(TruckSchedule, alloc.schedule_id)
    if sched:
        sched.allocation_status = AllocationStatus.UNALLOCATED

    await db.commit()

    from app.routers.schedules import broadcast_sse
    broadcast_sse("schedule_updated", {
        "schedule_id": alloc.schedule_id,
        "schedule_ref": sched.schedule_ref if sched else "",
        "allocation_id": allocation_id,
        "status": "DRAFT",
    })

    return {"ok": True, "allocation_id": allocation_id, "status": "DRAFT"}


# ── PATCH /api/allocations/{id}/remarks ──────────────────────────────────────

@router.patch("/{allocation_id}/remarks")
async def set_remarks(
    allocation_id: int,
    body: RemarksRequest,
    db: AsyncSession = Depends(get_db),
):
    alloc = await _get_or_404(allocation_id, db)
    alloc.remarks = body.remarks
    await db.commit()
    return {"ok": True, "allocation_id": allocation_id, "remarks": alloc.remarks}


# ── GET /api/allocations/export/final-status ──────────────────────────────────

@router.get("/export/final-status")
async def export_final_status(
    status: str | None = Query(None, description="Filter by: draft | waiting_loading | loaded | released"),
    schedule_id: int | None = Query(None, description="Filter by schedule ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export final status allocations as Excel file with Nyati branding.
    
    Query params:
      - status: Filter by allocation status
      - schedule_id: Filter by specific schedule
    
    Returns:
      - Excel file (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
    """
    # Load all matching allocations with their items and schedule data
    q = select(TruckAllocation).options(
        selectinload(TruckAllocation.items),
        selectinload(TruckAllocation.schedule),
    )
    
    if status:
        normalized_status = status.upper()
        if normalized_status in ("WAITING_LOADING", "RELEASED"):
            q = q.where(TruckAllocation.status.in_(WAITING_LOADING_STATUSES))
        else:
            q = q.where(TruckAllocation.status == normalized_status)
    
    if schedule_id:
        q = q.where(TruckAllocation.schedule_id == schedule_id)
    
    q = q.order_by(TruckAllocation.created_at.desc())
    
    result = await db.execute(q)
    allocations = result.scalars().all()
    
    if not allocations:
        raise HTTPException(
            status_code=404,
            detail="No allocations found matching the filter criteria"
        )
    
    # Generate Excel file
    excel_bytes = generate_final_status_report(allocations)
    
    # Return as downloadable file
    from datetime import datetime
    filename = f"final-status-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    
    return StreamingResponse(
        iter([excel_bytes.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
