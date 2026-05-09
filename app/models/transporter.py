"""
app/models/transporter.py — Transporter master.

Transporters are the third-party hauliers who deliver raw materials to Kimbiji
Plant. Their trucks are the vehicles we want to load with cement on the return leg.

Known fleets from actual LCL data (CLAUDE.md):
  KAIXIN (Mwamba Investment): T865EHY, T866EHY, T867EHY, T868EHY, T869EHY
  ANTU LOGISTICS:             T316ENF, T431CPQ, T460CPQ, T536CPQ, T565CPQ
  NACHARO ROYAL:              T218EJE, T216EJE, T219EJE, T323EJE, T220EJE
  SAIBABA TRUCKS, RAS LOGISTICS, etc.
"""

import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transporter(Base):
    __tablename__ = "transporters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Odoo link
    odoo_vendor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    odoo_vendor_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Identity
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Fleet characteristics
    fleet_size: Mapped[int] = mapped_column(Integer, default=1)
    avg_truck_capacity_tonnes: Mapped[float] = mapped_column(Float, default=30.0)
    _vehicle_types: Mapped[str | None] = mapped_column("vehicle_types", Text, nullable=True)

    # Route intelligence
    _preferred_corridors: Mapped[str | None] = mapped_column("preferred_corridors", Text, nullable=True)
    origin_region: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Commercial
    backhaul_willing: Mapped[bool] = mapped_column(Boolean, default=True)
    return_load_rate_pct: Mapped[float] = mapped_column(Float, default=0.60)
    payment_terms: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Performance
    reliability_score: Mapped[float] = mapped_column(Float, default=7.0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    schedules: Mapped[list] = relationship("TruckSchedule", back_populates="transporter")

    # ── JSON helpers ──────────────────────────────────────────────
    @property
    def vehicle_types(self) -> list[str]:
        return json.loads(self._vehicle_types) if self._vehicle_types else []

    @vehicle_types.setter
    def vehicle_types(self, value: list[str]) -> None:
        self._vehicle_types = json.dumps(value)

    @property
    def preferred_corridors(self) -> list[str]:
        return json.loads(self._preferred_corridors) if self._preferred_corridors else []

    @preferred_corridors.setter
    def preferred_corridors(self, value: list[str]) -> None:
        self._preferred_corridors = json.dumps(value)

    def __repr__(self) -> str:
        return f"<Transporter id={self.id} name={self.name!r} corridor={self.origin_region}>"
