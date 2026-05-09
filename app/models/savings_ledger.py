"""app/models/savings_ledger.py — One row per dispatched allocation."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SavingsLedger(Base):
    __tablename__ = "savings_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    proposal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("allocation_proposals.id"), nullable=False, unique=True
    )
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("truck_schedules.id"), nullable=False
    )

    proposal_ref: Mapped[str] = mapped_column(String(30), nullable=False)
    schedule_ref: Mapped[str] = mapped_column(String(30), nullable=False)
    truck_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transporter_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    corridor_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origin_region: Mapped[str | None] = mapped_column(String(50), nullable=True)

    fresh_freight_avoided_tzs: Mapped[float] = mapped_column(Float, default=0.0)
    return_freight_paid_tzs: Mapped[float] = mapped_column(Float, default=0.0)
    holding_cost_saved_tzs: Mapped[float] = mapped_column(Float, default=0.0)
    net_savings_tzs: Mapped[float] = mapped_column(Float, default=0.0)
    allocated_tonnes: Mapped[float] = mapped_column(Float, default=0.0)
    capacity_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    number_of_orders: Mapped[int] = mapped_column(Integer, default=0)

    dispatch_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    month_key: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
