"""
app/routers/schedules.py — TruckSchedule API endpoints.

GET  /api/schedules              — Live list (default: available only)
GET  /api/schedules/{id}         — Schedule detail
PATCH /api/schedules/{id}/confirm-details  — Add truck plate + driver
PATCH /api/schedules/{id}/arrived          — Mark physical arrival
PATCH /api/schedules/{id}/dispatch         — Mark loaded + dispatched
POST  /api/schedules/{id}/rematch          — Force re-run matching
GET  /api/schedules/feed                   — SSE live stream
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    AllocationProposal,
    AllocationStatus,
    TruckSchedule,
    TruckScheduleStatus,
)
from app.models.truck_schedule import TruckScheduleStatus as TSS
from app.schemas.truck_schedule import (
    TruckScheduleDetail,
    TruckScheduleListItem,
    TruckScheduleRead,
)

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

# Global SSE client registry {client_id: asyncio.Queue}
_sse_clients: dict[str, asyncio.Queue] = {}


def broadcast_sse(event_type: str, data: dict) -> None:
    """Push an SSE event to all connected dashboard clients."""
    payload = json.dumps({"type": event_type, **data})
    dead = []
    for cid, q in _sse_clients.items():
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(cid)
    for cid in dead:
        _sse_clients.pop(cid, None)


# ── GET /api/schedules ────────────────────────────────────────────────────────

@router.get("", response_model=list[TruckScheduleListItem])
async def list_schedules(
    status: str = Query("available", description="available | all | expected | arrived | dispatched"),
    db: AsyncSession = Depends(get_db),
):
    """
    List TruckSchedules.
    - status=available  → EXPECTED + PRE_CONFIRMED, not yet confirmed  [default]
    - status=all        → everything
    - status=expected   → only EXPECTED
    """
    q = select(TruckSchedule)

    if status == "available":
        q = q.where(
            TruckSchedule.status.in_([TSS.EXPECTED, TSS.PRE_CONFIRMED]),
            TruckSchedule.allocation_status.notin_([
                AllocationStatus.WAITING_LOADING,
                AllocationStatus.RELEASED,
                AllocationStatus.LOADED,
            ]),
        )
    elif status == "expected":
        q = q.where(TruckSchedule.status == TSS.EXPECTED)
    elif status != "all":
        q = q.where(TruckSchedule.status == status.upper())

    q = q.order_by(TruckSchedule.expected_arrival_dt.asc().nulls_last())
    result = await db.execute(q)
    schedules = result.scalars().all()
    return [TruckScheduleListItem.model_validate(s) for s in schedules]


# ── GET /api/schedules/export ────────────────────────────────────────────────

@router.get("/export")
async def export_schedules_excel(
    status: str = Query("all", description="available | all | expected | arrived | dispatched"),
    db: AsyncSession = Depends(get_db),
):
    """Export scheduled trucks as an Excel workbook."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    q = select(TruckSchedule)

    if status == "available":
        q = q.where(
            TruckSchedule.status.in_([TSS.EXPECTED, TSS.PRE_CONFIRMED]),
            TruckSchedule.allocation_status.notin_([
                AllocationStatus.RELEASED,
                AllocationStatus.LOADED,
            ]),
        )
    elif status == "expected":
        q = q.where(TruckSchedule.status == TSS.EXPECTED)
    elif status != "all":
        q = q.where(TruckSchedule.status == status.upper())

    q = q.order_by(TruckSchedule.expected_arrival_dt.asc().nulls_last())
    result = await db.execute(q)
    schedules = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Scheduled Trucks"

    headers = [
        "ETA",
        "PO Ref",
        "Material",
        "Transporter",
        "Driver Name",
        "License No.",
        "Dealer No.",
        "Truck No.",
        "Location",
        "Schedule Ref",
        "Truck Status",
        "Allocation Status",
        "Estimated Qty (T)",
        "Capacity (T)",
        "Corridor",
        "Notes",
    ]
    ws.append(headers)

    for schedule in schedules:
        ws.append([
            schedule.expected_arrival_dt,
            schedule.odoo_po_name,
            schedule.raw_material_type,
            schedule.transporter_name,
            schedule.driver_name,
            schedule.driver_license_no,
            schedule.dealer_number,
            schedule.truck_plate,
            schedule.origin_region,
            schedule.schedule_ref,
            schedule.status,
            schedule.allocation_status,
            schedule.estimated_qty_tonnes,
            schedule.effective_capacity_tonnes,
            schedule.corridor_name,
            schedule.notes,
        ])

    header_fill = PatternFill("solid", fgColor="173158")
    for cell in ws[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill

    ws.freeze_panes = "A2"
    for column in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in column)
        ws.column_dimensions[get_column_letter(column[0].column)].width = min(max_len + 2, 32)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"scheduled-trucks-{status}-{today}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /api/schedules/odoo-config ───────────────────────────────────────────

@router.get("/odoo-config")
async def get_odoo_config():
    """
    Returns Odoo SO creation URL config for client-side URL building.
    The Allocate button uses this to open a pre-filled Odoo SO form.
    """
    from app.config import get_settings
    s = get_settings()
    return {
        "odoo_url": s.odoo_url,
        "so_action_id": s.odoo_so_action_id,
        "so_menu_id": s.odoo_so_menu_id,
        "cids": s.odoo_so_cids,
        "fields": {
            "truck_no":       s.odoo_so_field_truck_no,
            "trailer_no":     s.odoo_so_field_trailer_no,
            "driver_name":    s.odoo_so_field_driver_name,
            "driver_phone":   s.odoo_so_field_driver_phone,
            "driver_license": s.odoo_so_field_driver_license,
        },
    }


# ── GET /api/schedules/{id}/odoo-url ─────────────────────────────────────────

@router.get("/{schedule_id}/odoo-url")
async def get_odoo_url(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """
    Build the Odoo SO creation URL for a specific truck schedule.
    Looks up fleet.vehicle by plate and driver.master.custom by license
    so the many2one fields are pre-filled (which triggers onchange to fill
    the readonly char fields like Truck No, Driver Name, etc.).
    """
    import asyncio as _aio
    from app.config import get_settings
    from app.services.odoo_sync import OdooClient

    schedule = await _get_or_404(schedule_id, db)
    s = get_settings()
    client = OdooClient()

    vehicle_odoo_id: int | None = None
    driver_odoo_id: int | None = None

    try:
        uid = await _aio.to_thread(client._uid_or_auth)
        models = client._models()

        if schedule.truck_plate:
            rows = await _aio.to_thread(
                models.execute_kw,
                s.odoo_db, uid, s.odoo_password,
                "fleet.vehicle", "search_read",
                [[["license_plate", "=", schedule.truck_plate]]],
                {"fields": ["id"], "limit": 1},
            )
            if rows:
                vehicle_odoo_id = rows[0]["id"]

        if schedule.driver_license_no:
            rows = await _aio.to_thread(
                models.execute_kw,
                s.odoo_db, uid, s.odoo_password,
                "driver.master.custom", "search_read",
                [[["license", "=", schedule.driver_license_no]]],
                {"fields": ["id"], "limit": 1},
            )
            if rows:
                driver_odoo_id = rows[0]["id"]
    except Exception:
        pass  # non-critical — open form without pre-fill if Odoo unreachable

    hash_parts = (
        f"cids={s.odoo_so_cids}"
        f"&menu_id={s.odoo_so_menu_id}"
        f"&action={s.odoo_so_action_id}"
        f"&model=sale.order&view_type=form"
    )
    if vehicle_odoo_id:
        hash_parts += f"&default_vehicle_id={vehicle_odoo_id}"
    if driver_odoo_id:
        hash_parts += f"&default_custom_driver_id={driver_odoo_id}"

    return {
        "url": f"{s.odoo_url}/web#{hash_parts}",
        "vehicle_found": vehicle_odoo_id is not None,
        "driver_found": driver_odoo_id is not None,
        "truck_plate": schedule.truck_plate,
        "driver_name": schedule.driver_name,
    }


# ── GET /api/schedules/order-status ──────────────────────────────────────────

@router.get("/order-status")
async def get_order_status(db: AsyncSession = Depends(get_db)):
    """
    Returns all active truck schedules with their local allocation status.
    No Odoo sync — status reflects what is tracked in the local DB only.
    """
    q = select(TruckSchedule).where(
        TruckSchedule.status.notin_(["CANCELLED", "COMPLETED"])
    ).order_by(TruckSchedule.expected_arrival_dt.asc().nulls_last())
    result = await db.execute(q)
    schedules = result.scalars().all()

    return [
        {
            "schedule_id":        s.id,
            "schedule_ref":       s.schedule_ref,
            "expected_arrival_dt": s.expected_arrival_dt.isoformat() if s.expected_arrival_dt else None,
            "truck_plate":        s.truck_plate,
            "driver_name":        s.driver_name,
            "driver_license_no":  s.driver_license_no,
            "dealer_number":      s.dealer_number,
            "transporter_name":   s.transporter_name,
            "corridor_name":      s.corridor_name,
            "origin_region":      s.origin_region,
            "raw_material_type":  s.raw_material_type,
            "odoo_po_name":       s.odoo_po_name,
            "truck_status":       s.status,
            "allocation_status":  s.allocation_status,
        }
        for s in schedules
    ]


# ── GET /api/schedules/{id} ───────────────────────────────────────────────────

@router.get("/{schedule_id}", response_model=TruckScheduleRead)
async def get_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    schedule = await _get_or_404(schedule_id, db)
    return TruckScheduleRead.model_validate(schedule)


# ── PATCH /api/schedules/{id}/confirm-details ─────────────────────────────────

@router.patch("/{schedule_id}/confirm-details")
async def confirm_details(
    schedule_id: int,
    payload: TruckScheduleDetail,
    db: AsyncSession = Depends(get_db),
):
    """Add truck plate, driver info, and actual capacity (transporter pre-advice)."""
    schedule = await _get_or_404(schedule_id, db)

    if payload.truck_plate:
        schedule.truck_plate = payload.truck_plate
    if payload.driver_name:
        schedule.driver_name = payload.driver_name
    if payload.driver_phone:
        schedule.driver_phone = payload.driver_phone
    if payload.actual_capacity_tonnes:
        schedule.actual_capacity_tonnes = payload.actual_capacity_tonnes
    if payload.notes:
        schedule.notes = payload.notes

    # Promote to PRE_CONFIRMED if we now have truck details
    if schedule.truck_plate and schedule.status == TSS.EXPECTED:
        schedule.status = TSS.PRE_CONFIRMED

    await db.commit()

    # Broadcast SSE update
    broadcast_sse("schedule_updated", {
        "schedule_id": schedule_id,
        "schedule_ref": schedule.schedule_ref,
        "status": schedule.status,
        "truck_plate": schedule.truck_plate,
    })

    return {"ok": True, "schedule_ref": schedule.schedule_ref, "status": schedule.status}


# ── PATCH /api/schedules/{id}/arrived ────────────────────────────────────────

@router.patch("/{schedule_id}/arrived")
async def mark_arrived(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Mark truck as physically arrived at Kimbiji Plant."""
    schedule = await _get_or_404(schedule_id, db)

    schedule.status = TSS.ARRIVED
    schedule.actual_arrival_dt = datetime.now(timezone.utc)
    await db.commit()

    broadcast_sse("truck_arrived", {
        "schedule_id": schedule_id,
        "schedule_ref": schedule.schedule_ref,
        "truck_plate": schedule.truck_plate,
        "origin_region": schedule.origin_region,
    })

    return {"ok": True, "schedule_ref": schedule.schedule_ref, "arrived_at": schedule.actual_arrival_dt}


# ── PATCH /api/schedules/{id}/dispatch ───────────────────────────────────────

@router.patch("/{schedule_id}/dispatch")
async def mark_dispatched(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Mark truck as loaded and dispatched."""
    schedule = await _get_or_404(schedule_id, db)

    schedule.status = TSS.DISPATCHED
    schedule.dispatched_at = datetime.now(timezone.utc)
    schedule.allocation_status = AllocationStatus.DISPATCHED

    result = await db.execute(
        select(AllocationProposal).where(
            AllocationProposal.schedule_id == schedule_id,
            AllocationProposal.status == "CONFIRMED",
        ).limit(1)
    )
    proposal = result.scalar_one_or_none()
    if proposal:
        proposal.dispatched_at = datetime.now(timezone.utc)
        proposal.status = "DISPATCHED"

    await db.commit()

    broadcast_sse("truck_dispatched", {
        "schedule_id": schedule_id,
        "schedule_ref": schedule.schedule_ref,
        "truck_plate": schedule.truck_plate,
    })

    return {"ok": True, "schedule_ref": schedule.schedule_ref}


# ── POST /api/schedules/{id}/rematch ─────────────────────────────────────────

@router.post("/{schedule_id}/rematch")
async def force_rematch(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Force re-run of the matching engine for this schedule."""
    schedule = await _get_or_404(schedule_id, db)

    from app.services.matching_engine import MatchingEngine
    from app.models.matching_event import MatchTrigger

    engine = MatchingEngine(db)
    proposals = await engine.rematch(schedule, trigger=MatchTrigger.MANUAL)
    await db.commit()

    broadcast_sse("proposals_updated", {
        "schedule_id": schedule_id,
        "schedule_ref": schedule.schedule_ref,
        "proposals_count": len(proposals),
    })

    return {
        "ok": True,
        "schedule_ref": schedule.schedule_ref,
        "proposals_generated": len(proposals),
    }


# ── GET /api/schedules/feed — SSE ────────────────────────────────────────────

@router.get("/feed")
async def sse_feed():
    """
    Server-Sent Events stream for live dashboard updates.
    The browser connects once and receives push events as trucks are
    allocated, arrive, or proposals are confirmed.
    """
    import uuid
    client_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_clients[client_id] = queue

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial connection confirmation
        yield f"data: {json.dumps({'type': 'connected', 'client_id': client_id})}\n\n"
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat — keep connection alive
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _sse_clients.pop(client_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(schedule_id: int, db: AsyncSession) -> TruckSchedule:
    result = await db.execute(
        select(TruckSchedule).where(TruckSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return schedule
