# SMART RETURN TRUCK ALLOCATOR
## Project Intelligence File — CLAUDE.md
### Lake Cement Limited (Nyati Cement), Tanzania
**Project Path:** `C:\Users\USER\return trucks optimization\`
**Plan File:** `C:\Users\USER\.claude\plans\you-are-senior-software-buzzing-clock.md`
**Last Updated:** 2026-05-18

---

## WHAT THIS PROJECT IS

A **return truck logistics dashboard** that tracks inbound raw material trucks and helps dispatchers allocate cement delivery orders to them via Odoo — before the trucks leave the plant.

**Data entry (as of 2026-05-18):** Truck schedule data is entered via **Excel import**, not Odoo PO sync. The Purchase department prepares an Excel sheet as soon as a transporter is dispatched from the supplier. The Logistics team uploads the sheet via `POST /api/schedules/import`. The server processes the file in memory (never written to disk), deduplicates by `truck_plate + dispatch_date`, auto-stamps `upload_date`, derives the return corridor from `raw_material_type`, and auto-purges terminal records (LOADED/RELEASED) older than 30 days on each successful import.

**Dispatcher workflow:**
1. Open the Schedule page — see all inbound trucks imported from Purchase dept Excel sheets
2. Use the filter bar (search, material, corridor dropdowns) to find relevant trucks
3. Click **Allocate →** on a truck row — opens the Odoo Sale Order creation form, pre-filled with the truck plate and driver details
4. Complete the Sale Order in Odoo — cement is assigned to the return truck
5. Monitor on Order Status page (live Odoo SOs) and Final Status page (outcomes: Dispatched vs Released)

**Background intelligence:** A matching engine and scoring system still run in the background — they score unallocated cement orders by corridor fit and urgency, and run a pre-arrival re-score job 24 hours before each truck's ETA. This data is available via API but is **not currently surfaced in the dispatcher UI** — the UI relies on the dispatcher completing allocation directly in Odoo.

**Financial tracking:** `Net Savings = Fresh outbound freight − Return load negotiated rate − Holding cost`

The system is built as a standalone **FastAPI Python service** connected to Odoo 15 via XML-RPC, with a local SQLite database for truck schedule tracking and savings ledger.

---

## PLANT & OPERATIONAL CONTEXT

| Attribute | Value |
|---|---|
| **Plant Name** | Kimbiji Plant |
| **Plant Location** | Kimbiji, Kigamboni, Dar es Salaam |
| **Odoo Location Code** | `Receipts(KIMBIJI PLANT)` |
| **Odoo Customer Code** | `C60011895` = LAKE CEMENT LIMITED (internal) |
| **ERP System** | Odoo 15 (Business Unit: TZG) |
| **Currency** | TZS (Tanzanian Shilling) |
| **Standard Truck Capacity** | 28–33 MT per trip (from GRN weighbridge data) |
| **Typical truck payload** | ~30 MT net |

---

## DATA FILES IN THIS DIRECTORY

All 8 Excel files are **source-of-truth reference data** for seeding, mapping, and validating the application. Never delete or overwrite them.

| File | Purpose | Rows | Key Use |
|---|---|---|---|
| `transporter master.xlsx` | Full transporter vendor list | 417 | Seed `Transporter` table; map vendor codes |
| `location master.xlsx` | All delivery locations with distances | 859 | Seed `CustomerLogistics`; **Kilometer field = distance from plant** |
| `Routes template26042026.xlsx` | RM source locations and route waypoints | 7+466 | Seed `RouteCorridor`; map RM materials to origins |
| `Customer master.xlsx` | Full customer database | 1,154 | Seed `CustomerLogistics`; map Zones to corridors |
| `LAKE CEMENT Daily Report (1).xlsx` | Actual inbound truck records (2026) | 1,665+ | Historical truck data; validate matching logic |
| `approved sales orders 1st April'25 to 24th April'26.xlsx` | Full SO history with truck + destination | 30,741 | Train scoring model; validate freight matrix |
| `RM and SFG GRN and DC or DN Details Apr 25 to Apr26.xlsx` | All RM receipts (GRNs) by material | 13,299+ | Historical truck arrivals; validate PO→truck mapping |
| `Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx` | RM transporters, suppliers, PO details | Multi-sheet | Critical: RM supplier→origin region mapping |

---

## RAW MATERIAL SOURCES (CONFIRMED FROM DATA)

This is the intelligence that powers the proactive truck tracking. Each material type comes from specific regions, determining which return corridor a truck uses.

### CLINKER (Item Code: RM000014)
| Supplier | Code | Location | Return Corridor |
|---|---|---|---|
| Tanga Cement PLC | CMLT2146 | Tanga | NORTHERN (via Chalinze→Segera→Tanga) |
| Maweni Limestone Limited | CMLT0365 | Tanga | NORTHERN (via Chalinze→Segera→Tanga) |
| Dangote Industries Limited | CMLU1522 | Mtwara | SOUTHERN COAST (via Kibiti→Lindi→Mtwara) |

**Clinker PO volumes:** 20,000–40,000 MT per order (Tanga Cement). Trucks run continuously; ~30 MT/truck → ~650–1,300 truck trips per PO.
**Key transporter for Clinker:** Lake Cement Ltd - Logistics (internal), ANTU LOGISTICS CO. LIMITED, KAIXIN, Nacharo Royal, SAIBABA TRUCKS LTD, RS COMPANY

### COAL (Item Code: RM000001)
| Supplier | Code | Region | Return Corridor |
|---|---|---|---|
| State Mining Corporation | CMLT0559 | Kyela/Mbeya | SOUTHERN HIGHLANDS |
| Market Insight Limited | CMLT0357 | Mbeya | SOUTHERN HIGHLANDS |
| Ruvuma Coal Limited | — | Songea/Ruvuma | SOUTHERN (via Iringa→Songea) |
| Montreal Company Limited | — | Mbeya | SOUTHERN HIGHLANDS |
| Yongda International Energy | CMLT2155 | Mbeya/Kyela | SOUTHERN HIGHLANDS |

**Coal PO volumes:** 3,000 MT per order → ~100 truck trips per PO.

### GYPSUM (Item Code: RM000003)
| Supplier | Code | Location | Return Corridor |
|---|---|---|---|
| Emmanuel Martini Mgonja | CMLT0153 | Kiranjeranje, Lindi | SOUTHERN COAST (Route R1) |
| Walson Company Limited | CMLT0642 / CMLT2302 | Dar es Salaam | LOCAL |
| Ongujo Investment Co. | CMLT1668 / CMLT2277 | Dar es Salaam | LOCAL |
| Rudo General Supplies | CMLT0493 | Dar es Salaam | LOCAL |
| Kamba's Group of Companies | CMLT2244 | Mwanza | LAKE VICTORIA |
| Abco Investment Limited | CMLT2247 | Dar es Salaam | LOCAL |
| Amerint Africa Limited | CMLT2213 | Dar es Salaam | LOCAL |

**Gypsum Route R1 (Lindi):** KIRANJERANJE → KIBITI → UTETE → NYAMISATI → IKWIRIRI → KIMBIJI (coastal route via Rufiji Delta)

### IRON ORE (Item Code: RM000004)
| Supplier | Code | Location | Return Corridor |
|---|---|---|---|
| Pecot General Supplies Ltd | CMLT1333 | Dodoma (Asanje) | CENTRAL |
| Right Investment Company | CMLT0489 | Dodoma | CENTRAL |
| Yerusalemu Hospitality Limited | CMLT1734 | Dodoma | CENTRAL |
| Rudo General Supplies | CMLT0493 | Dodoma | CENTRAL |

**Iron Ore PO volumes:** 34–600 MT per order, ~30 MT/truck.

---

## ODOO 15 DATA STRUCTURES (ACTUAL FIELD NAMES)

### Purchase Order (`purchase.order`)
```
PO Number format:     LPORD/YYYY/NNNNN  (e.g. LPORD/2025/02158)
GRN Number format:    CM/GRN/YYYY/NNNNN (e.g. CM/GRN/2025/00021)
Inward Token format:  RM/YYYY/NNNNN     (e.g. RM/2025/00009)
Gate Entry format:    RM-DD/MM/YYYY-N   (e.g. RM-02/04/2025-10)

Key fields used:
  - state            → 'purchase' (confirmed)
  - partner_id       → vendor/supplier code (CMLTXXXX)
  - scheduled_date   → expected delivery at plant
  - order_line       → product_id (RM000001/3/4/14), product_qty, product_uom (MT)
  - picking_ids      → linked stock.picking receipt
  - x_origin_region  → [NEW FIELD TO ADD] override if supplier has multiple origins
```

### Stock Picking — Inward Receipt
```
  - picking_type_code = 'incoming'
  - origin            = PO number (LPORD/...)
  - state             = 'draft'→'confirmed'→'assigned'→'done'
  - scheduled_date    = expected date
  - partner_id        = supplier
  When state = 'assigned': truck is near/at plant
  When state = 'done':     RM received, truck unloaded
```

### Sales Order (`sale.order`)
```
SO Number format:      SO/YYYY/NNNNN    (e.g. SO/2026/01246)
Sales Invoice format:  SI260XXXXXXX

Key fields (from approved SOs file):
  - Customer             → [CUS###] Name format
  - Order Reference      → SO/YYYY/NNNNN
  - Order Date
  - LPO No               → Customer's purchase order reference
  - Truck No             → Plate number (e.g. T810BZW)
  - Trailer No           → Trailer plate (e.g. T339BZT)
  - Driver Name
  - Driver Mobile No
  - Driver License No    → Driver ID number
  - Product              → "CEM II A–L 42.5 R", "CEM II B-M 42.5 N"
  - Baggage Type         → "50 Kg Bag", "Bulker"
  - Qty MT (Ordered)     → Metric tonnes
  - Destination Location → Location name from location master
  - Transporter Name     → "CUSTOMER ARRANGED", "LAKE CEMENT LTD - LOGISTICS", or specific transporter
  - Destination Location/District
  - Destination Location/Region
```

### GRN Data (from `RM and SFG GRN` file) — Critical for truck history
```
Fields available in GRN records:
  GRN No, GRN Date, Inward Token No, Gate Entry Serial No, Gate Entry Date,
  PO No, PO Date, Vendor Code, Vendor Name, Vendor DC No, Vendor DC Date,
  Vendor Invoice No, Vendor Invoice Date,
  Item Code, Item Name, UOM, Received Qty, Variance Qty, Rate, Value,
  Transporter Name, Freight (TZS),
  Vehicle No (truck plate), Vehicle Type (Open/Tipper),
  Unloading Date, Unloading Time,
  Weighbridge Net Qty, Weighbridge Ticket No,
  GRN Status (Done/Pending)
  [Coal only] QC Status, LC No, LC Amount, LC Status
```

---

## TRANSPORTER MASTER (from data files)

### RM Transporters (136 active — `Raw Material Vendor Master-Tran` sheet)
Key transporters for RM inbound:

| Code | Name | Region | Notes |
|---|---|---|---|
| CMLT2146 | Tanga Cement PLC | Tanga | Also supplier (Clinker) — own trucks |
| CMLT2307 | Mwamba Investment Limited | Dar es Salaam | Key Clinker transporter (KAIXIN fleet) |
| CMLT2314 | SALUM ABDULRAHMAN SALIM T/A SOLID LINK | Dar es Salaam | — |
| CMLT2317 | BANVA COMPANY LIMITED | Dar es Salaam | — |
| CMLT2318 | VAISAM LOGISTICS TANZANIA LIMITED | Dar es Salaam | — |
| CMLT2320 | Nacharo Royal Company Limited | Tanga | Key Clinker transporter |
| CMLT2322 | AFRINEXUS LOGISTICS LIMITED | Dar es Salaam | — |

**Named transporter fleets seen in Daily Report:**
- KAIXIN → Mwamba Investment Limited (trucks: T865EHY, T866EHY, T867EHY, T830EHY, T149ENC, T159ENC etc.)
- ANTU LOGISTICS → ANTU LOGISTICS CO. LIMITED (trucks: T316ENF, T431CPQ, T490ENX, T476ENX, T472ENX, T488EMB)
- NACHARO ROYAL → Nacharo Royal Company Limited (trucks: T218EJE, T216EJE, T258EJE, T724EKJ, T725EKJ)
- SAIBABA TRUCKS → SAIBABA TRUCKS LTD (trucks: T876DKD, T121AQL, T405DYX, T217AWR)
- RS COMPANY → (trucks: T795ELM, T794ELM, T195EGZ)
- MR&SONS → M R & SONS LIMITED (trucks: T768EFK)
- MWAMBA INV TD → Mwamba Investment Limited (T633EJW)
- RAS → Ras Logistics (T) Ltd (T718EKT, T719EKT)

### Cement Delivery Transporters (from sales orders)
- CUSTOMER ARRANGED — customer uses their own truck
- LAKE CEMENT LTD - LOGISTICS — LCL's own logistics
- GALCO LIMITED — Dodoma route (bulker)
- RELEVANCE INVESTMENTS LTD — Dodoma (self-deliver)
- EMMANUEL MARTINI MGONJA — Rufiji/Coast route
- Various customer-arranged transporters

---

## LOCATION MASTER INTELLIGENCE

The `location master.xlsx` has **859 delivery locations** with a critical `Kilometer` field = road distance from Kimbiji plant.

**Sample Distances (from Kilometer field — already measured by LCL):**
```
BONYOKWA (Ilala, DSM):         53 km
Buguruni (Ilala, DSM):         60 km
BUYUNI (Ilala, DSM):           65 km
CHANIKA (Ilala, DSM):          80 km
GONGO LA MBOTO (Ilala, DSM):   70 km
ILALA (DSM):                   80 km
KIMANGA (DSM):                 66 km
KINYEREZI (DSM):               72 km
```

**This is more accurate than any external mapping API** — use this field directly in `route_calculator.py` instead of estimating. Seed the `route_definitions` table from this file.

**Location `Type` field values:**
- `Both` — used for both inbound and outbound deliveries
- Other values to confirm from full data

---

## CUSTOMER MASTER INTELLIGENCE

**1,154 customers** with detailed Zone/Region/District classification.

### Customer Zone System
LCL uses a proprietary sales zone system:
```
PROJECT ZONES:  Project 1, Project 2, Project 3, Project 4, Project 5
REGIONAL ZONES: Central 1, Central 2
DSM ZONES:      DAR ES SALAAM 1, DAR ES SALAAM 2, DAR ES SALAAM 3, DAR ES SALAAM 4, DAR ES SALAAM 5
HIGHLANDS:      Southern highland 1, Southern highland 2
LAKE ZONE:      Lake 1 (Mwanza area)
NORTHERN:       Northern 1 (Arusha/Kilimanjaro area)
```

### Zone → Corridor Mapping
```python
ZONE_TO_CORRIDOR = {
    "Project 1": "DSM_LOCAL",
    "Project 2": "DSM_LOCAL",
    "DAR ES SALAAM 1": "DSM_LOCAL",
    "DAR ES SALAAM 2": "DSM_LOCAL",
    "DAR ES SALAAM 3": "DSM_LOCAL",
    "DAR ES SALAAM 4": "DSM_LOCAL",
    "DAR ES SALAAM 5": "DSM_LOCAL",
    "Central 1": "CENTRAL",       # Dodoma direction
    "Central 2": "CENTRAL",       # Dodoma/Singida direction
    "Southern highland 1": "SOUTHERN_HIGHLANDS",  # Iringa/Mbeya
    "Southern highland 2": "SOUTHERN_HIGHLANDS",
    "Lake 1": "LAKE_VICTORIA",    # Mwanza
    "Northern 1": "NORTHERN",     # Arusha/Moshi
}
```

### Customer Distribution (by Region — from data)
```
Dar es Salaam: ~400+ customers (largest segment)
Mbeya:         ~50+ customers (Southern Highlands)
Dodoma:        ~40+ customers (Central corridor)
Arusha/Moshi:  ~30+ customers (Northern corridor)
Pwani:         ~60+ customers (Coastal, includes Rufiji)
Tanga:         ~30+ customers
Mwanza:        ~20+ customers
International: Rwanda (RAF plates noted in SOs)
```

---

## SALES ORDER INTELLIGENCE (30,741 orders — Apr 2025 to Apr 2026)

### Products Sold
```
CEM II A–L 42.5 R   → "SUPER 42" equivalent — 50 Kg Bag (most common)
CEM II B-M 42.5 N   → "DURAMAX" equivalent — Bulker (large project orders)
```

### Order Size Distribution (from data)
- Typical SO: 15–35 MT
- Bulker orders: 30 MT exactly (project clients)
- Small orders: 15 MT
- Large project orders: 30–33.5 MT

### Key Delivery Destinations (from SOs — high volume)
```
TEMEKE               (DSM, Local)
KIGAMBONI            (DSM, Local — note: near plant!)
MOF YARD - MTUMBA - DODOMA   (Central corridor, Bulker)
Dodoma               (Central corridor)
NYAMISATI            (Pwani/Rufiji — Route R1)
GASABO               (Rwanda — international)
```

### Transporter Patterns (from SOs)
- **CUSTOMER ARRANGED:** Most common — customer sends own truck
- **LAKE CEMENT LTD - LOGISTICS:** LCL arranges truck (SIMBA DEVELOPERS orders)
- **GALCO LIMITED:** ESTIM CONSTRUCTION Dodoma orders (Bulker)
- **RELEVANCE INVESTMENTS LTD:** Self-delivery, Dodoma

---

## GRN (GOODS RECEIVED NOTE) INTELLIGENCE

Summary totals (Apr 2025 to Apr 2026):
```
Clinker SPG:  7,198 GRNs  (7,198 truck loads received)
Coal:         4,115 GRNs
Gypsum:       1,515 GRNs
Iron Ore:       471 GRNs
TOTAL:       13,299 truck arrivals in 12 months
```

**Average GRN rate: ~36 trucks/day inbound (all materials)**
**Average per material:**
- Clinker: ~20 trucks/day (continuous from Tanga + Mtwara)
- Coal: ~11 trucks/day (from Mbeya/Kyela, Songea)
- Gypsum: ~4 trucks/day (multiple sources)
- Iron Ore: ~1 truck/day

### Sample GRN Data (Clinker from Tanga)
```
Typical Clinker delivery (Tanga Cement PLC → Kimbiji):
  Transporter: Lake Cement Ltd - Logistics / KAIXIN / ANTU LOGISTICS
  Freight: TZS 60,000–84,000 per trip (Tanga route)
  Vehicle Types: Open (flatbed) and Tipper
  Net weight: 27.83–32.42 MT (weighbridge reading)
  Standard payload: 30 MT

Sample Coal delivery (from Mbeya):
  Transporter: Wefijojua Company Limited / Ras Logistics (T) Ltd
  Freight: TZS 135,000 per trip (Mbeya route)
  Vehicle Type: Open and Tipper
  Net weight: ~30 MT
```

---

## ROUTE CORRIDORS (CONFIRMED FROM DATA)

### Primary RM Inbound Routes (and their return paths)

```
NORTHERN CORRIDOR (Clinker — Tanga):
  TANGA → SEGERA → CHALINZE → KIMBIJI (inbound)
  Return: KIMBIJI → CHALINZE → SEGERA → TANGA
  Distance: ~360 km
  Delivery opportunities: Tanga customers (30+), Moshi customers

SOUTHERN HIGHLANDS CORRIDOR (Coal — Mbeya/Kyela):
  KYELA/MBEYA → IRINGA → MOROGORO → CHALINZE → KIMBIJI (inbound)
  Return: KIMBIJI → CHALINZE → MOROGORO → IRINGA → MBEYA/KYELA
  Distance: ~870 km (Mbeya), ~1,000 km (Kyela)
  Delivery opportunities: Mbeya customers, Iringa customers

CENTRAL CORRIDOR (Iron Ore — Dodoma):
  DODOMA → MOROGORO → CHALINZE → KIMBIJI (inbound)
  Return: KIMBIJI → CHALINZE → MOROGORO → DODOMA
  Distance: ~460 km
  Delivery opportunities: Morogoro customers, Dodoma customers

SOUTHERN COAST / RUFIJI CORRIDOR (Gypsum — Lindi):
  KIRANJERANJE(LINDI) → KIBITI → UTETE → NYAMISATI → IKWIRIRI → KIMBIJI (Route R1)
  Return: KIMBIJI → IKWIRIRI → NYAMISATI → UTETE → KIBITI → KIRANJERANJE
  Distance: ~500 km
  Delivery opportunities: Rufiji (Pwani) customers — NYAMISATI appears in SOs!

RUVUMA CORRIDOR (Coal — Songea):
  SONGEA(RUVUMA) → NJOMBE → IRINGA → MOROGORO → CHALINZE → KIMBIJI
  Return: reverse
  Distance: ~900 km

LOCAL (Gypsum — DSM-based suppliers):
  DSM → KIMBIJI
  These trucks return to DSM — match with DSM local orders
```

### The CHALINZE Junction (Critical Node)
**Chalinze (~60 km from Kimbiji) is where all routes diverge:**
- Left (A14 north): → Segera → Tanga / Moshi / Arusha
- Right (T3 west): → Morogoro → Dodoma / Mbeya / Iringa
- Coastal south: → Kibiti → Rufiji

Every return truck passes through Chalinze. **Chalinze-area delivery customers are the easiest matches** (near zero detour).

---

## ODOO 15 XML-RPC CONNECTION

```python
# Confirmed Odoo model names and key references:
ODOO_URL         = "http://odoo.lakecement.co.tz:8069"  # confirm with ERP team
ODOO_DB          = "lakecement_prod"                     # confirm with ERP team
ODOO_BUSINESS_UNIT = "TZG"

# Confirmed item codes:
RM_COAL          = "RM000001"
RM_GYPSUM        = "RM000003"
RM_IRON_ORE      = "RM000004"
RM_CLINKER_SPG   = "RM000014"

# Confirmed reference formats:
PO_PREFIX        = "LPORD"       # LPORD/YYYY/NNNNN
GRN_PREFIX       = "CM/GRN"     # CM/GRN/YYYY/NNNNN
SO_PREFIX        = "SO"         # SO/YYYY/NNNNN
SI_PREFIX        = "SI"         # SI260XXXXXXX

# Confirmed vendor code prefix: CMLT, CMLU
```

---

## DATA SEEDING INSTRUCTIONS

When running `scripts/seed_routes.py` and `scripts/seed_transporters.py`, use these files:

### Seed RouteCorridor from `Routes template26042026.xlsx` (Sheet1)
```python
# Map each row: RAW_MATERIAL + location + DISTRICT + ROUTE + DESTINATION(S) → RouteCorridor
# Route R1 is explicitly named for the Gypsum/Lindi route
# Waypoints are in DESTINATION, DESTINATION.1, DESTINATION.2, DESTINATION.3 columns
```

### Seed location distances from `location master.xlsx`
```python
# Kilometer column = road distance from Kimbiji plant (already calculated by LCL)
# Use this for route_calculator.py — MORE ACCURATE than estimates
# Type column: 'Both' = inbound + outbound eligible
```

### Seed Transporter from `Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx`
```python
# Sheet: 'Raw Material Vendor Master-Tran' — 136 RM transporters
# Fields: Code, Name, TIN, VRN, Region, Mobile, Phone, Email
# Also available in 'transporter master.xlsx' — 417 total (includes SO delivery transporters)
```

### Seed CustomerLogistics from `Customer master.xlsx`
```python
# Fields: Code, Customer/Firm/Agency Name, Location, City, Zone, Region, District
# Zone field → use ZONE_TO_CORRIDOR mapping above
# City → use city→region normalizer
```

### Historical data for algorithm training
```python
# Use 'approved sales orders...' (30,741 rows) to:
# 1. Derive average order size per customer
# 2. Map Destination Location → delivery_region
# 3. Understand transporter patterns per corridor

# Use 'RM and SFG GRN' (13,299 rows) to:
# 1. Understand typical truck arrival patterns by material
# 2. Derive avg truck capacity per transporter
# 3. Understand freight rates per route (Freight column in GRN)
```

---

## FREIGHT RATE INTELLIGENCE (from GRN data)

```
CONFIRMED FREIGHT RATES (from GRN records):
  Tanga → Kimbiji (Clinker):     TZS 60,000–84,000 per trip (~30 MT)
  Mbeya/Kyela → Kimbiji (Coal):  TZS 135,000 per trip (~30 MT)

DERIVED RATES PER TONNE:
  Tanga route:  TZS 2,000–2,800/MT
  Mbeya route:  TZS 4,500/MT

RETURN LOAD ASSUMPTION:
  Typical return rate: 50–60% of equivalent fresh outbound freight
  (Refine after first negotiation cycle with each transporter)

HOLDING COST:
  TZS 50,000/hour default (configurable via HOLD_COST_PER_HOUR_TZS env var)
```

---

## ALGORITHM CONFIGURATION (from real data)

```python
# Corridor-specific max detour tolerances
MAX_DETOUR_KM = {
    "NORTHERN":            60,   # Tanga trucks — not willing to detour far
    "SOUTHERN_HIGHLANDS": 100,   # Mbeya trucks — longer route, more flexible
    "CENTRAL":             80,   # Dodoma trucks — default
    "SOUTHERN_COAST":      50,   # Lindi/Rufiji trucks — coastal route, limited
    "RUVUMA":             120,   # Songea trucks — very long route, flexible
    "LOCAL":               40,   # DSM-area trucks — short trip, minimal detour
    "LAKE_VICTORIA":      150,   # Mwanza trucks — very long, very flexible
}

# Standard truck capacity (from GRN weighbridge data)
AVG_TRUCK_CAPACITY_TONNES = 30.0  # Most trucks: 28–33 MT
AVG_TARE_WEIGHT_TONNES = 8.0       # Estimate (Open trucks)

# PO qty to truck count
# PO for 3,000 MT Coal → 3,000 / 30 = 100 trucks over the PO period
# Must spread over PO duration, not all at once
```

---

## PROJECT STRUCTURE

```
C:\Users\USER\return trucks optimization\
│
├── CLAUDE.md                              ← This file
│
├── [DATA FILES — DO NOT MODIFY]
│   ├── transporter master.xlsx
│   ├── location master.xlsx
│   ├── Routes template26042026.xlsx
│   ├── Customer master.xlsx
│   ├── LAKE CEMENT Daily Report (1).xlsx
│   ├── approved sales orders 1st April'25 to 24th April'26.xlsx
│   ├── RM and SFG GRN and DC or DN  Details Apr 25 to Apr26.xlsx
│   └── Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx
│
├── app/
│   ├── main.py                            # FastAPI app + SSE
│   ├── config.py                          # pydantic-settings (all env vars)
│   ├── database.py                        # Async SQLAlchemy
│   ├── models/
│   │   ├── truck_schedule.py              # PO-driven inbound truck schedule
│   │   ├── cement_order.py                # Synced from Odoo sale.order
│   │   ├── allocation_proposal.py         # 3-variant proposals
│   │   ├── proposal_item.py               # Per-order allocation item
│   │   ├── matching_event.py              # Audit log
│   │   ├── transporter.py                 # Transporter master
│   │   ├── route_corridor.py              # Corridor definitions
│   │   ├── customer_logistics.py          # Customer GPS + zone
│   │   └── savings_ledger.py              # Monthly KPI ledger
│   ├── schemas/                           # Pydantic request/response
│   ├── routers/
│   │   ├── schedules.py                   # /api/schedules (incl. SSE feed + odoo-url)
│   │   ├── proposals.py                   # /api/proposals (backend only, no UI)
│   │   ├── orders.py                      # /api/orders (live-status, final-status, exports)
│   │   ├── allocations.py                 # /api/allocations (load plan management)
│   │   └── savings.py                     # /api/savings (KPI summary + by-corridor)
│   ├── services/
│   │   ├── po_scheduler.py                # ★ PO → TruckSchedule (core v2.0)
│   │   ├── matching_engine.py             # Core allocation algorithm
│   │   ├── freight_savings.py             # Savings = fresh - return - hold_cost
│   │   ├── scoring.py                     # Composite score formula
│   │   ├── route_calculator.py            # Uses location master km field!
│   │   ├── ai_advisor.py                  # Claude Sonnet (Anthropic SDK)
│   │   └── odoo_sync.py                   # XML-RPC: read PO+SO, write picking
│   ├── data/
│   │   ├── tanzania_regions.py            # Region codes + coordinates
│   │   └── route_matrix.py                # 10-region distance table
│   └── alembic/                           # DB migrations
│
├── dashboard/
│   ├── index.html                         # Schedule — inbound trucks, Allocate → Odoo
│   ├── order-status.html                  # Order Status — live SOs from Odoo
│   ├── final.html                         # Final Status — Dispatched/Released outcomes
│   └── static/
│       ├── css/nyati.css                  # Brand: #173158 navy / #F49545 orange
│       └── js/
│           ├── schedule-feed.js           # SSE client (live truck list)
│           └── api.js                     # Shared API client
│
├── scripts/
│   ├── seed_routes.py                     # From Routes template + location master
│   ├── seed_transporters.py               # From transporter master.xlsx
│   ├── seed_customers.py                  # From Customer master.xlsx
│   ├── seed_locations.py                  # From location master.xlsx (with km)
│   ├── test_odoo_connection.py
│   └── demo_allocation.py
│
├── tests/
│   ├── test_po_scheduler.py
│   ├── test_matching_engine.py
│   ├── test_freight_savings.py
│   ├── test_scoring.py
│   ├── test_route_calculator.py
│   └── test_odoo_sync.py
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## ENVIRONMENT VARIABLES

```ini
# Odoo 15
ODOO_URL=http://odoo.lakecement.co.tz:8069
ODOO_DB=lakecement_prod
ODOO_USERNAME=truck_allocator_svc
ODOO_PASSWORD=
ODOO_PICKING_TYPE_OUTGOING_ID=2
ODOO_LOCATION_STOCK_ID=8
ODOO_LOCATION_CUSTOMER_ID=5
ODOO_SYNC_INTERVAL_MINUTES=15

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# App
APP_PORT=8001
APP_SECRET_KEY=
DATABASE_URL=sqlite+aiosqlite:///./return_trucks.db

# Algorithm (tunable without redeploy)
SCORE_WEIGHT_SAVINGS=0.30
SCORE_WEIGHT_CAPACITY=0.25
SCORE_WEIGHT_ROUTE=0.25
SCORE_WEIGHT_URGENCY=0.20
DEFAULT_MAX_DETOUR_KM=80
HOLD_COST_PER_HOUR_TZS=50000
REMATCH_ALERT_THRESHOLD_TZS=200000
NEAR_READY_SCORE_PENALTY=0.70

# Odoo Item Codes
RM_COAL_CODE=RM000001
RM_GYPSUM_CODE=RM000003
RM_IRON_ORE_CODE=RM000004
RM_CLINKER_CODE=RM000014
```

---

## DEVELOPMENT QUICK START

```bash
cd "C:\Users\USER\return trucks optimization"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# DB setup
alembic upgrade head

# Seed from data files
python scripts/seed_routes.py        # Uses Routes template + location master
python scripts/seed_transporters.py  # Uses transporter master.xlsx
python scripts/seed_customers.py     # Uses Customer master.xlsx
python scripts/seed_locations.py     # Uses location master.xlsx (with km field)

# Test Odoo connection
python scripts/test_odoo_connection.py

# Run
uvicorn app.main:app --reload --port 8001
# Dashboard: http://localhost:8001
# Swagger:   http://localhost:8001/docs
```

---

## CONVENTIONS

- **Currency:** Always TZS. No USD in calculations.
- **Weight unit:** Metric Tonnes (MT). 1 tonne = 20 × 50kg bags.
- **Truck capacity:** Default 30 MT. Use GRN weighbridge data for actuals.
- **Plate format:** Tanzanian plates (T###XXX). Rwanda: RAF###X.
- **Transporter vs Supplier:** Same company can be both (e.g. Tanga Cement PLC supplies Clinker AND uses own trucks). Handle this in data model.
- **Zone system:** Use LCL's own Zone field, not just Region — Zones map to corridors more precisely.
- **Location distances:** Use `location master.xlsx` Kilometer field as primary source. More accurate than any external API.
- **GRN reference in Odoo:** Use `CM/GRN/YYYY/NNNNN` format — this is the link between PO and physical arrival.
- **Nyati Brand colors in UI:** `#173158` (Deep Navy), `#F49545` (Brand Orange), `#239557` (Brand Green).

---

## RELATED PROJECTS

| Project | Path | Notes |
|---|---|---|
| Nyati Branding Agent | `D:\new frontier\branding with cc\` | Claude agent pattern to follow |
| Nyati CRM | `C:\Users\USER\nyati-crm\` | Next.js 16, Supabase, TypeScript |
| Nyati Orders Portal | `C:\Users\USER\nyati-orders\` | Next.js 16, Prisma, SQLite |
| Nyati Website | `D:\LCLPROJECTS\lakecement-website\website-v2\nyatiwebsite\` | — |

---

*CLAUDE.md — Smart Return Truck Allocator — Lake Cement Limited*
*Updated: 2026-04-27*
