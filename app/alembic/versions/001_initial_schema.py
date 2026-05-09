"""Initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2026-04-27

Creates all 9 tables for the Smart Return Truck Allocator:
  transporters, route_corridors, customer_logistics,
  truck_schedules, cement_orders, allocation_proposals,
  proposal_items, matching_events, savings_ledger
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── transporters ─────────────────────────────────────────────
    op.create_table(
        "transporters",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("odoo_vendor_id", sa.Integer, nullable=True),
        sa.Column("odoo_vendor_code", sa.String(20), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("whatsapp_number", sa.String(30), nullable=True),
        sa.Column("fleet_size", sa.Integer, default=1, nullable=False),
        sa.Column("avg_truck_capacity_tonnes", sa.Float, default=30.0, nullable=False),
        sa.Column("vehicle_types", sa.Text, nullable=True),
        sa.Column("preferred_corridors", sa.Text, nullable=True),
        sa.Column("origin_region", sa.String(50), nullable=True),
        sa.Column("backhaul_willing", sa.Boolean, default=True, nullable=False),
        sa.Column("return_load_rate_pct", sa.Float, default=0.60, nullable=False),
        sa.Column("payment_terms", sa.String(100), nullable=True),
        sa.Column("reliability_score", sa.Float, default=7.0, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transporters_name", "transporters", ["name"])
    op.create_index("ix_transporters_odoo_vendor_id", "transporters", ["odoo_vendor_id"])

    # ── route_corridors ───────────────────────────────────────────
    op.create_table(
        "route_corridors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("origin_region", sa.String(50), nullable=False),
        sa.Column("waypoints", sa.Text, nullable=False, default="[]"),
        sa.Column("total_km", sa.Float, default=0.0, nullable=False),
        sa.Column("distance_matrix", sa.Text, nullable=True),
        sa.Column("rainy_season_penalty_pct", sa.Float, default=0.0, nullable=False),
        sa.Column("passable_all_year", sa.Boolean, default=True, nullable=False),
        sa.Column("max_detour_km", sa.Float, default=80.0, nullable=False),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # ── customer_logistics ────────────────────────────────────────
    op.create_table(
        "customer_logistics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("odoo_partner_id", sa.Integer, nullable=False, unique=True),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("zone", sa.String(50), nullable=True),
        sa.Column("corridor", sa.String(30), nullable=True),
        sa.Column("distance_km", sa.Float, nullable=True),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lng", sa.Float, nullable=True),
        sa.Column("truck_access_type", sa.String(20), default="FULL", nullable=False),
        sa.Column("preferred_delivery_days", sa.String(50), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_logistics_region", "customer_logistics", ["region"])

    # ── truck_schedules ───────────────────────────────────────────
    op.create_table(
        "truck_schedules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("schedule_ref", sa.String(30), nullable=False, unique=True),
        sa.Column("odoo_po_id", sa.Integer, nullable=True),
        sa.Column("odoo_po_name", sa.String(50), nullable=True),
        sa.Column("odoo_receipt_id", sa.Integer, nullable=True),
        sa.Column("transporter_id", sa.Integer, sa.ForeignKey("transporters.id"), nullable=True),
        sa.Column("origin_region", sa.String(50), nullable=False),
        sa.Column("raw_material_type", sa.String(30), nullable=True),
        sa.Column("estimated_qty_tonnes", sa.Float, default=30.0, nullable=False),
        sa.Column("estimated_truck_count", sa.Integer, default=1, nullable=False),
        sa.Column("truck_plate", sa.String(20), nullable=True),
        sa.Column("driver_name", sa.String(100), nullable=True),
        sa.Column("driver_phone", sa.String(30), nullable=True),
        sa.Column("actual_capacity_tonnes", sa.Float, nullable=True),
        sa.Column("corridor_name", sa.String(50), nullable=True),
        sa.Column("return_route", sa.Text, nullable=True),
        sa.Column("max_detour_km", sa.Float, default=80.0, nullable=False),
        sa.Column("po_date", sa.DateTime, nullable=True),
        sa.Column("expected_arrival_dt", sa.DateTime, nullable=True),
        sa.Column("actual_arrival_dt", sa.DateTime, nullable=True),
        sa.Column("loaded_out_dt", sa.DateTime, nullable=True),
        sa.Column("dispatched_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="EXPECTED"),
        sa.Column("allocation_status", sa.String(20), nullable=False, default="UNMATCHED"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_truck_schedules_schedule_ref", "truck_schedules", ["schedule_ref"])
    op.create_index("ix_truck_schedules_status", "truck_schedules", ["status"])
    op.create_index("ix_truck_schedules_allocation_status", "truck_schedules", ["allocation_status"])
    op.create_index("ix_truck_schedules_expected_arrival_dt", "truck_schedules", ["expected_arrival_dt"])
    op.create_index("ix_truck_schedules_truck_plate", "truck_schedules", ["truck_plate"])
    op.create_index("ix_truck_schedules_odoo_po_id", "truck_schedules", ["odoo_po_id"])

    # ── cement_orders ─────────────────────────────────────────────
    op.create_table(
        "cement_orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("odoo_order_id", sa.Integer, nullable=False, unique=True),
        sa.Column("odoo_order_name", sa.String(50), nullable=False),
        sa.Column("odoo_picking_id", sa.Integer, nullable=True),
        sa.Column("odoo_state", sa.String(30), nullable=True),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_odoo_id", sa.Integer, nullable=True),
        sa.Column("customer_phone", sa.String(30), nullable=True),
        sa.Column("delivery_region", sa.String(50), nullable=True),
        sa.Column("delivery_zone", sa.String(50), nullable=True),
        sa.Column("delivery_corridor", sa.String(30), nullable=True),
        sa.Column("delivery_address", sa.Text, nullable=True),
        sa.Column("delivery_lat", sa.Float, nullable=True),
        sa.Column("delivery_lng", sa.Float, nullable=True),
        sa.Column("distance_from_plant_km", sa.Float, nullable=True),
        sa.Column("product_code", sa.String(50), nullable=True),
        sa.Column("product_name", sa.String(200), nullable=True),
        sa.Column("quantity_tonnes", sa.Float, default=0.0, nullable=False),
        sa.Column("quantity_bags", sa.Integer, default=0, nullable=False),
        sa.Column("fresh_outbound_freight_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("unit_price_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("total_value_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("requested_delivery_dt", sa.DateTime, nullable=True),
        sa.Column("deadline_dt", sa.DateTime, nullable=True),
        sa.Column("urgency_score", sa.Float, default=5.0, nullable=False),
        sa.Column("dispatch_ready", sa.Boolean, default=False, nullable=False),
        sa.Column("credit_cleared", sa.Boolean, default=False, nullable=False),
        sa.Column("partial_load_allowed", sa.Boolean, default=False, nullable=False),
        sa.Column("loading_priority", sa.Integer, default=3, nullable=False),
        sa.Column("return_load_eligible", sa.Boolean, default=True, nullable=False),
        sa.Column("near_ready", sa.Boolean, default=False, nullable=False),
        sa.Column("near_ready_eta", sa.DateTime, nullable=True),
        sa.Column(
            "soft_reserved_schedule_id",
            sa.Integer,
            sa.ForeignKey("truck_schedules.id"),
            nullable=True,
        ),
        sa.Column("allocation_status", sa.String(20), nullable=False, default="UNALLOCATED"),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cement_orders_odoo_order_id", "cement_orders", ["odoo_order_id"])
    op.create_index("ix_cement_orders_delivery_region", "cement_orders", ["delivery_region"])
    op.create_index("ix_cement_orders_allocation_status", "cement_orders", ["allocation_status"])
    op.create_index("ix_cement_orders_deadline_dt", "cement_orders", ["deadline_dt"])
    op.create_index("ix_cement_orders_dispatch_ready", "cement_orders", ["dispatch_ready"])

    # ── allocation_proposals ──────────────────────────────────────
    op.create_table(
        "allocation_proposals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("proposal_ref", sa.String(30), nullable=False, unique=True),
        sa.Column("schedule_id", sa.Integer, sa.ForeignKey("truck_schedules.id"), nullable=False),
        sa.Column("variant_type", sa.String(20), nullable=False),
        sa.Column("total_allocated_tonnes", sa.Float, default=0.0, nullable=False),
        sa.Column("capacity_utilization_pct", sa.Float, default=0.0, nullable=False),
        sa.Column("total_route_deviation_km", sa.Float, default=0.0, nullable=False),
        sa.Column("number_of_stops", sa.Integer, default=0, nullable=False),
        sa.Column("total_fresh_freight_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("total_return_freight_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("holding_cost_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("estimated_savings_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("composite_score", sa.Float, default=0.0, nullable=False),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("ai_warnings", sa.Text, nullable=True),
        sa.Column("ai_recommendation", sa.String(20), nullable=True),
        sa.Column("has_pending_readiness_orders", sa.Boolean, default=False, nullable=False),
        sa.Column("pending_readiness_note", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="PROPOSED"),
        sa.Column("confirmed_by", sa.String(100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("dispatched_at", sa.DateTime, nullable=True),
        sa.Column("odoo_picking_ids", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_allocation_proposals_proposal_ref", "allocation_proposals", ["proposal_ref"])
    op.create_index("ix_allocation_proposals_schedule_id", "allocation_proposals", ["schedule_id"])
    op.create_index("ix_allocation_proposals_status", "allocation_proposals", ["status"])

    # ── proposal_items ────────────────────────────────────────────
    op.create_table(
        "proposal_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("proposal_id", sa.Integer, sa.ForeignKey("allocation_proposals.id"), nullable=False),
        sa.Column("cement_order_id", sa.Integer, sa.ForeignKey("cement_orders.id"), nullable=False),
        sa.Column("allocated_tonnes", sa.Float, default=0.0, nullable=False),
        sa.Column("allocated_bags", sa.Integer, default=0, nullable=False),
        sa.Column("sequence", sa.Integer, default=1, nullable=False),
        sa.Column("delivery_deviation_km", sa.Float, default=0.0, nullable=False),
        sa.Column("item_savings_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("is_near_ready", sa.Boolean, default=False, nullable=False),
        sa.Column("odoo_picking_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_proposal_items_proposal_id", "proposal_items", ["proposal_id"])

    # ── matching_events ───────────────────────────────────────────
    op.create_table(
        "matching_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("schedule_id", sa.Integer, sa.ForeignKey("truck_schedules.id"), nullable=True),
        sa.Column("triggered_by", sa.String(20), nullable=False),
        sa.Column("orders_evaluated", sa.Integer, default=0, nullable=False),
        sa.Column("orders_qualified", sa.Integer, default=0, nullable=False),
        sa.Column("proposals_generated", sa.Integer, default=0, nullable=False),
        sa.Column("top_savings_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("top_utilization_pct", sa.Float, default=0.0, nullable=False),
        sa.Column("savings_delta_tzs", sa.Float, nullable=True),
        sa.Column("alert_sent", sa.Boolean, default=False, nullable=False),
        sa.Column("ai_called", sa.Boolean, default=False, nullable=False),
        sa.Column("duration_ms", sa.Integer, default=0, nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_matching_events_schedule_id", "matching_events", ["schedule_id"])

    # ── savings_ledger ────────────────────────────────────────────
    op.create_table(
        "savings_ledger",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("proposal_id", sa.Integer, sa.ForeignKey("allocation_proposals.id"), nullable=False, unique=True),
        sa.Column("schedule_id", sa.Integer, sa.ForeignKey("truck_schedules.id"), nullable=False),
        sa.Column("proposal_ref", sa.String(30), nullable=False),
        sa.Column("schedule_ref", sa.String(30), nullable=False),
        sa.Column("truck_plate", sa.String(20), nullable=True),
        sa.Column("transporter_name", sa.String(200), nullable=True),
        sa.Column("corridor_name", sa.String(50), nullable=True),
        sa.Column("origin_region", sa.String(50), nullable=True),
        sa.Column("fresh_freight_avoided_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("return_freight_paid_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("holding_cost_saved_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("net_savings_tzs", sa.Float, default=0.0, nullable=False),
        sa.Column("allocated_tonnes", sa.Float, default=0.0, nullable=False),
        sa.Column("capacity_utilization_pct", sa.Float, default=0.0, nullable=False),
        sa.Column("number_of_orders", sa.Integer, default=0, nullable=False),
        sa.Column("dispatch_date", sa.DateTime, nullable=True),
        sa.Column("month_key", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_savings_ledger_dispatch_date", "savings_ledger", ["dispatch_date"])
    op.create_index("ix_savings_ledger_month_key", "savings_ledger", ["month_key"])


def downgrade() -> None:
    op.drop_table("savings_ledger")
    op.drop_table("matching_events")
    op.drop_table("proposal_items")
    op.drop_table("allocation_proposals")
    op.drop_table("cement_orders")
    op.drop_table("truck_schedules")
    op.drop_table("customer_logistics")
    op.drop_table("route_corridors")
    op.drop_table("transporters")
