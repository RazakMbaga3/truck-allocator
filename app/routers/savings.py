"""app/routers/savings.py — Savings KPI endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AllocationStatus, TruckSchedule
from app.models.truck_schedule import TruckScheduleStatus as TSS
from app.models.savings_ledger import SavingsLedger

router = APIRouter(prefix="/api/savings", tags=["savings"])


@router.get("/summary")
async def savings_summary(db: AsyncSession = Depends(get_db)):
    """MTD savings summary — powers the KPI header on the Schedule page."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_key = now.strftime("%Y-%m")

    # ── KPI 1: Inbound Trucks ─────────────────────────────────────────────────
    # All trucks currently en route (imported but not yet arrived or terminal)
    inbound_result = await db.execute(
        select(func.count(TruckSchedule.id)).where(
            TruckSchedule.status.in_([TSS.EXPECTED, TSS.PRE_CONFIRMED]),
        )
    )

    # ── KPI 2: Unallocated ────────────────────────────────────────────────────
    # En-route or arrived trucks that still have no cement order assigned
    unallocated_result = await db.execute(
        select(func.count(TruckSchedule.id)).where(
            TruckSchedule.status.in_([TSS.EXPECTED, TSS.PRE_CONFIRMED, TSS.ARRIVED]),
            TruckSchedule.allocation_status == AllocationStatus.UNALLOCATED,
        )
    )

    # ── KPI 3: At Plant ───────────────────────────────────────────────────────
    # Trucks physically at Kimbiji gate — need loading action now
    at_plant_result = await db.execute(
        select(func.count(TruckSchedule.id)).where(
            TruckSchedule.status == TSS.ARRIVED,
        )
    )

    # ── KPI 4: Dispatched This Month ─────────────────────────────────────────
    # Trucks that left the plant with cement this calendar month
    dispatched_mtd_result = await db.execute(
        select(func.count(TruckSchedule.id)).where(
            TruckSchedule.allocation_status.in_([
                AllocationStatus.LOADED,
                AllocationStatus.DISPATCHED,
            ]),
            TruckSchedule.dispatched_at >= month_start,
        )
    )

    # Total terminal this month (dispatched + released) for completion %
    total_terminal_result = await db.execute(
        select(func.count(TruckSchedule.id)).where(
            TruckSchedule.allocation_status.in_([
                AllocationStatus.LOADED,
                AllocationStatus.DISPATCHED,
                AllocationStatus.RELEASED,
            ]),
            TruckSchedule.upload_date >= month_start,
        )
    )

    # ── Savings ledger (financial KPIs) ───────────────────────────────────────
    ledger_result = await db.execute(
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
    row = ledger_result.one()

    hist = await db.execute(
        select(
            func.count(SavingsLedger.id).label("all_trips"),
            func.sum(SavingsLedger.net_savings_tzs).label("all_savings"),
        )
    )
    hrow = hist.one()

    inbound          = inbound_result.scalar() or 0
    unallocated      = unallocated_result.scalar() or 0
    at_plant         = at_plant_result.scalar() or 0
    dispatched_mtd   = dispatched_mtd_result.scalar() or 0
    total_terminal   = total_terminal_result.scalar() or 0

    completion_pct = round(
        dispatched_mtd / total_terminal * 100, 1
    ) if total_terminal else 0.0

    return {
        "month_key": month_key,
        # ── Schedule page KPI cards ──
        "trucks_inbound":           inbound,
        "trucks_unallocated":       unallocated,
        "trucks_at_plant":          at_plant,
        "trucks_dispatched_mtd":    dispatched_mtd,
        "dispatch_completion_pct":  completion_pct,
        # ── Legacy aliases (kept so old JS references don't break) ──
        "trucks_expected_next_7d":  inbound,
        "draft_load_plans":         unallocated,
        "waiting_loading_allocations": at_plant,
        "loaded_allocations_mtd":   dispatched_mtd,
        "load_plan_completion_pct": completion_pct,
        # ── Financial KPIs ──
        "confirmed_proposals_mtd":  row.trip_count or 0,
        "net_savings_tzs":          round(row.net_savings or 0, 2),
        "fresh_freight_avoided_tzs": round(row.fresh_avoided or 0, 2),
        "return_freight_paid_tzs":  round(row.return_paid or 0, 2),
        "holding_cost_saved_tzs":   round(row.holding_saved or 0, 2),
        "total_tonnes_mtd":         round(row.total_tonnes or 0, 2),
        "avg_utilization_pct":      round(row.avg_utilization or 0, 1),
        "total_orders_mtd":         row.total_orders or 0,
        "all_time_trips":           hrow.all_trips or 0,
        "all_time_savings_tzs":     round(hrow.all_savings or 0, 2),
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
