"""
scripts/seed_routes.py — Seed RouteCorridor table from tanzania_regions.py data.

Usage:
    python scripts/seed_routes.py [--dry-run]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from app.config import get_settings
from app.data.tanzania_regions import CORRIDOR_WAYPOINTS, DISTANCE_MATRIX, REGIONS
from app.database import AsyncSessionLocal, create_tables
from app.models import RouteCorridor
from app.services.route_calculator import road_distance_km

console = Console()
settings = get_settings()

# Corridor definitions
CORRIDOR_DEFS = [
    {
        "name":           "CENTRAL",
        "display_name":   "Central Corridor (T3 Highway)",
        "description":    "Kigamboni → Chalinze → Morogoro → Dodoma → Tabora → Mwanza",
        "origin_region":  "DODOMA",
        "max_detour_km":  settings.corridor_max_detour_km["CENTRAL"],
        "passable_all_year": True,
        "rainy_season_penalty_pct": 0.0,
    },
    {
        "name":           "NORTHERN",
        "display_name":   "Northern Corridor (A14 / T2)",
        "description":    "Kigamboni → Chalinze → Segera → Tanga / Moshi / Arusha",
        "origin_region":  "TANGA",
        "max_detour_km":  settings.corridor_max_detour_km["NORTHERN"],
        "passable_all_year": True,
        "rainy_season_penalty_pct": 0.0,
    },
    {
        "name":           "SOUTHERN_HIGHLAND",
        "display_name":   "Southern Highland Corridor",
        "description":    "Kigamboni → Chalinze → Morogoro → Iringa → Mbeya",
        "origin_region":  "MBEYA",
        "max_detour_km":  settings.corridor_max_detour_km["SOUTHERN_HIGHLAND"],
        "passable_all_year": True,
        "rainy_season_penalty_pct": 0.05,
    },
    {
        "name":           "COASTAL",
        "display_name":   "Coastal Corridor (Route R1 — Gypsum)",
        "description":    "Kigamboni → Kibiti → Utete → Nyamisati → Ikwiriri → Kiranjeranje (Rufiji delta)",
        "origin_region":  "KIRANJERANJE",
        "max_detour_km":  settings.corridor_max_detour_km["COASTAL"],
        "passable_all_year": False,  # affected by long rains
        "rainy_season_penalty_pct": 0.20,
    },
    {
        "name":           "LAKE",
        "display_name":   "Lake Zone Corridor",
        "description":    "Kigamboni → Chalinze → Morogoro → Dodoma → Tabora → Mwanza → Geita",
        "origin_region":  "MWANZA",
        "max_detour_km":  settings.corridor_max_detour_km["LAKE"],
        "passable_all_year": True,
        "rainy_season_penalty_pct": 0.0,
    },
    {
        "name":           "SOUTHERN",
        "display_name":   "Southern Corridor (Coal/Ruvuma)",
        "description":    "Kigamboni → Chalinze → Morogoro → Iringa → Songea",
        "origin_region":  "SONGEA",
        "max_detour_km":  settings.corridor_max_detour_km.get("SOUTHERN", 80.0),
        "passable_all_year": True,
        "rainy_season_penalty_pct": 0.05,
    },
    {
        "name":           "LOCAL",
        "display_name":   "Local DSM Corridor",
        "description":    "Kigamboni → Dar es Salaam metropolitan area",
        "origin_region":  "DSM",
        "max_detour_km":  30.0,
        "passable_all_year": True,
        "rainy_season_penalty_pct": 0.0,
    },
]


async def seed(dry_run: bool = False) -> None:
    if not dry_run:
        await create_tables()

    async with AsyncSessionLocal() as session:
        table = Table(title="Route Corridor Seeding", show_lines=True)
        table.add_column("Corridor", style="cyan")
        table.add_column("Origin", style="yellow")
        table.add_column("Waypoints")
        table.add_column("Total km", justify="right")
        table.add_column("Max Detour km", justify="right")
        table.add_column("Action")

        for defn in CORRIDOR_DEFS:
            # Check if already exists
            result = await session.execute(
                select(RouteCorridor).where(RouteCorridor.name == defn["name"])
            )
            existing = result.scalar_one_or_none()

            waypoints = CORRIDOR_WAYPOINTS.get(defn["name"], [])
            # Compute total km (sum of consecutive leg distances)
            total_km = 0.0
            for i in range(len(waypoints) - 1):
                leg = road_distance_km(waypoints[i], waypoints[i + 1])
                if leg < 1e9:
                    total_km += leg

            # Build distance matrix JSON for this corridor
            matrix: dict[str, float] = {}
            for i, a in enumerate(waypoints):
                for b in waypoints[i + 1:]:
                    key = f"{a}_{b}"
                    matrix[key] = road_distance_km(a, b)

            action = "SKIP" if existing else "INSERT"

            if not dry_run and not existing:
                corridor = RouteCorridor(
                    name=defn["name"],
                    display_name=defn["display_name"],
                    description=defn["description"],
                    origin_region=defn["origin_region"],
                    total_km=total_km,
                    max_detour_km=defn["max_detour_km"],
                    passable_all_year=defn["passable_all_year"],
                    rainy_season_penalty_pct=defn["rainy_season_penalty_pct"],
                    active=True,
                )
                corridor.waypoints = waypoints
                corridor.distance_matrix = matrix
                session.add(corridor)
                action = "INSERTED"

            table.add_row(
                defn["name"],
                defn["origin_region"],
                " → ".join(waypoints[:4]) + ("..." if len(waypoints) > 4 else ""),
                f"{total_km:.0f}",
                f"{defn['max_detour_km']:.0f}",
                f"[green]{action}[/green]" if action != "SKIP" else "[dim]SKIP[/dim]",
            )

        console.print(table)

        if not dry_run:
            await session.commit()
            console.print("[bold green]✓ Route corridors seeded successfully.[/bold green]")
        else:
            console.print("[yellow]DRY RUN — no changes written.[/yellow]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed RouteCorridor table")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    asyncio.run(seed(dry_run=args.dry_run))
