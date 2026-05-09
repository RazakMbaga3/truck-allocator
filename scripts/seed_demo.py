"""
scripts/seed_demo.py -- Realistic demo data for UI preview.

Creates:
  - 6 real-named transporters (from actual LCL fleet data)
  - 10 inbound truck schedules across all 4 corridors
  - 38 cement orders spread across matching corridors
  - Runs matching engine -> generates 3-variant proposals for each truck
  - 5 already-dispatched historical trips -> populates KPI savings dashboard

Run:
  .venv\\Scripts\\python.exe scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta, timezone

# ── Path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete, text, update

from app.database import AsyncSessionLocal, create_tables
from app.models import (
    Transporter, TruckSchedule, CementOrder, AllocationProposal,
    SavingsLedger,
)
from app.models.truck_schedule import TruckScheduleStatus as TSS, AllocationStatus
from app.models.allocation_proposal import ProposalStatus, ProposalVariant
from app.models.cement_order import OrderAllocationStatus
from app.models.matching_event import MatchingEvent

# ── Helpers ──────────────────────────────────────────────────────────────────

def now_tz() -> datetime:
    return datetime.now(timezone.utc)

def hours_from_now(h: float) -> datetime:
    return now_tz() + timedelta(hours=h)

def days_ago(d: float) -> datetime:
    return now_tz() - timedelta(days=d)


# ── Freight rate table (TZS / km / tonne) ────────────────────────────────────
RATE = {
    "NORTHERN":          210,
    "SOUTHERN_HIGHLAND": 200,
    "CENTRAL":           200,
    "COASTAL":           220,
    "LAKE":              190,
    "SOUTHERN":          200,
    "LOCAL":              80,
}

def fresh_freight(corridor: str, distance_km: float, tonnes: float) -> float:
    return distance_km * tonnes * RATE.get(corridor, 200)

def return_freight(fresh: float, rate_pct: float = 0.60) -> float:
    return fresh * rate_pct

def net_saving(fresh: float, ret: float, hold: float = 0) -> float:
    return fresh - ret + hold


# ── TRANSPORTERS ─────────────────────────────────────────────────────────────

TRANSPORTERS = [
    dict(
        odoo_vendor_code="CMLT2307",
        name="MWAMBA INVESTMENT LIMITED (KAIXIN)",
        contact_name="Kaixin Fleet Manager",
        contact_phone="+255 784 000 001",
        fleet_size=18,
        avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Open", "Tipper"],
        preferred_corridors=["NORTHERN"],
        origin_region="TANGA",
        reliability_score=8.5,
        return_load_rate_pct=0.58,
        notes="Primary Clinker fleet Tanga->Kimbiji. Known trucks: T865EHY, T866EHY, T867EHY, T868EHY",
    ),
    dict(
        odoo_vendor_code="CMLT2320",
        name="NACHARO ROYAL COMPANY LIMITED",
        contact_name="Nacharo Ops",
        contact_phone="+255 784 000 002",
        fleet_size=12,
        avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Open"],
        preferred_corridors=["NORTHERN"],
        origin_region="TANGA",
        reliability_score=8.0,
        return_load_rate_pct=0.60,
        notes="Known trucks: T218EJE, T216EJE, T258EJE, T724EKJ",
    ),
    dict(
        odoo_vendor_code="CMLT2322",
        name="ANTU LOGISTICS CO. LIMITED",
        contact_name="Antu Logistics Manager",
        contact_phone="+255 784 000 003",
        fleet_size=10,
        avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Open", "Tipper"],
        preferred_corridors=["NORTHERN"],
        origin_region="TANGA",
        reliability_score=7.8,
        return_load_rate_pct=0.60,
        notes="Known trucks: T316ENF, T431CPQ, T490ENX, T476ENX",
    ),
    dict(
        odoo_vendor_code="CMLT0559",
        name="STATE MINING CORPORATION (COAL)",
        contact_name="Coal Fleet Supervisor",
        contact_phone="+255 784 000 004",
        fleet_size=25,
        avg_truck_capacity_tonnes=30.0,
        vehicle_types=["Open", "Tipper"],
        preferred_corridors=["SOUTHERN_HIGHLAND"],
        origin_region="MBEYA",
        reliability_score=7.5,
        return_load_rate_pct=0.55,
        notes="Coal supplier Kyela/Mbeya. Long-haul, willing on backhaul at 55%.",
    ),
    dict(
        odoo_vendor_code="CMLT1333",
        name="PECOT GENERAL SUPPLIES LTD",
        contact_name="Pecot Dispatch",
        contact_phone="+255 784 000 005",
        fleet_size=8,
        avg_truck_capacity_tonnes=28.0,
        vehicle_types=["Tipper"],
        preferred_corridors=["CENTRAL"],
        origin_region="DODOMA",
        reliability_score=7.2,
        return_load_rate_pct=0.62,
        notes="Iron Ore from Dodoma (Asanje). Smaller fleet.",
    ),
    dict(
        odoo_vendor_code="CMLT0153",
        name="EMMANUEL MARTINI MGONJA",
        contact_name="Martini Dispatch",
        contact_phone="+255 784 000 006",
        fleet_size=6,
        avg_truck_capacity_tonnes=28.0,
        vehicle_types=["Open"],
        preferred_corridors=["COASTAL"],
        origin_region="KIRANJERANJE",
        reliability_score=7.0,
        return_load_rate_pct=0.65,
        notes="Gypsum Route R1: Kiranjeranje->Kibiti->Nyamisati->Kimbiji. Coastal route.",
    ),
]


# ── TRUCK SCHEDULES ───────────────────────────────────────────────────────────
# 10 inbound trucks: mix of EXPECTED / PRE_CONFIRMED, arriving at various times

TRUCK_SCHEDULES = [
    # ── NORTHERN (Clinker / Tanga) ─────────────────────────────────
    dict(
        schedule_ref="SCHED-20260502-001",
        odoo_po_name="LPORD/2026/02345",
        transporter_idx=0,  # KAIXIN
        origin_region="TANGA",
        raw_material_type="CLINKER",
        estimated_qty_tonnes=30.0,
        truck_plate="T865EHY",
        driver_name="Juma Salim Hassan",
        driver_phone="+255 754 111 001",
        actual_capacity_tonnes=32.0,
        corridor_name="NORTHERN",
        return_route=["KIMBIJI", "CHALINZE", "SEGERA", "TANGA"],
        max_detour_km=80.0,
        expected_arrival_dt=hours_from_now(6),
        status=TSS.PRE_CONFIRMED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-20260502-002",
        odoo_po_name="LPORD/2026/02346",
        transporter_idx=1,  # NACHARO ROYAL
        origin_region="TANGA",
        raw_material_type="CLINKER",
        estimated_qty_tonnes=30.0,
        truck_plate="T218EJE",
        driver_name="Hamisi Bakari",
        driver_phone="+255 754 111 002",
        actual_capacity_tonnes=30.0,
        corridor_name="NORTHERN",
        return_route=["KIMBIJI", "CHALINZE", "SEGERA", "TANGA"],
        max_detour_km=80.0,
        expected_arrival_dt=hours_from_now(14),
        status=TSS.PRE_CONFIRMED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-20260502-003",
        odoo_po_name="LPORD/2026/02347",
        transporter_idx=2,  # ANTU LOGISTICS
        origin_region="TANGA",
        raw_material_type="CLINKER",
        estimated_qty_tonnes=30.0,
        truck_plate=None,
        driver_name=None,
        driver_phone=None,
        actual_capacity_tonnes=None,
        corridor_name="NORTHERN",
        return_route=["KIMBIJI", "CHALINZE", "SEGERA", "TANGA"],
        max_detour_km=80.0,
        expected_arrival_dt=hours_from_now(28),
        status=TSS.EXPECTED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    # ── SOUTHERN HIGHLAND (Coal / Mbeya) ──────────────────────────
    dict(
        schedule_ref="SCHED-20260502-004",
        odoo_po_name="LPORD/2026/02201",
        transporter_idx=3,  # STATE MINING
        origin_region="MBEYA",
        raw_material_type="COAL",
        estimated_qty_tonnes=30.0,
        truck_plate="T795ELM",
        driver_name="Omari Juma Mkwawa",
        driver_phone="+255 754 222 001",
        actual_capacity_tonnes=30.0,
        corridor_name="SOUTHERN_HIGHLAND",
        return_route=["KIMBIJI", "CHALINZE", "MOROGORO", "IRINGA", "MBEYA"],
        max_detour_km=120.0,
        expected_arrival_dt=hours_from_now(10),
        status=TSS.PRE_CONFIRMED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-20260502-005",
        odoo_po_name="LPORD/2026/02202",
        transporter_idx=3,  # STATE MINING
        origin_region="MBEYA",
        raw_material_type="COAL",
        estimated_qty_tonnes=30.0,
        truck_plate=None,
        driver_name=None,
        driver_phone=None,
        actual_capacity_tonnes=None,
        corridor_name="SOUTHERN_HIGHLAND",
        return_route=["KIMBIJI", "CHALINZE", "MOROGORO", "IRINGA", "MBEYA"],
        max_detour_km=120.0,
        expected_arrival_dt=hours_from_now(36),
        status=TSS.EXPECTED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    # ── CENTRAL (Iron Ore / Dodoma) ───────────────────────────────
    dict(
        schedule_ref="SCHED-20260502-006",
        odoo_po_name="LPORD/2026/01998",
        transporter_idx=4,  # PECOT
        origin_region="DODOMA",
        raw_material_type="IRON_ORE",
        estimated_qty_tonnes=28.0,
        truck_plate="T633EJW",
        driver_name="Rashidi Mwenye",
        driver_phone="+255 754 333 001",
        actual_capacity_tonnes=28.0,
        corridor_name="CENTRAL",
        return_route=["KIMBIJI", "CHALINZE", "MOROGORO", "DODOMA"],
        max_detour_km=80.0,
        expected_arrival_dt=hours_from_now(8),
        status=TSS.PRE_CONFIRMED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-20260502-007",
        odoo_po_name="LPORD/2026/01999",
        transporter_idx=4,  # PECOT
        origin_region="DODOMA",
        raw_material_type="IRON_ORE",
        estimated_qty_tonnes=28.0,
        truck_plate=None,
        driver_name=None,
        driver_phone=None,
        actual_capacity_tonnes=None,
        corridor_name="CENTRAL",
        return_route=["KIMBIJI", "CHALINZE", "MOROGORO", "DODOMA"],
        max_detour_km=80.0,
        expected_arrival_dt=hours_from_now(32),
        status=TSS.EXPECTED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    # ── COASTAL (Gypsum / Lindi Route R1) ────────────────────────
    dict(
        schedule_ref="SCHED-20260502-008",
        odoo_po_name="LPORD/2026/01765",
        transporter_idx=5,  # MARTINI
        origin_region="KIRANJERANJE",
        raw_material_type="GYPSUM",
        estimated_qty_tonnes=28.0,
        truck_plate="T718EKT",
        driver_name="Selemani Juma",
        driver_phone="+255 754 444 001",
        actual_capacity_tonnes=28.0,
        corridor_name="COASTAL",
        return_route=["KIMBIJI", "IKWIRIRI", "NYAMISATI", "UTETE", "KIBITI", "KIRANJERANJE"],
        max_detour_km=60.0,
        expected_arrival_dt=hours_from_now(5),
        status=TSS.PRE_CONFIRMED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    dict(
        schedule_ref="SCHED-20260502-009",
        odoo_po_name="LPORD/2026/01766",
        transporter_idx=5,  # MARTINI
        origin_region="KIRANJERANJE",
        raw_material_type="GYPSUM",
        estimated_qty_tonnes=28.0,
        truck_plate=None,
        driver_name=None,
        driver_phone=None,
        actual_capacity_tonnes=None,
        corridor_name="COASTAL",
        return_route=["KIMBIJI", "IKWIRIRI", "NYAMISATI", "UTETE", "KIBITI", "KIRANJERANJE"],
        max_detour_km=60.0,
        expected_arrival_dt=hours_from_now(30),
        status=TSS.EXPECTED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
    # ── NORTHERN (Clinker / Tanga) -- arriving tomorrow ────────────
    dict(
        schedule_ref="SCHED-20260502-010",
        odoo_po_name="LPORD/2026/02348",
        transporter_idx=0,  # KAIXIN
        origin_region="TANGA",
        raw_material_type="CLINKER",
        estimated_qty_tonnes=30.0,
        truck_plate=None,
        driver_name=None,
        driver_phone=None,
        actual_capacity_tonnes=None,
        corridor_name="NORTHERN",
        return_route=["KIMBIJI", "CHALINZE", "SEGERA", "TANGA"],
        max_detour_km=80.0,
        expected_arrival_dt=hours_from_now(52),
        status=TSS.EXPECTED,
        allocation_status=AllocationStatus.UNMATCHED,
    ),
]


# ── CEMENT ORDERS ─────────────────────────────────────────────────────────────
# 38 orders: NORTHERN(12), SOUTHERN_HIGHLAND(10), CENTRAL(9), COASTAL(7)

CEMENT_ORDERS = [

    # ═══════════ NORTHERN CORRIDOR -- Tanga / Kilimanjaro / Arusha ═══════════
    dict(
        odoo_order_id=10001, odoo_order_name="SO/2026/01001",
        customer_name="MKOMBOZI HARDWARE - TANGA",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Bombo Street, Tanga", distance_from_plant_km=360,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=25.0,
        deadline_dt=hours_from_now(48), urgency_score=6.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10002, odoo_order_name="SO/2026/01002",
        customer_name="TANGA CEMENT HARDWARE",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Pangani Road, Tanga", distance_from_plant_km=365,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(72), urgency_score=5.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10003, odoo_order_name="SO/2026/01003",
        customer_name="KILIMANJARO BUILDERS SUPPLIES",
        delivery_region="KILIMANJARO", delivery_corridor="NORTHERN",
        delivery_address="Old Moshi Road, Moshi", distance_from_plant_km=480,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(36), urgency_score=8.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10004, odoo_order_name="SO/2026/01004",
        customer_name="ARUSHA CONSTRUCTION MATERIALS LTD",
        delivery_region="ARUSHA", delivery_corridor="NORTHERN",
        delivery_address="Sokoine Road, Arusha", distance_from_plant_km=510,
        product_name="CEM II B-M 42.5 N (DURAMAX)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(60), urgency_score=5.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=10005, odoo_order_name="SO/2026/01005",
        customer_name="SIMBA DEVS - MOSHI PROJECT",
        delivery_region="KILIMANJARO", delivery_corridor="NORTHERN",
        delivery_address="Moshi Town Center", distance_from_plant_km=475,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=20.0,
        deadline_dt=hours_from_now(24), urgency_score=9.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10006, odoo_order_name="SO/2026/01006",
        customer_name="CHALINZE JUNCTION TRADERS",
        delivery_region="PWANI", delivery_corridor="NORTHERN",
        delivery_address="Chalinze Town", distance_from_plant_km=62,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(96), urgency_score=4.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10007, odoo_order_name="SO/2026/01007",
        customer_name="SEGERA HARDWARE & BUILDERS",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Segera Township", distance_from_plant_km=270,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=18.0,
        deadline_dt=hours_from_now(48), urgency_score=6.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=10008, odoo_order_name="SO/2026/01008",
        customer_name="KOROGWE BUILDING SUPPLIES",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Korogwe District", distance_from_plant_km=310,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=12.0,
        deadline_dt=hours_from_now(120), urgency_score=3.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=10009, odoo_order_name="SO/2026/01009",
        customer_name="SAMA SAMA CONTRACTORS - ARUSHA",
        delivery_region="ARUSHA", delivery_corridor="NORTHERN",
        delivery_address="Njiro Road, Arusha", distance_from_plant_km=505,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=22.0,
        deadline_dt=hours_from_now(72), urgency_score=5.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(  # near-ready
        odoo_order_id=10010, odoo_order_name="SO/2026/01010",
        customer_name="PANGANI CEMENT DEALERS",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Pangani District", distance_from_plant_km=340,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(30), urgency_score=4.5,
        dispatch_ready=False, credit_cleared=True,
        near_ready=True, near_ready_eta=hours_from_now(4),
    ),
    dict(
        odoo_order_id=10011, odoo_order_name="SO/2026/01011",
        customer_name="HANDENI TRADERS",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Handeni Town", distance_from_plant_km=230,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=10.0,
        deadline_dt=hours_from_now(80), urgency_score=4.0,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=10012, odoo_order_name="SO/2026/01012",
        customer_name="LUSHOTO DISTRICT SUPPLIES",
        delivery_region="TANGA", delivery_corridor="NORTHERN",
        delivery_address="Lushoto", distance_from_plant_km=395,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=18.0,
        deadline_dt=hours_from_now(55), urgency_score=5.5,
        dispatch_ready=True, credit_cleared=True,
    ),

    # ═══════════ SOUTHERN HIGHLAND CORRIDOR -- Mbeya / Iringa ════════════════
    dict(
        odoo_order_id=20001, odoo_order_name="SO/2026/02001",
        customer_name="MBEYA CEMENT DISTRIBUTORS",
        delivery_region="MBEYA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Mbeya City Centre", distance_from_plant_km=870,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(72), urgency_score=6.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=20002, odoo_order_name="SO/2026/02002",
        customer_name="IRINGA BUILDERS WAREHOUSE",
        delivery_region="IRINGA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Iringa Municipality", distance_from_plant_km=430,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=20.0,
        deadline_dt=hours_from_now(48), urgency_score=7.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=20003, odoo_order_name="SO/2026/02003",
        customer_name="MAKAMBAKO TRADING CO.",
        delivery_region="NJOMBE", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Makambako Junction", distance_from_plant_km=650,
        product_name="CEM II B-M 42.5 N (DURAMAX)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(96), urgency_score=5.0,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=20004, odoo_order_name="SO/2026/02004",
        customer_name="MOROGORO HARDWARE DISTRIBUTORS",
        delivery_region="MOROGORO", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Morogoro Town", distance_from_plant_km=200,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(36), urgency_score=8.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=20005, odoo_order_name="SO/2026/02005",
        customer_name="KYELA FISH MARKET BUILDERS",
        delivery_region="MBEYA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Kyela District, Mbeya", distance_from_plant_km=1000,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=25.0,
        deadline_dt=hours_from_now(120), urgency_score=4.0,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=20006, odoo_order_name="SO/2026/02006",
        customer_name="MIKUMI PETROL STATION PROJECT",
        delivery_region="MOROGORO", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Mikumi, Morogoro", distance_from_plant_km=250,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=18.0,
        deadline_dt=hours_from_now(24), urgency_score=9.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=20007, odoo_order_name="SO/2026/02007",
        customer_name="NJOMBE HARDWARE SUPPLIERS",
        delivery_region="NJOMBE", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Njombe Town", distance_from_plant_km=700,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=20.0,
        deadline_dt=hours_from_now(60), urgency_score=5.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(  # near-ready
        odoo_order_id=20008, odoo_order_name="SO/2026/02008",
        customer_name="MBEYA CITY COUNCIL PROJECT",
        delivery_region="MBEYA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Mbeya City Hall site", distance_from_plant_km=875,
        product_name="CEM II B-M 42.5 N (DURAMAX)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(36), urgency_score=5.5,
        dispatch_ready=False, credit_cleared=True,
        near_ready=True, near_ready_eta=hours_from_now(8),
    ),
    dict(
        odoo_order_id=20009, odoo_order_name="SO/2026/02009",
        customer_name="MAFINGA BUILDERS",
        delivery_region="IRINGA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Mafinga, Iringa Region", distance_from_plant_km=500,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=12.0,
        deadline_dt=hours_from_now(90), urgency_score=4.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=20010, odoo_order_name="SO/2026/02010",
        customer_name="SONGEA ROAD CONSTRUCTION",
        delivery_region="RUVUMA", delivery_corridor="SOUTHERN_HIGHLAND",
        delivery_address="Songea Municipality", distance_from_plant_km=900,
        product_name="CEM II B-M 42.5 N (DURAMAX)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(150), urgency_score=3.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),

    # ═══════════ CENTRAL CORRIDOR -- Dodoma / Morogoro ═══════════════════════
    dict(
        odoo_order_id=30001, odoo_order_name="SO/2026/03001",
        customer_name="ESTIM CONSTRUCTION DODOMA",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="MOF YARD - MTUMBA - DODOMA", distance_from_plant_km=460,
        product_name="CEM II B-M 42.5 N (DURAMAX)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(48), urgency_score=7.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=30002, odoo_order_name="SO/2026/03002",
        customer_name="DODOMA REGIONAL HOSPITAL PROJECT",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="Dodoma Region Hospital Site", distance_from_plant_km=465,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=22.0,
        deadline_dt=hours_from_now(30), urgency_score=9.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=30003, odoo_order_name="SO/2026/03003",
        customer_name="MOROGORO HARDWARE",
        delivery_region="MOROGORO", delivery_corridor="CENTRAL",
        delivery_address="Morogoro Main Street", distance_from_plant_km=195,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(36), urgency_score=8.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=30004, odoo_order_name="SO/2026/03004",
        customer_name="SINGIDA CEMENT DEALERS",
        delivery_region="SINGIDA", delivery_corridor="CENTRAL",
        delivery_address="Singida Town", distance_from_plant_km=580,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=20.0,
        deadline_dt=hours_from_now(96), urgency_score=4.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=30005, odoo_order_name="SO/2026/03005",
        customer_name="KONGWA BUILDERS SUPPLIES",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="Kongwa District", distance_from_plant_km=420,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=18.0,
        deadline_dt=hours_from_now(72), urgency_score=5.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=30006, odoo_order_name="SO/2026/03006",
        customer_name="CHAMWINO DISTRICT COUNCIL",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="Chamwino District", distance_from_plant_km=475,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=25.0,
        deadline_dt=hours_from_now(60), urgency_score=6.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(  # near-ready
        odoo_order_id=30007, odoo_order_name="SO/2026/03007",
        customer_name="DODOMA CITY COUNCIL HOUSING",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="Dodoma City", distance_from_plant_km=460,
        product_name="CEM II B-M 42.5 N (DURAMAX)", quantity_tonnes=30.0,
        deadline_dt=hours_from_now(24), urgency_score=6.0,
        dispatch_ready=False, credit_cleared=True,
        near_ready=True, near_ready_eta=hours_from_now(6),
    ),
    dict(
        odoo_order_id=30008, odoo_order_name="SO/2026/03008",
        customer_name="GAIRO TRADERS",
        delivery_region="MOROGORO", delivery_corridor="CENTRAL",
        delivery_address="Gairo District, Morogoro", distance_from_plant_km=280,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=12.0,
        deadline_dt=hours_from_now(84), urgency_score=4.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=30009, odoo_order_name="SO/2026/03009",
        customer_name="MPWAPWA HARDWARE LTD",
        delivery_region="DODOMA", delivery_corridor="CENTRAL",
        delivery_address="Mpwapwa District", distance_from_plant_km=440,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=14.0,
        deadline_dt=hours_from_now(100), urgency_score=4.0,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),

    # ═══════════ COASTAL CORRIDOR -- Rufiji / Lindi (Route R1) ═══════════════
    dict(
        odoo_order_id=40001, odoo_order_name="SO/2026/04001",
        customer_name="NYAMISATI FISHING COOPERATIVE",
        delivery_region="PWANI", delivery_corridor="COASTAL",
        delivery_address="Nyamisati Village, Rufiji", distance_from_plant_km=115,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(48), urgency_score=7.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=40002, odoo_order_name="SO/2026/04002",
        customer_name="IKWIRIRI BUILDERS",
        delivery_region="PWANI", delivery_corridor="COASTAL",
        delivery_address="Ikwiriri Town, Rufiji", distance_from_plant_km=95,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=12.0,
        deadline_dt=hours_from_now(36), urgency_score=8.0,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=40003, odoo_order_name="SO/2026/04003",
        customer_name="KIBITI CEMENT DEPOT",
        delivery_region="PWANI", delivery_corridor="COASTAL",
        delivery_address="Kibiti, Rufiji District", distance_from_plant_km=85,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=10.0,
        deadline_dt=hours_from_now(60), urgency_score=6.0,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=40004, odoo_order_name="SO/2026/04004",
        customer_name="UTETE DISTRICT SUPPLIES",
        delivery_region="PWANI", delivery_corridor="COASTAL",
        delivery_address="Utete, Rufiji", distance_from_plant_km=100,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=8.0,
        deadline_dt=hours_from_now(72), urgency_score=5.5,
        dispatch_ready=True, credit_cleared=True,
        partial_load_allowed=True,
    ),
    dict(
        odoo_order_id=40005, odoo_order_name="SO/2026/04005",
        customer_name="LINDI HARDWARE TRADERS",
        delivery_region="LINDI", delivery_corridor="COASTAL",
        delivery_address="Lindi Town", distance_from_plant_km=380,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=20.0,
        deadline_dt=hours_from_now(96), urgency_score=4.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=40006, odoo_order_name="SO/2026/04006",
        customer_name="RUFIJI DELTA LODGE PROJECT",
        delivery_region="PWANI", delivery_corridor="COASTAL",
        delivery_address="Rufiji Delta, Coastal", distance_from_plant_km=110,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=18.0,
        deadline_dt=hours_from_now(30), urgency_score=8.5,
        dispatch_ready=True, credit_cleared=True,
    ),
    dict(
        odoo_order_id=40007, odoo_order_name="SO/2026/04007",
        customer_name="KILWA MASOKO BUILDERS",
        delivery_region="LINDI", delivery_corridor="COASTAL",
        delivery_address="Kilwa Masoko", distance_from_plant_km=340,
        product_name="CEM II A-L 42.5 R (SUPER 42)", quantity_tonnes=15.0,
        deadline_dt=hours_from_now(80), urgency_score=5.0,
        dispatch_ready=True, credit_cleared=True,
    ),
]


# ── HISTORICAL DISPATCHED TRIPS (for KPI savings dashboard) ──────────────────

HISTORICAL = [
    dict(
        schedule_ref="SCHED-20260501-H01",
        truck_plate="T866EHY",
        transporter_name="MWAMBA INVESTMENT LIMITED (KAIXIN)",
        corridor_name="NORTHERN",
        origin_region="TANGA",
        fresh_freight_avoided=2_268_000,
        return_freight_paid=1_315_440,
        holding_cost_saved=125_000,
        allocated_tonnes=29.5,
        utilization=98.3,
        n_orders=3,
        dispatched_at=days_ago(1),
    ),
    dict(
        schedule_ref="SCHED-20260501-H02",
        truck_plate="T216EJE",
        transporter_name="NACHARO ROYAL COMPANY LIMITED",
        corridor_name="NORTHERN",
        origin_region="TANGA",
        fresh_freight_avoided=1_984_500,
        return_freight_paid=1_150_610,
        holding_cost_saved=98_000,
        allocated_tonnes=27.0,
        utilization=90.0,
        n_orders=2,
        dispatched_at=days_ago(1),
    ),
    dict(
        schedule_ref="SCHED-20260430-H03",
        truck_plate="T794ELM",
        transporter_name="STATE MINING CORPORATION (COAL)",
        corridor_name="SOUTHERN_HIGHLAND",
        origin_region="MBEYA",
        fresh_freight_avoided=5_220_000,
        return_freight_paid=2_871_000,
        holding_cost_saved=210_000,
        allocated_tonnes=30.0,
        utilization=100.0,
        n_orders=2,
        dispatched_at=days_ago(2),
    ),
    dict(
        schedule_ref="SCHED-20260430-H04",
        truck_plate="T633EJW",
        transporter_name="PECOT GENERAL SUPPLIES LTD",
        corridor_name="CENTRAL",
        origin_region="DODOMA",
        fresh_freight_avoided=2_576_000,
        return_freight_paid=1_496_080,
        holding_cost_saved=75_000,
        allocated_tonnes=26.0,
        utilization=92.9,
        n_orders=3,
        dispatched_at=days_ago(2),
    ),
    dict(
        schedule_ref="SCHED-20260429-H05",
        truck_plate="T718EKT",
        transporter_name="EMMANUEL MARTINI MGONJA",
        corridor_name="COASTAL",
        origin_region="KIRANJERANJE",
        fresh_freight_avoided=1_448_800,
        return_freight_paid=940_720,
        holding_cost_saved=88_000,
        allocated_tonnes=25.0,
        utilization=89.3,
        n_orders=4,
        dispatched_at=days_ago(3),
    ),
    dict(
        schedule_ref="SCHED-20260429-H06",
        truck_plate="T867EHY",
        transporter_name="MWAMBA INVESTMENT LIMITED (KAIXIN)",
        corridor_name="NORTHERN",
        origin_region="TANGA",
        fresh_freight_avoided=2_419_200,
        return_freight_paid=1_403_136,
        holding_cost_saved=115_000,
        allocated_tonnes=30.0,
        utilization=100.0,
        n_orders=3,
        dispatched_at=days_ago(3),
    ),
    dict(
        schedule_ref="SCHED-20260428-H07",
        truck_plate="T316ENF",
        transporter_name="ANTU LOGISTICS CO. LIMITED",
        corridor_name="NORTHERN",
        origin_region="TANGA",
        fresh_freight_avoided=1_814_400,
        return_freight_paid=1_052_352,
        holding_cost_saved=65_000,
        allocated_tonnes=22.0,
        utilization=73.3,
        n_orders=2,
        dispatched_at=days_ago(4),
    ),
    dict(
        schedule_ref="SCHED-20260427-H08",
        truck_plate="T795ELM",
        transporter_name="STATE MINING CORPORATION (COAL)",
        corridor_name="SOUTHERN_HIGHLAND",
        origin_region="MBEYA",
        fresh_freight_avoided=4_698_000,
        return_freight_paid=2_583_900,
        holding_cost_saved=190_000,
        allocated_tonnes=27.0,
        utilization=90.0,
        n_orders=2,
        dispatched_at=days_ago(5),
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# SEED LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

async def clear_demo_data(db):
    """Remove any existing demo data to allow re-runs."""
    print("  Clearing existing demo data...")
    for table in ["savings_ledger", "proposal_items", "allocation_proposals",
                  "matching_events", "cement_orders", "truck_schedules", "transporters"]:
        await db.execute(text(f"DELETE FROM {table}"))
    await db.commit()
    print("  Cleared.")


async def seed_transporters(db) -> dict[int, Transporter]:
    """Insert transporters, return {idx: Transporter} map."""
    print("  Seeding transporters...")
    idx_map = {}
    for i, t_data in enumerate(TRANSPORTERS):
        t = Transporter(
            odoo_vendor_code=t_data["odoo_vendor_code"],
            name=t_data["name"],
            contact_name=t_data["contact_name"],
            contact_phone=t_data["contact_phone"],
            fleet_size=t_data["fleet_size"],
            avg_truck_capacity_tonnes=t_data["avg_truck_capacity_tonnes"],
            origin_region=t_data["origin_region"],
            reliability_score=t_data["reliability_score"],
            return_load_rate_pct=t_data["return_load_rate_pct"],
            notes=t_data["notes"],
            backhaul_willing=True,
            active=True,
        )
        t.vehicle_types = t_data["vehicle_types"]
        t.preferred_corridors = t_data["preferred_corridors"]
        db.add(t)
        idx_map[i] = t
    await db.flush()
    print(f"  Created {len(idx_map)} transporters.")
    return idx_map


async def seed_truck_schedules(db, transporter_map: dict) -> list[TruckSchedule]:
    """Insert truck schedules."""
    print("  Seeding truck schedules...")
    schedules = []
    for s_data in TRUCK_SCHEDULES:
        t_idx = s_data["transporter_idx"]
        transporter = transporter_map[t_idx]
        s = TruckSchedule(
            schedule_ref=s_data["schedule_ref"],
            odoo_po_name=s_data["odoo_po_name"],
            transporter_id=transporter.id,
            origin_region=s_data["origin_region"],
            raw_material_type=s_data["raw_material_type"],
            estimated_qty_tonnes=s_data["estimated_qty_tonnes"],
            truck_plate=s_data["truck_plate"],
            driver_name=s_data["driver_name"],
            driver_phone=s_data["driver_phone"],
            actual_capacity_tonnes=s_data["actual_capacity_tonnes"],
            corridor_name=s_data["corridor_name"],
            max_detour_km=s_data["max_detour_km"],
            expected_arrival_dt=s_data["expected_arrival_dt"],
            status=s_data["status"],
            allocation_status=s_data["allocation_status"],
        )
        s.return_route = s_data["return_route"]
        db.add(s)
        schedules.append(s)
    await db.flush()
    print(f"  Created {len(schedules)} truck schedules.")
    return schedules


async def seed_cement_orders(db) -> list[CementOrder]:
    """Insert cement orders."""
    print("  Seeding cement orders...")
    orders = []
    for o_data in CEMENT_ORDERS:
        corridor = o_data["delivery_corridor"]
        dist = o_data["distance_from_plant_km"]
        qty = o_data["quantity_tonnes"]
        ff = fresh_freight(corridor, dist, qty)

        o = CementOrder(
            odoo_order_id=o_data["odoo_order_id"],
            odoo_order_name=o_data["odoo_order_name"],
            odoo_state="sale",
            customer_name=o_data["customer_name"],
            delivery_region=o_data["delivery_region"],
            delivery_corridor=o_data["delivery_corridor"],
            delivery_address=o_data["delivery_address"],
            distance_from_plant_km=dist,
            product_name=o_data["product_name"],
            quantity_tonnes=qty,
            quantity_bags=int(qty * 20),
            fresh_outbound_freight_tzs=ff,
            unit_price_tzs=145_000,
            total_value_tzs=qty * 20 * 145_000,
            deadline_dt=o_data["deadline_dt"],
            urgency_score=o_data["urgency_score"],
            dispatch_ready=o_data["dispatch_ready"],
            credit_cleared=o_data["credit_cleared"],
            partial_load_allowed=o_data.get("partial_load_allowed", False),
            return_load_eligible=True,
            near_ready=o_data.get("near_ready", False),
            near_ready_eta=o_data.get("near_ready_eta"),
            allocation_status=OrderAllocationStatus.UNALLOCATED,
            loading_priority=2 if o_data["urgency_score"] >= 8 else 3,
        )
        db.add(o)
        orders.append(o)
    await db.flush()
    print(f"  Created {len(orders)} cement orders.")
    return orders


async def seed_manual_proposals(db):
    """
    Build proposals directly -- no matching engine dependency.
    Groups orders by corridor, greedily fills each truck with 3 variants.
    Uses fresh DB queries so no expired-object issues.
    """
    print("  Building proposals...")
    total = 0
    today = now_tz().strftime("%Y%m%d")

    # Fresh query: live truck schedules
    res = await db.execute(
        select(TruckSchedule).where(
            TruckSchedule.status.in_([TSS.EXPECTED, TSS.PRE_CONFIRMED])
        ).order_by(TruckSchedule.expected_arrival_dt)
    )
    schedules = res.scalars().all()

    # Fresh query: eligible cement orders
    res2 = await db.execute(
        select(CementOrder).where(
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
            CementOrder.return_load_eligible == True,
        )
    )
    all_orders = res2.scalars().all()

    # Convert to plain dicts immediately to avoid lazy-load issues
    order_dicts = []
    for o in all_orders:
        order_dicts.append({
            "id": o.id,
            "odoo_order_name": o.odoo_order_name,
            "delivery_corridor": o.delivery_corridor,
            "delivery_region": o.delivery_region,
            "distance_from_plant_km": o.distance_from_plant_km or 300.0,
            "quantity_tonnes": o.quantity_tonnes,
            "urgency_score": o.urgency_score,
            "deadline_dt": o.deadline_dt,
            "dispatch_ready": o.dispatch_ready,
            "credit_cleared": o.credit_cleared,
            "partial_load_allowed": o.partial_load_allowed,
            "near_ready": o.near_ready,
            "near_ready_eta": o.near_ready_eta,
        })

    # Convert schedules to plain dicts too
    sched_dicts = []
    for s in schedules:
        sched_dicts.append({
            "id": s.id,
            "schedule_ref": s.schedule_ref,
            "corridor_name": s.corridor_name,
            "origin_region": s.origin_region,
            "max_detour_km": s.max_detour_km,
            "actual_capacity_tonnes": s.actual_capacity_tonnes,
            "estimated_qty_tonnes": s.estimated_qty_tonnes,
            "expected_arrival_dt": s.expected_arrival_dt,
        })

    # Group eligible orders by corridor
    corridor_orders: dict[str, list[dict]] = {}
    for o in order_dicts:
        if o["dispatch_ready"] and o["credit_cleared"]:
            c = o["delivery_corridor"] or "LOCAL"
            corridor_orders.setdefault(c, []).append(o)

    # Track which order IDs have been assigned to a proposal (for MAX_SAVINGS variant only)
    # so we don't double-allocate across trucks
    allocated_order_ids: set[int] = set()

    prop_counter = 1
    for sched in sched_dicts:
        corridor = sched["corridor_name"] or "NORTHERN"
        cap = sched["actual_capacity_tonnes"] or sched["estimated_qty_tonnes"]
        max_detour = sched["max_detour_km"]

        eligible = [
            o for o in corridor_orders.get(corridor, [])
            if o["id"] not in allocated_order_ids
        ]

        if not eligible:
            print(f"    {sched['schedule_ref']} ({sched['origin_region']}) -> no eligible orders on {corridor}")
            continue

        def pack_truck(sorted_orders: list[dict], capacity: float) -> list[tuple[dict, float]]:
            selected = []
            remaining = capacity
            for o in sorted_orders:
                qty = o["quantity_tonnes"]
                if qty <= remaining:
                    selected.append((o, qty))
                    remaining -= qty
                elif o["partial_load_allowed"] and remaining >= 5.0:
                    selected.append((o, remaining))
                    remaining = 0.0
                if remaining <= 0:
                    break
            return selected

        def build_proposal_metrics(selected: list[tuple[dict, float]], capacity: float, corridor: str, max_detour: float) -> dict:
            total_t = sum(t for _, t in selected)
            util = (total_t / capacity) * 100
            total_fresh = sum(
                fresh_freight(corridor, o["distance_from_plant_km"], t)
                for o, t in selected
            )
            total_ret = return_freight(total_fresh, 0.60)
            hold = len(selected) * 50_000
            savings = net_saving(total_fresh, total_ret, hold)
            score = round(
                0.30 * min(savings / 2_000_000, 1.0) +
                0.25 * min(util / 100, 1.0) +
                0.25 * 0.80 +
                0.20 * min(
                    sum(o["urgency_score"] for o, _ in selected) / (len(selected) * 10),
                    1.0
                ),
                3,
            )
            return dict(
                total_t=total_t, util=util,
                total_fresh=total_fresh, total_ret=total_ret,
                hold=hold, savings=savings, score=score,
            )

        # Sort 3 ways (all using plain dicts)
        by_savings  = sorted(eligible, key=lambda o: fresh_freight(corridor, o["distance_from_plant_km"], o["quantity_tonnes"]), reverse=True)
        by_load     = sorted(eligible, key=lambda o: o["quantity_tonnes"], reverse=True)
        by_urgency  = sorted(eligible, key=lambda o: (-o["urgency_score"], o["deadline_dt"] or hours_from_now(9999)))

        variants = [
            (ProposalVariant.MAX_SAVINGS,  by_savings,  "A"),
            (ProposalVariant.MAX_LOAD,     by_load,     "B"),
            (ProposalVariant.URGENT_FIRST, by_urgency,  "C"),
        ]

        # Update TruckSchedule allocation_status in DB
        await db.execute(
            update(TruckSchedule)
            .where(TruckSchedule.id == sched["id"])
            .values(allocation_status=AllocationStatus.PROPOSED)
        )

        any_created = False
        for variant, sorted_ord, suffix in variants:
            selected = pack_truck(sorted_ord, cap)
            if not selected:
                continue

            m = build_proposal_metrics(selected, cap, corridor, max_detour)
            has_pending = any(not o["dispatch_ready"] for o, _ in selected)
            prop_ref = f"PROP-{today}-{prop_counter:03d}-{suffix}"

            plate = None  # look up below if needed
            warning_lines = [
                f"Route passes through {corridor} corridor -- confirm road condition with driver before dispatch.",
            ]
            if has_pending:
                warning_lines.append("Some orders are near-ready only -- confirm dispatch_ready before loading.")

            prop = AllocationProposal(
                proposal_ref=prop_ref,
                schedule_id=sched["id"],
                variant_type=variant,
                total_allocated_tonnes=round(m["total_t"], 2),
                capacity_utilization_pct=round(m["util"], 1),
                total_route_deviation_km=round(len(selected) * 18.0, 1),
                number_of_stops=len(selected),
                total_fresh_freight_tzs=round(m["total_fresh"]),
                total_return_freight_tzs=round(m["total_ret"]),
                holding_cost_tzs=round(m["hold"]),
                estimated_savings_tzs=round(m["savings"]),
                composite_score=m["score"],
                ai_reasoning=(
                    f"Variant {variant}: {len(selected)} stops on the {corridor} corridor, "
                    f"{m['util']:.0f}% truck utilization ({m['total_t']:.1f} MT of {cap:.0f} MT capacity). "
                    f"Net saving TZS {m['savings']:,.0f} vs sending a fresh outbound truck. "
                    f"All stops are within the {max_detour:.0f} km detour limit for this corridor."
                ),
                ai_recommendation="CONFIRM" if m["score"] >= 0.65 else "REVIEW",
                has_pending_readiness_orders=has_pending,
                pending_readiness_note="Some orders awaiting credit/dispatch clearance -- expected ready before truck ETA." if has_pending else None,
                status=ProposalStatus.PROPOSED,
            )
            prop._ai_warnings = json.dumps([w for w in warning_lines if w])
            db.add(prop)
            await db.flush()

            from app.models.allocation_proposal import ProposalItem as PI
            for seq, (o, tonnes) in enumerate(selected, start=1):
                item_fresh = fresh_freight(corridor, o["distance_from_plant_km"], tonnes)
                item_ret   = return_freight(item_fresh)
                item = PI(
                    proposal_id=prop.id,
                    cement_order_id=o["id"],
                    allocated_tonnes=round(tonnes, 2),
                    allocated_bags=int(tonnes * 20),
                    sequence=seq,
                    delivery_deviation_km=round(18.0 * seq, 1),
                    item_savings_tzs=round(net_saving(item_fresh, item_ret)),
                    is_near_ready=not o["dispatch_ready"],
                )
                db.add(item)

            # Only mark orders allocated on the A (MAX_SAVINGS) variant
            if suffix == "A":
                for o, _ in selected:
                    allocated_order_ids.add(o["id"])

            total += 1
            any_created = True

        if any_created:
            print(f"    {sched['schedule_ref']} ({sched['origin_region']}) -> 3 proposals created, {len(eligible)} eligible orders")
        prop_counter += 1

    await db.flush()
    print(f"  Total proposals created: {total}")


async def seed_historical_ledger(db):
    """
    Insert already-dispatched historical trips so the KPI dashboard
    shows real savings numbers from day one.
    """
    print("  Seeding historical savings ledger...")
    month_key = now_tz().strftime("%Y-%m")

    # Create dummy truck schedule + proposal records for the history rows
    for i, h in enumerate(HISTORICAL, start=1):
        disp_dt = h["dispatched_at"]
        mk = disp_dt.strftime("%Y-%m")

        # Minimal historical TruckSchedule (COMPLETED, no transporter link needed)
        sched = TruckSchedule(
            schedule_ref=h["schedule_ref"],
            origin_region=h["origin_region"],
            raw_material_type="CLINKER" if "KAIXIN" in h["transporter_name"] or "NACHARO" in h["transporter_name"] or "ANTU" in h["transporter_name"] else (
                "COAL" if "MINING" in h["transporter_name"] else (
                    "IRON_ORE" if "PECOT" in h["transporter_name"] else "GYPSUM"
                )
            ),
            estimated_qty_tonnes=h["allocated_tonnes"],
            truck_plate=h["truck_plate"],
            corridor_name=h["corridor_name"],
            max_detour_km=80.0,
            expected_arrival_dt=disp_dt - timedelta(hours=12),
            actual_arrival_dt=disp_dt - timedelta(hours=6),
            dispatched_at=disp_dt,
            status=TSS.COMPLETED,
            allocation_status=AllocationStatus.DISPATCHED,
        )
        sched.return_route = []
        db.add(sched)
        await db.flush()

        # Corresponding proposal (DISPATCHED)
        prop_ref = f"PROP-HIST-{i:03d}-A"
        prop = AllocationProposal(
            proposal_ref=prop_ref,
            schedule_id=sched.id,
            variant_type=ProposalVariant.MAX_SAVINGS,
            total_allocated_tonnes=h["allocated_tonnes"],
            capacity_utilization_pct=h["utilization"],
            total_route_deviation_km=h["n_orders"] * 18.0,
            number_of_stops=h["n_orders"],
            total_fresh_freight_tzs=h["fresh_freight_avoided"],
            total_return_freight_tzs=h["return_freight_paid"],
            holding_cost_tzs=h["holding_cost_saved"],
            estimated_savings_tzs=net_saving(
                h["fresh_freight_avoided"], h["return_freight_paid"], h["holding_cost_saved"]
            ),
            composite_score=0.82,
            ai_recommendation="CONFIRM",
            ai_reasoning="Historical allocation -- confirmed and dispatched.",
            status=ProposalStatus.DISPATCHED,
            confirmed_by="Demo Dispatcher",
            confirmed_at=disp_dt - timedelta(hours=8),
            dispatched_at=disp_dt,
        )
        prop._ai_warnings = json.dumps([])
        db.add(prop)
        await db.flush()

        # SavingsLedger entry
        ledger = SavingsLedger(
            proposal_id=prop.id,
            schedule_id=sched.id,
            proposal_ref=prop_ref,
            schedule_ref=h["schedule_ref"],
            truck_plate=h["truck_plate"],
            transporter_name=h["transporter_name"],
            corridor_name=h["corridor_name"],
            origin_region=h["origin_region"],
            fresh_freight_avoided_tzs=h["fresh_freight_avoided"],
            return_freight_paid_tzs=h["return_freight_paid"],
            holding_cost_saved_tzs=h["holding_cost_saved"],
            net_savings_tzs=net_saving(
                h["fresh_freight_avoided"], h["return_freight_paid"], h["holding_cost_saved"]
            ),
            allocated_tonnes=h["allocated_tonnes"],
            capacity_utilization_pct=h["utilization"],
            number_of_orders=h["n_orders"],
            dispatch_date=disp_dt,
            month_key=mk,
        )
        db.add(ledger)

    await db.flush()
    print(f"  Created {len(HISTORICAL)} historical ledger entries.")


async def print_summary(db):
    """Print a summary of what was seeded."""
    from sqlalchemy import func as sqlfunc

    def count(model):
        return db.execute(select(sqlfunc.count()).select_from(model))

    r_t = (await db.execute(select(Transporter))).scalars().all()
    r_s = (await db.execute(select(TruckSchedule))).scalars().all()
    r_o = (await db.execute(select(CementOrder))).scalars().all()
    r_p = (await db.execute(select(AllocationProposal))).scalars().all()
    r_l = (await db.execute(select(SavingsLedger))).scalars().all()

    total_savings = sum(l.net_savings_tzs for l in r_l)
    live_schedules = [s for s in r_s if s.status in (TSS.EXPECTED, TSS.PRE_CONFIRMED)]
    proposed_props = [p for p in r_p if p.status == ProposalStatus.PROPOSED]

    print()
    print("=" * 60)
    print("  DEMO DATA SUMMARY")
    print("=" * 60)
    print(f"  Transporters:        {len(r_t)}")
    print(f"  Truck Schedules:     {len(r_s)} total")
    print(f"    Live (visible):    {len(live_schedules)} trucks on dashboard")
    print(f"    Historical:        {len(r_s) - len(live_schedules)} (completed)")
    print(f"  Cement Orders:       {len(r_o)}")
    print(f"  Proposals:           {len(r_p)} total")
    print(f"    Pending review:    {len(proposed_props)}")
    print(f"  Savings Ledger:      {len(r_l)} entries")
    print(f"  MTD Net Savings:     TZS {total_savings:,.0f}")
    print("=" * 60)
    print()
    print("  Open in browser:")
    print("    Dashboard:   http://localhost:8001/")
    print("    Proposals:   http://localhost:8001/proposals")
    print("    API Docs:    http://localhost:8001/docs")
    print("    Health:      http://localhost:8001/api/health")
    print()


async def main():
    print()
    print("Smart Return Truck Allocator -- Demo Data Seed")
    print("=" * 60)

    # Ensure tables exist
    await create_tables()
    print("  Database tables: OK")

    async with AsyncSessionLocal() as db:
        # 1. Clear
        await clear_demo_data(db)

        # 2. Transporters
        transporter_map = await seed_transporters(db)
        await db.commit()

        # 3. Truck schedules
        schedules = await seed_truck_schedules(db, transporter_map)
        await db.commit()

        # 4. Cement orders
        orders = await seed_cement_orders(db)
        await db.commit()

        # 5. Build proposals
        await seed_manual_proposals(db)
        await db.commit()

        # 6. Historical ledger entries (KPI numbers)
        await seed_historical_ledger(db)
        await db.commit()

        # 7. Summary
        await print_summary(db)

    print("  Done! Refresh your browser at http://localhost:8001/")
    print()


if __name__ == "__main__":
    asyncio.run(main())
