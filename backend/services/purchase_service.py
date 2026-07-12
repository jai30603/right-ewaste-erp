from datetime import datetime

from database import get_connection

try:
    from backend.services.invoice_service import calculate_gst
except ModuleNotFoundError:
    from services.invoice_service import calculate_gst


def generate_purchase_invoice_number():
    year = datetime.now().year
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT purchase_invoice_number FROM purchase_invoice WHERE purchase_invoice_number LIKE ? ORDER BY purchase_invoice_number DESC",
        (f"PINV-{year}-%",),
    )
    max_num = 0
    for row in cursor.fetchall():
        number = row[0] or ""
        suffix = number.split("-")[-1]
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    conn.close()
    return f"PINV-{year}-{(max_num + 1):05d}"


def build_purchase_totals(items, company_state_code, supplier_state_code):
    subtotal = round(sum(i["amount"] for i in items), 2)
    gst = calculate_gst(subtotal, items, company_state_code, supplier_state_code)
    return {
        "subtotal": subtotal,
        "cgst": gst["cgst"],
        "sgst": gst["sgst"],
        "igst": gst["igst"],
        "round_off": gst["round_off"],
        "grand_total": gst["grand_total"],
        "gst_amount": gst["cgst"] + gst["sgst"] + gst["igst"],
    }
