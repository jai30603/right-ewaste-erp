from database import get_connection


def get_stock_summary(search_query=None, category=None, start_date=None, end_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    p_where = ["pi.is_active = 1", "pi.status NOT IN ('DRAFT', 'CANCELLED')"]
    p_params = []
    if start_date:
        p_where.append("pi.invoice_date >= ?")
        p_params.append(start_date)
    if end_date:
        p_where.append("pi.invoice_date <= ?")
        p_params.append(end_date)
    p_clause = " AND ".join(p_where)
    
    s_where = ["si.is_active = 1", "si.status NOT IN ('DRAFT', 'CANCELLED')"]
    s_params = []
    if start_date:
        s_where.append("si.invoice_date >= ?")
        s_params.append(start_date)
    if end_date:
        s_where.append("si.invoice_date <= ?")
        s_params.append(end_date)
    s_clause = " AND ".join(s_where)
    
    query = f"""
        SELECT 
            m.id,
            m.material_code AS code,
            m.material_name AS name,
            m.category,
            m.uom AS unit,
            COALESCE((SELECT AVG(rate) FROM purchase_invoice_item WHERE material_id = m.id), 0.0) AS rate,
            COALESCE(p.total_purchased, 0.0) AS purchased_qty,
            COALESCE(s.total_sold, 0.0) AS sold_qty,
            (COALESCE(p.total_purchased, 0.0) - COALESCE(s.total_sold, 0.0)) AS current_stock
        FROM material m
        LEFT JOIN (
            SELECT pii.material_id, SUM(pii.quantity) AS total_purchased
            FROM purchase_invoice_item pii
            JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
            WHERE {p_clause}
            GROUP BY pii.material_id
        ) p ON m.id = p.material_id
        LEFT JOIN (
            SELECT sii.material_id, SUM(sii.quantity) AS total_sold
            FROM sales_invoice_item sii
            JOIN sales_invoice si ON sii.sales_invoice_id = si.id
            WHERE {s_clause}
            GROUP BY sii.material_id
        ) s ON m.id = s.material_id
        WHERE m.is_active = 1
    """
    
    params = p_params + s_params
    
    if search_query:
        query += " AND (m.material_code LIKE ? OR m.material_name LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
    if category and category != "all":
        query += " AND m.category = ?"
        params.append(category)
        
    query += " ORDER BY m.material_code ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_material_ledger(material_id, start_date=None, end_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    p_query = """
        SELECT 
            pi.invoice_date AS date,
            pi.purchase_invoice_number AS ref_number,
            'Purchase' AS type,
            pii.quantity AS qty,
            pii.rate AS rate
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
        WHERE pii.material_id = ? AND pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
    """
    p_params = [material_id]
    
    if start_date:
        p_query += " AND pi.invoice_date >= ?"
        p_params.append(start_date)
    if end_date:
        p_query += " AND pi.invoice_date <= ?"
        p_params.append(end_date)
        
    s_query = """
        SELECT 
            si.invoice_date AS date,
            si.invoice_number AS ref_number,
            'Sale' AS type,
            sii.quantity AS qty,
            sii.rate AS rate
        FROM sales_invoice_item sii
        JOIN sales_invoice si ON sii.sales_invoice_id = si.id
        WHERE sii.material_id = ? AND si.is_active = 1 AND si.status NOT IN ('DRAFT', 'CANCELLED')
    """
    s_params = [material_id]
    
    if start_date:
        s_query += " AND si.invoice_date >= ?"
        s_params.append(start_date)
    if end_date:
        s_query += " AND si.invoice_date <= ?"
        s_params.append(end_date)
        
    union_query = f"""
        SELECT * FROM (
            {p_query}
            UNION ALL
            {s_query}
        ) ORDER BY date ASC, ref_number ASC
    """
    
    params = p_params + s_params
    cursor.execute(union_query, params)
    rows = cursor.fetchall()
    
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_all_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM material WHERE category IS NOT NULL AND category != '' AND is_active = 1")
    cats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return cats

