import io
import os
from datetime import date, timedelta
import calendar
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, abort
from xhtml2pdf import pisa
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from repositories.purchase_repository import (
    get_all_purchase_invoices,
    get_purchase_invoice_by_id,
    get_purchase_invoice_items,
    create_purchase_invoice,
    update_purchase_invoice,
    delete_purchase_invoice,
    get_purchase_register_rows,
    get_purchase_monthly_analytics,
    get_top_suppliers,
    get_top_purchased_materials,
    increment_purchase_print_count,
    increment_purchase_pdf_download_count,
)
from repositories.party_repository import get_all_parties, get_party_by_id
from repositories.material_repository import get_all_materials
from repositories.company_repository import get_company

purchase_bp = Blueprint("purchase", __name__)

PAYMENT_MODES = ["Cash", "UPI", "NEFT", "RTGS", "Cheque", "Credit"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _invoice_context(invoice_id):
    invoice = get_purchase_invoice_by_id(invoice_id)
    if not invoice:
        abort(404)
    items = get_purchase_invoice_items(invoice_id)
    supplier = get_party_by_id(invoice["supplier_id"])
    company = get_company()
    is_intra = (
        company and supplier and
        str(company["state_code"]).strip() == str(supplier["state_code"]).strip()
    )
    return dict(
        invoice=invoice,
        items=items,
        supplier=supplier,
        company=company,
        is_intra=is_intra
    )


def get_filter_date_range(date_filter, year, month, start_date, end_date):
    """
    Translates dropdown selection + start/end dates into ISO date strings.
    """
    today = date.today()
    parsed_start, parsed_end = None, None

    if date_filter == "today":
        parsed_start = today.isoformat()
        parsed_end = today.isoformat()
    elif date_filter == "this_week":
        start_of_week = today - timedelta(days=today.weekday())
        parsed_start = start_of_week.isoformat()
        parsed_end = today.isoformat()
    elif date_filter == "this_month":
        parsed_start = today.replace(day=1).isoformat()
        parsed_end = today.isoformat()
    elif date_filter == "last_6_months":
        six_months_ago = today - timedelta(days=6*30)
        parsed_start = six_months_ago.isoformat()
        parsed_end = today.isoformat()
    elif date_filter == "custom":
        if start_date:
            parsed_start = start_date
        if end_date:
            parsed_end = end_date
    elif year and year != "all":
        y = int(year)
        if month and month != "all":
            m = int(month)
            last_day = calendar.monthrange(y, m)[1]
            parsed_start = f"{y:04d}-{m:02d}-01"
            parsed_end = f"{y:04d}-{m:02d}-{last_day:02d}"
        else:
            parsed_start = f"{y:04d}-01-01"
            parsed_end = f"{y:04d}-12-31"
    elif month and month != "all":
        m = int(month)
        y = today.year
        last_day = calendar.monthrange(y, m)[1]
        parsed_start = f"{y:04d}-{m:02d}-01"
        parsed_end = f"{y:04d}-{m:02d}-{last_day:02d}"

    return parsed_start, parsed_end


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


# ── Main routes ───────────────────────────────────────────────────────────────

@purchase_bp.route("/purchase")
def purchase():
    q = request.args.get("q", "").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    supplier_id = request.args.get("supplier_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()
    state = request.args.get("state", "all").strip()
    gst_type = request.args.get("gst_type", "all").strip()
    status = request.args.get("status", "all").strip()
    payment_mode = request.args.get("payment_mode", "all").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    invoices = get_all_purchase_invoices(
        start_date=parsed_start,
        end_date=parsed_end,
        search_query=q,
        financial_year=financial_year,
        month=month,
        supplier_id=supplier_id,
        material_id=material_id,
        state=state,
        gst_type=gst_type,
        status=status,
        payment_mode=payment_mode,
        sort_by=sort_by
    )

    parties = get_all_parties()
    supplier_parties = [p for p in parties if p["party_type"] in ["SUPPLIER", "BOTH"]]
    materials = get_all_materials()
    
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT state FROM party WHERE state IS NOT NULL AND state != '' AND is_active = 1")
    states = [r[0] for r in cursor.fetchall()]
    conn.close()

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(invoices)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_invoices = invoices[offset : offset + per_page]

    return render_template(
        "purchase.html",
        invoices=paginated_invoices,
        parties=supplier_parties,
        materials=materials,
        states=states,
        q=q,
        date_filter=date_filter,
        year=year,
        financial_year=financial_year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        supplier_id=supplier_id,
        material_id=material_id,
        state=state,
        gst_type=gst_type,
        status=status,
        payment_mode=payment_mode,
        sort_by=sort_by,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )


@purchase_bp.route("/purchase/export")
def export_purchase():
    q = request.args.get("q", "").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    supplier_id = request.args.get("supplier_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()
    state = request.args.get("state", "all").strip()
    gst_type = request.args.get("gst_type", "all").strip()
    status = request.args.get("status", "all").strip()
    payment_mode = request.args.get("payment_mode", "all").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    invoices = get_all_purchase_invoices(
        start_date=parsed_start,
        end_date=parsed_end,
        search_query=q,
        financial_year=financial_year,
        month=month,
        supplier_id=supplier_id,
        material_id=material_id,
        state=state,
        gst_type=gst_type,
        status=status,
        payment_mode=payment_mode,
        sort_by=sort_by
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Purchase Invoices"
    ws.views.sheetView[0].showGridLines = True

    title_font = Font(name="Calibri", size=16, bold=True, color="1E3A8A")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    border_thin = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    ws.merge_cells("A1:M1")
    ws["A1"] = "Right Ewaste Recycle Pvt. Ltd. - Purchase Invoices Report"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    headers = [
        "Invoice No.", "Date", "Supplier", "GSTIN", "State", "Supplier Inv No.", 
        "Payment Mode", "Transporter", "Vehicle No.", "Items Count", 
        "Taxable Amount (₹)", "Round Off (₹)", "Grand Total (₹)"
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = border_thin
    ws.row_dimensions[3].height = 25

    row_num = 4
    for inv in invoices:
        ws.cell(row=row_num, column=1, value=inv["purchase_invoice_number"]).alignment = center_align
        ws.cell(row=row_num, column=2, value=inv["invoice_date"]).alignment = center_align
        ws.cell(row=row_num, column=3, value=inv["company_name"] or "—").alignment = left_align
        ws.cell(row=row_num, column=4, value=inv["gstin"] or "—").alignment = center_align
        ws.cell(row=row_num, column=5, value=inv["state"] or "—").alignment = center_align
        ws.cell(row=row_num, column=6, value=inv["supplier_invoice_number"] or "—").alignment = center_align
        ws.cell(row=row_num, column=7, value=inv["payment_mode"] or "—").alignment = center_align
        ws.cell(row=row_num, column=8, value=inv["transporter"] or "—").alignment = left_align
        ws.cell(row=row_num, column=9, value=inv["vehicle_number"] or "—").alignment = center_align
        ws.cell(row=row_num, column=10, value=inv["item_count"]).alignment = center_align
        
        c_sub = ws.cell(row=row_num, column=11, value=inv["subtotal"])
        c_sub.number_format = '#,##0.00'
        c_sub.alignment = right_align

        c_ro = ws.cell(row=row_num, column=12, value=inv["round_off"])
        c_ro.number_format = '#,##0.00'
        c_ro.alignment = right_align

        c_gt = ws.cell(row=row_num, column=13, value=inv["grand_total"])
        c_gt.number_format = '#,##0.00'
        c_gt.alignment = right_align

        for col_idx in range(1, 14):
            ws.cell(row=row_num, column=col_idx).border = border_thin
        ws.row_dimensions[row_num].height = 20
        row_num += 1

    for col_idx in range(1, 14):
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

    filename = get_report_filename("purchase_invoices", "xlsx", date_filter, year, month, start_date, end_date)
    return Response(
        xlsx_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(xlsx_data),
        }
    )


@purchase_bp.route("/purchase/export/pdf")
def export_purchase_pdf():
    q = request.args.get("q", "").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    supplier_id = request.args.get("supplier_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()
    state = request.args.get("state", "all").strip()
    gst_type = request.args.get("gst_type", "all").strip()
    status = request.args.get("status", "all").strip()
    payment_mode = request.args.get("payment_mode", "all").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    invoices = get_all_purchase_invoices(
        start_date=parsed_start,
        end_date=parsed_end,
        search_query=q,
        financial_year=financial_year,
        month=month,
        supplier_id=supplier_id,
        material_id=material_id,
        state=state,
        gst_type=gst_type,
        status=status,
        payment_mode=payment_mode,
        sort_by=sort_by
    )

    total_amount = sum(float(inv["grand_total"] or 0) for inv in invoices)
    today_str = date.today().strftime("%d-%b-%Y")

    html = render_template(
        "purchase_report_pdf.html",
        invoices=invoices,
        q=q,
        total_amount=total_amount,
        today_str=today_str,
        date_filter=date_filter,
        year=year,
        financial_year=financial_year,
        month=month,
        start_date=start_date,
        end_date=end_date
    )

    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buf, link_callback=_fetch_pdf_resource)
    pdf_bytes = buf.getvalue()

    filename = get_report_filename("purchase_report", "pdf", date_filter, year, month, start_date, end_date)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(pdf_bytes),
        }
    )


# ── Add & Edit & View & Print ─────────────────────────────────────────────────

@purchase_bp.route("/purchase/add", methods=["GET", "POST"])
def add_purchase_invoice():
    parties = get_all_parties()
    materials = get_all_materials()
    company = get_company()
    company_state_code = company["state_code"] if company else ""
    suppliers = [p for p in parties if p["party_type"] in {"SUPPLIER", "BOTH"}]

    if request.method == "POST":
        errors = _validate_header(request.form)
        material_ids = request.form.getlist("material_id[]")
        qtys = request.form.getlist("qty[]")
        weights = request.form.getlist("weight[]")
        pieces_list = request.form.getlist("pieces[]")
        rates = request.form.getlist("rate[]")
        amounts = request.form.getlist("amount[]")
        gst_percentages = request.form.getlist("gst_percentage[]")

        items = []
        for i in range(len(material_ids)):
            mid = material_ids[i].strip()
            if not mid:
                continue
            qty_val = float(qtys[i] or 0)
            rate_val = float(rates[i] or 0)
            w_val = float(weights[i] or 0)
            p_val = int(pieces_list[i] or 0)
            
            # Row verification: material, rate, weight or pieces required
            if qty_val <= 0:
                errors[f"row_{i}_qty"] = "Quantity must be greater than zero."
            if rate_val <= 0:
                errors[f"row_{i}_rate"] = "Rate is required."
            if w_val <= 0 and p_val <= 0:
                errors[f"row_{i}_weight_pieces"] = "Either Weight or Pieces is required."

            items.append({
                "material_id": int(mid),
                "qty": qty_val,
                "weight": w_val,
                "pieces": p_val,
                "rate": rate_val,
                "amount": float(amounts[i] or 0),
                "gst_percentage": float(gst_percentages[i] or 0),
            })

        if not items:
            errors["items"] = "Add at least one item."

        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors=errors,
                today=date.today().isoformat(),
            )

        supplier = get_party_by_id(int(request.form["supplier_id"]))
        supplier_state_code = supplier["state_code"] if supplier else ""

        try:
            invoice_id = create_purchase_invoice(
                party_id=request.form["supplier_id"],
                invoice_date=request.form["invoice_date"],
                supplier_invoice_number=request.form.get("supplier_invoice_number"),
                payment_mode=request.form.get("payment_mode"),
                transporter=request.form.get("transporter"),
                vehicle_number=request.form.get("vehicle_number"),
                remarks=request.form.get("remarks"),
                items=items,
                company_state_code=company_state_code,
                party_state_code=supplier_state_code,
                eway_bill_number=request.form.get("eway_bill_number"),
                reference_number=request.form.get("reference_number"),
                status=request.form.get("status", "CONFIRMED"),
                created_by=None
            )
        except Exception as exc:
            flash(str(exc), "danger")
            return render_template(
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors={},
                today=date.today().isoformat(),
            )

        flash("Purchase invoice created successfully.", "success")
        return redirect(url_for("purchase.view_purchase_invoice", invoice_id=invoice_id))

    return render_template(
        "purchase_form.html",
        form=None,
        suppliers=suppliers,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        errors={},
        today=date.today().isoformat(),
    )


@purchase_bp.route("/purchase/<int:invoice_id>/view")
def view_purchase_invoice(invoice_id):
    increment_purchase_print_count(invoice_id)
    ctx = _invoice_context(invoice_id)
    return render_template("purchase_invoice.html", **ctx)


@purchase_bp.route("/purchase/<int:invoice_id>/pdf")
def download_purchase_pdf(invoice_id):
    increment_purchase_pdf_download_count(invoice_id)
    ctx = _invoice_context(invoice_id)
    html = render_template("purchase_invoice_pdf.html", **ctx)
    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buf, link_callback=_fetch_pdf_resource)
    pdf_bytes = buf.getvalue()
    filename = f"{ctx['invoice']['purchase_invoice_number']}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(pdf_bytes)
        }
    )


@purchase_bp.route("/purchase/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit_purchase_invoice(invoice_id):
    existing = get_purchase_invoice_by_id(invoice_id)
    if not existing:
        flash("Purchase invoice not found.", "danger")
        return redirect(url_for("purchase.purchase"))

    parties = get_all_parties()
    materials = get_all_materials()
    company = get_company()
    company_state_code = company["state_code"] if company else ""
    suppliers = [p for p in parties if p["party_type"] in {"SUPPLIER", "BOTH"}]

    if request.method == "POST":
        errors = _validate_header(request.form)
        material_ids = request.form.getlist("material_id[]")
        qtys = request.form.getlist("qty[]")
        weights = request.form.getlist("weight[]")
        pieces_list = request.form.getlist("pieces[]")
        rates = request.form.getlist("rate[]")
        amounts = request.form.getlist("amount[]")
        gst_percentages = request.form.getlist("gst_percentage[]")

        items = []
        for i in range(len(material_ids)):
            mid = material_ids[i].strip()
            if not mid:
                continue
            qty_val = float(qtys[i] or 0)
            rate_val = float(rates[i] or 0)
            w_val = float(weights[i] or 0)
            p_val = int(pieces_list[i] or 0)
            
            if qty_val <= 0:
                errors[f"row_{i}_qty"] = "Quantity must be greater than zero."
            if rate_val <= 0:
                errors[f"row_{i}_rate"] = "Rate is required."
            if w_val <= 0 and p_val <= 0:
                errors[f"row_{i}_weight_pieces"] = "Either Weight or Pieces is required."

            items.append({
                "material_id": int(mid),
                "qty": qty_val,
                "weight": w_val,
                "pieces": p_val,
                "rate": rate_val,
                "amount": float(amounts[i] or 0),
                "gst_percentage": float(gst_percentages[i] or 0),
            })

        if not items:
            errors["items"] = "Add at least one item."

        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors=errors,
                today=existing["invoice_date"],
                invoice_id=invoice_id,
            )

        supplier = get_party_by_id(int(request.form["supplier_id"]))
        supplier_state_code = supplier["state_code"] if supplier else ""
        
        try:
            update_purchase_invoice(
                invoice_id,
                request.form["supplier_id"],
                request.form["invoice_date"],
                request.form.get("supplier_invoice_number"),
                request.form.get("payment_mode"),
                request.form.get("transporter"),
                request.form.get("vehicle_number"),
                request.form.get("remarks"),
                items,
                company_state_code,
                supplier_state_code,
                eway_bill_number=request.form.get("eway_bill_number"),
                reference_number=request.form.get("reference_number"),
                status=request.form.get("status", "CONFIRMED"),
                updated_by=None
            )
        except Exception as e:
            flash(str(e), "danger")
            return render_template(
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors={},
                today=existing["invoice_date"],
                invoice_id=invoice_id,
            )
            
        flash("Purchase invoice updated successfully.", "success")
        return redirect(url_for("purchase.view_purchase_invoice", invoice_id=invoice_id))

    existing_items = get_purchase_invoice_items(invoice_id)
    form_data = dict(existing)
    form_data["supplier_id"] = str(existing["supplier_id"] or "")
    form_data["invoice_date"] = existing["invoice_date"]
    form_data["supplier_invoice_number"] = existing["supplier_invoice_number"] or ""
    form_data["payment_mode"] = existing["payment_mode"] or ""
    form_data["transporter"] = existing["transporter"] or ""
    form_data["vehicle_number"] = existing["vehicle_number"] or ""
    form_data["remarks"] = existing["remarks"] or ""
    form_data["eway_bill_number"] = existing["eway_bill_number"] or ""
    form_data["reference_number"] = existing["reference_number"] or ""
    form_data["status"] = existing["status"] or "CONFIRMED"

    return render_template(
        "purchase_form.html",
        form=form_data,
        suppliers=suppliers,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        errors={},
        today=existing["invoice_date"],
        invoice_id=invoice_id,
        existing_items=existing_items,
    )


@purchase_bp.route("/purchase/<int:invoice_id>/delete", methods=["POST"])
def delete_purchase_invoice_route(invoice_id):
    existing = get_purchase_invoice_by_id(invoice_id)
    if not existing:
        flash("Purchase invoice not found.", "danger")
        return redirect(url_for("purchase.purchase"))
    delete_purchase_invoice(invoice_id)
    flash("Purchase invoice deleted successfully.", "warning")
    return redirect(url_for("purchase.purchase"))


# ── Purchase Register, Exporter & Duplicator ─────────────────────────────────

@purchase_bp.route("/purchase/register")
def purchase_register():
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    supplier_id = request.args.get("supplier_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    rows = get_purchase_register_rows(
        start_date=parsed_start,
        end_date=parsed_end,
        financial_year=financial_year,
        month=month,
        supplier_id=supplier_id,
        material_id=material_id
    )

    unique_invoices = {}
    unique_suppliers = set()
    total_taxable = 0.0
    total_gst = 0.0
    
    for r in rows:
        unique_invoices[r["purchase_number"]] = float(r["grand_total"] or 0.0)
        unique_suppliers.add(r["supplier_name"])
        total_taxable += float(r["taxable_value"] or 0.0)
        total_gst += float(r["gst_total"] or 0.0)

    total_invoices = len(unique_invoices)
    total_suppliers = len(unique_suppliers)
    total_invoice_value = sum(unique_invoices.values())
    
    avg_invoice_value = total_invoice_value / total_invoices if total_invoices > 0 else 0.0
    highest_invoice = max(unique_invoices.values()) if unique_invoices else 0.0
    lowest_invoice = min(unique_invoices.values()) if unique_invoices else 0.0

    monthly_analytics = get_purchase_monthly_analytics()
    top_suppliers = get_top_suppliers()
    top_materials = get_top_purchased_materials()

    parties = get_all_parties()
    supplier_parties = [p for p in parties if p["party_type"] in {"SUPPLIER", "BOTH"}]
    materials = get_all_materials()

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(rows)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_rows = rows[offset : offset + per_page]

    return render_template(
        "purchase_register.html",
        rows=paginated_rows,
        parties=supplier_parties,
        materials=materials,
        total_invoices=total_invoices,
        total_suppliers=total_suppliers,
        total_taxable=total_taxable,
        total_gst=total_gst,
        total_invoice_value=total_invoice_value,
        avg_invoice_value=avg_invoice_value,
        highest_invoice=highest_invoice,
        lowest_invoice=lowest_invoice,
        monthly_analytics=monthly_analytics,
        top_suppliers=top_suppliers,
        top_materials=top_materials,
        date_filter=date_filter,
        year=year,
        financial_year=financial_year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        supplier_id=supplier_id,
        material_id=material_id,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )


@purchase_bp.route("/purchase/register/export")
def export_purchase_register():
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    financial_year = request.args.get("financial_year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    supplier_id = request.args.get("supplier_id", "all").strip()
    material_id = request.args.get("material_id", "all").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    rows = get_purchase_register_rows(
        start_date=parsed_start,
        end_date=parsed_end,
        financial_year=financial_year,
        month=month,
        supplier_id=supplier_id,
        material_id=material_id
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Purchase Register"
    ws.views.sheetView[0].showGridLines = True

    title_font = Font(name="Calibri", size=16, bold=True, color="1E3A8A")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
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
    ws["A1"] = "Right Ewaste Recycle Pvt. Ltd. - Purchase Register Report"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    headers = [
        "Purchase Date", "Purchase Number", "Supplier Name", "Supplier GSTIN", "State", 
        "Material", "Taxable Amount (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", 
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
        ws.cell(row=row_num, column=2, value=item["purchase_number"]).alignment = center_align
        ws.cell(row=row_num, column=3, value=item["supplier_name"]).alignment = left_align
        ws.cell(row=row_num, column=4, value=item["supplier_gstin"] or "—").alignment = center_align
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

    filename = get_report_filename("purchase_register", "xlsx", date_filter, year, month, start_date, end_date)
    return Response(
        xlsx_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(xlsx_data),
        }
    )


@purchase_bp.route("/purchase/<int:invoice_id>/duplicate")
def duplicate_purchase_invoice(invoice_id):
    existing = get_purchase_invoice_by_id(invoice_id)
    if not existing:
        flash("Purchase invoice not found.", "danger")
        return redirect(url_for("purchase.purchase"))
        
    items = get_purchase_invoice_items(invoice_id)
    new_items = []
    for it in items:
        new_items.append({
            "material_id": it["material_id"],
            "qty": it["quantity"],
            "weight": it["weight"],
            "pieces": it["pieces"],
            "rate": it["rate"],
            "amount": it["amount"],
            "gst_percentage": it["gst_percentage"]
        })
        
    company = get_company()
    company_state_code = company["state_code"] if company else ""
    supplier = get_party_by_id(existing["supplier_id"])
    supplier_state_code = supplier["state_code"] if supplier else ""
    
    try:
        new_id = create_purchase_invoice(
            party_id=existing["supplier_id"],
            invoice_date=date.today().isoformat(),
            supplier_invoice_number=existing["supplier_invoice_number"],
            payment_mode=existing["payment_mode"],
            transporter=existing["transporter"],
            vehicle_number=existing["vehicle_number"],
            remarks=f"Duplicate of {existing['purchase_invoice_number']}",
            items=new_items,
            company_state_code=company_state_code,
            party_state_code=supplier_state_code,
            eway_bill_number=existing["eway_bill_number"],
            reference_number=existing["reference_number"],
            status="DRAFT",
            created_by=None
        )
        flash("Invoice duplicated successfully as a DRAFT. Please review and update details.", "success")
        return redirect(url_for("purchase.edit_purchase_invoice", invoice_id=new_id))
    except Exception as e:
        flash(f"Failed to duplicate invoice: {e}", "danger")
        return redirect(url_for("purchase.purchase"))


# ── Internal PDF resource loader ──────────────────────────────────────────────

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


def _validate_header(form):
    errors = {}
    if not form.get("supplier_id", "").strip():
        errors["supplier_id"] = "Supplier is required."
    if not form.get("invoice_date", "").strip():
        errors["invoice_date"] = "Invoice date is required."
    return errors