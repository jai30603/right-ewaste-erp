"""
Dashboard Repository
Provides aggregated business snapshot data for the main dashboard.
Focuses strictly on Core Production Scope: Sales, Purchase, Inventory, Masters.
All queries are lightweight and safe.
"""
from datetime import datetime
from database import get_connection


def get_dashboard_snapshot():
    """Return all KPI figures and recent records for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")

    # ── Today's Purchases ────────────────────────────────────────────────
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(grand_total), 0)
        FROM purchase_invoice
        WHERE is_active = 1
          AND status NOT IN ('DRAFT','CANCELLED')
          AND invoice_date = ?
    """, (today,))
    r = cursor.fetchone()
    today_purchase_count = r[0] or 0
    today_purchase_value = r[1] or 0.0

    # ── Today's Sales ────────────────────────────────────────────────────
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(grand_total), 0)
        FROM sales_invoice
        WHERE is_active = 1
          AND status NOT IN ('DRAFT','CANCELLED')
          AND invoice_date = ?
    """, (today,))
    r = cursor.fetchone()
    today_sales_count = r[0] or 0
    today_sales_value = r[1] or 0.0

    # ── Monthly Purchase ─────────────────────────────────────────────────
    cursor.execute("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM purchase_invoice
        WHERE is_active = 1
          AND status NOT IN ('DRAFT','CANCELLED')
          AND invoice_date LIKE ?
    """, (f"{month}-%",))
    monthly_purchase_value = cursor.fetchone()[0] or 0.0

    # ── Monthly Sales ────────────────────────────────────────────────────
    cursor.execute("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM sales_invoice
        WHERE is_active = 1
          AND status NOT IN ('DRAFT','CANCELLED')
          AND invoice_date LIKE ?
    """, (f"{month}-%",))
    monthly_sales_value = cursor.fetchone()[0] or 0.0

    # ── Party Count ──────────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM party WHERE is_active = 1")
    total_parties = cursor.fetchone()[0] or 0

    # ── Material Count ───────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM material WHERE is_active = 1")
    total_materials = cursor.fetchone()[0] or 0

    # ── Inventory Items (distinct active materials in stock with stock > 0) ──
    cursor.execute("""
        SELECT COUNT(DISTINCT material_id), COALESCE(SUM(current_quantity), 0)
        FROM inventory_balance
        WHERE current_quantity > 0
    """)
    inv_r = cursor.fetchone()
    inventory_items = inv_r[0] or 0
    total_stock_qty = inv_r[1] or 0.0

    # ── Total Confirmed Purchase Invoices (all time) ─────────────────────
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(grand_total), 0)
        FROM purchase_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT','CANCELLED')
    """)
    p_all = cursor.fetchone()
    total_purchase_invoices = p_all[0] or 0
    total_purchase_amount = p_all[1] or 0.0

    # ── Total Confirmed Sales Invoices (all time) ────────────────────────
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(grand_total), 0)
        FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT','CANCELLED')
    """)
    s_all = cursor.fetchone()
    total_sales_invoices = s_all[0] or 0
    total_sales_amount = s_all[1] or 0.0

    # ── Recent Sales Invoices (Latest 5) ─────────────────────────────────
    cursor.execute("""
        SELECT s.id, s.invoice_number, s.invoice_date, s.party_id, p.company_name as party_name,
               s.grand_total, s.status, s.created_at
        FROM sales_invoice s
        LEFT JOIN party p ON s.party_id = p.id
        WHERE s.is_active = 1
        ORDER BY s.id DESC
        LIMIT 5
    """)
    recent_sales = [dict(row) for row in cursor.fetchall()]

    # ── Recent Purchase Invoices (Latest 5) ──────────────────────────────
    cursor.execute("""
        SELECT pi.id, pi.purchase_invoice_number as invoice_number, pi.invoice_date, pi.supplier_id as party_id, p.company_name as party_name,
               pi.grand_total, pi.status, pi.created_at
        FROM purchase_invoice pi
        LEFT JOIN party p ON pi.supplier_id = p.id
        WHERE pi.is_active = 1
        ORDER BY pi.id DESC
        LIMIT 5
    """)
    recent_purchases = [dict(row) for row in cursor.fetchall()]

    # ── Top Inventory Items by Quantity ───────────────────────────────────
    cursor.execute("""
        SELECT m.id, m.material_code as code, m.material_name as name, m.category, m.uom, ib.current_quantity, ib.inventory_state
        FROM inventory_balance ib
        JOIN material m ON ib.material_id = m.id
        WHERE ib.current_quantity > 0
        ORDER BY ib.current_quantity DESC
        LIMIT 5
    """)
    top_stock = [dict(row) for row in cursor.fetchall()]


    conn.close()

    return {
        "today_purchase_count":    today_purchase_count,
        "today_purchase_value":    today_purchase_value,
        "today_sales_count":       today_sales_count,
        "today_sales_value":       today_sales_value,
        "monthly_purchase_value":  monthly_purchase_value,
        "monthly_sales_value":     monthly_sales_value,
        "total_parties":           total_parties,
        "total_materials":         total_materials,
        "inventory_items":         inventory_items,
        "total_stock_qty":         total_stock_qty,
        "total_purchase_invoices": total_purchase_invoices,
        "total_purchase_amount":   total_purchase_amount,
        "total_sales_invoices":    total_sales_invoices,
        "total_sales_amount":      total_sales_amount,
        "recent_sales":            recent_sales,
        "recent_purchases":        recent_purchases,
        "top_stock":               top_stock,
    }

