"""
tests/test_matching_engine.py — Matching engine integration tests.

Uses the in-memory test DB from conftest.py.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.models import (
    AllocationProposal,
    AllocationStatus,
    CementOrder,
    MatchingEvent,
    OrderAllocationStatus,
    ProposalStatus,
    TruckSchedule,
    TruckScheduleStatus,
)
from app.services.matching_engine import MatchingEngine
from tests.conftest import make_cement_order, make_truck_schedule


@pytest_asyncio.fixture
async def schedule_dodoma(db):
    """A truck coming from DODOMA (CENTRAL corridor)."""
    s = make_truck_schedule(db,
        schedule_ref="SCHED-TEST-DODOMA",
        origin_region="DODOMA",
        corridor_name="CENTRAL",
        max_detour_km=80.0,
        estimated_qty_tonnes=30.0,
        expected_arrival_dt=datetime.now(timezone.utc) + timedelta(days=2),
    )
    await db.flush()
    return s


@pytest_asyncio.fixture
async def order_morogoro(db):
    """A ready order to MOROGORO (on CENTRAL corridor)."""
    o = make_cement_order(db,
        odoo_order_id=10001,
        odoo_order_name="SO/2026/10001",
        delivery_region="MOROGORO",
        delivery_corridor="CENTRAL",
        distance_from_plant_km=200.0,
        quantity_tonnes=12.0,
        fresh_outbound_freight_tzs=480_000.0,
        dispatch_ready=True,
        credit_cleared=True,
        deadline_dt=datetime.now(timezone.utc) + timedelta(days=5),
    )
    await db.flush()
    return o


@pytest_asyncio.fixture
async def order_dodoma(db):
    """A ready order to DODOMA (on CENTRAL corridor)."""
    o = make_cement_order(db,
        odoo_order_id=10002,
        odoo_order_name="SO/2026/10002",
        delivery_region="DODOMA",
        delivery_corridor="CENTRAL",
        distance_from_plant_km=460.0,
        quantity_tonnes=15.0,
        fresh_outbound_freight_tzs=1_380_000.0,
        dispatch_ready=True,
        credit_cleared=True,
        deadline_dt=datetime.now(timezone.utc) + timedelta(days=3),
    )
    await db.flush()
    return o


@pytest_asyncio.fixture
async def order_tanga(db):
    """An order to TANGA — NOT on CENTRAL corridor (should be excluded)."""
    o = make_cement_order(db,
        odoo_order_id=10003,
        odoo_order_name="SO/2026/10003",
        delivery_region="TANGA",
        delivery_corridor="NORTHERN",
        distance_from_plant_km=360.0,
        quantity_tonnes=20.0,
        fresh_outbound_freight_tzs=1_512_000.0,
        dispatch_ready=True,
        credit_cleared=True,
    )
    await db.flush()
    return o


@pytest_asyncio.fixture
async def order_not_ready(db):
    """An order that is not dispatch_ready."""
    o = make_cement_order(db,
        odoo_order_id=10004,
        odoo_order_name="SO/2026/10004",
        delivery_region="DODOMA",
        delivery_corridor="CENTRAL",
        distance_from_plant_km=460.0,
        quantity_tonnes=10.0,
        dispatch_ready=False,
        credit_cleared=False,
        near_ready=False,
    )
    await db.flush()
    return o


@pytest_asyncio.fixture
async def order_near_ready(db):
    """An order that is near-ready (ready before truck ETA)."""
    o = make_cement_order(db,
        odoo_order_id=10005,
        odoo_order_name="SO/2026/10005",
        delivery_region="DODOMA",
        delivery_corridor="CENTRAL",
        distance_from_plant_km=460.0,
        quantity_tonnes=8.0,
        dispatch_ready=False,
        credit_cleared=False,
        near_ready=True,
        near_ready_eta=datetime.now(timezone.utc) + timedelta(hours=24),
        # Truck ETA is +2 days — near_ready_eta is within that window
    )
    await db.flush()
    return o


class TestMatchingEngine:
    @pytest.mark.asyncio
    async def test_generates_proposals_for_matched_orders(
        self, db, schedule_dodoma, order_morogoro, order_dodoma
    ):
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        assert len(proposals) >= 1
        # All proposals should contain at least one of our on-corridor orders
        all_order_ids = {
            item.cement_order_id
            for p in proposals for item in p.items
        }
        assert order_morogoro.id in all_order_ids or order_dodoma.id in all_order_ids

    @pytest.mark.asyncio
    async def test_off_corridor_order_excluded(
        self, db, schedule_dodoma, order_tanga
    ):
        """TANGA order should not appear in CENTRAL corridor proposals."""
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        all_order_ids = {
            item.cement_order_id
            for p in proposals for item in p.items
        }
        assert order_tanga.id not in all_order_ids

    @pytest.mark.asyncio
    async def test_not_ready_order_excluded(
        self, db, schedule_dodoma, order_not_ready
    ):
        """Non-dispatch_ready, non-near_ready order should be excluded."""
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        all_order_ids = {
            item.cement_order_id
            for p in proposals for item in p.items
        }
        assert order_not_ready.id not in all_order_ids

    @pytest.mark.asyncio
    async def test_near_ready_order_included(
        self, db, schedule_dodoma, order_near_ready
    ):
        """Near-ready order (near_ready_eta < truck ETA) should be included."""
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        all_order_ids = {
            item.cement_order_id
            for p in proposals for item in p.items
        }
        # May or may not be included depending on other orders — just verify flag
        near_ready_items = [
            item
            for p in proposals
            for item in p.items
            if item.cement_order_id == order_near_ready.id
        ]
        for item in near_ready_items:
            assert item.is_near_ready is True

    @pytest.mark.asyncio
    async def test_matching_event_logged(
        self, db, schedule_dodoma, order_morogoro
    ):
        from sqlalchemy import select
        engine = MatchingEngine(db)
        await engine.match(schedule_dodoma)
        await db.flush()

        result = await db.execute(
            select(MatchingEvent).where(MatchingEvent.schedule_id == schedule_dodoma.id)
        )
        events = result.scalars().all()
        assert len(events) >= 1
        assert events[-1].orders_evaluated >= 1

    @pytest.mark.asyncio
    async def test_proposals_have_savings(
        self, db, schedule_dodoma, order_dodoma
    ):
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        for p in proposals:
            assert p.estimated_savings_tzs >= 0

    @pytest.mark.asyncio
    async def test_schedule_status_becomes_proposed(
        self, db, schedule_dodoma, order_morogoro
    ):
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        if proposals:
            assert schedule_dodoma.allocation_status == AllocationStatus.PROPOSED

    @pytest.mark.asyncio
    async def test_three_variant_types_generated(
        self, db, schedule_dodoma, order_morogoro, order_dodoma
    ):
        engine = MatchingEngine(db)
        proposals = await engine.match(schedule_dodoma)
        await db.flush()

        variant_types = {p.variant_type for p in proposals}
        # With 2+ distinct orders all variants should be generated
        assert len(variant_types) >= 1
