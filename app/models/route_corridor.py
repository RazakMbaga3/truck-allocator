"""
app/models/route_corridor.py — Tanzania route corridor master.

Each corridor represents a named truck return route from Kimbiji Plant.
The distance_matrix stores pairwise km distances between all stops on
this corridor (serialised JSON).

Corridors confirmed from LCL data:
  CENTRAL           — Kigamboni → Chalinze → Morogoro → Dodoma → Tabora → Mwanza
  NORTHERN          — Kigamboni → Chalinze → Segera → Tanga / Moshi / Arusha
  SOUTHERN_HIGHLAND — Kigamboni → Chalinze → Morogoro → Iringa → Mbeya
  COASTAL           — Kigamboni → Kibiti → Utete → Nyamisati → Ikwiriri (Gypsum route R1)
  LAKE              — Kigamboni → Chalinze → Morogoro → Dodoma → Tabora → Mwanza
  SOUTHERN          — Kigamboni → Chalinze → Morogoro → Songea
"""

import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RouteCorridor(Base):
    __tablename__ = "route_corridors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # e.g. "CENTRAL"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Route definition
    origin_region: Mapped[str] = mapped_column(String(50), nullable=False)
    _waypoints: Mapped[str] = mapped_column("waypoints", Text, nullable=False, default="[]")
    total_km: Mapped[float] = mapped_column(Float, default=0.0)

    # Distance matrix JSON: {"KIGAMBONI_MOROGORO": 200, "MOROGORO_DODOMA": 260, ...}
    _distance_matrix: Mapped[str | None] = mapped_column("distance_matrix", Text, nullable=True)

    # Seasonal info
    rainy_season_penalty_pct: Mapped[float] = mapped_column(Float, default=0.0)
    passable_all_year: Mapped[bool] = mapped_column(Boolean, default=True)

    max_detour_km: Mapped[float] = mapped_column(Float, default=80.0)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # ── JSON helpers ──────────────────────────────────────────────
    @property
    def waypoints(self) -> list[str]:
        return json.loads(self._waypoints)

    @waypoints.setter
    def waypoints(self, value: list[str]) -> None:
        self._waypoints = json.dumps(value)

    @property
    def distance_matrix(self) -> dict[str, float]:
        return json.loads(self._distance_matrix) if self._distance_matrix else {}

    @distance_matrix.setter
    def distance_matrix(self, value: dict[str, float]) -> None:
        self._distance_matrix = json.dumps(value)

    def __repr__(self) -> str:
        return f"<RouteCorridor {self.name} — {self.origin_region}>"
