"""
app/models/cement_order.py — Cement delivery order awaiting allocation.

Sourced from Odoo sale.order. An order is eligible for return-truck allocation
when dispatch_ready=True AND credit_cleared=True (or near-ready by truck ETA).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderAllocationStatus:
    UNALLOCATED   = "UNALLOCATED"
    CANDIDATE     = "CANDIDATE"
    SOFT_RESERVED = "SOFT_RESERVED"
    ALLOCATED     = "ALLOCATED"
    DELIVERED     = "DELIVERED"


class CementOrder(Base):
    __tablename__ = "cement_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Odoo links ────────────────────────────────────────────────
    odoo_order_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    odoo_order_name: Mapped[str] = mapped_column(String(50), nullable=False)
    odoo_picking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odoo_state: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ── Customer ──────────────────────────────────────────────────
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_odoo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ── Delivery location ─────────────────────────────────────────
    delivery_region: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    delivery_zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_corridor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_from_plant_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Product ───────────────────────────────────────────────────
    product_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity_tonnes: Mapped[float] = mapped_column(Float, default=0.0)
    quantity_bags: Mapped[int] = mapped_column(Integer, default=0)

    # ── Order value ───────────────────────────────────────────────
    unit_price_tzs: Mapped[float] = mapped_column(Float, default=0.0)
    total_value_tzs: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Scheduling ────────────────────────────────────────────────
    requested_delivery_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deadline_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    urgency_score: Mapped[float] = mapped_column(Float, default=5.0)

    # ── Dispatch readiness ────────────────────────────────────────
    dispatch_ready: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    credit_cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    partial_load_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    loading_priority: Mapped[int] = mapped_column(Integer, default=3)
    return_load_eligible: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Near-ready ────────────────────────────────────────────────
    near_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    near_ready_eta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    soft_reserved_schedule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("truck_schedules.id"), nullable=True
    )

    # ── Allocation ────────────────────────────────────────────────
    allocation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrderAllocationStatus.UNALLOCATED, index=True
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    proposal_items: Mapped[list] = relationship("ProposalItem", back_populates="cement_order")

    @property
    def is_eligible(self) -> bool:
        return (
            self.dispatch_ready
            and self.credit_cleared
            and self.return_load_eligible
            and self.allocation_status == OrderAllocationStatus.UNALLOCATED
        )

    def __repr__(self) -> str:
        return (
            f"<CementOrder {self.odoo_order_name} "
            f"{self.quantity_tonnes}T → {self.delivery_region} "
            f"[{self.allocation_status}]>"
        )
