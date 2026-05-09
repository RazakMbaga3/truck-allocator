"""tests/test_route_calculator.py — Route intelligence tests."""

import pytest
from app.services.route_calculator import (
    detour_km,
    get_corridor_for_origin,
    get_route_waypoints,
    is_on_corridor,
    road_distance_km,
    route_position_pct,
    seasonal_penalty,
    sort_stops_by_route_order,
)


class TestRoadDistances:
    def test_kigamboni_morogoro(self):
        assert road_distance_km("KIGAMBONI", "MOROGORO") == 200.0

    def test_kigamboni_mbeya(self):
        assert road_distance_km("KIGAMBONI", "MBEYA") == 870.0

    def test_kigamboni_dodoma(self):
        assert road_distance_km("KIGAMBONI", "DODOMA") == 460.0

    def test_symmetric(self):
        ab = road_distance_km("MOROGORO", "DODOMA")
        ba = road_distance_km("DODOMA", "MOROGORO")
        assert ab == ba

    def test_self_distance_zero(self):
        assert road_distance_km("MOROGORO", "MOROGORO") == 0.0

    def test_floyd_warshall_fills_gaps(self):
        # TANGA → MOSHI not in seed dict but must be inferred
        d = road_distance_km("TANGA", "MOSHI")
        assert d > 0 and d < 400


class TestDetour:
    def test_zero_detour_on_corridor(self):
        # MOROGORO is perfectly between KIGAMBONI and DODOMA
        dev = detour_km("MOROGORO", "DODOMA")
        assert dev < 5.0

    def test_positive_detour_off_corridor(self):
        # TANGA is NOT on the MBEYA corridor
        dev = detour_km("TANGA", "MBEYA")
        assert dev > 200.0

    def test_iringa_on_southern_highland(self):
        dev = detour_km("IRINGA", "MBEYA")
        assert dev < 20.0  # Iringa is on the way to Mbeya


class TestCorridorMembership:
    def test_dodoma_on_central(self):
        assert is_on_corridor("DODOMA", "CENTRAL")

    def test_mbeya_on_southern_highland(self):
        assert is_on_corridor("MBEYA", "SOUTHERN_HIGHLAND")

    def test_tanga_not_on_southern_highland(self):
        assert not is_on_corridor("TANGA", "SOUTHERN_HIGHLAND")

    def test_mwanza_on_lake(self):
        assert is_on_corridor("MWANZA", "LAKE")


class TestRouteWaypoints:
    def test_kigamboni_to_mbeya_includes_endpoints(self):
        wps = get_route_waypoints("KIGAMBONI", "MBEYA")
        assert "KIGAMBONI" in wps
        assert "MBEYA" in wps

    def test_kigamboni_to_dodoma_via_morogoro(self):
        wps = get_route_waypoints("KIGAMBONI", "DODOMA")
        assert "MOROGORO" in wps  # intermediate stop

    def test_corridor_origin_mapping(self):
        assert get_corridor_for_origin("DODOMA") == "CENTRAL"
        assert get_corridor_for_origin("MBEYA") == "SOUTHERN_HIGHLAND"
        assert get_corridor_for_origin("TANGA") == "NORTHERN"


class TestSortStops:
    def test_sort_nearest_first(self):
        stops = ["DODOMA", "MOROGORO", "MWANZA"]
        sorted_stops = sort_stops_by_route_order(stops, "CENTRAL", reverse=False)
        # MOROGORO (200km) < DODOMA (460km) < MWANZA (1260km)
        assert sorted_stops.index("MOROGORO") < sorted_stops.index("DODOMA")

    def test_sort_farthest_first_for_loading(self):
        stops = ["DODOMA", "MOROGORO"]
        # LIFO loading: load DODOMA cargo first (delivered last)
        sorted_stops = sort_stops_by_route_order(stops, "CENTRAL", reverse=True)
        assert sorted_stops[0] == "DODOMA"


class TestSeasonalPenalty:
    def test_coastal_march_penalty(self):
        penalty = seasonal_penalty("COASTAL", 4)  # April (long rains)
        assert penalty == 0.20

    def test_central_no_penalty(self):
        assert seasonal_penalty("CENTRAL", 4) == 0.0

    def test_coastal_dry_season_no_penalty(self):
        assert seasonal_penalty("COASTAL", 7) == 0.0  # July (dry)
