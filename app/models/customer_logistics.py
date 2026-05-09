"""
app/models/customer_logistics.py — Enriched customer delivery data.

Supplements the Odoo res.partner record with logistics-specific fields
that are not stored in Odoo:
  - Corridor membership
  - Distance from Kimbiji Plant (from location master Kilometer field)
  - GPS coordinates
  - Truck access type

Seeded from: location master.xlsx (Kilometer column) + Customer master.xlsx
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TruckAccessType:
    FULL       = "FULL"        # Any truck size can access
    MEDIUM     = "MEDIUM"      # Up to 30T
    SMALL_ONLY = "SMALL_ONLY"  # Small trucks only (poor road)


class CustomerLogistics(Base):
    __tablename__ = "customer_logistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Links
    odoo_partner_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Location
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. "DODOMA", "MBEYA"
    zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. "Central 1", "Southern highland 2"
    corridor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # e.g. "CENTRAL", "SOUTHERN_HIGHLAND"

    # Distance from Kimbiji Plant
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    # From location master Kilometer column — most accurate source

    # GPS (from Odoo partner or manual entry)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Truck access
    truck_access_type: Mapped[str] = mapped_column(String(20), default=TruckAccessType.FULL)

    # Preferences
    preferred_delivery_days: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. "MON,TUE,WED"
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<CustomerLogistics {self.customer_name!r} "
            f"region={self.region} dist={self.distance_km}km>"
        )
