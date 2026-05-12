"""
app/schemas/truck_allocation.py — Pydantic v2 schemas for TruckAllocation API.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AllocationItemCreate(BaseModel):
    customer_name: str
    order_ref: str
    order_date: date | None = None
    product: str
    quantity_tonnes: float
    destination_location: str
    region: str


class AllocationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    allocation_id: int
    customer_name: str
    order_ref: str
    order_date: date | None
    product: str
    quantity_tonnes: float
    destination_location: str
    region: str
    sequence: int
    created_at: datetime


class TruckAllocationCreate(BaseModel):
    schedule_id: int
    released_by: str = "dispatcher"


class TruckAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    status: str
    remarks: str | None
    released_at: datetime | None
    loaded_at: datetime | None
    released_by: str | None
    created_at: datetime
    total_tonnes: float
    items: list[AllocationItemRead]

    # Denormalised from TruckSchedule (populated in router)
    schedule_ref: str | None = None
    odoo_po_name: str | None = None
    truck_plate: str | None = None
    transporter_name: str | None = None
    driver_name: str | None = None
    driver_license_no: str | None = None
    dealer_number: str | None = None
    origin_region: str | None = None
    expected_arrival_dt: datetime | None = None
    effective_capacity_tonnes: float | None = None


class TruckAllocationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    status: str
    remarks: str | None
    released_at: datetime | None
    loaded_at: datetime | None
    created_at: datetime
    total_tonnes: float
    item_count: int = 0

    # Denormalised from TruckSchedule (populated in router)
    schedule_ref: str | None = None
    odoo_po_name: str | None = None
    truck_plate: str | None = None
    transporter_name: str | None = None
    driver_name: str | None = None
    driver_license_no: str | None = None
    dealer_number: str | None = None
    origin_region: str | None = None
    expected_arrival_dt: datetime | None = None
    effective_capacity_tonnes: float | None = None


class ReleaseRequest(BaseModel):
    released_by: str = "dispatcher"


class RemarksRequest(BaseModel):
    remarks: str
