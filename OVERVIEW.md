# Nyati Cement — Return Truck Allocator

## What It Does

A logistics dashboard that tracks inbound raw material trucks from the moment a Purchase Order is confirmed in Odoo. It shows dispatchers which trucks are inbound, and lets them open an Odoo Sale Order form — pre-filled with the truck's details — so they can quickly assign a cement delivery order to the return journey.

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

1. A Purchase Order for raw materials (clinker, coal, gypsum, or iron ore) is confirmed in Odoo at Kimbiji Plant.
2. The system syncs with Odoo every 15 minutes. It picks up the PO, identifies the material's origin region and return corridor, and creates a **Truck Schedule** entry in the local database.
3. The **Schedule page** shows the dispatcher a live list of all inbound trucks, with key details: PO ref, material, transporter, driver, truck plate, and origin.
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

## Odoo Integration

- **Reads:** Purchase Orders (RM inbound), Sale Orders (cement deliveries), Stock Pickings (truck arrival status), Fleet Vehicles (truck plate lookup), Driver Master (driver ID lookup)
- **Writes:** Pre-filled Odoo SO form URL that the dispatcher uses to create a new Sale Order
- **Sync interval:** Every 15 minutes via XML-RPC

---

## Savings Formula

```
Net Savings = Fresh Outbound Freight − Return Load Negotiated Rate − Holding Cost
```

Savings are tracked per trip in the savings ledger and aggregated by corridor and month via the `/api/savings/summary` endpoint.

---

*Lake Cement Limited — Kimbiji Plant, Dar es Salaam, Tanzania*  
*App Version 3.0.0 · Updated May 2026*
