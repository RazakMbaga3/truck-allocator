"""
app/models/truck_schedule.py — TruckSchedule: the core proactive model.

Each TruckSchedule record represents ONE inbound truck expected at Kimbiji Plant,
derived from a confirmed Odoo raw material Purchase Order.

Status flow:
  EXPECTED → PRE_CONFIRMED → ARRIVED → LOADED → DISPATCHED → COMPLETED
"""

import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TruckScheduleStatus:
    EXPECTED      = "EXPECTED"
    PRE_CONFIRMED = "PRE_CONFIRMED"
    ARRIVED       = "ARRIVED"
    LOADED        = "LOADED"
    DISPATCHED    = "DISPATCHED"
    COMPLETED     = "COMPLETED"
    CANCELLED     = "CANCELLED"


class AllocationStatus:
    UNMATCHED  = "UNMATCHED"
    PROPOSED   = "PROPOSED"
    CONFIRMED  = "CONFIRMED"
    DISPATCHED = "DISPATCHED"


class TruckSchedule(Base):
    __tablename__ = "truck_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Reference ─────────────────────────────────────────────────
    schedule_ref: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)

    # ── Odoo links ────────────────────────────────────────────────
    odoo_po_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    odoo_po_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    odoo_receipt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Transporter ───────────────────────────────────────────────
    transporter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transporters.id"), nullable=True
    )
    transporter: Mapped["Transporter"] = relationship("Transporter", back_populates="schedules")
    transporter_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    origin_region: Mapped[str] = mapped_column(String(50), nullable=False)

    # ── Raw material ──────────────────────────────────────────────
    raw_material_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estimated_qty_tonnes: Mapped[float] = mapped_column(Float, default=30.0)
    estimated_truck_count: Mapped[int] = mapped_column(Integer, default=1)

    # ── Truck & driver details ────────────────────────────────────
    truck_plate: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    driver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    driver_license_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dealer_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Dealer/agent reference number from the transporter company
    actual_capacity_tonnes: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Route ─────────────────────────────────────────────────────
    corridor_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    _return_route: Mapped[str | None] = mapped_column("return_route", Text, nullable=True)
    max_detour_km: Mapped[float] = mapped_column(Float, default=80.0)

    # ── Timeline ──────────────────────────────────────────────────
    po_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expected_arrival_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    actual_arrival_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    loaded_out_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Status ────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TruckScheduleStatus.EXPECTED, index=True
    )
    allocation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AllocationStatus.UNMATCHED, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    proposals: Mapped[list] = relationship(
        "AllocationProposal", back_populates="schedule", cascade="all, delete-orphan"
    )

    @property
    def return_route(self) -> list[str]:
        return json.loads(self._return_route) if self._return_route else []

    @return_route.setter
    def return_route(self, value: list[str]) -> None:
        self._return_route = json.dumps(value)

    @property
    def effective_capacity_tonnes(self) -> float:
        return self.actual_capacity_tonnes or self.estimated_qty_tonnes

    @property
    def is_available(self) -> bool:
        return (
            self.status in (TruckScheduleStatus.EXPECTED, TruckScheduleStatus.PRE_CONFIRMED)
            and self.allocation_status != AllocationStatus.CONFIRMED
        )

    def __repr__(self) -> str:
        plate = self.truck_plate or "???"
        return (
            f"<TruckSchedule {self.schedule_ref} plate={plate} "
            f"origin={self.origin_region} status={self.status}>"
        )
