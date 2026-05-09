"""
app/schemas/allocation_proposal.py — Pydantic v2 schemas for AllocationProposal API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProposalItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cement_order_id: int
    allocated_tonnes: float
    allocated_bags: int
    sequence: int
    delivery_deviation_km: float
    is_near_ready: bool
    odoo_picking_id: int | None

    order_name: str | None = None
    customer_name: str | None = None
    order_date: datetime | None = None
    product_name: str | None = None
    quantity_tonnes: float | None = None
    delivery_zone: str | None = None
    delivery_region: str | None = None


class AllocationProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proposal_ref: str
    schedule_id: int
    variant_type: str

    total_allocated_tonnes: float
    capacity_utilization_pct: float
    total_route_deviation_km: float
    number_of_stops: int
    composite_score: float

    ai_reasoning: str | None
    ai_warnings: list[str]
    ai_recommendation: str | None

    has_pending_readiness_orders: bool
    pending_readiness_note: str | None

    status: str
    confirmed_by: str | None
    confirmed_at: datetime | None

    items: list[ProposalItemRead]
    created_at: datetime


class AllocationProposalListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proposal_ref: str
    schedule_id: int
    variant_type: str
    total_allocated_tonnes: float
    capacity_utilization_pct: float
    total_route_deviation_km: float
    number_of_stops: int
    has_pending_readiness_orders: bool
    ai_recommendation: str | None
    status: str
    confirmed_at: datetime | None
    created_at: datetime

    # Denormalised from TruckSchedule (populated in router)
    transporter_name: str | None = None
    driver_name: str | None = None
    driver_license_no: str | None = None
    dealer_number: str | None = None
    truck_plate: str | None = None
    origin_region: str | None = None
    raw_material_type: str | None = None
    expected_arrival_dt: datetime | None = None
    corridor_name: str | None = None
    schedule_ref: str | None = None

    # Order items (populated in router)
    items: list[ProposalItemRead] = []


class ConfirmProposalRequest(BaseModel):
    confirmed_by: str = "dispatcher"


class RejectProposalRequest(BaseModel):
    reason: str | None = None
