"""
scripts/test_odoo_connection.py — Full Odoo connectivity and field health check.

Produces a rich health report showing:
  ✅ Connection established
  ✅ Authentication successful
  ✅ purchase.order readable (N records found)
  ✅ sale.order readable (N records found)
  ⚠️  x_dispatch_ready field missing (will use defaults)
  ✅ stock.picking (receipts) readable
  ✅ res.partner readable
  ✅ fleet.vehicle readable
  ✅ WRITE test (creating + deleting a test picking): OK

Usage:
    python scripts/test_odoo_connection.py
    python scripts/test_odoo_connection.py --write-test   # test write access
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich import box

from app.services.odoo_sync import OdooClient

console = Console()


def check(label: str, fn, *, warn_only: bool = False):
    """Run fn(), print ✅ or ❌/⚠️ result row. Returns (ok, result)."""
    try:
        result = fn()
        return True, result
    except Exception as e:
        return False, str(e)


def run_health_check(write_test: bool = False) -> None:
    console.rule("[bold #173158]NYATI CEMENT — Odoo Connection Health Check[/bold #173158]")

    client = OdooClient()

    table = Table(
        title="Odoo Health Report",
        show_lines=True,
        box=box.ROUNDED,
        width=90,
    )
    table.add_column("Check", style="cyan", min_width=35)
    table.add_column("Status", min_width=8, justify="center")
    table.add_column("Detail")

    all_ok = True

    # 1. Ping (version)
    ok, result = check("Server reachable (version)", lambda: client._common().version())
    status = "[green]✅[/green]" if ok else "[red]❌[/red]"
    detail = result.get("server_version", str(result)) if ok else str(result)
    if not ok:
        all_ok = False
    table.add_row("Server reachable", status, detail)

    # 2. Authentication
    ok, result = check("Authentication", lambda: client.authenticate())
    status = "[green]✅[/green]" if ok else "[red]❌[/red]"
    detail = f"uid={result}" if ok else str(result)
    if not ok:
        all_ok = False
    table.add_row("Authentication", status, detail)

    # 3. purchase.order
    ok, pos = check("purchase.order readable", lambda: client.fetch_rm_purchase_orders())
    status = "[green]✅[/green]" if ok else "[yellow]⚠️[/yellow]"
    detail = f"{len(pos)} confirmed POs found" if ok else str(pos)
    if not ok:
        all_ok = False
    table.add_row("purchase.order (RM POs)", status, detail)

    # 4. x_return_load_eligible field
    has_x_eligible = False
    if ok and pos:
        try:
            client._execute(
                "purchase.order", "search_read",
                [["x_return_load_eligible", "=", True]],
                {"fields": ["id"], "limit": 1},
            )
            has_x_eligible = True
        except Exception:
            pass
    x_status = "[green]✅[/green]" if has_x_eligible else "[yellow]⚠️[/yellow]"
    x_detail = "Field exists" if has_x_eligible else "Missing — treating all POs as eligible"
    table.add_row("x_return_load_eligible (PO)", x_status, x_detail)

    # 5. sale.order
    ok, sos = check("sale.order readable", lambda: client.fetch_sale_orders())
    status = "[green]✅[/green]" if ok else "[yellow]⚠️[/yellow]"
    detail = f"{len(sos)} confirmed SOs found" if ok else str(sos)
    if not ok:
        all_ok = False
    table.add_row("sale.order (Cement Orders)", status, detail)

    # 6. x_dispatch_ready field
    has_dispatch = False
    if ok and sos:
        try:
            client._execute(
                "sale.order", "search_read",
                [["x_dispatch_ready", "=", True]],
                {"fields": ["id"], "limit": 1},
            )
            has_dispatch = True
        except Exception:
            pass
    x_status = "[green]✅[/green]" if has_dispatch else "[yellow]⚠️[/yellow]"
    x_detail = "Field exists" if has_dispatch else "Missing — dispatch_ready will default False"
    table.add_row("x_dispatch_ready (SO)", x_status, x_detail)

    # 7. x_credit_cleared field
    has_credit = False
    if ok and sos:
        try:
            client._execute(
                "sale.order", "search_read",
                [["x_credit_cleared", "=", True]],
                {"fields": ["id"], "limit": 1},
            )
            has_credit = True
        except Exception:
            pass
    x_status = "[green]✅[/green]" if has_credit else "[yellow]⚠️[/yellow]"
    x_detail = "Field exists" if has_credit else "Missing — credit_cleared will default False"
    table.add_row("x_credit_cleared (SO)", x_status, x_detail)

    # 8. stock.picking (receipts)
    ok, picks = check(
        "stock.picking (receipts)",
        lambda: client.fetch_rm_receipts(["LPORD/2026/00001"]),
    )
    status = "[green]✅[/green]" if ok else "[yellow]⚠️[/yellow]"
    detail = "Receipts API accessible" if ok else str(picks)
    table.add_row("stock.picking (receipts)", status, detail)

    # 9. res.partner
    ok, partner = check(
        "res.partner readable",
        lambda: client.fetch_partner(1),
    )
    status = "[green]✅[/green]" if ok else "[yellow]⚠️[/yellow]"
    detail = f"partner id=1: {partner.get('name','?')}" if ok and partner else "No record for id=1 (normal)"
    table.add_row("res.partner", status, detail)

    # 10. fleet.vehicle
    ok, vehicles = check("fleet.vehicle readable", lambda: client.fetch_fleet_vehicles())
    status = "[green]✅[/green]" if ok else "[yellow]⚠️[/yellow]"
    detail = f"{len(vehicles)} vehicles found" if ok else str(vehicles)
    table.add_row("fleet.vehicle", status, detail)

    # 11. Write test (optional)
    if write_test:
        console.print("\n[yellow]Running write test...[/yellow]")
        # Try to create and immediately delete a test picking
        ok_write = False
        write_detail = "Skipped"
        try:
            picking_id = client.create_stock_picking(
                sale_order_id=1,
                partner_id=1,
                product_id=1,
                qty=0.001,
                schedule_ref="TEST",
                proposal_ref="TEST-WRITE",
            )
            if picking_id:
                # Delete the test picking
                uid = client._uid_or_auth()
                client._models().execute_kw(
                    client._db, uid, client._password,
                    "stock.picking", "unlink",
                    [[picking_id]],
                )
                ok_write = True
                write_detail = f"Created picking {picking_id}, deleted OK"
        except Exception as e:
            write_detail = str(e)
        status = "[green]✅[/green]" if ok_write else "[red]❌[/red]"
        table.add_row("WRITE test (create+delete picking)", status, write_detail)

    console.print(table)

    # Summary
    if all_ok:
        console.print("\n[bold green]✅ All critical checks passed. Odoo integration is ready.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠️  Some checks failed. Review items marked ❌ above.[/bold yellow]")

    # Sample PO data
    if isinstance(pos, list) and pos:
        console.rule("[dim]Sample Purchase Order Data[/dim]")
        po = pos[0]
        console.print(f"  First PO: [cyan]{po.get('name')}[/cyan]")
        console.print(f"  Partner:  {po.get('partner_id')}")
        console.print(f"  Date:     {po.get('scheduled_date')}")
        console.print(f"  Lines:    {len(po.get('_lines', []))}")

    # Sample SO data
    if isinstance(sos, list) and sos:
        console.rule("[dim]Sample Sale Order Data[/dim]")
        so = sos[0]
        console.print(f"  First SO:  [cyan]{so.get('name')}[/cyan]")
        console.print(f"  Customer:  {so.get('partner_id')}")
        console.print(f"  Dispatch?  {so.get('_dispatch_ready')}")
        console.print(f"  Credit?    {so.get('_credit_cleared')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Odoo connectivity and field availability")
    parser.add_argument("--write-test", action="store_true", help="Test write access (creates a test picking)")
    args = parser.parse_args()
    run_health_check(write_test=args.write_test)
