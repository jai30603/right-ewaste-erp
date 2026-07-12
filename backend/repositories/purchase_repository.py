from database import get_connection
from services.purchase_service import generate_purchase_invoice_number, build_purchase_totals


def get_all_purchase_invoices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            pi.*,
            p.company_name,
            (SELECT COUNT(*) FROM purchase_invoice_item WHERE purchase_invoice_id = pi.id) AS item_count
        FROM purchase_invoice pi
        LEFT JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1
        ORDER BY pi.created_at DESC
    """)
    invoices = cursor.fetchall()
    conn.close()
    return invoices


def get_purchase_invoice_by_id(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pi.*, p.company_name
        FROM purchase_invoice pi
        LEFT JOIN party p ON pi.supplier_id = p.id
        WHERE pi.id = ?
    """, (invoice_id,))
    invoice = cursor.fetchone()
    conn.close()
    return invoice


def get_purchase_invoice_items(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pii.*, m.material_name, m.uom, m.gst_percentage
        FROM purchase_invoice_item pii
        LEFT JOIN material m ON pii.material_id = m.id
        WHERE pii.purchase_invoice_id = ?
        ORDER BY pii.id
    """, (invoice_id,))
    items = cursor.fetchall()
    conn.close()
    return items


def create_purchase_invoice(party_id, invoice_date, supplier_invoice_number, payment_mode, transporter, vehicle_number, remarks, items, company_state_code, party_state_code):
    totals = build_purchase_totals(items, company_state_code, party_state_code)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN")
        invoice_number = generate_purchase_invoice_number()
        cursor.execute("""
            INSERT INTO purchase_invoice (
                purchase_invoice_number, invoice_date, supplier_id, supplier_invoice_number,
                payment_mode, vehicle_number, transporter, remarks, subtotal, cgst, sgst, igst,
                gst_amount, round_off, grand_total, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            invoice_number,
            invoice_date,
            party_id,
            supplier_invoice_number or None,
            payment_mode or None,
            vehicle_number or None,
            transporter or None,
            remarks or None,
            totals["subtotal"],
            totals["cgst"],
            totals["sgst"],
            totals["igst"],
            totals["gst_amount"],
            totals["round_off"],
            totals["grand_total"],
            "CONFIRMED",
        ))
        invoice_id = cursor.lastrowid
        for item in items:
            cursor.execute("""
                INSERT INTO purchase_invoice_item (
                    purchase_invoice_id, material_id, quantity, weight, pieces, rate, amount
                ) VALUES (?,?,?,?,?,?,?)
            """, (
                invoice_id,
                item["material_id"],
                item["qty"],
                item["weight"],
                item["pieces"],
                item["rate"],
                item["amount"],
            ))
        conn.execute("COMMIT")
        return invoice_id
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def update_purchase_invoice(invoice_id, party_id, invoice_date, supplier_invoice_number, payment_mode, transporter, vehicle_number, remarks, items, company_state_code, party_state_code):
    totals = build_purchase_totals(items, company_state_code, party_state_code)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN")
        cursor.execute("""
            UPDATE purchase_invoice SET
                supplier_id = ?, invoice_date = ?, supplier_invoice_number = ?, payment_mode = ?,
                vehicle_number = ?, transporter = ?, remarks = ?, subtotal = ?, cgst = ?, sgst = ?,
                igst = ?, gst_amount = ?, round_off = ?, grand_total = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            party_id,
            invoice_date,
            supplier_invoice_number or None,
            payment_mode or None,
            vehicle_number or None,
            transporter or None,
            remarks or None,
            totals["subtotal"],
            totals["cgst"],
            totals["sgst"],
            totals["igst"],
            totals["gst_amount"],
            totals["round_off"],
            totals["grand_total"],
            invoice_id,
        ))
        cursor.execute("DELETE FROM purchase_invoice_item WHERE purchase_invoice_id = ?", (invoice_id,))
        for item in items:
            cursor.execute("""
                INSERT INTO purchase_invoice_item (
                    purchase_invoice_id, material_id, quantity, weight, pieces, rate, amount
                ) VALUES (?,?,?,?,?,?,?)
            """, (
                invoice_id,
                item["material_id"],
                item["qty"],
                item["weight"],
                item["pieces"],
                item["rate"],
                item["amount"],
            ))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def delete_purchase_invoice(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE purchase_invoice
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (invoice_id,))
    conn.commit()
    conn.close()


def search_purchase_invoice(keyword):
    like = f"%{keyword}%"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            pi.*,
            p.company_name,
            (SELECT COUNT(*) FROM purchase_invoice_item WHERE purchase_invoice_id = pi.id) AS item_count
        FROM purchase_invoice pi
        LEFT JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1
          AND (
              pi.purchase_invoice_number LIKE ? OR
              p.company_name LIKE ? OR
              pi.invoice_date LIKE ?
          )
        ORDER BY pi.created_at DESC
    """, (like, like, like))
    invoices = cursor.fetchall()
    conn.close()
    return invoices
