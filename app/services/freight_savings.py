"""Freight savings calculations for return-truck allocations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


FREIGHT_RATE_TZS_PER_KM_TONNE: dict[str, float] = {
    "NORTHERN": 210.0,
    "CENTRAL": 200.0,
    "SOUTHERN": 200.0,
    "SOUTHERN_COAST": 200.0,
    "SOUTHERN_HIGHLAND": 200.0,
    "SOUTHERN_HIGHLANDS": 200.0,
    "LAKE_VICTORIA": 200.0,
    "LOCAL": 200.0,
}

DEFAULT_FREIGHT_RATE_TZS_PER_KM_TONNE = 200.0
RETURN_LOAD_RATE_PCT = 0.60
HOLDING_COST_TZS_PER_TONNE_HOUR = 1_000.0


@dataclass(frozen=True)
class FreightSavings:
    order_id: int
    order_ref: str
    corridor: str | None
    distance_km: float
    tonnes: float
    fresh_freight_tzs: float
    return_freight_tzs: float
    gross_saving_tzs: float
    holding_cost_saved_tzs: float
    net_saving_tzs: float
    saving_per_tonne_tzs: float


def estimate_fresh_freight(
    distance_km: float,
    tonnes: float,
    corridor: str | None,
) -> float:
    if distance_km <= 0 or tonnes <= 0:
        return 0.0

    rate = FREIGHT_RATE_TZS_PER_KM_TONNE.get(
        (corridor or "").upper(),
        DEFAULT_FREIGHT_RATE_TZS_PER_KM_TONNE,
    )
    return distance_km * tonnes * rate


def compute_hold_hours(deadline_dt: datetime | None) -> float:
    if deadline_dt is None:
        return 12.0

    now = datetime.now(timezone.utc)
    if deadline_dt.tzinfo is None:
        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

    hours_until_deadline = (deadline_dt - now).total_seconds() / 3600.0
    if hours_until_deadline <= 0:
        return 24.0
    if hours_until_deadline >= 24.0:
        return 0.0
    return round(24.0 - hours_until_deadline, 2)


def compute_savings(
    order_id: int,
    order_ref: str,
    distance_km: float,
    tonnes: float,
    corridor: str | None,
    deadline_dt: datetime | None = None,
) -> FreightSavings:
    fresh = estimate_fresh_freight(distance_km, tonnes, corridor)
    return_freight = fresh * RETURN_LOAD_RATE_PCT
    gross = fresh - return_freight
    holding_saved = compute_hold_hours(deadline_dt) * tonnes * HOLDING_COST_TZS_PER_TONNE_HOUR
    net = gross + holding_saved

    return FreightSavings(
        order_id=order_id,
        order_ref=order_ref,
        corridor=corridor,
        distance_km=distance_km,
        tonnes=tonnes,
        fresh_freight_tzs=fresh,
        return_freight_tzs=return_freight,
        gross_saving_tzs=gross,
        holding_cost_saved_tzs=holding_saved,
        net_saving_tzs=net,
        saving_per_tonne_tzs=(net / tonnes) if tonnes > 0 else 0.0,
    )
