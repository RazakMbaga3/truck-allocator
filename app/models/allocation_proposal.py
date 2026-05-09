"""
app/models/allocation_proposal.py — AllocationProposal + ProposalItem.

One TruckSchedule can have up to 3 proposals (variants):
  BEST_MATCH   — orders with highest composite score
  MAX_LOAD     — orders sorted by largest quantity (fill the truck)
  URGENT_FIRST — orders sorted by nearest deadline
"""

import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProposalVariant:
    BEST_MATCH   = "BEST_MATCH"
    MAX_LOAD     = "MAX_LOAD"
    URGENT_FIRST = "URGENT_FIRST"


class ProposalStatus:
    PROPOSED   = "PROPOSED"
    CONFIRMED  = "CONFIRMED"
    DISPATCHED = "DISPATCHED"
    COMPLETED  = "COMPLETED"
    REJECTED   = "REJECTED"


class AllocationProposal(Base):
    __tablename__ = "allocation_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_ref: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)

    # ── Links ─────────────────────────────────────────────────────
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("truck_schedules.id"), nullable=False, index=True
    )
    schedule: Mapped["TruckSchedule"] = relationship("TruckSchedule", back_populates="proposals")

    variant_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── Metrics ───────────────────────────────────────────────────
    total_allocated_tonnes: Mapped[float] = mapped_column(Float, default=0.0)
    capacity_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    total_route_deviation_km: Mapped[float] = mapped_column(Float, default=0.0)
    number_of_stops: Mapped[int] = mapped_column(Integer, default=0)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── AI Advisory ───────────────────────────────────────────────
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    _ai_warnings: Mapped[str | None] = mapped_column("ai_warnings", Text, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Near-ready orders ─────────────────────────────────────────
    has_pending_readiness_orders: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_readiness_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Workflow ──────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProposalStatus.PROPOSED, index=True
    )
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Odoo write-back ───────────────────────────────────────────
    _odoo_picking_ids: Mapped[str | None] = mapped_column("odoo_picking_ids", Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["ProposalItem"]] = relationship(
        "ProposalItem", back_populates="proposal", cascade="all, delete-orphan",
        order_by="ProposalItem.sequence"
    )

    @property
    def ai_warnings(self) -> list[str]:
        return json.loads(self._ai_warnings) if self._ai_warnings else []

    @ai_warnings.setter
    def ai_warnings(self, value: list[str]) -> None:
        self._ai_warnings = json.dumps(value)

    @property
    def odoo_picking_ids(self) -> list[int]:
        return json.loads(self._odoo_picking_ids) if self._odoo_picking_ids else []

    @odoo_picking_ids.setter
    def odoo_picking_ids(self, value: list[int]) -> None:
        self._odoo_picking_ids = json.dumps(value)

    def __repr__(self) -> str:
        return (
            f"<AllocationProposal {self.proposal_ref} "
            f"variant={self.variant_type} util={self.capacity_utilization_pct:.0f}% "
            f"status={self.status}>"
        )


class ProposalItem(Base):
    __tablename__ = "proposal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    proposal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("allocation_proposals.id"), nullable=False, index=True
    )
    proposal: Mapped["AllocationProposal"] = relationship("AllocationProposal", back_populates="items")

    cement_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cement_orders.id"), nullable=False
    )
    cement_order: Mapped["CementOrder"] = relationship("CementOrder", back_populates="proposal_items")

    allocated_tonnes: Mapped[float] = mapped_column(Float, default=0.0)
    allocated_bags: Mapped[int] = mapped_column(Integer, default=0)
    sequence: Mapped[int] = mapped_column(Integer, default=1)

    delivery_deviation_km: Mapped[float] = mapped_column(Float, default=0.0)
    is_near_ready: Mapped[bool] = mapped_column(Boolean, default=False)

    odoo_picking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<ProposalItem proposal={self.proposal_id} "
            f"order={self.cement_order_id} {self.allocated_tonnes}T seq={self.sequence}>"
        )
