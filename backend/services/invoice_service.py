from datetime import datetime
from database import get_connection


def generate_invoice_number():

    year = datetime.now().year

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM sales_invoice")

    count = cursor.fetchone()[0] + 1

    conn.close()

    return f"INV-{year}-{count:05d}"

def get_company():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM company LIMIT 1")

    company = cursor.fetchone()

    conn.close()

    return company


def get_party(party_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM party WHERE id = ?",
        (party_id,)
    )

    party = cursor.fetchone()

    conn.close()

    return party

def create_sales_invoice(
    party_id,
    payment_mode,
    transporter,
    vehicle_number,
    items,
    remarks=""
):

    company = get_company()
    party = get_party(party_id)

    totals = calculate_totals(
        items,
        company["state_code"],
        party["state_code"]
    )

    invoice_number = generate_invoice_number()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sales_invoice(

            invoice_number,
            invoice_date,
            party_id,
            payment_mode,
            transporter,
            vehicle_number,
            subtotal,
            cgst,
            sgst,
            igst,
            round_off,
            grand_total,
            remarks

        )

        VALUES(
            ?,DATE('now'),
            ?,?,?,?,?,?,?,?,?,?,?
        )
    """,(

        invoice_number,

        party_id,

        payment_mode,

        transporter,

        vehicle_number,

        totals["subtotal"],

        totals["cgst"],

        totals["sgst"],

        totals["igst"],

        0,

        totals["grand_total"],

        remarks

    ))

    invoice_id = cursor.lastrowid

    for item in items:

        amount = item["quantity"] * item["rate"]

        cursor.execute("""

            INSERT INTO sales_invoice_item(

                sales_invoice_id,
                material_id,
                quantity,
                rate,
                amount

            )

            VALUES(?,?,?,?,?)

        """,(

            invoice_id,

            item["material_id"],

            item["quantity"],

            item["rate"],

            amount

        ))

    conn.commit()
    conn.close()

    return invoice_number

def calculate_gst(*args):
    subtotal = None
    items = None
    company_state_code = None
    party_state_code = None
    gst_percentage = None

    if len(args) == 4:
        first, second, third, fourth = args
        if isinstance(second, (list, tuple)) or (isinstance(second, dict) and "gst_percentage" in second):
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

    if gst_percentage is None:
        gst_percentage = 18
        if items:
            first_item = items[0]
            if isinstance(first_item, dict) and "gst_percentage" in first_item:
                gst_percentage = float(first_item.get("gst_percentage", 18) or 18)
    else:
        gst_percentage = float(gst_percentage)

    gst_amount = subtotal * gst_percentage / 100
    if company_state_code and party_state_code and str(company_state_code) == str(party_state_code):
        return {
            "cgst": round(gst_amount / 2, 2),
            "sgst": round(gst_amount / 2, 2),
            "igst": 0.0,
            "round_off": 0.0,
            "grand_total": round(subtotal + gst_amount, 2),
        }

    return {
        "cgst": 0.0,
        "sgst": 0.0,
        "igst": round(gst_amount, 2),
        "round_off": 0.0,
        "grand_total": round(subtotal + gst_amount, 2),
    }


def calculate_totals(items, company_state_code, party_state_code):

    subtotal = 0

    for item in items:
        subtotal += item["quantity"] * item["rate"]

    gst = calculate_gst(
        company_state_code,
        party_state_code,
        subtotal
    )

    grand_total = (
        subtotal
        + gst["cgst"]
        + gst["sgst"]
        + gst["igst"]
    )

    return {
        "subtotal": subtotal,
        "cgst": gst["cgst"],
        "sgst": gst["sgst"],
        "igst": gst["igst"],
        "grand_total": grand_total
    }