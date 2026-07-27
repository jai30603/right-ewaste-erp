import logging
from database import get_connection

logger = logging.getLogger(__name__)


def generate_batch_number(conn=None):
    from repositories import settings_repository
    return settings_repository.increment_and_get_number("BATCH", conn)


def create_batch(batch_data, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        cursor = conn.cursor()
        batch_number = batch_data.get("batch_number") or generate_batch_number(conn)

        cursor.execute(
            """INSERT INTO material_batch (
                batch_number, purchase_invoice_id, purchase_invoice_number, supplier_id, supplier_name,
                purchase_date, material_id, material_name, quantity, weight, remaining_quantity,
                remaining_weight, warehouse_id, status, financial_valuation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                batch_number,
                batch_data.get("purchase_invoice_id"),
                batch_data.get("purchase_invoice_number", ""),
                batch_data.get("supplier_id"),
                batch_data.get("supplier_name", ""),
                batch_data.get("purchase_date"),
                batch_data["material_id"],
                batch_data["material_name"],
                float(batch_data.get("quantity", 0)),
                float(batch_data.get("weight", 0)),
                float(batch_data.get("remaining_quantity", batch_data.get("quantity", 0))),
                float(batch_data.get("remaining_weight", batch_data.get("weight", 0))),
                batch_data.get("warehouse_id", 1),
                batch_data.get("status", "IN_STORE"),
                float(batch_data.get("financial_valuation", 0.0))
            )
        )
        batch_id = cursor.lastrowid
        if close_conn:
            conn.commit()
        return batch_id, batch_number
    finally:
        if close_conn:
            conn.close()


def get_batch_by_id(batch_id, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM material_batch WHERE id = ?", (batch_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if close_conn:
            conn.close()


def get_batch_by_number(batch_number, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM material_batch WHERE batch_number = ?", (batch_number,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if close_conn:
            conn.close()


def get_all_batches(query="", status="all", material_id=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = "SELECT mb.*, m.material_code FROM material_batch mb JOIN material m ON mb.material_id = m.id WHERE 1=1"
        params = []

        if query:
            like = f"%{query}%"
            sql += " AND (mb.batch_number LIKE ? OR mb.material_name LIKE ? OR mb.supplier_name LIKE ? OR mb.purchase_invoice_number LIKE ?)"
            params.extend([like, like, like, like])

        if status != "all" and status:
            sql += " AND mb.status = ?"
            params.append(status)

        if material_id:
            sql += " AND mb.material_id = ?"
            params.append(material_id)

        sql += " ORDER BY mb.id DESC"
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_batch_remaining(batch_id, qty_deduct, weight_deduct, new_status=None, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT remaining_quantity, remaining_weight FROM material_batch WHERE id = ?", (batch_id,))
        row = cursor.fetchone()
        if row:
            rem_q = max(0.0, row[0] - qty_deduct)
            rem_w = max(0.0, row[1] - weight_deduct)

            if new_status is None:
                if rem_w <= 0.001 and rem_q <= 0.001:
                    new_status = "PROCESSED"
                else:
                    new_status = "IN_PROCESSING"

            cursor.execute(
                """UPDATE material_batch
                   SET remaining_quantity = ?, remaining_weight = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (rem_q, rem_w, new_status, batch_id)
            )

        if close_conn:
            conn.commit()
    finally:
        if close_conn:
            conn.close()
