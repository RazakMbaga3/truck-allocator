"""tests/test_freight_savings.py — Freight savings calculator tests."""

from datetime import datetime, timedelta, timezone

import pytest
from app.services.freight_savings import (
    FreightSavings,
    compute_hold_hours,
    compute_savings,
    estimate_fresh_freight,
)


class TestEstimateFreshFreight:
    def test_tanga_30t(self):
        # 360km × 30T × TZS 210/km/T = TZS 2,268,000
        result = estimate_fresh_freight(360, 30, "NORTHERN")
        assert result == 360 * 30 * 210.0

    def test_mbeya_30t(self):
        # 870km × 30T × TZS 200/km/T = TZS 5,220,000
        result = estimate_fresh_freight(870, 30, "SOUTHERN_HIGHLAND")
        assert result == 870 * 30 * 200.0

    def test_zero_distance_returns_zero(self):
        assert estimate_fresh_freight(0, 30, "CENTRAL") == 0.0

    def test_zero_tonnes_returns_zero(self):
        assert estimate_fresh_freight(460, 0, "CENTRAL") == 0.0

    def test_unknown_corridor_uses_default_rate(self):
        r1 = estimate_fresh_freight(460, 30, "UNKNOWN_CORRIDOR")
        r2 = estimate_fresh_freight(460, 30, None)
        assert r1 == r2 == 460 * 30 * 200.0


class TestComputeHoldHours:
    def test_past_deadline_returns_24(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert compute_hold_hours(past) == 24.0

    def test_deadline_within_24h_high_hold(self):
        soon = datetime.now(timezone.utc) + timedelta(hours=12)
        hours = compute_hold_hours(soon)
        assert hours >= 12.0

    def test_far_deadline_low_hold(self):
        far = datetime.now(timezone.utc) + timedelta(days=30)
        hours = compute_hold_hours(far)
        assert hours <= 48.0

    def test_none_deadline_returns_default(self):
        assert compute_hold_hours(None) == 12.0


class TestComputeSavings:
    def test_gross_saving_is_40pct_of_fresh(self):
        result = compute_savings(1, "SO/001", 460, 30, "CENTRAL")
        expected_fresh = 460 * 30 * 200.0
        assert abs(result.fresh_freight_tzs - expected_fresh) < 1
        assert abs(result.return_freight_tzs - expected_fresh * 0.60) < 1
        assert abs(result.gross_saving_tzs - expected_fresh * 0.40) < 1

    def test_net_saving_exceeds_gross(self):
        # Holding cost pushes net above gross
        result = compute_savings(1, "SO/001", 460, 30, "CENTRAL",
                                 deadline_dt=datetime.now(timezone.utc) + timedelta(hours=12))
        assert result.net_saving_tzs > result.gross_saving_tzs

    def test_mbeya_30t_saves_over_1_5m(self):
        result = compute_savings(2, "SO/002", 870, 30, "SOUTHERN_HIGHLAND")
        assert result.net_saving_tzs > 1_500_000, f"Expected >TZS 1.5M, got {result.net_saving_tzs:,.0f}"

    def test_saving_per_tonne_is_positive(self):
        result = compute_savings(3, "SO/003", 200, 15, "CENTRAL")
        assert result.saving_per_tonne_tzs > 0

    def test_dataclass_fields_present(self):
        result = compute_savings(4, "SO/004", 360, 20, "NORTHERN")
        assert isinstance(result, FreightSavings)
        assert result.order_id == 4
        assert result.corridor == "NORTHERN"
