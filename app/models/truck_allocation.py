"""
app/models/truck_allocation.py — TruckAllocation + AllocationItem.

One TruckSchedule has at most one TruckAllocation.
AllocationItem = one cement order line typed in by the dispatcher.

Status flow:
  DRAFT → WAITING_LOADING (orders assigned, waiting for physical cement loading)
         → LOADED
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TruckAllocationStatus:
    DRAFT           = "DRAFT"
    WAITING_LOADING = "WAITING_LOADING"
    LOADED          = "LOADED"

    # Legacy value retained so existing rows keep working.
    RELEASED = "RELEASED"


class TruckAllocation(Base):
    __tablename__ = "truck_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("truck_schedules.id"), nullable=False, unique=True, index=True
    )
    schedule: Mapped["TruckSchedule"] = relationship(
        "TruckSchedule", back_populates="allocation"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TruckAllocationStatus.DRAFT, index=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    released_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["AllocationItem"]] = relationship(
        "AllocationItem",
        back_populates="allocation",
        cascade="all, delete-orphan",
        order_by="AllocationItem.sequence",
    )

    @property
    def total_tonnes(self) -> float:
        return sum(item.quantity_tonnes for item in self.items)

    def __repr__(self) -> str:
        return (
            f"<TruckAllocation schedule={self.schedule_id} "
            f"status={self.status} items={len(self.items)}>"
        )


class AllocationItem(Base):
    __tablename__ = "allocation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    allocation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("truck_allocations.id"), nullable=False, index=True
    )
    allocation: Mapped["TruckAllocation"] = relationship(
        "TruckAllocation", back_populates="items"
    )

    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    order_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    product: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_tonnes: Mapped[float] = mapped_column(Float, nullable=False)
    destination_location: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<AllocationItem {self.order_ref} "
            f"{self.quantity_tonnes}T → {self.destination_location}>"
        )
