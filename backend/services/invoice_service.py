from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from database import get_connection


MONEY_PLACES = Decimal("0.01")


def _money(value):
    try:
        return Decimal(str(value)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError("Amounts must be valid numbers.") from error


def _next_invoice_number(cursor):
    year = datetime.now().year
    prefix = f"INV-{year}-"
    cursor.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(invoice_number, ?) AS INTEGER)), 0) "
        "FROM sales_invoice WHERE invoice_number LIKE ?",
        (len(prefix) + 1, f"{prefix}%"),
    )
    return f"{prefix}{cursor.fetchone()[0] + 1:05d}"


def calculate_gst(company_state_code, party_state_code, subtotal, gst_percentage=18):
    subtotal = _money(subtotal)
    gst_amount = _money(subtotal * _money(gst_percentage) / Decimal("100"))
    if company_state_code == party_state_code:
        cgst = _money(gst_amount / 2)
        return {"cgst": cgst, "sgst": _money(gst_amount - cgst), "igst": Decimal("0.00")}
    return {"cgst": Decimal("0.00"), "sgst": Decimal("0.00"), "igst": gst_amount}


def calculate_totals(items, company_state_code, party_state_code):
    totals = {"subtotal": Decimal("0.00"), "cgst": Decimal("0.00"), "sgst": Decimal("0.00"), "igst": Decimal("0.00")}
    for item in items:
        quantity = _money(item["quantity"])
        rate = _money(item["rate"])
        if quantity <= 0 or rate < 0:
            raise ValueError("Invoice quantities must be positive and rates cannot be negative.")
        amount = _money(quantity * rate)
        gst = calculate_gst(company_state_code, party_state_code, amount, item.get("gst_percentage", 18))
        totals["subtotal"] += amount
        for tax in ("cgst", "sgst", "igst"):
            totals[tax] += gst[tax]
    if not items:
        raise ValueError("An invoice must contain at least one item.")
    totals = {key: _money(value) for key, value in totals.items()}
    totals["grand_total"] = _money(sum(totals.values()))
    return totals


def create_sales_invoice(party_id, payment_mode, transporter, vehicle_number, items, remarks=""):
    """Create a fully validated sales invoice as one atomic transaction."""
    if not isinstance(items, list):
        raise ValueError("Invoice items must be a list.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        company = cursor.execute("SELECT * FROM company WHERE is_active = 1 LIMIT 1").fetchone()
        party = cursor.execute("SELECT * FROM party WHERE id = ? AND is_active = 1", (party_id,)).fetchone()
        if company is None:
            raise ValueError("Set up an active company before creating invoices.")
        if party is None or party["party_type"] not in {"CUSTOMER", "BOTH"}:
            raise ValueError("Choose an active customer for this sales invoice.")

        enriched_items = []
        for item in items:
            try:
                material_id = int(item["material_id"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Every invoice item needs a valid material.") from error
            material = cursor.execute(
                "SELECT id, gst_percentage FROM material WHERE id = ? AND is_active = 1", (material_id,)
            ).fetchone()
            if material is None:
                raise ValueError("Every invoice item must use an active material.")
            enriched_items.append({**item, "material_id": material_id, "gst_percentage": material["gst_percentage"]})

        totals = calculate_totals(enriched_items, company["state_code"], party["state_code"])
        invoice_number = _next_invoice_number(cursor)
        cursor.execute(
            """INSERT INTO sales_invoice (
                invoice_number, invoice_date, party_id, payment_mode, transporter, vehicle_number,
                subtotal, cgst, sgst, igst, round_off, grand_total, remarks
            ) VALUES (?, DATE('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (invoice_number, party_id, payment_mode, transporter, vehicle_number,
             *[str(totals[key]) for key in ("subtotal", "cgst", "sgst", "igst")],
             "0.00", str(totals["grand_total"]), remarks),
        )
        invoice_id = cursor.lastrowid
        for item in enriched_items:
            quantity, rate = _money(item["quantity"]), _money(item["rate"])
            cursor.execute(
                "INSERT INTO sales_invoice_item (sales_invoice_id, material_id, quantity, rate, amount) VALUES (?, ?, ?, ?, ?)",
                (invoice_id, item["material_id"], str(quantity), str(rate), str(_money(quantity * rate))),
            )
        conn.commit()
        return invoice_number
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
