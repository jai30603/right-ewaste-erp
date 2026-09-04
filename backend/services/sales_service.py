import logging
from repositories import sales_repository

logger = logging.getLogger(__name__)

def generate_sales_invoice_number():
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    inv_num = sales_repository._generate_invoice_number(cursor)
    conn.close()
    return inv_num

def calculate_invoice_totals(items, company_state_code, party_state_code):
    from services.calculation_service import calculate_invoice_result
    res = calculate_invoice_result(items, company_state_code, party_state_code)
    return {
        "subtotal": res["taxable_total"],
        "cgst": res["cgst_total"],
        "sgst": res["sgst_total"],
        "igst": res["igst_total"],
        "round_off": res["round_off"],
        "grand_total": res["grand_total"]
    }

def create_sales_invoice(*args, **kwargs):
    logger.info("Service Layer: Creating sales invoice")
    return sales_repository.create_sales_invoice(*args, **kwargs)

def update_sales_invoice(*args, **kwargs):
    logger.info("Service Layer: Updating sales invoice")
    return sales_repository.update_sales_invoice(*args, **kwargs)

def check_stock_available(material_id, needed_qty, needed_weight=0.0, exclude_invoice_id=None):
    """Validate both supported stock dimensions against movement-backed inventory."""
    from database import get_connection

    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(current_quantity), 0), COALESCE(SUM(current_weight), 0)
               FROM inventory_balance WHERE material_id = ?""",
            (material_id,),
        ).fetchone()
        available_qty, available_weight = float(row[0] or 0), float(row[1] or 0)
        if exclude_invoice_id:
            existing = conn.execute(
                """SELECT COALESCE(SUM(quantity), 0), COALESCE(SUM(weight), 0)
                   FROM sales_invoice_item WHERE sales_invoice_id = ? AND material_id = ?""",
                (exclude_invoice_id, material_id),
            ).fetchone()
            available_qty += float(existing[0] or 0)
            available_weight += float(existing[1] or 0)
        return available_qty >= float(needed_qty or 0) and available_weight >= float(needed_weight or 0)
    finally:
        conn.close()

def validate_status_transition(old_status, new_status):
    if old_status == new_status:
        return True
    if old_status == "DRAFT":
        return new_status in ["DRAFT", "CONFIRMED", "CANCELLED"]
    if old_status == "CONFIRMED":
        return new_status in ["CONFIRMED", "PRINTED", "PAID", "CANCELLED"]
    if old_status == "PRINTED":
        return new_status in ["PRINTED", "PAID", "CANCELLED"]
    if old_status in ["PAID", "CANCELLED"]:
        return False
    return True
