"""
app/schemas/cement_order.py — Pydantic v2 schemas for CementOrder API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CementOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    odoo_order_id: int
    odoo_order_name: str
    customer_name: str
    delivery_region: str | None
    delivery_zone: str | None
    delivery_corridor: str | None
    distance_from_plant_km: float | None
    product_code: str | None
    product_name: str | None
    quantity_tonnes: float
    quantity_bags: int
    total_value_tzs: float
    deadline_dt: datetime | None
    urgency_score: float
    dispatch_ready: bool
    credit_cleared: bool
    partial_load_allowed: bool
    loading_priority: int
    near_ready: bool
    near_ready_eta: datetime | None
    allocation_status: str
    last_synced_at: datetime | None
    created_at: datetime


class CementOrderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    odoo_order_name: str
    customer_name: str
    delivery_region: str | None
    delivery_corridor: str | None
    quantity_tonnes: float
    deadline_dt: datetime | None
    urgency_score: float
    dispatch_ready: bool
    credit_cleared: bool
    near_ready: bool
    allocation_status: str
