"""
app/schemas/truck_schedule.py — Pydantic v2 schemas for TruckSchedule API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TruckScheduleBase(BaseModel):
    origin_region: str
    raw_material_type: str | None = None
    estimated_qty_tonnes: float = 30.0
    corridor_name: str | None = None
    max_detour_km: float = 80.0
    expected_arrival_dt: datetime | None = None
    notes: str | None = None


class TruckScheduleCreate(TruckScheduleBase):
    odoo_po_id: int | None = None
    odoo_po_name: str | None = None
    transporter_id: int | None = None


class TruckScheduleDetail(TruckScheduleBase):
    """Detail schema — used for PATCH /confirm-details."""
    truck_plate: str | None = None
    driver_name: str | None = None
    driver_license_no: str | None = None
    driver_phone: str | None = None
    dealer_number: str | None = None
    transporter_name: str | None = None
    actual_capacity_tonnes: float | None = None


class TruckScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_ref: str
    odoo_po_id: int | None
    odoo_po_name: str | None
    transporter_id: int | None
    transporter_name: str | None
    origin_region: str
    raw_material_type: str | None
    estimated_qty_tonnes: float
    estimated_truck_count: int
    truck_plate: str | None
    driver_name: str | None
    driver_license_no: str | None
    driver_phone: str | None
    dealer_number: str | None
    actual_capacity_tonnes: float | None
    corridor_name: str | None
    return_route: list[str]
    max_detour_km: float
    po_date: datetime | None
    expected_arrival_dt: datetime | None
    actual_arrival_dt: datetime | None
    dispatched_at: datetime | None
    dispatch_date: datetime | None
    upload_date: datetime | None
    status: str
    allocation_status: str
    is_available: bool
    effective_capacity_tonnes: float
    created_at: datetime
    updated_at: datetime


class TruckScheduleListItem(BaseModel):
    """Lightweight row for the Available Trucks dashboard list."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_ref: str
    odoo_po_name: str | None
    origin_region: str
    raw_material_type: str | None
    estimated_qty_tonnes: float
    truck_plate: str | None
    driver_name: str | None
    driver_license_no: str | None
    driver_phone: str | None
    dealer_number: str | None
    transporter_name: str | None
    corridor_name: str | None
    expected_arrival_dt: datetime | None
    dispatch_date: datetime | None
    upload_date: datetime | None
    status: str
    allocation_status: str
    is_available: bool
