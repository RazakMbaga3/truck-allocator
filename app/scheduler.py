"""
app/scheduler.py — APScheduler background jobs.

3 jobs:
  ODOO_SYNC           — every 15 min: sync RM POs + Sale Orders from Odoo
  URGENCY_RESCORE     — every 60 min: recalculate urgency scores
  PRE_ARRIVAL_REMATCH — every 6 hours: re-run matching for trucks arriving within 24h
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="Africa/Dar_es_Salaam")

    _scheduler.add_job(
        job_odoo_sync,
        trigger=IntervalTrigger(minutes=settings.odoo_sync_interval_minutes),
        id="ODOO_SYNC",
        name="Odoo RM PO + SO Sync",
        replace_existing=True,
        misfire_grace_time=120,
    )

    _scheduler.add_job(
        job_urgency_rescore,
        trigger=IntervalTrigger(minutes=60),
        id="URGENCY_RESCORE",
        name="Urgency Score Refresh",
        replace_existing=True,
        misfire_grace_time=300,
    )

    _scheduler.add_job(
        job_pre_arrival_rematch,
        trigger=IntervalTrigger(hours=6),
        id="PRE_ARRIVAL_REMATCH",
        name="Pre-Arrival Re-Match",
        replace_existing=True,
        misfire_grace_time=600,
    )

    _scheduler.add_job(
        job_allocation_sync,
        trigger=IntervalTrigger(minutes=5),
        id="ALLOCATION_SYNC",
        name="Auto-Sync Allocation Status from Odoo",
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started: %d jobs — sync every %d min",
        len(_scheduler.get_jobs()),
        settings.odoo_sync_interval_minutes,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


async def job_odoo_sync() -> None:
    from app.database import AsyncSessionLocal
    from app.services.odoo_sync import OdooSyncService

    logger.info("JOB: ODOO_SYNC starting")
    async with AsyncSessionLocal() as session:
        try:
            svc = OdooSyncService(session)
            stats = await svc.run_full_sync()
            logger.info("ODOO_SYNC complete: %s", stats)
        except Exception as e:
            logger.error("ODOO_SYNC failed: %s", e)


async def job_urgency_rescore() -> None:
    from app.database import AsyncSessionLocal
    from app.models import CementOrder, OrderAllocationStatus
    from app.services.scoring import urgency_lookup
    from sqlalchemy import select

    logger.info("JOB: URGENCY_RESCORE starting")
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(CementOrder).where(
                    CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED
                )
            )
            orders = result.scalars().all()
            for order in orders:
                order.urgency_score = urgency_lookup(order.deadline_dt) * 10
            await session.commit()
            logger.info("URGENCY_RESCORE: updated %d orders", len(orders))
        except Exception as e:
            logger.error("URGENCY_RESCORE failed: %s", e)


async def job_allocation_sync() -> None:
    """
    Option B: Auto-sync allocation status by cross-referencing Odoo REST API
    truck plates with local TruckSchedule records. Runs every 5 minutes.
    """
    from app.database import AsyncSessionLocal
    from app.models import AllocationStatus, TruckSchedule
    from app.services.odoo_sync import OdooClient
    from app.routers.schedules import broadcast_sse
    from sqlalchemy import select

    logger.info("JOB: ALLOCATION_SYNC starting")
    client = OdooClient()

    try:
        so_rows = await asyncio.to_thread(client.fetch_sale_orders_rest, 90)
    except Exception as e:
        logger.error("ALLOCATION_SYNC: REST fetch failed: %s", e)
        return

    odoo_plates = {
        (r.get("truck_no") or "").replace(" ", "").upper()
        for r in so_rows
        if r.get("truck_no")
    }

    if not odoo_plates:
        logger.info("ALLOCATION_SYNC: no truck plates in Odoo SOs")
        return

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(TruckSchedule).where(
                    TruckSchedule.allocation_status == AllocationStatus.UNALLOCATED,
                    TruckSchedule.truck_plate.isnot(None),
                )
            )
            schedules = result.scalars().all()
            matched = 0
            for s in schedules:
                plate = (s.truck_plate or "").replace(" ", "").upper()
                if plate in odoo_plates:
                    s.allocation_status = AllocationStatus.WAITING_LOADING
                    broadcast_sse("schedule_updated", {
                        "schedule_id": s.id,
                        "allocation_status": s.allocation_status,
                        "truck_plate": s.truck_plate,
                    })
                    matched += 1
            if matched:
                await session.commit()
            logger.info("ALLOCATION_SYNC: matched and updated %d truck(s)", matched)
        except Exception as e:
            logger.error("ALLOCATION_SYNC failed: %s", e)


async def job_pre_arrival_rematch() -> None:
    from datetime import datetime, timedelta, timezone

    from app.database import AsyncSessionLocal
    from app.models import AllocationStatus, TruckSchedule
    from app.models.truck_schedule import TruckScheduleStatus
    from app.models.matching_event import MatchTrigger
    from app.services.matching_engine import MatchingEngine
    from sqlalchemy import select

    logger.info("JOB: PRE_ARRIVAL_REMATCH starting")
    cutoff = datetime.now(timezone.utc) + timedelta(hours=settings.rematch_before_eta_hours)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(TruckSchedule).where(
                    TruckSchedule.status.in_([TruckScheduleStatus.EXPECTED, TruckScheduleStatus.PRE_CONFIRMED]),
                    TruckSchedule.allocation_status.notin_([
                        AllocationStatus.WAITING_LOADING,
                        AllocationStatus.RELEASED,
                        AllocationStatus.LOADED,
                    ]),
                    TruckSchedule.expected_arrival_dt <= cutoff,
                )
            )
            schedules = result.scalars().all()

            engine = MatchingEngine(session)
            for schedule in schedules:
                try:
                    await engine.rematch(schedule, trigger=MatchTrigger.CRON)
                except Exception as e:
                    logger.error("Re-match failed for %s: %s", schedule.schedule_ref, e)

            await session.commit()
            logger.info("PRE_ARRIVAL_REMATCH: processed %d schedules", len(schedules))
        except Exception as e:
            logger.error("PRE_ARRIVAL_REMATCH failed: %s", e)
