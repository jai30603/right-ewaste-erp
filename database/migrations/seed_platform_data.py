"""Seed: Dashboard widgets and KPI definitions for Module 3 – Platform Services."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

WIDGETS = [
    ('total_purchase_today', 'Today Purchase', 'METRIC', 'purchase',
     '/platform/api/kpi/total_purchase_today', 'bi bi-cart', '#10b981', 1),
    ('total_sales_today', 'Today Sales', 'METRIC', 'sales',
     '/platform/api/kpi/total_sales_today', 'bi bi-receipt', '#6366f1', 2),
    ('inventory_value', 'Inventory Value', 'METRIC', 'inventory',
     '/platform/api/kpi/inventory_value', 'bi bi-boxes', '#f59e0b', 3),
    ('pending_certificates', 'Pending Certificates', 'METRIC', 'certificate',
     '/platform/api/kpi/pending_certificates', 'bi bi-patch-check', '#ef4444', 4),
    ('activity_feed', 'Recent Activity', 'FEED', 'platform',
     '/platform/api/widgets/activity_feed', 'bi bi-activity', '#8b5cf6', 5),
    ('processing_jobs', 'Processing Jobs', 'METRIC', 'processing',
     '/platform/api/kpi/processing_jobs', 'bi bi-cpu', '#06b6d4', 6),
]

KPIS = [
    ('total_purchase_today', 'Total Purchase Today', 'OPERATIONAL', 'INR', 'SQL',
     'SELECT COALESCE(SUM(total_amount),0) FROM purchase_invoice WHERE DATE(created_at)=DATE("now") AND status!="CANCELLED"',
     None, None, None),
    ('total_sales_today', 'Total Sales Today', 'OPERATIONAL', 'INR', 'SQL',
     'SELECT COALESCE(SUM(total_amount),0) FROM sales_invoice WHERE DATE(created_at)=DATE("now") AND status!="CANCELLED"',
     None, None, None),
    ('inventory_value', 'Inventory Value', 'FINANCIAL', 'INR', 'SQL',
     'SELECT COALESCE(SUM(i.current_weight * COALESCE(m.rate_per_kg,0)),0) FROM inventory_stock i JOIN material_master m ON i.material_id=m.id WHERE i.current_weight>0',
     None, None, None),
    ('pending_certificates', 'Pending Certificates', 'OPERATIONAL', 'count', 'SQL',
     'SELECT COUNT(*) FROM certificate WHERE status="PENDING"',
     None, None, None),
    ('processing_jobs', 'Active Processing Jobs', 'OPERATIONAL', 'count', 'SQL',
     'SELECT COUNT(*) FROM processing_job WHERE status IN ("PENDING","IN_PROGRESS")',
     None, None, None),
]


def seed(conn):
    c = conn.cursor()
    for w in WIDGETS:
        c.execute(
            'INSERT OR IGNORE INTO dashboard_widgets '
            '(widget_key,widget_name,widget_type,source_module,data_endpoint,icon,color,sort_order) '
            'VALUES (?,?,?,?,?,?,?,?)',
            w
        )
    for k in KPIS:
        c.execute(
            'INSERT OR IGNORE INTO kpi_definitions '
            '(kpi_key,kpi_name,kpi_category,unit,formula_type,formula,target_value,warning_threshold,critical_threshold) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            k
        )
    conn.commit()
    print("Seeding complete.")


if __name__ == "__main__":
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'erp.db')
    conn = sqlite3.connect(DB_PATH)
    seed(conn)
    conn.close()
