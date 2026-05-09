"""
scripts/seed_customers.py — Enrich CustomerLogistics from Customer master.

Reads: "Customer master.xlsx"
Columns: Code, Customer/Firm/Agency Name, TIN, VRN, Business License No,
         Partner Type, Dormant, Street, Street2, Location, City, Zone, Region,
         District, Division, ZIP, Country, Salesperson, Phone, Email,
         Status, Approval Status

Matches on customer_name (exact) and updates Zone, corridor, phone.
Also creates new CustomerLogistics records for customers not already seeded.

Usage:
    python scripts/seed_customers.py [--dry-run] [--file PATH]
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

from app.data.tanzania_regions import ZONE_TO_CORRIDOR, normalise_city
from app.database import AsyncSessionLocal, create_tables
from app.models import CustomerLogistics

console = Console()

DEFAULT_FILE = "Customer master.xlsx"


def zone_to_corridor(zone: str) -> str | None:
    if not zone or pd.isna(zone):
        return None
    return ZONE_TO_CORRIDOR.get(str(zone).strip())


def parse_region(region_raw: str) -> str | None:
    if not region_raw or pd.isna(region_raw):
        return None
    clean = str(region_raw).replace("(TZ)", "").strip()
    return normalise_city(clean) or clean.upper().replace(" REGION", "")


async def seed(file_path: str = DEFAULT_FILE, dry_run: bool = False) -> None:
    if not dry_run:
        await create_tables()

    fp = Path(file_path)
    if not fp.exists():
        console.print(f"[red]File not found: {fp}[/red]")
        sys.exit(1)

    console.print(f"[cyan]Reading: {fp.name}[/cyan]")
    df = pd.read_excel(fp)

    # Only approved, non-dormant
    if "Approval Status" in df.columns:
        df = df[df["Approval Status"] == "Approved"].copy()
    if "Dormant" in df.columns:
        df = df[df["Dormant"] != True].copy()

    name_col = "Customer/Firm/Agency Name"
    df = df.dropna(subset=[name_col])
    console.print(f"[cyan]{len(df)} approved active customers found[/cyan]")

    updated = 0
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            code = str(row.get("Code", "")).strip()
            zone_raw = str(row.get("Zone", "")) if not pd.isna(row.get("Zone", "")) else ""
            region_raw = str(row.get("Region", "")) if not pd.isna(row.get("Region", "")) else ""
            city_raw = str(row.get("City", "")) if not pd.isna(row.get("City", "")) else ""
            phone = str(row.get("Phone", "")) if not pd.isna(row.get("Phone", "")) else ""

            zone = zone_raw.strip() if zone_raw else None
            corridor = zone_to_corridor(zone)
            region = parse_region(region_raw) or normalise_city(city_raw)

            # Look for existing record by name
            result = await session.execute(
                select(CustomerLogistics).where(
                    CustomerLogistics.customer_name == name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update missing fields
                changed = False
                if not existing.zone and zone:
                    existing.zone = zone
                    changed = True
                if not existing.corridor and corridor:
                    existing.corridor = corridor
                    changed = True
                if not existing.region and region:
                    existing.region = region
                    changed = True
                if not existing.city and city_raw:
                    existing.city = city_raw
                    changed = True
                if changed and not dry_run:
                    updated += 1
                else:
                    skipped += 1
            else:
                import hashlib
                surrogate_id = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 10_000_000

                if not dry_run:
                    cl = CustomerLogistics(
                        odoo_partner_id=surrogate_id,
                        customer_name=name,
                        city=city_raw if city_raw else None,
                        region=region,
                        zone=zone,
                        corridor=corridor,
                        active=True,
                    )
                    session.add(cl)
                inserted += 1

        if not dry_run:
            await session.commit()

    summary = Table(title="Customer Seeding Summary", show_lines=True)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", justify="right")
    summary.add_row("Total customers in file", str(len(df)))
    summary.add_row("Newly inserted", f"[green]{inserted}[/green]")
    summary.add_row("Updated (zone/corridor enriched)", f"[cyan]{updated}[/cyan]")
    summary.add_row("Skipped (no change)", str(skipped))
    console.print(summary)

    if dry_run:
        console.print("[yellow]DRY RUN — no changes written.[/yellow]")
    else:
        console.print("[bold green]✓ Customer seeding complete.[/bold green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed/enrich CustomerLogistics from customer master")
    parser.add_argument("--file", default=DEFAULT_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(file_path=args.file, dry_run=args.dry_run))
