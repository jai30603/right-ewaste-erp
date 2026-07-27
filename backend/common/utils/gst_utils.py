"""
GST Utilities
Handles intra/inter state GST calculations and totals computation.
"""
from backend.common.utils.number_utils import round2, round_int

def calculate_gst(*args):
    subtotal = None
    items = None
    company_state_code = None
    party_state_code = None
    gst_percentage = None

    if len(args) == 4:
        first, second, third, fourth = args
        if isinstance(second, (list, tuple)) or (isinstance(second, dict) and ("gst_percentage" in second or "gst" in second)):
            subtotal = first
            items = second
            company_state_code = third
            party_state_code = fourth
        else:
            company_state_code = first
            party_state_code = second
            subtotal = third
            gst_percentage = fourth
    elif len(args) == 3:
        company_state_code = args[0]
        party_state_code = args[1]
        subtotal = args[2]
    elif len(args) == 2:
        subtotal = args[0]
        gst_percentage = args[1]
    elif len(args) == 1:
        subtotal = args[0]
    else:
        raise TypeError("calculate_gst expects 1-4 positional arguments")

    if isinstance(subtotal, str):
        subtotal = float(subtotal or 0)

    # 1. Calculate the total gst_amount
    if items and isinstance(items, (list, tuple)):
        gst_amount = 0.0
        for item in items:
            if isinstance(item, dict):
                # Retrieve amount
                amt = float(item.get("amount") or 0.0)
                if amt == 0.0 and "quantity" in item and "rate" in item:
                    amt = float(item.get("quantity") or 0.0) * float(item.get("rate") or 0.0)
                elif amt == 0.0 and "qty" in item and "rate" in item:
                    amt = float(item.get("qty") or 0.0) * float(item.get("rate") or 0.0)
                
                # Retrieve gst_percentage
                pct = float(item.get("gst_percentage") if item.get("gst_percentage") is not None else item.get("gst", 18))
                gst_amount += amt * pct / 100.0
            else:
                pct = float(gst_percentage if gst_percentage is not None else 18)
                gst_amount += subtotal * pct / 100.0
    else:
        if gst_percentage is None:
            gst_percentage = 18
        else:
            gst_percentage = float(gst_percentage)
        gst_amount = subtotal * gst_percentage / 100

    # 2. Determine intra / inter state tax splitting
    intra = True
    if company_state_code is not None and party_state_code is not None:
        intra = str(company_state_code).strip() == str(party_state_code).strip()
    
    cgst = round2(gst_amount / 2) if intra else 0.0
    sgst = round2(gst_amount / 2) if intra else 0.0
    igst = 0.0 if intra else round2(gst_amount)

    # 3. Calculate round-off and grand_total matching sales invoice logic
    grand_raw = subtotal + cgst + sgst + igst
    grand_round = round_int(grand_raw)
    round_off = round2(grand_round - grand_raw)

    return {
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "round_off": round_off,
        "grand_total": float(grand_round),
    }


def calculate_totals(items, company_state_code, party_state_code):
    subtotal = 0

    for item in items:
        subtotal += item.get("quantity", item.get("qty", 0)) * item["rate"]

    gst = calculate_gst(
        subtotal,
        items,
        company_state_code,
        party_state_code
    )

    return {
        "subtotal": subtotal,
        "cgst": gst["cgst"],
        "sgst": gst["sgst"],
        "igst": gst["igst"],
        "round_off": gst["round_off"],
        "grand_total": gst["grand_total"]
    }
