from datetime import datetime
from database import get_connection


def generate_invoice_number():
    year = datetime.now().year
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(CAST(SUBSTR(invoice_number, 10) AS INTEGER)) "
        "FROM sales_invoice WHERE invoice_number LIKE ?",
        (f"INV-{year}-%",)
    )
    max_num = cursor.fetchone()[0] or 0
    conn.close()
    return f"INV-{year}-{(max_num + 1):05d}"


def get_all_invoices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            si.*,
            p.company_name,
            (SELECT COUNT(*) FROM sales_invoice_item WHERE sales_invoice_id = si.id) AS item_count
        FROM sales_invoice si
        LEFT JOIN party p ON si.party_id = p.id
        ORDER BY si.created_at DESC
    """)
    invoices = cursor.fetchall()
    conn.close()
    return invoices


def get_invoice_by_id(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT si.*, p.company_name
        FROM sales_invoice si
        LEFT JOIN party p ON si.party_id = p.id
        WHERE si.id = ?
    """, (invoice_id,))
    invoice = cursor.fetchone()
    conn.close()
    return invoice


def get_invoice_items(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sii.*, m.material_name, m.uom
        FROM sales_invoice_item sii
        LEFT JOIN material m ON sii.material_id = m.id
        WHERE sii.sales_invoice_id = ?
        ORDER BY sii.id
    """, (invoice_id,))
    items = cursor.fetchall()
    conn.close()
    return items


def create_sales_invoice(
    party_id, invoice_date, payment_mode,
    transporter, vehicle_number, remarks,
    items                               # list of dicts
):
    invoice_number = generate_invoice_number()

    subtotal = sum(i["amount"] for i in items)
    grand_total = subtotal              # GST will be added in Phase 3

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sales_invoice (
            invoice_number, invoice_date, party_id,
            payment_mode, transporter, vehicle_number,
            subtotal, cgst, sgst, igst, round_off, grand_total,
            remarks, status
        ) VALUES (?,?,?,?,?,?,?,0,0,0,0,?,?,?)
    """, (
        invoice_number, invoice_date, party_id,
        payment_mode or None, transporter or None, vehicle_number or None,
        subtotal, grand_total, remarks or None,
        "DRAFT"
    ))

    invoice_id = cursor.lastrowid

    for item in items:
        cursor.execute("""
            INSERT INTO sales_invoice_item
                (sales_invoice_id, material_id, quantity, weight, pieces, rate, amount)
            VALUES (?,?,?,?,?,?,?)
        """, (
            invoice_id,
            item["material_id"],
            item["qty"],
            item["weight"],
            item["pieces"],
            item["rate"],
            item["amount"],
        ))

    conn.commit()
    conn.close()
    return invoice_id
