from database import get_connection


def get_inventory(search_query=None, category=None, inventory_state=None, unit=None, stock_status=None):
    conn = get_connection()
    try:
        query = """
            SELECT m.id, m.material_code AS code, m.material_name AS name, m.category,
                   m.hsn_code, m.uom AS unit, m.tracking_type,
                   COALESCE(SUM(ib.current_quantity), 0) AS current_stock,
                   COALESCE(SUM(ib.current_weight), 0) AS current_weight,
                   COALESCE((SELECT AVG(pii.rate) FROM purchase_invoice_item pii WHERE pii.material_id = m.id), 0) AS rate,
                   0.0 AS purchased_qty, 0.0 AS sold_qty,
                   COALESCE(MAX(ib.last_updated), m.updated_at) AS last_updated,
                   GROUP_CONCAT(DISTINCT ib.inventory_state) AS inventory_states
            FROM material m
            LEFT JOIN inventory_balance ib ON ib.material_id = m.id
            WHERE m.is_active = 1
        """
        params = []
        if search_query:
            like = f"%{search_query}%"
            query += " AND (m.material_code LIKE ? OR m.material_name LIKE ? OR m.category LIKE ? OR m.hsn_code LIKE ?)"
            params.extend([like, like, like, like])
        if category and category != "all":
            query += " AND m.category = ?"
            params.append(category)
        if inventory_state and inventory_state != "all":
            query += " AND ib.inventory_state = ?"
            params.append(inventory_state)
        if unit and unit != "all":
            query += " AND m.uom = ?"
            params.append(unit)
        query += " GROUP BY m.id"
        if stock_status == "available":
            query += " HAVING current_stock > 0"
        elif stock_status == "out":
            query += " HAVING current_stock <= 0"
        elif stock_status == "low":
            query += " HAVING current_stock > 0 AND current_stock < 10"
        query += " ORDER BY m.material_name COLLATE NOCASE"
        results = [dict(row) for row in conn.execute(query, params).fetchall()]
        for item in results:
            item["current_stock"] = float(item["current_stock"] or 0)
            item["stock_status"] = "Out of Stock" if item["current_stock"] <= 0 else ("Low Stock" if item["current_stock"] < 10 else "Available")
        return results
    finally:
        conn.close()


def get_stock_summary(search_query=None, category=None, start_date=None, end_date=None):
    # Retains the existing route contract. Date-scoped stock is provided by the ledger,
    # while the summary intentionally reports the current, movement-backed balance.
    return get_inventory(search_query, category)


def get_stock(material_id, inventory_state="RAW", warehouse_id=1, conn=None):
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        row = conn.execute(
            """SELECT current_quantity, current_weight
               FROM inventory_balance
               WHERE material_id = ? AND warehouse_id = ? AND inventory_state = ?""",
            (material_id, warehouse_id, inventory_state),
        ).fetchone()
        return dict(row) if row else {"current_quantity": 0.0, "current_weight": 0.0}
    finally:
        if owns_connection:
            conn.close()


def apply_movement(movement, conn):
    """Persist a validated movement and update the balance cache in one transaction."""
    current = get_stock(movement["material_id"], movement["inventory_state"], movement["warehouse_id"], conn)
    quantity_after = current["current_quantity"] + movement["quantity_change"]
    weight_after = current["current_weight"] + movement["weight_change"]

    conn.execute(
        """INSERT INTO stock_movement (
               movement_key, material_id, warehouse_id, inventory_state, movement_type,
               reference_type, reference_id, reference_number,
               quantity_before, quantity_change, quantity_after,
               weight_before, weight_change, weight_after,
               batch_id, batch_number, from_location, to_location, financial_valuation,
               performed_by, remarks, processing_job_reference, certificate_reference, created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            movement["movement_key"], movement["material_id"], movement["warehouse_id"],
            movement["inventory_state"], movement["movement_type"], movement["reference_type"],
            movement.get("reference_id"), movement.get("reference_number"),
            current["current_quantity"], movement["quantity_change"], quantity_after,
            current["current_weight"], movement["weight_change"], weight_after,
            movement.get("batch_id"), movement.get("batch_number"),
            movement.get("from_location"), movement.get("to_location"),
            movement.get("financial_valuation", 0.0),
            movement["performed_by"], movement.get("remarks"), movement.get("processing_job_reference"),
            movement.get("certificate_reference"), movement.get("created_at"),
        ),
    )
    conn.execute(
        """INSERT INTO inventory_balance (
               material_id, warehouse_id, inventory_state, current_quantity, current_weight, last_updated
           ) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(material_id, warehouse_id, inventory_state) DO UPDATE SET
               current_quantity=excluded.current_quantity,
               current_weight=excluded.current_weight,
               last_updated=CURRENT_TIMESTAMP""",
        (movement["material_id"], movement["warehouse_id"], movement["inventory_state"], quantity_after, weight_after),
    )


def remove_source_movements(reference_type, reference_id, conn):
    rows = conn.execute(
        """SELECT material_id, warehouse_id, inventory_state, quantity_change, weight_change
           FROM stock_movement WHERE reference_type = ? AND reference_id = ?""",
        (reference_type, reference_id),
    ).fetchall()
    for row in rows:
        conn.execute(
            """UPDATE inventory_balance
               SET current_quantity = current_quantity - ?, current_weight = current_weight - ?,
                   last_updated = CURRENT_TIMESTAMP
               WHERE material_id = ? AND warehouse_id = ? AND inventory_state = ?""",
            (row[3], row[4], row[0], row[1], row[2]),
        )
    conn.execute("DELETE FROM stock_movement WHERE reference_type = ? AND reference_id = ?", (reference_type, reference_id))


def get_document_items(document_type, document_id, conn):
    if document_type == "PURCHASE":
        return conn.execute(
            """SELECT pi.id, pi.purchase_invoice_number AS document_number, pi.invoice_date,
                      pi.status, pi.is_active, pii.id AS item_id, pii.material_id, pii.quantity, pii.weight,
                      m.material_name, m.tracking_type
               FROM purchase_invoice pi 
               JOIN purchase_invoice_item pii ON pii.purchase_invoice_id = pi.id
               LEFT JOIN material m ON pii.material_id = m.id
               WHERE pi.id = ?""",
            (document_id,),
        ).fetchall()
    return conn.execute(
        """SELECT si.id, si.invoice_number AS document_number, si.invoice_date,
                  si.status, si.is_active, sii.id AS item_id, sii.material_id, sii.quantity, sii.weight,
                  sii.item_type, m.material_name, m.tracking_type
           FROM sales_invoice si 
           JOIN sales_invoice_item sii ON sii.sales_invoice_id = si.id
           LEFT JOIN material m ON sii.material_id = m.id
           WHERE si.id = ?""",
        (document_id,),
    ).fetchall()


def get_stock_movements(material_id=None, movement_type=None, limit=100):
    conn = get_connection()
    try:
        query = """
            SELECT sm.*, m.material_name, m.material_code, m.uom
            FROM stock_movement sm JOIN material m ON m.id = sm.material_id
            WHERE 1=1
        """
        params = []
        if material_id:
            query += " AND sm.material_id = ?"
            params.append(material_id)
        if movement_type and movement_type != "all":
            query += " AND sm.movement_type = ?"
            params.append(movement_type)
        query += " ORDER BY sm.created_at DESC, sm.id DESC LIMIT ?"
        params.append(limit)
        rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        for row in rows:
            row["date"] = row["created_at"]
            row["ref_number"] = row["reference_number"] or "-"
            row["type"] = "Purchase" if row["movement_type"] == "PURCHASE" else "Sale" if row["movement_type"] == "SALE" else row["movement_type"].title()
            row["qty"] = abs(float(row["quantity_change"] or 0))
            row["rate"] = 0.0
        return rows
    finally:
        conn.close()


def get_material_ledger(material_id, start_date=None, end_date=None):
    conn = get_connection()
    try:
        query = "SELECT * FROM stock_movement WHERE material_id = ?"
        params = [material_id]
        if start_date:
            query += " AND date(created_at) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date(created_at) <= ?"
            params.append(end_date)
        query += " ORDER BY created_at ASC, id ASC"
        
        type_map = {
            'PURCHASE': 'Purchase',
            'SALE': 'Sale',
            'MANUAL_ADJUSTMENT': 'Adjustment',
            'WEIGHT_ADJUSTMENT': 'Wt Adjust',
            'PROCESSING': 'Processing',
            'REFURBISHMENT': 'Refurbishment',
            'DISMANTLING': 'Dismantling',
            'SORTING': 'Sorting',
            'INTERNAL_CONSUMPTION': 'Internal Use',
            'RETURN': 'Return',
            'TRANSFER': 'Transfer'
        }
        rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        for r in rows:
            r['type'] = type_map.get(r['movement_type'], r['movement_type'])
            r['qty'] = abs(r['quantity_change'])
            r['date'] = r['created_at'][:10] if r['created_at'] else ''
            r['ref_number'] = r['reference_number']
            r['rate'] = 0.0
            if r['movement_type'] == 'PURCHASE' and r['reference_id']:
                rate_row = conn.execute(
                    "SELECT rate FROM purchase_invoice_item WHERE purchase_invoice_id = ? AND material_id = ? LIMIT 1",
                    (r['reference_id'], material_id)
                ).fetchone()
                if rate_row:
                    r['rate'] = rate_row[0]
            elif r['movement_type'] == 'SALE' and r['reference_id']:
                rate_row = conn.execute(
                    "SELECT rate FROM sales_invoice_item WHERE sales_invoice_id = ? AND material_id = ? LIMIT 1",
                    (r['reference_id'], material_id)
                ).fetchone()
                if rate_row:
                    r['rate'] = rate_row[0]
        return rows
    finally:
        conn.close()


def get_dashboard_summary():
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT COUNT(DISTINCT CASE WHEN current_quantity > 0 THEN material_id END) AS total_items,
                      COUNT(DISTINCT CASE WHEN inventory_state = 'RAW' AND current_quantity > 0 THEN material_id END) AS raw_items,
                      COUNT(DISTINCT CASE WHEN inventory_state IN ('FINISHED', 'RECOVERED') AND current_quantity > 0 THEN material_id END) AS finished_items,
                      COALESCE(SUM(current_weight), 0) AS total_weight,
                      COUNT(DISTINCT CASE WHEN current_quantity > 0 AND current_quantity < 10 THEN material_id END) AS low_stock
               FROM inventory_balance"""
        ).fetchone()
        categories = conn.execute(
            """SELECT COALESCE(m.category, 'Uncategorized') AS label, SUM(ib.current_quantity) AS value
               FROM inventory_balance ib JOIN material m ON m.id = ib.material_id
               WHERE ib.current_quantity > 0 GROUP BY m.category ORDER BY value DESC"""
        ).fetchall()
        states = conn.execute(
            "SELECT inventory_state AS label, SUM(current_quantity) AS value FROM inventory_balance WHERE current_quantity > 0 GROUP BY inventory_state"
        ).fetchall()
        return {"snapshot": dict(row), "categories": [dict(x) for x in categories], "states": [dict(x) for x in states]}
    finally:
        conn.close()


def get_all_categories():
    conn = get_connection()
    try:
        return [row[0] for row in conn.execute("SELECT DISTINCT category FROM material WHERE category IS NOT NULL AND category != '' AND is_active = 1 ORDER BY category")]
    finally:
        conn.close()
