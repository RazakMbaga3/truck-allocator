# Smart Return Truck Allocator
## Odoo Integration & Report Specification
### Lake Cement Limited (Nyati Cement) — Kimbiji Plant, Tanzania

---

**Document Type:** Technical Handoff — Odoo Development Team  
**Prepared by:** Smart Return Truck Allocator Project  
**Date:** 2026-04-30  
**Version:** 1.0  
**System:** Smart Return Truck Allocator v2.1 ↔ Odoo 15 (Business Unit: TZG)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Integration Architecture](#2-integration-architecture)
3. [Implementation Progress](#3-implementation-progress)
4. [Report Specifications (13 Reports)](#4-report-specifications)
   - [Category A — Real-Time Operational (R-01 to R-04)](#category-a--real-time-operational-reports)
   - [Category B — Financial & KPI (R-05 to R-07)](#category-b--financial--kpi-reports)
   - [Category C — Odoo Integration / ERP (R-08 to R-10)](#category-c--odoo-integration--erp-reports)
   - [Category D — Audit & Compliance (R-11 to R-12)](#category-d--audit--compliance-reports)
   - [Category E — Management Analysis (R-13)](#category-e--management-analysis-reports)
5. [Odoo Custom Fields Required](#5-odoo-custom-fields-required)
6. [Odoo API Access Requirements](#6-odoo-api-access-requirements)
7. [Report Summary Matrix](#7-report-summary-matrix)
8. [Verification & Testing](#8-verification--testing)

---

## 1. Executive Summary

The **Smart Return Truck Allocator** is a standalone FastAPI service that integrates with Odoo 15 to reduce outbound cement freight costs at Kimbiji Plant. When a raw material (RM) Purchase Order is confirmed in Odoo, the system knows a truck is inbound from a specific origin (Tanga, Mbeya, Dodoma, Lindi, etc.). Instead of letting that truck return empty, the system matches it with cement delivery orders along its return corridor — before the truck arrives.

The financial engine computes:

> **Net Savings (TZS) = Fresh Outbound Freight Avoided − Return Truck Rate Paid + Holding Cost Saved**

The system generates up to three allocation variants per truck, presents them to the dispatcher via a web dashboard with AI-powered reasoning (Claude Sonnet), and writes the confirmed allocation back to Odoo as outbound `stock.picking` records.

This document specifies every report this system requires, the Odoo data fields each report consumes or produces, and the custom fields that must be added to Odoo to support the full integration.

---

## 2. Integration Architecture

### 2.1 Two-Way Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ODOO 15 (TZG BU)                           │
│                                                                     │
│  purchase.order ──────► [READ every 15 min]                        │
│  (state=purchase,        Confirmed RM POs with item codes:         │
│   RM item codes)         RM000001 COAL                             │
│                          RM000003 GYPSUM                           │
│                          RM000004 IRON ORE                         │
│                          RM000014 CLINKER                          │
│                                                                     │
│  sale.order ──────────► [READ every 15 min]                        │
│  (state=sale)            Cement delivery orders ready to dispatch  │
│                                                                     │
│  res.partner ─────────► [READ on demand]                          │
│                          Customer + transporter master data        │
│                                                                     │
│  stock.location ──────► [READ on startup]                         │
│                          Warehouse location IDs                    │
│                                                                     │
│  stock.picking ◄──────── [WRITE on proposal confirm]              │
│  stock.move    ◄──────── One picking per allocated cement order   │
│                                                                     │
│  sale.order ◄─────────── [WRITE on proposal confirm]              │
│  (x_ custom fields)      x_return_load_status, x_truck_plate,     │
│                          x_proposal_ref                            │
│                                                                     │
│  purchase.order ◄──────── [WRITE sync status]                     │
│  (x_ custom fields)       x_truck_schedule_ref                    │
└──────────────┬──────────────────────────┬──────────────────────────┘
               │  XML-RPC (port 8069)      │
               ▼                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SMART RETURN TRUCK ALLOCATOR (FastAPI, port 8001)     │
│                                                                     │
│  ┌─────────────────┐  ┌───────────────────┐  ┌──────────────────┐ │
│  │  PO Scheduler   │  │  Matching Engine  │  │   AI Advisor     │ │
│  │  PO → Schedule  │  │  11-step + Score  │  │  Claude Sonnet   │ │
│  └────────┬────────┘  └────────┬──────────┘  └────────┬─────────┘ │
│           │                    │                       │           │
│  ┌────────▼────────────────────▼───────────────────────▼─────────┐ │
│  │                     SQLite / PostgreSQL DB                    │ │
│  │  TruckSchedule · CementOrder · AllocationProposal            │ │
│  │  ProposalItem · SavingsLedger · MatchingEvent                │ │
│  │  Transporter · RouteCorridor · CustomerLogistics             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Web Dashboard (SSE Live Updates)               │   │
│  │   / (Trucks)  ·  /proposals  ·  /confirmed                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Odoo Models Consumed

| Odoo Model | Access | Purpose |
|---|---|---|
| `purchase.order` | READ | Trigger truck schedule creation on confirmed RM POs |
| `sale.order` | READ + WRITE | Sync cement delivery orders; write allocation status back |
| `sale.order.line` | READ | Get product (cement type) and quantity per SO |
| `stock.picking` | WRITE | Create outbound delivery orders for allocated cement orders |
| `stock.move` | WRITE | Line-level quantity on each outbound picking |
| `res.partner` | READ | Customer and transporter master (name, region) |
| `stock.location` | READ | Warehouse location IDs for picking creation |

### 2.3 Reference Numbers & Formats

| Document | Format Example | Odoo Model |
|---|---|---|
| Purchase Order | `LPORD/2026/00045` | `purchase.order.name` |
| Goods Received Note | `CM/GRN/2026/00021` | `stock.picking` (incoming) |
| Inward Token | `RM/2026/00009` | Custom field / picking origin |
| Gate Entry | `RM-02/04/2026-10` | Custom reference |
| Sales Order | `SO/2026/00456` | `sale.order.name` |
| Sales Invoice | `SI2600XXXXXX` | `account.move.name` |
| Truck Plate | `T810BZW` (TZ), `RAF###X` (RW) | Custom field on picking |

### 2.4 RM Item Codes (Odoo Confirmed)

| Item Code | Material | Typical Origin | Return Corridor |
|---|---|---|---|
| `RM000001` | Coal | Kyela / Mbeya / Songea | SOUTHERN_HIGHLAND / SOUTHERN |
| `RM000003` | Gypsum | Lindi / Dar es Salaam | COASTAL / LOCAL |
| `RM000004` | Iron Ore | Dodoma | CENTRAL |
| `RM000014` | Clinker SPG | Tanga / Mtwara | NORTHERN / SOUTHERN_COAST |

---

## 3. Implementation Progress

The allocator service is at **v2.1.0**, approximately 85% feature-complete. All critical business logic paths are live. The table below is provided so the Odoo team understands which integration points are ready to connect.

| Component | Status | Completion | Notes |
|---|---|---|---|
| Database Models (8 tables) | Live | 100% | TruckSchedule, CementOrder, AllocationProposal, ProposalItem, SavingsLedger, MatchingEvent, Transporter, RouteCorridor |
| API Endpoints (15+) | Live | 95% | All CRUD + SSE feed; AI-reasoning polling endpoint TBD |
| Matching Engine (11-step) | Live | 100% | 3-variant generation: MAX_SAVINGS, MAX_LOAD, URGENT_FIRST |
| Composite Scoring (4-component) | Live | 100% | Weights configurable via .env |
| Freight Savings Calculator | Live | 100% | Per-corridor rate tables, holding cost, net savings |
| Route Calculator (Floyd-Warshall) | Live | 100% | Detour analysis, LIFO stop sequencing, seasonal penalties |
| PO Scheduler | Live | 100% | Converts confirmed Odoo POs → TruckSchedule records |
| Odoo Sync (READ) | Live | 100% | PO + SO + partner + location reads every 15 min |
| Odoo Write-back (stock.picking) | Scaffolded | 80% | Basic structure in place; full error handling + rollback TBD |
| AI Advisor (Claude Sonnet) | Live | 100% | Async, non-blocking, prompt-cached |
| Background Scheduler (APScheduler) | Live | 70% | ODOO_SYNC + PRE_ARRIVAL_REMATCH live; DAILY_SAVINGS_LEDGER TBD |
| Dashboard — Available Trucks | Live | 100% | SSE real-time, KPI header, sync controls |
| Dashboard — Proposals | Live | 100% | 3-variant cards, AI reasoning async panel |
| Dashboard — Confirmed | Scaffolded | 5% | Placeholder only; needs implementation |
| Authentication (API Key) | Live | 95% | Infrastructure ready; not yet enforced on all endpoints |
| Data Seeding Scripts | Live | 100% | All 4 Excel masters: transporters, locations, routes, customers |
| Unit Test Suite | Live | 85% | Matching, scoring, freight, routes fully tested |

### Known Gaps (Odoo Team Action Required)

1. **Custom fields not yet in Odoo** — six `x_` fields listed in Section 5 must be created before full write-back can be tested.
2. **Service account `truck_allocator_svc`** — must be created in Odoo with permissions listed in Section 6.
3. **Odoo static IDs to confirm** — `ODOO_PICKING_TYPE_OUTGOING_ID`, `ODOO_LOCATION_STOCK_ID`, `ODOO_LOCATION_CUSTOMER_ID` must be verified against the production database (current defaults: 2, 8, 5).

---

## 4. Report Specifications

---

### Category A — Real-Time Operational Reports

---

#### R-01: Available Trucks Pending Allocation

| Attribute | Detail |
|---|---|
| **Report ID** | R-01 |
| **Report Name** | Available Trucks Pending Allocation |
| **Purpose** | Show dispatchers every inbound RM truck that is expected or pre-confirmed but not yet matched with cement orders, so they can monitor allocation urgency and intervene if the algorithm has not produced proposals. |
| **Category** | Real-Time Operational |
| **Update Frequency** | Live (Server-Sent Events from `/api/schedules/feed`) |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Logistics Dispatcher | Full — view and act (confirm details, trigger rematch) |
| Transport Manager | Read-only |
| Odoo Administrator | Read-only via Odoo list view |

**Data Source**

Primary table: `TruckSchedule`  
Filter condition: `status IN ('EXPECTED', 'PRE_CONFIRMED') AND allocation_status != 'CONFIRMED'`  
Joins: `Transporter` (name, contact), `RouteCorridor` (display_name, waypoints)

**Output Fields**

| Field | Source Column | Description |
|---|---|---|
| Schedule Ref | `schedule_ref` | e.g., SCHED-20260430-001 |
| Odoo PO Number | `odoo_po_name` | e.g., LPORD/2026/00045 |
| ETA | `expected_arrival_dt` | Expected plant arrival (UTC+3) |
| Transporter | `Transporter.name` | Haulier name |
| Origin Region | `origin_region` | e.g., TANGA, MBEYA, DODOMA |
| Raw Material | `raw_material_type` | CLINKER / COAL / GYPSUM / IRON_ORE |
| Corridor | `corridor_name` | Return route identifier |
| Est. Capacity (MT) | `estimated_qty_tonnes` | Tonnes available for return load |
| Truck Plate | `truck_plate` | Populated after transporter pre-advice; blank if unknown |
| Schedule Status | `status` | EXPECTED or PRE_CONFIRMED |
| Allocation Status | `allocation_status` | UNMATCHED / PROPOSED |
| Hours to Arrival | Computed | `expected_arrival_dt − now()` |

**Filters & Grouping**

| Filter | Type | Values |
|---|---|---|
| Corridor | Multi-select | NORTHERN, CENTRAL, SOUTHERN_HIGHLAND, COASTAL, LAKE, SOUTHERN, LOCAL |
| Raw Material | Multi-select | CLINKER, COAL, GYPSUM, IRON_ORE |
| ETA Range | Date-time range | From / To |
| Status | Single-select | EXPECTED, PRE_CONFIRMED, or All |
| Arriving within 24h | Toggle | Highlights rows where hours_to_arrival ≤ 24 |

**Business Logic & Calculations**

- A truck is shown as "available" until `allocation_status = CONFIRMED` — the moment a dispatcher confirms a proposal, the truck disappears from this list and an SSE event (`truck_allocated`) is broadcast to all connected browsers.
- `estimated_qty_tonnes` is derived from the Odoo PO line quantity divided by `AVG_TRUCK_CAPACITY_TONNES` (default 30 MT). If `actual_capacity_tonnes` is provided by transporter pre-advice, that value takes precedence.
- Rows where `truck_plate` is blank and ETA < 6h should be highlighted in amber (transporter has not confirmed truck details yet).
- Count of trucks per corridor is displayed in a summary row at the top of each corridor group.

**Output Format**

- **Primary:** Live sortable table on allocator dashboard (`/` route), updated via SSE.
- **Export:** CSV downloadable on demand via `GET /api/schedules?status=available&format=csv`.
- **Odoo Integration:** Odoo list view on `purchase.order` showing a custom smart button "Return Load Status" (badge count = trucks not yet allocated). Clicking opens allocator dashboard in embedded iframe or external tab. No Odoo write required for this view.

---

#### R-02: Pending Allocation Proposals

| Attribute | Detail |
|---|---|
| **Report ID** | R-02 |
| **Report Name** | Pending Allocation Proposals |
| **Purpose** | Present the three matching variants generated for each inbound truck, with AI reasoning, so the dispatcher can make an informed decision on which allocation to confirm. |
| **Category** | Real-Time Operational |
| **Update Frequency** | Refreshed on each match run; AI reasoning populates asynchronously (typically 3–8 seconds after proposals appear). |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Logistics Dispatcher | Full — view, confirm, or reject |
| Transport Manager | Read-only |

**Data Source**

Primary table: `AllocationProposal` (status = PROPOSED)  
Joins: `ProposalItem` → `CementOrder`, `TruckSchedule`, `Transporter`

**Output Fields — Proposal Header**

| Field | Source Column | Description |
|---|---|---|
| Proposal Ref | `proposal_ref` | e.g., PROP-20260430-001-A |
| Variant | `variant_type` | MAX_SAVINGS / MAX_LOAD / URGENT_FIRST |
| Schedule Ref | `schedule_ref` | Links back to TruckSchedule |
| Truck Plate | `TruckSchedule.truck_plate` | Blank if not yet confirmed by transporter |
| Corridor | `TruckSchedule.corridor_name` | Return corridor |
| Estimated Savings | `estimated_savings_tzs` | Net TZS saved vs. fresh truck |
| Capacity Utilization | `capacity_utilization_pct` | Percentage of truck capacity filled (0–100%) |
| Number of Stops | `number_of_stops` | Count of delivery orders in proposal |
| Route Deviation | `total_route_deviation_km` | Total extra km vs. direct return |
| Holding Cost | `holding_cost_tzs` | TZS cost of orders waiting for this truck |
| Composite Score | `composite_score` | 0.00–1.00 (algorithm ranking) |
| AI Recommendation | `ai_recommendation` | CONFIRM / REVIEW / HOLD |
| AI Reasoning | `ai_reasoning` | 2–4 sentence narrative |
| AI Warnings | `ai_warnings` | JSON array of risk flags (e.g., "Coastal route — rainy season risk") |
| Pending Readiness | `has_pending_readiness_orders` | True if any order not yet dispatch_ready |
| Pending Note | `pending_readiness_note` | Detail on which orders are near-ready only |
| Created At | `created_at` | When proposals were generated |

**Output Fields — Per-Order Line (ProposalItem)**

| Field | Source | Description |
|---|---|---|
| SO Number | `CementOrder.odoo_order_name` | e.g., SO/2026/00456 |
| Customer | `CementOrder.customer_name` | Delivery recipient |
| Delivery Region | `CementOrder.delivery_region` | Region of destination |
| Distance (km) | `CementOrder.distance_from_plant_km` | From location master |
| Allocated Tonnes | `ProposalItem.allocated_tonnes` | MT on this proposal |
| Allocated Bags | `ProposalItem.allocated_bags` | 50 kg bags (1 MT = 20 bags) |
| Sequence | `ProposalItem.sequence` | Load order (1 = deliver first, load last — LIFO) |
| Detour (km) | `ProposalItem.delivery_deviation_km` | Extra km for this stop |
| Item Savings | `ProposalItem.item_savings_tzs` | Savings attributed to this order |
| Near-Ready | `ProposalItem.is_near_ready` | True = not yet dispatch_ready but expected before truck ETA |

**Filters & Grouping**

| Filter | Type | Values |
|---|---|---|
| Schedule / Truck | Single-select | Filter to proposals for one truck |
| Variant Type | Multi-select | MAX_SAVINGS, MAX_LOAD, URGENT_FIRST |
| AI Recommendation | Multi-select | CONFIRM, REVIEW, HOLD |
| Date Range | Date range | Proposals created between dates |
| Corridor | Multi-select | All corridors |

**Composite Score Formula**

```
Score = (0.30 × savings_score)
      + (0.25 × capacity_score)
      + (0.25 × route_score)
      + (0.20 × urgency_score)
```

Weights are configurable via `.env` variables (`SCORE_WEIGHT_SAVINGS`, etc.).

**Output Format**

- **Primary:** Card-based layout on allocator dashboard (`/proposals`). Three cards side-by-side per truck, with AI panel below the recommended card.
- **List View:** Scrollable table for all pending proposals across all trucks (`/proposals` no query param).
- **Odoo Integration:** On proposal confirmation, the allocator calls Odoo to create a `stock.picking` batch. No native Odoo view for proposals — the allocator dashboard is the authoritative UI.

---

#### R-03: Confirmed Allocations (Today / This Week)

| Attribute | Detail |
|---|---|
| **Report ID** | R-03 |
| **Report Name** | Confirmed Allocations |
| **Purpose** | Show all trucks where a dispatcher has confirmed an allocation proposal, including the linked Odoo delivery orders (stock.picking IDs) and the savings locked in. |
| **Category** | Real-Time Operational |
| **Update Frequency** | Live (SSE event `truck_allocated` updates dashboard immediately on confirm). |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Logistics Dispatcher | Full |
| Warehouse Manager | Read-only (to prepare cement loading sequence) |
| Operations Manager | Read-only |
| Odoo Administrator | Read-only (via stock.picking in Odoo) |

**Data Source**

Primary table: `AllocationProposal` (status IN CONFIRMED, DISPATCHED)  
Joins: `TruckSchedule`, `Transporter`, `ProposalItem`, `CementOrder`

**Output Fields**

| Field | Source | Description |
|---|---|---|
| Proposal Ref | `proposal_ref` | Confirmed proposal reference |
| Truck Plate | `TruckSchedule.truck_plate` | Physical truck plate |
| Transporter | `Transporter.name` | Haulier |
| Corridor | `TruckSchedule.corridor_name` | Return corridor |
| Raw Material | `TruckSchedule.raw_material_type` | What the truck brought in |
| Orders Count | `number_of_orders` | Cement orders on this truck |
| Total Tonnes | `total_allocated_tonnes` | MT of cement loaded |
| Utilization | `capacity_utilization_pct` | % of truck capacity used |
| Net Savings | `estimated_savings_tzs` | TZS saved on this trip |
| Confirmed By | `confirmed_by` | Dispatcher name |
| Confirmed At | `confirmed_at` | Confirmation timestamp |
| Dispatched At | `dispatched_at` | When truck left plant (if done) |
| Status | `status` | CONFIRMED or DISPATCHED |
| Odoo Pickings | `_odoo_picking_ids` | Comma-separated list of stock.picking IDs |

**Filters & Grouping**

| Filter | Type |
|---|---|
| Date Range (Confirmed At) | Date range |
| Corridor | Multi-select |
| Transporter | Multi-select |
| Status | CONFIRMED / DISPATCHED / All |
| Group by Corridor | Toggle |
| Group by Transporter | Toggle |

**Business Logic**

- A confirmed allocation is locked. The cement orders in it are marked `ALLOCATED` in `CementOrder`. The truck is marked `allocation_status = CONFIRMED` and no longer appears on R-01.
- The LIFO sequence from `ProposalItem.sequence` is the loading order: the warehouse team should load sequence-1 orders last (they deliver first).
- When the truck is physically dispatched, the dispatcher updates status to DISPATCHED, which writes a `SavingsLedger` entry and contributes to the MTD KPI.

**Output Format**

- **Primary:** Table on allocator dashboard (`/confirmed` — currently scaffolded, to be implemented).
- **Export:** CSV with all fields including Odoo picking IDs.
- **Odoo Integration:** Each `stock.picking` created by the allocator has `origin` set to the `proposal_ref` (prefixed `ALLOC-`). The Odoo warehouse team can filter `stock.picking` by origin `ilike ALLOC-%` to see all allocator-driven deliveries. Picking state progresses normally in Odoo.

---

#### R-04: Unallocated Orders Backlog

| Attribute | Detail |
|---|---|
| **Report ID** | R-04 |
| **Report Name** | Unallocated Orders Backlog |
| **Purpose** | Flag cement orders that are eligible for return-load allocation but have not yet been matched to any truck. Helps dispatchers identify orders at risk of missing their deadline or holding inventory unnecessarily. |
| **Category** | Real-Time Operational |
| **Update Frequency** | Refreshed every Odoo sync cycle (15 min); urgency scores updated hourly. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Logistics Dispatcher | Full |
| Sales Coordinator | Read-only (own orders) |
| Customer Service | Read-only |

**Data Source**

Primary table: `CementOrder`  
Filter: `allocation_status = 'UNALLOCATED' AND dispatch_ready = TRUE AND credit_cleared = TRUE AND return_load_eligible = TRUE`  
Also include: `near_ready = TRUE` orders (not yet dispatch_ready but expected before next truck ETA)

**Output Fields**

| Field | Source | Description |
|---|---|---|
| SO Number | `odoo_order_name` | Odoo SO reference |
| Customer | `customer_name` | Delivery recipient |
| Delivery Corridor | `delivery_corridor` | Which return route serves this customer |
| Delivery Region | `delivery_region` | Geographic region |
| Distance (km) | `distance_from_plant_km` | From location master |
| Qty (MT) | `quantity_tonnes` | Cement to deliver |
| Qty (Bags) | `quantity_bags` | 50 kg bags |
| Product | `product_name` | Cement grade |
| Requested Delivery | `requested_delivery_dt` | Customer's desired delivery date |
| Deadline | `deadline_dt` | Latest acceptable delivery |
| Urgency Score | `urgency_score` | 0–10, recalculated hourly |
| Days Unallocated | Computed | `today − created_at` |
| Near-Ready | `near_ready` | True = not dispatch_ready but expected soon |
| Near-Ready ETA | `near_ready_eta` | When order is expected to clear dispatch_ready |
| Fresh Freight (TZS) | `fresh_outbound_freight_tzs` | Cost if sent by dedicated fresh truck |

**Filters & Grouping**

| Filter | Type | Notes |
|---|---|---|
| Corridor | Multi-select | Show orders per return corridor |
| Urgency Score | Range | e.g., show only urgency ≥ 7 |
| Days Unallocated | Min threshold | e.g., stuck > 3 days |
| Near-Ready Only | Toggle | Show orders approaching readiness |
| Deadline within N days | Number input | Highlight imminent deadlines |
| Group by Corridor | Toggle | Useful to match against R-01 |

**Business Logic**

- `urgency_score` is a value 0–10 computed from time remaining to `deadline_dt`:
  - Past deadline: 10.0
  - < 24h: 9.5 · < 48h: 8.0 · < 72h: 6.5 · < 120h: 5.0 · < 168h: 3.5 · < 336h: 2.0 · > 336h: 1.0
  - No deadline: 3.0 (default moderate urgency)
  - Near-ready penalty: score × 0.70 (discounted until dispatch_ready)
- This report serves as the "demand side" companion to R-01's "supply side". A dispatcher comparing R-01 (arriving trucks) with R-04 (unallocated orders) by corridor quickly sees matching opportunities.

**Output Format**

- **Primary:** Dashboard widget on allocator index page, showing count by corridor with drill-down.
- **Export:** CSV on demand.
- **Odoo Integration:** `sale.order.x_return_load_status` (custom field — see Section 5) will show `unallocated` for all orders in this report. Sales team can filter this field in Odoo's SO list view to see which orders are not yet matched.

---

### Category B — Financial & KPI Reports

---

#### R-05: Monthly Freight Savings Summary (MTD)

| Attribute | Detail |
|---|---|
| **Report ID** | R-05 |
| **Report Name** | Monthly Freight Savings Summary (MTD) |
| **Purpose** | Top-level KPI report showing the total net TZS saved through the return load programme in the current month. The headline number for management and finance. |
| **Category** | Financial & KPI |
| **Update Frequency** | Real-time as proposals are dispatched; month key resets on the 1st of each month. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Transport Manager | Full |
| Finance Manager | Read-only |
| CEO / Management | Read-only (summary only) |

**Data Source**

Primary table: `SavingsLedger`  
Filter: `month_key = YYYY-MM` (current period)  
Aggregation: SUM across all rows in the filtered period

**Output Fields**

| KPI | Calculation | Description |
|---|---|---|
| Net Savings (TZS) | `SUM(net_savings_tzs)` | Total benefit of the programme |
| Fresh Freight Avoided (TZS) | `SUM(fresh_freight_avoided_tzs)` | What would have been paid for fresh trucks |
| Return Freight Paid (TZS) | `SUM(return_freight_paid_tzs)` | What was actually paid for return trucks |
| Holding Cost Saved (TZS) | `SUM(holding_cost_saved_tzs)` | Warehouse/working-capital cost avoided |
| Trips Completed | `COUNT(*)` | Number of return-load trucks dispatched |
| Orders Delivered | `SUM(number_of_orders)` | Cement orders fulfilled via return load |
| Tonnes Delivered | `SUM(allocated_tonnes)` | MT of cement on return trucks |
| Avg Utilization | `AVG(capacity_utilization_pct)` | Mean truck fill rate (%) |
| Avg Savings / Trip | `SUM(net_savings_tzs) / COUNT(*)` | Per-trip value |
| Trucks Expected (next 7d) | Sub-query on TruckSchedule | Forward-looking demand |
| Unallocated Orders | Sub-query on CementOrder | Current backlog count |

**Filters**

| Filter | Type |
|---|---|
| Month Key | YYYY-MM picker (default: current month) |
| Date Range | Override: custom from/to date |
| Corridor | Multi-select (optional sub-filter) |
| Origin Region | Multi-select (optional sub-filter) |

**Business Logic & Calculations**

Savings formula per trip (from `SavingsLedger`):
```
net_savings_tzs = fresh_freight_avoided_tzs − return_freight_paid_tzs + holding_cost_saved_tzs
```

Fresh freight rate table used (TZS per km per tonne):

| Corridor | Rate (TZS/km/MT) |
|---|---|
| NORTHERN | 210 |
| CENTRAL | 200 |
| SOUTHERN_HIGHLAND | 200 |
| COASTAL | 220 |
| LAKE | 190 |
| SOUTHERN | 200 |
| LOCAL | 80 |

Return truck rate: `fresh_freight × 0.60` (transporter accepts 60% of fresh rate for loaded return vs. empty).  
Holding cost: `hold_hours × (50,000 TZS / 30 MT) × quantity_tonnes` (hold cost configurable via `HOLD_COST_PER_HOUR_TZS`).

**Output Format**

- **Primary:** KPI header row on allocator dashboard (4 headline cards: Net Savings, Trips, Orders, Avg Utilization).
- **Full Detail:** Expandable panel or `/api/savings/summary?month=2026-04` API endpoint.
- **Export:** CSV / PDF for finance reporting.
- **Odoo Integration:** Monthly total can be pushed to a custom Odoo model `x.freight.savings.summary` for inclusion in management accounting reports. Push triggered by end-of-month `DAILY_SAVINGS_LEDGER` scheduler job.

---

#### R-06: Savings by Corridor

| Attribute | Detail |
|---|---|
| **Report ID** | R-06 |
| **Report Name** | Freight Savings by Return Corridor |
| **Purpose** | Break down the programme's financial performance by return corridor. Shows which routes generate the most savings and helps management prioritise transporter relationships and order scheduling by corridor. |
| **Category** | Financial & KPI |
| **Update Frequency** | Refreshed on each truck dispatch; monthly summary on demand. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Transport Manager | Full |
| Operations Analyst | Full |
| Procurement | Read-only |

**Data Source**

Primary table: `SavingsLedger` grouped by `corridor_name`  
Join: `RouteCorridor` for display name and metadata

**Output Fields**

| Field | Calculation | Description |
|---|---|---|
| Corridor | `corridor_name` | Return corridor identifier |
| Display Name | `RouteCorridor.display_name` | Human-readable name |
| Trips | `COUNT(*)` | Number of return-load dispatches |
| Total Tonnes | `SUM(allocated_tonnes)` | MT delivered via this corridor |
| Net Savings (TZS) | `SUM(net_savings_tzs)` | Total savings this corridor |
| Avg Savings / Trip | `SUM / COUNT` | Per-trip average |
| Avg Utilization | `AVG(capacity_utilization_pct)` | Mean fill rate |
| Best Trip Savings | `MAX(net_savings_tzs)` | Single best trip on this corridor |
| % of Total Savings | Computed | Corridor share of programme total |

**Filters**

| Filter | Type |
|---|---|
| Month Key | YYYY-MM |
| Date Range | Custom from/to |
| Corridor | Multi-select |

**Business Logic**

- Corridors without any dispatched trips in the period still appear in the table with zero values (to highlight underperforming corridors).
- Sorting default: NET_SAVINGS DESC.
- COASTAL corridor includes a seasonal note when querying March–May (rainy season; 20% rate premium applied, fewer trips expected).

**Output Format**

- **Primary:** Bar chart + sortable table on `/api/savings/by-corridor`.
- **Export:** CSV.
- **Odoo Integration:** Optional — can be included in a custom Odoo financial pivot view if the Odoo team creates the `x.freight.savings.summary` model with `corridor_name` as a dimension field.

---

#### R-07: Savings by Transporter

| Attribute | Detail |
|---|---|
| **Report ID** | R-07 |
| **Report Name** | Freight Savings by Transporter |
| **Purpose** | Rank individual transport companies by their contribution to the return load programme. Supports procurement negotiations (which transporters deliver the most value?) and reliability scoring. |
| **Category** | Financial & KPI |
| **Update Frequency** | Refreshed on each truck dispatch. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Transport Manager | Full |
| Procurement Manager | Full |

**Data Source**

Primary table: `SavingsLedger` grouped by `transporter_name`  
Join: `Transporter` via `transporter_name` for `odoo_vendor_code`, `origin_region`, `reliability_score`

**Output Fields**

| Field | Calculation | Description |
|---|---|---|
| Transporter Name | `transporter_name` | Company name |
| Odoo Vendor Code | `Transporter.odoo_vendor_code` | e.g., CMLT2307 |
| Origin Region | `Transporter.origin_region` | Typical RM origin |
| Trips | `COUNT(*)` | Return-load trips completed |
| Total Tonnes | `SUM(allocated_tonnes)` | MT delivered |
| Net Savings (TZS) | `SUM(net_savings_tzs)` | Total savings generated |
| Avg Savings / Trip | `SUM / COUNT` | Per-trip efficiency |
| Avg Utilization | `AVG(capacity_utilization_pct)` | Fill rate |
| Reliability Score | `Transporter.reliability_score` | 0–10, from transporter master |

**Filters**

| Filter | Type |
|---|---|
| Month Key | YYYY-MM |
| Date Range | Custom |
| Corridor / Origin Region | Multi-select |

**Output Format**

- **Primary:** Ranked table (sortable) on allocator analytics page.
- **Export:** CSV.
- **Odoo Integration:** `odoo_vendor_code` maps directly to `res.partner` (vendor). The Odoo team can add a smart button on the vendor form showing this transporter's return-load statistics, pulling from the allocator API via `GET /api/savings/by-transporter?vendor_code=CMLT2307`.

---

### Category C — Odoo Integration / ERP Reports

---

#### R-08: RM Purchase Order → Truck Schedule Sync Log

| Attribute | Detail |
|---|---|
| **Report ID** | R-08 |
| **Report Name** | RM PO → Truck Schedule Sync Log |
| **Purpose** | Provide a reconciliation view showing which Odoo RM Purchase Orders have been ingested by the allocator and converted into TruckSchedule records. Flags sync failures and missing conversions so the ERP and logistics teams can investigate discrepancies. |
| **Category** | Odoo Integration / ERP |
| **Update Frequency** | Updated every 15 minutes by the ODOO_SYNC background job. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| ERP Administrator | Full |
| Logistics Manager | Read-only |
| IT Support | Full |

**Data Source**

Primary table: `TruckSchedule` (columns: `odoo_po_name`, `odoo_po_id`, `raw_material_type`, `origin_region`, `estimated_truck_count`, `created_at`)  
Join: `MatchingEvent` (triggered_by = PO_SYNC, linked via `schedule_id`)

**Output Fields**

| Field | Source | Description |
|---|---|---|
| Odoo PO Number | `odoo_po_name` | e.g., LPORD/2026/00045 |
| PO Date | `TruckSchedule.created_at` | Approx. sync timestamp |
| Vendor Code | Derived from Odoo sync | Supplier code (e.g., CMLT2146) |
| Raw Material | `raw_material_type` | Item code mapped to material name |
| Estimated Trucks | `estimated_truck_count` | Derived from PO qty ÷ 30 MT |
| Schedule Refs | `schedule_ref` (list) | TruckSchedule records created |
| Sync Timestamp | `MatchingEvent.created_at` | When sync ran |
| Matching Triggered | `MatchingEvent.proposals_generated > 0` | Boolean |
| Proposals Generated | `MatchingEvent.proposals_generated` | Count |
| Top Savings (TZS) | `MatchingEvent.top_savings_tzs` | Best savings found |
| Error Flag | `MatchingEvent.error_message IS NOT NULL` | True if sync had errors |
| Error Message | `MatchingEvent.error_message` | Error detail if any |

**Filters**

| Filter | Type |
|---|---|
| Date Range (PO Date) | Date range |
| Raw Material | Multi-select |
| Error Flag | Toggle (show only errors) |
| Sync Status | Synced / Missing / Error |

**Business Logic**

- Every `purchase.order` in Odoo with `state = 'purchase'` and an RM item code (`RM000001`, `RM000003`, `RM000004`, `RM000014`) should appear here.
- A "missing" row indicates the PO exists in Odoo but the sync has not yet ingested it — could mean the sync job is lagging, or the vendor code is not in the `Transporter` master.
- The `x_origin_region` custom field on `purchase.order` (see Section 5) overrides the material-default origin. If this field is blank, the system uses the material default:

| Material | Default Origin |
|---|---|
| CLINKER | TANGA |
| COAL | MBEYA |
| GYPSUM | KIRANJERANJE |
| IRON_ORE | DODOMA |

**Odoo Fields Required (READ)**

| Odoo Field | Type | Notes |
|---|---|---|
| `purchase.order.name` | Char | PO reference number |
| `purchase.order.state` | Selection | Filter: `state = 'purchase'` |
| `purchase.order.partner_id` | Many2one | Supplier (mapped to Transporter) |
| `purchase.order.scheduled_date` | Datetime | Expected delivery date → truck ETA |
| `purchase.order.order_line.product_id` | Many2one | RM item code |
| `purchase.order.order_line.product_qty` | Float | Total qty (MT) → truck count |
| `purchase.order.x_origin_region` | Char | **NEW FIELD** — origin override |

**Odoo Fields Written (WRITE)**

| Odoo Field | Type | Written When |
|---|---|---|
| `purchase.order.x_truck_schedule_ref` | Char | After TruckSchedule created; comma-separated if multiple |

**Output Format**

- **Allocator:** Admin table at `/api/schedules?show_sync_log=true` (to be implemented).
- **Odoo:** Custom list view on `purchase.order` with a computed "Sync Status" widget that calls the allocator API to show a badge (Synced ✓ / Pending ⏳ / Error ✗). Can be implemented as an Odoo JS widget reading `x_truck_schedule_ref`.

---

#### R-09: Sale Order Allocation Status Report

| Attribute | Detail |
|---|---|
| **Report ID** | R-09 |
| **Report Name** | Sale Order — Return Load Allocation Status |
| **Purpose** | Show every cement sale order and its current allocation status within the return load programme. Enables the sales team to answer "has my customer's order been allocated to a return truck?" and gives dispatchers visibility across the full SO pipeline. |
| **Category** | Odoo Integration / ERP |
| **Update Frequency** | Updated on every Odoo sync (15 min) and on every allocation event (real-time). |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Sales Team | Read-only (via Odoo SO list view) |
| Customer Service | Read-only (own orders) |
| Logistics Dispatcher | Full |
| Operations Manager | Read-only |

**Data Source**

Primary table: `CementOrder` (all records)  
Join: `AllocationProposal` (if `allocation_status` ≠ UNALLOCATED), `TruckSchedule`

**Output Fields**

| Field | Source | Description |
|---|---|---|
| SO Number | `odoo_order_name` | e.g., SO/2026/00456 |
| Customer | `customer_name` | Delivery recipient |
| Delivery Region | `delivery_region` | Geographic region |
| Delivery Corridor | `delivery_corridor` | Return route serving this order |
| Distance (km) | `distance_from_plant_km` | From plant to destination |
| Qty (MT) | `quantity_tonnes` | Cement ordered |
| Product | `product_name` | Cement grade (SUPER 42, MAX 32, DURAMAX 42, PREMIUM OPC) |
| Allocation Status | `allocation_status` | UNALLOCATED / CANDIDATE / SOFT_RESERVED / ALLOCATED / DELIVERED |
| Proposal Ref | `AllocationProposal.proposal_ref` | Linked proposal (if allocated) |
| Truck Plate | `TruckSchedule.truck_plate` | Truck assigned (if confirmed) |
| Origin Region | `TruckSchedule.origin_region` | Where truck came from |
| Est. Dispatch Date | `TruckSchedule.expected_arrival_dt` | Approx. dispatch date for this truck |
| Odoo Picking ID | `ProposalItem.odoo_picking_id` | Outbound picking in Odoo (if created) |
| Dispatch Ready | `dispatch_ready` | Boolean — order cleared for dispatch |
| Credit Cleared | `credit_cleared` | Boolean — finance cleared |
| Near-Ready | `near_ready` | Approaching readiness |

**Allocation Status Enum**

| Status | Meaning |
|---|---|
| UNALLOCATED | Not yet matched to any truck |
| CANDIDATE | Currently being evaluated by matching engine |
| SOFT_RESERVED | Included in a PROPOSED proposal (not confirmed yet) |
| ALLOCATED | Proposal confirmed; Odoo picking created |
| DELIVERED | Truck dispatched; savings ledger entry written |

**Filters**

| Filter | Type |
|---|---|
| Allocation Status | Multi-select |
| Delivery Corridor | Multi-select |
| Date Range (SO Date) | Date range |
| Customer | Search |
| Dispatch Ready | Toggle |
| Credit Cleared | Toggle |

**Odoo Write-Back Fields**

When a proposal is confirmed, the allocator writes back to `sale.order`:

| Custom Field | Type | Value Written |
|---|---|---|
| `x_return_load_status` | Selection | unallocated / candidate / soft_reserved / allocated / delivered |
| `x_truck_plate` | Char | Truck plate number (e.g., T810BZW) |
| `x_proposal_ref` | Char | Proposal reference (e.g., PROP-20260430-001-A) |

**Output Format**

- **Allocator:** Table at `GET /api/orders` and `GET /api/orders/by-corridor/{name}`.
- **Odoo:** Standard `sale.order` list view with custom columns for `x_return_load_status`, `x_truck_plate`, `x_proposal_ref`. The Odoo team should add these as optional columns or a dedicated "Return Load" tab on the SO form view.
- **Export:** CSV from either system.

---

#### R-10: Stock Picking Write-Back Report

| Attribute | Detail |
|---|---|
| **Report ID** | R-10 |
| **Report Name** | Allocator-Created Stock Pickings (Write-Back Audit) |
| **Purpose** | Audit trail of all outbound `stock.picking` records created in Odoo by the allocator. Reconciles the allocator's confirmed proposals with Odoo's warehouse operations. |
| **Category** | Odoo Integration / ERP |
| **Update Frequency** | Updated each time a proposal is confirmed. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Warehouse Manager | Full (to validate loading plan) |
| ERP Administrator | Full |
| Logistics Dispatcher | Read-only |

**Data Source**

Primary table: `ProposalItem` (columns: `odoo_picking_id`, `allocated_tonnes`, `allocated_bags`, `sequence`)  
Join: `AllocationProposal`, `TruckSchedule`, `CementOrder`

**Output Fields**

| Field | Source | Description |
|---|---|---|
| Odoo Picking ID | `odoo_picking_id` | stock.picking primary key in Odoo |
| Odoo Picking Name | Retrieved from Odoo | e.g., WH/OUT/00456 |
| Proposal Ref | `AllocationProposal.proposal_ref` | Originating proposal |
| SO Number | `CementOrder.odoo_order_name` | Source sale order |
| Customer | `CementOrder.customer_name` | Delivery recipient |
| Delivery Address | `CementOrder.delivery_address` | Full destination |
| Allocated (MT) | `ProposalItem.allocated_tonnes` | MT on this picking |
| Allocated (Bags) | `ProposalItem.allocated_bags` | 50 kg bags |
| Load Sequence | `ProposalItem.sequence` | LIFO order (1 = deliver first) |
| Truck Plate | `TruckSchedule.truck_plate` | Physical truck |
| Corridor | `TruckSchedule.corridor_name` | Return corridor |
| Picking State | Retrieved from Odoo | draft / confirmed / assigned / done |
| Created At | `ProposalItem.created_at` | When allocator created the picking |

**Odoo Fields Used**

| Odoo Field | Value Set by Allocator |
|---|---|
| `stock.picking.picking_type_id` | `ODOO_PICKING_TYPE_OUTGOING_ID` (default: 2) |
| `stock.picking.location_id` | `ODOO_LOCATION_STOCK_ID` (default: 8) |
| `stock.picking.location_dest_id` | `ODOO_LOCATION_CUSTOMER_ID` (default: 5) |
| `stock.picking.origin` | `ALLOC-{proposal_ref}` |
| `stock.picking.partner_id` | Customer's `res.partner` ID |
| `stock.picking.scheduled_date` | `TruckSchedule.expected_arrival_dt` |
| `stock.move.product_id` | Cement product ID from `CementOrder` |
| `stock.move.product_uom_qty` | `allocated_tonnes` |

**Filters**

| Filter | Type |
|---|---|
| Date Range (Created At) | Date range |
| Picking State | Multi-select |
| Corridor | Multi-select |
| Proposal Ref | Search |

**Business Logic**

- All allocator-created pickings have `origin` set to `ALLOC-{proposal_ref}`. The Odoo team can create a saved filter on `stock.picking` list view: `origin ilike ALLOC-%` to see all allocator-driven pickings.
- If Odoo picking creation fails (network error, validation error), the error is logged in `MatchingEvent.error_message` and the allocator retries on the next sync. The proposal remains CONFIRMED in the allocator even if the Odoo write-back is pending.
- The `sequence` / LIFO loading order must be communicated to the warehouse loading team via this report — it determines in what order bags are loaded onto the truck.

**Output Format**

- **Allocator:** Table at admin endpoint (to be implemented: `GET /api/proposals/{id}/pickings`).
- **Odoo:** Standard `stock.picking` list view filtered by `origin ilike ALLOC-%`. No custom model needed — uses standard Odoo picking UI.
- **Reconciliation:** The ERP team should run a weekly reconciliation comparing `ProposalItem.odoo_picking_id` values against `stock.picking` records to catch any orphaned or missing entries.

---

### Category D — Audit & Compliance Reports

---

#### R-11: Matching Engine Audit Log

| Attribute | Detail |
|---|---|
| **Report ID** | R-11 |
| **Report Name** | Matching Engine Audit Log |
| **Purpose** | Full audit trail of every execution of the matching algorithm — when it ran, what triggered it, how many orders it evaluated, and whether it raised any performance or savings-delta alerts. Used for system monitoring, troubleshooting, and compliance. |
| **Category** | Audit & Compliance |
| **Update Frequency** | Written on every match run. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| System Administrator | Full |
| Operations Manager | Read-only |
| IT Support | Full |

**Data Source**

Primary table: `MatchingEvent` (all records)

**Output Fields**

| Field | Source | Description |
|---|---|---|
| Event ID | `id` | Auto-increment primary key |
| Schedule Ref | `schedule_ref` | Which truck this match was for |
| Triggered By | `triggered_by` | PO_SYNC / SO_CHANGE / MANUAL / CRON / REMATCH |
| Orders Evaluated | `orders_evaluated` | Total CementOrders considered |
| Orders Qualified | `orders_qualified` | Orders passing all filters |
| Proposals Generated | `proposals_generated` | Variants created (0–3) |
| Top Savings (TZS) | `top_savings_tzs` | Best net savings in this run |
| Top Utilization | `top_utilization_pct` | Best capacity fill in this run |
| Savings Delta (TZS) | `savings_delta_tzs` | Change vs previous run (REMATCH only) |
| Alert Sent | `alert_sent` | True if |delta| ≥ TZS 200,000 |
| AI Called | `ai_called` | True if Claude Sonnet was invoked |
| Duration (ms) | `duration_ms` | Algorithm execution time |
| Error Message | `error_message` | Error detail if run failed |
| Created At | `created_at` | Timestamp (indexed) |

**Filters**

| Filter | Type | Notes |
|---|---|---|
| Triggered By | Multi-select | Filter by trigger type |
| Schedule Ref | Search | Filter to one truck's history |
| Alert Sent | Toggle | Show only runs that triggered alerts |
| Errors Only | Toggle | `error_message IS NOT NULL` |
| Date Range | Date range | |
| Duration > N ms | Threshold | Performance monitoring |

**Business Logic**

- `alert_sent = TRUE` when `|savings_delta_tzs| ≥ REMATCH_ALERT_THRESHOLD_TZS` (default TZS 200,000, configurable via env).
- A `triggered_by = REMATCH` entry with a large positive delta means a much better match was found after re-running — the dispatcher should review the new proposals.
- A `triggered_by = REMATCH` entry with a large negative delta means previously matched orders were removed (credit block, cancellation) — the dispatcher should re-confirm or re-allocate.
- `duration_ms > 5000` may indicate a performance degradation in the route calculator or database query — flag for IT review.

**Output Format**

- **Allocator:** Admin table at `GET /api/matching-events` (to be implemented).
- **Export:** CSV for compliance archives.
- **Odoo Integration:** None required. This is an internal system audit log.

---

#### R-12: Allocation Proposal Decision History

| Attribute | Detail |
|---|---|
| **Report ID** | R-12 |
| **Report Name** | Allocation Proposal Decision History |
| **Purpose** | Full lifecycle history of every allocation proposal — from generation through to confirmation, rejection, or dispatch. Enables management to review decision quality, understand which proposal variants dispatchers prefer, and audit the AI advisor's accuracy. |
| **Category** | Audit & Compliance |
| **Update Frequency** | Updated on every status change (confirm, reject, dispatch). |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Operations Manager | Full |
| Transport Manager | Read-only |
| Compliance / Audit | Read-only |
| System Administrator | Full |

**Data Source**

Primary table: `AllocationProposal` (all statuses)  
Joins: `TruckSchedule`, `SavingsLedger` (if dispatched)

**Output Fields**

| Field | Source | Description |
|---|---|---|
| Proposal Ref | `proposal_ref` | e.g., PROP-20260430-001-A |
| Schedule Ref | `schedule_ref` | Linked truck |
| Variant Type | `variant_type` | MAX_SAVINGS / MAX_LOAD / URGENT_FIRST |
| Status | `status` | PROPOSED / CONFIRMED / DISPATCHED / REJECTED |
| Composite Score | `composite_score` | Algorithm ranking (0–1) |
| Estimated Savings | `estimated_savings_tzs` | Savings when proposed |
| Actual Savings | `SavingsLedger.net_savings_tzs` | Savings on dispatch (if DISPATCHED) |
| Savings Variance | Computed | `actual − estimated` (accuracy check) |
| Utilization | `capacity_utilization_pct` | % truck filled |
| Stops | `number_of_stops` | Delivery orders in proposal |
| AI Recommendation | `ai_recommendation` | CONFIRM / REVIEW / HOLD |
| AI Reasoning | `ai_reasoning` | Claude's narrative (truncated to 200 chars in list) |
| Dispatcher Decision | `status` vs `ai_recommendation` | Match or override |
| Confirmed By | `confirmed_by` | Dispatcher name (if confirmed) |
| Confirmed At | `confirmed_at` | Confirmation timestamp |
| Dispatched At | `dispatched_at` | Dispatch timestamp |
| Rejection Reason | `rejection_reason` | Free-text reason (if rejected) |
| Created At | `created_at` | When proposal was generated |

**Filters**

| Filter | Type |
|---|---|
| Status | Multi-select |
| Variant Type | Multi-select |
| AI Recommendation | Multi-select |
| Confirmed By | Search |
| Date Range (Created At) | Date range |
| Dispatcher Override | Toggle — shows where AI said HOLD/REVIEW but dispatcher confirmed |

**Business Logic & Analysis**

- **Variant Preference Rate:** Count by `variant_type` where `status = CONFIRMED`. Tells management whether dispatchers prefer MAX_SAVINGS, MAX_LOAD, or URGENT_FIRST — validates algorithm design.
- **AI Accuracy Rate:** Percentage of proposals where `ai_recommendation = CONFIRM` and dispatcher confirmed (AI correct) vs. AI said HOLD but dispatcher confirmed anyway (override rate).
- **Savings Variance:** For DISPATCHED proposals, `actual_savings − estimated_savings` measures forecast accuracy of the freight savings calculator.
- **Decision Latency:** `confirmed_at − created_at` measures how long dispatchers take to act on proposals — informs training needs.

**Output Format**

- **Allocator:** History table at `GET /api/proposals?status=all` with sorting and pagination.
- **Export:** CSV / PDF for monthly management reporting.
- **Odoo Integration:** No direct write-back. However, the `confirmed_by` + `confirmed_at` + `ai_recommendation` combination can be surfaced in the `purchase.order` chatter (note posted via `message_post`) for audit trail purposes — the Odoo team can implement this as a webhook trigger from the allocator on proposal confirm.

---

### Category E — Management Analysis Reports

---

#### R-13: Corridor & Route Performance Analysis

| Attribute | Detail |
|---|---|
| **Report ID** | R-13 |
| **Report Name** | Corridor & Route Performance Analysis |
| **Purpose** | Multi-month trend analysis showing how each return corridor performs over time — savings trends, utilization rates, seasonal patterns, and top contributors. Used by management to set targets, plan transporter negotiations, and identify optimisation opportunities. |
| **Category** | Management Analysis |
| **Update Frequency** | Generated on demand; data from `SavingsLedger` is live. |

**Target Users & Access**

| Role | Access Level |
|---|---|
| Transport Manager | Full |
| CEO / Management | Read-only (summary view) |
| Finance | Read-only |

**Data Source**

Primary table: `SavingsLedger` grouped by `month_key` + `corridor_name`  
Joins: `RouteCorridor` (for metadata), `Transporter` (for top transporter by corridor)

**Output Fields**

| Field | Calculation | Description |
|---|---|---|
| Month | `month_key` | YYYY-MM period |
| Corridor | `corridor_name` | Return corridor |
| Trips | `COUNT(*)` | Dispatched return loads |
| Total Tonnes | `SUM(allocated_tonnes)` | MT delivered |
| Net Savings (TZS) | `SUM(net_savings_tzs)` | Total programme benefit |
| Avg Utilization | `AVG(capacity_utilization_pct)` | Fill rate (%) |
| Avg Detour (km) | From matching data | Average delivery deviation |
| Rainy Season | Computed | True if month IN (3,4,5) AND corridor = COASTAL |
| Seasonal Rate Premium | 20% if rainy+coastal | Applied to COASTAL Mar–May |
| MoM Change (%) | Computed | `(this_month − last_month) / last_month × 100` |
| Top Transporter | Sub-query | Transporter with most trips this corridor/month |
| Top Customer | Sub-query | Customer with most MT delivered this corridor/month |

**Filters**

| Filter | Type |
|---|---|
| Date Range (multi-month) | From/To month picker |
| Corridor | Multi-select |
| Min Trips | Threshold |

**Business Logic**

- **Seasonal Penalty (COASTAL corridor):** March–May (long rains in coastal Tanzania) — route passes through Rufiji Delta and is subject to flooding. The algorithm applies a 20% rate premium for COASTAL in these months. This report should flag these periods with a note.
- **MoM Change:** Negative month-on-month savings change on a corridor may indicate: fewer RM trucks arriving (procurement change), orders shifting to fresh trucks (credit issues, urgency), or seasonal slowdown.
- **Underperforming Corridors:** Corridors with trips = 0 for a full month should be highlighted — may indicate a broken data link (supplier moved, transporter changed) rather than genuine zero demand.
- **Fleet Size Check:** If `SUM(allocated_tonnes)` / `AVG(capacity_utilization_pct)` implies truck count far below expected daily arrivals (from GRN data), it suggests matching opportunities are being missed.

**Expected Volumes (from 13,299 GRN records / year):**

| Corridor | Trucks/Day | Annual Trips |
|---|---|---|
| NORTHERN (Clinker/Tanga) | ~20 | ~7,300 |
| SOUTHERN_HIGHLAND (Coal/Mbeya) | ~11 | ~4,015 |
| COASTAL (Gypsum/Lindi) | ~4 | ~1,460 |
| CENTRAL (Iron Ore/Dodoma) | ~1 | ~365 |

**Output Format**

- **Primary:** Trend line chart (savings over time per corridor) + pivot table.
- **Export:** CSV + PDF for board reporting.
- **Odoo Integration:** Monthly totals can be pushed to `x.freight.savings.summary` model (same target as R-05) with `corridor_name` as grouping dimension, enabling native Odoo financial pivot/graph views.

---

## 5. Odoo Custom Fields Required

The following new fields must be added to Odoo 15 (Business Unit: TZG) before the full integration can be activated. All fields should be added via a custom module (not directly in the database) to survive upgrades.

### 5.1 Fields on `purchase.order`

| Field Name | Type | Default | Required | Written By | Read By |
|---|---|---|---|---|---|
| `x_origin_region` | Char (64) | — | No | Odoo User (manual override) | Allocator (PO sync) |
| `x_return_load_eligible` | Boolean | True | No | Odoo User | Allocator (filters out ineligible POs) |
| `x_truck_schedule_ref` | Char (256) | — | No | Allocator (on sync) | Odoo display only |

**Field Descriptions:**

- `x_origin_region`: Free-text override for the RM origin region. If blank, the allocator uses the material-type default (CLINKER→TANGA, COAL→MBEYA, etc.). Use this when a supplier has multiple plants (e.g., Dangote supplies Clinker from Mtwara, not Tanga).
- `x_return_load_eligible`: Set to False to exclude a specific PO from the return load programme (e.g., emergency spot procurement, unusual route).
- `x_truck_schedule_ref`: Written by the allocator after TruckSchedule records are created. Comma-separated if a large PO generates multiple schedules. Display-only field for the Odoo user.

### 5.2 Fields on `sale.order`

| Field Name | Type | Selection Values | Required | Written By | Read By |
|---|---|---|---|---|---|
| `x_return_load_status` | Selection | unallocated, candidate, soft_reserved, allocated, delivered | No | Allocator (on allocation events) | Sales team, Customer Service |
| `x_truck_plate` | Char (20) | — | No | Allocator (on proposal confirm) | Sales team, Warehouse |
| `x_proposal_ref` | Char (64) | — | No | Allocator (on proposal confirm) | Dispatcher, Audit |

**Field Descriptions:**

- `x_return_load_status`: Mirrors `CementOrder.allocation_status` in the allocator. Allows the Odoo sales team to filter and kanban their orders by return-load stage without leaving Odoo. Allocator writes back via XML-RPC on every status change.
- `x_truck_plate`: The confirmed truck plate. Populated when a proposal is confirmed by the dispatcher. Allows warehouse staff to verify the truck at the gate.
- `x_proposal_ref`: Links the SO back to the specific allocation proposal. Useful for cross-referencing in case of disputes or queries.

### 5.3 Odoo View Recommendations

| Model | Recommended Odoo Change |
|---|---|
| `purchase.order` | Add `x_origin_region`, `x_return_load_eligible`, `x_truck_schedule_ref` to PO form view (optional info tab or "Return Load" tab) |
| `sale.order` | Add `x_return_load_status` as a status badge in SO header; add `x_truck_plate` + `x_proposal_ref` in delivery tab |
| `sale.order` list view | Add `x_return_load_status` as optional column with colour coding (green=allocated, red=unallocated+overdue) |
| `stock.picking` list view | Add saved filter: `origin ilike ALLOC-%` to show allocator-created pickings; add `origin` column |
| `res.partner` (vendor) | Add smart button "Return Load Trips" showing trip count from allocator API (optional, for high-volume transporters) |

---

## 6. Odoo API Access Requirements

### 6.1 Service Account

| Parameter | Value |
|---|---|
| Username | `truck_allocator_svc` |
| Business Unit | TZG |
| Authentication | Standard Odoo XML-RPC with username + API key (not password) |
| Session Management | Authenticate once; cache session for connection lifetime |

### 6.2 Permissions Required

| Odoo Model | Read | Write | Create | Notes |
|---|---|---|---|---|
| `purchase.order` | ✅ | ✅ | ❌ | Write: x_truck_schedule_ref only |
| `purchase.order.line` | ✅ | ❌ | ❌ | Read product_id and product_qty |
| `sale.order` | ✅ | ✅ | ❌ | Write: x_return_load_status, x_truck_plate, x_proposal_ref |
| `sale.order.line` | ✅ | ❌ | ❌ | Read product and quantity |
| `stock.picking` | ✅ | ✅ | ✅ | Create outbound pickings for confirmed proposals |
| `stock.move` | ✅ | ✅ | ✅ | Create move lines for each picking |
| `res.partner` | ✅ | ❌ | ❌ | Read customer and vendor master |
| `stock.location` | ✅ | ❌ | ❌ | Read warehouse location IDs on startup |
| `product.product` | ✅ | ❌ | ❌ | Read cement product IDs |

### 6.3 Odoo Static IDs to Confirm

The following Odoo record IDs are used for stock.picking creation and must be verified against the production database before go-live:

| Config Variable | Odoo Record | Current Default | Action |
|---|---|---|---|
| `ODOO_PICKING_TYPE_OUTGOING_ID` | `stock.picking.type` (outgoing) | 2 | Confirm with Odoo admin |
| `ODOO_LOCATION_STOCK_ID` | `stock.location` (source stock) | 8 | Confirm with Odoo admin |
| `ODOO_LOCATION_CUSTOMER_ID` | `stock.location` (customer destination) | 5 | Confirm with Odoo admin |

Run `scripts/test_odoo_connection.py` to verify connectivity and validate these IDs before seeding.

### 6.4 Connection Parameters

| Parameter | Value |
|---|---|
| URL | `http://odoo.lakecement.co.tz:8069` |
| Database | `lakecement_prod` |
| Protocol | XML-RPC over HTTP |
| Sync Interval | 15 minutes (configurable: `ODOO_SYNC_INTERVAL_MINUTES`) |
| Timeout | 30 seconds per request |
| Retry Policy | 3 attempts with exponential backoff on connection error |

### 6.5 Domain Filters Used in Odoo Queries

**RM Purchase Orders:**
```python
[
    ('state', '=', 'purchase'),
    ('order_line.product_id.default_code', 'in', ['RM000001', 'RM000003', 'RM000004', 'RM000014']),
    ('company_id.name', 'ilike', 'TZG')
]
```

**Cement Sale Orders:**
```python
[
    ('state', '=', 'sale'),
    ('x_return_load_status', '!=', 'delivered'),
    ('company_id.name', 'ilike', 'TZG')
]
```

---

## 7. Report Summary Matrix

| ID | Report Name | Category | Users | Data Source | Odoo Read | Odoo Write | Status |
|---|---|---|---|---|---|---|---|
| R-01 | Available Trucks Pending Allocation | Operational | Dispatcher, Transport Mgr | TruckSchedule | purchase.order | x_truck_schedule_ref | Live |
| R-02 | Pending Allocation Proposals | Operational | Dispatcher | AllocationProposal | sale.order | stock.picking | Live |
| R-03 | Confirmed Allocations | Operational | Dispatcher, Ops Mgr | AllocationProposal | — | stock.picking | Scaffolded |
| R-04 | Unallocated Orders Backlog | Operational | Dispatcher, Sales | CementOrder | sale.order | x_return_load_status | Live |
| R-05 | Monthly Savings Summary (MTD) | Financial / KPI | Management, Finance | SavingsLedger | — | x.freight.savings.summary | Live |
| R-06 | Savings by Corridor | Financial / KPI | Transport Mgr, Analyst | SavingsLedger | — | Optional | Live |
| R-07 | Savings by Transporter | Financial / KPI | Transport Mgr, Procurement | SavingsLedger | res.partner | Optional | Live |
| R-08 | PO → Truck Schedule Sync Log | ERP Integration | ERP Admin | TruckSchedule, MatchingEvent | purchase.order | x_truck_schedule_ref | Live |
| R-09 | Sale Order Allocation Status | ERP Integration | Sales, Customer Service | CementOrder | sale.order | x_return_load_status, x_truck_plate, x_proposal_ref | Live |
| R-10 | Stock Picking Write-Back Audit | ERP Integration | Warehouse, ERP Admin | ProposalItem | stock.picking | stock.picking, stock.move | Scaffolded |
| R-11 | Matching Engine Audit Log | Audit | Sys Admin, Ops Mgr | MatchingEvent | — | — | Live |
| R-12 | Proposal Decision History | Audit | Ops Mgr, Compliance | AllocationProposal | — | purchase.order chatter (optional) | Live |
| R-13 | Corridor Performance Analysis | Management | Transport Mgr, CEO | SavingsLedger | — | x.freight.savings.summary | Live |

---

## 8. Verification & Testing

### 8.1 Pre-Go-Live Checklist

**Odoo Team Tasks:**

- [ ] Create service account `truck_allocator_svc` with permissions in Section 6.2
- [ ] Add 6 custom fields from Section 5 via Odoo custom module
- [ ] Confirm static IDs: `ODOO_PICKING_TYPE_OUTGOING_ID`, `ODOO_LOCATION_STOCK_ID`, `ODOO_LOCATION_CUSTOMER_ID`
- [ ] Add `x_return_load_status` column to `sale.order` list view
- [ ] Add "Return Load" tab to `sale.order` form view with `x_truck_plate` and `x_proposal_ref`
- [ ] Create saved filter on `stock.picking` list: `origin ilike ALLOC-%`

**Allocator Team Tasks:**

- [ ] Run `scripts/test_odoo_connection.py` — verify connectivity and static IDs
- [ ] Run all 4 seed scripts (transporters, locations, routes, customers)
- [ ] Seed from historical Excel files; verify 859 locations, 417 transporters, 6 corridors loaded
- [ ] Trigger manual Odoo sync: `POST /api/orders/sync` — verify SOs ingested
- [ ] Confirm a test PO exists with RM item code and state=purchase — verify TruckSchedule created
- [ ] Run matching engine manually on test schedule — verify 3 proposals generated
- [ ] Confirm one proposal — verify Odoo stock.picking created and linked

### 8.2 Report Validation Test Cases

| Report | Test | Expected Result |
|---|---|---|
| R-01 | Confirm a PO in Odoo → sync → check R-01 | New truck row appears within 15 min |
| R-02 | New truck in R-01 → wait for match run | 3 proposal cards appear on /proposals |
| R-03 | Confirm proposal → check R-03 | Truck moves from R-01 to R-03; Odoo picking created |
| R-04 | Create SO in Odoo → sync | SO appears on R-04 backlog |
| R-05 | Dispatch a truck → check R-05 | Net savings MTD increases by expected TZS amount |
| R-06 | Dispatch trucks on 2 corridors | Both corridors appear in R-06 with correct savings split |
| R-07 | Dispatch 2 trips via same transporter | Transporter appears in R-07 with aggregated trip count |
| R-08 | Create PO in Odoo → sync → check R-08 | PO row in R-08 with sync_timestamp and schedule_ref populated |
| R-09 | Confirm proposal → check R-09 | SO row shows allocation_status=allocated, truck_plate populated |
| R-10 | Confirm proposal → check Odoo stock.picking | Picking exists with origin=ALLOC-{proposal_ref} |
| R-11 | Trigger manual match | MatchingEvent row created with duration_ms and proposals_generated |
| R-12 | Confirm one proposal, reject another | Both appear in R-12 with correct status and confirmed_by |
| R-13 | Query R-13 for current month | Corridor data matches sum of R-06 for same period |

### 8.3 Historical Data for Testing

The following Excel files in the project directory can be used to seed realistic test data:

| File | Use For |
|---|---|
| `LAKE CEMENT Daily Report (1).xlsx` | Seed historical TruckSchedule records (1,665+ rows) |
| `approved sales orders 1st April'25 to 24th April'26.xlsx` | Seed CementOrder records (30,741 rows); validate R-04 backlog |
| `RM and SFG GRN and DC or DN Details Apr 25 to Apr26.xlsx` | Validate truck arrival patterns (13,299 GRNs); cross-check R-01 volumes |
| `Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx` | Validate R-08 PO sync log; verify vendor code mapping |

---

*End of Document*

---

**Smart Return Truck Allocator — Odoo Report Specification v1.0**  
**Lake Cement Limited (Nyati Cement) | Kimbiji Plant, Dar es Salaam, Tanzania**  
**Document maintained alongside source code at:** `C:\Users\USER\return trucks optimization\`
