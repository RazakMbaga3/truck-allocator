"""
app/routers/proposals.py — AllocationProposal API endpoints.

GET   /api/proposals                    — List proposals
GET   /api/proposals/{id}               — Detail with items + AI reasoning
PATCH /api/proposals/{id}/confirm       — Confirm → write Odoo, update statuses
PATCH /api/proposals/{id}/reject        — Reject proposal
GET   /api/proposals/{id}/ai-reasoning  — Poll for async Claude output
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AllocationProposal,
    AllocationStatus,
    CementOrder,
    OrderAllocationStatus,
    ProposalStatus,
    TruckSchedule,
)
from app.models.allocation_proposal import ProposalItem
from app.schemas.allocation_proposal import (
    AllocationProposalListItem,
    AllocationProposalRead,
    ConfirmProposalRequest,
    ProposalItemRead,
    RejectProposalRequest,
)

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


# ── GET /api/proposals ────────────────────────────────────────────────────────

@router.get("", response_model=list[AllocationProposalListItem])
async def list_proposals(
    status: str | None = Query(None, description="proposed | confirmed | dispatched | completed | rejected"),
    schedule_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(AllocationProposal).options(
        selectinload(AllocationProposal.schedule),
        selectinload(AllocationProposal.items).selectinload(ProposalItem.cement_order),
    )
    if status:
        q = q.where(AllocationProposal.status == status.upper())
    if schedule_id:
        q = q.where(AllocationProposal.schedule_id == schedule_id)
    q = q.order_by(AllocationProposal.capacity_utilization_pct.desc())

    result = await db.execute(q)
    proposals = result.scalars().all()

    items = []
    for p in proposals:
        item = AllocationProposalListItem.model_validate(p)
        s = p.schedule
        if s:
            item.transporter_name    = s.transporter_name
            item.driver_name         = s.driver_name
            item.driver_license_no   = s.driver_license_no
            item.dealer_number       = s.dealer_number
            item.truck_plate         = s.truck_plate
            item.origin_region       = s.origin_region
            item.raw_material_type   = s.raw_material_type
            item.expected_arrival_dt = s.expected_arrival_dt
            item.corridor_name       = s.corridor_name
            item.schedule_ref        = s.schedule_ref

        enriched_items = []
        for pi in p.items:
            item_read = ProposalItemRead.model_validate(pi)
            order = pi.cement_order
            if order:
                item_read.order_name      = order.odoo_order_name
                item_read.customer_name   = order.customer_name
                item_read.order_date      = order.requested_delivery_dt or order.created_at
                item_read.product_name    = order.product_name
                item_read.quantity_tonnes = order.quantity_tonnes
                item_read.delivery_zone   = order.delivery_zone
                item_read.delivery_region = order.delivery_region
            enriched_items.append(item_read)
        item.items = enriched_items

        items.append(item)
    return items


# ── GET /api/proposals/{id} ───────────────────────────────────────────────────

@router.get("/{proposal_id}", response_model=AllocationProposalRead)
async def get_proposal(proposal_id: int, db: AsyncSession = Depends(get_db)):
    proposal = await _get_or_404(proposal_id, db, load_items=True)

    # Enrich items with order info
    read = AllocationProposalRead.model_validate(proposal)
    for item_read, item in zip(read.items, proposal.items):
        order = item.cement_order
        item_read.order_name = order.odoo_order_name if order else None
        item_read.customer_name = order.customer_name if order else None
        item_read.delivery_region = order.delivery_region if order else None

    return read


# ── PATCH /api/proposals/{id}/confirm ────────────────────────────────────────

@router.patch("/{proposal_id}/confirm")
async def confirm_proposal(
    proposal_id: int,
    body: ConfirmProposalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm an allocation proposal:
    1. AllocationProposal.status → CONFIRMED
    2. TruckSchedule.allocation_status → CONFIRMED (truck disappears from available list)
    3. CementOrder.allocation_status → ALLOCATED for each order in the proposal
    4. Reject sibling proposals for the same schedule
    5. Create Odoo stock.picking for each order (async, non-blocking)
    6. Push SSE event to all dashboard clients
    """
    proposal = await _get_or_404(proposal_id, db, load_items=True)

    if proposal.status == ProposalStatus.CONFIRMED:
        return {"ok": True, "message": "Already confirmed", "proposal_ref": proposal.proposal_ref}

    if proposal.status not in (ProposalStatus.PROPOSED,):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm proposal in status '{proposal.status}'",
        )

    now = datetime.now(timezone.utc)

    # ── 1. Confirm this proposal ──────────────────────────────────
    proposal.status = ProposalStatus.CONFIRMED
    proposal.confirmed_by = body.confirmed_by
    proposal.confirmed_at = now

    # ── 2. Update TruckSchedule ───────────────────────────────────
    result = await db.execute(
        select(TruckSchedule).where(TruckSchedule.id == proposal.schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if schedule:
        schedule.allocation_status = AllocationStatus.CONFIRMED

    # ── 3. Mark cement orders as ALLOCATED ───────────────────────
    order_ids = [item.cement_order_id for item in proposal.items]
    if order_ids:
        result2 = await db.execute(
            select(CementOrder).where(CementOrder.id.in_(order_ids))
        )
        orders = result2.scalars().all()
        for order in orders:
            order.allocation_status = OrderAllocationStatus.ALLOCATED

    # ── 4. Reject sibling proposals ───────────────────────────────
    result3 = await db.execute(
        select(AllocationProposal).where(
            AllocationProposal.schedule_id == proposal.schedule_id,
            AllocationProposal.id != proposal_id,
            AllocationProposal.status == ProposalStatus.PROPOSED,
        )
    )
    siblings = result3.scalars().all()
    for sibling in siblings:
        sibling.status = ProposalStatus.REJECTED

    await db.commit()

    # ── 5. Odoo write-back (non-blocking) ─────────────────────────
    import asyncio
    asyncio.create_task(_write_odoo_pickings(proposal_id))

    # ── 6. SSE broadcast ──────────────────────────────────────────
    from app.routers.schedules import broadcast_sse
    broadcast_sse("truck_allocated", {
        "schedule_id": proposal.schedule_id,
        "schedule_ref": schedule.schedule_ref if schedule else "",
        "proposal_id": proposal_id,
        "proposal_ref": proposal.proposal_ref,
        "confirmed_by": body.confirmed_by,
    })

    return {
        "ok": True,
        "proposal_ref": proposal.proposal_ref,
        "schedule_ref": schedule.schedule_ref if schedule else None,
        "orders_allocated": len(order_ids),
        "capacity_utilization_pct": proposal.capacity_utilization_pct,
    }


# ── PATCH /api/proposals/{id}/reject ─────────────────────────────────────────

@router.patch("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    body: RejectProposalRequest,
    db: AsyncSession = Depends(get_db),
):
    proposal = await _get_or_404(proposal_id, db)
    proposal.status = ProposalStatus.REJECTED
    await db.commit()
    return {"ok": True, "proposal_ref": proposal.proposal_ref}


# ── GET /api/proposals/{id}/ai-reasoning ─────────────────────────────────────

@router.get("/{proposal_id}/ai-reasoning")
async def get_ai_reasoning(proposal_id: int, db: AsyncSession = Depends(get_db)):
    """Poll endpoint for async Claude AI reasoning."""
    proposal = await _get_or_404(proposal_id, db)
    return {
        "proposal_id": proposal_id,
        "ai_reasoning": proposal.ai_reasoning,
        "ai_warnings": proposal.ai_warnings,
        "ai_recommendation": proposal.ai_recommendation,
        "ready": proposal.ai_reasoning is not None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(
    proposal_id: int, db: AsyncSession, load_items: bool = False
) -> AllocationProposal:
    q = select(AllocationProposal).where(AllocationProposal.id == proposal_id)
    if load_items:
        q = q.options(
            selectinload(AllocationProposal.items).selectinload(
                __import__("app.models.allocation_proposal", fromlist=["ProposalItem"]).ProposalItem.cement_order
            )
        )
    result = await db.execute(q)
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return proposal


async def _write_odoo_pickings(proposal_id: int) -> None:
    """Create stock.picking records in Odoo for each item in the confirmed proposal."""
    import asyncio as aio
    try:
        from app.database import AsyncSessionLocal
        from app.services.odoo_sync import OdooClient
        from sqlalchemy.orm import selectinload as sload

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AllocationProposal)
                .where(AllocationProposal.id == proposal_id)
                .options(sload(AllocationProposal.items).sload(
                    __import__("app.models.allocation_proposal", fromlist=["ProposalItem"]).ProposalItem.cement_order
                ))
            )
            proposal = result.scalar_one_or_none()
            if not proposal:
                return

            result2 = await db.execute(
                select(TruckSchedule).where(TruckSchedule.id == proposal.schedule_id)
            )
            schedule = result2.scalar_one_or_none()

            client = OdooClient()
            picking_ids: list[int] = []

            for item in proposal.items:
                order = item.cement_order
                if not order or not order.customer_odoo_id:
                    continue

                # Get product_id from order
                product_id = None
                if order.odoo_order_id:
                    try:
                        so_lines = client._execute(
                            "sale.order.line", "search_read",
                            [["order_id", "=", order.odoo_order_id]],
                            {"fields": ["product_id"], "limit": 1},
                        )
                        if so_lines:
                            product_id = so_lines[0]["product_id"][0]
                    except Exception:
                        pass

                if not product_id:
                    continue

                picking_id = await aio.to_thread(
                    client.create_stock_picking,
                    order.odoo_order_id,
                    order.customer_odoo_id,
                    product_id,
                    item.allocated_tonnes * 20,  # convert to bags (50kg)
                    schedule.schedule_ref if schedule else "UNKNOWN",
                    proposal.proposal_ref,
                )

                if picking_id:
                    item.odoo_picking_id = picking_id
                    picking_ids.append(picking_id)
                    # Confirm the picking
                    await aio.to_thread(client.confirm_stock_picking, picking_id)

            proposal.odoo_picking_ids = picking_ids
            await db.commit()

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            "Odoo write-back failed for proposal %d: %s", proposal_id, e
        )
