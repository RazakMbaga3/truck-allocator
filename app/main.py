"""
app/main.py — FastAPI application factory.

Mounts:
  /api/schedules  — TruckSchedule API (incl. SSE /api/schedules/feed)
  /api/proposals  — AllocationProposal API
  /api/orders     — CementOrder API
  /api/health     — Odoo + DB connectivity check
  /               — Dashboard HTML (static files)
  /docs           — Swagger UI (dev only)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import create_tables
from app.logging_config import configure_logging, RequestLoggingMiddleware

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    logger.info("[OK] Database tables ready")

    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("[OK] Background scheduler started")
    except ImportError:
        logger.warning("Scheduler not available - background jobs disabled")

    yield

    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nyati Cement — Smart Return Truck Allocator",
        description=(
            "Proactive return-truck allocation system for Lake Cement Limited. "
            "Tracks inbound RM trucks from Purchase Order confirmation, "
            "matches them with cement delivery orders along the return route."
        ),
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routers ───────────────────────────────────────────────
    from app.routers.schedules import router as schedules_router
    from app.routers.proposals import router as proposals_router
    from app.routers.orders import router as orders_router
    from app.routers.savings import router as savings_router
    from app.routers.allocations import router as allocations_router

    app.include_router(schedules_router)
    app.include_router(proposals_router)
    app.include_router(orders_router)
    app.include_router(savings_router)
    app.include_router(allocations_router)

    # ── Health endpoint ───────────────────────────────────────────
    @app.get("/api/health", tags=["system"])
    async def health():
        import asyncio as aio
        from app.services.odoo_sync import OdooClient
        from app.database import engine

        client = OdooClient()
        odoo_status = await aio.to_thread(client.ping)

        db_ok = False
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False

        return {
            "status": "ok" if (odoo_status["connected"] and db_ok) else "degraded",
            "database": "ok" if db_ok else "error",
            "odoo": odoo_status,
            "version": "3.0.0",
        }

    # ── Routes info ───────────────────────────────────────────────
    @app.get("/api/routes", tags=["system"])
    async def get_routes():
        from app.data.tanzania_regions import CORRIDOR_WAYPOINTS, REGIONS
        return {
            "corridors": {
                name: {"waypoints": wps, "total_regions": len(wps)}
                for name, wps in CORRIDOR_WAYPOINTS.items()
            },
            "regions_count": len(REGIONS),
        }

    # ── Transporters list ─────────────────────────────────────────
    @app.get("/api/transporters", tags=["system"])
    async def list_transporters():
        from app.database import AsyncSessionLocal
        from app.models import Transporter
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Transporter).where(Transporter.active == True).order_by(Transporter.name)
            )
            transporters = result.scalars().all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "origin_region": t.origin_region,
                    "preferred_corridors": t.preferred_corridors,
                    "avg_capacity_tonnes": t.avg_truck_capacity_tonnes,
                    "reliability_score": t.reliability_score,
                }
                for t in transporters
            ]

    # ── Static files (dashboard) ──────────────────────────────────
    dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
    if os.path.exists(dashboard_dir):
        app.mount("/static", StaticFiles(directory=os.path.join(dashboard_dir, "static")), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_dashboard():
            return FileResponse(os.path.join(dashboard_dir, "index.html"))

        @app.get("/loadplan", include_in_schema=False)
        async def serve_loadplan():
            return FileResponse(os.path.join(dashboard_dir, "dispatch.html"))

        @app.get("/final", include_in_schema=False)
        async def serve_final():
            return FileResponse(os.path.join(dashboard_dir, "final.html"))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=True,
        log_level="info",
    )
