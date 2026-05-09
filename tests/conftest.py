"""
tests/conftest.py — Shared pytest fixtures for the Smart Return Truck Allocator.

Uses a fresh in-memory SQLite database for each test session.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import create_app
from app.models import (
    AllocationStatus,
    CementOrder,
    OrderAllocationStatus,
    Transporter,
    TruckSchedule,
    TruckScheduleStatus,
)

# ── In-memory test DB ─────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Provide a clean DB session for each test (rolled back after)."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db) -> AsyncClient:
    """HTTP test client with injected test DB."""
    app = create_app()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Data factories ────────────────────────────────────────────────────────────

def make_transporter(session: AsyncSession, **kwargs) -> Transporter:
    defaults = {
        "name": "Test Transporter Ltd",
        "origin_region": "DODOMA",
        "avg_truck_capacity_tonnes": 30.0,
        "backhaul_willing": True,
        "reliability_score": 7.5,
        "active": True,
    }
    defaults.update(kwargs)
    t = Transporter(**defaults)
    session.add(t)
    return t


def make_truck_schedule(session: AsyncSession, **kwargs) -> TruckSchedule:
    from app.services.route_calculator import get_route_waypoints
    defaults = {
        "schedule_ref": f"SCHED-TEST-{id(kwargs):05d}",
        "origin_region": "DODOMA",
        "corridor_name": "CENTRAL",
        "estimated_qty_tonnes": 30.0,
        "estimated_truck_count": 1,
        "max_detour_km": 80.0,
        "expected_arrival_dt": datetime.now(timezone.utc) + timedelta(days=2),
        "status": TruckScheduleStatus.EXPECTED,
        "allocation_status": AllocationStatus.UNMATCHED,
    }
    defaults.update(kwargs)
    s = TruckSchedule(**defaults)
    s.return_route = get_route_waypoints("KIGAMBONI", defaults["origin_region"])
    session.add(s)
    return s


def make_cement_order(session: AsyncSession, **kwargs) -> CementOrder:
    defaults = {
        "odoo_order_id": id(kwargs),
        "odoo_order_name": f"SO/2026/{id(kwargs):05d}",
        "customer_name": "Test Customer",
        "delivery_region": "DODOMA",
        "delivery_corridor": "CENTRAL",
        "distance_from_plant_km": 460.0,
        "quantity_tonnes": 15.0,
        "quantity_bags": 300,
        "fresh_outbound_freight_tzs": 1_380_000.0,  # 460km × 15T × 200
        "deadline_dt": datetime.now(timezone.utc) + timedelta(days=5),
        "urgency_score": 5.0,
        "dispatch_ready": True,
        "credit_cleared": True,
        "partial_load_allowed": False,
        "loading_priority": 3,
        "return_load_eligible": True,
        "allocation_status": OrderAllocationStatus.UNALLOCATED,
    }
    defaults.update(kwargs)
    o = CementOrder(**defaults)
    session.add(o)
    return o
