# Smart Return Truck Allocator — User Guide
### Lake Cement Limited (Nyati Cement) · Kimbiji Plant, Dar es Salaam

---

## What This System Does

Every day, raw material trucks (Clinker, Coal, Gypsum, Iron Ore) arrive at Kimbiji Plant from Tanga, Mbeya, Dodoma, Lindi, and other origins. Once they unload, those trucks drive back empty.

**This system prevents that.**

The allocator automatically matches each inbound truck with cement delivery orders going in the same direction — before the truck even arrives. The dispatcher reviews the proposal, confirms it, and the truck loads and leaves with cement instead of returning empty.

**Financial formula:** `Net Savings = Fresh Outbound Freight − Return Load Rate − Holding Cost`

A typical 30 MT Clinker truck returning from Tanga saves **TZS 400,000–600,000 per trip** in avoided fresh freight.

---

## Who Uses This System

| Role | What They Do |
|------|-------------|
| **Logistics Dispatcher** | Reviews proposals, confirms allocations, marks trucks arrived/dispatched |
| **Transport Manager** | Monitors KPIs, reviews savings reports, handles exceptions |
| **Operations Manager** | Views confirmed allocations, exports monthly reports |

---

## Getting Started

Open your browser and go to:

```
http://localhost:8001
```

You will see three tabs in the top navigation bar:

| Tab | Purpose |
|-----|---------|
| **Schedule** | Live list of all inbound trucks and their allocation status |
| **Proposals** | AI-generated loading proposals waiting for your confirmation |
| **Confirmed** | History of confirmed and dispatched allocations with savings KPIs |

The green dot in the top-right corner means the dashboard is receiving live updates automatically — you do not need to refresh the page.

---

## Page 1: Schedule (Inbound Truck Schedule)

**URL:** `http://localhost:8001/`

This is your main working screen. It shows every inbound raw material truck that is expected at Kimbiji Plant.

### KPI Cards (top of page)

| Card | Meaning |
|------|---------|
| **Expected Trucks (7 days)** | Number of trucks arriving in the next 7 days not yet matched |
| **Unallocated Orders** | Cement orders ready to load but not yet assigned to a truck |
| **Avg Utilization** | Average truck fill rate for matched trucks (target: >85%) |
| **Matched This Month** | Number of confirmed allocations this calendar month |

### Truck Table

Each row is one truck. Columns explained:

| Column | Meaning |
|--------|---------|
| **ETA** | Expected arrival date and time at Kimbiji Plant |
| **Transporter** | Haulier company name |
| **Driver Name** | Driver name (filled in when transporter pre-advises) |
| **License No.** | Driver licence number |
| **Dealer No.** | Transporter's internal job/dealer reference number |
| **Truck No.** | Truck plate (e.g. T865EHY) |
| **Origin** | Where the truck is coming from (TANGA, MBEYA, DODOMA, KIRANJERANJE) |
| **Material** | Raw material being delivered (CLINKER, COAL, GYPSUM, IRON_ORE) |
| **Route** | Return corridor (NORTHERN, CENTRAL, SOUTHERN_HIGHLAND, COASTAL) |
| **Status** | Current truck lifecycle stage (see below) |
| **Action** | Button to view proposals for this truck |

### Truck Status Values

| Status | Meaning |
|--------|---------|
| `EXPECTED` | Truck is coming — PO confirmed in Odoo, not yet pre-advised |
| `PRE_CONFIRMED` | Transporter has sent pre-advice (plate and/or driver known) |
| `ARRIVED` | Truck has physically arrived at Kimbiji Plant gate |
| `LOADED` | Cement has been loaded onto the truck |
| `DISPATCHED` | Truck has left the plant with cement |
| `COMPLETED` | Trip fully completed and logged |

### Allocation Status Values

| Status | Meaning |
|--------|---------|
| `UNMATCHED` | No cement orders matched yet |
| `PROPOSED` | System has generated proposals — awaiting dispatcher review |
| `CONFIRMED` | Dispatcher has confirmed a loading plan |
| `DISPATCHED` | Truck has departed with cement |

### Adding Truck Details (Pre-Advice)

When a transporter calls in advance with truck plate, driver name, and capacity:

1. Click the **Review** button on the truck row.
2. On the proposals page, the truck details panel will appear at the top.
3. Enter the truck plate, driver name, driver phone, and actual capacity.
4. Click **Save Details** — the status moves from EXPECTED to PRE_CONFIRMED.

### Marking a Truck as Arrived

When a truck physically arrives at the plant gate:

1. Find the truck in the Schedule table.
2. Click **Review** → then **Mark Arrived** on the proposals page.
3. The status updates to ARRIVED and the actual arrival time is recorded.

### Syncing with Odoo

The system syncs with Odoo automatically every 15 minutes. To force an immediate sync:

Click **⟳ Sync Odoo** in the top-right of the Schedule table.

This pulls any new confirmed Purchase Orders (new inbound trucks) and updated Sale Orders (new cement delivery orders) from Odoo.

---

## Page 2: Proposals

**URL:** `http://localhost:8001/proposals`

**URL for a specific truck:** `http://localhost:8001/proposals?schedule=<id>`

This is where you confirm what cement goes on which truck.

For each truck, the system generates **three proposal variants** automatically:

| Variant | Header Colour | What It Optimises |
|---------|--------------|-------------------|
| **MAX SAVINGS** | Navy blue | Highest TZS savings — picks the orders that save the most freight cost |
| **MAX LOAD** | Orange | Highest tonnage — fills the truck as full as possible |
| **URGENT FIRST** | Red | Prioritises orders with the closest delivery deadlines |

### Reading a Proposal Card

Each card shows:

- **Estimated Savings** — How much this allocation saves in TZS vs. sending a fresh truck
- **Capacity Utilisation** — What percentage of the truck's capacity is used (e.g. 87%)
- **Stops** — Number of delivery stops on the return route
- **Route Deviation** — Extra kilometres added to the truck's return journey
- **Holding Cost** — Cost of having cement wait in the warehouse
- **Orders list** — Each cement order included, with customer name, tonnage, and destination

### AI Advisory Panel

Below the three variants you may see an **AI Advisory** panel. This shows a recommendation from the Claude AI model — CONFIRM, REVIEW, or HOLD — with a written explanation. This is advisory only; the dispatcher makes the final decision.

### Confirming a Proposal

1. Review the three variants and choose the one that best fits your operational priorities.
2. Click **Confirm** on that variant's card.
3. A confirmation dialog will appear — click **Yes, Confirm**.
4. The truck status updates to CONFIRMED and the matched cement orders are reserved.
5. An Odoo delivery order (stock.picking) is created automatically.

Once confirmed, the other two variants are automatically rejected.

### Rejecting All Proposals

If none of the proposals are suitable (e.g. the truck is too small, or no orders match):

1. Click **Reject** on any card and select a reason.
2. The system will re-run the matching engine and generate new proposals when new orders are available.

### Force Re-Match

If the proposal looks outdated (new orders came in after the proposals were generated):

Click **Re-Match** at the top of the proposals page for that truck. The system re-runs the algorithm immediately with the latest available orders.

---

## Page 3: Confirmed Allocations

**URL:** `http://localhost:8001/confirmed`

This page is a historical record of all confirmed and dispatched allocations, with full KPI reporting.

### KPI Cards

| Card | Meaning |
|------|---------|
| **Total Trips** | Number of confirmed allocations in the selected month |
| **Avg Utilization** | Average truck fill rate for the month |
| **Net Savings** | Total TZS saved vs. using fresh outbound trucks |
| **Total Tonnes** | Total cement tonnage delivered via return trucks |

Use the **month selector** (top-right) to switch between months.

### Allocation Table

| Column | Meaning |
|--------|---------|
| **Proposal Ref** | Internal allocation reference number |
| **Truck** | Truck plate number |
| **Transporter** | Haulier company |
| **Route** | Return corridor |
| **Confirmed** | Date and time dispatcher confirmed the allocation |
| **Dispatched** | Date and time truck departed with cement |
| **Orders** | Number of cement delivery orders on the truck |
| **Tonnes** | Total cement loaded |
| **Savings (TZS)** | Net savings for this trip |
| **Utilisation** | Truck fill percentage |

### Exporting Data

Click **⬇ Export CSV** to download the current month's confirmed allocations as a spreadsheet. This is used for finance reporting and transporter payment reconciliation.

---

## Understanding the Matching Algorithm

The system scores each cement order against each inbound truck using four factors:

| Factor | Weight | What It Checks |
|--------|--------|----------------|
| **Savings** | 30% | How much freight cost is avoided |
| **Capacity** | 25% | How well the order fills the truck |
| **Route** | 25% | How far off the truck's return route the delivery is |
| **Urgency** | 20% | How close the delivery deadline is |

Orders are only matched if:
- The delivery destination is on or near the truck's return corridor
- The detour required does not exceed the corridor's maximum (60–150 km depending on route)
- The cement order is marked **dispatch-ready** and **credit-cleared** in Odoo

---

## Corridor Reference

| Corridor | Origin | Typical Trucks |
|----------|--------|---------------|
| **NORTHERN** | Tanga (Clinker) | KAIXIN, ANTU LOGISTICS, NACHARO ROYAL |
| **SOUTHERN_HIGHLAND** | Mbeya/Kyela (Coal) | WEFIJOJUA, RAS LOGISTICS |
| **CENTRAL** | Dodoma (Iron Ore) | Various |
| **COASTAL** | Lindi/Kiranjeranje (Gypsum) | EMMANUEL MARTINI MGONJA |
| **LOCAL** | DSM-area (Gypsum) | Various |
| **LAKE_VICTORIA** | Mwanza (Gypsum) | Various |

---

## Common Situations and What to Do

**A truck arrives but has no proposals:**
The truck may have no matching cement orders for its corridor. Click **Re-Match** or check if cement orders for that route are marked dispatch-ready in Odoo.

**Proposals show "Near-Ready" warning:**
One or more orders on the proposal are not yet fully dispatch-ready (credit or stock not cleared). The proposal is valid but carries a small risk of delay. Confirm if the orders are expected to clear within the next few hours.

**Savings figure seems low:**
Check the Route Deviation km. A high detour (>80 km) significantly reduces savings. The URGENT FIRST variant may have better savings if deadline orders happen to be close to the route.

**The live dot turns grey:**
The SSE connection has dropped. Refresh the page — data will not have been lost, the page just stopped receiving automatic updates temporarily.

**Truck arrived but not in the system:**
The PO may not yet be confirmed in Odoo, or the 15-minute sync has not run. Click **⟳ Sync Odoo** to pull the latest POs immediately.

---

## Quick Reference — Dispatcher Daily Workflow

```
MORNING
  1. Open Schedule page → check trucks arriving today and tomorrow
  2. Click ⟳ Sync Odoo to pull overnight POs and SOs
  3. Review any PROPOSED trucks → open Proposals page → confirm best variant

DURING THE DAY
  4. When transporter calls with pre-advice → enter truck plate + driver details
  5. When truck arrives at gate → click Mark Arrived
  6. When truck is loaded and leaving → click Dispatch

END OF DAY
  7. Review Confirmed page → check no trucks left unloaded
  8. Export CSV if needed for daily operations report
```

---

## System Access

| Item | Value |
|------|-------|
| Dashboard URL | `http://localhost:8001` |
| API documentation | `http://localhost:8001/docs` |
| Odoo integration | Syncs every 15 minutes automatically |
| Support contact | Digital Team · digital@lakecement.co.tz |

---

*Smart Return Truck Allocator · Lake Cement Limited (Nyati Cement) · Kimbiji Plant*
*Document version: May 2026*
