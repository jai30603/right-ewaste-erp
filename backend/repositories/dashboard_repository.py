"""
Dashboard Repository
Provides aggregated business snapshot data for the main dashboard.
All queries are intentionally lightweight — single-pass aggregations only.
"""
from datetime import datetime
from database import get_connection


def get_dashboard_snapshot():
    """Return all KPI figures needed for the dashboard in a single DB connection."""
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
        SELECT COUNT(*) FROM (
            SELECT 
                m.id,
                (COALESCE(p.total_purchased, 0.0) - COALESCE(s.total_sold, 0.0)) AS current_stock
            FROM material m
            LEFT JOIN (
                SELECT pii.material_id, SUM(pii.quantity) AS total_purchased
                FROM purchase_invoice_item pii
                JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
                WHERE pi.is_active = 1 AND pi.status NOT IN ('DRAFT', 'CANCELLED')
                GROUP BY pii.material_id
            ) p ON m.id = p.material_id
            LEFT JOIN (
                SELECT sii.material_id, SUM(sii.quantity) AS total_sold
                FROM sales_invoice_item sii
                JOIN sales_invoice si ON sii.sales_invoice_id = si.id
                WHERE si.is_active = 1 AND si.status NOT IN ('DRAFT', 'CANCELLED')
                GROUP BY sii.material_id
            ) s ON m.id = s.material_id
            WHERE m.is_active = 1 AND (COALESCE(p.total_purchased, 0.0) - COALESCE(s.total_sold, 0.0)) > 0
        )
    """)
    inventory_items = cursor.fetchone()[0] or 0

    # ── Total Confirmed Purchase Invoices (all time) ─────────────────────
    cursor.execute("""
        SELECT COUNT(*)
        FROM purchase_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT','CANCELLED')
    """)
    total_purchase_invoices = cursor.fetchone()[0] or 0

    # ── Total Confirmed Sales Invoices (all time) ────────────────────────
    cursor.execute("""
        SELECT COUNT(*)
        FROM sales_invoice
        WHERE is_active = 1 AND status NOT IN ('DRAFT','CANCELLED')
    """)
    total_sales_invoices = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "today_purchase_count":   today_purchase_count,
        "today_purchase_value":   today_purchase_value,
        "today_sales_count":      today_sales_count,
        "today_sales_value":      today_sales_value,
        "monthly_purchase_value": monthly_purchase_value,
        "monthly_sales_value":    monthly_sales_value,
        "total_parties":          total_parties,
        "total_materials":        total_materials,
        "inventory_items":        inventory_items,
        "total_purchase_invoices": total_purchase_invoices,
        "total_sales_invoices":   total_sales_invoices,
        "pending_processing":     0,  # placeholder — Factory module
        "pending_certificates":   0,  # placeholder — Certificates module
    }
