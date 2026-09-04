import logging
from datetime import datetime
from database import get_connection

logger = logging.getLogger(__name__)


# ── Invoice number ────────────────────────────────────────────────────────────

def _generate_invoice_number(cursor):
    """
    Must be called inside an open transaction so the MAX read and the
    subsequent INSERT are atomic — prevents duplicate numbers under concurrent
    requests.
    """
    from repositories import settings_repository
    return settings_repository.increment_and_get_number("SALES", cursor.connection)


from services.invoice_service import calculate_gst as _calculate_gst

def calculate_gst(subtotal, items_gst, company_state_code, party_state_code):
    return _calculate_gst(subtotal, items_gst, company_state_code, party_state_code)


# ── Read queries ──────────────────────────────────────────────────────────────

def get_all_invoices(
    start_date=None, end_date=None, search_query=None,
    financial_year=None, month=None, customer_id=None,
    material_id=None, state=None, gst_type=None,
    status=None, payment_mode=None, sort_by=None,
    category=None, created_by=None,
    gstin=None, shipping_state_code=None, dispatch_location=None,
    hsn_sac=None, item_type=None, uom=None,
    gst_rate=None, tcs_applicable=None, transporter=None,
    vehicle_number=None, company_bank_account_number=None
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT
            si.*,
            p.company_name,
            p.gstin,
            p.state,
            (SELECT COUNT(*) FROM sales_invoice_item
             WHERE sales_invoice_id = si.id) AS item_count
        FROM sales_invoice si
        LEFT JOIN party p ON si.party_id = p.id
        WHERE si.is_active = 1
    """
    params = []
    
    if start_date:
        query += " AND si.invoice_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND si.invoice_date <= ?"
        params.append(end_date)
        
    if financial_year and financial_year != "all":
        parts = financial_year.split("-")
        if len(parts) == 2:
            start_yr = int(parts[0])
            end_yr = int(parts[1])
            query += " AND si.invoice_date >= ? AND si.invoice_date <= ?"
            params.append(f"{start_yr}-04-01")
            params.append(f"{end_yr}-03-31")
            
    if month and month != "all":
        query += " AND strftime('%m', si.invoice_date) = ?"
        padded_month = f"{int(month):02d}"
        params.append(padded_month)
        
    if customer_id and customer_id != "all":
        query += " AND si.party_id = ?"
        params.append(int(customer_id))
        
    if material_id and material_id != "all":
        query += """ AND EXISTS (
            SELECT 1 FROM sales_invoice_item sii
            WHERE sii.sales_invoice_id = si.id AND sii.material_id = ?
        )"""
        params.append(int(material_id))

    if category and category != "all":
        query += """ AND EXISTS (
            SELECT 1 FROM sales_invoice_item sii
            JOIN material m ON sii.material_id = m.id
            WHERE sii.sales_invoice_id = si.id AND m.category = ?
        )"""
        params.append(category)

    if created_by and created_by != "all":
        query += " AND si.created_by = ?"
        params.append(created_by)
        
    if state and state != "all":
        query += " AND p.state = ?"
        params.append(state)
        
    if gst_type and gst_type != "all":
        if gst_type == "INTRA":
            query += " AND (si.cgst > 0 OR si.sgst > 0 OR (si.igst = 0 OR si.igst IS NULL OR si.igst = 0.0))"
        elif gst_type == "INTER":
            query += " AND si.igst > 0"
            
    if status and status != "all":
        query += " AND si.status = ?"
        params.append(status)
        
    if payment_mode and payment_mode != "all":
        query += " AND si.payment_mode = ?"
        params.append(payment_mode)

    if gstin and gstin != "all":
        query += " AND (p.gstin = ? OR si.billing_gstin = ?)"
        params.extend([gstin, gstin])
        
    if shipping_state_code and shipping_state_code != "all":
        query += " AND si.shipping_state_code = ?"
        params.append(shipping_state_code)
        
    if dispatch_location and dispatch_location != "all":
        query += " AND si.dispatch_location = ?"
        params.append(dispatch_location)
        
    if hsn_sac and hsn_sac != "all":
        query += " AND EXISTS (SELECT 1 FROM sales_invoice_item sii WHERE sii.sales_invoice_id = si.id AND (sii.hsn_sac = ? OR sii.hsn_code = ?))"
        params.extend([hsn_sac, hsn_sac])
        
    if item_type and item_type != "all":
        query += " AND EXISTS (SELECT 1 FROM sales_invoice_item sii WHERE sii.sales_invoice_id = si.id AND sii.item_type = ?)"
        params.append(item_type)
        
    if uom and uom != "all":
        query += " AND EXISTS (SELECT 1 FROM sales_invoice_item sii WHERE sii.sales_invoice_id = si.id AND sii.uom = ?)"
        params.append(uom)
        
    if gst_rate and gst_rate != "all":
        query += " AND EXISTS (SELECT 1 FROM sales_invoice_item sii WHERE sii.sales_invoice_id = si.id AND sii.gst_percentage = ?)"
        params.append(float(gst_rate))
        
    if tcs_applicable is not None and tcs_applicable != "all":
        val = 1 if str(tcs_applicable).lower() in ('true', '1', 'yes') else 0
        query += " AND si.tcs_applicable = ?"
        params.append(val)
        
    if transporter and transporter != "all":
        query += " AND si.transporter LIKE ?"
        params.append(f"%{transporter}%")
        
    if vehicle_number and vehicle_number != "all":
        query += " AND si.vehicle_number LIKE ?"
        params.append(f"%{vehicle_number}%")
        
    if company_bank_account_number and company_bank_account_number != "all":
        query += " AND si.company_bank_account_number = ?"
        params.append(company_bank_account_number)

    if search_query:
        query += """ AND (
            si.invoice_number LIKE ? OR
            p.company_name LIKE ? OR
            p.gstin LIKE ? OR
            si.invoice_date LIKE ? OR
            si.vehicle_number LIKE ? OR
            si.transporter LIKE ? OR
            si.remarks LIKE ? OR
            si.reference_number LIKE ? OR
            si.status LIKE ? OR
            EXISTS (
                SELECT 1 FROM sales_invoice_item sii
                LEFT JOIN material m ON sii.material_id = m.id
                WHERE sii.sales_invoice_id = si.id AND (
                    m.material_name LIKE ? OR
                    sii.hsn_sac LIKE ? OR
                    m.hsn_code LIKE ?
                )
            )
        )"""
        like_str = f"%{search_query}%"
        params.extend([like_str] * 12)
        
    if sort_by == "date_desc":
        query += " ORDER BY si.invoice_date DESC, si.invoice_number DESC"
    elif sort_by == "date_asc":
        query += " ORDER BY si.invoice_date ASC, si.invoice_number ASC"
    elif sort_by == "inv_number":
        query += " ORDER BY si.invoice_number ASC"
    elif sort_by == "customer":
        query += " ORDER BY p.company_name ASC"
    elif sort_by == "grand_total":
        query += " ORDER BY si.grand_total DESC"
    elif sort_by == "created_at":
        query += " ORDER BY si.created_at DESC"
    else:
        query += " ORDER BY si.invoice_date DESC, si.invoice_number DESC"
        
    cursor.execute(query, params)
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
        SELECT sii.*, m.material_name, m.uom as master_uom, 
               COALESCE(sii.gst_percentage, m.gst_percentage, 18.0) as gst_percentage
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
    items,               # list of dicts: material_id, qty, weight, rate, amount, gst_percentage
    company_state_code,
    party_state_code,
    eway_bill_number=None,
    reference_number=None,
    status="CONFIRMED",
    created_by=None,
    billing_party_name=None,
    billing_address=None,
    billing_gstin=None,
    billing_state=None,
    billing_state_code=None,
    billing_contact=None,
    shipping_party_name=None,
    shipping_address=None,
    shipping_gstin=None,
    shipping_state=None,
    shipping_state_code=None,
    shipping_contact=None,
    dispatch_location=None,
    dispatch_address=None,
    dispatch_gstin=None,
    dispatch_state=None,
    dispatch_state_code=None,
    company_bank_name=None,
    company_bank_account_number=None,
    company_bank_ifsc=None,
    company_bank_branch=None,
    financial_year=None,
    tcs_applicable=False,
    tcs_rate=0.0
):
    """
    Saves the invoice header and all line-items inside a single explicit
    database transaction, recording snapshot parameters and calculated tax splits.
    """
    from services.calculation_service import calculate_invoice_result
    calc = calculate_invoice_result(
        items,
        company_state_code,
        billing_state_code=billing_state_code or party_state_code,
        shipping_state_code=shipping_state_code,
        tcs_applicable=tcs_applicable,
        tcs_rate=tcs_rate
    )

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        # ── BEGIN explicit transaction ────────────────────────────────────
        conn.execute("BEGIN")

        # ── Step 1: generate invoice number (inside transaction) ──────────
        invoice_number = _generate_invoice_number(cursor)
        logger.info("Creating invoice %s for party_id=%s", invoice_number, party_id)

        # ── Step 2: insert invoice header ─────────────────────────────────
        cursor.execute("""
            INSERT INTO sales_invoice (
                invoice_number, invoice_date, party_id,
                payment_mode, transporter, vehicle_number,
                subtotal, cgst, sgst, igst, round_off, grand_total,
                remarks, status, eway_bill_number, reference_number,
                created_by,
                billing_party_name, billing_address, billing_gstin,
                billing_state, billing_state_code, billing_contact,
                shipping_party_name, shipping_address, shipping_gstin,
                shipping_state, shipping_state_code, shipping_contact,
                dispatch_location, dispatch_address, dispatch_gstin,
                dispatch_state, dispatch_state_code,
                company_bank_name, company_bank_account_number,
                company_bank_ifsc, company_bank_branch,
                financial_year,
                tcs_rate, tcs_amount, tcs_base_amount,
                tcs_applicable,
                amount_in_words
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            invoice_number, invoice_date, party_id,
            payment_mode  or None,
            transporter   or None,
            vehicle_number or None,
            calc["taxable_total"],
            calc["cgst_total"], calc["sgst_total"], calc["igst_total"],
            calc["round_off"], calc["grand_total"],
            remarks or None,
            status or "CONFIRMED",
            eway_bill_number or None,
            reference_number or None,
            created_by or None,
            billing_party_name or None,
            billing_address or None,
            billing_gstin or None,
            billing_state or None,
            billing_state_code or None,
            billing_contact or None,
            shipping_party_name or None,
            shipping_address or None,
            shipping_gstin or None,
            shipping_state or None,
            shipping_state_code or None,
            shipping_contact or None,
            dispatch_location or None,
            dispatch_address or None,
            dispatch_gstin or None,
            dispatch_state or None,
            dispatch_state_code or None,
            company_bank_name or None,
            company_bank_account_number or None,
            company_bank_ifsc or None,
            company_bank_branch or None,
            financial_year or None,
            calc["tcs_rate"], calc["tcs_amount"], calc["tcs_base_amount"],
            1 if tcs_applicable else 0,
            calc["amount_in_words"]
        ))

        invoice_id = cursor.lastrowid
        logger.info("Invoice header saved — id=%s", invoice_id)

        # ── Step 3: insert every line-item ────────────────────────────────
        for idx, item in enumerate(items, start=0):
            line_calc = calc["lines"][idx] if idx < len(calc["lines"]) else {
                "taxable_amount": item["amount"], "gst_rate": item.get("gst_percentage", 18.0),
                "cgst": 0.0, "sgst": 0.0, "igst": 0.0
            }
            cursor.execute("""
                INSERT INTO sales_invoice_item
                    (sales_invoice_id, material_id,
                     quantity, weight, rate, amount,
                     item_type, description, hsn_sac, uom, item_reference,
                     gst_percentage, cgst, sgst, igst)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                invoice_id,
                item.get("material_id") or 999999,
                item["qty"],
                item.get("weight") or 0.0,
                item["rate"],
                line_calc["taxable_amount"],
                item.get("item_type", "Goods"),
                item.get("description"),
                item.get("hsn_sac"),
                item.get("uom", "KGS"),
                item.get("item_reference"),
                line_calc["gst_rate"],
                line_calc["cgst"],
                line_calc["sgst"],
                line_calc["igst"]
            ))
            logger.debug("  item %d saved (material_id=%s)", idx+1, item.get("material_id"))

        # ── Step 4: commit only when every insert succeeded ───────────────
        conn.execute("COMMIT")
        logger.info("Invoice %s committed successfully (%d items)", invoice_number, len(items))
        return invoice_id

    except Exception as exc:
        # ── Rollback — neither header nor items will persist ──────────────
        conn.execute("ROLLBACK")
        logger.error(
            "Invoice creation failed — rolled back. Error: %s", exc, exc_info=True
        )
        raise RuntimeError(f"Invoice save failed and was rolled back: {exc}") from exc
    finally:
        conn.close()


def update_sales_invoice(
    invoice_id, party_id, invoice_date, payment_mode,
    transporter, vehicle_number, remarks, items,
    company_state_code, party_state_code,
    eway_bill_number=None,
    reference_number=None,
    status="CONFIRMED",
    updated_by=None,
    billing_party_name=None,
    billing_address=None,
    billing_gstin=None,
    billing_state=None,
    billing_state_code=None,
    billing_contact=None,
    shipping_party_name=None,
    shipping_address=None,
    shipping_gstin=None,
    shipping_state=None,
    shipping_state_code=None,
    shipping_contact=None,
    dispatch_location=None,
    dispatch_address=None,
    dispatch_gstin=None,
    dispatch_state=None,
    dispatch_state_code=None,
    company_bank_name=None,
    company_bank_account_number=None,
    company_bank_ifsc=None,
    company_bank_branch=None,
    financial_year=None,
    tcs_applicable=False,
    tcs_rate=0.0
):
    from services.calculation_service import calculate_invoice_result
    calc = calculate_invoice_result(
        items,
        company_state_code,
        billing_state_code=billing_state_code or party_state_code,
        shipping_state_code=shipping_state_code,
        tcs_applicable=tcs_applicable,
        tcs_rate=tcs_rate
    )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN")
        cursor.execute("""
            UPDATE sales_invoice SET
                party_id = ?, invoice_date = ?, payment_mode = ?,
                transporter = ?, vehicle_number = ?, subtotal = ?,
                cgst = ?, sgst = ?, igst = ?, round_off = ?,
                grand_total = ?, remarks = ?, status = ?,
                eway_bill_number = ?, reference_number = ?,
                billing_party_name = ?, billing_address = ?, billing_gstin = ?,
                billing_state = ?, billing_state_code = ?, billing_contact = ?,
                shipping_party_name = ?, shipping_address = ?, shipping_gstin = ?,
                shipping_state = ?, shipping_state_code = ?, shipping_contact = ?,
                dispatch_location = ?, dispatch_address = ?, dispatch_gstin = ?,
                dispatch_state = ?, dispatch_state_code = ?,
                company_bank_name = ?, company_bank_account_number = ?,
                company_bank_ifsc = ?, company_bank_branch = ?,
                financial_year = ?,
                tcs_rate = ?, tcs_amount = ?, tcs_base_amount = ?,
                tcs_applicable = ?,
                amount_in_words = ?,
                updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            party_id,
            invoice_date,
            payment_mode or None,
            transporter or None,
            vehicle_number or None,
            calc["taxable_total"],
            calc["cgst_total"],
            calc["sgst_total"],
            calc["igst_total"],
            calc["round_off"],
            calc["grand_total"],
            remarks or None,
            status or "CONFIRMED",
            eway_bill_number or None,
            reference_number or None,
            billing_party_name or None,
            billing_address or None,
            billing_gstin or None,
            billing_state or None,
            billing_state_code or None,
            billing_contact or None,
            shipping_party_name or None,
            shipping_address or None,
            shipping_gstin or None,
            shipping_state or None,
            shipping_state_code or None,
            shipping_contact or None,
            dispatch_location or None,
            dispatch_address or None,
            dispatch_gstin or None,
            dispatch_state or None,
            dispatch_state_code or None,
            company_bank_name or None,
            company_bank_account_number or None,
            company_bank_ifsc or None,
            company_bank_branch or None,
            financial_year or None,
            calc["tcs_rate"], calc["tcs_amount"], calc["tcs_base_amount"],
            1 if tcs_applicable else 0,
            calc["amount_in_words"],
            updated_by or None,
            invoice_id,
        ))
        
        cursor.execute("DELETE FROM sales_invoice_item WHERE sales_invoice_id = ?", (invoice_id,))
        for idx, item in enumerate(items, start=0):
            line_calc = calc["lines"][idx] if idx < len(calc["lines"]) else {
                "taxable_amount": item["amount"], "gst_rate": item.get("gst_percentage", 18.0),
                "cgst": 0.0, "sgst": 0.0, "igst": 0.0
            }
            cursor.execute("""
                INSERT INTO sales_invoice_item (
                    sales_invoice_id, material_id, quantity, weight, rate, amount,
                    item_type, description, hsn_sac, uom, item_reference,
                    gst_percentage, cgst, sgst, igst
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                invoice_id,
                item.get("material_id") or 999999,
                item["qty"],
                item.get("weight") or 0.0,
                item["rate"],
                line_calc["taxable_amount"],
                item.get("item_type", "Goods"),
                item.get("description"),
                item.get("hsn_sac"),
                item.get("uom", "KGS"),
                item.get("item_reference"),
                line_calc["gst_rate"],
                line_calc["cgst"],
                line_calc["sgst"],
                line_calc["igst"]
            ))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def increment_print_count(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sales_invoice SET print_count = print_count + 1 WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()


def increment_pdf_download_count(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sales_invoice SET pdf_download_count = pdf_download_count + 1 WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()


def delete_sales_invoice(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sales_invoice
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (invoice_id,))
    conn.commit()
    conn.close()


def get_monthly_analytics():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-%m', si.invoice_date) AS month, 
               SUM(si.subtotal) AS taxable,
               SUM(si.cgst + si.sgst + si.igst) AS gst,
               SUM(si.grand_total) AS revenue
        FROM sales_invoice si
        WHERE si.is_active = 1
        GROUP BY month
        ORDER BY month ASC
        LIMIT 12
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_customers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.company_name, SUM(si.grand_total) AS total_val
        FROM sales_invoice si
        JOIN party p ON si.party_id = p.id
        WHERE si.is_active = 1
        GROUP BY si.party_id
        ORDER BY total_val DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_materials():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.material_name, SUM(sii.quantity) AS qty
        FROM sales_invoice_item sii
        JOIN sales_invoice si ON sii.sales_invoice_id = si.id
        JOIN material m ON sii.material_id = m.id
        WHERE si.is_active = 1
        GROUP BY sii.material_id
        ORDER BY qty DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sales_register_rows(
    start_date=None, end_date=None, financial_year=None,
    month=None, customer_id=None, material_id=None
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            si.invoice_date,
            si.invoice_number,
            p.company_name AS customer_name,
            p.gstin,
            p.state,
            m.material_name AS material,
            sii.amount AS taxable_value,
            m.gst_percentage,
            si.payment_mode,
            si.status,
            si.round_off,
            si.grand_total,
            p.state_code AS party_state_code
        FROM sales_invoice_item sii
        JOIN sales_invoice si ON sii.sales_invoice_id = si.id
        JOIN party p ON si.party_id = p.id
        JOIN material m ON sii.material_id = m.id
        WHERE si.is_active = 1 AND si.status != 'DRAFT'
    """
    params = []
    
    if start_date:
        query += " AND si.invoice_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND si.invoice_date <= ?"
        params.append(end_date)
        
    if financial_year and financial_year != "all":
        parts = financial_year.split("-")
        if len(parts) == 2:
            start_yr = int(parts[0])
            end_yr = int(parts[1])
            query += " AND si.invoice_date >= ? AND si.invoice_date <= ?"
            params.append(f"{start_yr}-04-01")
            params.append(f"{end_yr}-03-31")
            
    if month and month != "all":
        query += " AND strftime('%m', si.invoice_date) = ?"
        padded_month = f"{int(month):02d}"
        params.append(padded_month)
        
    if customer_id and customer_id != "all":
        query += " AND si.party_id = ?"
        params.append(int(customer_id))
        
    if material_id and material_id != "all":
        query += " AND sii.material_id = ?"
        params.append(int(material_id))
        
    query += " ORDER BY si.invoice_date DESC, si.invoice_number DESC"
    
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
        
        is_intra = str(item["party_state_code"]).strip() == company_state_code
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


