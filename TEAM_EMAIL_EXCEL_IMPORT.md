# Team Email — Excel Import Workflow Change

---

**To:** Logistics Team, Purchase Department, Transport Manager, Operations Manager  
**From:** Digital Team  
**Date:** 18 May 2026  
**Subject:** Return Truck Allocator — Important Update: How Trucks Now Enter the System

---

Dear Team,

Following a meeting held today with the Purchase Head, we are pleased to announce a significant improvement to the **Nyati Cement Return Truck Allocator** — one that will make the Schedule page faster to use and far more responsive to ground-level dispatch activity.

---

**What Has Changed**

From today, inbound truck records on the Schedule page will no longer come from Odoo Purchase Orders. Instead, truck data will be entered through an **Excel upload** prepared by the Purchase department.

This change was requested because the Purchase team has confirmed dispatch details — transporter, driver, truck plate, and date of departure from the supplier — at the point of dispatch, which is earlier and more accurate than the Odoo PO confirmation cycle.

---

**How It Works — Step by Step**

**Purchase Department (action required):**
1. As soon as a transporter is dispatched with raw materials from the supplier, prepare an Excel sheet with the following columns:

   | Column | Required? |
   |---|---|
   | Truck No. (plate) | Yes |
   | Date of Dispatch | Yes |
   | Transporter Name | Yes |
   | Driver Name | Yes |
   | Driver Mobile | Yes |
   | Driver Licence No. | Yes |
   | Material (Clinker / Coal / Gypsum / Iron Ore) | Yes |
   | Location / Origin Region | Yes |
   | PO Ref | Optional |
   | Qty (MT) | Optional (defaults to 30 MT) |

2. Send the Excel file to the Logistics team (or upload it directly if you have dashboard access).

   > The column headers can be in any capitalisation — the system recognises common variants automatically (e.g. "Truck No", "Vehicle", "Plate" all work for the truck plate field).

**Logistics Team (action required):**
1. Open the Schedule page on the dashboard.
2. Click the **↑ Import Excel** button (top-right of the Inbound Trucks card).
3. Select the Excel file received from Purchase.
4. A notification will confirm how many trucks were added (e.g. _"Imported 8 trucks · 2 skipped"_).
5. The truck list updates immediately — no page refresh needed.

**Re-uploading is safe.** If Purchase sends an updated file with the same trucks, duplicates are skipped automatically. You will not create double entries.

---

**What's New on the Schedule Page**

Along with this change, the following improvements have been made to the Schedule page:

- **Date of Dispatch** — now visible as a column in the truck table (from the Excel sheet)
- **Date of Upload** — automatically recorded by the system when the file is imported
- **Dealer No. column removed** — no longer required
- **Filter bar** — search trucks by plate, driver, or transporter; filter by material or corridor; live truck count shown as a badge
- **Delete rows** — individual or bulk deletion with confirmation, for cleaning up incorrect entries

---

**What Stays the Same**

- The **Allocate →** button works exactly as before — clicking it opens the Odoo Sale Order form pre-filled with the truck details
- The **Order Status** and **Final Status** pages continue to pull data from Odoo (no change)
- The **⟳ Sync Odoo** button remains for refreshing Odoo-sourced data

---

**Who Needs to Act**

| Department | Action |
|---|---|
| **Purchase** | Begin preparing and sharing the Excel dispatch sheet for each outgoing truck load |
| **Logistics** | Upload the sheet via ↑ Import Excel as soon as it is received |
| **Transport Manager** | No action required — dashboard usage is unchanged |
| **IT / Digital** | System is live as of today. No further deployment required. |

---

**Questions or Issues**

If you encounter any problems with the import (e.g. column headers not recognised, import errors), please contact the Digital Team at **digital@lakecement.co.tz** or reach out on the internal WhatsApp group.

We will also be available to walk through the new workflow with any team member who needs a demonstration.

Thank you for your cooperation.

Kind regards,  
**Digital Team**  
Lake Cement Limited (Nyati Cement)  
Kimbiji Plant, Dar es Salaam

---

*This email relates to app version 3.1.0 deployed on 18 May 2026.*
