"""
app/services/route_calculator.py — Route intelligence for Tanzania corridors.

Provides:
  - Floyd-Warshall all-pairs shortest path (fills in missing distance pairs)
  - detour_km(delivery_region, truck_origin) — cost of serving a customer on a return route
  - is_on_corridor(delivery_region, corridor_name) — fast corridor membership check
  - sort_stops_by_route_order(stops, corridor_name) — order stops for loading sequence
  - route_position_pct(region, corridor) — 0.0 (near plant) → 1.0 (far end)
  - seasonal_penalty(corridor_name, month) — rainy season km penalty

Design:
  The Floyd-Warshall matrix is built once at module import time from the
  DISTANCE_MATRIX seed data. Every pair that has no direct data is filled in
  via the algorithm. This means detour_km is always available, even for
  region pairs not directly in the seed dict.
"""

from __future__ import annotations

import math
from functools import lru_cache

from app.data.tanzania_regions import (
    CORRIDOR_WAYPOINTS,
    DISTANCE_MATRIX,
    REGIONS,
    RM_ORIGIN_TO_CORRIDOR,
    get_corridor_for_region,
)

# ── Build Floyd-Warshall complete distance matrix ─────────────────────────────

_INFINITY = math.inf


def _build_fw_matrix() -> dict[tuple[str, str], float]:
    """
    Run Floyd-Warshall over all known regions to fill in all pairwise
    road distances.  Returns a complete dict[tuple[str, str], float].
    """
    all_nodes = list(REGIONS.keys())
    # Initialise with seed data (bidirectional)
    dist: dict[tuple[str, str], float] = {}
    for node in all_nodes:
        dist[(node, node)] = 0.0
    for (a, b), km in DISTANCE_MATRIX.items():
        a = a.upper()
        b = b.upper()
        dist[(a, b)] = min(km, dist.get((a, b), _INFINITY))
        dist[(b, a)] = min(km, dist.get((b, a), _INFINITY))

    # Floyd-Warshall
    for k in all_nodes:
        for i in all_nodes:
            for j in all_nodes:
                through_k = dist.get((i, k), _INFINITY) + dist.get((k, j), _INFINITY)
                if through_k < dist.get((i, j), _INFINITY):
                    dist[(i, j)] = through_k

    return dist


# Computed once at import time — O(n³) but n ≈ 30 nodes → negligible
_FW: dict[tuple[str, str], float] = _build_fw_matrix()

# Assertions: spot-check the matrix at import time
assert _FW.get(("KIGAMBONI", "MOROGORO"), _INFINITY) == 200.0, "KGM→MOROGORO should be 200"
assert _FW.get(("KIGAMBONI", "MBEYA"), _INFINITY) == 870.0, "KGM→MBEYA should be 870"
assert _FW.get(("MOROGORO", "IRINGA"), _INFINITY) <= 320.0, "MOROGORO→IRINGA ≤ 320"


def road_distance_km(origin: str, destination: str) -> float:
    """
    Return road distance in km between two region keys.
    Returns math.inf if no path is found (should not happen for known regions).
    """
    if origin == destination:
        return 0.0
    return _FW.get((origin.upper(), destination.upper()), _INFINITY)


def detour_km(
    delivery_region: str,
    truck_origin_region: str,
    plant_region: str = "KIGAMBONI",
) -> float:
    """
    Calculate the km detour a truck must make to deliver to delivery_region
    on its return from plant_region to truck_origin_region.

    detour = dist(plant → delivery) + dist(delivery → truck_origin)
             - dist(plant → truck_origin)

    A value of 0 means the delivery is perfectly on the return corridor.
    A positive value means the truck must deviate that many km.
    """
    d_plant_delivery = road_distance_km(plant_region, delivery_region)
    d_delivery_origin = road_distance_km(delivery_region, truck_origin_region)
    d_plant_origin = road_distance_km(plant_region, truck_origin_region)

    if d_plant_origin == _INFINITY:
        return _INFINITY

    result = d_plant_delivery + d_delivery_origin - d_plant_origin
    return max(0.0, result)  # never negative due to triangle inequality


def is_on_corridor(delivery_region: str, corridor_name: str, max_detour: float = 80.0) -> bool:
    """
    Return True if delivery_region is within max_detour km of the corridor.
    Uses the last waypoint (far end) of the corridor as the truck origin.
    """
    waypoints = CORRIDOR_WAYPOINTS.get(corridor_name.upper(), [])
    if not waypoints:
        return False
    truck_origin = waypoints[-1]
    dev = detour_km(delivery_region.upper(), truck_origin.upper())
    return dev <= max_detour


def get_corridor_for_origin(origin_region: str) -> str:
    """Map an RM origin region to its return corridor."""
    return RM_ORIGIN_TO_CORRIDOR.get(origin_region.upper(), "CENTRAL")


def route_position_pct(region: str, corridor_name: str) -> float:
    """
    Returns a float 0.0–1.0 indicating how far along the corridor
    the delivery point is (0 = near plant, 1 = far end).

    Used for sequencing stops on a loaded truck:
    load the last delivery first (LIFO stacking).
    """
    waypoints = CORRIDOR_WAYPOINTS.get(corridor_name.upper(), [])
    if region.upper() in waypoints:
        idx = waypoints.index(region.upper())
        return idx / max(len(waypoints) - 1, 1)
    # Not a named waypoint — estimate from km distance
    plant_to_region = road_distance_km("KIGAMBONI", region.upper())
    if waypoints:
        plant_to_end = road_distance_km("KIGAMBONI", waypoints[-1])
        if plant_to_end > 0:
            return min(1.0, plant_to_region / plant_to_end)
    return 0.5


def sort_stops_by_route_order(
    stops: list[str], corridor_name: str, reverse: bool = False
) -> list[str]:
    """
    Sort a list of region names by their position along the corridor.
    Default order: plant → far end (first stop is nearest the plant).
    Pass reverse=True for loading order (load far-end cargo first — LIFO).
    """
    def key(r: str) -> float:
        return route_position_pct(r, corridor_name)

    return sorted(stops, key=key, reverse=reverse)


def get_route_waypoints(origin: str, destination: str) -> list[str]:
    """
    Return the ordered waypoint list from origin to destination
    using the appropriate corridor.
    """
    if origin.upper() == "KIGAMBONI":
        corridor = get_corridor_for_origin(destination.upper())
        waypoints = CORRIDOR_WAYPOINTS.get(corridor, [])
        # Trim to include only waypoints up to and including destination
        result = []
        for wp in waypoints:
            result.append(wp)
            if wp == destination.upper():
                break
        return result if result else ["KIGAMBONI", destination.upper()]
    return ["KIGAMBONI", destination.upper()]


_RAINY_MONTHS_LONG: set[int] = {3, 4, 5}    # March–May (long rains)
_RAINY_MONTHS_SHORT: set[int] = {11, 12}     # Nov–Dec (short rains)
_COASTAL_RAINY_PENALTY_PCT: float = 0.20     # 20% slower on coastal routes


def seasonal_penalty(corridor_name: str, month: int) -> float:
    """
    Return a penalty factor (0.0 = no penalty, 0.20 = 20% slower / longer).
    The COASTAL corridor (Rufiji delta) is most affected by rains.
    """
    if corridor_name.upper() == "COASTAL":
        if month in _RAINY_MONTHS_LONG:
            return _COASTAL_RAINY_PENALTY_PCT
        if month in _RAINY_MONTHS_SHORT:
            return _COASTAL_RAINY_PENALTY_PCT * 0.5
    return 0.0


# ── Inline assertions ─────────────────────────────────────────────────────────
# These run at module import — catch mis-wired routes immediately.

# detour of 0 for a city perfectly on a corridor
assert detour_km("MOROGORO", "DODOMA") < 5.0, \
    "MOROGORO is on the way to DODOMA — detour should be ~0"

assert detour_km("ARUSHA", "MBEYA") > 200.0, \
    "ARUSHA is NOT on the MBEYA (Southern Highland) route"

assert is_on_corridor("DODOMA", "CENTRAL"), "DODOMA is on CENTRAL corridor"
assert is_on_corridor("MBEYA", "SOUTHERN_HIGHLAND"), "MBEYA is on SOUTHERN_HIGHLAND"
assert not is_on_corridor("TANGA", "SOUTHERN_HIGHLAND"), "TANGA is NOT on SOUTHERN_HIGHLAND"

_wps = get_route_waypoints("KIGAMBONI", "MBEYA")
assert "KIGAMBONI" in _wps and "MBEYA" in _wps, "Route KIGAMBONI→MBEYA must include both endpoints"
