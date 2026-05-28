"""
scripts/seed_test_trucks.py — Insert test truck records for Schedule page testing.
Run: python scripts/seed_test_trucks.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from app.database import AsyncSessionLocal, engine, Base
from app.models.truck_schedule import TruckSchedule, TruckScheduleStatus, AllocationStatus


TEST_TRUCKS = [
    # ── Rudo General Supplies — Truck 1 ──────────────────────────
    {
        "schedule_ref":          "TEST-RUDO-001",
        "transporter_name":      "Rudo General Supplies Company Limited",
        "truck_plate":           "T308ELB",
        "driver_name":           "Rajabu M Sudi",
        "driver_license_no":     "4000186647",
        "driver_phone":          "0778010415",
        "actual_capacity_tonnes": 32.0,
        "estimated_qty_tonnes":  32.0,
        "raw_material_type":     "GYPSUM",
        "origin_region":         "Dar es Salaam",
        "corridor_name":         "LOCAL",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=6),
        "dispatch_date":         datetime.now(timezone.utc),
    },
    # ── Rudo General Supplies — Truck 2 ──────────────────────────
    {
        "schedule_ref":          "TEST-RUDO-002",
        "transporter_name":      "Rudo General Supplies Company Limited",
        "truck_plate":           "T893EKX",
        "driver_name":           "Rajabu M Sudi",
        "driver_license_no":     "4000186647",
        "driver_phone":          "0778010415",
        "actual_capacity_tonnes": 32.0,
        "estimated_qty_tonnes":  32.0,
        "raw_material_type":     "GYPSUM",
        "origin_region":         "Dar es Salaam",
        "corridor_name":         "LOCAL",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=8),
        "dispatch_date":         datetime.now(timezone.utc),
    },
    # ── Chi Chi Business Company Limited — Truck 1 ───────────────
    {
        "schedule_ref":          "TEST-CHICHI-001",
        "transporter_name":      "Chi Chi Business Company Limited",
        "truck_plate":           "T564EGG",
        "dealer_number":         "T188EFW",
        "driver_name":           "Sandu Sosoma",
        "driver_license_no":     "4004100026",
        "driver_phone":          "0716575065",
        "actual_capacity_tonnes": 33.0,
        "estimated_qty_tonnes":  33.0,
        "raw_material_type":     "GYPSUM",
        "origin_region":         "Dar es Salaam",
        "corridor_name":         "LOCAL",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "dispatch_date":         datetime(2026, 5, 27, tzinfo=timezone.utc),
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=4),
    },
    # ── Chi Chi Business Company Limited — Truck 2 ───────────────
    {
        "schedule_ref":          "TEST-CHICHI-002",
        "transporter_name":      "Chi Chi Business Company Limited",
        "truck_plate":           "T574EGG",
        "dealer_number":         "T190EFW",
        "driver_name":           "Rajabu Juma Rajabu",
        "driver_license_no":     "4006209068",
        "driver_phone":          "0794650513",
        "actual_capacity_tonnes": 33.0,
        "estimated_qty_tonnes":  33.0,
        "raw_material_type":     "GYPSUM",
        "origin_region":         "Dar es Salaam",
        "corridor_name":         "LOCAL",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "dispatch_date":         datetime(2026, 5, 27, tzinfo=timezone.utc),
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=5),
    },
    # ── Aljamad Logistics Ltd ─────────────────────────────────────
    {
        "schedule_ref":          "TEST-ALJAMAD-001",
        "transporter_name":      "Aljamad Logistics Ltd",
        "truck_plate":           "T965AHA",
        "dealer_number":         "T429AHN",
        "driver_name":           "Eliatosha Erasto",
        "driver_license_no":     "4001717097",
        "driver_phone":          "0755716350",
        "actual_capacity_tonnes": 36.0,
        "estimated_qty_tonnes":  36.0,
        "raw_material_type":     "CLINKER",
        "origin_region":         "Tanga",
        "corridor_name":         "NORTHERN",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "dispatch_date":         datetime.now(timezone.utc),
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=10),
    },
    # ── John Galt Hauliers Company Limited ───────────────────────
    {
        "schedule_ref":          "TEST-JOHNGALT-001",
        "transporter_name":      "John Galt Hauliers Company Limited",
        "truck_plate":           "T642DWY",
        "dealer_number":         "T976APF",
        "driver_name":           "Ridhiwani Karambo Ally",
        "driver_license_no":     "4000387708",
        "driver_phone":          "0663142671",
        "actual_capacity_tonnes": 30.0,
        "estimated_qty_tonnes":  30.0,
        "raw_material_type":     "GYPSUM",
        "origin_region":         "Dar es Salaam",
        "corridor_name":         "LOCAL",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "dispatch_date":         datetime.now(timezone.utc),
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=3),
    },
    # ── Swift Haul Logistics Company Limited — Truck 1 ───────────
    {
        "schedule_ref":          "TEST-SWIFT-001",
        "transporter_name":      "Swift Haul Logistics Company Limited",
        "truck_plate":           "T647EJW",
        "dealer_number":         "T230EJK",
        "driver_name":           "Said Amour",
        "driver_license_no":     "4000710754",
        "driver_phone":          "0766255957",
        "actual_capacity_tonnes": 30.0,
        "estimated_qty_tonnes":  30.0,
        "raw_material_type":     "COAL",
        "origin_region":         "Mbeya",
        "corridor_name":         "SOUTHERN_HIGHLANDS",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "dispatch_date":         datetime.now(timezone.utc),
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=14),
    },
    # ── Swift Haul Logistics Company Limited — Truck 2 ───────────
    {
        "schedule_ref":          "TEST-SWIFT-002",
        "transporter_name":      "Swift Haul Logistics Company Limited",
        "truck_plate":           "T241EJK",
        "dealer_number":         "T702ACW",
        "driver_name":           "Hemed Hemed",
        "driver_license_no":     "4001113660",
        "driver_phone":          "0786520004",
        "actual_capacity_tonnes": 30.0,
        "estimated_qty_tonnes":  30.0,
        "raw_material_type":     "COAL",
        "origin_region":         "Mbeya",
        "corridor_name":         "SOUTHERN_HIGHLANDS",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "dispatch_date":         datetime.now(timezone.utc),
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=16),
    },
    # ── ZAS Company Limited ───────────────────────────────────────
    {
        "schedule_ref":          "TEST-ZAS-001",
        "transporter_name":      "ZAS Company Limited",
        "truck_plate":           "T199CCD",
        "dealer_number":         "T486BTL",   # trailer stored in dealer_number
        "driver_name":           "Shafii Abdallah",
        "driver_license_no":     "4001997843",
        "driver_phone":          "0639420569",
        "actual_capacity_tonnes": 30.0,
        "estimated_qty_tonnes":  30.0,
        "raw_material_type":     "CLINKER",
        "origin_region":         "Tanga",
        "corridor_name":         "NORTHERN",
        "status":                TruckScheduleStatus.EXPECTED,
        "allocation_status":     AllocationStatus.UNALLOCATED,
        "expected_arrival_dt":   datetime.now(timezone.utc) + timedelta(hours=12),
        "dispatch_date":         datetime.now(timezone.utc),
    },
]


async def seed():
    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped  = 0

        for data in TEST_TRUCKS:
            from sqlalchemy import select
            result = await session.execute(
                select(TruckSchedule).where(
                    TruckSchedule.schedule_ref == data["schedule_ref"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  SKIP  {data['schedule_ref']} — already exists")
                skipped += 1
                continue

            truck = TruckSchedule(**data)
            truck.upload_date = datetime.now(timezone.utc)
            session.add(truck)
            print(f"  ADD   {data['schedule_ref']} | {data['truck_plate']} | {data['transporter_name']}")
            inserted += 1

        await session.commit()
        print(f"\nDone — {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
