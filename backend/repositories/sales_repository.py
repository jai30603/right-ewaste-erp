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
            p.company_name
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
        SELECT
            si.*,
            p.company_name
        FROM sales_invoice si
        LEFT JOIN party p ON si.party_id = p.id
        WHERE si.id = ?
    """, (invoice_id,))
    invoice = cursor.fetchone()
    conn.close()
    return invoice


def create_sales_invoice(
    party_id, invoice_date, payment_mode,
    transporter, vehicle_number, remarks
):
    invoice_number = generate_invoice_number()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sales_invoice (
            invoice_number, invoice_date, party_id,
            payment_mode, transporter, vehicle_number,
            subtotal, cgst, sgst, igst, round_off, grand_total,
            remarks, status
        ) VALUES (?,?,?,?,?,?,0,0,0,0,0,0,?,?)
    """, (
        invoice_number, invoice_date, party_id,
        payment_mode or None, transporter or None,
        vehicle_number or None, remarks or None,
        "DRAFT"
    ))
    conn.commit()
    invoice_id = cursor.lastrowid
    conn.close()
    return invoice_id
