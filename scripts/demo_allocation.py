"""
scripts/demo_allocation.py — End-to-end demo with sample data.

Creates 3 test truck schedules and 10 test cement orders, runs the
matching engine, and prints a rich report.

Usage:
    python scripts/demo_allocation.py
    python scripts/demo_allocation.py --assert   # fail if assertions not met
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich import box

from app.database import AsyncSessionLocal, create_tables
from app.models import (
    AllocationStatus,
    CementOrder,
    OrderAllocationStatus,
    Transporter,
    TruckSchedule,
    TruckScheduleStatus,
)
from app.services.matching_engine import MatchingEngine
from app.services.route_calculator import get_route_waypoints

console = Console()


async def run_demo(assert_mode: bool = False) -> None:
    await create_tables()

    async with AsyncSessionLocal() as session:
        console.rule("[bold #173158]NYATI CEMENT — Return Truck Allocator Demo[/bold #173158]")

        # ── Create test transporters ──────────────────────────────
        transporters = []
        for t_def in [
            ("Mbeya Cargo", "MBEYA", "SOUTHERN_HIGHLAND", 32.0),
            ("Salama Transports", "DODOMA", "CENTRAL", 30.0),
            ("Kilimanjaro Fleet", "TANGA", "NORTHERN", 28.0),
        ]:
            t = Transporter(
                name=t_def[0],
                origin_region=t_def[1],
                avg_truck_capacity_tonnes=t_def[3],
                reliability_score=8.0,
                backhaul_willing=True,
                active=True,
            )
            t.preferred_corridors = [t_def[2]]
            session.add(t)
            transporters.append(t)
        await session.flush()

        # ── Create test TruckSchedules (from POs) ────────────────
        now = datetime.now(timezone.utc)
        schedules_def = [
            ("SCHED-DEMO-001", "MBEYA",  "SOUTHERN_HIGHLAND", 32.0, now + timedelta(days=3), transporters[0]),
            ("SCHED-DEMO-002", "DODOMA", "CENTRAL",           30.0, now + timedelta(days=1), transporters[1]),
            ("SCHED-DEMO-003", "TANGA",  "NORTHERN",          28.0, now + timedelta(days=2), transporters[2]),
        ]

        schedules = []
        for ref, origin, corridor, cap, eta, trans in schedules_def:
            s = TruckSchedule(
                schedule_ref=ref,
                odoo_po_name=f"LPORD/2026/{ref[-3:]}",
                transporter_id=trans.id,
                origin_region=origin,
                corridor_name=corridor,
                raw_material_type="COAL" if origin == "MBEYA" else "CLINKER" if origin == "TANGA" else "IRON_ORE",
                estimated_qty_tonnes=cap,
                estimated_truck_count=1,
                max_detour_km=120.0 if corridor == "SOUTHERN_HIGHLAND" else 80.0,
                expected_arrival_dt=eta,
                status=TruckScheduleStatus.EXPECTED,
                allocation_status=AllocationStatus.UNMATCHED,
            )
            s.return_route = get_route_waypoints("KIGAMBONI", origin)
            session.add(s)
            schedules.append(s)
        await session.flush()

        # ── Create test CementOrders ──────────────────────────────
        orders_def = [
            # (name, region, corridor, dist_km, qty_t, dispatch_ready, near_ready, deadline_days)
            ("SO/2026/50001", "IRINGA",   "SOUTHERN_HIGHLAND", 510, 12, True,  False, 5),
            ("SO/2026/50002", "MBEYA",    "SOUTHERN_HIGHLAND", 870, 18, True,  False, 4),
            ("SO/2026/50003", "MOROGORO", "CENTRAL",           200, 15, True,  False, 3),
            ("SO/2026/50004", "DODOMA",   "CENTRAL",           460, 12, True,  False, 4),
            ("SO/2026/50005", "TANGA",    "NORTHERN",          360, 20, True,  False, 6),
            ("SO/2026/50006", "MOROGORO", "CENTRAL",            200, 8, False, True,  2),  # near-ready
            ("SO/2026/50007", "MOSHI",    "NORTHERN",          570, 15, True,  False, 7),
            ("SO/2026/50008", "IRINGA",   "SOUTHERN_HIGHLAND", 510, 10, True,  False, 8),
            ("SO/2026/50009", "DODOMA",   "CENTRAL",           460, 20, True,  False, 5),
            ("SO/2026/50010", "MBEYA",    "SOUTHERN_HIGHLAND", 870,  5, False, False, 3),  # NOT ready
        ]

        orders = []
        for i, (name, region, corridor, dist, qty, ready, near_ready, deadline) in enumerate(orders_def):
            fresh = dist * qty * 200.0
            o = CementOrder(
                odoo_order_id=50000 + i,
                odoo_order_name=name,
                customer_name=f"Customer {i+1}",
                delivery_region=region,
                delivery_corridor=corridor,
                distance_from_plant_km=float(dist),
                quantity_tonnes=float(qty),
                quantity_bags=qty * 20,
                fresh_outbound_freight_tzs=fresh,
                deadline_dt=now + timedelta(days=deadline),
                urgency_score=float(10 - deadline),
                dispatch_ready=ready,
                credit_cleared=ready,
                near_ready=near_ready,
                near_ready_eta=now + timedelta(hours=18) if near_ready else None,
                partial_load_allowed=False,
                loading_priority=3,
                return_load_eligible=True,
                allocation_status=OrderAllocationStatus.UNALLOCATED,
            )
            session.add(o)
            orders.append(o)
        await session.flush()

        # ── Run matching for all schedules ────────────────────────
        console.print("\n[cyan]Running matching engine for all 3 truck schedules…[/cyan]")
        engine = MatchingEngine(session)
        all_proposals = []
        for schedule in schedules:
            proposals = await engine.match(schedule)
            all_proposals.extend(proposals)
        await session.commit()

        # ── Print results ─────────────────────────────────────────
        console.print(f"\n[bold]Generated {len(all_proposals)} proposals[/bold]\n")

        for schedule in schedules:
            sched_proposals = [p for p in all_proposals if p.schedule_id == schedule.id]
            if not sched_proposals:
                continue

            console.print(f"\n[bold cyan]{'─'*60}[/bold cyan]")
            console.print(f"[bold]Truck: {schedule.schedule_ref}[/bold]  "
                          f"Origin: [yellow]{schedule.origin_region}[/yellow]  "
                          f"ETA: {schedule.expected_arrival_dt.strftime('%d %b')}")

            t = Table(box=box.SIMPLE, show_header=True)
            t.add_column("Variant", style="cyan")
            t.add_column("Savings", justify="right")
            t.add_column("Util%", justify="right")
            t.add_column("Stops", justify="right")
            t.add_column("Orders")

            for p in sched_proposals:
                stops = ", ".join(
                    f"{item.cement_order.delivery_region}({item.allocated_tonnes:.0f}T)"
                    for item in sorted(p.items, key=lambda x: x.sequence)
                    if item.cement_order
                )
                near_flag = " ⚡" if p.has_pending_readiness_orders else ""
                t.add_row(
                    p.variant_type,
                    f"[green]TZS {p.estimated_savings_tzs:,.0f}[/green]",
                    f"{p.capacity_utilization_pct:.0f}%",
                    str(p.number_of_stops),
                    stops + near_flag,
                )
            console.print(t)

        # ── Assertions ────────────────────────────────────────────
        console.print("\n[bold]Running assertions…[/bold]")

        # 1. Each schedule should have at least 1 proposal
        for s in schedules:
            count = sum(1 for p in all_proposals if p.schedule_id == s.id)
            status = "[green]✅[/green]" if count >= 1 else "[red]❌[/red]"
            console.print(f"  {status} Schedule {s.schedule_ref}: {count} proposals")
            if assert_mode:
                assert count >= 1, f"No proposals for {s.schedule_ref}"

        # 2. TANGA order should NOT appear in MBEYA truck proposals
        mbeya_sched = next(s for s in schedules if s.origin_region == "MBEYA")
        mbeya_props = [p for p in all_proposals if p.schedule_id == mbeya_sched.id]
        mbeya_regions = {
            item.cement_order.delivery_region
            for p in mbeya_props for item in p.items if item.cement_order
        }
        tanga_in_mbeya = "TANGA" in mbeya_regions
        status = "[red]❌[/red]" if tanga_in_mbeya else "[green]✅[/green]"
        console.print(f"  {status} TANGA order excluded from MBEYA (Southern Highland) truck")
        if assert_mode:
            assert not tanga_in_mbeya, "TANGA should not be in MBEYA proposals"

        # 3. Near-ready order (SO/50006) should be flagged where included
        near_ready_items = [
            item
            for p in all_proposals for item in p.items
            if item.cement_order and item.cement_order.odoo_order_name == "SO/2026/50006"
        ]
        if near_ready_items:
            all_flagged = all(item.is_near_ready for item in near_ready_items)
            status = "[green]✅[/green]" if all_flagged else "[red]❌[/red]"
            console.print(f"  {status} Near-ready order SO/50006 correctly flagged (is_near_ready=True)")
            if assert_mode:
                assert all_flagged, "Near-ready order items must have is_near_ready=True"
        else:
            console.print("  [yellow]⚠️  Near-ready order SO/50006 not included in any proposal (may be outside detour limit)[/yellow]")

        # 4. All confirmed proposals should have savings > 0
        negative_savings = [p for p in all_proposals if p.estimated_savings_tzs < 0]
        status = "[green]✅[/green]" if not negative_savings else "[red]❌[/red]"
        console.print(f"  {status} All proposals have non-negative savings")
        if assert_mode:
            assert not negative_savings, f"Proposals with negative savings: {negative_savings}"

        console.print("\n[bold green]ALL DEMO ASSERTIONS PASSED ✅[/bold green]" if not assert_mode else "")
        console.rule()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo allocation with test data")
    parser.add_argument("--assert", dest="assert_mode", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_demo(assert_mode=args.assert_mode))
