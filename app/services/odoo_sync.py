"""
app/services/odoo_sync.py — Odoo 15 XML-RPC integration.

OdooClient: thin XML-RPC wrapper for all Odoo reads and writes.
OdooSyncService: higher-level sync logic that writes to the local DB.

Odoo reference formats confirmed from LCL data:
  Purchase Orders: LPORD/YYYY/NNNNN
  GRNs:            CM/GRN/YYYY/NNNNN
  Sale Orders:     SO/YYYY/NNNNN
  Delivery Orders: DO/YYYY/NNNNN

RM item codes:
  COAL=RM000001  GYPSUM=RM000003  IRON_ORE=RM000004  CLINKER=RM000014
"""

from __future__ import annotations

import logging
import time
import xmlrpc.client
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.data.tanzania_regions import normalise_city
from app.models import (
    AllocationStatus,
    CementOrder,
    OrderAllocationStatus,
    Transporter,
    TruckSchedule,
    TruckScheduleStatus,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ── XML-RPC low-level client ──────────────────────────────────────────────────

class OdooClient:
    """
    Thin wrapper around Odoo 15 XML-RPC external API.

    Designed to be synchronous (xmlrpc.client is synchronous) but called
    from async context via asyncio.to_thread() in OdooSyncService.

    All methods return plain Python dicts/lists (no SQLAlchemy objects).
    """

    def __init__(self) -> None:
        self._url = settings.odoo_url
        self._db = settings.odoo_db
        self._username = settings.odoo_username
        self._password = settings.odoo_password
        self._uid: int | None = None

    def _common(self) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")

    def _models(self) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/object")

    def authenticate(self) -> int:
        """Authenticate and cache uid. Raises on failure."""
        uid = self._common().authenticate(
            self._db, self._username, self._password, {}
        )
        if not uid:
            raise ConnectionError(
                f"Odoo authentication failed for user '{self._username}' on db '{self._db}'"
            )
        self._uid = uid
        return uid

    def _uid_or_auth(self) -> int:
        if self._uid is None:
            self.authenticate()
        return self._uid  # type: ignore[return-value]

    def _execute(
        self,
        model: str,
        method: str,
        domain: list,
        kwargs: dict | None = None,
        retry: int = 2,
    ) -> list[dict]:
        """Search_read with retry on transport error."""
        uid = self._uid_or_auth()
        for attempt in range(retry + 1):
            try:
                return self._models().execute_kw(
                    self._db, uid, self._password,
                    model, method,
                    [domain],
                    kwargs or {},
                )
            except xmlrpc.client.Fault as e:
                # Odoo-level error (e.g. field not found) — don't retry
                logger.error("Odoo XML-RPC Fault [%s.%s]: %s", model, method, e.faultString)
                raise
            except Exception as e:
                if attempt < retry:
                    logger.warning("Odoo transport error (attempt %d): %s", attempt + 1, e)
                    time.sleep(2 ** attempt)
                else:
                    raise

        return []

    # ── READ: Purchase Orders ─────────────────────────────────────

    def fetch_rm_purchase_orders(self, since_date: datetime | None = None) -> list[dict]:
        """
        Fetch confirmed RM Purchase Orders not yet fully received.
        Filters: state=purchase, RM category products, not fully done.

        Returns dicts with keys:
          id, name, state, partner_id, scheduled_date, date_order,
          order_line, picking_ids, x_return_load_eligible (if exists)
        """
        domain: list = [
            ["state", "=", "purchase"],
        ]
        if since_date:
            domain.append(["write_date", ">=", since_date.strftime("%Y-%m-%d %H:%M:%S")])

        # Fetch PO headers
        try:
            pos = self._execute(
                "purchase.order", "search_read", domain,
                {
                    "fields": [
                        "id", "name", "state", "partner_id",
                        "date_planned", "date_order",
                        "order_line", "picking_ids",
                        "scheduled_date",
                    ],
                    "limit": 500,
                    "order": "date_order asc",
                }
            )
        except Exception as e:
            logger.error("Failed to fetch purchase orders: %s", e)
            return []

        # Try to fetch x_return_load_eligible — gracefully skip if field doesn't exist
        try:
            eligible_pos = self._execute(
                "purchase.order", "search_read",
                [["id", "in", [p["id"] for p in pos]], ["x_return_load_eligible", "=", True]],
                {"fields": ["id"]},
            )
            eligible_ids = {p["id"] for p in eligible_pos}
        except Exception:
            # Field doesn't exist yet — treat all as eligible
            eligible_ids = {p["id"] for p in pos}
            logger.warning("x_return_load_eligible field not found — treating all POs as eligible")

        # Enrich with line quantities
        for po in pos:
            po["_eligible"] = po["id"] in eligible_ids
            po["_lines"] = []
            if po.get("order_line"):
                try:
                    lines = self._execute(
                        "purchase.order.line", "search_read",
                        [["id", "in", po["order_line"]]],
                        {"fields": ["product_id", "product_qty", "product_uom", "price_unit"]},
                    )
                    po["_lines"] = lines
                except Exception as e:
                    logger.warning("Could not fetch PO lines for %s: %s", po["name"], e)

        return [p for p in pos if p["_eligible"]]

    # ── READ: RM Receipts ─────────────────────────────────────────

    def fetch_rm_receipts(self, po_names: list[str]) -> list[dict]:
        """
        Track stock.picking (receipts) for RM POs.
        When receipt state = 'assigned' → truck is near/at plant.
        When receipt state = 'done'     → raw materials received.
        """
        if not po_names:
            return []
        try:
            return self._execute(
                "stock.picking", "search_read",
                [
                    ["picking_type_code", "=", "incoming"],
                    ["origin", "in", po_names],
                    ["state", "in", ["assigned", "done", "waiting", "confirmed"]],
                ],
                {"fields": ["id", "origin", "state", "scheduled_date", "partner_id", "name"]},
            )
        except Exception as e:
            logger.error("Failed to fetch RM receipts: %s", e)
            return []

    # ── READ: Sale Orders ─────────────────────────────────────────

    def fetch_sale_orders(self, since_date: datetime | None = None) -> list[dict]:
        """
        Fetch confirmed cement sale orders not yet fully delivered.
        """
        domain: list = [
            ["state", "in", ["sale", "done"]],
        ]
        if since_date:
            domain.append(["write_date", ">=", since_date.strftime("%Y-%m-%d %H:%M:%S")])

        try:
            sos = self._execute(
                "sale.order", "search_read", domain,
                {
                    "fields": [
                        "id", "name", "state", "partner_id",
                        "commitment_date", "amount_total",
                        "order_line", "picking_ids",
                    ],
                    "limit": 1000,
                    "order": "commitment_date asc",
                }
            )
        except Exception as e:
            logger.error("Failed to fetch sale orders: %s", e)
            return []

        # Fetch x_dispatch_ready / x_credit_cleared if they exist
        for so in sos:
            so["_dispatch_ready"] = False
            so["_credit_cleared"] = False
            so["_loading_priority"] = 3
        try:
            extra = self._execute(
                "sale.order", "search_read",
                [["id", "in", [s["id"] for s in sos]]],
                {"fields": ["id", "x_dispatch_ready", "x_credit_cleared", "x_loading_priority"]},
            )
            extra_map = {e["id"]: e for e in extra}
            for so in sos:
                e = extra_map.get(so["id"], {})
                so["_dispatch_ready"] = bool(e.get("x_dispatch_ready", False))
                so["_credit_cleared"] = bool(e.get("x_credit_cleared", False))
                so["_loading_priority"] = int(e.get("x_loading_priority") or 3)
        except Exception:
            logger.warning("x_dispatch_ready / x_credit_cleared fields not found in sale.order")

        # Fetch SO lines
        for so in sos:
            so["_lines"] = []
            if so.get("order_line"):
                try:
                    lines = self._execute(
                        "sale.order.line", "search_read",
                        [["id", "in", so["order_line"]]],
                        {"fields": ["product_id", "product_uom_qty", "product_uom", "price_unit", "name"]},
                    )
                    so["_lines"] = lines
                except Exception as e:
                    logger.warning("Could not fetch SO lines for %s: %s", so["name"], e)

        return sos

    # ── READ: Partner ─────────────────────────────────────────────

    def fetch_partner(self, partner_id: int) -> dict | None:
        """Fetch a single res.partner record."""
        try:
            results = self._execute(
                "res.partner", "search_read",
                [["id", "=", partner_id]],
                {"fields": ["id", "name", "city", "street", "phone", "mobile",
                            "x_delivery_corridor", "x_supplier_origin_region"]},
            )
            return results[0] if results else None
        except Exception as e:
            logger.error("Failed to fetch partner %d: %s", partner_id, e)
            return None

    # ── READ: Fleet vehicles ──────────────────────────────────────

    def fetch_fleet_vehicles(self) -> list[dict]:
        """Fetch truck fleet from fleet.vehicle."""
        try:
            return self._execute(
                "fleet.vehicle", "search_read",
                [["active", "=", True]],
                {"fields": ["id", "license_plate", "driver_id", "state_id"]},
            )
        except Exception as e:
            logger.error("Failed to fetch fleet vehicles: %s", e)
            return []

    # ── WRITE: Stock Picking ──────────────────────────────────────

    def create_stock_picking(
        self,
        sale_order_id: int,
        partner_id: int,
        product_id: int,
        qty: float,
        schedule_ref: str,
        proposal_ref: str,
    ) -> int | None:
        """
        Create an outbound delivery order (stock.picking) in Odoo.
        Returns picking_id on success, None on failure.
        """
        uid = self._uid_or_auth()
        try:
            picking_vals = {
                "picking_type_id": settings.odoo_picking_type_outgoing_id,
                "location_id": settings.odoo_location_stock_id,
                "location_dest_id": settings.odoo_location_customer_id,
                "partner_id": partner_id,
                "origin": f"TRUCK/{schedule_ref}/{proposal_ref}",
                "move_ids": [(0, 0, {
                    "name": f"Return Truck Allocation {proposal_ref}",
                    "product_id": product_id,
                    "product_uom_qty": qty,
                    "product_uom": 1,  # default UoM — will be overridden by product
                    "location_id": settings.odoo_location_stock_id,
                    "location_dest_id": settings.odoo_location_customer_id,
                })],
            }
            picking_id = self._models().execute_kw(
                self._db, uid, self._password,
                "stock.picking", "create",
                [picking_vals],
            )
            logger.info("Created Odoo picking %d for proposal %s", picking_id, proposal_ref)
            return picking_id
        except Exception as e:
            logger.error("Failed to create stock.picking for proposal %s: %s", proposal_ref, e)
            return None

    def confirm_stock_picking(self, picking_id: int) -> bool:
        """Call action_confirm on an existing picking."""
        uid = self._uid_or_auth()
        try:
            self._models().execute_kw(
                self._db, uid, self._password,
                "stock.picking", "action_confirm",
                [[picking_id]],
            )
            return True
        except Exception as e:
            logger.error("Failed to confirm picking %d: %s", picking_id, e)
            return False

    # ── HEALTH ────────────────────────────────────────────────────

    def ping(self) -> dict:
        """Check Odoo connectivity. Returns dict with status details."""
        try:
            version = self._common().version()
            uid = self.authenticate()
            return {
                "connected": True,
                "uid": uid,
                "odoo_version": version.get("server_version", "?"),
                "url": self._url,
                "db": self._db,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}


# ── Higher-level sync service ─────────────────────────────────────────────────

class OdooSyncService:
    """
    Orchestrates syncing Odoo data into the local DB.
    Called by APScheduler every 15 minutes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.client = OdooClient()

    async def sync_rm_purchase_orders(self) -> dict[str, int]:
        """
        Sync RM purchase orders → TruckSchedule records.
        Returns stats dict.
        """
        import asyncio
        pos = await asyncio.to_thread(self.client.fetch_rm_purchase_orders)
        created = 0
        skipped = 0

        for po in pos:
            # Check if this PO is already tracked
            result = await self.session.execute(
                select(TruckSchedule).where(TruckSchedule.odoo_po_id == po["id"])
            )
            existing = result.scalars().all()
            if existing:
                skipped += 1
                continue

            # Find transporter in local DB
            partner_id = po["partner_id"][0] if po.get("partner_id") else None
            transporter = None
            if partner_id:
                result2 = await self.session.execute(
                    select(Transporter).where(Transporter.odoo_vendor_id == partner_id)
                )
                transporter = result2.scalar_one_or_none()
                if not transporter:
                    # Try by code from Odoo
                    result2 = await self.session.execute(
                        select(Transporter).where(Transporter.odoo_vendor_code.isnot(None))
                    )
                    # Accept any for now — po_scheduler will refine

            # Import here to avoid circular
            from app.services.po_scheduler import POScheduler
            scheduler = POScheduler(self.session)
            schedules = await scheduler.process_new_po(po, transporter)
            created += len(schedules)

        return {"created": created, "skipped": skipped}

    async def sync_sale_orders(self) -> dict[str, int]:
        """Sync sale orders → CementOrder records."""
        import asyncio
        sos = await asyncio.to_thread(self.client.fetch_sale_orders)
        upserted = 0

        for so in sos:
            partner_id = so["partner_id"][0] if so.get("partner_id") else None
            partner_name = so["partner_id"][1] if so.get("partner_id") else "Unknown"

            # Derive delivery details from partner
            delivery_region = None
            delivery_corridor = None
            distance_km = None
            if partner_id:
                result = await self.session.execute(
                    select(
                        __import__("app.models.customer_logistics",
                                   fromlist=["CustomerLogistics"]).CustomerLogistics
                    ).where(
                        __import__("app.models.customer_logistics",
                                   fromlist=["CustomerLogistics"]).CustomerLogistics.odoo_partner_id == partner_id
                    )
                )
                cl = result.scalar_one_or_none()
                if cl:
                    delivery_region = cl.region
                    delivery_corridor = cl.corridor
                    distance_km = cl.distance_km

            # Total quantity from lines
            qty_tonnes = 0.0
            qty_bags = 0
            product_code = None
            product_name = None
            unit_price = 0.0
            for line in so.get("_lines", []):
                qty_bags += int(line.get("product_uom_qty", 0))
                unit_price = float(line.get("price_unit", 0))
                if line.get("product_id"):
                    product_name = line["product_id"][1]
            qty_tonnes = qty_bags / 20.0  # 50kg bags → tonnes
            total_value = float(so.get("amount_total", 0))

            # Check if order exists
            result = await self.session.execute(
                select(CementOrder).where(CementOrder.odoo_order_id == so["id"])
            )
            order = result.scalar_one_or_none()

            if order:
                # Update mutable fields
                order.dispatch_ready = so["_dispatch_ready"]
                order.credit_cleared = so["_credit_cleared"]
                order.loading_priority = so["_loading_priority"]
                order.odoo_state = so["state"]
                order.last_synced_at = datetime.now(timezone.utc)
            else:
                commitment_date = None
                if so.get("commitment_date"):
                    try:
                        commitment_date = datetime.fromisoformat(
                            str(so["commitment_date"]).replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                order = CementOrder(
                    odoo_order_id=so["id"],
                    odoo_order_name=so["name"],
                    odoo_state=so["state"],
                    customer_name=partner_name,
                    customer_odoo_id=partner_id,
                    delivery_region=delivery_region,
                    delivery_corridor=delivery_corridor,
                    distance_from_plant_km=distance_km,
                    product_name=product_name,
                    quantity_tonnes=qty_tonnes,
                    quantity_bags=qty_bags,
                    unit_price_tzs=unit_price,
                    total_value_tzs=total_value,
                    deadline_dt=commitment_date,
                    dispatch_ready=so["_dispatch_ready"],
                    credit_cleared=so["_credit_cleared"],
                    loading_priority=so["_loading_priority"],
                    allocation_status=OrderAllocationStatus.UNALLOCATED,
                    last_synced_at=datetime.now(timezone.utc),
                )
                self.session.add(order)

            upserted += 1

        await self.session.commit()
        return {"upserted": upserted}

    async def sync_rm_receipts(self, po_names: list[str]) -> dict[str, int]:
        """
        Track RM receipt state → update TruckSchedule.status.
        When receipt is 'assigned' or 'done' → mark truck as ARRIVED.
        """
        import asyncio
        receipts = await asyncio.to_thread(self.client.fetch_rm_receipts, po_names)
        updated = 0

        for receipt in receipts:
            origin = receipt.get("origin", "")
            result = await self.session.execute(
                select(TruckSchedule).where(TruckSchedule.odoo_po_name == origin)
            )
            schedules = result.scalars().all()

            for schedule in schedules:
                if (
                    receipt["state"] in ("assigned", "done")
                    and schedule.status == TruckScheduleStatus.EXPECTED
                ):
                    schedule.status = TruckScheduleStatus.ARRIVED
                    schedule.actual_arrival_dt = datetime.now(timezone.utc)
                    updated += 1

        if updated:
            await self.session.commit()

        return {"updated": updated}

    async def run_full_sync(self) -> dict:
        """Run complete sync cycle. Called by APScheduler every 15 min."""
        start = time.monotonic()
        stats: dict[str, Any] = {}

        try:
            stats["purchase_orders"] = await self.sync_rm_purchase_orders()
        except Exception as e:
            stats["purchase_orders"] = {"error": str(e)}
            logger.error("PO sync failed: %s", e)

        try:
            stats["sale_orders"] = await self.sync_sale_orders()
        except Exception as e:
            stats["sale_orders"] = {"error": str(e)}
            logger.error("SO sync failed: %s", e)

        stats["duration_ms"] = int((time.monotonic() - start) * 1000)
        logger.info("Full sync complete: %s", stats)
        return stats

