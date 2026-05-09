"""
scripts/seed_locations.py — Seed CustomerLogistics table from location master.

Reads: "location master.xlsx"
Columns: Name, City, District, Region, Country, Type, Kilometer, Status, Approval Status

The Kilometer column is the measured road distance from Kimbiji Plant — the most
accurate distance source available. This is seeded into CustomerLogistics.distance_km.

Usage:
    python scripts/seed_locations.py [--dry-run] [--file PATH]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from app.data.tanzania_regions import (
    ZONE_TO_CORRIDOR,
    normalise_city,
)
from app.database import AsyncSessionLocal, create_tables
from app.models import CustomerLogistics

console = Console()

DEFAULT_FILE = "location master.xlsx"


def parse_region(region_str: str) -> str | None:
    """Convert Odoo region string like 'Dodoma (TZ)' to canonical key."""
    if not region_str or pd.isna(region_str):
        return None
    clean = str(region_str).replace("(TZ)", "").replace("(tz)", "").strip()
    return normalise_city(clean) or clean.upper()


async def seed(file_path: str = DEFAULT_FILE, dry_run: bool = False) -> None:
    if not dry_run:
        await create_tables()

    fp = Path(file_path)
    if not fp.exists():
        console.print(f"[red]File not found: {fp}[/red]")
        sys.exit(1)

    console.print(f"[cyan]Reading: {fp.name}[/cyan]")
    df = pd.read_excel(fp)
    # Filter: approved records only
    if "Approval Status" in df.columns:
        df = df[df["Approval Status"] == "Approved"].copy()
    df = df.dropna(subset=["Name"])

    console.print(f"[cyan]{len(df)} approved locations found[/cyan]")

    inserted = 0
    skipped = 0
    no_km = 0

    async with AsyncSessionLocal() as session:
        for _, row in df.iterrows():
            name = str(row.get("Name", "")).strip()
            if not name:
                continue

            city = str(row.get("City", "")) if not pd.isna(row.get("City", "")) else ""
            region_raw = str(row.get("Region", "")) if not pd.isna(row.get("Region", "")) else ""
            region = parse_region(region_raw) or normalise_city(city)

            km_val = row.get("Kilometer")
            try:
                distance_km = float(km_val) if km_val and not pd.isna(km_val) else None
            except (ValueError, TypeError):
                distance_km = None

            if distance_km is None:
                no_km += 1

            # We use name as a proxy for odoo_partner_id during initial seed
            # (real partner IDs come from Odoo sync later)
            # Use a hash-based surrogate for now — will be overwritten on first Odoo sync
            import hashlib
            surrogate_id = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 10_000_000

            result = await session.execute(
                select(CustomerLogistics).where(
                    CustomerLogistics.customer_name == name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update distance_km if we have it and existing doesn't
                if distance_km and not existing.distance_km and not dry_run:
                    existing.distance_km = distance_km
                    skipped += 1
                else:
                    skipped += 1
                continue

            if not dry_run:
                cl = CustomerLogistics(
                    odoo_partner_id=surrogate_id,
                    customer_name=name,
                    city=city if city else None,
                    region=region,
                    distance_km=distance_km,
                    active=True,
                )
                session.add(cl)

            inserted += 1

        if not dry_run:
            await session.commit()

    # Summary table
    summary = Table(title="Location Seeding Summary", show_lines=True)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", justify="right")
    summary.add_row("Total locations in file", str(len(df)))
    summary.add_row("Inserted", f"[green]{inserted}[/green]")
    summary.add_row("Skipped (already exists)", str(skipped))
    summary.add_row("No distance (Kilometer blank)", f"[yellow]{no_km}[/yellow]")
    console.print(summary)

    if dry_run:
        console.print("[yellow]DRY RUN — no changes written.[/yellow]")
    else:
        console.print("[bold green]✓ Location seeding complete.[/bold green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed CustomerLogistics from location master")
    parser.add_argument("--file", default=DEFAULT_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(file_path=args.file, dry_run=args.dry_run))
