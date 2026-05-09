"""
app/models/matching_event.py — Audit log of every matching engine run.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MatchTrigger:
    PO_SYNC   = "PO_SYNC"
    SO_CHANGE = "SO_CHANGE"
    MANUAL    = "MANUAL"
    CRON      = "CRON"
    REMATCH   = "REMATCH"


class MatchingEvent(Base):
    __tablename__ = "matching_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    schedule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("truck_schedules.id"), nullable=True, index=True
    )

    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)

    orders_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    orders_qualified: Mapped[int] = mapped_column(Integer, default=0)
    proposals_generated: Mapped[int] = mapped_column(Integer, default=0)

    top_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)

    ai_called: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<MatchingEvent id={self.id} schedule={self.schedule_id} "
            f"trigger={self.triggered_by} util={self.top_utilization_pct:.0f}%>"
        )
