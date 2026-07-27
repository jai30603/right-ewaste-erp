import io
import os
from datetime import date, timedelta
import calendar
from flask import Blueprint, render_template, request, Response, abort
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from repositories.inventory_repository import (
    get_stock_summary, get_material_ledger, get_all_categories,
    get_inventory, get_dashboard_summary, get_stock_movements
)
from repositories.material_repository import get_material_by_id
from services.inventory_service import calculate_running_balance, adjust_stock, InventoryError
from backend.common.utils.date_utils import get_filter_date_range
from backend.common.utils.format_utils import get_report_filename
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info
from backend.services.pdf_service import render_to_pdf, send_pdf_response

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/inventory/dashboard")
def inventory_dashboard():
    data = get_dashboard_summary()
    return render_template(
        "inventory/inventory_dashboard.html",
        snapshot=data["snapshot"],
        categories=data["categories"],
        states=data["states"],
        recent_movements=get_stock_movements(limit=8),
    )


@inventory_bp.route("/inventory")
def inventory():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    summary = get_stock_summary(q, category, parsed_start, parsed_end)
    categories = get_all_categories()

    # Calculate Summary Metrics
    total_materials = len(summary)
    low_stock_alerts = sum(1 for item in summary if item["current_stock"] < 10)
    total_purchased = sum(item["purchased_qty"] for item in summary)
    total_sold = sum(item["sold_qty"] for item in summary)
    total_stock_value = sum(item["current_stock"] * item["rate"] for item in summary)

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(summary)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_summary = summary[offset : offset + per_page]

    return render_template(
        "inventory/inventory.html",
        summary=paginated_summary,
        categories=categories,
        q=q,
        category=category,
        date_filter=date_filter,
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        total_materials=total_materials,
        low_stock_alerts=low_stock_alerts,
        total_purchased=total_purchased,
        total_sold=total_sold,
        total_stock_value=total_stock_value,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )



@inventory_bp.route("/inventory/<int:material_id>")
def inventory_details(material_id):
    material = get_material_by_id(material_id)
    if not material:
        abort(404)
    states = get_inventory(inventory_state="all")
    stock_rows = [row for row in states if row["id"] == material_id]
    stock = stock_rows[0] if stock_rows else {"current_stock": 0, "current_weight": 0, "inventory_states": ""}
    movements = get_stock_movements(material_id=material_id, limit=50)
    return render_template("inventory/inventory_details.html", material=material, stock=stock, movements=movements)


@inventory_bp.route("/inventory/movements")
def movement_history():
    material_id = request.args.get("material_id", type=int)
    movement_type = request.args.get("movement_type", "all")
    materials = get_inventory()
    return render_template(
        "inventory/inventory_movements.html",
        movements=get_stock_movements(material_id, movement_type, limit=250),
        materials=materials,
        material_id=material_id,
        movement_type=movement_type,
    )


@inventory_bp.route("/inventory/adjust", methods=["GET", "POST"])
def stock_adjustment():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        abort(403)
    materials = get_inventory()
    if request.method == "POST":
        try:
            adjust_stock(
                material_id=int(request.form.get("material_id", 0)),
                direction=request.form.get("direction", ""),
                quantity=request.form.get("quantity", 0),
                weight=request.form.get("weight", 0),
                reason=request.form.get("reason", ""),
                performed_by=user["username"],
            )
            flash_success("Stock adjustment recorded successfully.")
            return redirect(url_for("inventory.inventory"))
        except (ValueError, InventoryError) as exc:
            flash_error(str(exc))
    return render_template("inventory/inventory_adjustment.html", materials=materials)


@inventory_bp.route("/inventory/<int:material_id>/ledger")
def material_ledger(material_id):
    material = get_material_by_id(material_id)
    if not material:
        abort(404)

    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    raw_ledger = get_material_ledger(material_id, parsed_start, parsed_end)
    ledger = calculate_running_balance(raw_ledger)

    current_stock = ledger[-1]["balance"] if ledger else 0.0
    rates = [item["rate"] for item in raw_ledger if item["type"] == "Purchase"]
    avg_rate = sum(rates) / len(rates) if rates else 0.0

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(ledger)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_ledger = ledger[offset : offset + per_page]

    return render_template(
        "inventory/inventory_ledger.html",
        material=material,
        ledger=paginated_ledger,
        current_stock=current_stock,
        rate=avg_rate,
        date_filter=date_filter,
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )


@inventory_bp.route("/inventory/export")
def export_inventory():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    summary = get_stock_summary(q, category, parsed_start, parsed_end)

    wb = Workbook()
    ws = wb.active
    ws.title = "Stock Summary"
    ws.views.sheetView[0].showGridLines = True

    # Style definitions - Teal theme
    title_font = Font(name="Calibri", size=16, bold=True, color="004D40")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="00796B", end_color="00796B", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    border_thin = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    ws.merge_cells("A1:H1")
    ws["A1"] = "Right Ewaste Recycle Pvt. Ltd. - Stock Summary Report"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    headers = [
        "Material Code", "Material Name", "Category", 
        "Purchased Qty", "Sold Qty", "Current Stock", 
        "Unit", "Stock Value (₹)"
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = border_thin
    ws.row_dimensions[3].height = 25

    row_num = 4
    for item in summary:
        ws.cell(row=row_num, column=1, value=item["code"]).alignment = center_align
        ws.cell(row=row_num, column=2, value=item["name"]).alignment = left_align
        ws.cell(row=row_num, column=3, value=item["category"] or "—").alignment = center_align
        
        c_purchased = ws.cell(row=row_num, column=4, value=item["purchased_qty"])
        c_purchased.number_format = '#,##0.00'
        c_purchased.alignment = right_align
        
        c_sold = ws.cell(row=row_num, column=5, value=item["sold_qty"])
        c_sold.number_format = '#,##0.00'
        c_sold.alignment = right_align
        
        c_stock = ws.cell(row=row_num, column=6, value=item["current_stock"])
        c_stock.number_format = '#,##0.00'
        c_stock.alignment = right_align
        
        ws.cell(row=row_num, column=7, value=item["unit"]).alignment = center_align
        
        stock_val = float(item["current_stock"] or 0.0) * float(item["rate"] or 0.0)
        c_val = ws.cell(row=row_num, column=8, value=stock_val)
        c_val.number_format = '#,##0.00'
        c_val.alignment = right_align

        for col_idx in range(1, 9):
            ws.cell(row=row_num, column=col_idx).border = border_thin

        ws.row_dimensions[row_num].height = 20
        row_num += 1

    for col_idx in range(1, 9):
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

    filename = get_report_filename("stock_summary_report", "xlsx", date_filter, year, month, start_date, end_date)
    return Response(
        xlsx_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(xlsx_data),
        }
    )


@inventory_bp.route("/inventory/export/pdf")
def export_inventory_pdf():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip()
    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    summary = get_stock_summary(q, category, parsed_start, parsed_end)

    total_stock_value = sum(item["current_stock"] * item["rate"] for item in summary)
    today_str = date.today().strftime("%d-%b-%Y")

    pdf_bytes = render_to_pdf(
        "reports/inventory_report_pdf.html",
        {
            "summary": summary,
            "total_stock_value": total_stock_value,
            "today_str": today_str,
            "category": category,
            "date_filter": date_filter,
            "year": year,
            "month": month,
            "start_date": start_date,
            "end_date": end_date
        }
    )

    filename = get_report_filename("stock_summary_report", "pdf", date_filter, year, month, start_date, end_date)
    return send_pdf_response(pdf_bytes, filename)


@inventory_bp.route("/inventory/<int:material_id>/ledger/export")
def export_ledger(material_id):
    material = get_material_by_id(material_id)
    if not material:
        abort(404)

    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    raw_ledger = get_material_ledger(material_id, parsed_start, parsed_end)
    ledger = calculate_running_balance(raw_ledger)

    wb = Workbook()
    ws = wb.active
    ws.title = "Material Ledger"
    ws.views.sheetView[0].showGridLines = True

    # Style definitions - Teal theme
    title_font = Font(name="Calibri", size=16, bold=True, color="004D40")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="00796B", end_color="00796B", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    border_thin = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    ws.merge_cells("A1:G1")
    ws["A1"] = f"Right Ewaste Recycle Pvt. Ltd. - Ledger for {material['material_name']} ({material['material_code']})"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 40

    headers = [
        "Date", "Reference Number", "Type", 
        "In Qty (Purchase)", "Out Qty (Sale)", 
        "Rate (₹)", "Running Balance"
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = border_thin
    ws.row_dimensions[3].height = 25

    row_num = 4
    for item in ledger:
        ws.cell(row=row_num, column=1, value=item["date"]).alignment = center_align
        ws.cell(row=row_num, column=2, value=item["ref_number"]).alignment = center_align
        ws.cell(row=row_num, column=3, value=item["type"]).alignment = center_align
        
        c_in = ws.cell(row=row_num, column=4, value=item["qty"] if item["type"] == "Purchase" else "—")
        if item["type"] == "Purchase":
            c_in.number_format = '#,##0.00'
        c_in.alignment = right_align
        
        c_out = ws.cell(row=row_num, column=5, value=item["qty"] if item["type"] == "Sale" else "—")
        if item["type"] == "Sale":
            c_out.number_format = '#,##0.00'
        c_out.alignment = right_align
        
        c_rate = ws.cell(row=row_num, column=6, value=item["rate"])
        c_rate.number_format = '#,##0.00'
        c_rate.alignment = right_align
        
        c_bal = ws.cell(row=row_num, column=7, value=item["balance"])
        c_bal.number_format = '#,##0.00'
        c_bal.alignment = right_align

        for col_idx in range(1, 8):
            ws.cell(row=row_num, column=col_idx).border = border_thin

        ws.row_dimensions[row_num].height = 20
        row_num += 1

    for col_idx in range(1, 8):
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

    base_filename = f"ledger_{material['material_code']}_report"
    filename = get_report_filename(base_filename, "xlsx", date_filter, year, month, start_date, end_date)
    return Response(
        xlsx_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(xlsx_data),
        }
    )


@inventory_bp.route("/inventory/<int:material_id>/ledger/export/pdf")
def export_ledger_pdf(material_id):
    material = get_material_by_id(material_id)
    if not material:
        abort(404)

    date_filter = request.args.get("date_filter", "all").strip()
    year = request.args.get("year", "all").strip()
    month = request.args.get("month", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    parsed_start, parsed_end = get_filter_date_range(date_filter, year, month, start_date, end_date)
    raw_ledger = get_material_ledger(material_id, parsed_start, parsed_end)
    ledger = calculate_running_balance(raw_ledger)

    current_stock = ledger[-1]["balance"] if ledger else 0.0
    today_str = date.today().strftime("%d-%b-%Y")
    rates = [item["rate"] for item in raw_ledger if item["type"] == "Purchase"]
    avg_rate = sum(rates) / len(rates) if rates else 0.0

    pdf_bytes = render_to_pdf(
        "reports/inventory_ledger_pdf.html",
        {
            "material": material,
            "ledger": ledger,
            "current_stock": current_stock,
            "rate": avg_rate,
            "today_str": today_str,
            "date_filter": date_filter,
            "year": year,
            "month": month,
            "start_date": start_date,
            "end_date": end_date
        }
    )

    base_filename = f"ledger_{material['material_code']}_report"
    filename = get_report_filename(base_filename, "pdf", date_filter, year, month, start_date, end_date)
    return send_pdf_response(pdf_bytes, filename)
