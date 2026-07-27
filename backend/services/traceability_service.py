import logging
from database import get_connection

logger = logging.getLogger(__name__)


def build_batch_genealogy(batch_number):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM material_batch WHERE batch_number = ?", (batch_number,))
        batch_row = cursor.fetchone()
        if not batch_row:
            return None

        batch = dict(batch_row)
        batch_id = batch["id"]

        # 1. Purchase Stage
        purchase = None
        if batch["purchase_invoice_id"]:
            cursor.execute(
                """SELECT pi.*, p.company_name as supplier_name, p.party_code
                   FROM purchase_invoice pi
                   JOIN party p ON pi.supplier_id = p.id
                   WHERE pi.id = ?""",
                (batch["purchase_invoice_id"],)
            )
            p_row = cursor.fetchone()
            if p_row:
                purchase = dict(p_row)

        # 2. Movement Ledger entries for this batch
        cursor.execute(
            """SELECT sm.*, m.material_name, m.material_code
               FROM stock_movement sm
               JOIN material m ON sm.material_id = m.id
               WHERE sm.batch_id = ? OR sm.batch_number = ?
               ORDER BY sm.id ASC""",
            (batch_id, batch_number)
        )
        movements = [dict(r) for r in cursor.fetchall()]

        # 3. Processing Jobs where this batch was consumed
        cursor.execute(
            """SELECT DISTINCT pj.*
               FROM processing_job pj
               JOIN processing_input pi ON pi.processing_job_id = pj.id
               WHERE pi.batch_id = ? OR pi.batch_number = ?""",
            (batch_id, batch_number)
        )
        processing_jobs = [dict(r) for r in cursor.fetchall()]

        # 4. Classified Outputs generated from processing this batch
        cursor.execute(
            """SELECT po.*, m.material_name, m.material_code
               FROM processing_output po
               JOIN material m ON po.material_id = m.id
               WHERE po.parent_batch_id = ? OR po.parent_batch_number = ?""",
            (batch_id, batch_number)
        )
        classified_outputs = [dict(r) for r in cursor.fetchall()]

        # 5. Disposal Queue items from this batch
        cursor.execute(
            """SELECT dq.*
               FROM disposal_queue dq
               WHERE dq.parent_batch_id = ? OR dq.parent_batch_number = ?""",
            (batch_id, batch_number)
        )
        disposal_items = [dict(r) for r in cursor.fetchall()]

        # 6. Sales Dispatches from this batch
        cursor.execute(
            """SELECT si.*, s.invoice_number, s.invoice_date, p.company_name as buyer_name, m.material_name
               FROM sales_invoice_item si
               JOIN sales_invoice s ON si.sales_invoice_id = s.id
               JOIN party p ON s.party_id = p.id
               JOIN material m ON si.material_id = m.id
               WHERE si.batch_id = ? OR si.batch_number = ?""",
            (batch_id, batch_number)
        )
        sales_dispatches = [dict(r) for r in cursor.fetchall()]

        return {
            "batch": batch,
            "purchase": purchase,
            "movements": movements,
            "processing_jobs": processing_jobs,
            "classified_outputs": classified_outputs,
            "disposal_items": disposal_items,
            "sales_dispatches": sales_dispatches
        }
    finally:
        conn.close()


def search_traceability(query_str):
    if not query_str:
        return {"type": "empty", "results": []}

    q = str(query_str).strip()
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Check if query matches batch number
        cursor.execute("SELECT batch_number FROM material_batch WHERE batch_number LIKE ? LIMIT 5", (f"%{q}%",))
        batches = [r[0] for r in cursor.fetchall()]

        # Check if query matches processing job number
        cursor.execute("SELECT processing_number, id FROM processing_job WHERE processing_number LIKE ? LIMIT 5", (f"%{q}%",))
        jobs = [dict(r) for r in cursor.fetchall()]

        # Check if query matches purchase invoice number
        cursor.execute("SELECT purchase_invoice_number, id FROM purchase_invoice WHERE purchase_invoice_number LIKE ? LIMIT 5", (f"%{q}%",))
        purchases = [dict(r) for r in cursor.fetchall()]

        # Check if query matches sales invoice number
        cursor.execute("SELECT invoice_number, id FROM sales_invoice WHERE invoice_number LIKE ? LIMIT 5", (f"%{q}%",))
        sales = [dict(r) for r in cursor.fetchall()]

        # Check if query matches material code/name
        cursor.execute("SELECT id, material_code, material_name FROM material WHERE material_code LIKE ? OR material_name LIKE ? LIMIT 5", (f"%{q}%", f"%{q}%"))
        materials = [dict(r) for r in cursor.fetchall()]

        return {
            "query": q,
            "batches": batches,
            "jobs": jobs,
            "purchases": purchases,
            "sales": sales,
            "materials": materials
        }
    finally:
        conn.close()
