import logging
from datetime import datetime
from database import get_connection
from services.purchase_service import build_purchase_totals

logger = logging.getLogger(__name__)


# ── Purchase Invoice number generation ────────────────────────────────────────

def _generate_purchase_invoice_number(cursor):
    """
    Called inside transaction context to prevent duplicate purchase invoice numbers.
    """
    year = datetime.now().year
    cursor.execute(
        "SELECT MAX(CAST(SUBSTR(purchase_invoice_number, 10) AS INTEGER)) "
        "FROM purchase_invoice WHERE purchase_invoice_number LIKE ?",
        (f"PUR-{year}-%",)
    )
    max_num = cursor.fetchone()[0] or 0
    return f"PUR-{year}-{(max_num + 1):06d}"


# ── Read queries ──────────────────────────────────────────────────────────────

def get_all_purchase_invoices(
    start_date=None, end_date=None, search_query=None,
    financial_year=None, month=None, supplier_id=None,
    material_id=None, state=None, gst_type=None,
    status=None, payment_mode=None, sort_by=None
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT
            pi.*,
            p.company_name,
            p.gstin,
            p.state,
            (SELECT COUNT(*) FROM purchase_invoice_item WHERE purchase_invoice_id = pi.id) AS item_count
        FROM purchase_invoice pi
        LEFT JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1
    """
    params = []
    
    if start_date:
        query += " AND pi.invoice_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND pi.invoice_date <= ?"
        params.append(end_date)
        
    if financial_year and financial_year != "all":
        parts = financial_year.split("-")
        if len(parts) == 2:
            start_yr = int(parts[0])
            end_yr = int(parts[1])
            query += " AND pi.invoice_date >= ? AND pi.invoice_date <= ?"
            params.append(f"{start_yr}-04-01")
            params.append(f"{end_yr}-03-31")
            
    if month and month != "all":
        query += " AND strftime('%m', pi.invoice_date) = ?"
        padded_month = f"{int(month):02d}"
        params.append(padded_month)
        
    if supplier_id and supplier_id != "all":
        query += " AND pi.supplier_id = ?"
        params.append(int(supplier_id))
        
    if material_id and material_id != "all":
        query += """ AND EXISTS (
            SELECT 1 FROM purchase_invoice_item pii
            WHERE pii.purchase_invoice_id = pi.id AND pii.material_id = ?
        )"""
        params.append(int(material_id))
        
    if state and state != "all":
        query += " AND p.state = ?"
        params.append(state)
        
    if gst_type and gst_type != "all":
        if gst_type == "INTRA":
            query += " AND (pi.cgst > 0 OR pi.sgst > 0 OR pi.igst = 0 OR pi.igst IS NULL OR pi.igst = 0.0)"
        elif gst_type == "INTER":
            query += " AND pi.igst > 0"
            
    if status and status != "all":
        query += " AND pi.status = ?"
        params.append(status)
        
    if payment_mode and payment_mode != "all":
        query += " AND pi.payment_mode = ?"
        params.append(payment_mode)

    if search_query:
        query += """ AND (
            pi.purchase_invoice_number LIKE ? OR
            p.company_name LIKE ? OR
            p.gstin LIKE ? OR
            pi.invoice_date LIKE ? OR
            pi.vehicle_number LIKE ? OR
            pi.transporter LIKE ? OR
            pi.supplier_invoice_number LIKE ? OR
            pi.remarks LIKE ? OR
            EXISTS (
                SELECT 1 FROM purchase_invoice_item pii
                JOIN material m ON pii.material_id = m.id
                WHERE pii.purchase_invoice_id = pi.id AND m.material_name LIKE ?
            )
        )"""
        like_str = f"%{search_query}%"
        params.extend([like_str] * 9)
        
    if sort_by == "date_desc":
        query += " ORDER BY pi.invoice_date DESC, pi.purchase_invoice_number DESC"
    elif sort_by == "date_asc":
        query += " ORDER BY pi.invoice_date ASC, pi.purchase_invoice_number ASC"
    elif sort_by == "purchase_number":
        query += " ORDER BY pi.purchase_invoice_number ASC"
    elif sort_by == "supplier":
        query += " ORDER BY p.company_name ASC"
    elif sort_by == "amount":
        query += " ORDER BY pi.grand_total DESC"
    else:
        query += " ORDER BY pi.invoice_date DESC, pi.purchase_invoice_number DESC"
        
    cursor.execute(query, params)
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
        SELECT pii.*, m.material_name, m.uom, m.gst_percentage, m.hsn_code, m.category
        FROM purchase_invoice_item pii
        LEFT JOIN material m ON pii.material_id = m.id
        WHERE pii.purchase_invoice_id = ?
        ORDER BY pii.id
    """, (invoice_id,))
    items = cursor.fetchall()
    conn.close()
    return items


# ── Create & Update (transactional) ───────────────────────────────────────────

def create_purchase_invoice(
    party_id, invoice_date, supplier_invoice_number, payment_mode,
    transporter, vehicle_number, remarks, items, company_state_code, party_state_code,
    eway_bill_number=None, reference_number=None, status="CONFIRMED", created_by=None,
    intake_type="Purchase", vehicle_type=None, driver_name=None,
    weight_slip_number=None, ready_for_processing=0
):
    totals = build_purchase_totals(items, company_state_code, party_state_code)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN")
        invoice_number = _generate_purchase_invoice_number(cursor)
        cursor.execute("""
            INSERT INTO purchase_invoice (
                purchase_invoice_number, invoice_date, supplier_id, supplier_invoice_number,
                payment_mode, vehicle_number, transporter, remarks, subtotal, cgst, sgst, igst,
                gst_amount, round_off, grand_total, status, eway_bill_number, reference_number,
                created_by, intake_type, vehicle_type, driver_name, weight_slip_number,
                ready_for_processing
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            status or "CONFIRMED",
            eway_bill_number or None,
            reference_number or None,
            created_by or None,
            intake_type or "Purchase",
            vehicle_type or None,
            driver_name or None,
            weight_slip_number or None,
            int(ready_for_processing or 0)
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
    except Exception as e:
        conn.execute("ROLLBACK")
        logger.error("Failed to create purchase invoice: %s", e, exc_info=True)
        raise RuntimeError(f"Purchase invoice creation failed: {e}") from e
    finally:
        conn.close()


def update_purchase_invoice(
    invoice_id, party_id, invoice_date, supplier_invoice_number, payment_mode,
    transporter, vehicle_number, remarks, items, company_state_code, party_state_code,
    eway_bill_number=None, reference_number=None, status="CONFIRMED", updated_by=None,
    intake_type="Purchase", vehicle_type=None, driver_name=None,
    weight_slip_number=None, ready_for_processing=0
):
    totals = build_purchase_totals(items, company_state_code, party_state_code)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN")
        cursor.execute("""
            UPDATE purchase_invoice SET
                supplier_id = ?, invoice_date = ?, supplier_invoice_number = ?, payment_mode = ?,
                vehicle_number = ?, transporter = ?, remarks = ?, subtotal = ?, cgst = ?, sgst = ?,
                igst = ?, gst_amount = ?, round_off = ?, grand_total = ?, status = ?,
                eway_bill_number = ?, reference_number = ?, updated_by = ?, intake_type = ?,
                vehicle_type = ?, driver_name = ?, weight_slip_number = ?,
                ready_for_processing = ?, updated_at = CURRENT_TIMESTAMP
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
            status or "CONFIRMED",
            eway_bill_number or None,
            reference_number or None,
            updated_by or None,
            intake_type or "Purchase",
            vehicle_type or None,
            driver_name or None,
            weight_slip_number or None,
            int(ready_for_processing or 0),
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
    except Exception as e:
        conn.execute("ROLLBACK")
        logger.error("Failed to update purchase invoice: %s", e, exc_info=True)
        raise RuntimeError(f"Purchase invoice update failed: {e}") from e
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


# ── Audit increment functions ────────────────────────────────────────────────

def increment_purchase_print_count(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE purchase_invoice SET print_count = print_count + 1 WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()


def increment_purchase_pdf_download_count(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE purchase_invoice SET pdf_download_count = pdf_download_count + 1 WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()


# ── Register and Analytics queries ────────────────────────────────────────────

def get_purchase_register_rows(
    start_date=None, end_date=None, financial_year=None,
    month=None, supplier_id=None, material_id=None
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            pi.invoice_date,
            pi.purchase_invoice_number AS purchase_number,
            p.company_name AS supplier_name,
            p.gstin AS supplier_gstin,
            p.state,
            m.material_name AS material,
            pii.amount AS taxable_value,
            m.gst_percentage,
            pi.payment_mode,
            pi.status,
            pi.round_off,
            pi.grand_total,
            p.state_code AS supplier_state_code
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        JOIN party p ON pi.supplier_id = p.id
        JOIN material m ON pii.material_id = m.id
        WHERE pi.is_active = 1 AND pi.status != 'DRAFT'
    """
    params = []
    
    if start_date:
        query += " AND pi.invoice_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND pi.invoice_date <= ?"
        params.append(end_date)
        
    if financial_year and financial_year != "all":
        parts = financial_year.split("-")
        if len(parts) == 2:
            start_yr = int(parts[0])
            end_yr = int(parts[1])
            query += " AND pi.invoice_date >= ? AND pi.invoice_date <= ?"
            params.append(f"{start_yr}-04-01")
            params.append(f"{end_yr}-03-31")
            
    if month and month != "all":
        query += " AND strftime('%m', pi.invoice_date) = ?"
        padded_month = f"{int(month):02d}"
        params.append(padded_month)
        
    if supplier_id and supplier_id != "all":
        query += " AND pi.supplier_id = ?"
        params.append(int(supplier_id))
        
    if material_id and material_id != "all":
        query += " AND pii.material_id = ?"
        params.append(int(material_id))
        
    query += " ORDER BY pi.invoice_date DESC, pi.purchase_invoice_number DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    cursor.execute("SELECT state_code FROM company LIMIT 1")
    company_row = cursor.fetchone()
    company_state_code = company_row[0] if company_row else "27"
    
    conn.close()
    
    results = []
    for r in rows:
        item = dict(r)
        taxable = float(item["taxable_value"] or 0.0)
        gst_pct = float(item["gst_percentage"] or 18.0)
        gst_amount = taxable * gst_pct / 100.0
        
        is_intra = str(item["supplier_state_code"]).strip() == company_state_code
        if is_intra:
            item["cgst"] = round(gst_amount / 2.0, 2)
            item["sgst"] = round(gst_amount / 2.0, 2)
            item["igst"] = 0.0
        else:
            item["cgst"] = 0.0
            item["sgst"] = 0.0
            item["igst"] = round(gst_amount, 2)
        item["gst_total"] = item["cgst"] + item["sgst"] + item["igst"]
        results.append(item)
        
    return results


def get_purchase_monthly_analytics():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-%m', pi.invoice_date) AS month, 
               SUM(pi.subtotal) AS taxable,
               SUM(pi.cgst + pi.sgst + pi.igst) AS gst,
               SUM(pi.grand_total) AS total
         FROM purchase_invoice pi
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY month
        ORDER BY month ASC
        LIMIT 12
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_suppliers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.company_name, SUM(pi.grand_total) AS total_val
        FROM purchase_invoice pi
        JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pi.supplier_id
        ORDER BY total_val DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_purchased_materials():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.material_name, SUM(pii.quantity) AS qty
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        JOIN material m ON pii.material_id = m.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pii.material_id
        ORDER BY qty DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_purchase_dashboard_stats():
    conn = get_connection()
    cursor = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    month_str = datetime.now().strftime("%Y-%m-%d")[:7] # YYYY-MM
    
    # Today's Purchases
    cursor.execute("""
        SELECT SUM(grand_total) FROM purchase_invoice 
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED') AND invoice_date = ?
    """, (today_str,))
    today_purchases = cursor.fetchone()[0] or 0.0
    
    # Monthly Purchases
    cursor.execute("""
        SELECT SUM(grand_total) FROM purchase_invoice 
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED') AND invoice_date LIKE ?
    """, (f"{month_str}-%",))
    monthly_purchases = cursor.fetchone()[0] or 0.0
    
    # Total Weight
    cursor.execute("""
        SELECT SUM(pii.weight) FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
    """)
    total_weight = cursor.fetchone()[0] or 0.0
    
    # Total Pieces
    cursor.execute("""
        SELECT SUM(pii.pieces) FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
    """)
    total_pieces = cursor.fetchone()[0] or 0
    
    # Invoice Count
    cursor.execute("""
        SELECT COUNT(id) FROM purchase_invoice 
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """)
    invoice_count = cursor.fetchone()[0] or 0
    
    # GST Paid
    cursor.execute("""
        SELECT SUM(cgst + sgst + igst) FROM purchase_invoice 
        WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """)
    gst_paid = cursor.fetchone()[0] or 0.0
    
    # Top Supplier
    cursor.execute("""
        SELECT p.company_name, SUM(pi.grand_total) AS total_val
        FROM purchase_invoice pi
        JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pi.supplier_id
        ORDER BY total_val DESC
        LIMIT 1
    """)
    top_sup_row = cursor.fetchone()
    top_supplier = top_sup_row[0] if top_sup_row else "—"
    
    # Most Purchased Material
    cursor.execute("""
        SELECT m.material_name, SUM(pii.quantity) AS qty
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        JOIN material m ON pii.material_id = m.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pii.material_id
        ORDER BY qty DESC
        LIMIT 1
    """)
    top_mat_row = cursor.fetchone()
    top_material = top_mat_row[0] if top_mat_row else "—"
    
    # Today's Weight Received
    cursor.execute("""
        SELECT SUM(pii.weight) FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED') AND pi.invoice_date = ?
    """, (today_str,))
    today_weight = cursor.fetchone()[0] or 0.0

    # Today's Pieces Received
    cursor.execute("""
        SELECT SUM(pii.pieces) FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED') AND pi.invoice_date = ?
    """, (today_str,))
    today_pieces = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "today_purchases": today_purchases,
        "monthly_purchases": monthly_purchases,
        "total_weight": total_weight,
        "total_pieces": total_pieces,
        "invoice_count": invoice_count,
        "gst_paid": gst_paid,
        "top_supplier": top_supplier,
        "top_material": top_material,
        "today_weight": today_weight,
        "today_pieces": today_pieces,
        "pending_processing": 0  # Placeholder for future Factory module integration
    }


def get_purchase_charts_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Material-wise Purchases
    cursor.execute("""
        SELECT m.material_name AS label, SUM(pii.quantity) AS value
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        JOIN material m ON pii.material_id = m.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pii.material_id
        ORDER BY value DESC
        LIMIT 5
    """)
    material_wise = [dict(r) for r in cursor.fetchall()]
    
    # Category-wise Purchases
    cursor.execute("""
        SELECT m.category AS label, SUM(pii.quantity) AS value
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        JOIN material m ON pii.material_id = m.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY m.category
        ORDER BY value DESC
    """)
    category_wise = [dict(r) for r in cursor.fetchall()]
    
    # Top Suppliers List
    cursor.execute("""
        SELECT p.company_name AS label, SUM(pi.grand_total) AS value
        FROM purchase_invoice pi
        JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pi.supplier_id
        ORDER BY value DESC
        LIMIT 5
    """)
    top_suppliers = [dict(r) for r in cursor.fetchall()]
    
    # Recent purchases
    cursor.execute("""
        SELECT pi.id, pi.purchase_invoice_number, pi.invoice_date, p.company_name, pi.grand_total, pi.status
        FROM purchase_invoice pi
        JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1
        ORDER BY pi.invoice_date DESC, pi.id DESC
        LIMIT 5
    """)
    recent_purchases = [dict(r) for r in cursor.fetchall()]
    
    # Recent suppliers added
    cursor.execute("""
        SELECT id, company_name, phone, state, created_at
        FROM party
        WHERE is_active = 1
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_suppliers = [dict(r) for r in cursor.fetchall()]
    
    # Recent materials added
    cursor.execute("""
        SELECT id, material_code, material_name, category, uom
        FROM material
        WHERE is_active = 1
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_materials = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        "material_wise": material_wise,
        "category_wise": category_wise,
        "top_suppliers": top_suppliers,
        "recent_purchases": recent_purchases,
        "recent_suppliers": recent_suppliers,
        "recent_materials": recent_materials
    }


def get_source_party_ledger_stats(party_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total purchases amount and invoice count
    cursor.execute("""
        SELECT SUM(grand_total), COUNT(id) FROM purchase_invoice
        WHERE supplier_id = ? AND is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """, (party_id,))
    amt_cnt = cursor.fetchone()
    total_purchases = amt_cnt[0] or 0.0
    total_invoices = amt_cnt[1] or 0
    
    # Total Weight and Pieces
    cursor.execute("""
        SELECT SUM(pii.weight), SUM(pii.pieces) FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        WHERE pi.supplier_id = ? AND pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
    """, (party_id,))
    wp = cursor.fetchone()
    total_weight = wp[0] or 0.0
    total_pieces = wp[1] or 0
    
    # Last purchase date
    cursor.execute("""
        SELECT MAX(invoice_date) FROM purchase_invoice
        WHERE supplier_id = ? AND is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """, (party_id,))
    last_purchase_date = cursor.fetchone()[0] or "—"
    
    # Frequent materials
    cursor.execute("""
        SELECT m.material_name, SUM(pii.quantity) as total_qty, m.uom
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        JOIN material m ON pii.material_id = m.id
        WHERE pi.supplier_id = ? AND pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
        GROUP BY pii.material_id
        ORDER BY total_qty DESC
        LIMIT 5
    """, (party_id,))
    frequent_materials = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_purchases": total_purchases,
        "total_invoices": total_invoices,
        "total_weight": total_weight,
        "total_pieces": total_pieces,
        "last_purchase_date": last_purchase_date,
        "frequent_materials": frequent_materials
    }
