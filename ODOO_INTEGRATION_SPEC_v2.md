# Return Truck Allocator — Odoo Integration Technical Specification
### Lake Cement Limited (Nyati Cement) · Kimbiji Plant, Tanzania

---

**Document Type:** Technical Specification — Odoo Development Team  
**Prepared by:** Digital Team · Lake Cement Limited  
**Date:** 19 May 2026  
**Version:** 2.0 (Updated — Excel Import Workflow)  
**System:** Return Truck Allocator v3.1 ↔ Odoo 15 (Business Unit: TZG)  
**Contact:** razakmbaga3@gmail.com

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Changed in v3.1](#2-what-changed-in-v31)
3. [Integration Architecture](#3-integration-architecture)
4. [Data Flow — Detailed](#4-data-flow--detailed)
5. [Odoo Models Used](#5-odoo-models-used)
6. [The Allocate Button — How It Works](#6-the-allocate-button--how-it-works)
7. [Sale Order Fields Required](#7-sale-order-fields-required)
8. [Fleet & Driver Master Requirements](#8-fleet--driver-master-requirements)
9. [Custom Fields Required in Odoo](#9-custom-fields-required-in-odoo)
10. [Service Account & Permissions](#10-service-account--permissions)
11. [Connection Details](#11-connection-details)
12. [Reference Numbers & Formats](#12-reference-numbers--formats)
13. [Proposed Enhancement — Write-Back on Import](#13-proposed-enhancement--write-back-on-import)
14. [Action Items for Odoo Team](#14-action-items-for-odoo-team)

---

## 1. Executive Summary

The **Return Truck Allocator** is a standalone FastAPI web service running at Kimbiji Plant that helps Logistics dispatchers assign cement delivery orders to inbound raw material trucks — before those trucks leave the plant empty.

The system connects to Odoo 15 via XML-RPC for two purposes:

1. **READ** — Pull cement Sale Orders and truck/driver registration data from Odoo
2. **WRITE** — Open a pre-filled Odoo Sale Order form when the dispatcher clicks **Allocate →**

The allocator maintains its own local database (SQLite) for truck schedule tracking. It does **not** depend on Odoo for inbound truck data — that data now comes from a Purchase department Excel upload (see Section 2).

**Financial objective:**

> Net Savings (TZS) = Fresh Outbound Freight Avoided − Return Truck Rate Paid − Holding Cost

---

## 2. What Changed in v3.1

This section is critical for the Odoo team to understand. The integration scope changed in May 2026 following a decision by the Purchase Head.

### Previous Architecture (v2.x — Retired)

```
Odoo purchase.order (confirmed RM POs)
        ↓  XML-RPC READ every 15 min
Return Truck Allocator — TruckSchedule table
```

The system read confirmed Purchase Orders from Odoo to know which trucks were inbound. This created a dependency on the Odoo PO confirmation cycle, which lagged behind ground-level dispatch activity.

### Current Architecture (v3.1 — Active)

```
Purchase Dept prepares Excel sheet at point of truck dispatch
        ↓  Manual upload via ↑ Import Excel button
Return Truck Allocator — TruckSchedule table
```

Inbound truck records are now entered by uploading an Excel file. The Purchase department prepares this file as soon as a transporter is dispatched from the supplier — earlier and more accurate than the Odoo PO cycle.

### Impact on Odoo Integration

| Integration Point | v2.x Status | v3.1 Status |
|---|---|---|
| READ `purchase.order` for truck schedule | Active — used to create TruckSchedule records | **Retired** — truck data comes from Excel |
| READ `sale.order` for Order Status / Final Status pages | Active | **Active — unchanged** |
| READ `fleet.vehicle` to pre-fill Allocate form | Active | **Active — unchanged** |
| READ `driver.master.custom` to pre-fill Allocate form | Active | **Active — unchanged** |
| WRITE `stock.picking` on allocation confirm | Scaffolded | **Under review** |
| WRITE fleet/driver records from Excel import | Not implemented | **Proposed — see Section 13** |

---

## 3. Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ODOO 15 (TZG BU)                              │
│                                                                          │
│  sale.order ──────────────► [READ every 15 min via XML-RPC]             │
│  (state = 'sale')            Cement delivery orders → Order Status page  │
│                              Invoice status     → Final Status page      │
│                                                                          │
│  account.move ────────────► [READ every 15 min]                         │
│  (posted invoices)           Invoice No., date → Final Status page       │
│                                                                          │
│  fleet.vehicle ────────────► [READ on Allocate → click]                 │
│                               Lookup by truck plate → pre-fill SO form   │
│                                                                          │
│  driver.master.custom ─────► [READ on Allocate → click]                 │
│                               Lookup by licence no. → pre-fill SO form   │
│                                                                          │
│  sale.order (form) ◄──────── [WRITE via browser redirect]               │
│                               Dispatcher opens pre-filled new SO form    │
│                               and completes allocation directly in Odoo  │
└────────────────────────┬────────────────────────────────────────────────┘
                         │  XML-RPC  (port 8069)
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│          RETURN TRUCK ALLOCATOR  (FastAPI, port 8001)                   │
│                                                                          │
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐   │
│  │  Excel Import        │    │  Odoo Sync Service                   │   │
│  │  POST /api/schedules │    │  Reads SO, invoices every 15 min     │   │
│  │  /import             │    │  Reads fleet/driver on Allocate →    │   │
│  └──────────┬───────────┘    └────────────────────┬─────────────────┘   │
│             │                                     │                     │
│  ┌──────────▼─────────────────────────────────────▼─────────────────┐   │
│  │                    SQLite Local Database                          │   │
│  │  TruckSchedule · CementOrder · SavingsLedger                     │   │
│  │  Transporter · RouteCorridor · CustomerLogistics                 │   │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │   Web Dashboard  (3 pages · SSE live updates)                  │     │
│  │   /  Schedule   ·   /order-status   ·   /final                │     │
│  └────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow — Detailed

### 4.1 Truck Schedule (Excel → Allocator)

**Trigger:** Purchase department prepares Excel sheet at truck dispatch.  
**Action:** Logistics team uploads via `POST /api/schedules/import`.  
**Processing:**
- File read entirely in memory (never written to disk)
- Each row: dedup check on `truck_plate + dispatch_date`
- `upload_date` auto-stamped (UTC)
- Return corridor derived from `raw_material_type`
- Terminal records older than 30 days auto-purged

**No Odoo involvement at this stage.**

---

### 4.2 Sale Order Sync (Odoo → Allocator)

**Trigger:** APScheduler background job, every 15 minutes.  
**Odoo model:** `sale.order` where `state = 'sale'`  
**Fields read:**

| Field | Used For |
|---|---|
| `name` | SO number (SO/YYYY/NNNNN) |
| `partner_id` | Customer name and code |
| `date_order` | Order date |
| `order_line.product_id` | Cement product type |
| `order_line.product_uom_qty` | Quantity (MT) |
| `x_destination_location` | Delivery location |
| `x_truck_no` | Truck plate on the SO |
| `x_driver_name` | Driver name on the SO |
| `x_driver_mobile` | Driver phone on the SO |
| `x_driver_licence` | Driver licence on the SO |
| `x_transporter_name` | Transporter on the SO |
| `x_dispatch_status` | Pending or Dispatched |

**Destination:** Local `CementOrder` table → feeds Order Status and Final Status pages.

---

### 4.3 Invoice Sync (Odoo → Allocator)

**Trigger:** Same 15-minute sync job.  
**Odoo model:** `account.move` where `move_type = 'out_invoice'` and `state = 'posted'`  
**Fields read:** `name` (invoice number), `invoice_date`, `ref` (SO reference)  
**Used for:** Final Status page — trucks with a posted invoice show as **Dispatched**; trucks without show as **Released**.

---

### 4.4 Fleet Lookup (Odoo → Allocator — On Demand)

**Trigger:** Dispatcher clicks **Allocate →** on a truck row.  
**Odoo model:** `fleet.vehicle`  
**Query:** `license_plate = <truck_plate from TruckSchedule>`  
**Returns:** Odoo internal `id` of the vehicle record  
**Used for:** `default_vehicle_id` parameter in the Odoo SO form URL

---

### 4.5 Driver Lookup (Odoo → Allocator — On Demand)

**Trigger:** Same Allocate → click.  
**Odoo model:** `driver.master.custom`  
**Query:** `license = <driver_license_no from TruckSchedule>`  
**Returns:** Odoo internal `id` of the driver record  
**Used for:** `default_custom_driver_id` parameter in the Odoo SO form URL

---

### 4.6 SO Form Pre-Fill (Allocator → Odoo Browser Redirect)

**Trigger:** Allocate → button click.  
**Mechanism:** The allocator builds a URL and opens it in a new browser tab. No XML-RPC write occurs — the dispatcher fills in the SO and saves it directly in Odoo.

**URL structure:**
```
https://erp.lakecement.co.tz/web#
  cids=<BU_ID>
  &menu_id=<SO_MENU_ID>
  &action=<SO_ACTION_ID>
  &model=sale.order
  &view_type=form
  &default_vehicle_id=<fleet.vehicle odoo id>
  &default_custom_driver_id=<driver.master.custom odoo id>
```

If the truck plate or driver is not registered in Odoo, the form opens without pre-fill and the dispatcher is notified to fill in the fields manually.

---

## 5. Odoo Models Used

| Model | Access Type | Method | Purpose |
|---|---|---|---|
| `sale.order` | READ | `search_read` | Sync cement delivery orders |
| `sale.order.line` | READ | via `order_line` relation | Get product and quantity |
| `account.move` | READ | `search_read` | Get posted invoices for Final Status |
| `fleet.vehicle` | READ | `search_read` | Truck plate lookup for Allocate pre-fill |
| `driver.master.custom` | READ | `search_read` | Driver licence lookup for Allocate pre-fill |
| `res.partner` | READ | `search_read` | Customer name and region |

> **Note:** `purchase.order` is no longer read by the allocator for truck schedule creation. It may be read in future for PO reference linkage only (see Section 13).

---

## 6. The Allocate Button — How It Works

This is the core Odoo integration touchpoint. Understanding this flow is essential.

```
Dispatcher clicks  [Allocate →]  on a truck row
          │
          ▼
GET /api/schedules/{id}/odoo-url
          │
          ├─ XML-RPC → fleet.vehicle.search_read(license_plate = truck_plate)
          │   → returns vehicle_odoo_id  (or null if not found)
          │
          ├─ XML-RPC → driver.master.custom.search_read(license = driver_licence)
          │   → returns driver_odoo_id  (or null if not found)
          │
          └─ Builds URL:
             {ODOO_URL}/web#cids={cids}&menu_id={menu_id}&action={action_id}
             &model=sale.order&view_type=form
             [&default_vehicle_id={vehicle_odoo_id}]
             [&default_custom_driver_id={driver_odoo_id}]
          │
          ▼
Browser opens Odoo SO creation form in new tab
(pre-filled with truck plate and driver details via onchange triggers)
          │
          ▼
Dispatcher completes SO in Odoo → saves and confirms
          │
          ▼
SO appears on Order Status page within 15 minutes (next sync cycle)
```

**Critical dependency:** The `default_vehicle_id` and `default_custom_driver_id` parameters only pre-fill the form if those records exist in Odoo's fleet and driver master. Records not in Odoo must be entered manually. See Section 8 for the fleet/driver register requirements.

---

## 7. Sale Order Fields Required

The Order Status and Final Status pages depend on these fields being present and populated on Odoo Sale Orders. The Odoo team must confirm all these fields exist and are correctly mapped.

### Standard Fields (should already exist)

| Field Name | Type | Used On |
|---|---|---|
| `name` | Char | SO number — both pages |
| `date_order` | Datetime | Order date — Order Status |
| `partner_id` | Many2one | Customer — both pages |
| `state` | Selection | Order state filter |
| `order_line.product_id` | Many2one | Cement product |
| `order_line.product_uom_qty` | Float | Quantity (MT) |

### Custom / Extended Fields (confirm names with Odoo team)

| Field Name | Type | Used On | Notes |
|---|---|---|---|
| `x_destination_location` | Char / Many2one | Both pages | Delivery location name |
| `x_truck_no` | Char | Order Status | Truck plate on the SO |
| `x_driver_name` | Char | Order Status | Driver name |
| `x_driver_mobile` | Char | Order Status | Driver phone |
| `x_driver_licence` | Char | Order Status | Driver licence/ID |
| `x_transporter_name` | Char / Many2one | Order Status | Transport company |
| `x_dispatch_status` | Selection | Both pages | `pending` / `dispatched` |
| `x_invoice_no` | Char | Final Status | Invoice reference |
| `x_invoice_date` | Date | Final Status | Invoice post date |

> **Action for Odoo team:** Confirm the exact technical field names for each of the above. The sync service will fail silently on unknown field names — the WARNING log `x_dispatch_ready / x_credit_cleared fields not found` is an example of this already happening.

---

## 8. Fleet & Driver Master Requirements

Pre-filling the Odoo SO form depends entirely on trucks and drivers being registered in Odoo's fleet and driver master modules. This is the most operationally sensitive dependency.

### 8.1 fleet.vehicle

| Requirement | Detail |
|---|---|
| **Model** | `fleet.vehicle` |
| **Lookup field** | `license_plate` — must match the truck plate as entered in the Excel sheet (e.g. `T865EHY`) |
| **Coverage needed** | All transporters delivering raw materials to Kimbiji Plant |
| **Approximate volume** | ~200–400 active trucks (from transporter master data) |

**If a plate is missing:** The Allocate form opens without pre-fill. The dispatcher must enter the truck details manually in Odoo. A notification on the dashboard informs them of this.

### 8.2 driver.master.custom

| Requirement | Detail |
|---|---|
| **Model** | `driver.master.custom` |
| **Lookup field** | `license` — must match the driver licence number as entered in the Excel sheet |
| **Coverage needed** | All drivers associated with RM delivery transporters |

> **Recommendation:** The Odoo team should provide a bulk import template so the fleet/driver register can be seeded from the transporter master data files held by the allocator team. Alternatively, see Section 13 for the proposed auto-registration approach.

---

## 9. Custom Fields Required in Odoo

The following custom fields must exist in Odoo for full integration. Fields marked **Critical** block core functionality if missing.

### On `sale.order`

| Field Technical Name | Label | Type | Priority | Purpose |
|---|---|---|---|---|
| `x_truck_no` | Truck No. | Char | **Critical** | Truck plate — read by allocator for Order Status |
| `x_driver_name` | Driver Name | Char | **Critical** | Driver name — read by allocator |
| `x_driver_mobile` | Driver Mobile | Char | High | Driver phone — read by allocator |
| `x_driver_licence` | Driver Licence No. | Char | **Critical** | Driver ID — used for fleet lookup |
| `x_transporter_name` | Transporter Name | Char | **Critical** | Transporter company — read by allocator |
| `x_destination_location` | Destination Location | Char | **Critical** | Delivery location — read by allocator |
| `x_dispatch_status` | Dispatch Status | Selection (`pending`/`dispatched`) | **Critical** | Powers Order Status page status pills |
| `x_dispatch_ready` | Ready for Dispatch | Boolean | Medium | Dispatch readiness flag (currently causing sync errors — see Section 7 note) |
| `x_credit_cleared` | Credit Cleared | Boolean | Medium | Credit clearance flag |
| `x_return_load_ref` | Return Load Reference | Char | Low | Links SO to allocator truck schedule ref (IMP-XXXXXXXXXX) |

### On `fleet.vehicle`

| Field | Requirement |
|---|---|
| `license_plate` | Must be populated for all RM delivery trucks |
| `partner_id` | Linked to the transporter company (`res.partner`) |

### On `driver.master.custom`

| Field | Requirement |
|---|---|
| `license` | Driver licence number — must match Excel upload data exactly |
| `name` | Driver full name |
| `mobile` | Driver mobile number |

---

## 10. Service Account & Permissions

The allocator connects to Odoo using a dedicated service account. This account must exist in Odoo before the integration can function.

### Account Details

| Attribute | Value |
|---|---|
| **Username** | `truck_allocator_svc` |
| **Role** | Internal User (read-only on most models) |
| **MFA** | Must be disabled (XML-RPC does not support MFA flows) |
| **Active** | Must remain active at all times |

### Required Permissions

| Model | Read | Write | Create | Delete | Notes |
|---|---|---|---|---|---|
| `sale.order` | ✅ | ✅ | — | — | Write for `x_return_load_ref` only |
| `sale.order.line` | ✅ | — | — | — | |
| `account.move` | ✅ | — | — | — | Posted invoices only |
| `fleet.vehicle` | ✅ | ✅ | ✅ | — | Create if proposed write-back enabled (Section 13) |
| `driver.master.custom` | ✅ | ✅ | ✅ | — | Same |
| `purchase.order` | ✅ | — | — | — | Read for PO reference lookup only |
| `res.partner` | ✅ | — | — | — | Customer and transporter names |
| `stock.location` | ✅ | — | — | — | Warehouse IDs on startup |

---

## 11. Connection Details

```ini
ODOO_URL      = http://odoo.lakecement.co.tz:8069
ODOO_DB       = lakecement_prod
ODOO_USERNAME = truck_allocator_svc
ODOO_PASSWORD = <to be provided by Odoo team>

# SO Form Navigation IDs — must be confirmed by Odoo team
ODOO_SO_ACTION_ID  = <action id for sale.order form view>
ODOO_SO_MENU_ID    = <menu id for Sales > Orders>
ODOO_SO_CIDS       = <company/BU id for TZG>

# Warehouse Location IDs — must be confirmed by Odoo team
ODOO_PICKING_TYPE_OUTGOING_ID = <id of outgoing picking type at Kimbiji>
ODOO_LOCATION_STOCK_ID        = <id of Kimbiji stock location>
ODOO_LOCATION_CUSTOMER_ID     = <id of customer location>
```

> **Action for Odoo team:** Please provide confirmed values for all IDs above. Current defaults (2, 8, 5) are estimates and must be verified against the production database.

### Confirming the SO Action and Menu IDs

The allocator needs the exact Odoo action ID and menu ID so the Allocate → button opens the correct Sale Order form with the correct business unit context.

To find these in Odoo:
1. Enable developer mode (`Settings → Activate Developer Mode`)
2. Navigate to `Sales → Orders → Orders`
3. The URL will contain `action=<id>` and `menu_id=<id>` — copy these values

---

## 12. Reference Numbers & Formats

| Document | Format | Example | Odoo Model |
|---|---|---|---|
| Purchase Order | `LPORD/YYYY/NNNNN` | `LPORD/2026/02347` | `purchase.order.name` |
| Inward Token | `RM/YYYY/NNNNN` | `RM/2026/00009` | Custom field / picking origin |
| Gate Entry | `RM-DD/MM/YYYY-N` | `RM-02/04/2026-10` | Custom reference |
| Sale Order | `SO/YYYY/NNNNN` | `SO/2026/01246` | `sale.order.name` |
| Sales Invoice | `SI260XXXXXXX` | `SI2600012345` | `account.move.name` |
| Truck Plate (TZ) | `T###XXX` | `T865EHY` | `fleet.vehicle.license_plate` |
| Truck Plate (RW) | `RAF###X` | `RAF123A` | `fleet.vehicle.license_plate` |
| Allocator Ref | `IMP-XXXXXXXXXX` | `IMP-A3F7C2D1E8` | Internal — `x_return_load_ref` |

---

## 13. Proposed Enhancement — Write-Back on Import

This section describes a proposed integration enhancement that was discussed and is pending Odoo team review. It is **not yet implemented** and requires Odoo team input before development begins.

### The Proposal

When the Purchase department uploads an Excel sheet and new truck records are imported, the allocator would automatically push the truck and driver details into Odoo — creating or updating `fleet.vehicle` and `driver.master.custom` records. This would ensure the Allocate → form pre-fill works for every imported truck without any manual fleet registration.

### Proposed Flow

```
Excel Upload → TruckSchedule created locally
                    │
                    ▼
         For each imported row:
         ┌────────────────────────────────────────────────┐
         │ fleet.vehicle.search(license_plate=truck_plate)│
         │   → found: no action (record already exists)   │
         │   → not found: fleet.vehicle.create({          │
         │       license_plate: truck_plate,              │
         │       partner_id: transporter_partner_id       │
         │     })                                         │
         └────────────────────────────────────────────────┘
         ┌────────────────────────────────────────────────┐
         │ driver.master.custom.search(license=licence)   │
         │   → found: no action                           │
         │   → not found: driver.master.custom.create({   │
         │       license: driver_license_no,              │
         │       name: driver_name,                       │
         │       mobile: driver_phone                     │
         │     })                                         │
         └────────────────────────────────────────────────┘
```

### Questions for Odoo Team

Before this is implemented, the following must be confirmed:

1. Is `driver.master.custom` a standard Odoo module or a custom LCL development? What are the exact field names?
2. Can `fleet.vehicle` records be created via XML-RPC by the service account, or does this require a specific fleet manager role?
3. Is there a `transporter` linkage on `fleet.vehicle` (via `partner_id`) that we should populate? What is the `res.partner` lookup field for transporters?
4. Are there any mandatory fields on `fleet.vehicle` or `driver.master.custom` that would cause `create()` to fail if not supplied?
5. Should the allocator also update existing records (e.g. new driver phone number), or only create missing ones?

---

## 14. Action Items for Odoo Team

The following is a consolidated checklist of everything the Odoo team needs to action before the integration is fully operational.

### Immediate (Blocking)

| # | Action | Owner | Priority |
|---|---|---|---|
| 1 | Create service account `truck_allocator_svc` with permissions in Section 10 | Odoo Admin | **Critical** |
| 2 | Confirm SO Action ID and Menu ID for TZG business unit | Odoo Admin | **Critical** |
| 3 | Confirm `cids` value for TZG business unit | Odoo Admin | **Critical** |
| 4 | Confirm Warehouse location IDs: `ODOO_LOCATION_STOCK_ID`, `ODOO_LOCATION_CUSTOMER_ID`, `ODOO_PICKING_TYPE_OUTGOING_ID` | Odoo Admin | **Critical** |
| 5 | Confirm exact technical field names for all `x_` custom fields on `sale.order` listed in Section 7 | Odoo Developer | **Critical** |

### High Priority

| # | Action | Owner | Priority |
|---|---|---|---|
| 6 | Ensure `fleet.vehicle.license_plate` is populated for all active RM delivery trucks (~200–400 trucks) | Odoo / Logistics | High |
| 7 | Ensure `driver.master.custom` records exist for all active RM drivers | Odoo / Logistics | High |
| 8 | Confirm whether `driver.master.custom` is a standard or custom module; provide field schema | Odoo Developer | High |
| 9 | Remove or disable `x_dispatch_ready` and `x_credit_cleared` field references if these fields do not exist (currently causing WARNING logs every 15 min) | Odoo Developer | High |

### For Discussion

| # | Action | Owner | Priority |
|---|---|---|---|
| 10 | Review and approve the proposed write-back design in Section 13 | Odoo Developer + Digital Team | Medium |
| 11 | Confirm if `purchase.order` PO Reference linkage to `TruckSchedule` is desired (for audit trail) | Business / Odoo Admin | Medium |
| 12 | Agree on the `x_return_load_ref` field naming convention and populate it when dispatcher completes SO | Odoo Developer | Low |

---

## Appendix A — Raw Material Item Codes

| Item Code | Material | Typical Origin | Return Corridor |
|---|---|---|---|
| `RM000001` | Coal | Kyela / Mbeya / Songea | SOUTHERN_HIGHLANDS |
| `RM000003` | Gypsum | Lindi / Dar es Salaam | SOUTHERN_COAST / LOCAL |
| `RM000004` | Iron Ore | Dodoma | CENTRAL |
| `RM000014` | Clinker SPG | Tanga / Mtwara | NORTHERN / SOUTHERN_COAST |

## Appendix B — Return Corridors

| Corridor | Origin Region | Key Route |
|---|---|---|
| NORTHERN | Tanga | Tanga → Segera → Chalinze → Kimbiji |
| SOUTHERN_HIGHLANDS | Mbeya / Kyela | Kyela → Mbeya → Iringa → Morogoro → Kimbiji |
| CENTRAL | Dodoma | Dodoma → Morogoro → Chalinze → Kimbiji |
| SOUTHERN_COAST | Lindi / Mtwara | Kiranjeranje → Kibiti → Rufiji → Kimbiji |
| LOCAL | Dar es Salaam | DSM → Kimbiji |

## Appendix C — Known Integration Errors (Current)

| Error | Location | Cause | Fix Required |
|---|---|---|---|
| `ValueError: Invalid field 'x_dispatch_ready' on model 'sale.order'` | `odoo_sync.py` every 15 min | Field does not exist in Odoo | Odoo team to either create the field or confirm alternative field name |
| `ValueError: Invalid field 'x_credit_cleared' on model 'sale.order'` | `odoo_sync.py` every 15 min | Same as above | Same fix |

---

*Return Truck Allocator — Odoo Integration Technical Specification v2.0*  
*Lake Cement Limited (Nyati Cement) · Kimbiji Plant · 19 May 2026*  
*Prepared by Digital Team · razakmbaga3@gmail.com*
