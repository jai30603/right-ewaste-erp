import io
import os
import logging
logger = logging.getLogger(__name__)
from datetime import date, timedelta
import calendar
from urllib.parse import urlparse
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, Response, abort,
)
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from backend.common.utils.date_utils import get_filter_date_range
from backend.common.utils.format_utils import get_report_filename
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info
from backend.services.pdf_service import render_to_pdf, send_pdf_response, render_url_to_pdf
from backend.services.sales_service import check_stock_available, validate_status_transition

from repositories.sales_repository import (
    get_all_invoices,
    get_invoice_by_id,
    get_invoice_items,
    create_sales_invoice,
    update_sales_invoice,
    delete_sales_invoice,
    get_sales_register_rows,
    get_monthly_analytics,
    get_top_customers,
    get_top_materials,
    increment_print_count,
    increment_pdf_download_count,
)
from repositories.party_repository import get_all_parties, get_party_by_id
from repositories.material_repository import get_all_materials
from repositories.company_repository import get_company
from repositories.activity_log_repository import log_activity

sales_bp = Blueprint("sales", __name__)

PAYMENT_MODES = ["Cash", "NEFT", "RTGS", "UPI", "Cheque", "Credit"]


# ── V2 Stock & Status Transition Validation ───────────────────────────────



# ── Helpers ───────────────────────────────────────────────────────────────────

def _invoice_context(invoice_id):
    """Shared data bundle for view + PDF routes."""
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        abort(404)
    invoice = dict(invoice)
    items   = get_invoice_items(invoice_id)
    party   = get_party_by_id(invoice["party_id"])
    company = get_company()
    
    is_intra = True
    if invoice.get("igst", 0.0) > 0.0:
        is_intra = False
    elif invoice.get("cgst", 0.0) > 0.0 or invoice.get("sgst", 0.0) > 0.0:
        is_intra = True
    else:
        comp_state = str(company["state_code"] if company else "").strip()
        pos_state = str(invoice.get("shipping_state_code") or invoice.get("billing_state_code") or (party["state_code"] if party else "")).strip()
        if comp_state and pos_state:
            is_intra = (comp_state == pos_state)
            
    # Build HSN-wise tax breakdown
    breakdown = {}
    for it in items:
        item = dict(it)
        hsn = item.get("hsn_sac") or item.get("hsn_code") or "—"
        rate = float(item.get("gst_percentage") if item.get("gst_percentage") is not None else 18.0)
        taxable = float(item.get("amount") or 0.0)
        cgst = float(item.get("cgst") or 0.0)
        sgst = float(item.get("sgst") or 0.0)
        igst = float(item.get("igst") or 0.0)
        
        # fallback for old invoices
        if cgst == 0.0 and sgst == 0.0 and igst == 0.0:
            total_gst = taxable * rate / 100.0
            if is_intra:
                cgst = round(total_gst / 2.0, 2)
                sgst = round(total_gst / 2.0, 2)
                igst = 0.0
            else:
                cgst = 0.0
                sgst = 0.0
                igst = round(total_gst, 2)
                
        hsn_str = str(hsn or "—").strip()
        key = (hsn_str, rate)
        if key not in breakdown:
            breakdown[key] = {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0}
        breakdown[key]["taxable"] += taxable
        breakdown[key]["cgst"] += cgst
        breakdown[key]["sgst"] += sgst
        breakdown[key]["igst"] += igst
        
    tax_breakdown = []
    for (hsn_val, rate_val), vals in breakdown.items():
        tax_breakdown.append({
            "hsn": hsn_val,
            "rate": rate_val,
            "taxable": round(vals["taxable"], 2),
            "cgst": round(vals["cgst"], 2),
            "sgst": round(vals["sgst"], 2),
            "igst": round(vals["igst"], 2),
            "total_tax": round(vals["cgst"] + vals["sgst"] + vals["igst"], 2)
        })
        
    return dict(
        invoice  = invoice,
        items    = items,
        party    = party,
        company  = company,
        is_intra = is_intra,
        tax_breakdown = tax_breakdown
    )


# ── List ──────────────────────────────────────────────────────────────────────

def get_filter_date_range(date_filter, year, month, start_date_str, end_date_str):
    start_date = None
    end_date = None
    
    today = date.today()
    
    if date_filter == "today":
        start_date = today.isoformat()
        end_date = today.isoformat()
    elif date_filter == "this_week":
        start_date = (today - timedelta(days=today.weekday())).isoformat()
        end_date = today.isoformat()
    elif date_filter == "this_month":
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()
    elif date_filter == "last_6_months":
        start_date = (today - timedelta(days=180)).isoformat()
        end_date = today.isoformat()
    elif date_filter == "custom":
        if start_date_str:
            start_date = start_date_str
        if end_date_str:
            end_date = end_date_str
            
    if year and year != "all":
        y = int(year)
        if month and month != "all":
            m = int(month)
            _, last_day = calendar.monthrange(y, m)
            start_date = date(y, m, 1).isoformat()
            end_date = date(y, m, last_day).isoformat()
        else:
            start_date = date(y, 1, 1).isoformat()
            end_date = date(y, 12, 31).isoformat()
    elif month and month != "all":
        y = today.year
        m = int(month)
        _, last_day = calendar.monthrange(y, m)
        start_date = date(y, m, 1).isoformat()
        end_date = date(y, m, last_day).isoformat()
        
    return start_date, end_date


def get_report_filename(base_name, extension, date_filter, year, month, start_date, end_date):
    suffix = "all"
    
    if year and year != "all":
        if month and month != "all":
            suffix = f"{year}_{month}"
        else:
            suffix = f"{year}"
    elif month and month != "all":
        suffix = f"month_{month}"
    elif date_filter and date_filter != "all":
        if date_filter == "custom":
            start = start_date if start_date else "start"
            end = end_date if end_date else "end"
            suffix = f"{start}_to_{end}"
        else:
            suffix = date_filter
            
    return f"{base_name}_{suffix}.{extension}"



@sales_bp.route("/sales")
def sales():
    q = request.args.get("q", "").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    customer_id = request.args.get("customer_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()
    category = request.args.get("category", "all").strip()
    created_by = request.args.get("created_by", "all").strip()
    state = request.args.get("state", "all").strip()
    gst_type = request.args.get("gst_type", "all").strip()
    status = request.args.get("status", "all").strip()
    payment_mode = request.args.get("payment_mode", "all").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()
    
    # Advanced Filters
    gstin = request.args.get("gstin", "all").strip()
    shipping_state_code = request.args.get("shipping_state_code", "all").strip()
    dispatch_location = request.args.get("dispatch_location", "all").strip()
    hsn_sac = request.args.get("hsn_sac", "all").strip()
    item_type = request.args.get("item_type", "all").strip()
    uom = request.args.get("uom", "all").strip()
    gst_rate = request.args.get("gst_rate", "all").strip()
    tcs_applicable = request.args.get("tcs_applicable", "all").strip()
    transporter = request.args.get("transporter", "all").strip()
    vehicle_number = request.args.get("vehicle_number", "all").strip()
    company_bank_account_number = request.args.get("company_bank_account_number", "all").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    invoices = get_all_invoices(
        start_date=parsed_start,
        end_date=parsed_end,
        search_query=q,
        financial_year=financial_year,
        month=month,
        customer_id=customer_id,
        material_id=material_id,
        state=state,
        gst_type=gst_type,
        status=status,
        payment_mode=payment_mode,
        sort_by=sort_by,
        category=category,
        created_by=created_by,
        gstin=gstin,
        shipping_state_code=shipping_state_code,
        dispatch_location=dispatch_location,
        hsn_sac=hsn_sac,
        item_type=item_type,
        uom=uom,
        gst_rate=gst_rate,
        tcs_applicable=tcs_applicable,
        transporter=transporter,
        vehicle_number=vehicle_number,
        company_bank_account_number=company_bank_account_number
    )

    from repositories.party_repository import get_all_parties, get_active_party_states
    from repositories.material_repository import get_all_materials
    from repositories.inventory_repository import get_all_categories
    from database import get_connection

    parties = [p for p in get_all_parties() if p["party_type"] in ("CUSTOMER", "BOTH")]
    materials = get_all_materials()
    states = get_active_party_states()
    categories_list = get_all_categories()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT created_by FROM sales_invoice WHERE created_by IS NOT NULL AND created_by != ''")
    creators = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT id, location_name FROM dispatch_location")
    dispatch_locations = [{"id": r[0], "name": r[1]} for r in cursor.fetchall()]
    
    cursor.execute("SELECT id, bank_name, account_number FROM company_bank")
    bank_accounts = [{"id": r[0], "bank_name": r[1], "account_number": r[2]} for r in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT hsn_sac FROM sales_invoice_item WHERE hsn_sac IS NOT NULL AND hsn_sac != ''")
    hsns = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT uom FROM sales_invoice_item WHERE uom IS NOT NULL AND uom != ''")
    uoms = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT gst_percentage FROM sales_invoice_item WHERE gst_percentage IS NOT NULL ORDER BY gst_percentage ASC")
    gst_rates = [float(r[0]) for r in cursor.fetchall()]
    conn.close()

    # Count how many non-default filters are active
    active_filters_count = sum([
        bool(q),
        date_filter not in ("", "all"),
        financial_year not in ("", "all"),
        month not in ("", "all"),
        bool(start_date),
        bool(end_date),
        customer_id not in ("", "all"),
        material_id not in ("", "all"),
        category not in ("", "all"),
        created_by not in ("", "all"),
        state not in ("", "all"),
        gst_type not in ("", "all"),
        status not in ("", "all"),
        payment_mode not in ("", "all"),
        gstin not in ("", "all"),
        shipping_state_code not in ("", "all"),
        dispatch_location not in ("", "all"),
        hsn_sac not in ("", "all"),
        item_type not in ("", "all"),
        uom not in ("", "all"),
        gst_rate not in ("", "all"),
        tcs_applicable not in ("", "all"),
        transporter not in ("", "all"),
        vehicle_number not in ("", "all"),
        company_bank_account_number not in ("", "all"),
    ])

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(invoices)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_invoices = invoices[offset : offset + per_page]

    return render_template(
        "sales/sales.html",
        invoices=paginated_invoices,
        parties=parties,
        materials=materials,
        states=states,
        categories_list=categories_list,
        creators=creators,
        dispatch_locations=dispatch_locations,
        bank_accounts=bank_accounts,
        hsns=hsns,
        uoms=uoms,
        gst_rates=gst_rates,
        q=q,
        date_filter=date_filter,
        year=year,
        financial_year=financial_year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        material_id=material_id,
        category=category,
        created_by=created_by,
        state=state,
        gst_type=gst_type,
        status=status,
        payment_mode=payment_mode,
        sort_by=sort_by,
        gstin=gstin,
        shipping_state_code=shipping_state_code,
        dispatch_location=dispatch_location,
        hsn_sac=hsn_sac,
        item_type=item_type,
        uom=uom,
        gst_rate=gst_rate,
        tcs_applicable=tcs_applicable,
        transporter=transporter,
        vehicle_number=vehicle_number,
        company_bank_account_number=company_bank_account_number,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        today=date.today().isoformat(),
        active_filters_count=active_filters_count,
    )



@sales_bp.route("/sales/export")
def export_sales():
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    invoices = get_all_invoices(parsed_start, parsed_end)

    invoice_list = []
    for inv in invoices:
        invoice_list.append(dict(inv))

    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Invoices"
    ws.views.sheetView[0].showGridLines = True

    title_font = Font(name="Calibri", size=16, bold=True, color="1B5E20")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    border_thin = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    ws.merge_cells("A1:J1")
    ws["A1"] = "Right Ewaste Recycle Pvt. Ltd. - Sales Invoices Report"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    headers = [
        "Invoice No.", "Date", "Customer", "Payment Mode", 
        "Transporter", "Vehicle No.", "Items Count", "Status", 
        "Subtotal (₹)", "Grand Total (₹)"
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = border_thin
    ws.row_dimensions[3].height = 25

    row_num = 4
    for inv in invoice_list:
        ws.cell(row=row_num, column=1, value=inv["invoice_number"]).alignment = center_align
        ws.cell(row=row_num, column=2, value=inv["invoice_date"]).alignment = center_align
        ws.cell(row=row_num, column=3, value=inv["company_name"] or "—").alignment = left_align
        ws.cell(row=row_num, column=4, value=inv["payment_mode"] or "—").alignment = center_align
        ws.cell(row=row_num, column=5, value=inv["transporter"] or "—").alignment = left_align
        ws.cell(row=row_num, column=6, value=inv["vehicle_number"] or "—").alignment = center_align
        ws.cell(row=row_num, column=7, value=inv["item_count"]).alignment = center_align
        ws.cell(row=row_num, column=8, value=inv["status"]).alignment = center_align

        cell_sub = ws.cell(row=row_num, column=9, value=inv["subtotal"])
        cell_sub.number_format = '#,##0.00'
        cell_sub.alignment = right_align

        cell_grand = ws.cell(row=row_num, column=10, value=inv["grand_total"])
        cell_grand.number_format = '#,##0.00'
        cell_grand.alignment = right_align

        for col_idx in range(1, 11):
            ws.cell(row=row_num, column=col_idx).border = border_thin

        ws.row_dimensions[row_num].height = 20
        row_num += 1

    for col_idx in range(1, 11):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row in range(2, row_num):
            val = ws.cell(row=row, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_data = buffer.getvalue()

    filename = get_report_filename("sales_invoices_report", "xlsx", date_filter, year, month, start_date, end_date)
    return Response(
        xlsx_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(xlsx_data),
        }
    )


@sales_bp.route("/sales/export/pdf")
def export_sales_pdf():
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    invoices = get_all_invoices(parsed_start, parsed_end)

    total_amount = sum(float(inv["grand_total"] or 0) for inv in invoices)
    today_str = date.today().strftime("%d-%b-%Y")

    pdf_bytes = render_to_pdf(
        "reports/sales_report_pdf.html",
        {
            "invoices": invoices,
            "total_amount": total_amount,
            "today_str": today_str,
            "date_filter": date_filter,
            "year": year,
            "month": month,
            "start_date": start_date,
            "end_date": end_date
        }
    )

    filename = get_report_filename("sales_invoices_report", "pdf", date_filter, year, month, start_date, end_date)
    return send_pdf_response(pdf_bytes, filename)


# ── Add ───────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales/add", methods=["GET", "POST"])
def add_sales_invoice():
    parties   = [p for p in get_all_parties() if p["party_type"] in ("CUSTOMER", "BOTH")]
    materials = get_all_materials()
    company   = get_company()
    company_state_code = company["state_code"] if company else ""

    # Fetch bank accounts
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_bank WHERE is_active = 1")
    bank_accounts = [dict(r) for r in cursor.fetchall()]
    
    # Fetch dispatch locations
    cursor.execute("SELECT * FROM dispatch_location WHERE is_active = 1")
    dispatch_locations = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if request.method == "POST":
        errors = _validate_header(request.form)

        material_ids    = request.form.getlist("material_id[]")
        qtys            = request.form.getlist("qty[]")
        weights         = request.form.getlist("weight[]")
        rates           = request.form.getlist("rate[]")
        amounts         = request.form.getlist("amount[]")
        gst_percentages = request.form.getlist("gst_percentage[]")
        item_types      = request.form.getlist("item_type[]")
        descriptions    = request.form.getlist("description[]")
        hsn_sacs        = request.form.getlist("hsn_sac[]")
        uoms            = request.form.getlist("uom[]")
        item_references = request.form.getlist("item_reference[]")

        items = []
        for i in range(len(material_ids)):
            mid_str = material_ids[i].strip() if i < len(material_ids) else ""
            mid = int(mid_str) if mid_str else 0
            
            # Fetch material tracking type
            tracking_type = "BOTH"
            if mid > 0:
                from repositories.material_repository import get_material_by_id
                mat = get_material_by_id(mid)
                tracking_type = mat["tracking_type"] if mat else "BOTH"
                
            qty_val = float(qtys[i] or 0) if i < len(qtys) else 0.0
            weight_val = float(weights[i] or 0) if i < len(weights) else 0.0
            item_type_val = item_types[i].strip() if i < len(item_types) else "Goods"
            rate_val = float(rates[i] or 0) if i < len(rates) else 0.0

            if qty_val < 0 or weight_val < 0 or rate_val < 0:
                errors["items"] = "Negative quantity, weight, or rate is not allowed."

            if item_type_val == "Goods":
                if tracking_type == "WEIGHT_ONLY":
                    qty_val = 0.0
                    if weight_val <= 0:
                        errors["items"] = "Weight is required and must be greater than 0 for all goods items."
                elif tracking_type == "QUANTITY_ONLY":
                    weight_val = 0.0
                    if qty_val <= 0:
                        errors["items"] = "Quantity is required and must be greater than 0 for all goods items."
                else:
                    if qty_val <= 0:
                        errors["items"] = "Quantity is required for all goods items."
            
            amount_val = round((weight_val if (item_type_val == "Goods" and tracking_type == "WEIGHT_ONLY") else qty_val) * rate_val, 2)
            
            items.append({
                "material_id":    mid if mid > 0 else None,
                "qty":            qty_val,
                "weight":         weight_val,
                "rate":           rate_val,
                "amount":         amount_val,
                "gst_percentage": float(gst_percentages[i] or 0) if i < len(gst_percentages) else 0.0,
                "item_type":      item_type_val,
                "description":    descriptions[i].strip() if i < len(descriptions) else None,
                "hsn_sac":        hsn_sacs[i].strip() if i < len(hsn_sacs) else None,
                "uom":            uoms[i].strip() if i < len(uoms) else "KGS",
                "item_reference": item_references[i].strip() if i < len(item_references) else None
            })

        if not items:
            errors["items"] = "Add at least one item."

        tcs_applicable = request.form.get("tcs_applicable") == "on"
        tcs_rate = float(request.form.get("tcs_rate") or 0.0) if tcs_applicable else 0.0

        # AUTHORITATIVE SERVER CALCULATION
        from services.calculation_service import calculate_invoice_result
        calc = calculate_invoice_result(
            items=items,
            company_state_code=company_state_code,
            billing_state_code=request.form.get("billing_state_code"),
            shipping_state_code=request.form.get("shipping_state_code"),
            tcs_applicable=tcs_applicable,
            tcs_rate=tcs_rate
        )

        # Mismatch Validation
        submitted_grand = float(request.form.get("hidden_grand_total") or 0.0)
        if abs(submitted_grand - calc["grand_total"]) > 1.0:
            errors["grand_total"] = f"Tax mismatch: Server computed ₹{calc['grand_total']:.2f} but form submitted ₹{submitted_grand:.2f}."

        # Check stock for goods items if status is CONFIRMED
        status_val = request.form.get("status", "CONFIRMED")
        if status_val == "CONFIRMED":
            stock_errors = []
            for item in items:
                if item["item_type"] == "Goods" and item["material_id"]:
                    is_available = check_stock_available(item["material_id"], item["qty"], item["weight"])
                    if not is_available:
                        from repositories.material_repository import get_material_by_id
                        mat = get_material_by_id(item["material_id"])
                        mat_name = mat["material_name"] if mat else "Selected material"
                        stock_errors.append(f"Stock not available for '{mat_name}' (insufficient quantity).")
            if stock_errors:
                errors["items"] = " ".join(stock_errors)

        if errors:
            flash_error("Please fix the errors below.")
            return render_template(
                "sales/sales_form.html",
                form=request.form,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                bank_accounts=bank_accounts,
                dispatch_locations=dispatch_locations,
                errors=errors,
                today=date.today().isoformat(),
            )

        party            = get_party_by_id(int(request.form["party_id"]))
        party_state_code = party["state_code"] if party else ""

        try:
            invoice_id = create_sales_invoice(
                party_id           = request.form["party_id"],
                invoice_date       = request.form["invoice_date"],
                payment_mode       = request.form.get("payment_mode"),
                transporter        = request.form.get("transporter"),
                vehicle_number     = request.form.get("vehicle_number"),
                remarks            = request.form.get("remarks"),
                items              = items,
                company_state_code = company_state_code,
                party_state_code   = party_state_code,
                eway_bill_number   = request.form.get("eway_bill_number"),
                reference_number   = request.form.get("reference_number"),
                status             = status_val,
                created_by         = "System User",
                billing_party_name = request.form.get("billing_party_name"),
                billing_address    = request.form.get("billing_address"),
                billing_gstin      = request.form.get("billing_gstin"),
                billing_state      = request.form.get("billing_state"),
                billing_state_code = request.form.get("billing_state_code"),
                billing_contact    = request.form.get("billing_contact"),
                shipping_party_name = request.form.get("shipping_party_name"),
                shipping_address   = request.form.get("shipping_address"),
                shipping_gstin     = request.form.get("shipping_gstin"),
                shipping_state     = request.form.get("shipping_state"),
                shipping_state_code = request.form.get("shipping_state_code"),
                shipping_contact   = request.form.get("shipping_contact"),
                dispatch_location  = request.form.get("dispatch_location"),
                dispatch_address   = request.form.get("dispatch_address"),
                dispatch_gstin     = request.form.get("dispatch_gstin"),
                dispatch_state     = request.form.get("dispatch_state"),
                dispatch_state_code = request.form.get("dispatch_state_code"),
                company_bank_name  = request.form.get("company_bank_name"),
                company_bank_account_number = request.form.get("company_bank_account_number"),
                company_bank_ifsc  = request.form.get("company_bank_ifsc"),
                company_bank_branch = request.form.get("company_bank_branch"),
                financial_year     = request.form.get("financial_year"),
                tcs_applicable     = tcs_applicable,
                tcs_rate           = tcs_rate
            )
            from services.inventory_service import sync_document
            sync_document("SALE", invoice_id)
        except Exception as exc:
            flash_error(str(exc))
            return render_template(
                "sales/sales_form.html",
                form=request.form,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                bank_accounts=bank_accounts,
                dispatch_locations=dispatch_locations,
                errors={},
                today=date.today().isoformat(),
            )

        invoice = get_invoice_by_id(invoice_id)
        inv_num = invoice["invoice_number"] if invoice else f"ID {invoice_id}"
        log_activity("System User", "Create Invoice", f"Created sales invoice {inv_num}")

        flash_success("Sales invoice created successfully.")
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    return render_template(
        "sales/sales_form.html",
        form=None,
        parties=parties,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        bank_accounts=bank_accounts,
        dispatch_locations=dispatch_locations,
        errors={},
        today=date.today().isoformat(),
    )


# ── Edit ────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit_sales_invoice(invoice_id):
    existing = get_invoice_by_id(invoice_id)
    if not existing:
        flash_error("Sales invoice not found.")
        return redirect(url_for("sales.sales"))

    parties = [p for p in get_all_parties() if p["party_type"] in ("CUSTOMER", "BOTH")]
    materials = get_all_materials()
    company = get_company()
    company_state_code = company["state_code"] if company else ""

    # Fetch bank accounts
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_bank WHERE is_active = 1")
    bank_accounts = [dict(r) for r in cursor.fetchall()]
    
    # Fetch dispatch locations
    cursor.execute("SELECT * FROM dispatch_location WHERE is_active = 1")
    dispatch_locations = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if request.method == "POST":
        errors = _validate_header(request.form)
        material_ids = request.form.getlist("material_id[]")
        qtys = request.form.getlist("qty[]")
        weights = request.form.getlist("weight[]")
        rates = request.form.getlist("rate[]")
        amounts = request.form.getlist("amount[]")
        gst_percentages = request.form.getlist("gst_percentage[]")
        item_types      = request.form.getlist("item_type[]")
        descriptions    = request.form.getlist("description[]")
        hsn_sacs        = request.form.getlist("hsn_sac[]")
        uoms            = request.form.getlist("uom[]")
        item_references = request.form.getlist("item_reference[]")

        items = []
        for i in range(len(material_ids)):
            mid_str = material_ids[i].strip() if i < len(material_ids) else ""
            mid = int(mid_str) if mid_str else 0
            
            # Fetch material tracking type
            tracking_type = "BOTH"
            if mid > 0:
                from repositories.material_repository import get_material_by_id
                mat = get_material_by_id(int(mid))
                tracking_type = mat["tracking_type"] if mat else "BOTH"
            
            qty_val = float(qtys[i] or 0) if i < len(qtys) else 0.0
            weight_val = float(weights[i] or 0) if i < len(weights) else 0.0
            item_type_val = item_types[i].strip() if i < len(item_types) else "Goods"
            rate_val = float(rates[i] or 0) if i < len(rates) else 0.0

            if qty_val < 0 or weight_val < 0 or rate_val < 0:
                errors["items"] = "Negative quantity, weight, or rate is not allowed."

            if item_type_val == "Goods":
                if tracking_type == "WEIGHT_ONLY":
                    qty_val = 0.0
                    if weight_val <= 0:
                        errors["items"] = "Weight is required and must be greater than 0 for all goods items."
                elif tracking_type == "QUANTITY_ONLY":
                    weight_val = 0.0
                    if qty_val <= 0:
                        errors["items"] = "Quantity is required and must be greater than 0 for all goods items."
                else:
                    if qty_val <= 0:
                        errors["items"] = "Quantity is required for all goods items."

            amount_val = round((weight_val if (item_type_val == "Goods" and tracking_type == "WEIGHT_ONLY") else qty_val) * rate_val, 2)
            items.append({
                "material_id": mid if mid > 0 else None,
                "qty": qty_val,
                "weight": weight_val,
                "rate": rate_val,
                "amount": amount_val,
                "gst_percentage": float(gst_percentages[i] or 0) if i < len(gst_percentages) else 0.0,
                "item_type":      item_type_val,
                "description":    descriptions[i].strip() if i < len(descriptions) else None,
                "hsn_sac":        hsn_sacs[i].strip() if i < len(hsn_sacs) else None,
                "uom":            uoms[i].strip() if i < len(uoms) else "KGS",
                "item_reference": item_references[i].strip() if i < len(item_references) else None
            })

        if not items:
            errors["items"] = "Add at least one item."

        # Finalized Invoice Edit Protection for non-admin roles
        from flask import session
        role = session.get("user", {}).get("role", "").upper() if session.get("user") else ""
        if existing["status"] != "DRAFT" and role != "ADMIN":
            party_changed = int(request.form.get("party_id") or 0) != int(existing["party_id"])
            date_changed = request.form.get("invoice_date") != existing["invoice_date"]
            
            existing_items = get_invoice_items(invoice_id)
            items_changed = len(items) != len(existing_items)
            if not items_changed:
                for idx, item in enumerate(items):
                    ex_item = dict(existing_items[idx])
                    if (item["material_id"] != ex_item["material_id"] or
                        abs(item["qty"] - ex_item["quantity"]) > 0.000001 or
                        abs(item["weight"] - ex_item["weight"]) > 0.000001 or
                        abs(item["rate"] - ex_item["rate"]) > 0.000001):
                        items_changed = True
                        break
            
            if party_changed or date_changed or items_changed:
                errors["items"] = "Only administrators can modify line items, quantities, rates, customer, or dates of a finalized invoice."
                flash_error("Only administrators can modify line items, quantities, rates, customer, or dates of a finalized invoice.")

        tcs_applicable = request.form.get("tcs_applicable") == "on"
        tcs_rate = float(request.form.get("tcs_rate") or 0.0) if tcs_applicable else 0.0

        # AUTHORITATIVE SERVER CALCULATION
        from services.calculation_service import calculate_invoice_result
        calc = calculate_invoice_result(
            items=items,
            company_state_code=company_state_code,
            billing_state_code=request.form.get("billing_state_code"),
            shipping_state_code=request.form.get("shipping_state_code"),
            tcs_applicable=tcs_applicable,
            tcs_rate=tcs_rate
        )

        # Mismatch Validation
        submitted_grand = float(request.form.get("hidden_grand_total") or 0.0)
        if abs(submitted_grand - calc["grand_total"]) > 1.0:
            errors["grand_total"] = f"Tax mismatch: Server computed ₹{calc['grand_total']:.2f} but form submitted ₹{submitted_grand:.2f}."

        # 1. Status Transition validation
        old_status = existing["status"] or "CONFIRMED"
        new_status = request.form.get("status", "CONFIRMED")
        if not validate_status_transition(old_status, new_status):
            errors["status"] = f"Invalid status transition from {old_status} to {new_status}."

        # 2. Check stock for each item if new status is CONFIRMED
        if new_status == "CONFIRMED" and not errors.get("status"):
            stock_errors = []
            for item in items:
                if item["item_type"] == "Goods" and item["material_id"]:
                    is_available = check_stock_available(item["material_id"], item["qty"], item["weight"], exclude_invoice_id=invoice_id)
                    if not is_available:
                        from repositories.material_repository import get_material_by_id
                        mat = get_material_by_id(item["material_id"])
                        mat_name = mat["material_name"] if mat else "Selected material"
                        stock_errors.append(f"Stock not available for '{mat_name}' (insufficient quantity).")
            if stock_errors:
                errors["items"] = " ".join(stock_errors)

        if errors:
            flash_error("Please fix the errors below.")
            form_data = dict(request.form)
            form_data["status"] = new_status
            return render_template(
                "sales/sales_form.html",
                form=form_data,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                bank_accounts=bank_accounts,
                dispatch_locations=dispatch_locations,
                errors=errors,
                today=existing["invoice_date"],
                invoice_id=invoice_id,
            )

        party = get_party_by_id(int(request.form["party_id"]))
        party_state_code = party["state_code"] if party else ""
        try:
            update_sales_invoice(
                invoice_id,
                request.form["party_id"],
                request.form["invoice_date"],
                request.form.get("payment_mode"),
                request.form.get("transporter"),
                request.form.get("vehicle_number"),
                request.form.get("remarks"),
                items,
                company_state_code,
                party_state_code,
                eway_bill_number   = request.form.get("eway_bill_number"),
                reference_number   = request.form.get("reference_number"),
                status             = new_status,
                updated_by         = "System User",
                billing_party_name = request.form.get("billing_party_name"),
                billing_address    = request.form.get("billing_address"),
                billing_gstin      = request.form.get("billing_gstin"),
                billing_state      = request.form.get("billing_state"),
                billing_state_code = request.form.get("billing_state_code"),
                billing_contact    = request.form.get("billing_contact"),
                shipping_party_name = request.form.get("shipping_party_name"),
                shipping_address   = request.form.get("shipping_address"),
                shipping_gstin     = request.form.get("shipping_gstin"),
                shipping_state     = request.form.get("shipping_state"),
                shipping_state_code = request.form.get("shipping_state_code"),
                shipping_contact   = request.form.get("shipping_contact"),
                dispatch_location  = request.form.get("dispatch_location"),
                dispatch_address   = request.form.get("dispatch_address"),
                dispatch_gstin     = request.form.get("dispatch_gstin"),
                dispatch_state     = request.form.get("dispatch_state"),
                dispatch_state_code = request.form.get("dispatch_state_code"),
                company_bank_name  = request.form.get("company_bank_name"),
                company_bank_account_number = request.form.get("company_bank_account_number"),
                company_bank_ifsc  = request.form.get("company_bank_ifsc"),
                company_bank_branch = request.form.get("company_bank_branch"),
                financial_year     = request.form.get("financial_year"),
                tcs_applicable     = tcs_applicable,
                tcs_rate           = tcs_rate
            )
            from services.inventory_service import sync_document
            sync_document("SALE", invoice_id)
            log_activity("System User", "Update Invoice", f"Updated sales invoice {existing['invoice_number']}")
        except Exception as exc:
            flash_error(str(exc))
            form_data = dict(request.form)
            form_data["status"] = new_status
            return render_template(
                "sales/sales_form.html",
                form=form_data,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                bank_accounts=bank_accounts,
                dispatch_locations=dispatch_locations,
                errors={},
                today=existing["invoice_date"],
                invoice_id=invoice_id,
            )
        flash_success("Sales invoice updated successfully.")
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    existing_items = get_invoice_items(invoice_id)
    form_data = dict(existing)
    form_data["party_id"] = str(form_data.get("party_id") or "")
    form_data["invoice_date"] = form_data.get("invoice_date")
    form_data["payment_mode"] = form_data.get("payment_mode") or ""
    form_data["transporter"] = form_data.get("transporter") or ""
    form_data["vehicle_number"] = form_data.get("vehicle_number") or ""
    form_data["remarks"] = form_data.get("remarks") or ""
    form_data["eway_bill_number"] = form_data.get("eway_bill_number") or ""
    form_data["reference_number"] = form_data.get("reference_number") or ""
    form_data["status"] = form_data.get("status") or "CONFIRMED"
    form_data["tcs_applicable"] = bool(form_data.get("tcs_applicable"))
    form_data["tcs_rate"] = form_data.get("tcs_rate") or 0.0

    return render_template(
        "sales/sales_form.html",
        form=form_data,
        parties=parties,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        bank_accounts=bank_accounts,
        dispatch_locations=dispatch_locations,
        errors={},
        today=existing["invoice_date"],
        invoice_id=invoice_id,
        existing_items=existing_items,
    )


@sales_bp.route("/sales/<int:invoice_id>/delete", methods=["POST"])
def delete_sales_invoice_route(invoice_id):
    existing = get_invoice_by_id(invoice_id)
    if not existing:
        flash_error("Sales invoice not found.")
        return redirect(url_for("sales.sales"))
    delete_sales_invoice(invoice_id)
    from services.inventory_service import sync_document
    sync_document("SALE", invoice_id)
    log_activity("System User", "Delete Invoice", f"Deleted sales invoice {existing['invoice_number']}")
    flash_warning("Sales invoice deleted successfully.")
    return redirect(url_for("sales.sales"))


# ── View / Preview ────────────────────────────────────────────────────────────

@sales_bp.route("/sales/<int:invoice_id>/view")
@sales_bp.route("/sales/view/<int:invoice_id>")
def view_invoice(invoice_id):
    increment_print_count(invoice_id)
    ctx = _invoice_context(invoice_id)
    log_activity("System User", "Print Invoice", f"Printed sales invoice {ctx['invoice']['invoice_number']}")
    return render_template("sales/sales_invoice.html", **ctx)


# ── Download PDF ──────────────────────────────────────────────────────────────

def _fetch_pdf_resource(uri, rel):
    parsed = urlparse(uri)
    if parsed.scheme == 'file':
        path = parsed.path
        if path.startswith('/') and path[2:3] == ':':
            path = path[1:]
        return os.path.normpath(path)
    if uri.startswith('/static/'):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        return os.path.normpath(os.path.join(root, uri.lstrip('/').replace('/', os.sep)))
    return uri

@sales_bp.route("/print/sales/<int:invoice_id>")
def print_sales_invoice(invoice_id):
    ctx  = _invoice_context(invoice_id)
    ctx["invoice_type"] = "sales"
    rendered_html = render_template("reports/invoice_print.html", **ctx)
    
    # Save a temporary copy for troubleshooting
    try:
        debug_path = os.path.join(os.path.dirname(__file__), "..", "static", "invoice_debug.html")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
    except Exception as debug_err:
        print("Failed to save invoice_debug.html:", debug_err)
        
    return rendered_html

@sales_bp.route("/sales/<int:invoice_id>/pdf")
@sales_bp.route("/sales/pdf/<int:invoice_id>")
def download_pdf(invoice_id):
    increment_pdf_download_count(invoice_id)
    ctx  = _invoice_context(invoice_id)
    ctx["invoice_type"] = "sales"
    log_activity("System User", "Download PDF", f"Downloaded PDF for sales invoice {ctx['invoice']['invoice_number']}")
    
    from backend.services.pdf_service import compile_html_to_pdf, render_url_to_pdf, send_pdf_response
    rendered_html = render_template("reports/invoice_print.html", **ctx)
    
    try:
        pdf_bytes = compile_html_to_pdf(rendered_html)
    except Exception as exc1:
        try:
            host = request.host_url if request else "http://127.0.0.1:5000/"
            if host in {"http://localhost/", "http://127.0.0.1/"}:
                host = "http://127.0.0.1:5000/"
            invoice_url = f"{host.rstrip('/')}/print/sales/{invoice_id}"
            pdf_bytes = render_url_to_pdf(invoice_url)
        except Exception as e:
            logger.error("PDF generation failed for invoice %s: %s (direct: %s)", invoice_id, e, exc1, exc_info=True)
            flash_error("Unable to generate the invoice PDF. Please try again.")
            return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))
        
    filename = f"Sales_Invoice_{ctx['invoice']['invoice_number']}_{ctx['invoice'].get('financial_year') or '2026-27'}.pdf"
    filename = filename.replace('/', '-').replace('\\', '-')
    return send_pdf_response(pdf_bytes, filename)


# ── Email (mailto link handled in template) ───────────────────────────────────

@sales_bp.route("/sales/<int:invoice_id>/email")
def email_invoice(invoice_id):
    ctx = _invoice_context(invoice_id)
    return render_template("sales/sales_invoice.html", open_email_modal=True, **ctx)


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_header(form):
    errors = {}
    if not form.get("party_id", "").strip():
        errors["party_id"] = "Customer is required."
    if not form.get("invoice_date", "").strip():
        errors["invoice_date"] = "Invoice date is required."
    return errors


@sales_bp.route("/sales/register")
def sales_register():
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    customer_id = request.args.get("customer_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    rows = get_sales_register_rows(
        start_date=parsed_start,
        end_date=parsed_end,
        financial_year=financial_year,
        month=month,
        customer_id=customer_id,
        material_id=material_id
    )

    unique_invoices = {}
    unique_customers = set()
    total_taxable = 0.0
    total_gst = 0.0
    
    for r in rows:
        unique_invoices[r["invoice_number"]] = float(r["grand_total"] or 0.0)
        unique_customers.add(r["customer_name"])
        total_taxable += float(r["taxable_value"] or 0.0)
        total_gst += float(r["gst_total"] or 0.0)

    total_invoices = len(unique_invoices)
    total_customers = len(unique_customers)
    total_invoice_value = sum(unique_invoices.values())
    
    avg_invoice_value = total_invoice_value / total_invoices if total_invoices > 0 else 0.0
    highest_invoice = max(unique_invoices.values()) if unique_invoices else 0.0
    lowest_invoice = min(unique_invoices.values()) if unique_invoices else 0.0

    monthly_analytics = get_monthly_analytics()
    top_customers = get_top_customers()
    top_materials = get_top_materials()

    parties = get_all_parties()
    materials = get_all_materials()

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(rows)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_rows = rows[offset : offset + per_page]

    return render_template(
        "sales/sales_register.html",
        rows=paginated_rows,
        parties=parties,
        materials=materials,
        total_invoices=total_invoices,
        total_customers=total_customers,
        total_taxable=total_taxable,
        total_gst=total_gst,
        total_invoice_value=total_invoice_value,
        avg_invoice_value=avg_invoice_value,
        highest_invoice=highest_invoice,
        lowest_invoice=lowest_invoice,
        monthly_analytics=monthly_analytics,
        top_customers=top_customers,
        top_materials=top_materials,
        date_filter=date_filter,
        year=year,
        financial_year=financial_year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        material_id=material_id,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )


@sales_bp.route("/sales/register/export")
def export_sales_register():
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    customer_id = request.args.get("customer_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    rows = get_sales_register_rows(
        start_date=parsed_start,
        end_date=parsed_end,
        financial_year=financial_year,
        month=month,
        customer_id=customer_id,
        material_id=material_id
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Register"
    ws.views.sheetView[0].showGridLines = True

    title_font = Font(name="Calibri", size=16, bold=True, color="1B5E20")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    border_thin = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    ws.merge_cells("A1:O1")
    ws["A1"] = "Right Ewaste Recycle Pvt. Ltd. - Sales Register Report"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    headers = [
        "Invoice Date", "Invoice Number", "Customer Name", "GSTIN", "State", 
        "Material", "Taxable Value (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", 
        "GST Total (₹)", "Round Off (₹)", "Invoice Total (₹)", "Payment Mode", "Status"
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = border_thin
    ws.row_dimensions[3].height = 25

    row_num = 4
    for item in rows:
        ws.cell(row=row_num, column=1, value=item["invoice_date"]).alignment = center_align
        ws.cell(row=row_num, column=2, value=item["invoice_number"]).alignment = center_align
        ws.cell(row=row_num, column=3, value=item["customer_name"]).alignment = left_align
        ws.cell(row=row_num, column=4, value=item["gstin"] or "—").alignment = center_align
        ws.cell(row=row_num, column=5, value=item["state"]).alignment = center_align
        ws.cell(row=row_num, column=6, value=item["material"]).alignment = left_align
        
        c_tax = ws.cell(row=row_num, column=7, value=item["taxable_value"])
        c_tax.number_format = '#,##0.00'
        c_tax.alignment = right_align
        
        c_cgst = ws.cell(row=row_num, column=8, value=item["cgst"])
        c_cgst.number_format = '#,##0.00'
        c_cgst.alignment = right_align
        
        c_sgst = ws.cell(row=row_num, column=9, value=item["sgst"])
        c_sgst.number_format = '#,##0.00'
        c_sgst.alignment = right_align
        
        c_igst = ws.cell(row=row_num, column=10, value=item["igst"])
        c_igst.number_format = '#,##0.00'
        c_igst.alignment = right_align
        
        c_gst_tot = ws.cell(row=row_num, column=11, value=item["gst_total"])
        c_gst_tot.number_format = '#,##0.00'
        c_gst_tot.alignment = right_align
        
        c_ro = ws.cell(row=row_num, column=12, value=item["round_off"])
        c_ro.number_format = '#,##0.00'
        c_ro.alignment = right_align
        
        c_gt = ws.cell(row=row_num, column=13, value=item["grand_total"])
        c_gt.number_format = '#,##0.00'
        c_gt.alignment = right_align
        
        ws.cell(row=row_num, column=14, value=item["payment_mode"] or "—").alignment = center_align
        ws.cell(row=row_num, column=15, value=item["status"]).alignment = center_align

        for col_idx in range(1, 16):
            ws.cell(row=row_num, column=col_idx).border = border_thin

        ws.row_dimensions[row_num].height = 20
        row_num += 1

    for col_idx in range(1, 16):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row in range(2, row_num):
            val = ws.cell(row=row, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_data = buffer.getvalue()

    filename = get_report_filename("sales_register", "xlsx", date_filter, year, month, start_date, end_date)
    return Response(
        xlsx_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(xlsx_data),
        }
    )
@sales_bp.route("/sales/<int:invoice_id>/duplicate")
def duplicate_invoice(invoice_id):
    existing = get_invoice_by_id(invoice_id)
    if not existing:
        flash_error("Sales invoice not found.")
        return redirect(url_for("sales.sales"))
    existing = dict(existing)
        
    items = get_invoice_items(invoice_id)
    new_items = []
    for it in items:
        it_dict = dict(it)
        new_items.append({
            "material_id": it_dict["material_id"],
            "qty": it_dict["quantity"],
            "weight": it_dict["weight"],
            "rate": it_dict["rate"],
            "amount": it_dict["amount"],
            "gst_percentage": it_dict["gst_percentage"],
            "item_type": it_dict.get("item_type") or "Goods",
            "description": it_dict.get("description"),
            "hsn_sac": it_dict.get("hsn_sac"),
            "uom": it_dict.get("uom") or "KGS",
            "item_reference": it_dict.get("item_reference")
        })
        
    company = get_company()
    company_state_code = company["state_code"] if company else ""
    party = get_party_by_id(existing["party_id"])
    party_state_code = party["state_code"] if party else ""
    
    try:
        new_id = create_sales_invoice(
            party_id=existing["party_id"],
            invoice_date=date.today().isoformat(),
            payment_mode=existing["payment_mode"],
            transporter=existing["transporter"],
            vehicle_number=existing["vehicle_number"],
            remarks=f"Duplicate of {existing['invoice_number']}",
            items=new_items,
            company_state_code=company_state_code,
            party_state_code=party_state_code,
            eway_bill_number=existing["eway_bill_number"],
            reference_number=existing["reference_number"],
            status="DRAFT",
            created_by=None,
            billing_party_name=existing.get("billing_party_name"),
            billing_address=existing.get("billing_address"),
            billing_gstin=existing.get("billing_gstin"),
            billing_state=existing.get("billing_state"),
            billing_state_code=existing.get("billing_state_code"),
            billing_contact=existing.get("billing_contact"),
            shipping_party_name=existing.get("shipping_party_name"),
            shipping_address=existing.get("shipping_address"),
            shipping_gstin=existing.get("shipping_gstin"),
            shipping_state=existing.get("shipping_state"),
            shipping_state_code=existing.get("shipping_state_code"),
            shipping_contact=existing.get("shipping_contact"),
            dispatch_location=existing.get("dispatch_location"),
            dispatch_address=existing.get("dispatch_address"),
            dispatch_gstin=existing.get("dispatch_gstin"),
            dispatch_state=existing.get("dispatch_state"),
            dispatch_state_code=existing.get("dispatch_state_code"),
            company_bank_name=existing.get("company_bank_name"),
            company_bank_account_number=existing.get("company_bank_account_number"),
            company_bank_ifsc=existing.get("company_bank_ifsc"),
            company_bank_branch=existing.get("company_bank_branch"),
            financial_year=existing.get("financial_year"),
            tcs_applicable=bool(existing.get("tcs_applicable", 0)),
            tcs_rate=float(existing.get("tcs_rate") or 0.0)
        )
        flash_success("Invoice duplicated successfully as a DRAFT. Please review and update details.")
        return redirect(url_for("sales.edit_sales_invoice", invoice_id=new_id))
    except Exception as e:
        flash_error(f"Failed to duplicate invoice: {e}")
        return redirect(url_for("sales.sales"))


@sales_bp.route("/api/company/bank/<int:bank_id>")
def api_company_bank_details(bank_id):
    from database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM company_bank WHERE id = ?", (bank_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "Bank account not found"}, 404
    return dict(row)


@sales_bp.route("/api/company/dispatch/<int:location_id>")
def api_company_dispatch_details(location_id):
    from database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM dispatch_location WHERE id = ?", (location_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "Dispatch location not found"}, 404
    return dict(row)


# ── API Customer Details ──────────────────────────────────────────────────────

@sales_bp.route("/api/party/<int:party_id>")
def api_party_details(party_id):
    party = get_party_by_id(party_id)
    if not party:
        return {"error": "Party not found"}, 404
    return {
        "id": party["id"],
        "company_name": party["company_name"],
        "gstin": party["gstin"] or "",
        "billing_address": party["billing_address"] or "",
        "state": party["state"] or "",
        "state_code": party["state_code"] or ""
    }


# ── Sales Dashboard ───────────────────────────────────────────────────────────

@sales_bp.route("/sales/dashboard")
def sales_dashboard():
    from database import get_connection
    from datetime import date
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Total confirmed invoices count & revenue
    cursor.execute("""
        SELECT COUNT(*), SUM(grand_total), AVG(grand_total), MAX(grand_total), MIN(grand_total)
        FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """)
    totals = cursor.fetchone()
    invoice_count = totals[0] or 0
    total_sales = totals[1] or 0.0
    avg_sales = totals[2] or 0.0
    max_sales = totals[3] or 0.0
    min_sales = totals[4] or 0.0
    
    # 2. Today's sales
    today_str = date.today().isoformat()
    cursor.execute("""
        SELECT SUM(grand_total) FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED') AND invoice_date = ?
    """, (today_str,))
    today_sales = cursor.fetchone()[0] or 0.0
    
    # 3. This month's sales
    month_str = date.today().strftime("%Y-%m")
    cursor.execute("""
        SELECT SUM(grand_total) FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED') AND strftime('%Y-%m', invoice_date) = ?
    """, (month_str,))
    this_month_sales = cursor.fetchone()[0] or 0.0
    
    # 4. Total GST Collected
    cursor.execute("""
        SELECT SUM(cgst + sgst + igst) FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """)
    total_gst = cursor.fetchone()[0] or 0.0
    
    # 5. Top Customer
    cursor.execute("""
        SELECT p.company_name, SUM(si.grand_total) as val
        FROM sales_invoice si
        JOIN party p ON si.party_id = p.id
        WHERE si.is_active = 1 AND si.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY si.party_id
        ORDER BY val DESC
        LIMIT 1
    """)
    top_customer_row = cursor.fetchone()
    top_customer = top_customer_row[0] if top_customer_row else "—"
    
    # 6. Top Selling Material
    cursor.execute("""
        SELECT m.material_name, SUM(sii.quantity) as qty
        FROM sales_invoice_item sii
        JOIN sales_invoice si ON sii.sales_invoice_id = si.id
        JOIN material m ON sii.material_id = m.id
        WHERE si.is_active = 1 AND si.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY sii.material_id
        ORDER BY qty DESC
        LIMIT 1
    """)
    top_material_row = cursor.fetchone()
    top_selling_material = top_material_row[0] if top_material_row else "—"
    
    # Monthly sales trends (last 12 months)
    cursor.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(grand_total) as val, SUM(cgst + sgst + igst) as gst_val
        FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY month
        ORDER BY month ASC
        LIMIT 12
    """)
    trend_rows = cursor.fetchall()
    months = [r[0] for r in trend_rows]
    revenues = [float(r[1] or 0) for r in trend_rows]
    gsts = [float(r[2] or 0) for r in trend_rows]
    
    # Sales by category
    cursor.execute("""
        SELECT m.category, SUM(sii.amount) as val
        FROM sales_invoice_item sii
        JOIN sales_invoice si ON sii.sales_invoice_id = si.id
        JOIN material m ON sii.material_id = m.id
        WHERE si.is_active = 1 AND si.status NOT IN ('DRAFT', 'CANCELLED') AND m.category IS NOT NULL
        GROUP BY m.category
    """)
    category_rows = cursor.fetchall()
    categories = [r[0] for r in category_rows]
    category_vals = [float(r[1] or 0) for r in category_rows]
    
    conn.close()
    
    return render_template(
        "sales/sales_dashboard.html",
        invoice_count=invoice_count,
        total_sales=total_sales,
        avg_sales=avg_sales,
        max_sales=max_sales,
        min_sales=min_sales,
        today_sales=today_sales,
        this_month_sales=this_month_sales,
        total_gst=total_gst,
        top_customer=top_customer,
        top_selling_material=top_selling_material,
        months=months,
        revenues=revenues,
        gsts=gsts,
        categories=categories,
        category_vals=category_vals
    )

# ── Audit Trail (Activity Log) ───────────────────────────────────────────────

@sales_bp.route("/audit-log")
def audit_log():
    from repositories.activity_log_repository import get_all_activities
    logs = get_all_activities()
    return render_template("dashboard/activity_log.html", logs=logs)


@sales_bp.route("/api/sales/calculate", methods=["POST"])
def api_calculate_sales():
    data = request.json or {}
    company_state_code = data.get("company_state_code")
    if not company_state_code:
        company = get_company()
        company_state_code = company["state_code"] if company else ""
        
    items = data.get("items") or []
    billing_state_code = data.get("billing_state_code") or ""
    shipping_state_code = data.get("shipping_state_code") or ""
    tcs_applicable = bool(data.get("tcs_applicable"))
    tcs_rate = float(data.get("tcs_rate") or 0.0)
    
    from services.calculation_service import calculate_invoice_result
    try:
        res = calculate_invoice_result(
            items=items,
            company_state_code=company_state_code,
            billing_state_code=billing_state_code,
            shipping_state_code=shipping_state_code,
            tcs_applicable=tcs_applicable,
            tcs_rate=tcs_rate
        )
        return res
    except Exception as e:
        return {"error": str(e)}, 400


@sales_bp.route("/api/sales/<int:invoice_id>/details")
def api_sales_invoice_details(invoice_id):
    try:
        ctx = _invoice_context(invoice_id)
        items_dict = [dict(it) for it in ctx["items"]]
        invoice_dict = dict(ctx["invoice"])
        party_dict = dict(ctx["party"]) if ctx["party"] else None
        company_dict = dict(ctx["company"]) if ctx["company"] else None
        
        return {
            "invoice": invoice_dict,
            "items": items_dict,
            "party": party_dict,
            "company": company_dict,
            "is_intra": ctx["is_intra"],
            "tax_breakdown": ctx["tax_breakdown"]
        }
    except Exception as e:
        logger.error("Failed to fetch invoice details API: %s", e, exc_info=True)
        return {"error": str(e)}, 500


