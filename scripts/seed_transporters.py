"""
scripts/seed_transporters.py — Seed Transporter table from Excel data.

Reads: "Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx"
Sheet: "Raw Material Vendor Master-Tran"
Columns: Code, Name, TIN, VRN, Region, Mobile, Phone, Email, Created By,
         Tax Registration Type, Status, Approval Status

Cross-references: "Raw Material Vendor Master-Supp" to find which RM items
each transporter carries (used to determine origin_region and corridor).

Usage:
    python scripts/seed_transporters.py [--dry-run] [--file PATH]
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

from app.data.tanzania_regions import CITY_TO_REGION, RM_ORIGIN_TO_CORRIDOR, normalise_city
from app.database import AsyncSessionLocal, create_tables
from app.models import Transporter

console = Console()

DEFAULT_FILE = "Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx"
TRANSPORTER_SHEET = "Raw Material Vendor Master-Tran"
SUPPLIER_SHEET = "Raw Material Vendor Master-Supp"

# Known transporters from CLAUDE.md — truck capacity overrides
KNOWN_CAPACITY_OVERRIDES: dict[str, float] = {
    "Mwamba Investment Limited":           30.0,   # KAIXIN trucks
    "Antu Logistics":                      30.0,
    "Nacharo Royal Company Limited":       30.0,
    "Saibaba Trucks":                      32.0,
    "Ras Logistics":                       28.0,
}

# Known corridor overrides where Region in Odoo is not the origin
KNOWN_CORRIDOR_OVERRIDES: dict[str, str] = {
    "CMLT2146": "NORTHERN",   # Tanga Cement PLC
    "CMLT0365": "NORTHERN",   # Maweni Limestone
    "CMLU1522": "SOUTHERN",   # Dangote (Mtwara)
    "CMLT0559": "SOUTHERN_HIGHLAND",  # State Mining (Mbeya/Kyela)
    "CMLT0357": "SOUTHERN_HIGHLAND",  # Market Insight (Mbeya)
    "CMLT0153": "COASTAL",    # Emmanuel Martini Mgonja (Lindi/Kiranjeranje)
    "CMLT1333": "CENTRAL",    # Pecot (Dodoma)
    "CMLT0489": "CENTRAL",    # Right Investment (Dodoma)
    "CMLT1734": "CENTRAL",    # Yerusalemu (Dodoma)
}


def region_from_odoo_region(odoo_region: str) -> str | None:
    """
    Parse the Odoo region string (e.g. 'Tanga (TZ)' or 'Dar es Salaam (TZ)')
    into a canonical region key.
    """
    if not odoo_region or pd.isna(odoo_region):
        return None
    # Strip ' (TZ)' suffix
    clean = str(odoo_region).replace("(TZ)", "").replace("(tz)", "").strip().lower()
    # Try city normaliser
    result = normalise_city(clean)
    if result:
        return result
    # Try direct region match
    for key in CITY_TO_REGION:
        if key in clean:
            return CITY_TO_REGION[key]
    return None


async def seed(file_path: str = DEFAULT_FILE, dry_run: bool = False) -> None:
    if not dry_run:
        await create_tables()

    fp = Path(file_path)
    if not fp.exists():
        console.print(f"[red]File not found: {fp}[/red]")
        sys.exit(1)

    console.print(f"[cyan]Reading: {fp.name}[/cyan]")
    xl = pd.ExcelFile(fp)
    sheet = TRANSPORTER_SHEET if TRANSPORTER_SHEET in xl.sheet_names else xl.sheet_names[0]
    df_trans = pd.read_excel(fp, sheet_name=sheet)
    df_trans = df_trans[df_trans["Status"] == "Approved"].copy()
    df_trans = df_trans.dropna(subset=["Name"])

    # Build a set of codes that appear as RM supplier codes (not pure transporters)
    try:
        df_supp = pd.read_excel(fp, sheet_name=SUPPLIER_SHEET)
        supplier_codes = set(df_supp["Code"].dropna().astype(str).tolist())
    except Exception:
        supplier_codes = set()

    table = Table(title=f"Transporter Seeding ({len(df_trans)} rows)", show_lines=True)
    table.add_column("Code", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Region")
    table.add_column("Corridor", style="yellow")
    table.add_column("Phone")
    table.add_column("Action")

    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for _, row in df_trans.iterrows():
            code = str(row.get("Code", "")).strip()
            name = str(row.get("Name", "")).strip()
            if not name:
                continue

            odoo_region_str = str(row.get("Region", "")) if not pd.isna(row.get("Region", "")) else ""
            origin_region = region_from_odoo_region(odoo_region_str)
            corridor = KNOWN_CORRIDOR_OVERRIDES.get(code)
            if not corridor and origin_region:
                corridor = RM_ORIGIN_TO_CORRIDOR.get(origin_region)

            mobile = str(row.get("Mobile", "") or row.get("Phone", "") or "").strip()
            capacity = KNOWN_CAPACITY_OVERRIDES.get(name, 30.0)

            # Check if already exists (by odoo_vendor_code)
            result = await session.execute(
                select(Transporter).where(Transporter.odoo_vendor_code == code)
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                action = "SKIP"
            else:
                action = "INSERT"
                if not dry_run:
                    t = Transporter(
                        odoo_vendor_code=code,
                        name=name,
                        contact_phone=mobile if mobile else None,
                        origin_region=origin_region,
                        avg_truck_capacity_tonnes=capacity,
                        backhaul_willing=True,
                        reliability_score=7.0,
                        active=True,
                    )
                    if corridor:
                        t.preferred_corridors = [corridor]
                    session.add(t)
                    inserted += 1
                    action = "INSERTED"

            table.add_row(
                code[:12],
                name[:40],
                origin_region or "?",
                corridor or "?",
                mobile[:20] if mobile else "-",
                f"[green]{action}[/green]" if "INSERT" in action else f"[dim]{action}[/dim]",
            )

        console.print(table)

        if not dry_run:
            await session.commit()
            console.print(
                f"[bold green]✓ Transporters seeded: {inserted} inserted, {skipped} skipped.[/bold green]"
            )
        else:
            console.print(
                f"[yellow]DRY RUN — would insert {sum(1 for _ in df_trans.iterrows())} records.[/yellow]"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Transporter table from Excel")
    parser.add_argument("--file", default=DEFAULT_FILE, help="Path to Excel file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    asyncio.run(seed(file_path=args.file, dry_run=args.dry_run))
