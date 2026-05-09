# CLAUDE CODE PROMPT PLAYBOOK
## Smart Return Truck Allocator — Step-by-Step Build Guide
### Lake Cement Limited / Nyati Cement, Tanzania

> **How to use this file:**
> Open VS Code in `C:\Users\USER\return trucks optimization\`
> Open Claude Code panel (Ctrl+Shift+P → "Claude Code")
> Copy each prompt EXACTLY as written, paste into Claude Code, execute, verify before moving to next.
> Each prompt builds on the previous — do NOT skip steps.

---

## BEFORE YOU START — VS Code Setup

```
1. Open VS Code
2. File → Open Folder → C:\Users\USER\return trucks optimization
3. Open Claude Code (sidebar or Ctrl+Shift+P → Claude Code: Open)
4. Claude Code will automatically read CLAUDE.md in this folder
5. Always start a new session with Prompt 0 below
```

---

## PROMPT 0 — Session Primer (Use at the start of EVERY session)

```
Read CLAUDE.md in this project root carefully. This is the Smart Return Truck
Allocator for Lake Cement Limited (Nyati Cement), Tanzania. The plant is at
Kimbiji, Kigamboni, Dar es Salaam.

Key context:
- We are building a FastAPI Python service that proactively matches inbound raw
  material trucks with outbound cement delivery orders BEFORE the trucks arrive,
  using Odoo 15 purchase.order as the trigger.
- Architecture: FastAPI + SQLAlchemy (async) + Odoo XML-RPC + Claude AI + HTML dashboard
- All data files in this folder are reference data — never modify them
- The full project plan is at:
  C:\Users\USER\.claude\plans\you-are-senior-software-buzzing-clock.md

Confirm you have read CLAUDE.md and summarise: (1) the 4 RM materials and their
source regions, (2) the 3 main return corridors, (3) what triggers the matching engine.
```

**Expected response:** Claude confirms CLINKER/Tanga, COAL/Mbeya, GYPSUM/Lindi, IRON ORE/Dodoma + 3 corridors + PO trigger. If it gets any wrong, paste the relevant CLAUDE.md section and re-ask.

---

---

# PHASE 1 — PROJECT FOUNDATION
## (Week 1 — Run these in order)

---

## PROMPT 1.1 — Initialize Project Structure

```
Create the full project directory structure for this app as defined in CLAUDE.md.
Create all empty __init__.py files and placeholder files with a single comment line.
Also create:
  - requirements.txt with all packages from the plan
  - .env.example with all variables from CLAUDE.md
  - .gitignore (Python standard, ignore .env, *.db, __pycache__, venv/)

Do NOT write any logic yet — just the skeleton with correct imports at the top of
each file. Show me the tree after creation.

requirements.txt must include:
fastapi>=0.111.0, uvicorn[standard]>=0.29.0, sqlalchemy>=2.0.0, alembic>=1.13.0,
aiosqlite>=0.20.0, asyncpg>=0.29.0, pydantic-settings>=2.2.0, python-dotenv>=1.0.0,
anthropic>=0.93.0, httpx>=0.27.0, apscheduler>=3.10.0, pydantic>=2.7.0,
rich>=13.0.0, openpyxl>=3.1.0, pandas>=2.0.0,
pytest>=8.2.0, pytest-asyncio>=0.23.0
```

**Verify:** Run `tree /F` in terminal. All folders and __init__.py files should exist.

---

## PROMPT 1.2 — Config and Database Base

```
Write these two files completely:

1. app/config.py
   - Use pydantic-settings BaseSettings
   - Load from .env file
   - Include ALL variables from .env.example in CLAUDE.md
   - Add computed properties:
     * odoo_rm_item_codes: dict mapping material names to RM codes (from CLAUDE.md)
     * corridor_max_detour_km: dict from CLAUDE.md MAX_DETOUR_KM section
   - Settings singleton: settings = Settings()

2. app/database.py
   - Async SQLAlchemy engine
   - AsyncSession factory
   - Base = declarative_base()
   - get_db() async dependency for FastAPI
   - create_tables() async function (for startup)
   - Support both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL
```

**Verify:** `python -c "from app.config import settings; print(settings.app_port)"` should print 8001.

---

## PROMPT 1.3 — All Database Models

```
Write all 9 SQLAlchemy models in app/models/. Each must import Base from
app.database and use proper async-compatible types.

Models to create (full field definitions from CLAUDE.md data requirements):

1. app/models/transporter.py — Transporter
   Fields: id, code(unique), name, tin, vrn, region, mobile, phone, email,
   fleet_size, vehicle_types(JSON), backhaul_willing(bool, default True),
   preferred_corridors(JSON), reliability_score(Numeric 4,1, default 7.0),
   return_load_rate_pct(Numeric 4,3, default 0.55),
   avg_truck_capacity_tonnes(Numeric 6,2, default 30.0),
   payment_terms, notes, active(bool, default True), created_at

2. app/models/route_corridor.py — RouteCorridor
   Fields: id, source_region, corridor_name, waypoints(JSON),
   eligible_customer_regions(JSON), distance_km(Integer),
   estimated_hours(Numeric 4,1), road_quality, seasonal_notes,
   max_detour_km(Integer, default 80), created_at

3. app/models/customer_logistics.py — CustomerLogistics
   Fields: id, customer_odoo_id(unique), customer_code, customer_name,
   delivery_region, corridor, zone, delivery_lat(Numeric 9,6),
   delivery_lng(Numeric 9,6), distance_km_from_plant(Integer),
   truck_access_type, avg_order_tonnes(Numeric 6,2),
   notes, updated_at

4. app/models/cement_order.py — CementOrder
   Fields: id, odoo_order_id(unique), odoo_order_name, odoo_picking_id,
   customer_name, customer_odoo_id, customer_code, customer_phone,
   delivery_region, delivery_address, delivery_lat, delivery_lng,
   distance_km_from_plant(Integer),
   product_code, quantity_tonnes(Numeric 8,2), quantity_bags(Integer),
   baggage_type, fresh_outbound_freight_tzs(Numeric 14,2),
   unit_price_tzs(Numeric 14,2), total_value_tzs(Numeric 14,2),
   lpo_no, requested_delivery_dt, deadline_dt,
   urgency_score(Numeric 4,2, default 0),
   dispatch_ready(bool, default False), credit_cleared(bool, default False),
   partial_load_allowed(bool, default False), loading_priority(Integer, default 3),
   near_ready(bool, default False), near_ready_eta(DateTime),
   soft_reserved_schedule_id(FK→truck_schedules, nullable),
   odoo_state, allocation_status(default 'UNALLOCATED'),
   last_synced_at, created_at, updated_at

5. app/models/truck_schedule.py — TruckSchedule
   Fields: id, schedule_ref(unique), odoo_po_id(Integer), odoo_po_name,
   odoo_receipt_id(Integer, nullable),
   supplier_id(FK→transporters, nullable), origin_region, raw_material_type,
   estimated_qty_tonnes(Numeric 8,2), estimated_truck_count(Integer, default 1),
   truck_plate(nullable), driver_name(nullable), driver_phone(nullable),
   actual_capacity_tonnes(Numeric 8,2, nullable),
   return_route(JSON), max_detour_km(Integer, default 80),
   po_date, expected_arrival_dt, actual_arrival_dt(nullable),
   unloaded_dt(nullable), loaded_out_dt(nullable), dispatched_at(nullable),
   status(default 'EXPECTED'), allocation_status(default 'UNMATCHED'),
   notes, created_at, updated_at

6. app/models/allocation_proposal.py — AllocationProposal
   Fields: id, proposal_ref(unique), schedule_id(FK→truck_schedules),
   variant_type,
   total_allocated_tonnes(Numeric 8,2), capacity_utilization_pct(Numeric 5,2),
   total_route_deviation_km(Integer), number_of_stops(Integer),
   total_fresh_freight_tzs(Numeric 14,2), total_return_freight_tzs(Numeric 14,2),
   holding_cost_tzs(Numeric 14,2), estimated_savings_tzs(Numeric 14,2),
   composite_score(Numeric 6,3),
   ai_reasoning(Text, nullable), ai_warnings(JSON, nullable),
   ai_recommendation(nullable),
   has_pending_readiness_orders(bool, default False),
   pending_readiness_note(Text, nullable),
   status(default 'PROPOSED'),
   confirmed_by(nullable), confirmed_at(nullable), dispatched_at(nullable),
   odoo_picking_ids(JSON, nullable), created_at

7. app/models/proposal_item.py — ProposalItem
   Fields: id, proposal_id(FK→allocation_proposals), cement_order_id(FK→cement_orders),
   allocated_tonnes(Numeric 8,2), allocated_bags(Integer), sequence(Integer),
   delivery_deviation_km(Integer), item_savings_tzs(Numeric 14,2),
   is_near_ready(bool, default False), odoo_picking_id(nullable), created_at

8. app/models/matching_event.py — MatchingEvent
   Fields: id, schedule_id(FK→truck_schedules), triggered_by,
   orders_evaluated(Integer), orders_qualified(Integer),
   proposals_generated(Integer), top_savings_tzs(Numeric 14,2),
   top_utilization_pct(Numeric 5,2), ai_called(bool), duration_ms(Integer),
   created_at

9. app/models/savings_ledger.py — SavingsLedger
   Fields: id, month_year(String 7, e.g. '2026-04'), proposal_id(FK),
   trip_ref, transporter_name, corridor,
   fresh_freight_saved_tzs(Numeric 14,2), return_freight_paid_tzs(Numeric 14,2),
   holding_cost_tzs(Numeric 14,2), net_saving_tzs(Numeric 14,2),
   customer_count(Integer), tonnes_delivered(Numeric 8,2), created_at

Also update app/models/__init__.py to export all models.
Add relationships between models (e.g. TruckSchedule.proposals, AllocationProposal.items).
```

**Verify:** `python -c "from app.models import TruckSchedule, AllocationProposal; print('Models OK')"` should print Models OK.

---

## PROMPT 1.4 — Alembic Migration

```
Set up Alembic for database migrations:

1. Initialize Alembic: alembic init app/alembic
2. Update app/alembic/env.py to:
   - Import all models from app.models
   - Import Base from app.database
   - Set target_metadata = Base.metadata
   - Support async SQLite and PostgreSQL via DATABASE_URL from settings
3. Generate first migration: alembic revision --autogenerate -m "initial_schema"
4. Review the generated migration — confirm all 9 tables are present
5. Apply migration: alembic upgrade head

Show me the list of tables created.
```

**Verify:** Run `python -c "from app.database import engine; import asyncio; from sqlalchemy import inspect, text; ..."` or check with `alembic current` showing `head`.

---

## PROMPT 1.5 — Pydantic Schemas

```
Write Pydantic v2 schemas in app/schemas/ for API request/response.

1. app/schemas/truck_schedule.py
   - TruckScheduleCreate (POST body: origin_region, odoo_po_id, odoo_po_name,
     raw_material_type, estimated_qty_tonnes, expected_arrival_dt, supplier_id)
   - TruckScheduleUpdate (PATCH body: truck_plate, driver_name, driver_phone,
     actual_capacity_tonnes, status, notes)
   - TruckScheduleResponse (full response, include supplier name)
   - TruckScheduleListItem (compact for list view: ref, origin, ETA, status,
     estimated_qty, allocation_status, best_savings_tzs)

2. app/schemas/cement_order.py
   - CementOrderResponse (full)
   - CementOrderListItem (compact)

3. app/schemas/allocation_proposal.py
   - ProposalResponse (full with items list)
   - ProposalListItem (compact: ref, variant_type, savings, utilization, status)
   - ProposalConfirm (PATCH body: confirmed_by)
   - ProposalItemResponse

4. app/schemas/savings.py
   - SavingsSummary (mtd_savings_tzs, truck_count, match_rate_pct,
     avg_utilization_pct, avg_savings_per_trip_tzs, by_corridor list)

All schemas use orm_mode = True (model_config = ConfigDict(from_attributes=True)).
```

---

# PHASE 2 — ROUTE INTELLIGENCE & DATA SEEDING
## (Week 2)

---

## PROMPT 2.1 — Tanzania Regions Data

```
Write app/data/tanzania_regions.py with these structures:

1. REGIONS dict: all 10+ Tanzania regions with:
   - code (e.g. "DSM", "DODOMA", "MBEYA", "TANGA", "MOSHI", "ARUSHA",
     "IRINGA", "MWANZA", "TABORA", "LINDI", "MTWARA", "PWANI",
     "RUVUMA", "SINGIDA", "SONGEA")
   - full_name
   - lat, lng (city centre coordinates)
   - corridor (which primary corridor it belongs to)

2. DISTANCE_MATRIX dict: symmetric road distances (km) between region pairs,
   measured from KIMBIJI PLANT (Kigamboni, DSM). Use values from CLAUDE.md:
   - DSM→MOROGORO: 200km, DSM→TANGA: 360km, DSM→DODOMA: 460km
   - DSM→MOSHI: 570km, DSM→ARUSHA: 640km, DSM→IRINGA: 510km
   - DSM→MBEYA: 870km, DSM→TABORA: 850km, DSM→MWANZA: 1260km
   - DSM→LINDI: 500km, DSM→MTWARA: 600km, DSM→PWANI: 180km
   - DSM→SONGEA: 900km
   - Plus all inter-region pairs (MOROGORO→DODOMA: 260km etc.)
   Make it symmetric: get_distance(A,B) == get_distance(B,A)

3. CORRIDOR_WAYPOINTS dict: ordered waypoints for each corridor
   - NORTHERN: ["KIGAMBONI","CHALINZE","SEGERA","TANGA"] +
               ["KIGAMBONI","CHALINZE","SEGERA","KOROGWE","MOSHI","ARUSHA"]
   - CENTRAL: ["KIGAMBONI","CHALINZE","MOROGORO","DODOMA","SINGIDA","TABORA","MWANZA"]
   - SOUTHERN_HIGHLANDS: ["KIGAMBONI","CHALINZE","MOROGORO","IRINGA","MBEYA","KYELA"]
   - SOUTHERN_COAST: ["KIGAMBONI","IKWIRIRI","NYAMISATI","UTETE","KIBITI","KIRANJERANJE"]
   - RUVUMA: ["KIGAMBONI","CHALINZE","MOROGORO","IRINGA","NJOMBE","SONGEA"]
   - LOCAL: ["KIGAMBONI","DSM"]

4. RM_ORIGIN_TO_CORRIDOR dict: maps each RM material+supplier to their return corridor
   (derived from CLAUDE.md RM sources section)

5. CITY_TO_REGION dict: 150+ city/town name aliases → region code
   Include all cities from Customer master and Location master.
   Cover common Odoo city field variations (uppercase, lowercase, with spaces).

6. Helper functions:
   get_distance(region_a, region_b) -> int
   get_corridor_for_region(region_code) -> str
   normalize_city_to_region(city_str) -> str | None
   get_route_waypoints(origin, destination) -> list[str]
```

---

## PROMPT 2.2 — Route Calculator Service

```
Write app/services/route_calculator.py completely.

This is the core geographic intelligence. Use the DISTANCE_MATRIX from
app/data/tanzania_regions.py as input.

Implement:

1. floyd_warshall_all_pairs(matrix: dict) -> dict
   Compute shortest paths between ALL region pairs.
   Cache result as module-level ALL_PAIRS_DISTANCES on import.

2. deviation_km(plant: str, delivery_region: str, truck_origin: str) -> int
   detour = dist(plant→delivery) + dist(delivery→origin) - dist(plant→origin)
   Return max(0, detour). Zero means delivery is perfectly on return route.
   Use KIGAMBONI as plant.

3. route_position_pct(delivery_region: str, return_route: list[str]) -> float
   Returns 0.0–1.0 representing how far along the route the delivery is.
   0.0 = at plant, 1.0 = at origin. Used for stop sequencing.

4. sort_stops_by_route_order(orders: list, return_route: list[str]) -> list
   Sort delivery orders by their position along the return route.
   (Driver delivers in route order — no backtracking)

5. is_on_corridor(delivery_region: str, corridor_name: str) -> bool
   True if delivery_region is a waypoint or within max_detour of the corridor.

6. compute_seasonal_penalty(delivery_region: str, month: int) -> int
   Returns additional km penalty for seasonal road conditions.
   (From CLAUDE.md: Iringa-Dodoma muddy June-Aug, Tanga-Pangani March-May)

7. get_all_on_corridor_regions(corridor: str, max_detour: int = 80) -> list[str]
   Returns all regions reachable from a corridor within max_detour km.

Add unit test stubs at bottom (if __name__ == '__main__') that verify:
- deviation_km("KIGAMBONI", "MOROGORO", "DODOMA") == 0 (Morogoro is on DSM-Dodoma route)
- deviation_km("KIGAMBONI", "TANGA", "MBEYA") > 500 (Tanga is not on Mbeya route)
```

**Verify:** Run `python app/services/route_calculator.py` — both assertions should pass silently.

---

## PROMPT 2.3 — Seeding Scripts

```
Write 4 seeding scripts. Each must be runnable standalone AND importable.
Each script reads from the Excel files in the project root.

1. scripts/seed_locations.py
   Reads: location master.xlsx (Sheet1)
   Columns: Name, City, District, Region, Country, Type, Kilometer, Status
   Creates CustomerLogistics records for each APPROVED location.
   Maps: Kilometer → distance_km_from_plant
   Maps: Region → delivery_region (normalize to our region codes)
   Maps: City → normalize_city_to_region() for delivery_region
   Only import locations where Status='Approved'
   Print progress: "Seeded NNN locations"

2. scripts/seed_transporters.py
   Reads: transporter master.xlsx AND
          Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx
          (sheet: Raw Material Vendor Master-Tran)
   Merge both lists (deduplicate by Code).
   For RM transporters: backhaul_willing=True, avg_truck_capacity_tonnes=30.0
   Maps Region field → preferred_corridors based on CORRIDOR_WAYPOINTS
   Print: "Seeded NNN transporters (NNN RM, NNN FG)"

3. scripts/seed_routes.py
   Reads: Routes template26042026.xlsx (Sheet1)
   For each row: RAW_MATERIAL + location + DISTRICT + ROUTE + DESTINATION cols
   Creates RouteCorridor entries.
   Also seeds the 6 primary corridors from CORRIDOR_WAYPOINTS (hard-coded from
   app/data/tanzania_regions.py).
   Print: "Seeded NNN route corridors"

4. scripts/seed_customers.py
   Reads: Customer master.xlsx (Sheet1)
   For each APPROVED customer: create/update CustomerLogistics
   Maps: Zone → corridor (using ZONE_TO_CORRIDOR from CLAUDE.md)
   Maps: City → delivery_region
   Maps: Region field → delivery_region
   Print: "Seeded NNN customers"

Each script must:
- Handle missing/NaN values gracefully (skip row, log warning)
- Use upsert logic (create_or_update by code/id)
- Run with: python scripts/seed_locations.py
- Accept --dry-run flag that prints what would be inserted without writing to DB
```

**Verify:** Run each script. Should complete without errors and print counts.

---

# PHASE 3 — ODOO INTEGRATION
## (Week 2–3)

---

## PROMPT 3.1 — Odoo XML-RPC Client

```
Write app/services/odoo_sync.py completely.

This is the bridge between our app and Odoo 15.

class OdooClient:
    def __init__(self, settings): ...
    def authenticate(self) -> int: ...  # returns uid
    def ping(self) -> bool: ...

    # ─── READ OPERATIONS ───────────────────────────────────────────

    def fetch_rm_purchase_orders(self, since_date=None) -> list[dict]:
        '''
        Read confirmed RM purchase.order not yet fully received.
        Filter: state='purchase', x_return_load_eligible=True
        Fields: id, name, state, partner_id, scheduled_date, date_order,
                order_line, picking_ids, x_origin_region, x_truck_count_est
        Also fetch order_line details: product_id, product_qty, product_uom
        Map product_id to RM material type using settings.odoo_rm_item_codes
        '''

    def fetch_rm_receipts(self, po_names: list) -> list[dict]:
        '''
        Read stock.picking (receipts) for given PO names.
        Filter: picking_type_code='incoming', origin in po_names
        Fields: id, origin, state, scheduled_date, partner_id
        Used to detect when truck physically arrives.
        '''

    def fetch_sale_orders(self, since_date=None) -> list[dict]:
        '''
        Read confirmed cement SOs not yet allocated.
        Filter: state IN ('sale'), x_return_load_eligible=True or not set
        Fields: id, name, state, partner_id, commitment_date, amount_total,
                x_dispatch_ready, x_credit_cleared, x_loading_priority,
                x_partial_load_ok, order_line
        Fetch order lines: product_id, product_uom_qty, product_uom, price_unit
        '''

    def fetch_partner(self, partner_id: int) -> dict:
        '''
        Read res.partner for customer/supplier details.
        Fields: id, name, city, street, phone, mobile,
                x_delivery_corridor, x_supplier_origin_region,
                x_delivery_lat, x_delivery_lng
        '''

    def fetch_fleet_vehicles(self) -> list[dict]:
        '''
        Read fleet.vehicle (active trucks).
        Fields: id, name, license_plate, driver_id, payload_weight, state_id
        '''

    def fetch_freight_rate(self, destination: str, transporter_code: str) -> float:
        '''
        Read freight rate for destination+transporter from location master or
        a dedicated freight model. Return TZS per trip.
        If not found: return estimate based on distance_km * rate_per_km.
        '''

    # ─── WRITE OPERATIONS ──────────────────────────────────────────

    def create_stock_picking(self, order_data: dict, proposal_ref: str,
                              schedule_ref: str) -> int:
        '''
        Create outbound stock.picking in Odoo for a confirmed allocation.
        picking_type_id = settings.odoo_picking_type_outgoing_id
        origin = f"TRUCK/{schedule_ref}/{proposal_ref}"
        Returns picking_id.
        '''

    def confirm_stock_picking(self, picking_id: int) -> bool: ...

    def cancel_stock_picking(self, picking_id: int) -> bool: ...

Include:
- Connection pooling (reuse authenticated session)
- Retry logic: 3 retries with 2s backoff on XMLRPCFault
- Detailed logging on every call (model, method, filter used, record count returned)
- Graceful handling when Odoo field doesn't exist (missing x_ fields)
  → log warning, return None for that field, don't crash
- OdooConnectionError exception class for connection failures
```

---

## PROMPT 3.2 — Odoo Connection Test Script

```
Write scripts/test_odoo_connection.py — a diagnostic tool.

When run: python scripts/test_odoo_connection.py

It should print a full health report:

  ✅ Connection to Odoo: OK (uid=5)
  ✅ Sale Orders: Found NNN confirmed SOs
     Sample: SO/2026/01246 | Customer: Bandasheria | 32T | TEMEKE
  ✅ Purchase Orders (RM): Found NNN confirmed POs
     Sample: LPORD/2025/02158 | Tanga Cement PLC | 20,000MT Clinker
  ✅ Fleet Vehicles: Found NNN active trucks
     Sample: T245DAR | 30T
  ✅ Partners: Read OK (sample partner tested)
  ✅ Stock Locations: Outgoing picking type found (id=N)
  ✅ Write test: Created test picking, immediately cancelled. ID=N
  ⚠️  Missing field: sale.order.x_dispatch_ready — needs to be added in Odoo
  ⚠️  Missing field: res.partner.x_delivery_corridor — needs to be added in Odoo

Also check: can we read the freight/location master?
Print: "Required Odoo custom fields missing: [list]"
Print: "Recommended: Share this report with ERP team before Phase 5"

Handle gracefully if Odoo is unreachable — print clear error with connection details.
```

---

## PROMPT 3.3 — Odoo Sync Service (Scheduler)

```
Write the sync orchestration layer in app/services/odoo_sync.py (add to existing file):

class OdooSyncService:
    '''Orchestrates periodic sync from Odoo to local DB'''

    async def sync_rm_purchase_orders(self, db: AsyncSession) -> SyncResult:
        '''
        Fetch new/updated RM POs from Odoo.
        For each NEW PO not already in our DB:
          1. Create TruckSchedule record(s) via po_scheduler.process_new_po()
          2. Auto-trigger matching engine for each new schedule
        For UPDATED POs: update expected_arrival_dt if scheduled_date changed.
        Returns: SyncResult(new_schedules=N, updated=N, errors=N)
        '''

    async def sync_sale_orders(self, db: AsyncSession) -> SyncResult:
        '''
        Fetch new/updated confirmed SOs from Odoo.
        Upsert CementOrder records.
        For each NEW order: run is_near_ready check against all EXPECTED schedules.
        For CANCELLED orders: release any soft_reservations.
        Re-run matching for affected schedules if significant changes.
        Returns: SyncResult(new_orders=N, updated=N, cancelled=N, errors=N)
        '''

    async def sync_rm_receipts(self, db: AsyncSession) -> SyncResult:
        '''
        Check stock.picking receipt states for EXPECTED/PRE_CONFIRMED trucks.
        When state='assigned' → update TruckSchedule.status = 'ARRIVED'
        When state='done' → update TruckSchedule.actual_arrival_dt
        Returns: SyncResult(arrived=N, completed=N)
        '''

    async def run_full_sync(self, db: AsyncSession) -> dict:
        '''Run all 3 syncs, return combined results'''

    async def rerun_urgency_scores(self, db: AsyncSession):
        '''
        Recalculate urgency_score for all UNALLOCATED orders based on deadline.
        Formula: 1.0 if deadline < now+24h, 0.7 < 48h, 0.4 < 72h, 0.1 else.
        Called after sync_sale_orders.
        '''
```

---

# PHASE 4 — CORE ALGORITHM
## (Week 3)

---

## PROMPT 4.1 — Freight Savings Calculator

```
Write app/services/freight_savings.py completely.

from dataclasses import dataclass

@dataclass
class FreightSavings:
    fresh_freight_tzs: float
    return_freight_tzs: float
    hold_cost_tzs: float
    gross_saving_tzs: float
    net_saving_tzs: float
    saving_pct: float      # 0.0–1.0
    is_viable: bool        # True if net_saving > 0

def compute_savings(
    fresh_freight_tzs: float,        # from CementOrder.fresh_outbound_freight_tzs
    return_load_rate_pct: float,     # from Transporter.return_load_rate_pct
    hold_hours: float,               # time truck waits at plant
    hold_cost_per_hour_tzs: float    # from settings
) -> FreightSavings:
    '''
    Core savings formula from CLAUDE.md:
    return_freight = fresh_freight * return_load_rate_pct
    hold_cost = hold_hours * hold_cost_per_hour_tzs
    gross_saving = fresh_freight - return_freight
    net_saving = gross_saving - hold_cost
    saving_pct = net_saving / fresh_freight (clamped to [0.0, 1.0])
    is_viable = net_saving > 0
    '''

def estimate_fresh_freight(distance_km: int, quantity_tonnes: float) -> float:
    '''
    Estimate freight when not available from Odoo freight matrix.
    Use confirmed rates from CLAUDE.md:
      Tanga route (~360km): TZS 72,000/trip → TZS 2,400/km
      Mbeya route (~870km): TZS 135,000/trip → TZS 155/km
    Use graduated rate table by distance band.
    '''

def compute_hold_hours(truck: TruckSchedule) -> float:
    '''
    If truck.actual_arrival_dt and truck.preferred_departure_dt: use actual
    Else: estimate = 2.0 hours default
    '''

Also write tests inline (if __name__ == '__main__'):
  assert compute_savings(2_100_000, 0.55, 2, 50_000).net_saving_tzs == 845_000
  assert compute_savings(2_100_000, 0.55, 40, 50_000).is_viable == False
```

**Verify:** Run `python app/services/freight_savings.py` — both assertions must pass.

---

## PROMPT 4.2 — Scoring Engine

```
Write app/services/scoring.py completely.

from dataclasses import dataclass

@dataclass
class CandidateScore:
    order_id: int
    capacity_score: float    # 0.0–1.0
    route_score: float       # 0.0–1.0
    urgency_score: float     # 0.0–1.0
    savings_score: float     # 0.0–1.0
    composite_score: float   # weighted sum
    is_near_ready: bool
    deviation_km: int
    item_savings_tzs: float

def score_candidate(
    order: CementOrder,
    truck: TruckSchedule,
    transporter: Transporter,
    remaining_capacity_tonnes: float,
    settings: Settings
) -> CandidateScore:

    # capacity_score
    allocatable = min(order.quantity_tonnes, remaining_capacity_tonnes)
    capacity_score = allocatable / truck.available_payload_tonnes

    # route_score — use route_calculator.deviation_km()
    deviation = deviation_km("KIGAMBONI", order.delivery_region, truck.origin_region)
    route_score = max(0.0, 1.0 - (deviation / truck.max_detour_km))

    # urgency_score
    hours_to_deadline = ...
    urgency_score = urgency_lookup(hours_to_deadline)

    # savings_score — use freight_savings.compute_savings()
    savings = compute_savings(order.fresh_outbound_freight_tzs,
                               transporter.return_load_rate_pct, ...)
    savings_score = max(0.0, min(1.0, savings.saving_pct))

    # near_ready penalty
    nr_penalty = settings.near_ready_score_penalty if order.near_ready else 1.0

    # composite
    composite = (
        settings.score_weight_capacity * capacity_score  +
        settings.score_weight_route    * route_score     +
        settings.score_weight_urgency  * urgency_score * nr_penalty +
        settings.score_weight_savings  * savings_score
    )

    return CandidateScore(...)

def urgency_lookup(hours: float) -> float:
    if hours < 24:   return 1.0
    if hours < 48:   return 0.7
    if hours < 72:   return 0.4
    return 0.1

Add inline tests for edge cases:
  - urgency_lookup(12) == 1.0
  - urgency_lookup(96) == 0.1
  - score with deviation > max_detour returns route_score == 0.0
```

---

## PROMPT 4.3 — PO Scheduler Service

```
Write app/services/po_scheduler.py completely.

This is the TRIGGER SERVICE — converts a new Odoo PO into TruckSchedule record(s).

class POScheduler:

    def process_new_po(self, po_data: dict, db: AsyncSession) -> list[TruckSchedule]:
        '''
        Called when a new RM purchase.order is synced from Odoo.

        Steps:
        1. Identify transporter from po_data['partner_id'] → look up in Transporter table
        2. Determine origin_region:
           a. If po_data has x_origin_region → use it
           b. Else look up transporter.preferred_corridors[0]
           c. Else use RM_ORIGIN_TO_CORRIDOR[material_type] from tanzania_regions.py
        3. Identify raw_material_type from order line product_id → RM item code
        4. Compute estimated_qty_tonnes from PO line quantities
        5. Compute truck_count = ceil(estimated_qty / transporter.avg_truck_capacity_tonnes)
           Cap at reasonable max (e.g. 50 trucks per PO — large POs spread over days)
        6. For each truck (1 to truck_count):
           a. Generate schedule_ref: SCHED-YYYYMMDD-NNN
           b. Build return_route from get_route_waypoints(origin_region, "KIGAMBONI")
              (reversed — the route FROM plant BACK to origin)
           c. Spread expected_arrival_dt: po.scheduled_date ± (i * avg_hours_between_trucks)
              Use avg_hours_between_trucks = 24h / daily_truck_rate for that material
           d. Create TruckSchedule with status='EXPECTED'
        7. Save all schedules to DB
        8. Return list of created schedules
        (Caller triggers matching engine for each)
        '''

    def estimate_daily_truck_rate(self, material_type: str) -> float:
        '''
        Clinker: ~20/day, Coal: ~11/day, Gypsum: ~4/day, Iron Ore: ~1/day
        From CLAUDE.md GRN statistics (13,299 trips/year).
        '''

    def get_schedule_ref(self, db: AsyncSession) -> str:
        '''Generate unique SCHED-YYYYMMDD-NNN with sequence from DB.'''

    def should_process_po(self, po_data: dict) -> bool:
        '''
        Returns False if:
        - PO already fully processed (all qty received)
        - TruckSchedule records already exist for this po_id
        - x_return_load_eligible = False
        '''
```

---

## PROMPT 4.4 — Matching Engine (Core)

```
Write app/services/matching_engine.py completely.

This is the heart of the application.

from dataclasses import dataclass

@dataclass
class AllocationVariant:
    variant_type: str    # MAX_SAVINGS / MAX_LOAD / URGENT_FIRST
    items: list[CandidateScore]
    total_allocated_tonnes: float
    capacity_utilization_pct: float
    total_route_deviation_km: int
    total_fresh_freight_tzs: float
    total_return_freight_tzs: float
    holding_cost_tzs: float
    estimated_savings_tzs: float
    composite_score: float
    has_pending_readiness_orders: bool
    pending_readiness_note: str

async def match(
    schedule: TruckSchedule,
    db: AsyncSession,
    settings: Settings
) -> list[AllocationVariant]:
    '''
    Full matching flow — returns up to 3 variants.

    Step 1: LOAD candidates
      Load all CementOrder WHERE:
        allocation_status IN ('UNALLOCATED', 'NEAR_READY')
        AND odoo_state IN ('sale')
        AND soft_reserved_schedule_id IS NULL (or = this schedule)
        AND delivery_region IS NOT NULL

    Step 2: FILTER by corridor (deviation check)
      For each order:
        dev = deviation_km("KIGAMBONI", order.delivery_region, schedule.origin_region)
        Include if dev <= schedule.max_detour_km
        Include near_ready orders if order.near_ready_eta <= schedule.expected_arrival_dt

    Step 3: FILTER by capacity
      Include if order.quantity_tonnes <= schedule.available_payload_tonnes
      OR if order.partial_load_allowed = True

    Step 4: FILTER by dispatch readiness
      Include ALL that pass corridor test — but mark near_ready orders
      (dispatch_ready=False orders with near_ready=True are candidates with penalty)
      Skip orders where dispatch_ready=False AND near_ready=False

    Step 5: SCORE each candidate
      Use scoring.score_candidate() for each

    Step 6: GENERATE 3 VARIANTS using greedy packing
      Variant A (MAX_SAVINGS):   sort candidates by savings_score DESC, pack until full
      Variant B (MAX_LOAD):      sort candidates by quantity_tonnes DESC, pack until full
      Variant C (URGENT_FIRST):  sort candidates by urgency_score DESC (then savings), pack

      Greedy packing function:
        remaining = schedule.available_payload_tonnes
        packed = []
        for candidate in sorted_candidates:
          alloc_qty = min(candidate.quantity_tonnes, remaining)
          if alloc_qty >= 0.5:  # at least 0.5 MT threshold
            packed.append(with allocated_qty=alloc_qty)
            remaining -= alloc_qty
          if remaining < 0.5: break
        return packed

    Step 7: SEQUENCE stops in each variant
      sort packed items by route_position_pct() along return_route

    Step 8: COMPUTE totals for each variant
      Sum: allocated_tonnes, fresh_freight_tzs, return_freight_tzs, hold_cost, savings

    Step 9: LOG matching event to MatchingEvent table

    Step 10: SAVE proposals to AllocationProposal + ProposalItem tables
      Update TruckSchedule.allocation_status = 'PROPOSED'

    Step 11: TRIGGER AI advisor asynchronously (non-blocking)
      asyncio.create_task(ai_advisor.advise_async(schedule, variants, db))

    Return list of AllocationVariant (up to 3, remove empty variants)
    '''

async def rematch(schedule_id: int, trigger: str, db: AsyncSession) -> list[AllocationVariant]:
    '''
    Re-run match for an existing schedule.
    Archive old PROPOSED proposals.
    Run match() fresh.
    Compute delta vs previous best proposal.
    If delta.savings_change > settings.rematch_alert_threshold_tzs:
      Mark for dispatcher alert.
    '''

async def load_available_schedule_for_region(delivery_region: str,
                                               db: AsyncSession) -> list[TruckSchedule]:
    '''Find EXPECTED/PRE_CONFIRMED trucks whose return route covers a region.
    Used when a new SO arrives to find which trucks it could ride on.'''
```

**Verify:** Run `scripts/demo_allocation.py` (next prompt) to test end-to-end.

---

## PROMPT 4.5 — Demo Allocation Script

```
Write scripts/demo_allocation.py — end-to-end demonstration script.

This script:
1. Creates sample data in the DB (no real Odoo connection needed):

   TRUCK SCHEDULES (3 trucks):
   a. SCHED-TEST-001: Origin=DODOMA (Iron Ore), ETA=today+1day, capacity=30T
      return_route=["KIGAMBONI","CHALINZE","MOROGORO","DODOMA"]
   b. SCHED-TEST-002: Origin=MBEYA (Coal), ETA=today+2days, capacity=30T
      return_route=["KIGAMBONI","CHALINZE","MOROGORO","IRINGA","MBEYA"]
   c. SCHED-TEST-003: Origin=TANGA (Clinker), ETA=today+1day, capacity=30T
      return_route=["KIGAMBONI","CHALINZE","SEGERA","TANGA"]

   CEMENT ORDERS (10 orders):
   SO01: Morogoro, 15T SUPER42, dispatch_ready=True,  fresh_freight=1,800,000 TZS
   SO02: Dodoma,   12T MAX32,   dispatch_ready=True,  fresh_freight=2,100,000 TZS
   SO03: Iringa,    8T SUPER42, dispatch_ready=True,  fresh_freight=1,500,000 TZS
   SO04: Mbeya,    18T MAX32,   dispatch_ready=True,  fresh_freight=2,500,000 TZS
   SO05: Tanga,    20T SUPER42, dispatch_ready=True,  fresh_freight=1,200,000 TZS
   SO06: Arusha,   10T MAX32,   dispatch_ready=True,  fresh_freight=1,400,000 TZS
   SO07: Mwanza,   25T SUPER42, dispatch_ready=True,  fresh_freight=3,000,000 TZS
   SO08: Morogoro, 8T SUPER42,  dispatch_ready=False, near_ready=True, near_ready_eta=today+0.5day
   SO09: Temeke(DSM), 5T MAX32, dispatch_ready=True,  fresh_freight=500,000 TZS
   SO10: Dodoma,   30T BULKER,  dispatch_ready=True,  fresh_freight=2,100,000 TZS

2. Runs matching engine on all 3 trucks

3. Prints formatted results using rich tables:

   ┌─────────────────────────────────────────────────────────────────────┐
   │  MATCH RESULTS — TRUCK SCHED-TEST-001 (DODOMA return, 30T)          │
   ├──────────┬────────────────────────────┬───────────┬──────────────── ┤
   │ Variant  │ Orders                     │ Util %    │ Savings (TZS)   │
   ├──────────┼────────────────────────────┼───────────┼──────────────── ┤
   │ MAX_SAV  │ SO01 Morogoro+SO02 Dodoma  │ 90%       │ 2,350,000       │
   │ MAX_LOAD │ SO10 Dodoma(30T)           │ 100%      │ 1,890,000       │
   │ URGENT   │ SO08(near)+SO01+SO02       │ 83%       │ 2,100,000       │
   └──────────┴────────────────────────────┴───────────┴──────────────── ┘

4. Asserts:
   - SO07 (Mwanza) NOT matched to SCHED-TEST-001 (Dodoma truck — wrong corridor)
   - SO05 (Tanga) matched to SCHED-TEST-003 (Tanga truck)
   - SO03 (Iringa) matched to SCHED-TEST-002 (Mbeya truck — Iringa is on route)
   - SO08 (near_ready) appears in proposals with is_near_ready=True flag

5. Confirms 1 allocation → prints "Would create Odoo stock.picking for..."
   (dry run — no actual Odoo call)

Run with: python scripts/demo_allocation.py
Run with: python scripts/demo_allocation.py --assert  (exits 0 if all pass)
```

**CRITICAL GATE:** All assertions must pass before proceeding to Phase 5.

---

# PHASE 5 — API LAYER & DASHBOARD
## (Week 4)

---

## PROMPT 5.1 — FastAPI App & Routers

```
Write the FastAPI application in app/main.py and all 4 routers.

app/main.py:
- FastAPI app with title "Nyati Return Truck Allocator"
- CORS middleware (allow all origins in dev)
- Static files: mount /static → dashboard/static/
- Templates: mount dashboard/ as template directory
- Startup event: create DB tables + start APScheduler
- Include all routers with /api prefix
- SSE endpoint: GET /api/schedules/feed
  Streams live TruckSchedule updates as Server-Sent Events
  Format: data: {"type": "schedule_update", "id": N, "status": "...", "allocation_status": "..."}
  When a proposal is confirmed, emit: {"type": "truck_allocated", "schedule_id": N}
- Health endpoint: GET /api/health
  Returns: {odoo: "ok"|"error", db: "ok"|"error", schedules_pending: N, orders_unallocated: N}

app/routers/schedules.py:
  GET    /api/schedules          (filter: status, allocation_status, date_from, date_to)
  GET    /api/schedules/available  (only EXPECTED/PRE_CONFIRMED, not CONFIRMED)
  GET    /api/schedules/{id}
  PATCH  /api/schedules/{id}/confirm-details  (add truck_plate, driver, actual_capacity)
  PATCH  /api/schedules/{id}/arrived          (set status=ARRIVED, actual_arrival_dt=now)
  PATCH  /api/schedules/{id}/dispatch         (set status=DISPATCHED)
  POST   /api/schedules/{id}/rematch          (trigger rematch engine)

app/routers/proposals.py:
  GET    /api/proposals          (filter: status, schedule_id)
  GET    /api/proposals/{id}     (full detail with items)
  GET    /api/proposals/{id}/ai-reasoning  (poll for async Claude result)
  PATCH  /api/proposals/{id}/confirm       (confirm → Odoo write-back → SSE push)
  PATCH  /api/proposals/{id}/reject

app/routers/orders.py:
  GET    /api/orders             (filter: status, region, deadline)
  GET    /api/orders/unallocated
  GET    /api/orders/near-ready
  GET    /api/orders/by-corridor/{corridor}
  POST   /api/orders/sync        (force Odoo sync)

app/routers/savings.py:
  GET    /api/savings/summary    (MTD totals)
  GET    /api/savings/by-corridor
  GET    /api/savings/by-transporter

On PATCH /api/proposals/{id}/confirm:
  1. Set proposal.status = CONFIRMED
  2. Set schedule.allocation_status = CONFIRMED
  3. Set each order.allocation_status = ALLOCATED
  4. Call odoo_sync.create_stock_picking() for each item
  5. Store odoo_picking_ids on proposal
  6. Write to SavingsLedger
  7. Emit SSE event: {"type": "truck_allocated", "schedule_id": N}
  8. Return updated proposal
```

---

## PROMPT 5.2 — Dashboard HTML Pages

```
Write the 3 dashboard HTML pages. Use vanilla JavaScript — no React/Vue.
Style with Nyati brand colors: #173158 (navy), #F49545 (orange), #239557 (green).
Use Bootstrap 5 CDN for layout. Custom CSS in dashboard/static/css/nyati.css.

1. dashboard/index.html — Home / Live Schedule
   Layout:
   - Navbar: "🏭 Nyati Cement — Return Truck Allocator" (navy background, white text)
   - KPI row (4 cards, orange accent):
     * INBOUND THIS WEEK (count of EXPECTED trucks next 7 days)
     * UNALLOCATED ORDERS (count)
     * SAVINGS THIS MONTH (TZS formatted: "TZS 18.4M")
     * AVG UTILIZATION (%)
   - "AVAILABLE TRUCKS" table (live via SSE):
     Columns: ETA | Transporter | Origin | Est. Capacity | Match Status | Savings | Action
     Color coding: EXPECTED=gray, PRE_CONFIRMED=blue pill, match found=orange badge
     [VIEW PROPOSALS] button links to proposals.html?schedule={id}
   - Collapsed section "ALLOCATED TRUCKS" (green ✓, Odoo DO reference)
   - SSE connection: reconnects automatically on disconnect

2. dashboard/proposals.html — Allocation Proposals Review
   URL param: ?schedule_id=N
   Layout:
   - Truck header card: plate/origin/ETA/capacity/status
   - 3 variant cards side-by-side (flex/grid):
     Each card shows:
     * Variant label (MAX SAVINGS / MAX LOAD / URGENT FIRST) with color badge
     * Savings amount (large, green font: "TZS 2,350,000")
     * Capacity bar (orange fill)
     * Order list: Customer | Region | Tonnes | Deadline | ⚠ if near-ready
     * [CONFIRM] button (orange, prominent) + [REJECT] (ghost)
   - AI Reasoning panel (loads async):
     Spinner while loading. Shows Claude's text when ready.
     Warnings shown as yellow alert boxes.
   - On CONFIRM click: POST to /api/proposals/{id}/confirm
     Show success toast + redirect to index.html after 2s

3. dashboard/confirmed.html — Confirmed Allocations History
   Layout:
   - Filter bar: date range, corridor, transporter
   - Table: Date | Trip Ref | Truck | Transporter | Corridor | Orders | Savings | Odoo DO | Status
   - [Export CSV] button

Write dashboard/static/css/nyati.css with brand variables and component styles.
Write dashboard/static/js/api.js (fetch wrapper with base URL and error handling).
Write dashboard/static/js/schedule-feed.js (SSE client with reconnect logic).
```

---

# PHASE 6 — ODOO WRITE-BACK & AI ADVISOR
## (Week 5–6)

---

## PROMPT 6.1 — Odoo Write-Back (Confirm → Picking)

```
Complete the Odoo write-back in app/services/odoo_sync.py.

Implement create_stock_picking() fully:

def create_stock_picking(self, order: CementOrder, proposal: AllocationProposal,
                          item: ProposalItem, schedule: TruckSchedule) -> int:
    '''
    Create a stock.picking in Odoo for a single order line.

    payload = {
        'picking_type_id': settings.odoo_picking_type_outgoing_id,
        'partner_id': order.customer_odoo_id,
        'location_id': settings.odoo_location_stock_id,
        'location_dest_id': settings.odoo_location_customer_id,
        'origin': f'TRUCK/{schedule.schedule_ref}/{proposal.proposal_ref}',
        'note': f'Return load allocation. Truck: {schedule.truck_plate or "TBC"}. '
                f'Transporter: {schedule.supplier.name}. '
                f'Driver: {schedule.driver_name or "TBC"}.',
        'move_ids': [(0, 0, {
            'name': order.product_code,
            'product_id': <lookup odoo product_id from order.odoo_order_id>,
            'product_uom_qty': item.allocated_bags,
            'product_uom': <UOM bag id from settings or lookup>,
            'location_id': settings.odoo_location_stock_id,
            'location_dest_id': settings.odoo_location_customer_id,
        })]
    }

    Also implement an error retry queue:
    - If create fails: save to local FailedOdooWrite table (create this model)
    - APScheduler retries failed writes every 30 min (max 3 attempts)
    - After 3 failures: mark as MANUAL_ACTION_REQUIRED, alert via log

    Write integration test: tests/test_odoo_writeback.py
    Use respx or unittest.mock to mock the XML-RPC calls.
    Assert picking payload has correct origin format.
    '''
```

---

## PROMPT 6.2 — Claude AI Advisor

```
Write app/services/ai_advisor.py completely.

Follow the EXACT same pattern as the NyatiBrandAgent in:
D:\new frontier\branding with cc\agent\agent.py

class TruckAllocationAdvisor:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"

    CACHED_SYSTEM_PROMPT = """
    You are a logistics optimization advisor for Lake Cement Limited (Nyati Cement),
    Tanzania. The cement plant is at Kimbiji, Kigamboni, Dar es Salaam.

    RAW MATERIAL SOURCES:
    - Clinker: Tanga (Tanga Cement PLC, Maweni Limestone) and Mtwara (Dangote)
    - Coal: Kyela/Mbeya (State Mining, Market Insight, Ruvuma Coal, Yongda)
    - Gypsum: Lindi/Kiranjeranje (Emmanuel Martini), Mwanza (Kamba's Group), DSM (local)
    - Iron Ore: Dodoma/Asanje (Pecot, Right Investment, Yerusalemu, Rudo General)

    RETURN CORRIDORS:
    - Northern: Kigamboni → Chalinze → Segera → Tanga / Moshi → Arusha
    - Central: Kigamboni → Chalinze → Morogoro → Dodoma → Tabora → Mwanza
    - Southern Highlands: Kigamboni → Chalinze → Morogoro → Iringa → Mbeya → Kyela
    - Southern Coast: Kigamboni → Ikwiriri → Nyamisati → Kibiti → Kiranjeranje (Lindi)
    - Ruvuma: via Iringa → Njombe → Songea

    KEY FACTS:
    - Standard truck capacity: 28–33 MT (30 MT typical)
    - Chalinze junction (60km from plant) is where ALL routes diverge
    - Currency: TZS (Tanzanian Shilling)
    - Typical freight: Tanga route TZS 60–84k/trip, Mbeya route TZS 135k/trip
    - Allocations are made BEFORE the truck arrives (proactive model)

    YOUR ROLE: Given a proposed allocation, provide:
    1. A plain-language rationale (2–3 sentences) a logistics dispatcher can understand
    2. Risk flags (list): credit holds, near-ready order risks, seasonal road issues,
       driver hours concerns, capacity mismatch, any driver/transporter reliability issues
    3. A single alternative suggestion if you see a better option
    4. A clear recommendation: CONFIRM / REVIEW / HOLD with one-line reason

    Be concise. Be specific to Tanzania. Reference real cities and routes.
    Always mention the estimated savings in TZS.
    """

    async def advise_async(
        self,
        schedule: TruckSchedule,
        variants: list[AllocationVariant],
        db: AsyncSession
    ) -> AIAdvisory:
        '''
        Non-blocking AI advisory. Called via asyncio.create_task().
        Builds prompt from schedule + variants data.
        Stores result in AllocationProposal.ai_reasoning and ai_warnings.
        Uses prompt caching (mark system prompt as cache_control: ephemeral).
        Returns AIAdvisory dataclass.
        '''

    def build_advice_prompt(self, schedule, variants) -> str:
        '''
        Build a concise prompt with:
        - Truck details: origin, capacity, ETA, transporter, reliability score
        - For each variant: orders (customer/region/qty/deadline), savings, utilization
        - Near-ready orders flagged
        - Ask Claude to pick the best variant and explain why
        '''

Prompt caching: wrap the CACHED_SYSTEM_PROMPT in:
  {"type": "text", "text": CACHED_SYSTEM_PROMPT,
   "cache_control": {"type": "ephemeral"}}

This reduces cost significantly for repeated calls.
```

---

## PROMPT 6.3 — APScheduler Automation

```
Add APScheduler to app/main.py for automated background tasks.

On FastAPI startup, configure these scheduled jobs:

1. ODOO_SYNC — every 15 minutes
   sync_service.run_full_sync(db)
   Log: "Sync complete: {N} new schedules, {N} new orders, {N} arrivals detected"

2. URGENCY_RESCORE — every 1 hour
   sync_service.rerun_urgency_scores(db)
   For orders whose urgency_score changed significantly:
     Re-run match for affected EXPECTED/PROPOSED trucks

3. PRE_ARRIVAL_REMATCH — every 6 hours
   For all EXPECTED trucks with ETA within 24 hours:
     Run rematch(schedule_id, trigger='24H_BEFORE_ETA')
     If better proposals found → update DB + alert in next SSE push

4. DAILY_SAVINGS_LEDGER — daily at 23:59
   Aggregate today's confirmed proposals into SavingsLedger

Configure APScheduler:
- Use AsyncIOScheduler
- Start on FastAPI startup event, shutdown on shutdown event
- Log all job executions
- Handle job failures gracefully (log error, don't crash server)

Add job status to GET /api/health response:
  "scheduler": {"status": "running", "next_sync_in_seconds": N}
```

---

# PHASE 7 — TESTING & HARDENING
## (Week 7–8)

---

## PROMPT 7.1 — Unit Tests

```
Write the complete test suite in tests/.

tests/conftest.py:
  - pytest fixtures: async_db_session, sample_truck_schedule, sample_cement_orders,
    sample_transporter, mock_odoo_client
  - Use pytest-asyncio with asyncio_mode="auto"
  - Use in-memory SQLite for tests

tests/test_route_calculator.py:
  - test_morogoro_zero_detour_for_dodoma_truck()
    deviation_km("KIGAMBONI", "MOROGORO", "DODOMA") == 0
  - test_tanga_high_detour_for_mbeya_truck()
    deviation_km("KIGAMBONI", "TANGA", "MBEYA") > 500
  - test_iringa_on_mbeya_corridor()
    is_on_corridor("IRINGA", "SOUTHERN_HIGHLANDS") == True
  - test_arusha_not_on_central_corridor()
    is_on_corridor("ARUSHA", "CENTRAL") == False
  - test_stop_sequencing_dodoma_route()
    stops [DODOMA, MOROGORO] → sorted as [MOROGORO, DODOMA] (Morogoro first)
  - test_city_normalization_variations()
    normalize_city_to_region("morogoro urban") == "MOROGORO"
    normalize_city_to_region("DAR ES SALAAM") == "DSM"
    normalize_city_to_region("Mbeya City") == "MBEYA"

tests/test_freight_savings.py:
  - test_basic_savings_calculation()
  - test_hold_cost_erodes_savings()
  - test_not_viable_when_hold_too_long()
  - test_distance_based_estimate()

tests/test_scoring.py:
  - test_on_route_order_scores_1_for_route()
  - test_order_at_detour_limit_scores_zero()
  - test_urgent_order_scores_high()
  - test_near_ready_penalty_applied()
  - test_composite_weights_sum_to_composite()

tests/test_matching_engine.py:
  - test_off_corridor_orders_excluded()
    Mwanza order not in proposals for Dodoma truck
  - test_three_variants_generated()
  - test_stops_sequenced_correctly()
    Morogoro stop comes before Dodoma stop for Dodoma-return truck
  - test_near_ready_flagged_in_proposals()
  - test_capacity_not_exceeded()
    Total allocated_tonnes <= truck.available_payload
  - test_allocated_truck_absent_from_available_list()

tests/test_odoo_sync.py:
  - test_fetch_sale_orders_maps_fields()
    Mock XML-RPC response → assert CementOrder fields populated correctly
  - test_create_picking_correct_origin_format()
    Assert origin = "TRUCK/SCHED-TEST-001/PROP-TEST-001"
  - test_connection_error_raises_odoo_error()

Run all tests with: pytest tests/ -v
All must pass. Target: 90%+ coverage on services/.
```

---

## PROMPT 7.2 — API Key Authentication

```
Add simple API key authentication to protect all /api/ endpoints.

1. In app/config.py: add APP_API_KEY: str setting
2. Create app/auth.py with:
   - verify_api_key(api_key: str = Header(alias="X-API-Key")) dependency
   - Reads from settings.app_api_key
   - Raises HTTP 401 if missing or wrong
   - Skips auth for: /api/health, /docs, /openapi.json, /static/**, dashboard pages
3. Apply to all /api/ routers via dependencies=
4. Dashboard JS: include X-API-Key header in all fetch() calls (read from meta tag)
5. .env.example: add APP_API_KEY=your-secret-key-here

Note: The dashboard reads API key from a <meta name="api-key"> tag in HTML,
populated from settings at page render time (simple Jinja2 context injection).
```

---

## PROMPT 7.3 — Structured Logging

```
Add structured JSON logging to the application.

1. Create app/logging_config.py:
   - JSON formatter that outputs: timestamp, level, logger, message,
     plus any extra fields passed
   - Always include: truck_schedule_id, proposal_id, order_id where relevant
   - Output to stdout (for containerization)
   - Log level from settings.log_level (default: INFO)

2. Create app/logger.py:
   - get_logger(name) factory function
   - Bound logger factory: get_bound_logger(name, **context)
     Returns logger with pre-bound fields (e.g. schedule_id=N)

3. Add structured log calls to all service methods:
   matching_engine: log when match runs, how many candidates, which were filtered out
   odoo_sync: log every Odoo call with record counts
   ai_advisor: log when Claude is called, token usage, cache hit/miss
   proposals confirm: log savings captured, odoo picking created

4. Update GET /api/health to show:
   "last_sync": "2026-04-27T14:30:00Z",
   "last_sync_result": {"new_schedules": 3, "new_orders": 12}
```

---

# PHASE 8 — FINAL INTEGRATION & DEPLOY
## (Week 8)

---

## PROMPT 8.1 — End-to-End Integration Test

```
Write scripts/integration_test.py — a complete end-to-end test
that simulates the full proactive allocation workflow WITHOUT requiring
a live Odoo connection.

The script uses a test SQLite database and mocks Odoo responses.

SCENARIO (from CLAUDE.md demo scenario):

Step 1: Simulate Odoo PO sync
  Feed in mock PO: LPORD/TEST/00001
  Supplier: Tanga Cement PLC (CMLT2146), 600 MT Clinker, ETA tomorrow
  → Assert: 1 TruckSchedule created (SCHED-XXXX), status=EXPECTED
  → Assert: Matching engine ran automatically

Step 2: Check proposals created
  → Assert: AllocationProposal(s) exist for the schedule
  → Assert: 3 variants proposed

Step 3: Simulate new SO arriving
  Feed in mock SO: SO/TEST/00001, Tanga customer, 20T, dispatch_ready=True
  → Assert: rematch triggered for the EXPECTED Tanga truck
  → Assert: Tanga order now appears in proposals

Step 4: Confirm a proposal
  PATCH /api/proposals/{id}/confirm with confirmed_by="Test Dispatcher"
  → Assert: proposal.status == CONFIRMED
  → Assert: schedule.allocation_status == CONFIRMED
  → Assert: order.allocation_status == ALLOCATED
  → Assert: schedule NOT in GET /api/schedules/available response (key test!)
  → Assert: Odoo picking creation was attempted with correct payload

Step 5: Check SSE event emitted
  → Assert: SSE buffer contains {"type": "truck_allocated", "schedule_id": N}

Step 6: Check savings ledger
  → Assert: SavingsLedger entry created for this month

Print "ALL INTEGRATION TESTS PASSED ✅" or show detailed failure.
Exit code 0 on pass, 1 on failure.
```

---

## PROMPT 8.2 — README and Deployment

```
Write README.md for this project (professional, comprehensive).

Include sections:
1. Overview (1 paragraph — what this does and why)
2. Architecture diagram (ASCII text version)
3. Prerequisites (Python 3.11+, Odoo 15 service account)
4. Quick Start (dev setup in 5 commands)
5. Configuration (table of all .env variables with descriptions)
6. Data Files (table of 8 Excel files and how they're used)
7. Seeding (commands to run seed scripts)
8. Running the app
9. Running tests
10. API Documentation (link to /docs)
11. Odoo Setup Requirements (what fields to add, service account permissions)
12. Production Deployment (gunicorn + systemd + nginx)

Also write a Makefile with targets:
  make install    → pip install -r requirements.txt
  make migrate    → alembic upgrade head
  make seed       → run all seed scripts
  make test       → pytest tests/ -v
  make demo       → python scripts/demo_allocation.py
  make run        → uvicorn app.main:app --reload --port 8001
  make integration → python scripts/integration_test.py
```

---

## BONUS PROMPTS — Enhancement Implementations

### BONUS A — WhatsApp Transporter Notification

```
Add WhatsApp notification when allocation is confirmed.

In app/services/notifications.py:
  async def notify_transporter_whatsapp(schedule, proposal):
    '''
    Send WhatsApp message to transporter/driver when allocation confirmed.
    Message template:
    "Dear [Transporter], your truck [plate] arriving [ETA] from [origin]
    has been pre-assigned with cement orders:
    1. [Customer] - [Region] - [Tonnes]T
    2. ...
    Loading will be prepared on your arrival at Kimbiji Plant.
    Loading instructions ref: [proposal_ref]
    Contact: [dispatcher_phone]"

    Integration options (in order of preference):
    1. Africa's Talking SMS/WhatsApp API
    2. Twilio WhatsApp Business API
    3. Simple SMS fallback via Africa's Talking

    Store notification log in DB.
    '''

Configure: WHATSAPP_API_KEY in .env, DISPATCHER_PHONE, DISPATCHER_NAME.
Trigger from: PATCH /api/proposals/{id}/confirm (after Odoo write-back).
```

### BONUS B — Monthly Savings PDF Report

```
Write scripts/generate_monthly_report.py.

Uses reportlab (same library used in D:\new frontier\branding with cc\generate_brand_manual.py).
Reuse the NyatiBrandAgent report styling patterns.

Report contains:
1. Cover page: Nyati brand header (#173158 navy), month/year, "Return Truck Optimization Report"
2. Executive Summary: Total savings TZS, truck count, match rate, utilization
3. Bar chart: Savings by corridor (use reportlab's chart module)
4. Table: Top 10 savings allocations of the month
5. Table: Savings by transporter
6. Line chart: Daily savings trend
7. Appendix: All allocation details

Output to: reports/YYYY-MM-return-truck-report.pdf
Schedule with APScheduler: run on 1st of each month at 06:00.
Run manually: python scripts/generate_monthly_report.py --month 2026-04
```

---

## QUICK REFERENCE — Verification Commands

After each phase, run these to confirm everything is working:

```bash
# Phase 1 check
python -c "from app.models import TruckSchedule; print('Models OK')"
alembic current   # should show head

# Phase 2 check
python app/services/route_calculator.py    # assertions pass
python scripts/seed_routes.py --dry-run   # shows what will be seeded

# Phase 3 check
python scripts/test_odoo_connection.py    # full health report

# Phase 4 check
python scripts/demo_allocation.py --assert  # all assertions pass

# Phase 5 check
uvicorn app.main:app --reload &
curl http://localhost:8001/api/health       # {"status": "ok"}
curl http://localhost:8001/api/schedules    # empty list (before seeding)
open http://localhost:8001                 # dashboard loads

# Phase 6 check
python scripts/integration_test.py         # ALL TESTS PASSED

# Full test suite
pytest tests/ -v --tb=short               # all green
```

---

## TROUBLESHOOTING PROMPTS

Use these if you hit problems:

### If Odoo connection fails:
```
The Odoo XML-RPC connection in app/services/odoo_sync.py is failing with [error].
The Odoo URL is [URL], database is [DB].
Check the connection code and add better error messages that tell me:
1. Is it a network issue (can't reach server)?
2. Is it an authentication issue (wrong credentials)?
3. Is it a field mapping issue (field doesn't exist in this Odoo version)?
Show me a diagnostic that checks each layer separately.
```

### If matching produces wrong results:
```
The matching engine is [including/excluding] order [SO_ID] from the proposals
for truck [SCHED_ID]. Expected: [what you expect].
Order details: region=[X], qty=[Y], dispatch_ready=[Z]
Truck details: origin=[X], return_route=[Y], max_detour=[Z]

Check route_calculator.deviation_km() for this combination and show me
the step-by-step calculation. Also check the scoring for this candidate.
```

### If SSE dashboard doesn't update:
```
The SSE endpoint at /api/schedules/feed is connected but the dashboard
doesn't update when I confirm an allocation via the API.
Check the SSE event emission in the confirm endpoint and the
schedule-feed.js client code. Show me the full event flow.
```

---

*PROMPTS-PLAYBOOK.md — Smart Return Truck Allocator*
*Use these prompts sequentially in VS Code with Claude Code.*
*Each prompt is designed to be self-contained and verifiable.*
