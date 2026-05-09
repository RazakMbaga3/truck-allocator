"""
app/routers/orders.py — CementOrder API endpoints.

GET /api/orders                     — All synced orders
GET /api/orders/unallocated         — Orders awaiting a truck
GET /api/orders/near-ready          — Near-ready (not dispatch_ready but eligible by ETA)
GET /api/orders/by-corridor/{name}  — Orders filtered by corridor
POST /api/orders/sync               — Force full Odoo sync
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CementOrder, OrderAllocationStatus
from app.schemas.cement_order import CementOrderListItem, CementOrderRead

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=list[CementOrderListItem])
async def list_orders(
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CementOrder)
        .order_by(CementOrder.deadline_dt.asc().nulls_last())
        .limit(limit)
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/unallocated", response_model=list[CementOrderListItem])
async def list_unallocated(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CementOrder)
        .where(
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
            CementOrder.return_load_eligible == True,
        )
        .order_by(CementOrder.urgency_score.desc())
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/near-ready", response_model=list[CementOrderListItem])
async def list_near_ready(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CementOrder)
        .where(
            CementOrder.near_ready == True,
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
        )
        .order_by(CementOrder.near_ready_eta.asc().nulls_last())
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/by-corridor/{corridor}", response_model=list[CementOrderListItem])
async def list_by_corridor(corridor: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CementOrder)
        .where(
            CementOrder.delivery_corridor == corridor.upper(),
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
        )
        .order_by(CementOrder.urgency_score.desc())
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/{order_id}", response_model=CementOrderRead)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    result = await db.execute(select(CementOrder).where(CementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return CementOrderRead.model_validate(order)


@router.post("/sync")
async def sync_orders(db: AsyncSession = Depends(get_db)):
    """Force a full Odoo sync of purchase orders + sale orders."""
    from app.services.odoo_sync import OdooSyncService
    svc = OdooSyncService(db)
    stats = await svc.run_full_sync()
    return {"ok": True, "stats": stats}
