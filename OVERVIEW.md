# Nyati Cement — Smart Return Truck Allocator

## What It Does

A smart logistics tool that tracks inbound raw material trucks from the moment a Purchase Order is confirmed in Odoo. It matches each truck's return journey with cement delivery orders heading in the same direction — so trucks that would otherwise return empty can carry a load of cement, saving freight cost on both ends.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Database | SQLite via SQLAlchemy (async) |
| ERP Integration | Odoo 15 (XML-RPC) |
| AI Advisor | Anthropic Claude |
| Background Jobs | APScheduler |
| Dashboard | 3 HTML pages (vanilla JS) |
| Live Updates | Server-Sent Events (SSE) |

---

## How It Works — Step by Step

1. A Purchase Order for raw materials (clinker, coal, gypsum, or iron ore) is confirmed in Odoo at Kimbiji Plant.
2. The system syncs with Odoo every 15 minutes. It picks up the PO, identifies the material's origin region and return corridor, and creates a **Truck Schedule** entry.
3. The **matching engine** scores all unallocated cement Sale Orders by how well they fit the truck's return route and remaining load capacity.
4. The **Schedule page** shows the dispatcher a live list of inbound trucks, each with an **Allocate →** button.
5. Clicking Allocate opens the Odoo Sale Order creation form — pre-filled with the truck plate and driver details.
6. The dispatcher completes the Sale Order in Odoo, assigning the cement delivery to the return truck.
7. The **Order Status page** shows all Sale Orders created in Odoo and their dispatch state (Pending or Dispatched).
8. The **Final Status page** shows completed outcomes — which trucks carried cement (Dispatched) and which returned empty (Released), along with invoice details.

---

## Dashboard Pages

| Page | URL | Purpose |
|---|---|---|
| Schedule | `/` | Live inbound truck list; Allocate button opens Odoo SO form |
| Order Status | `/order-status` | Cement Sale Orders from Odoo — Pending or Dispatched |
| Final Status | `/final` | Outcomes over past N days — Dispatched vs Released with invoice data |

All pages update live via SSE (Server-Sent Events) without needing a manual refresh.

---

## Return Corridors

Trucks are matched based on which corridor they travel. The system knows the origin of each raw material and maps it to a return route:

| Corridor | Raw Material | Truck Origin |
|---|---|---|
| Northern | Clinker | Tanga |
| Southern Highlands | Coal | Mbeya / Kyela |
| Central | Iron Ore | Dodoma |
| Southern Coast | Gypsum | Lindi / Rufiji |

The matching engine only considers cement delivery orders that fall along the truck's return corridor — within an acceptable detour distance.

---

## Odoo Integration

- **Reads:** Purchase Orders (inbound raw materials), Sale Orders (cement deliveries), Stock Pickings (truck arrival status)
- **Writes:** Opens a pre-filled Odoo Sale Order form for the dispatcher to complete
- **Sync interval:** Every 15 minutes via XML-RPC

---

## Savings Formula

```
Net Savings = Fresh Outbound Freight − Return Load Negotiated Rate − Holding Cost
```

The system tracks actual savings per trip and aggregates them by corridor and month.

---

*Lake Cement Limited — Kimbiji Plant, Dar es Salaam, Tanzania*
