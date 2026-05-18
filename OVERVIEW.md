# Nyati Cement — Return Truck Allocator

## What It Does

A logistics dashboard that tracks inbound raw material trucks and helps dispatchers allocate cement delivery orders to them before the trucks leave the plant.

Truck data enters the system through the **Purchase department**, who prepare an Excel sheet as soon as a transporter is dispatched with raw materials. The Logistics team uploads the sheet via the **Import Excel** button on the Schedule page — the system records each truck instantly, stamping the upload date automatically.

The goal: stop trucks from returning empty. Every truck that carries cement back to its origin saves the cost of sending a separate outbound truck on the same route.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Database | SQLite via SQLAlchemy (async) |
| ERP Integration | Odoo 15 (XML-RPC) |
| Background Jobs | APScheduler |
| Dashboard | 3 HTML pages (vanilla JS) |
| Live Updates | Server-Sent Events (SSE) |

---

## How It Works — Step by Step

1. A transporter is dispatched with raw materials from the supplier. The **Purchase department** prepares an Excel sheet with the truck details (transporter, driver, plate, origin, date of dispatch, etc.).
2. The Logistics team uploads the Excel sheet using the **↑ Import Excel** button on the Schedule page. The system processes it in memory (no file is stored), deduplicates rows, and auto-stamps each record with the upload date.
3. The **Schedule page** shows a live list of all inbound trucks, searchable and filterable by material, corridor, plate, driver, or transporter.
4. The dispatcher clicks **Allocate →** on a truck row. A new window opens — the Odoo Sale Order creation form, pre-filled with the truck plate and driver ID.
5. The dispatcher completes the Sale Order in Odoo: selects the customer, cement product, quantity, and delivery location.
6. The **Order Status page** shows all Sale Orders created in Odoo, updated every 15 minutes. Orders are either **Pending** (truck not yet loaded) or **Dispatched** (truck has left the plant).
7. The **Final Status page** shows completed outcomes for any selected period — trucks that carried cement (**Dispatched**) and trucks that returned empty (**Released**), along with invoice numbers and quantities.

---

## Dashboard Pages

| Page | URL | Purpose |
|---|---|---|
| Schedule | `/` | Live inbound truck list; Allocate button opens Odoo SO form |
| Order Status | `/order-status` | Cement Sale Orders from Odoo — Pending or Dispatched |
| Final Status | `/final` | Outcomes over past N days — Dispatched vs Released with invoice data |

---

## Return Corridors

Trucks are grouped by the route they travel back to their origin. The system maps each raw material supplier to a corridor automatically:

| Corridor | Raw Material | Truck Origin |
|---|---|---|
| Northern | Clinker | Tanga |
| Southern Highlands | Coal | Mbeya / Kyela |
| Central | Iron Ore | Dodoma |
| Southern Coast | Gypsum | Lindi / Rufiji |

---

## Data Entry

| Source | What It Provides |
|---|---|
| **Purchase dept — Excel upload** | Inbound truck records (transporter, driver, plate, material, origin, dispatch date) |
| **Odoo (Sale Orders)** | Cement delivery orders — Order Status and Final Status pages |
| **Odoo (Fleet / Driver Master)** | Pre-fills truck plate and driver ID on the Allocate → SO form |

## Odoo Integration

- **Reads:** Sale Orders (cement deliveries), Fleet Vehicles (truck plate lookup), Driver Master (driver ID lookup)
- **Writes:** Pre-filled Odoo SO form URL that the dispatcher uses to create a new Sale Order
- **Note:** Purchase Order sync from Odoo is no longer used for the Schedule page. Truck data now comes from Purchase department Excel uploads.

---

## Savings Formula

```
Net Savings = Fresh Outbound Freight − Return Load Negotiated Rate − Holding Cost
```

Savings are tracked per trip in the savings ledger and aggregated by corridor and month via the `/api/savings/summary` endpoint.

---

*Lake Cement Limited — Kimbiji Plant, Dar es Salaam, Tanzania*  
*App Version 3.1.0 · Updated May 2026*
