"""
app/routers/orders.py — CementOrder API endpoints.

GET /api/orders                     — All synced orders
GET /api/orders/unallocated         — Orders awaiting a truck
GET /api/orders/near-ready          — Near-ready (not dispatch_ready but eligible by ETA)
GET /api/orders/by-corridor/{name}  — Orders filtered by corridor
POST /api/orders/sync               — Force full Odoo sync
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CementOrder, OrderAllocationStatus
from app.schemas.cement_order import CementOrderListItem, CementOrderRead

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=list[CementOrderListItem])
async def list_orders(
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CementOrder)
        .order_by(CementOrder.deadline_dt.asc().nulls_last())
        .limit(limit)
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/unallocated", response_model=list[CementOrderListItem])
async def list_unallocated(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CementOrder)
        .where(
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
            CementOrder.return_load_eligible == True,
        )
        .order_by(CementOrder.urgency_score.desc())
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/near-ready", response_model=list[CementOrderListItem])
async def list_near_ready(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CementOrder)
        .where(
            CementOrder.near_ready == True,
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
        )
        .order_by(CementOrder.near_ready_eta.asc().nulls_last())
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


@router.get("/by-corridor/{corridor}", response_model=list[CementOrderListItem])
async def list_by_corridor(corridor: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CementOrder)
        .where(
            CementOrder.delivery_corridor == corridor.upper(),
            CementOrder.allocation_status == OrderAllocationStatus.UNALLOCATED,
        )
        .order_by(CementOrder.urgency_score.desc())
    )
    return [CementOrderListItem.model_validate(o) for o in result.scalars().all()]


# ── GET /api/orders/live-status — Order Status page ──────────────────────────

@router.get("/live-status")
async def get_live_status(days: int = Query(7, ge=1, le=90)):
    """
    Fetch recent Sale Orders directly from Odoo for the Order Status dashboard page.
    Returns: date, customer, location, transporter, driver, license, qty, status.
    """
    import asyncio as _aio
    import re
    from datetime import datetime, timedelta, timezone
    from app.services.odoo_sync import OdooClient
    from app.config import get_settings

    s = get_settings()
    client = OdooClient()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

    uid = await _aio.to_thread(client._uid_or_auth)
    models = client._models()

    rows = await _aio.to_thread(
        models.execute_kw,
        s.odoo_db, uid, s.odoo_password,
        "sale.order", "search_read",
        [[["date_order", ">=", cutoff], ["state", "not in", ["cancel"]]]],
        {
            "fields": [
                "name", "date_order", "partner_id", "custom_location_id",
                "transporter_name", "custom_driver_name", "driver_license",
                "driver_mobile", "qty_mt_ordered", "state",
            ],
            "order": "date_order desc",
            "limit": 50,
        },
    )

    STATUS = {
        "draft": "Pending", "sent": "Pending",
        "sale": "Pending", "done": "Dispatched", "cancel": "Cancelled",
    }

    result = []
    for r in rows:
        driver      = r["custom_driver_name"] or None
        location    = r["custom_location_id"][1] if r["custom_location_id"] else None
        transporter = r["transporter_name"] or None
        # Skip SOs with no truck details assigned yet — not actionable for dispatch
        if not driver and not transporter and not location:
            continue
        result.append({
            "so_name":      r["name"],
            "date_order":   r["date_order"],
            "customer":     r["partner_id"][1] if r["partner_id"] else None,
            "location":     location,
            "transporter":  transporter,
            "driver":       driver,
            "license":      r["driver_license"] or None,
            "driver_phone": r["driver_mobile"] or None,
            "qty_mt":       r["qty_mt_ordered"] or 0,
            "status":       STATUS.get(r["state"], r["state"]),
        })
    return result


# ── GET /api/orders/live-status/export — Excel download ──────────────────────

@router.get("/live-status/export")
async def export_live_status(
    days: int = Query(7, ge=1, le=90),
    status: str = Query("", alias="status"),
):
    """Export Order Status data as branded Excel file."""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    from datetime import datetime
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    rows = await get_live_status(days=days)
    if status:
        rows = [r for r in rows if r.get("status") == status]

    wb = Workbook()
    ws = wb.active
    ws.title = "Order Status"

    NAVY, ORANGE, WHITE, GRAY = "173158", "F49545", "FFFFFF", "F5F5F5"
    hdr_font   = Font(bold=True, color=WHITE, size=10)
    hdr_fill   = PatternFill("solid", fgColor=NAVY)
    hdr_align  = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin       = Side(style="thin", color="D3D3D3")
    border     = Border(left=thin, right=thin, top=thin, bottom=thin)
    center     = Alignment(horizontal="center", vertical="center")
    left       = Alignment(horizontal="left",   vertical="center")
    right      = Alignment(horizontal="right",  vertical="center")

    ws.merge_cells("A1:J1")
    c = ws["A1"]
    c.value = "NYATI CEMENT — ORDER STATUS REPORT"
    c.font  = Font(bold=True, color=WHITE, size=13)
    c.fill  = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:J2")
    s = ws["A2"]
    s.value = f"Period: Last {days} days  |  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}"
    s.font  = Font(color=ORANGE, size=9)
    s.fill  = PatternFill("solid", fgColor="EEF2F7")
    s.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 16

    headers = ["SO No.", "Date", "Customer", "Location", "Transporter",
               "Driver", "Phone", "Licence", "Qty (MT)", "Status"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.font = hdr_font; cell.fill = hdr_fill
        cell.alignment = hdr_align; cell.border = border
    ws.row_dimensions[3].height = 20

    def fmt_date(dt):
        if not dt: return ""
        try: return str(dt)[:10]
        except: return str(dt)

    aligns = [center, center, left, left, left, left, center, center, right, center]
    for i, r in enumerate(rows):
        rn   = i + 4
        fill = PatternFill("solid", fgColor=GRAY if i % 2 == 0 else WHITE)
        vals = [
            r.get("so_name") or "",
            fmt_date(r.get("date_order")),
            r.get("customer") or "",
            r.get("location") or "",
            r.get("transporter") or "",
            r.get("driver") or "",
            r.get("driver_phone") or "",
            r.get("license") or "",
            r.get("qty_mt") or 0,
            r.get("status") or "",
        ]
        for col, (val, aln) in enumerate(zip(vals, aligns), 1):
            cell = ws.cell(row=rn, column=col, value=val)
            cell.fill = fill; cell.alignment = aln
            cell.border = border; cell.font = Font(size=9)
            if col == 10:
                color = NAVY if val == "Dispatched" else ORANGE
                cell.font = Font(size=9, bold=True, color=color)
        ws.row_dimensions[rn].height = 15

    for col, w in enumerate([14,12,22,18,20,18,14,14,10,12], 1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "A4"

    buf = BytesIO()
    wb.save(buf); buf.seek(0)
    fname = f"order-status-{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── GET /api/orders/final-status — Final Status page ─────────────────────────

@router.get("/final-status")
async def get_final_status(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch SOs with invoice data from Odoo + PO reference from local TruckSchedule.
    Returns: po_ref, so_name, transporter, driver, location, qty, invoice_no,
             invoice_date, status (Dispatched/Released), remark.
    """
    import asyncio as _aio
    import re
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select as sa_select
    from app.models import TruckSchedule
    from app.services.odoo_sync import OdooClient
    from app.config import get_settings

    s = get_settings()
    client = OdooClient()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

    uid = await _aio.to_thread(client._uid_or_auth)
    models = client._models()

    # 1. Fetch SOs
    so_rows = await _aio.to_thread(
        models.execute_kw,
        s.odoo_db, uid, s.odoo_password,
        "sale.order", "search_read",
        [[["date_order", ">=", cutoff], ["state", "not in", ["cancel", "draft"]]]],
        {
            "fields": [
                "name", "date_order", "partner_id", "custom_location_id",
                "transporter_name", "custom_driver_name", "driver_license",
                "qty_mt_ordered", "state", "invoice_ids", "vehicle",
                "client_order_ref", "note",
            ],
            "order": "date_order desc",
            "limit": 50,
        },
    )

    # 2. Batch-fetch all invoices in one call
    all_inv_ids = [inv_id for r in so_rows for inv_id in (r["invoice_ids"] or [])]
    inv_map: dict[int, dict] = {}
    if all_inv_ids:
        inv_rows = await _aio.to_thread(
            models.execute_kw,
            s.odoo_db, uid, s.odoo_password,
            "account.move", "read",
            [list(set(all_inv_ids))],
            {"fields": ["id", "name", "invoice_date", "state", "payment_state"]},
        )
        inv_map = {i["id"]: i for i in inv_rows}

    # 3. Look up PO references from local DB by truck plate
    plates = [r["vehicle"] for r in so_rows if r.get("vehicle")]
    po_by_plate: dict[str, str] = {}
    if plates:
        result = await db.execute(
            sa_select(TruckSchedule.truck_plate, TruckSchedule.odoo_po_name).where(
                TruckSchedule.truck_plate.in_(plates),
                TruckSchedule.odoo_po_name.isnot(None),
            )
        )
        po_by_plate = {row.truck_plate: row.odoo_po_name for row in result}

    def strip_html(html: str) -> str:
        if not html:
            return ""
        return re.sub(r"<[^>]+>", "", html).strip()

    def so_status(r: dict) -> str:
        inv_ids = r.get("invoice_ids") or []
        posted = any(inv_map.get(i, {}).get("state") == "posted" for i in inv_ids)
        if posted:
            return "Dispatched"
        return "Released"

    def clean_po_ref(r: dict) -> str | None:
        # Prefer internal PO name matched by truck plate
        plate_ref = po_by_plate.get(r.get("vehicle") or "", None)
        if plate_ref:
            return plate_ref
        raw = (r.get("client_order_ref") or "").strip()
        if not raw:
            return None
        # Reject tender descriptions: too long or multi-word (not a compact reference code)
        if len(raw) > 40 or raw.count(" ") > 3:
            return None
        return raw

    output = []
    for r in so_rows:
        inv_ids = r.get("invoice_ids") or []
        first_inv = inv_map.get(inv_ids[0]) if inv_ids else None
        driver    = r["custom_driver_name"] or None
        location  = r["custom_location_id"][1] if r["custom_location_id"] else None
        transporter = r["transporter_name"] or None

        # Skip rows with no operational data (no truck details and no invoice)
        if not driver and not location and not transporter and not first_inv:
            continue

        output.append({
            "po_ref":        clean_po_ref(r),
            "so_name":       r["name"],
            "transporter":   transporter,
            "driver":        driver,
            "license":       r["driver_license"] or None,
            "location":      location,
            "qty_mt":        r["qty_mt_ordered"] or 0,
            "invoice_no":    first_inv["name"] if first_inv else None,
            "invoice_date":  first_inv["invoice_date"] if first_inv else None,
            "status":        so_status(r),
            "remark":        strip_html(r.get("note") or ""),
            "date_order":    r["date_order"],
        })
    return output


# ── GET /api/orders/final-status/export — Excel download ─────────────────────

@router.get("/final-status/export")
async def export_final_status(
    days: int = Query(30, ge=1, le=90),
    status: str = Query("", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    """Export Final Status data as branded Excel file."""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    from datetime import datetime, timedelta, timezone
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    import asyncio as _aio
    from app.services.odoo_sync import OdooClient
    from app.config import get_settings

    # Reuse the same data fetch as get_final_status
    rows = (await get_final_status(days=days, db=db))

    if status:
        rows = [r for r in rows if r.get("status") == status]

    # Build Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Final Status"

    NAVY   = "173158"
    ORANGE = "F49545"
    WHITE  = "FFFFFF"
    GRAY   = "F5F5F5"

    header_font    = Font(bold=True, color=WHITE, size=10)
    header_fill    = PatternFill("solid", fgColor=NAVY)
    header_align   = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_side      = Side(style="thin", color="D3D3D3")
    thin_border    = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    center_align   = Alignment(horizontal="center", vertical="center")
    left_align     = Alignment(horizontal="left",   vertical="center")
    right_align    = Alignment(horizontal="right",  vertical="center")

    # Title row
    ws.merge_cells("A1:J1")
    title_cell = ws["A1"]
    title_cell.value = f"NYATI CEMENT — FINAL STATUS REPORT"
    title_cell.font  = Font(bold=True, color=WHITE, size=13)
    title_cell.fill  = PatternFill("solid", fgColor=NAVY)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # Sub-title
    ws.merge_cells("A2:J2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Period: Last {days} days  |  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}"
    sub_cell.font  = Font(color=ORANGE, size=9)
    sub_cell.fill  = PatternFill("solid", fgColor="EEF2F7")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 16

    # Headers
    headers = ["PO Ref", "SO No.", "Transporter", "Driver", "Location",
               "Qty (MT)", "Invoice No.", "Invoice Date", "Status", "Remark"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align
        cell.border    = thin_border
    ws.row_dimensions[3].height = 20

    # Data rows
    for i, r in enumerate(rows):
        row_num = i + 4
        fill = PatternFill("solid", fgColor=GRAY if i % 2 == 0 else WHITE)
        values = [
            r.get("po_ref") or "",
            r.get("so_name") or "",
            r.get("transporter") or "",
            r.get("driver") or "",
            r.get("location") or "",
            r.get("qty_mt") or 0,
            r.get("invoice_no") or "",
            r.get("invoice_date") or "",
            r.get("status") or "",
            r.get("remark") or "",
        ]
        aligns = [center_align, center_align, left_align, left_align, left_align,
                  right_align, center_align, center_align, center_align, left_align]
        for col, (val, aln) in enumerate(zip(values, aligns), 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.fill      = fill
            cell.alignment = aln
            cell.border    = thin_border
            cell.font      = Font(size=9)
            if col == 9:  # Status column — color by value
                if val == "Released":
                    cell.font = Font(size=9, bold=True, color=ORANGE)
                elif val == "Dispatched":
                    cell.font = Font(size=9, bold=True, color=NAVY)
        ws.row_dimensions[row_num].height = 15

    # Column widths
    col_widths = [14, 16, 22, 18, 20, 10, 16, 14, 12, 30]
    for col, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.freeze_panes = "A4"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"final-status-{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── GET /api/orders/{order_id} ────────────────────────────────────────────────

@router.get("/{order_id}", response_model=CementOrderRead)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    result = await db.execute(select(CementOrder).where(CementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return CementOrderRead.model_validate(order)


@router.post("/sync")
async def sync_orders(db: AsyncSession = Depends(get_db)):
    """Force a full Odoo sync of purchase orders + sale orders."""
    from app.services.odoo_sync import OdooSyncService
    svc = OdooSyncService(db)
    stats = await svc.run_full_sync()
    return {"ok": True, "stats": stats}
