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
        SELECT COUNT(DISTINCT material_id) FROM inventory_balance WHERE current_quantity > 0
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

    # ── Pending Processing Jobs ──────────────────────────────────────────
    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_job
        WHERE status IN ('DRAFT', 'IN_PROGRESS')
    """)
    pending_processing = cursor.fetchone()[0] or 0

    # ── Pending Certificates ─────────────────────────────────────────────
    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_job pj
        WHERE pj.status = 'COMPLETED'
          AND pj.id NOT IN (
              SELECT cp.processing_job_id
              FROM certificate_processing cp
              JOIN certificate c ON cp.certificate_id = c.id
              WHERE c.status NOT IN ('CANCELLED')
          )
    """)
    pending_certificates = cursor.fetchone()[0] or 0

    # ── Employee Management Metrics ─────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
    total_employees = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM employee_attendance WHERE attendance_date = ? AND attendance_status = 'Present'", (today,))
    present_today = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(DISTINCT lr.employee_id) 
        FROM employee_leave_requests lr
        JOIN employees e ON lr.employee_id = e.id
        WHERE lr.status = 'Approved' AND ? BETWEEN lr.start_date AND lr.end_date AND e.status = 'Active'
    """, (today,))
    employees_on_leave = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM employee_leave_requests WHERE status = 'Pending'")
    pending_leave_requests = cursor.fetchone()[0] or 0

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
        "pending_processing":     pending_processing,
        "pending_certificates":   pending_certificates,
        "total_employees":        total_employees,
        "present_today":          present_today,
        "employees_on_leave":     employees_on_leave,
        "pending_leave_requests": pending_leave_requests,
    }
