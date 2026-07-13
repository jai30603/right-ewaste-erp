import logging
from datetime import datetime
from database import get_connection

logger = logging.getLogger(__name__)

try:
    from backend.services.invoice_service import calculate_gst
except ModuleNotFoundError:
    from services.invoice_service import calculate_gst


def generate_purchase_invoice_number():
    """
    Service layer wrapper to generate the PUR-YYYY-000001 format
    """
    year = datetime.now().year
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT purchase_invoice_number FROM purchase_invoice WHERE purchase_invoice_number LIKE ?",
        (f"PUR-{year}-%",)
    )
    rows = cursor.fetchall()
    conn.close()
    
    max_num = 0
    for r in rows:
        val = r[0]
        try:
            num = int(val.split("-")[2])
            if num > max_num:
                max_num = num
        except (IndexError, ValueError):
            continue
            
    return f"PUR-{year}-{(max_num + 1):06d}"


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


def validate_purchase_items(items, errors_dict):
    """
    Validates material items row values against tracking types
    """
    from repositories.material_repository import get_material_by_id
    
    for idx, item in enumerate(items):
        mid = item["material_id"]
        mat = get_material_by_id(mid)
        tracking_type = mat["tracking_type"] if mat else "BOTH"
        
        qty = float(item["qty"] or 0)
        rate = float(item["rate"] or 0)
        w = float(item["weight"] or 0)
        p = int(item["pieces"] or 0)
        
        if qty <= 0:
            errors_dict[f"row_{idx}_qty"] = "Quantity must be greater than zero."
        if rate <= 0:
            errors_dict[f"row_{idx}_rate"] = "Rate is required."
            
        if tracking_type == "WEIGHT_ONLY" and w <= 0:
            errors_dict[f"row_{idx}_weight"] = f"Weight is required for weight-only material '{mat['material_name']}'."
        elif tracking_type == "PIECES_ONLY" and p <= 0:
            errors_dict[f"row_{idx}_pieces"] = f"Pieces quantity is required for pieces-only material '{mat['material_name']}'."
        elif tracking_type == "BOTH" and (w <= 0 or p <= 0):
            errors_dict[f"row_{idx}_both"] = f"Both Weight and Pieces are required for material '{mat['material_name']}'."
            
    return errors_dict


def validate_purchase_status_transition(old_status, new_status):
    if old_status == new_status:
        return True
    if old_status == "DRAFT":
        return new_status in ["DRAFT", "CONFIRMED", "CANCELLED"]
    if old_status == "CONFIRMED":
        return new_status in ["CONFIRMED", "CANCELLED"]
    if old_status == "CANCELLED":
        return False
    return True
