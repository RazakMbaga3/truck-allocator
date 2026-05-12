"""app/routers/savings.py — Savings KPI endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AllocationStatus, TruckSchedule
from app.models.savings_ledger import SavingsLedger
from app.models.truck_allocation import TruckAllocation, TruckAllocationStatus

router = APIRouter(prefix="/api/savings", tags=["savings"])


@router.get("/summary")
async def savings_summary(db: AsyncSession = Depends(get_db)):
    """MTD savings summary — powers the KPI header."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_key = now.strftime("%Y-%m")
    next_7d = now + timedelta(days=7)

    result = await db.execute(
        select(
            func.count(SavingsLedger.id).label("trip_count"),
            func.sum(SavingsLedger.net_savings_tzs).label("net_savings"),
            func.sum(SavingsLedger.fresh_freight_avoided_tzs).label("fresh_avoided"),
            func.sum(SavingsLedger.return_freight_paid_tzs).label("return_paid"),
            func.sum(SavingsLedger.holding_cost_saved_tzs).label("holding_saved"),
            func.sum(SavingsLedger.allocated_tonnes).label("total_tonnes"),
            func.avg(SavingsLedger.capacity_utilization_pct).label("avg_utilization"),
            func.sum(SavingsLedger.number_of_orders).label("total_orders"),
        ).where(SavingsLedger.month_key == month_key)
    )
    row = result.one()

    # Historical total (all time)
    hist = await db.execute(
        select(
            func.count(SavingsLedger.id).label("all_trips"),
            func.sum(SavingsLedger.net_savings_tzs).label("all_savings"),
        )
    )
    hrow = hist.one()

    expected_result = await db.execute(
        select(func.count(TruckSchedule.id)).where(
            TruckSchedule.expected_arrival_dt <= next_7d,
            TruckSchedule.allocation_status.notin_([
                AllocationStatus.WAITING_LOADING,
                AllocationStatus.RELEASED,
                AllocationStatus.LOADED,
            ]),
        )
    )
    draft_result = await db.execute(
        select(func.count(TruckAllocation.id)).where(
            TruckAllocation.status == TruckAllocationStatus.DRAFT
        )
    )
    released_result = await db.execute(
        select(func.count(TruckAllocation.id)).where(
            TruckAllocation.status.in_([
                TruckAllocationStatus.WAITING_LOADING,
                TruckAllocationStatus.RELEASED,
            ])
        )
    )
    loaded_result = await db.execute(
        select(func.count(TruckAllocation.id)).where(
            TruckAllocation.status == TruckAllocationStatus.LOADED,
            TruckAllocation.loaded_at >= month_start,
        )
    )

    drafts_open = draft_result.scalar() or 0
    released_open = released_result.scalar() or 0
    loaded_mtd = loaded_result.scalar() or 0
    active_load_plans = drafts_open + released_open

    return {
        "month_key": month_key,
        "trucks_expected_next_7d": expected_result.scalar() or 0,
        "draft_load_plans": drafts_open,
        "released_awaiting_loading": released_open,
        "waiting_loading_allocations": released_open,
        "loaded_allocations_mtd": loaded_mtd,
        "active_load_plans": active_load_plans,
        "load_plan_completion_pct": round(
            loaded_mtd / (active_load_plans + loaded_mtd) * 100,
            1,
        ) if (active_load_plans + loaded_mtd) else 0.0,
        "confirmed_proposals_mtd": row.trip_count or 0,
        "net_savings_tzs": round(row.net_savings or 0, 2),
        "fresh_freight_avoided_tzs": round(row.fresh_avoided or 0, 2),
        "return_freight_paid_tzs": round(row.return_paid or 0, 2),
        "holding_cost_saved_tzs": round(row.holding_saved or 0, 2),
        "total_tonnes_mtd": round(row.total_tonnes or 0, 2),
        "avg_utilization_pct": round(row.avg_utilization or 0, 1),
        "total_orders_mtd": row.total_orders or 0,
        "all_time_trips": hrow.all_trips or 0,
        "all_time_savings_tzs": round(hrow.all_savings or 0, 2),
    }


@router.get("/by-corridor")
async def savings_by_corridor(db: AsyncSession = Depends(get_db)):
    """Savings breakdown by return corridor."""
    result = await db.execute(
        select(
            SavingsLedger.corridor_name,
            func.count(SavingsLedger.id).label("trip_count"),
            func.sum(SavingsLedger.net_savings_tzs).label("net_savings"),
            func.avg(SavingsLedger.capacity_utilization_pct).label("avg_utilization"),
            func.sum(SavingsLedger.allocated_tonnes).label("total_tonnes"),
        ).group_by(SavingsLedger.corridor_name)
        .order_by(func.sum(SavingsLedger.net_savings_tzs).desc())
    )
    rows = result.all()
    return [
        {
            "corridor_name": r.corridor_name or "UNKNOWN",
            "trip_count": r.trip_count,
            "net_savings_tzs": round(r.net_savings or 0, 2),
            "avg_utilization_pct": round(r.avg_utilization or 0, 1),
            "total_tonnes": round(r.total_tonnes or 0, 1),
        }
        for r in rows
    ]
