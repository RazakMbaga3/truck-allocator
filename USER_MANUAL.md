# User Manual — Nyati Cement Return Truck Allocator
### Lake Cement Limited · Kimbiji Plant, Dar es Salaam

---

## 1. What Is This Tool?

The Return Truck Allocator is a logistics dashboard that helps dispatchers track inbound raw material trucks and assign cement delivery orders to them before they leave the plant.

When a supplier delivers raw materials (clinker, coal, gypsum, or iron ore) to Kimbiji Plant, the delivery truck does not need to return empty. This tool shows you which trucks are inbound, helps you identify which ones can carry a cement order on the return journey, and opens the Odoo Sale Order form pre-filled with the truck's details so you can complete the allocation quickly.

**The result:** fewer empty return trips, lower freight costs, and better truck utilisation.

---

## 2. How to Access

Open a web browser and go to:

```
http://localhost:8001
```

> If the app is deployed on a server, your IT team will give you the server address instead.

The app has three pages, accessible from the navigation bar at the top:

| Page | What It Shows |
|---|---|
| **Schedule** | Inbound trucks expected at the plant |
| **Order Status** | Cement Sale Orders and their dispatch state |
| **Final Status** | Completed outcomes — which trucks were loaded, which returned empty |

---

## 3. The Schedule Page

**URL:** `/`  
**Purpose:** Your main working page. Shows all inbound raw material trucks synced from Odoo.

### Reading the Dashboard Cards

At the top of the page you will see four summary cards:

| Card | What It Means |
|---|---|
| **Expected Trucks (7 days)** | Trucks due to arrive in the next 7 days that have not yet been allocated |
| **Draft Load Plans** | Allocation records started but not yet confirmed |
| **Awaiting Loading** | Trucks that have been allocated and are waiting to be loaded |
| **Loaded This Month** | Trucks successfully loaded with cement this month, with completion % |

### Reading the Truck Table

The main table lists all inbound trucks. Each row is one truck:

| Column | Meaning |
|---|---|
| **PO Ref** | The Odoo Purchase Order number (LPORD/YYYY/NNNNN) |
| **Material** | The raw material being delivered (CLINKER, COAL, GYPSUM, IRON ORE) |
| **Transporter** | The transport company name |
| **Driver** | Driver's full name |
| **Phone** | Driver's mobile number |
| **Licence** | Driver's licence/ID number |
| **Dealer No.** | Inward token or gate entry number (RM/YYYY/NNNNN) |
| **Truck No.** | Vehicle plate number |
| **Location** | The truck's origin region (where it is coming from) |
| **Action** | Button or status indicator |

### Truck Status Pills

Trucks that have already been processed show a status pill instead of an Allocate button:

| Pill | Meaning |
|---|---|
| Grey — *Unallocated* | No action taken yet |
| Navy — *Awaiting Loading* | Allocated; truck is being loaded with cement |
| Green — *Loaded ✓* | Truck has been loaded and dispatched |

### The Collapsible Section at the Bottom

Below the main table is a collapsible **Allocated / Dispatched Trucks** section showing trucks that have already been processed. Click the heading to expand it.

---

## 4. How to Allocate a Truck

This is the core action. When you see an inbound truck that can carry a cement order, follow these steps:

**Step 1:** Find the truck in the Schedule table. Check the Material and Location to understand which return corridor it is travelling on.

**Step 2:** Click the **Allocate →** button on that truck's row.

**Step 3:** A new window opens — this is the Odoo Sale Order creation form. If the truck's plate number and driver are registered in Odoo's fleet, these fields are pre-filled automatically. If not, a notification tells you to fill them in manually.

**Step 4:** In Odoo, complete the Sale Order:
- Select or confirm the Customer
- Choose the cement product and quantity
- Confirm the delivery location
- Save and confirm the order

**Step 5:** Return to the Allocator dashboard. The truck's status updates automatically. You can see the new Sale Order on the **Order Status** page.

> **Tip:** The Allocate button opens Odoo in a new browser tab. Keep the Allocator dashboard open in your original tab so you can continue monitoring other trucks.

---

## 5. The Order Status Page

**URL:** `/order-status`  
**Purpose:** Shows cement Sale Orders that have been created in Odoo — how many are waiting to be dispatched and how many have already been loaded onto trucks.

### Dashboard Cards

| Card | What It Means |
|---|---|
| **Total Orders** | All Sale Orders in the selected date range |
| **Pending** | Orders created but truck not yet loaded |
| **Dispatched** | Orders where the truck has been loaded and left |
| **Qty Dispatched (MT)** | Total metric tonnes of cement dispatched |

### Filters

- **Last ___ days:** Change the date range (default: last 7 days, max: 90 days)
- **Status filter:** View All, Pending only, or Dispatched only

### Table Columns

| Column | Meaning |
|---|---|
| **SO No.** | Odoo Sale Order number (SO/YYYY/NNNNN) |
| **Date** | Date the Sale Order was created |
| **Customer** | Customer name |
| **Location** | Delivery destination |
| **Transporter** | Transport company |
| **Driver** | Driver name |
| **Phone** | Driver's mobile number |
| **Licence** | Driver's licence/ID number |
| **Qty (MT)** | Ordered quantity in metric tonnes |
| **Status** | Pending (orange) or Dispatched (green) |

### Status Meaning

| Status | Meaning |
|---|---|
| **Pending** | Sale Order exists; truck assigned but not yet confirmed as loaded in Odoo |
| **Dispatched** | Truck has left the plant with the cement order |

> **Note:** This page pulls data directly from Odoo. Data is as current as the Odoo system.

---

## 6. The Final Status Page

**URL:** `/final`  
**Purpose:** Shows the final outcome for trucks over a selected period — did they carry cement (Dispatched) or leave empty (Released)?

### Dashboard Cards

| Card | What It Means |
|---|---|
| **Total Outcomes** | All trucks processed in the selected period |
| **Dispatched ✓** | Trucks that were successfully loaded with a cement order |
| **Released ⊘** | Trucks that left the plant without a cement order |
| **Total Qty (MT)** | Total cement loaded across all dispatched trucks |

### Filters

- **Last ___ days:** Change the date range (default: last 30 days, max: 90 days)
- **Status filter:** View All, Dispatched only, or Released only

### Table Columns

| Column | Meaning |
|---|---|
| **PO Ref** | Purchase Order number for the inbound RM delivery |
| **SO No.** | Odoo Sale Order number (cement delivery) |
| **Transporter** | Transport company |
| **Driver** | Driver name |
| **Location** | Cement delivery destination |
| **Qty (MT)** | Cement quantity in metric tonnes |
| **Invoice No.** | Odoo invoice number (if issued) |
| **Invoice Date** | Date invoice was posted in Odoo |
| **Status** | Dispatched (navy) or Released (orange) |
| **Remark** | Any notes recorded against the Sale Order |

### Status Meaning

| Status | Meaning |
|---|---|
| **Dispatched** | An invoice was posted in Odoo — truck left loaded with cement |
| **Released** | No invoice posted — truck left without a cement allocation |

---

## 7. Exporting Data to Excel

Every page has an **Export Excel** button. Clicking it downloads an Excel file with all rows currently visible in the table (respecting any active filters).

The Excel file is formatted with Nyati Cement branding (navy and orange headers).

- **Schedule page:** Exports the full truck schedule list
- **Order Status page:** Exports Sale Orders for the selected date range and status filter
- **Final Status page:** Exports allocation outcomes for the selected date range and status filter

---

## 8. Syncing with Odoo

The system automatically syncs with Odoo every **15 minutes**. This means:
- New Purchase Orders confirmed in Odoo will appear as new truck rows within 15 minutes
- Sale Order status changes (dispatched, cancelled) will appear within 15 minutes

**To force an immediate sync:** Click the **⟳ Sync Odoo** button on the Schedule page. This triggers a manual full sync with Odoo and refreshes all data.

**To refresh the current view without syncing:** Click the **Refresh** button.

The **last sync time** is shown in the top-right corner of each page next to the green live indicator dot.

---

## 9. Live Updates (SSE)

The Schedule page updates automatically in real time using Server-Sent Events (SSE). You do not need to refresh the page manually — when another user marks a truck as arrived or loaded, your view updates instantly.

The connection status is shown in the top-right corner of the page. If the connection is lost, the indicator will change; refresh the page to reconnect.

---

## 10. Return Corridors — Quick Reference

The system organises trucks by their **return corridor** — the route the truck follows back to its home base. Cement delivery orders are matched to trucks based on whether the delivery location falls along that corridor.

| Corridor | Raw Material | Truck Origin | Key Delivery Areas |
|---|---|---|---|
| **Northern** | Clinker | Tanga | Tanga, Moshi, Kilimanjaro, Arusha |
| **Southern Highlands** | Coal | Mbeya / Kyela | Mbeya, Iringa, Morogoro |
| **Central** | Iron Ore | Dodoma | Dodoma, Morogoro |
| **Southern Coast** | Gypsum | Lindi / Kiranjeranje | Rufiji, Kibiti, Nyamisati |

---

## 11. Common Questions

**Q: The Allocate button opened Odoo but the truck details were not pre-filled — what do I do?**
A: The truck plate or driver is not registered in Odoo's fleet master. Fill in the Truck No. and Driver fields manually in the Odoo SO form. Notify your Odoo administrator to add the vehicle to the fleet register.

**Q: A truck is showing in the Schedule but the PO Ref column is blank — is that normal?**
A: Yes, this can happen if the Purchase Order was synced before the PO number was recorded. It will fill in on the next sync cycle (within 15 minutes).

**Q: The Order Status page shows "No orders found" — is that correct?**
A: Check the date range filter (default is last 7 days). Extend it to 14 or 30 days. If still empty, the Odoo sync may not have run yet — click **Sync Odoo** on the Schedule page and then refresh.

**Q: A truck appears in Final Status as "Released" but I know it was loaded — what happened?**
A: Released means no posted invoice was found in Odoo for that truck. Check in Odoo whether the invoice for that Sale Order has been confirmed/posted. Once posted, it will show as Dispatched on the next data refresh.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **PO** | Purchase Order — the order placed by Lake Cement to buy raw materials from a supplier |
| **SO** | Sale Order — the order for cement delivery created in Odoo when a truck is allocated |
| **GRN** | Goods Received Note — issued when raw materials are received and weighed at the plant |
| **MT** | Metric Tonnes |
| **Inbound truck** | A truck bringing raw materials to Kimbiji Plant |
| **Return corridor** | The route a truck follows back to its origin after unloading at the plant |
| **Allocated** | A truck that has been assigned a cement delivery order for its return journey |
| **Released** | A truck that left without a cement order (empty return) |
| **Dispatched** | A truck that has left the plant loaded with cement (confirmed by Odoo invoice) |
| **Pending** | A Sale Order that exists in Odoo but the truck has not yet been confirmed as loaded |
| **Transporter** | The transport company operating the truck |
| **Dealer No.** | The inward token or gate entry number assigned when the truck arrives at the plant |
| **TZS** | Tanzanian Shilling — currency used for freight and savings calculations |

---

*Nyati Cement — Lake Cement Limited · Kimbiji Plant, Dar es Salaam, Tanzania*  
*App Version 3.0.0 · Updated May 2026*
