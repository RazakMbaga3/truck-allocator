"""
scripts/seed_demo.py -- Minimal demo data for fast UI preview.

Creates:
  - 3 transporters
  - 4 inbound truck schedules (2 corridors)
  - 6 cement orders
  - 2 historical dispatched trips (KPI dashboard)
  - 3 proposals (1 per truck route)

Run:
  .venv\\Scripts\\python.exe scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete, text, update

from app.database import AsyncSessionLocal, create_tables
from app.models import (
    Transporter, TruckSchedule, CementOrder, AllocationProposal, SavingsLedger,
)
from app.models.truck_schedule import TruckScheduleStatus as TSS, AllocationStatus
from app.models.allocation_proposal import ProposalStatus, ProposalVariant
from app.models.cement_order import OrderAllocationStatus
from app.models.matching_event import MatchingEvent


def now_tz() -> datetime:
    return datetime.now(timezone.utc)

def hours(h: float) -> datetime:
    return now_tz() + timedelta(hours=h)

def days_ago(d: float) -> datetime:
    return now_tz() - timedelta(days=d)


# ── 3 TRANSPORTERS ────────────────────────────────────────────────────────────

TRANSPORTERS = [
    dict(
        odoo_vendor_code="CMLT2307", name="MWAMBA INVESTMENT LTD (KAIXIN)",
        contact_name="Kaixin Fleet Mgr", contact_phone="+255 784 000 001",
        fleet_size=18, avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Open", "Tipper"], preferred_corridors=["NORTHERN"],
        origin_region="TANGA", reliability_score=8.5, return_load_rate_pct=0.58,
        notes="Primary Clinker Tanga→Kimbiji",
    ),
    dict(
        odoo_vendor_code="CMLT0559", name="STATE MINING CORPORATION",
        contact_name="Coal Fleet Sup", contact_phone="+255 784 000 004",
        fleet_size=25, avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Open", "Tipper"], preferred_corridors=["SOUTHERN_HIGHLAND"],
        origin_region="MBEYA", reliability_score=7.5, return_load_rate_pct=0.55,
        notes="Coal Kyela/Mbeya",
    ),
    dict(
        odoo_vendor_code="CMLT1333", name="PECOT GENERAL SUPPLIES LTD",
        contact_name="Pecot Dispatch", contact_phone="+255 784 000 005",
        fleet_size=8, avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Tipper"], preferred_corridors=["CENTRAL"],
        origin_region="DODOMA", reliability_score=7.2, return_load_rate_pct=0.62,
        notes="Iron Ore Dodoma",
    ),
]


# ── 4 TRUCK SCHEDULES ─────────────────────────────────────────────────────────

TRUCK_SCHEDULES = [
    dict(
        schedule_ref="SCHED-2026-001", odoo_po_name="LPORD/2026/02345",
        transporter_idx=0, origin_region="TANGA", raw_material_type="CLINKER",
        estimated_qty_tonnes=30.28, truck_plate="T946BXS",
        driver_name="ALEX BENEDICT", driver_license_no="4000728011",
        driver_phone="+255 754 111 001", dealer_number="RM/2026/01109",
        actual_capacity_tonnes=30.28, corridor_name="NORTHERN",
        return_route=["KIMBIJI", "CHALINZE", "SEGERA", "TANGA"],
        max_detour_km=80.0, expected_arrival_dt=hours(4),
        status=TSS.PRE_CONFIRMED, allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-2026-002", odoo_po_name="LPORD/2026/02346",
        transporter_idx=0, origin_region="TANGA", raw_material_type="CLINKER",
        estimated_qty_tonnes=30.06, truck_plate="T865EHY",
        driver_name="JUMA SALIM HASSAN", driver_license_no="4001628246",
        driver_phone="+255 754 111 002", dealer_number="RM/2026/01110",
        actual_capacity_tonnes=30.06, corridor_name="NORTHERN",
        return_route=["KIMBIJI", "CHALINZE", "SEGERA", "TANGA"],
        max_detour_km=80.0, expected_arrival_dt=hours(12),
        status=TSS.PRE_CONFIRMED, allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-2026-004", odoo_po_name="LPORD/2026/02201",
        transporter_idx=1, origin_region="MBEYA", raw_material_type="COAL",
        estimated_qty_tonnes=29.0, truck_plate="T824DFZ",
        driver_name="HEMED ALLY", driver_license_no="4001113660",
        driver_phone="+255 754 222 001", dealer_number="RM/2026/00605",
        actual_capacity_tonnes=29.0, corridor_name="SOUTHERN_HIGHLAND",
        return_route=["KIMBIJI", "CHALINZE", "MOROGORO", "IRINGA", "MBEYA"],
        max_detour_km=120.0, expected_arrival_dt=hours(8),
        status=TSS.PRE_CONFIRMED, allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-2026-005", odoo_po_name="LPORD/2026/01998",
        transporter_idx=2, origin_region="DODOMA", raw_material_type="IRON_ORE",
        estimated_qty_tonnes=29.46, truck_plate="T397BUR",
        driver_name="ABDUL-RAHIM", driver_license_no="4000044339",
        driver_phone="+255 754 333 001", dealer_number="RM/2026/00407",
        actual_capacity_tonnes=29.46, corridor_name="CENTRAL",
        return_route=["KIMBIJI", "CHALINZE", "MOROGORO", "DODOMA"],
        max_detour_km=80.0, expected_arrival_dt=hours(6),
        status=TSS.PRE_CONFIRMED, allocation_status=AllocationStatus.UNMATCHED,
    ),
]


# ── 6 CEMENT ORDERS ───────────────────────────────────────────────────────────

CEMENT_ORDERS = [
    dict(
        odoo_order_id=10001, odoo_order_name="SO/2026/01001",
        customer_name="MKOMBOZI HARDWARE - TANGA",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Bombo Street, Tanga", distance_from_plant_km=360,
        product_name="CEM II A-L 42.5 R", quantity_tonnes=25.0,
        deadline_dt=hours(48), urgency_score=7.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10002, odoo_order_name="SO/2026/01002",
        customer_name="KILIMANJARO BUILDERS",
        delivery_region="KILIMANJARO", delivery_corridor="NORTHERN",
        delivery_address="Old Moshi Rd", distance_from_plant_km=480,
        product_name="CEM II A-L 42.5 R", quantity_tonnes=30.0,
        deadline_dt=hours(36), urgency_score=8.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10003, odoo_order_name="SO/2026/01003",
        customer_name="SEGERA HARDWARE",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Segera Township", distance_from_plant_km=270,
        product_name="CEM II A-L 42.5 R", quantity_tonnes=18.0,
        deadline_dt=hours(60), urgency_score=5.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=20001, odoo_order_name="SO/2026/02001",
        customer_name="MBEYA CEMENT DIST",
        delivery_region="MBEYA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Mbeya City", distance_from_plant_km=870,
        product_name="CEM II A-L 42.5 R", quantity_tonnes=30.0,
        deadline_dt=hours(72), urgency_score=6.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=20002, odoo_order_name="SO/2026/02002",
        customer_name="IRINGA BUILDERS",
        delivery_region="IRINGA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Iringa Town", distance_from_plant_km=430,
        product_name="CEM II A-L 42.5 R", quantity_tonnes=20.0,
        deadline_dt=hours(48), urgency_score=7.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=30001, odoo_order_name="SO/2026/03001",
        customer_name="ESTIM CONSTRUCTION",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="MOF YARD - DODOMA", distance_from_plant_km=460,
        product_name="CEM II B-M 42.5 N", quantity_tonnes=30.0,
        deadline_dt=hours(48), urgency_score=7.0,
        dispatch_ready=True, credit_cleared=True,
    ),
]


# ── 2 HISTORICAL TRIPS (KPI dashboard) ────────────────────────────────────────

HISTORICAL = [
    dict(
        schedule_ref="SCHED-HIST-H01", truck_plate="T866EHY",
        transporter_name="MWAMBA INVESTMENT LTD (KAIXIN)",
        corridor_name="NORTHERN", origin_region="TANGA",
        fresh_freight_avoided=2_268_000, return_freight_paid=1_315_440,
        holding_cost_saved=125_000, allocated_tonnes=29.5,
        utilization=98.3, n_orders=2, dispatched_at=days_ago(1),
    ),
    dict(
        schedule_ref="SCHED-HIST-H02", truck_plate="T794ELM",
        transporter_name="STATE MINING CORPORATION",
        corridor_name="SOUTHERN_HIGHLAND", origin_region="MBEYA",
        fresh_freight_avoided=5_220_000, return_freight_paid=2_871_000,
        holding_cost_saved=210_000, allocated_tonnes=30.0,
        utilization=100.0, n_orders=2, dispatched_at=days_ago(2),
    ),
]


# ── RATES ─────────────────────────────────────────────────────────────────────

RATE = {"NORTHERN": 210, "SOUTHERN_HIGHLAND": 200, "CENTRAL": 200, "LOCAL": 80}

def fresh_freight(corridor, km, tonnes):
    return km * tonnes * RATE.get(corridor, 200)

def return_freight(fresh, pct=0.60):
    return fresh * pct

def net_saving(fresh, ret, hold=0):
    return fresh - ret + hold


# ── SEED FUNCTIONS ────────────────────────────────────────────────────────────

async def clear_demo_data(db):
    print("  Clearing existing data...")
    for table in ["savings_ledger", "proposal_items", "allocation_proposals",
                  "matching_events", "cement_orders", "truck_schedules", "transporters"]:
        await db.execute(text(f"DELETE FROM {table}"))
    await db.commit()


async def seed_transporters(db):
    idx_map = {}
    for i, t in enumerate(TRANSPORTERS):
        obj = Transporter(
            odoo_vendor_code=t["odoo_vendor_code"], name=t["name"],
            contact_name=t["contact_name"], contact_phone=t["contact_phone"],
            fleet_size=t["fleet_size"], avg_truck_capacity_tonnes=t["avg_truck_capacity_tonnes"],
            origin_region=t["origin_region"], reliability_score=t["reliability_score"],
            return_load_rate_pct=t["return_load_rate_pct"], notes=t["notes"],
            backhaul_willing=True, active=True,
        )
        obj.vehicle_types    = t["vehicle_types"]
        obj.preferred_corridors = t["preferred_corridors"]
        db.add(obj)
        idx_map[i] = obj
    await db.flush()
    print(f"  ✓ {len(idx_map)} transporters")
    return idx_map


async def seed_schedules(db, tmap):
    schedules = []
    for s in TRUCK_SCHEDULES:
        tr = tmap[s["transporter_idx"]]
        obj = TruckSchedule(
            schedule_ref=s["schedule_ref"], odoo_po_name=s["odoo_po_name"],
            transporter_id=tr.id, transporter_name=tr.name,
            origin_region=s["origin_region"], raw_material_type=s["raw_material_type"],
            estimated_qty_tonnes=s["estimated_qty_tonnes"],
            truck_plate=s["truck_plate"], driver_name=s["driver_name"],
            driver_license_no=s["driver_license_no"], driver_phone=s["driver_phone"],
            dealer_number=s["dealer_number"], actual_capacity_tonnes=s["actual_capacity_tonnes"],
            corridor_name=s["corridor_name"], max_detour_km=s["max_detour_km"],
            expected_arrival_dt=s["expected_arrival_dt"],
            status=s["status"], allocation_status=s["allocation_status"],
        )
        obj.return_route = s["return_route"]
        db.add(obj)
        schedules.append(obj)
    await db.flush()
    print(f"  ✓ {len(schedules)} truck schedules")
    return schedules


async def seed_orders(db):
    orders = []
    for o in CEMENT_ORDERS:
        ff = fresh_freight(o["delivery_corridor"], o["distance_from_plant_km"], o["quantity_tonnes"])
        obj = CementOrder(
            odoo_order_id=o["odoo_order_id"], odoo_order_name=o["odoo_order_name"],
            odoo_state="sale", customer_name=o["customer_name"],
            delivery_region=o["delivery_region"], delivery_corridor=o["delivery_corridor"],
            delivery_address=o["delivery_address"],
            distance_from_plant_km=o["distance_from_plant_km"],
            product_name=o["product_name"], quantity_tonnes=o["quantity_tonnes"],
            quantity_bags=int(o["quantity_tonnes"] * 20),
            fresh_outbound_freight_tzs=ff,
            unit_price_tzs=145_000,
            total_value_tzs=o["quantity_tonnes"] * 20 * 145_000,
            deadline_dt=o["deadline_dt"], urgency_score=o["urgency_score"],
            dispatch_ready=o["dispatch_ready"], credit_cleared=o["credit_cleared"],
            partial_load_allowed=False,
            return_load_eligible=True, near_ready=False,
            allocation_status=OrderAllocationStatus.UNALLOCATED,
            loading_priority=2 if o["urgency_score"] >= 8 else 3,
        )
        db.add(obj)
        orders.append(obj)
    await db.flush()
    print(f"  ✓ {len(orders)} cement orders")
    return orders


async def seed_proposals(db):
    today = now_tz().strftime("%Y%m%d")
    res = await db.execute(
        select(TruckSchedule).where(TruckSchedule.status.in_([TSS.EXPECTED, TSS.PRE_CONFIRMED]))
    )
    schedules = res.scalars().all()

    res2 = await db.execute(
        select(CementOrder).where(
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
            CementOrder.return_load_eligible == True,
        )
    )
    all_orders = res2.scalars().all()

    corridor_orders: dict[str, list] = {}
    for o in all_orders:
        if o.dispatch_ready and o.credit_cleared:
            corridor_orders.setdefault(o.delivery_corridor, []).append(o)

    total = 0
    for i, sched in enumerate(schedules, 1):
        eligible = corridor_orders.get(sched.corridor_name, [])
        if not eligible:
            continue

        cap = sched.actual_capacity_tonnes
        selected, remaining = [], cap
        for o in sorted(eligible, key=lambda x: -x.urgency_score):
            if o.quantity_tonnes <= remaining:
                selected.append((o, o.quantity_tonnes))
                remaining -= o.quantity_tonnes
            if remaining <= 0:
                break

        if not selected:
            continue

        total_t  = sum(t for _, t in selected)
        total_ff = sum(fresh_freight(sched.corridor_name, o.distance_from_plant_km, t) for o, t in selected)
        total_ret = return_freight(total_ff)
        savings  = net_saving(total_ff, total_ret, len(selected) * 50_000)
        score    = round(0.30 * min(savings / 2_000_000, 1) + 0.25 * min(total_t / cap, 1) + 0.45, 3)

        await db.execute(
            update(TruckSchedule)
            .where(TruckSchedule.id == sched.id)
            .values(allocation_status=AllocationStatus.PROPOSED)
        )

        prop = AllocationProposal(
            proposal_ref=f"PROP-{today}-{i:03d}-A",
            schedule_id=sched.id,
            variant_type=ProposalVariant.BEST_MATCH,
            total_allocated_tonnes=round(total_t, 2),
            capacity_utilization_pct=round(total_t / cap * 100, 1),
            total_route_deviation_km=round(len(selected) * 18.0, 1),
            number_of_stops=len(selected),
            total_fresh_freight_tzs=round(total_ff),
            total_return_freight_tzs=round(total_ret),
            holding_cost_tzs=round(len(selected) * 50_000),
            estimated_savings_tzs=round(savings),
            composite_score=score,
            ai_recommendation="CONFIRM" if score >= 0.65 else "REVIEW",
            ai_reasoning=f"{len(selected)} stops {sched.corridor_name}, {total_t:.0f}MT, TZS {savings:,.0f}",
            status=ProposalStatus.PROPOSED,
        )
        prop._ai_warnings = json.dumps([])
        db.add(prop)
        await db.flush()

        from app.models.allocation_proposal import ProposalItem as PI
        for seq, (o, tonnes) in enumerate(selected, 1):
            item_ff  = fresh_freight(sched.corridor_name, o.distance_from_plant_km, tonnes)
            item_ret = return_freight(item_ff)
            db.add(PI(
                proposal_id=prop.id, cement_order_id=o.id,
                allocated_tonnes=round(tonnes, 2), allocated_bags=int(tonnes * 20),
                sequence=seq, delivery_deviation_km=round(18.0 * seq, 1),
                item_savings_tzs=round(net_saving(item_ff, item_ret)),
                is_near_ready=False,
            ))
        total += 1

    await db.flush()
    print(f"  ✓ {total} proposals generated")


async def seed_historical(db):
    for i, h in enumerate(HISTORICAL, 1):
        sched = TruckSchedule(
            schedule_ref=h["schedule_ref"], origin_region=h["origin_region"],
            raw_material_type="CLINKER" if "KAIXIN" in h["transporter_name"] else (
                "COAL" if "MINING" in h["transporter_name"] else "IRON_ORE"
            ),
            estimated_qty_tonnes=h["allocated_tonnes"],
            truck_plate=h["truck_plate"], corridor_name=h["corridor_name"],
            max_detour_km=80.0,
            expected_arrival_dt=h["dispatched_at"] - timedelta(hours=12),
            actual_arrival_dt=h["dispatched_at"] - timedelta(hours=6),
            dispatched_at=h["dispatched_at"],
            status=TSS.COMPLETED, allocation_status=AllocationStatus.DISPATCHED,
        )
        sched.return_route = []
        db.add(sched)
        await db.flush()

        prop_ref = f"PROP-HIST-{i:03d}-A"
        prop = AllocationProposal(
            proposal_ref=prop_ref, schedule_id=sched.id,
            variant_type=ProposalVariant.BEST_MATCH,
            total_allocated_tonnes=h["allocated_tonnes"],
            capacity_utilization_pct=h["utilization"],
            total_route_deviation_km=h["n_orders"] * 18.0,
            number_of_stops=h["n_orders"],
            total_fresh_freight_tzs=h["fresh_freight_avoided"],
            total_return_freight_tzs=h["return_freight_paid"],
            holding_cost_tzs=h["holding_cost_saved"],
            estimated_savings_tzs=net_saving(h["fresh_freight_avoided"], h["return_freight_paid"], h["holding_cost_saved"]),
            composite_score=0.82, ai_recommendation="CONFIRM",
            ai_reasoning="Historical allocation — dispatched.",
            status=ProposalStatus.DISPATCHED,
            confirmed_by="Demo Dispatcher",
            confirmed_at=h["dispatched_at"] - timedelta(hours=8),
            dispatched_at=h["dispatched_at"],
        )
        prop._ai_warnings = json.dumps([])
        db.add(prop)
        await db.flush()

        mk = h["dispatched_at"].strftime("%Y-%m")
        db.add(SavingsLedger(
            proposal_id=prop.id, schedule_id=sched.id,
            proposal_ref=prop_ref, schedule_ref=h["schedule_ref"],
            truck_plate=h["truck_plate"], transporter_name=h["transporter_name"],
            corridor_name=h["corridor_name"], origin_region=h["origin_region"],
            fresh_freight_avoided_tzs=h["fresh_freight_avoided"],
            return_freight_paid_tzs=h["return_freight_paid"],
            holding_cost_saved_tzs=h["holding_cost_saved"],
            net_savings_tzs=net_saving(h["fresh_freight_avoided"], h["return_freight_paid"], h["holding_cost_saved"]),
            allocated_tonnes=h["allocated_tonnes"],
            capacity_utilization_pct=h["utilization"],
            number_of_orders=h["n_orders"],
            dispatch_date=h["dispatched_at"], month_key=mk,
        ))

    await db.flush()
    print(f"  ✓ {len(HISTORICAL)} historical KPI entries")


async def main():
    print("\nSmart Return Truck Allocator — Minimal Demo Seed")
    print("=" * 50)
    await create_tables()

    async with AsyncSessionLocal() as db:
        await clear_demo_data(db)
        tmap = await seed_transporters(db)
        await db.commit()

        await seed_schedules(db, tmap)
        await db.commit()

        await seed_orders(db)
        await db.commit()

        await seed_proposals(db)
        await db.commit()

        await seed_historical(db)
        await db.commit()

    print("=" * 50)
    print("✓ Ready — http://localhost:8001/\n")


if __name__ == "__main__":
    asyncio.run(main())
