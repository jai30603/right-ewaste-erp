import sqlite3
from datetime import datetime, date
from database import get_connection

def create_certificate(cert_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO certificate (
                certificate_number, certificate_type, customer_id, status, template_key, template_version,
                generation_date, version_number, superseded_certificate_id, replaces_certificate_id,
                verification_uuid, digital_signature_hash, signed_by, signed_at, verification_hash, remarks,
                purchase_id, template_json, custom_table_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                cert_data["certificate_number"],
                cert_data["certificate_type"],
                cert_data["customer_id"],
                cert_data.get("status", "DRAFT"),
                cert_data["template_key"],
                cert_data.get("template_version", 1),
                cert_data.get("generation_date"),
                cert_data.get("version_number", 1),
                cert_data.get("superseded_certificate_id"),
                cert_data.get("replaces_certificate_id"),
                cert_data["verification_uuid"],
                cert_data.get("digital_signature_hash"),
                cert_data.get("signed_by"),
                cert_data.get("signed_at"),
                cert_data.get("verification_hash"),
                cert_data.get("remarks"),
                cert_data.get("purchase_id"),
                cert_data.get("template_json"),
                cert_data.get("custom_table_json")
            )
        )
        cert_id = cursor.lastrowid
        return cert_id
    finally:
        if close_conn:
            conn.close()

def update_certificate(cert_id, cert_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE certificate
               SET certificate_type = ?, status = ?, template_key = ?, template_version = ?,
                   generation_date = ?, version_number = ?, superseded_certificate_id = ?, replaces_certificate_id = ?,
                   digital_signature_hash = ?, signed_by = ?, signed_at = ?, verification_hash = ?, remarks = ?,
                   cancellation_reason = ?, cancelled_by = ?, cancelled_at = ?, purchase_id = ?,
                   template_json = ?, custom_table_json = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                cert_data["certificate_type"],
                cert_data["status"],
                cert_data["template_key"],
                cert_data.get("template_version", 1),
                cert_data.get("generation_date"),
                cert_data.get("version_number", 1),
                cert_data.get("superseded_certificate_id"),
                cert_data.get("replaces_certificate_id"),
                cert_data.get("digital_signature_hash"),
                cert_data.get("signed_by"),
                cert_data.get("signed_at"),
                cert_data.get("verification_hash"),
                cert_data.get("remarks"),
                cert_data.get("cancellation_reason"),
                cert_data.get("cancelled_by"),
                cert_data.get("cancelled_at"),
                cert_data.get("purchase_id"),
                cert_data.get("template_json"),
                cert_data.get("custom_table_json"),
                cert_id
            )
        )
    finally:
        if close_conn:
            conn.close()

def get_certificate(cert_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT c.*, p.company_name AS customer_name, p.billing_address AS customer_address, p.gstin AS customer_gstin,
                      p.pan AS customer_pan, replaces.certificate_number AS replaced_certificate_number,
                      superseded.certificate_number AS superseded_by_number,
                      pi.purchase_invoice_number, pi.invoice_date AS purchase_invoice_date
               FROM certificate c
               JOIN party p ON c.customer_id = p.id
               LEFT JOIN certificate replaces ON c.replaces_certificate_id = replaces.id
               LEFT JOIN certificate superseded ON c.superseded_certificate_id = superseded.id
               LEFT JOIN purchase_invoice pi ON c.purchase_id = pi.id
               WHERE c.id = ?""",
            (cert_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        cert = dict(row)
        
        # Get Template details from document_template (versioned table)
        cursor.execute(
            "SELECT * FROM document_template WHERE template_key = ? AND version = ?",
            (cert["template_key"], cert["template_version"])
        )
        t_row = cursor.fetchone()
        if not t_row:
            # Fallback to latest
            cursor.execute(
                "SELECT * FROM document_template WHERE template_key = ? ORDER BY version DESC LIMIT 1",
                (cert["template_key"],)
            )
            t_row = cursor.fetchone()
        cert["template"] = dict(t_row) if t_row else None
        
        # Populate materials table
        cert["materials"] = []
        import json
        if cert.get("custom_table_json"):
            try:
                cert["materials"] = json.loads(cert["custom_table_json"])
            except Exception:
                cert["materials"] = []
        elif cert.get("purchase_id"):
            cursor.execute(
                """SELECT m.material_name, m.material_code, m.uom AS unit,
                           pii.quantity, pii.weight, 'RAW' AS inventory_state
                    FROM purchase_invoice_item pii
                    JOIN material m ON pii.material_id = m.id
                    WHERE pii.purchase_invoice_id = ?
                    ORDER BY pii.id""",
                (cert["purchase_id"],)
            )
            cert["materials"] = [dict(r) for r in cursor.fetchall()]
            
        # Get Linked Processing Jobs
        cursor.execute(
            """SELECT cp.*, pj.processing_number, pj.processing_date, pj.operator_id, pj.remarks, pj.priority,
                      (SELECT COALESCE(SUM(weight), 0) FROM processing_input WHERE processing_job_id = pj.id) AS total_input_weight,
                      (SELECT COALESCE(SUM(weight), 0) FROM processing_output WHERE processing_job_id = pj.id) AS total_output_weight
               FROM certificate_processing cp
               JOIN processing_job pj ON cp.processing_job_id = pj.id
               WHERE cp.certificate_id = ?""",
            (cert_id,)
        )
        cert["processing_jobs"] = [dict(r) for r in cursor.fetchall()]
        
        # Get Linked Purchase Invoices (legacy relationship support)
        cursor.execute(
            """SELECT cpur.*, pi.purchase_invoice_number, pi.invoice_date,
                      (SELECT COALESCE(SUM(weight), 0) FROM purchase_invoice_item WHERE purchase_invoice_id = pi.id) AS total_weight
               FROM certificate_purchase cpur
               JOIN purchase_invoice pi ON cpur.purchase_id = pi.id
               WHERE cpur.certificate_id = ?""",
            (cert_id,)
        )
        cert["purchases"] = [dict(r) for r in cursor.fetchall()]
        
        # If materials is empty (e.g. legacy certificates linked via processing), fallback to processing yield
        if not cert["materials"] and cert["processing_jobs"]:
            job_ids = [job["processing_job_id"] for job in cert["processing_jobs"]]
            placeholders = ",".join("?" for _ in job_ids)
            cursor.execute(
                f"""SELECT m.material_name, m.material_code, m.uom AS unit,
                           SUM(po.quantity) AS quantity, SUM(po.weight) AS weight, po.inventory_state
                    FROM processing_output po
                    JOIN material m ON po.material_id = m.id
                    WHERE po.processing_job_id IN ({placeholders})
                    GROUP BY po.material_id, po.inventory_state""",
                job_ids
            )
            cert["materials"] = [dict(r) for r in cursor.fetchall()]
            
        # Get PDF Archive
        cursor.execute("SELECT * FROM certificate_pdf WHERE certificate_id = ? ORDER BY version DESC", (cert_id,))
        cert["pdfs"] = [dict(r) for r in cursor.fetchall()]
        
        # Get Activities
        cursor.execute("SELECT * FROM certificate_activity WHERE certificate_id = ? ORDER BY timestamp ASC, id ASC", (cert_id,))
        cert["activities"] = [dict(r) for r in cursor.fetchall()]
        
        # Get Asset Attachments
        cursor.execute("SELECT * FROM certificate_asset_attachment WHERE certificate_id = ?", (cert_id,))
        cert["attachments"] = [dict(r) for r in cursor.fetchall()]
        
        return cert
    finally:
        if close_conn:
            conn.close()

def get_certificate_by_number(certificate_number):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM certificate WHERE certificate_number = ?", (certificate_number,))
        row = cursor.fetchone()
        if row:
            return get_certificate(row[0])
        return None
    finally:
        conn.close()

def search_certificates(search_query=None, filters=None):
    conn = get_connection()
    try:
        query = """
            SELECT DISTINCT c.*, p.company_name AS customer_name,
                   (SELECT COUNT(*) FROM certificate_processing WHERE certificate_id = c.id) AS job_count,
                   (SELECT COALESCE(SUM(po.weight), 0)
                    FROM certificate_processing cp
                    JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
                    WHERE cp.certificate_id = c.id) AS certified_weight
            FROM certificate c
            JOIN party p ON c.customer_id = p.id
            LEFT JOIN certificate_processing cp ON cp.certificate_id = c.id
            LEFT JOIN processing_job pj ON cp.processing_job_id = pj.id
            WHERE 1=1
        """
        params = []
        if search_query:
            like = f"%{search_query}%"
            query += " AND (c.certificate_number LIKE ? OR p.company_name LIKE ? OR pj.processing_number LIKE ?)"
            params.extend([like, like, like])
            
        if filters:
            if filters.get("status") and filters["status"] != "all":
                query += " AND c.status = ?"
                params.append(filters["status"])
            if filters.get("type") and filters["type"] != "all":
                query += " AND c.certificate_type = ?"
                params.append(filters["type"])
            if filters.get("customer") and filters["customer"] != "all":
                query += " AND c.customer_id = ?"
                params.append(filters["customer"])
            if filters.get("start_date"):
                query += " AND c.generation_date >= ?"
                params.append(filters["start_date"])
            if filters.get("end_date"):
                query += " AND c.generation_date <= ?"
                params.append(filters["end_date"])
                
        query += " ORDER BY c.id DESC"
        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_certificate_templates():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t1.* FROM document_template t1
            INNER JOIN (
                SELECT template_key, MAX(version) AS max_ver
                FROM document_template
                GROUP BY template_key
            ) t2 ON t1.template_key = t2.template_key AND t1.version = t2.max_ver
            ORDER BY t1.template_name
        """)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def get_template_by_key(template_key):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM document_template WHERE template_key = ? ORDER BY version DESC LIMIT 1", (template_key,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def save_template(t_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        
        # 1. Fetch current max version
        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) FROM document_template WHERE template_key = ?",
            (t_data["template_key"],)
        )
        current_max = cursor.fetchone()[0]
        next_ver = current_max + 1
        
        # 2. Insert new version
        cursor.execute(
            """INSERT INTO document_template (
                template_key, template_name, title, declaration_text, show_logo, show_customer_details,
                show_purchase_references, show_processing_summary, show_weight_summary,
                show_asset_list, show_sustainability, sustainability_statement, signature_title, logo_path,
                header_text, footer_text, page_layout, margin_top, margin_bottom, margin_left, margin_right,
                show_gst, show_cin, show_pan, show_pcb, show_iso, show_r2, show_estewards, status, version, created_by, template_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t_data["template_key"], t_data["template_name"], t_data["title"], t_data["declaration_text"],
                t_data.get("show_logo", 1), t_data.get("show_customer_details", 1),
                t_data.get("show_purchase_references", 1), t_data.get("show_processing_summary", 1),
                t_data.get("show_weight_summary", 1),
                t_data.get("show_asset_list", 1), t_data.get("show_sustainability", 0),
                t_data.get("sustainability_statement"), t_data.get("signature_title", "Authorized Signatory"),
                t_data.get("logo_path"), t_data.get("header_text"), t_data.get("footer_text"),
                t_data.get("page_layout", "A4_PORTRAIT"), t_data.get("margin_top", 36.0),
                t_data.get("margin_bottom", 36.0), t_data.get("margin_left", 36.0), t_data.get("margin_right", 36.0),
                t_data.get("show_gst", 1), t_data.get("show_cin", 1), t_data.get("show_pan", 1),
                t_data.get("show_pcb", 1), t_data.get("show_iso", 0), t_data.get("show_r2", 0),
                t_data.get("show_estewards", 0), t_data.get("status", "ACTIVE"), next_ver, t_data.get("created_by", "System"),
                t_data.get("template_json")
            )
        )
        if close_conn:
            conn.commit()
        return next_ver
    finally:
        if close_conn:
            conn.close()

def link_processing_job(cert_id, job_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        conn.execute(
            "INSERT INTO certificate_processing (certificate_id, processing_job_id) VALUES (?, ?)",
            (cert_id, job_id)
        )
    finally:
        if close_conn:
            conn.close()

def link_purchase(cert_id, purchase_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        conn.execute(
            "INSERT INTO certificate_purchase (certificate_id, purchase_id) VALUES (?, ?)",
            (cert_id, purchase_id)
        )
    finally:
        if close_conn:
            conn.close()

def save_pdf_version(pdf_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO certificate_pdf (certificate_id, pdf_path, version, generated_by, checksum, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                pdf_data["certificate_id"],
                pdf_data["pdf_path"],
                pdf_data["version"],
                pdf_data["generated_by"],
                pdf_data["checksum"],
                pdf_data.get("status", "ACTIVE")
            )
        )
    finally:
        if close_conn:
            conn.close()

def save_certificate_activity(cert_id, action, performed_by, remarks=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        conn.execute(
            """INSERT INTO certificate_activity (certificate_id, action, performed_by, remarks, timestamp)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (cert_id, action, performed_by, remarks)
        )
    finally:
        if close_conn:
            conn.close()

def save_asset_attachment(a_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        conn.execute(
            """INSERT INTO certificate_asset_attachment (certificate_id, file_name, file_path, file_type, uploaded_by)
               VALUES (?, ?, ?, ?, ?)""",
            (
                a_data["certificate_id"],
                a_data["file_name"],
                a_data["file_path"],
                a_data["file_type"],
                a_data["uploaded_by"]
            )
        )
    finally:
        if close_conn:
            conn.close()

def remove_asset_attachment(attachment_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        conn.execute("DELETE FROM certificate_asset_attachment WHERE id = ?", (attachment_id,))
    finally:
        if close_conn:
            conn.close()

def get_eligible_processing_jobs():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Query confirmed purchases that have NO ACTIVE CERTIFICATES
        cursor.execute(
            """SELECT pi.id, pi.purchase_invoice_number AS processing_number, pi.invoice_date AS processing_date,
                      pi.remarks, pi.supplier_id AS customer_id, p.company_name AS customer_name,
                      p.billing_address, p.gstin,
                      (SELECT COALESCE(SUM(weight), 0) FROM purchase_invoice_item WHERE purchase_invoice_id = pi.id) AS input_weight
               FROM purchase_invoice pi
               JOIN party p ON pi.supplier_id = p.id
               WHERE pi.status = 'CONFIRMED' AND pi.is_active = 1
               ORDER BY pi.id DESC"""
        )
        purchases = [dict(r) for r in cursor.fetchall()]
        
        # Calculate readiness for each purchase invoice
        for p in purchases:
            c_id = p["customer_id"]
            billing_address = p["billing_address"]
            gstin = p["gstin"]
            
            # Check if certified already
            cursor.execute(
                """SELECT c.certificate_number, c.status
                   FROM certificate c
                   WHERE c.purchase_id = ? AND c.status NOT IN ('CANCELLED')
                   LIMIT 1""",
                (p["id"],)
            )
            cert_row = cursor.fetchone()
            
            if cert_row:
                p["readiness"] = "Already Certified"
                p["readiness_color"] = "danger"
                p["certificate_number"] = cert_row[0]
            elif not billing_address or not gstin:
                p["readiness"] = "Missing Customer Information"
                p["readiness_color"] = "warning"
            else:
                p["readiness"] = "Ready for Certificate"
                p["readiness_color"] = "success"
                
        return purchases
    finally:
        conn.close()

def get_customer_certificates(customer_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT c.*,
                      (SELECT COALESCE(SUM(po.weight), 0)
                       FROM certificate_processing cp
                       JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
                       WHERE cp.certificate_id = c.id) AS certified_weight
               FROM certificate c
               WHERE c.customer_id = ?
               ORDER BY c.id DESC""",
            (customer_id,)
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def get_dashboard_summary():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today_str = date.today().strftime("%Y-%m-%d")
        
        cursor.execute("SELECT COUNT(*) FROM certificate WHERE generation_date = ?", (today_str,))
        generated_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM certificate WHERE status = 'DRAFT'")
        draft_certs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM certificate WHERE status = 'CANCELLED'")
        cancelled_certs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM certificate WHERE status IN ('GENERATED', 'LOCKED')")
        locked_certs = cursor.fetchone()[0]
        
        # Calculate totals
        cursor.execute(
            """SELECT COALESCE(SUM(po.weight), 0), COALESCE(SUM(po.quantity), 0)
               FROM certificate_processing cp
               JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
               JOIN certificate c ON cp.certificate_id = c.id
               WHERE c.status IN ('GENERATED', 'LOCKED')"""
        )
        row = cursor.fetchone()
        certified_weight = row[0] if row else 0.0
        certified_quantity = row[1] if row else 0
        
        # Serviced customers count
        cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM certificate WHERE status NOT IN ('CANCELLED')")
        customers_count = cursor.fetchone()[0]
        
        # Recent certificates
        cursor.execute(
            """SELECT c.*, p.company_name AS customer_name,
                      (SELECT COALESCE(SUM(po.weight), 0)
                       FROM certificate_processing cp
                       JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
                       WHERE cp.certificate_id = c.id) AS weight
               FROM certificate c
               JOIN party p ON c.customer_id = p.id
               ORDER BY c.id DESC
               LIMIT 5"""
        )
        recent_certs = [dict(r) for r in cursor.fetchall()]
        
        # Type Distribution
        cursor.execute(
            "SELECT certificate_type, COUNT(*) FROM certificate WHERE status NOT IN ('CANCELLED') GROUP BY certificate_type"
        )
        type_dist = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            "generated_today": generated_today,
            "draft_certs": draft_certs,
            "cancelled_certs": cancelled_certs,
            "locked_certs": locked_certs,
            "certified_weight": certified_weight,
            "certified_quantity": certified_quantity,
            "customers_count": customers_count,
            "recent_certs": recent_certs,
            "type_distribution": type_dist
        }
    finally:
        conn.close()

def get_analytics_summary():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Monthly certified metrics trend
        cursor.execute(
            """SELECT STRFTIME('%Y-%m', c.generation_date) AS ym, COUNT(*), SUM(po.weight)
               FROM certificate c
               JOIN certificate_processing cp ON cp.certificate_id = c.id
               JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
               WHERE c.status IN ('GENERATED', 'LOCKED') AND c.generation_date IS NOT NULL
               GROUP BY ym
               ORDER BY ym ASC
               LIMIT 12"""
        )
        trend_rows = cursor.fetchall()
        months = [r[0] for r in trend_rows]
        counts = [r[1] for r in trend_rows]
        weights = [float(r[2] or 0) for r in trend_rows]
        
        # Customer distribution
        cursor.execute(
            """SELECT p.company_name, COUNT(*) AS cnt, SUM(po.weight) AS wt
               FROM certificate c
               JOIN party p ON c.customer_id = p.id
               JOIN certificate_processing cp ON cp.certificate_id = c.id
               JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
               WHERE c.status IN ('GENERATED', 'LOCKED')
               GROUP BY c.customer_id
               ORDER BY wt DESC
               LIMIT 5"""
        )
        cust_rows = cursor.fetchall()
        top_customers = [{"name": r[0], "count": r[1], "weight": float(r[2] or 0)} for r in cust_rows]
        
        # Material breakdown
        cursor.execute(
            """SELECT m.material_name, SUM(po.weight) AS wt
               FROM certificate_processing cp
               JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
               JOIN material m ON po.material_id = m.id
               JOIN certificate c ON cp.certificate_id = c.id
               WHERE c.status IN ('GENERATED', 'LOCKED')
               GROUP BY po.material_id
               ORDER BY wt DESC
               LIMIT 5"""
        )
        mat_rows = cursor.fetchall()
        top_materials = [{"name": r[0], "weight": float(r[1] or 0)} for r in mat_rows]
        
        # Template usage count
        cursor.execute(
            "SELECT template_key, COUNT(*) FROM certificate WHERE status NOT IN ('CANCELLED') GROUP BY template_key"
        )
        template_usage = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Average generation time: placeholder or query
        avg_generation_time = "—" # Usually instant (1-2s PDF generation)
        
        return {
            "months": months,
            "counts": counts,
            "weights": weights,
            "top_customers": top_customers,
            "top_materials": top_materials,
            "template_usage": template_usage,
            "avg_generation_time": avg_generation_time
        }
    finally:
        conn.close()
