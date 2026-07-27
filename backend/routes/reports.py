from flask import Blueprint, render_template
from database import get_connection

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/reports")
def reports():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Purchases totals
    cursor.execute("""
        SELECT COALESCE(SUM(grand_total), 0),
               (SELECT COALESCE(SUM(weight), 0) FROM purchase_invoice_item pii 
                JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id 
                WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED'))
        FROM purchase_invoice WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """)
    r_pur = cursor.fetchone()
    purchase_value = r_pur[0] if r_pur else 0
    purchase_weight = r_pur[1] if r_pur and r_pur[1] else 0
    
    # 2. Sales totals
    cursor.execute("""
        SELECT COALESCE(SUM(grand_total), 0),
               (SELECT COALESCE(SUM(weight), 0) FROM sales_invoice_item sii 
                JOIN sales_invoice si ON sii.sales_invoice_id = si.id 
                WHERE si.is_active = 1 AND si.status NOT IN ('DRAFT', 'CANCELLED'))
        FROM sales_invoice WHERE is_active = 1 AND status NOT IN ('DRAFT', 'CANCELLED')
    """)
    r_sal = cursor.fetchone()
    sales_value = r_sal[0] if r_sal else 0
    sales_weight = r_sal[1] if r_sal and r_sal[1] else 0
    
    # 3. Processing totals
    cursor.execute("""
        SELECT COUNT(*),
               COALESCE((SELECT SUM(weight) FROM processing_input WHERE processing_job_id IN 
                 (SELECT id FROM processing_job WHERE status = 'COMPLETED')), 0),
               COALESCE((SELECT SUM(weight) FROM processing_output WHERE processing_job_id IN 
                 (SELECT id FROM processing_job WHERE status = 'COMPLETED')), 0)
        FROM processing_job WHERE status = 'COMPLETED'
    """)
    r_proc = cursor.fetchone()
    processed_batches = r_proc[0] if r_proc else 0
    processed_input_weight = r_proc[1] if r_proc else 0
    processed_output_weight = r_proc[2] if r_proc else 0
    
    # 4. Certificates totals
    cursor.execute("""
        SELECT COUNT(DISTINCT c.id), COALESCE(SUM(po.weight), 0)
        FROM certificate c
        LEFT JOIN certificate_processing cp ON cp.certificate_id = c.id
        LEFT JOIN processing_output po ON po.processing_job_id = cp.processing_job_id
        WHERE c.status NOT IN ('CANCELLED')
    """)
    r_cert = cursor.fetchone()
    certificates_count = r_cert[0] if r_cert else 0
    certified_weight = r_cert[1] if r_cert else 0
    
    conn.close()
    
    stats = {
        "purchase_value": purchase_value,
        "purchase_weight": purchase_weight,
        "sales_value": sales_value,
        "sales_weight": sales_weight,
        "processed_batches": processed_batches,
        "processed_input_weight": processed_input_weight,
        "processed_output_weight": processed_output_weight,
        "certificates_count": certificates_count,
        "certified_weight": certified_weight
    }
    
    return render_template("reports/dashboard.html", stats=stats)
