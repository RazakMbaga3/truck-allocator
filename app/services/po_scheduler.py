"""
app/services/po_scheduler.py — PO → TruckSchedule conversion.

The proactive core of the allocator: when a raw material Purchase Order
is confirmed in Odoo, this service creates TruckSchedule records — one
per estimated truck — immediately, days before the trucks arrive.

Key intelligence:
  - Identify transporter from PO partner_id
  - Determine origin_region from transporter corridor or Odoo region field
  - Estimate truck count = ceil(po_qty_tonnes / avg_truck_capacity)
  - Spread ETAs across expected_arrival_dt ± variance
  - Generate schedule_ref: SCHED-YYYYMMDD-NNN
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.data.tanzania_regions import RM_ORIGIN_TO_CORRIDOR, normalise_city
from app.models import (
    AllocationStatus,
    Transporter,
    TruckSchedule,
    TruckScheduleStatus,
)
from app.services.route_calculator import get_corridor_for_origin, get_route_waypoints

logger = logging.getLogger(__name__)
settings = get_settings()

# RM item code → material type name (confirmed from LCL Odoo data)
RM_ITEM_CODE_MAP: dict[str, str] = {
    "RM000001": "COAL",
    "RM000003": "GYPSUM",
    "RM000004": "IRON_ORE",
    "RM000014": "CLINKER",
}

# Default trucks per material type per day (from GRN stats: 13,299/year)
# Used for estimating truck count when exact PO qty is unavailable
DAILY_TRUCK_RATES: dict[str, float] = settings.daily_truck_rates


class POScheduler:
    """
    Converts confirmed Odoo RM purchase.order dicts into TruckSchedule records.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_new_po(
        self,
        po: dict,
        transporter: Transporter | None = None,
    ) -> list[TruckSchedule]:
        """
        Process one confirmed RM PO and create TruckSchedule records.

        Args:
            po: Dict from OdooClient.fetch_rm_purchase_orders() with keys:
                id, name, scheduled_date, partner_id, _lines, _eligible
            transporter: Pre-loaded Transporter ORM object (or None — will be looked up)

        Returns:
            List of newly created TruckSchedule records.
        """
        if not self._should_process_po(po):
            return []

        # Resolve transporter
        if transporter is None:
            transporter = await self._resolve_transporter(po)

        # Determine material type
        material_type = self._get_material_type(po)

        # Determine origin region
        origin_region = self._get_origin_region(po, transporter)

        # Estimate total tonnage from PO lines
        total_qty_tonnes = self._get_po_tonnes(po)

        # Estimate truck count
        avg_capacity = (
            transporter.avg_truck_capacity_tonnes
            if transporter else settings.avg_truck_capacity_tonnes
        )
        truck_count = self._estimate_truck_count(total_qty_tonnes, avg_capacity)

        # Parse expected arrival date
        expected_arrival = self._parse_arrival_date(po)

        # Determine return corridor
        corridor = get_corridor_for_origin(origin_region)
        return_route = get_route_waypoints("KIGAMBONI", origin_region)
        max_detour = settings.corridor_max_detour_km.get(corridor, settings.default_max_detour_km)

        # Parse PO date
        po_date = None
        if po.get("date_order"):
            try:
                po_date = datetime.fromisoformat(
                    str(po["date_order"]).replace("Z", "+00:00")
                )
            except Exception:
                pass

        # Create one TruckSchedule per estimated truck
        schedules: list[TruckSchedule] = []
        for i in range(truck_count):
            ref = await self._next_schedule_ref(expected_arrival)
            # Spread ETAs: trucks may arrive on the same day or ±1 day
            etas_spread = timedelta(hours=i * 4)  # 4h apart for multiple trucks
            eta = (expected_arrival + etas_spread) if expected_arrival else None

            schedule = TruckSchedule(
                schedule_ref=ref,
                odoo_po_id=po["id"],
                odoo_po_name=po["name"],
                transporter_id=transporter.id if transporter else None,
                origin_region=origin_region,
                raw_material_type=material_type,
                estimated_qty_tonnes=total_qty_tonnes / truck_count if total_qty_tonnes > 0 else avg_capacity,
                estimated_truck_count=truck_count,
                corridor_name=corridor,
                max_detour_km=max_detour,
                po_date=po_date,
                expected_arrival_dt=eta,
                status=TruckScheduleStatus.EXPECTED,
                allocation_status=AllocationStatus.UNMATCHED,
            )
            schedule.return_route = return_route

            self.session.add(schedule)
            schedules.append(schedule)

        await self.session.flush()  # get IDs assigned

        logger.info(
            "Created %d TruckSchedule records for PO %s "
            "(origin=%s, material=%s, trucks=%d)",
            len(schedules), po["name"], origin_region, material_type, truck_count,
        )

        # Trigger matching for each new schedule (non-blocking)
        for schedule in schedules:
            asyncio.create_task(self._trigger_match(schedule.id))

        return schedules

    # ── Private helpers ───────────────────────────────────────────

    def _should_process_po(self, po: dict) -> bool:
        """Guard: skip cancelled, draft, or already-tracked POs."""
        if po.get("state") not in ("purchase", "done"):
            return False
        if not po.get("_eligible", True):
            return False
        return True

    async def _resolve_transporter(self, po: dict) -> Transporter | None:
        """Find Transporter record by Odoo partner_id."""
        partner_id = None
        if po.get("partner_id"):
            partner_id = po["partner_id"][0] if isinstance(po["partner_id"], list) else po["partner_id"]

        if not partner_id:
            return None

        result = await self.session.execute(
            select(Transporter).where(Transporter.odoo_vendor_id == partner_id)
        )
        transporter = result.scalar_one_or_none()

        # If not found by odoo_vendor_id, try by vendor code
        if not transporter:
            # vendor code might be in PO name prefix — try to match by name
            partner_name = po.get("partner_id", [None, ""])[1] if isinstance(po.get("partner_id"), list) else ""
            if partner_name:
                result2 = await self.session.execute(
                    select(Transporter).where(
                        Transporter.name.ilike(f"%{partner_name[:20]}%")
                    ).limit(1)
                )
                transporter = result2.scalar_one_or_none()

        return transporter

    def _get_material_type(self, po: dict) -> str | None:
        """Determine RM material type from PO lines."""
        for line in po.get("_lines", []):
            product_info = line.get("product_id", [None, ""])
            if isinstance(product_info, list) and len(product_info) > 1:
                product_name = product_info[1].upper()
                for code, mtype in RM_ITEM_CODE_MAP.items():
                    if mtype in product_name:
                        return mtype
                # Try default_code match
                if "COAL" in product_name:
                    return "COAL"
                if "GYPSUM" in product_name or "GYP" in product_name:
                    return "GYPSUM"
                if "IRON" in product_name or "ORE" in product_name:
                    return "IRON_ORE"
                if "CLINKER" in product_name or "CLNK" in product_name:
                    return "CLINKER"
        return None

    def _get_origin_region(self, po: dict, transporter: Transporter | None) -> str:
        """
        Determine the origin region for the truck.
        Priority: transporter.origin_region > x_origin_region from PO > partner region normalised
        """
        # 1. Transporter has a known origin
        if transporter and transporter.origin_region:
            return transporter.origin_region

        # 2. PO has x_origin_region override
        if po.get("x_origin_region"):
            return str(po["x_origin_region"]).upper()

        # 3. Derive from partner region (res.partner.x_supplier_origin_region)
        partner_info = po.get("partner_id")
        if isinstance(partner_info, list) and len(partner_info) > 1:
            partner_name = partner_info[1]
            region = normalise_city(partner_name)
            if region:
                return region

        # 4. Default: DODOMA (most common RM origin — Iron Ore)
        material = self._get_material_type(po)
        if material == "CLINKER":
            return "TANGA"
        if material in ("COAL",):
            return "MBEYA"
        if material == "GYPSUM":
            return "KIRANJERANJE"
        if material == "IRON_ORE":
            return "DODOMA"
        return "DODOMA"

    def _get_po_tonnes(self, po: dict) -> float:
        """Sum all PO line quantities into approximate tonnes."""
        total = 0.0
        for line in po.get("_lines", []):
            qty = float(line.get("product_qty", 0) or 0)
            uom = (line.get("product_uom") or [None, ""])[1] if isinstance(
                line.get("product_uom"), list
            ) else str(line.get("product_uom", ""))
            uom_upper = uom.upper()
            if "MT" in uom_upper or "TONN" in uom_upper:
                total += qty
            elif "KG" in uom_upper:
                total += qty / 1000.0
            elif "BAG" in uom_upper or "UNIT" in uom_upper:
                total += qty * 50 / 1000.0  # 50kg bags
            else:
                total += qty  # assume tonnes
        return total if total > 0 else settings.avg_truck_capacity_tonnes

    def _estimate_truck_count(self, total_tonnes: float, avg_capacity: float) -> int:
        """ceil(total_tonnes / avg_capacity), minimum 1, maximum 20."""
        if total_tonnes <= 0 or avg_capacity <= 0:
            return 1
        return min(20, max(1, math.ceil(total_tonnes / avg_capacity)))

    def _parse_arrival_date(self, po: dict) -> datetime | None:
        """Parse scheduled/planned delivery date from PO dict."""
        raw = po.get("scheduled_date") or po.get("date_planned")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    async def _next_schedule_ref(self, expected_dt: datetime | None) -> str:
        """
        Generate next schedule_ref: SCHED-YYYYMMDD-NNN
        NNN is a 3-digit sequence number for that day.
        """
        date_str = (expected_dt or datetime.now(timezone.utc)).strftime("%Y%m%d")
        prefix = f"SCHED-{date_str}-"

        # Count existing schedules for this date prefix
        result = await self.session.execute(
            select(func.count(TruckSchedule.id)).where(
                TruckSchedule.schedule_ref.like(f"{prefix}%")
            )
        )
        count = result.scalar() or 0
        return f"{prefix}{count + 1:03d}"

    async def _trigger_match(self, schedule_id: int) -> None:
        """Non-blocking trigger to start matching engine for a new schedule."""
        try:
            # Import here to avoid circular at module level
            from app.services.matching_engine import MatchingEngine
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as match_session:
                engine = MatchingEngine(match_session)
                result = await match_session.execute(
                    select(TruckSchedule).where(TruckSchedule.id == schedule_id)
                )
                schedule = result.scalar_one_or_none()
                if schedule:
                    await engine.match(schedule)
                    await match_session.commit()
        except Exception as e:
            logger.error("Auto-match failed for schedule %d: %s", schedule_id, e)

    def estimate_daily_truck_rate(self, material_type: str) -> float:
        """Return expected daily truck arrivals for a material type."""
        return DAILY_TRUCK_RATES.get((material_type or "").upper(), 3.0)
