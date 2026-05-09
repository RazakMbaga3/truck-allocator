"""
app/services/scoring.py — Candidate order scoring for the matching engine.

Composite score:
  composite = 0.35×capacity_score + 0.40×route_score + 0.25×urgency_score
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import get_settings

settings = get_settings()


@dataclass
class CandidateScore:
    """Scoring result for one candidate order against one truck schedule."""
    order_id: int
    order_name: str
    delivery_region: str | None
    quantity_tonnes: float

    # Component scores (0.0–1.0 each)
    capacity_score: float       # how well quantity fills the truck
    route_score: float          # how close delivery is to the return corridor
    urgency_score: float        # deadline proximity (adjusted for near-ready)

    composite_score: float      # weighted sum

    # Raw values
    detour_km: float
    is_near_ready: bool


def score_candidate(
    order_id: int,
    order_name: str,
    delivery_region: str | None,
    quantity_tonnes: float,
    deadline_dt: datetime | None,
    dispatch_ready: bool,
    detour_km: float,
    truck_capacity_tonnes: float,
    is_near_ready: bool = False,
) -> CandidateScore:
    """Score a single candidate order for a given truck."""
    cfg = settings

    # ── Capacity score (0.0–1.0) ──────────────────────────────────
    if truck_capacity_tonnes > 0:
        fill_ratio = quantity_tonnes / truck_capacity_tonnes
        if fill_ratio <= 1.0:
            capacity_score = fill_ratio
        else:
            capacity_score = max(0.0, 1.0 - (fill_ratio - 1.0) * 2)
    else:
        capacity_score = 0.0

    # ── Route score (0.0–1.0) ─────────────────────────────────────
    max_detour = cfg.default_max_detour_km
    if detour_km <= 0:
        route_score = 1.0
    elif detour_km >= max_detour:
        route_score = 0.0
    else:
        route_score = 1.0 - (detour_km / max_detour)

    # ── Urgency score (0.0–1.0) ───────────────────────────────────
    base_urgency = _compute_urgency(deadline_dt)
    urgency_score = base_urgency * cfg.near_ready_score_penalty if is_near_ready else base_urgency

    # ── Composite ─────────────────────────────────────────────────
    composite = (
        cfg.score_weight_capacity * capacity_score
        + cfg.score_weight_route    * route_score
        + cfg.score_weight_urgency  * urgency_score
    )

    return CandidateScore(
        order_id=order_id,
        order_name=order_name,
        delivery_region=delivery_region,
        quantity_tonnes=quantity_tonnes,
        capacity_score=capacity_score,
        route_score=route_score,
        urgency_score=urgency_score,
        composite_score=composite,
        detour_km=detour_km,
        is_near_ready=is_near_ready,
    )


def _compute_urgency(deadline_dt: datetime | None) -> float:
    if deadline_dt is None:
        return 0.3

    now = datetime.now(timezone.utc)
    if deadline_dt.tzinfo is None:
        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

    hours_until = (deadline_dt - now).total_seconds() / 3600

    if hours_until <= 0:
        return 1.0
    elif hours_until <= 24:
        return 0.95
    elif hours_until <= 48:
        return 0.80
    elif hours_until <= 72:
        return 0.65
    elif hours_until <= 120:
        return 0.50
    elif hours_until <= 168:
        return 0.35
    elif hours_until <= 336:
        return 0.20
    else:
        return 0.10


def urgency_lookup(deadline_dt: datetime | None) -> float:
    """Convenience alias used by matching_engine."""
    return _compute_urgency(deadline_dt)
