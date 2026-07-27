from datetime import datetime, date
from database import get_connection

def create_processing_job(job_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO processing_job (
                processing_number, processing_date, status, priority, operator_id, remarks, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                job_data["processing_number"],
                job_data["processing_date"],
                job_data.get("status", "DRAFT"),
                job_data.get("priority", "NORMAL"),
                job_data["operator_id"],
                job_data.get("remarks"),
            )
        )
        job_id = cursor.lastrowid
        return job_id
    finally:
        if close_conn:
            conn.close()

def update_processing_job(job_id, job_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE processing_job
               SET processing_date = ?, status = ?, priority = ?, operator_id = ?, remarks = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                job_data["processing_date"],
                job_data["status"],
                job_data["priority"],
                job_data["operator_id"],
                job_data.get("remarks"),
                job_id,
            )
        )
    finally:
        if close_conn:
            conn.close()

def delete_draft_job(job_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        conn.execute("DELETE FROM processing_job WHERE id = ? AND status IN ('DRAFT', 'READY')", (job_id,))
    finally:
        if close_conn:
            conn.close()

def save_inputs(job_id, inputs, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processing_input WHERE processing_job_id = ?", (job_id,))
        for item in inputs:
            cursor.execute(
                """INSERT INTO processing_input (
                    processing_job_id, material_id, quantity, weight, unit, processing_type, inventory_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    item["material_id"],
                    item.get("quantity", 0),
                    item.get("weight", 0),
                    item["unit"],
                    item["processing_type"],
                    item.get("inventory_reference"),
                )
            )
    finally:
        if close_conn:
            conn.close()

def save_outputs(job_id, outputs, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processing_output WHERE processing_job_id = ?", (job_id,))
        for item in outputs:
            cursor.execute(
                """INSERT INTO processing_output (
                    processing_job_id, material_id, quantity, weight, unit, inventory_state, output_category, recovered_from_material_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    item["material_id"],
                    item.get("quantity", 0),
                    item.get("weight", 0),
                    item.get("unit", "KGS"),
                    item.get("inventory_state", "RAW"),
                    item.get("output_category", "RECOVERABLE"),
                    item.get("recovered_from_material_id"),
                )
            )
    finally:
        if close_conn:
            conn.close()

def save_processing_loss(job_id, losses, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processing_loss WHERE processing_job_id = ?", (job_id,))
        for item in losses:
            cursor.execute(
                """INSERT INTO processing_loss (
                    processing_job_id, loss_weight, loss_reason, remarks
                ) VALUES (?, ?, ?, ?)""",
                (
                    job_id,
                    item.get("loss_weight", 0),
                    item["loss_reason"],
                    item.get("remarks"),
                )
            )
    finally:
        if close_conn:
            conn.close()

def log_job_activity(job_id, status, performed_by, remarks=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO processing_job_activity (
                processing_job_id, status, performed_by, remarks, created_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (job_id, status, performed_by, remarks)
        )
    finally:
        if close_conn:
            conn.close()

def get_processing_job(job_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processing_job WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        job = dict(row)
        
        # Get Inputs
        cursor.execute(
            """SELECT pi.*, m.material_code, m.material_name
               FROM processing_input pi
               JOIN material m ON pi.material_id = m.id
               WHERE pi.processing_job_id = ?""",
            (job_id,)
        )
        job["inputs"] = [dict(r) for r in cursor.fetchall()]
        
        # Get Outputs
        cursor.execute(
            """SELECT po.*, m.material_code, m.material_name, src.material_name AS recovered_from_name
               FROM processing_output po
               JOIN material m ON po.material_id = m.id
               LEFT JOIN material src ON po.recovered_from_material_id = src.id
               WHERE po.processing_job_id = ?""",
            (job_id,)
        )
        job["outputs"] = [dict(r) for r in cursor.fetchall()]
        
        # Get Losses
        cursor.execute("SELECT * FROM processing_loss WHERE processing_job_id = ?", (job_id,))
        job["losses"] = [dict(r) for r in cursor.fetchall()]
        
        # Get Activities
        cursor.execute("SELECT * FROM processing_job_activity WHERE processing_job_id = ? ORDER BY created_at ASC, id ASC", (job_id,))
        job["activities"] = [dict(r) for r in cursor.fetchall()]
        
        return job
    finally:
        conn.close()

def get_processing_job_by_number(processing_number):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM processing_job WHERE processing_number = ?", (processing_number,))
        row = cursor.fetchone()
        if row:
            return get_processing_job(row[0])
        return None
    finally:
        conn.close()

def search_processing_jobs(search_query=None, filters=None):
    conn = get_connection()
    try:
        query = """
            SELECT DISTINCT pj.*,
                   (SELECT COUNT(*) FROM processing_input WHERE processing_job_id = pj.id) AS input_count,
                   (SELECT COUNT(*) FROM processing_output WHERE processing_job_id = pj.id) AS output_count,
                   (SELECT COALESCE(SUM(weight), 0) FROM processing_input WHERE processing_job_id = pj.id) AS input_weight,
                   (SELECT COALESCE(SUM(weight), 0) FROM processing_output WHERE processing_job_id = pj.id) AS output_weight,
                   (SELECT COALESCE(SUM(loss_weight), 0) FROM processing_loss WHERE processing_job_id = pj.id) AS loss_weight
            FROM processing_job pj
            LEFT JOIN processing_input pi ON pi.processing_job_id = pj.id
            LEFT JOIN material m ON pi.material_id = m.id
            WHERE 1=1
        """
        params = []
        if search_query:
            like = f"%{search_query}%"
            query += " AND (pj.processing_number LIKE ? OR pj.operator_id LIKE ? OR pj.remarks LIKE ? OR m.material_code LIKE ? OR m.material_name LIKE ?)"
            params.extend([like, like, like, like, like])
            
        if filters:
            if filters.get("status"):
                if filters["status"] == "active":
                    query += " AND pj.status IN ('DRAFT', 'READY', 'IN_PROGRESS')"
                elif filters["status"] != "all":
                    query += " AND pj.status = ?"
                    params.append(filters["status"])
            if filters.get("priority") and filters["priority"] != "all":
                query += " AND pj.priority = ?"
                params.append(filters["priority"])
            if filters.get("operator") and filters["operator"] != "all":
                query += " AND pj.operator_id = ?"
                params.append(filters["operator"])
            if filters.get("start_date"):
                query += " AND pj.processing_date >= ?"
                params.append(filters["start_date"])
            if filters.get("end_date"):
                query += " AND pj.processing_date <= ?"
                params.append(filters["end_date"])
                
        # Order by status logic (e.g. READY/IN_PROGRESS first) or standard updated_at/id
        query += " ORDER BY pj.processing_date DESC, pj.id DESC"
        
        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_processing_queue():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Query materials with state RAW and positive stock
        cursor.execute(
            """SELECT m.id, m.material_code AS code, m.material_name AS name, m.category, m.uom AS unit,
                      ib.current_quantity AS qty, ib.current_weight AS weight,
                      COALESCE((SELECT MIN(pi.invoice_date)
                                FROM purchase_invoice_item pii
                                JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
                                WHERE pii.material_id = m.id AND pi.is_active = 1), '') AS oldest_purchase
               FROM inventory_balance ib
               JOIN material m ON ib.material_id = m.id
               WHERE ib.inventory_state = 'RAW' AND ib.current_quantity > 0 AND m.is_active = 1
               ORDER BY oldest_purchase ASC, m.material_name COLLATE NOCASE"""
        )
        rows = [dict(r) for r in cursor.fetchall()]
        
        # Calculate waiting days and priority based on waiting days
        today = date.today()
        for r in rows:
            oldest = r["oldest_purchase"]
            if oldest:
                try:
                    p_date = datetime.strptime(oldest[:10], "%Y-%m-%d").date()
                    days = (today - p_date).days
                    r["waiting_days"] = max(0, days)
                except Exception:
                    r["waiting_days"] = 0
            else:
                r["waiting_days"] = 0
                
            # Assign priority suggestions based on waiting days
            if r["waiting_days"] >= 30:
                r["priority"] = "URGENT"
            elif r["waiting_days"] >= 14:
                r["priority"] = "HIGH"
            elif r["waiting_days"] >= 7:
                r["priority"] = "NORMAL"
            else:
                r["priority"] = "LOW"
                
        # Sort queue by priority: URGENT -> HIGH -> NORMAL -> LOW, then waiting_days DESC
        priority_order = {"URGENT": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
        rows.sort(key=lambda x: (priority_order.get(x["priority"], 3), -x["waiting_days"]))
        return rows
    finally:
        conn.close()

def get_dashboard_summary():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        today_str = date.today().strftime("%Y-%m-%d")
        
        # 1. KPI Cards
        cursor.execute("SELECT COUNT(*) FROM processing_job WHERE processing_date = ?", (today_str,))
        created_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM processing_job WHERE status = 'IN_PROGRESS'")
        in_progress = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM processing_job WHERE status = 'READY'")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM processing_job WHERE status = 'COMPLETED'")
        completed = cursor.fetchone()[0]
        
        # Recovery weight & loss weight of completed jobs
        cursor.execute(
            """SELECT COALESCE(SUM(po.weight), 0)
               FROM processing_output po
               JOIN processing_job pj ON po.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'"""
        )
        recovery_weight = cursor.fetchone()[0]
        
        cursor.execute(
            """SELECT COALESCE(SUM(pl.loss_weight), 0)
               FROM processing_loss pl
               JOIN processing_job pj ON pl.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'"""
        )
        loss_weight = cursor.fetchone()[0]
        
        cursor.execute(
            """SELECT COALESCE(SUM(pi.weight), 0)
               FROM processing_input pi
               JOIN processing_job pj ON pi.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'"""
        )
        input_weight = cursor.fetchone()[0]
        
        # Output Category Stream Weight Breakdown
        cursor.execute(
            """SELECT COALESCE(SUM(po.weight), 0)
               FROM processing_output po
               JOIN processing_job pj ON po.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED' AND po.output_category = 'RECOVERABLE'"""
        )
        recoverable_weight = cursor.fetchone()[0]

        cursor.execute(
            """SELECT COALESCE(SUM(po.weight), 0)
               FROM processing_output po
               JOIN processing_job pj ON po.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED' AND po.output_category = 'REFURBISHABLE'"""
        )
        refurbishable_weight = cursor.fetchone()[0]

        cursor.execute(
            """SELECT COALESCE(SUM(po.weight), 0)
               FROM processing_output po
               JOIN processing_job pj ON po.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED' AND po.output_category = 'DISPOSAL'"""
        )
        disposal_weight = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM disposal_queue WHERE status = 'Pending'")
        pending_disposal_count = cursor.fetchone()[0]

        recovery_pct = 0.0
        disposal_pct = 0.0
        processing_yield = 0.0
        loss_pct = 0.0
        if input_weight > 0:
            recovery_pct = ((recoverable_weight + refurbishable_weight) / input_weight) * 100
            disposal_pct = (disposal_weight / input_weight) * 100
            processing_yield = recovery_pct
            loss_pct = max(0.0, 100.0 - recovery_pct - disposal_pct)
            
        # Top Operator
        cursor.execute(
            """SELECT operator_id, COUNT(*) as cnt
               FROM processing_job
               GROUP BY operator_id
               ORDER BY cnt DESC
               LIMIT 1"""
        )
        top_op_row = cursor.fetchone()
        top_operator = top_op_row[0] if top_op_row else "—"
        
        # Most Processed Material
        cursor.execute(
            """SELECT m.material_name, SUM(pi.weight) as total_wt
               FROM processing_input pi
               JOIN material m ON pi.material_id = m.id
               JOIN processing_job pj ON pi.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'
               GROUP BY pi.material_id
               ORDER BY total_wt DESC
               LIMIT 1"""
        )
        top_mat_row = cursor.fetchone()
        most_processed_material = top_mat_row[0] if top_mat_row else "—"
        
        # Recent Jobs
        cursor.execute(
            """SELECT pj.*,
                      (SELECT COUNT(*) FROM processing_input WHERE processing_job_id = pj.id) as input_count,
                      (SELECT COALESCE(SUM(weight), 0) FROM processing_input WHERE processing_job_id = pj.id) as input_weight
               FROM processing_job pj
               ORDER BY pj.id DESC
               LIMIT 5"""
        )
        recent_jobs = [dict(r) for r in cursor.fetchall()]
        
        # 2. Charts Data
        # Processing Type Distribution (Refurbishment, Dismantling, etc.)
        cursor.execute(
            """SELECT pi.processing_type, SUM(pi.weight) as wt
               FROM processing_input pi
               JOIN processing_job pj ON pi.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'
               GROUP BY pi.processing_type"""
        )
        type_distribution = {row[0]: float(row[1] or 0) for row in cursor.fetchall()}
        
        # Output Streams breakdown for chart
        output_stream_distribution = {
            "Recoverable": float(recoverable_weight),
            "Refurbishable": float(refurbishable_weight),
            "Disposal": float(disposal_weight)
        }

        # Daily processing count & weight trend over last 15 days
        cursor.execute(
            """SELECT pj.processing_date, COUNT(*), SUM(pi.weight)
               FROM processing_job pj
               JOIN processing_input pi ON pi.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'
               GROUP BY pj.processing_date
               ORDER BY pj.processing_date ASC
               LIMIT 15"""
        )
        trend_rows = cursor.fetchall()
        trend_dates = [r[0] for r in trend_rows]
        trend_counts = [r[1] for r in trend_rows]
        trend_weights = [float(r[2] or 0) for r in trend_rows]
        
        # Recovery breakdown by category
        cursor.execute(
            """SELECT m.category, SUM(po.weight)
               FROM processing_output po
               JOIN material m ON po.material_id = m.id
               JOIN processing_job pj ON po.processing_job_id = pj.id
               WHERE pj.status = 'COMPLETED'
               GROUP BY m.category"""
        )
        category_distribution = {row[0] or "Uncategorized": float(row[1] or 0) for row in cursor.fetchall()}
        
        return {
            "created_today": created_today,
            "in_progress": in_progress,
            "pending": pending,
            "completed": completed,
            "recovery_weight": recovery_weight,
            "recoverable_weight": recoverable_weight,
            "refurbishable_weight": refurbishable_weight,
            "disposal_weight": disposal_weight,
            "pending_disposal_count": pending_disposal_count,
            "loss_weight": loss_weight,
            "recovery_pct": recovery_pct,
            "disposal_pct": disposal_pct,
            "processing_yield": processing_yield,
            "loss_pct": loss_pct,
            "top_operator": top_operator,
            "most_processed_material": most_processed_material,
            "recent_jobs": recent_jobs,
            "charts": {
                "type_distribution": type_distribution,
                "output_stream_distribution": output_stream_distribution,
                "trend_dates": trend_dates,
                "trend_counts": trend_counts,
                "trend_weights": trend_weights,
                "category_distribution": category_distribution,
            }
        }
    finally:
        conn.close()

def get_operators():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT operator_id FROM processing_job ORDER BY operator_id")
        return [row[0] for row in cursor.fetchall() if row[0]]
    finally:
        conn.close()
