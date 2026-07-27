import logging
from datetime import datetime
from database import get_connection

logger = logging.getLogger(__name__)

try:
    from backend.services.invoice_service import calculate_gst
except ModuleNotFoundError:
    from services.invoice_service import calculate_gst


def generate_purchase_invoice_number(conn=None):
    """
    Service layer wrapper to generate the PUR-YYYY-000001 format
    """
    if not conn:
        conn = get_connection()
    from repositories import settings_repository
    return settings_repository.increment_and_get_number("PURCHASE", conn)


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
        
        if rate <= 0:
            errors_dict[f"row_{idx}_rate"] = "Rate is required."
            
        if tracking_type == "WEIGHT_ONLY":
            item["qty"] = 0.0
            item["amount"] = round(w * rate, 2)
            if w <= 0:
                errors_dict[f"row_{idx}_weight"] = f"Weight is required for weight-only material '{mat['material_name']}'."
        elif tracking_type == "QUANTITY_ONLY":
            item["weight"] = 0.0
            item["amount"] = round(qty * rate, 2)
            if qty <= 0:
                errors_dict[f"row_{idx}_qty"] = f"Quantity is required for quantity-only material '{mat['material_name']}'."
        else:
            if qty <= 0:
                errors_dict[f"row_{idx}_qty"] = f"Quantity is required for material '{mat['material_name']}'."
            if w <= 0:
                errors_dict[f"row_{idx}_weight"] = f"Weight is required for material '{mat['material_name']}'."
            
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
