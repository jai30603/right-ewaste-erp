import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "database" / "erp.db"

print("Database Path:", str(DATABASE.resolve()))


def initialize_database():
    conn = sqlite3.connect(DATABASE)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        


        # 1. Run all schema SQL scripts dynamically from database/schema
        schema_dir = BASE_DIR / "database" / "schema"
        if schema_dir.is_dir():
            sql_files = sorted(schema_dir.glob("*.sql"))
            for sql_file in sql_files:
                with open(sql_file, "r", encoding="utf-8") as f:
                    sql_script = f.read()
                cursor.executescript(sql_script)
        
        # Create company_bank table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                ifsc_code TEXT NOT NULL,
                branch_name TEXT,
                account_type TEXT DEFAULT 'Current',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Seed default company bank if empty
        cursor.execute("SELECT COUNT(*) FROM company_bank")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO company_bank (bank_name, account_number, ifsc_code, branch_name, account_type)
                VALUES ('HDFC Bank Ltd', '50200087654321', 'HDFC0001203', 'Sector 63, Noida', 'Current Account')
            """)
            cursor.execute("""
                INSERT INTO company_bank (bank_name, account_number, ifsc_code, branch_name, account_type)
                VALUES ('State Bank of India', '30099887766', 'SBIN0004560', 'Bhiwandi Branch', 'Current Account')
            """)

        # Create dispatch_location table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dispatch_location (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT NOT NULL UNIQUE,
                address_line_1 TEXT NOT NULL,
                address_line_2 TEXT,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                state_code TEXT NOT NULL,
                gstin TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Seed default dispatch location if empty
        cursor.execute("SELECT COUNT(*) FROM dispatch_location")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO dispatch_location (location_name, address_line_1, address_line_2, city, state, state_code, gstin)
                VALUES ('Main Facility (Noida)', 'Building C-1, Sector 63', 'Industrial Area', 'Noida', 'Uttar Pradesh', '09', '09AAACR1234A1Z9')
            """)
            cursor.execute("""
                INSERT INTO dispatch_location (location_name, address_line_1, address_line_2, city, state, state_code, gstin)
                VALUES ('Warehouse Bhiwandi', 'Building No. C1, 1st Floor', 'Antariksh Logidrome, Village Amane', 'Bhiwandi', 'Maharashtra', '27', '27AALCR5544C1ZB')
            """)
        
        # Seed default Service / Charge material if not present
        cursor.execute("SELECT id FROM material WHERE material_code = 'SERVICE_CHARGE'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO material (id, material_code, material_name, hsn_code, uom, gst_percentage, tracking_type)
                VALUES (999999, 'SERVICE_CHARGE', 'Service / Charge', '9987', 'NOS', 18.0, 'QUANTITY_ONLY')
            """)
        
        # 2. Run idempotent migrations to add columns if tables exist but lack them
        
        # Migrations for sales_invoice
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_invoice'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(sales_invoice)")
            columns = [row[1] for row in cursor.fetchall()]
            if "is_active" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN is_active INTEGER DEFAULT 1")
            if "eway_bill_number" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN eway_bill_number TEXT")
            if "reference_number" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN reference_number TEXT")
            if "created_by" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN created_by TEXT")
            if "updated_by" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN updated_by TEXT")
            if "print_count" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN print_count INTEGER DEFAULT 0")
            if "pdf_download_count" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN pdf_download_count INTEGER DEFAULT 0")
            if "billing_party_name" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN billing_party_name TEXT")
            if "billing_address" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN billing_address TEXT")
            if "billing_gstin" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN billing_gstin TEXT")
            if "billing_state" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN billing_state TEXT")
            if "billing_state_code" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN billing_state_code TEXT")
            if "billing_contact" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN billing_contact TEXT")
            if "shipping_party_name" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN shipping_party_name TEXT")
            if "shipping_address" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN shipping_address TEXT")
            if "shipping_gstin" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN shipping_gstin TEXT")
            if "shipping_state" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN shipping_state TEXT")
            if "shipping_state_code" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN shipping_state_code TEXT")
            if "shipping_contact" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN shipping_contact TEXT")
            if "dispatch_location" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN dispatch_location TEXT")
            if "dispatch_address" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN dispatch_address TEXT")
            if "dispatch_gstin" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN dispatch_gstin TEXT")
            if "dispatch_state" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN dispatch_state TEXT")
            if "dispatch_state_code" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN dispatch_state_code TEXT")
            if "company_bank_name" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN company_bank_name TEXT")
            if "company_bank_account_number" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN company_bank_account_number TEXT")
            if "company_bank_ifsc" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN company_bank_ifsc TEXT")
            if "company_bank_branch" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN company_bank_branch TEXT")
            if "financial_year" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN financial_year TEXT")
            if "tcs_rate" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN tcs_rate REAL DEFAULT 0.0")
            if "tcs_amount" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN tcs_amount REAL DEFAULT 0.0")
            if "tcs_base_amount" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN tcs_base_amount REAL DEFAULT 0.0")
            if "tcs_applicable" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN tcs_applicable INTEGER DEFAULT 0")
            if "amount_in_words" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN amount_in_words TEXT")

        # Migrations for purchase_invoice
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_invoice'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(purchase_invoice)")
            columns = [row[1] for row in cursor.fetchall()]
            if "intake_type" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN intake_type TEXT DEFAULT 'Purchase'")
            if "eway_bill_number" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN eway_bill_number TEXT")
            if "reference_number" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN reference_number TEXT")
            if "created_by" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN created_by TEXT")
            if "updated_by" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN updated_by TEXT")
            if "print_count" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN print_count INTEGER DEFAULT 0")
            if "pdf_download_count" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN pdf_download_count INTEGER DEFAULT 0")
            if "vehicle_type" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN vehicle_type TEXT")
            if "driver_name" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN driver_name TEXT")
            if "weight_slip_number" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN weight_slip_number TEXT")
            if "ready_for_processing" not in columns:
                cursor.execute("ALTER TABLE purchase_invoice ADD COLUMN ready_for_processing INTEGER DEFAULT 0")

        # Migrations for material
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='material'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(material)")
            columns = [row[1] for row in cursor.fetchall()]
            if "tracking_type" not in columns:
                cursor.execute("ALTER TABLE material ADD COLUMN tracking_type TEXT NOT NULL DEFAULT 'BOTH'")

        # Migrations for processing_output
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processing_output'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(processing_output)")
            columns = [row[1] for row in cursor.fetchall()]
            if "output_category" not in columns:
                cursor.execute("ALTER TABLE processing_output ADD COLUMN output_category TEXT NOT NULL DEFAULT 'RECOVERABLE'")

        # Migrations for activity_log
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(activity_log)")
            columns = [row[1] for row in cursor.fetchall()]
            if "module" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN module TEXT")
            if "reference_number" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN reference_number TEXT")
            if "remarks" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN remarks TEXT")
            if "ip_address" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN ip_address TEXT")
            if "approval" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN approval TEXT")
            if "device" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN device TEXT")
            # Module 3 – Platform Services additions
            if "session_id" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN session_id TEXT")
            if "record_id" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN record_id TEXT")
            if "before_value" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN before_value TEXT")
            if "after_value" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN after_value TEXT")
            if "severity" not in columns:
                cursor.execute("ALTER TABLE activity_log ADD COLUMN severity TEXT DEFAULT 'INFO'")
        
        # Seed platform data (dashboard_widgets, kpi_definitions) if empty
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_widgets'")
        if cursor.fetchone():
            try:
                cursor.execute("SELECT COUNT(*) FROM dashboard_widgets")
                widget_count = cursor.fetchone()[0]
                if widget_count == 0:
                    widgets = [
                        ('total_purchase_today','Today Purchase','METRIC','purchase','/platform/api/kpi/total_purchase_today','bi bi-cart','#10b981',1),
                        ('total_sales_today','Today Sales','METRIC','sales','/platform/api/kpi/total_sales_today','bi bi-receipt','#6366f1',2),
                        ('inventory_value','Inventory Value','METRIC','inventory','/platform/api/kpi/inventory_value','bi bi-boxes','#f59e0b',3),
                        ('pending_certificates','Pending Certificates','METRIC','certificate','/platform/api/kpi/pending_certificates','bi bi-patch-check','#ef4444',4),
                        ('activity_feed','Recent Activity','FEED','platform','/platform/api/widgets/activity_feed','bi bi-activity','#8b5cf6',5),
                        ('processing_jobs','Processing Jobs','METRIC','processing','/platform/api/kpi/processing_jobs','bi bi-cpu','#06b6d4',6),
                    ]
                    cursor.executemany(
                        'INSERT OR IGNORE INTO dashboard_widgets (widget_key,widget_name,widget_type,source_module,data_endpoint,icon,color,sort_order) VALUES (?,?,?,?,?,?,?,?)',
                        widgets
                    )
            except Exception:
                pass

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_definitions'")
        if cursor.fetchone():
            try:
                # Force reload of platform KPI definitions to apply corrected SQL formulas
                cursor.execute("DELETE FROM kpi_definitions WHERE kpi_key IN ('total_purchase_today','total_sales_today','inventory_value','pending_certificates','processing_jobs')")
                
                kpis = [
                    ('total_purchase_today','Total Purchase Today','OPERATIONAL','INR','SQL','SELECT COALESCE(SUM(grand_total),0) FROM purchase_invoice WHERE is_active=1 AND status!="CANCELLED" AND invoice_date=DATE("now")',None,None,None),
                    ('total_sales_today','Total Sales Today','OPERATIONAL','INR','SQL','SELECT COALESCE(SUM(grand_total),0) FROM sales_invoice WHERE is_active=1 AND status!="CANCELLED" AND invoice_date=DATE("now")',None,None,None),
                    ('inventory_value','Inventory Value','FINANCIAL','kg','SQL','SELECT COALESCE(SUM(current_weight),0) FROM inventory_balance WHERE current_weight>0',None,None,None),
                    ('pending_certificates','Pending Certificates','OPERATIONAL','count','SQL','SELECT COUNT(*) FROM processing_job pj WHERE pj.status = \'COMPLETED\' AND pj.id NOT IN (SELECT cp.processing_job_id FROM certificate_processing cp JOIN certificate c ON cp.certificate_id = c.id WHERE c.status NOT IN (\'CANCELLED\'))',None,None,None),
                    ('processing_jobs','Active Processing Jobs','OPERATIONAL','count','SQL','SELECT COUNT(*) FROM processing_job WHERE status IN (\'DRAFT\',\'IN_PROGRESS\')',None,None,None),
                ]
                cursor.executemany(
                    'INSERT OR IGNORE INTO kpi_definitions (kpi_key,kpi_name,kpi_category,unit,formula_type,formula,target_value,warning_threshold,critical_threshold) VALUES (?,?,?,?,?,?,?,?,?)',
                    kpis
                )
            except Exception:
                pass

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_movement'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(stock_movement)")
            columns = [row[1] for row in cursor.fetchall()]
            if "batch_id" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN batch_id INTEGER")
            if "batch_number" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN batch_number TEXT")
            if "from_location" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN from_location TEXT")
            if "to_location" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN to_location TEXT")
            if "financial_valuation" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN financial_valuation REAL DEFAULT 0.0")
            if "cogs" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN cogs REAL DEFAULT 0.0")
            if "disposal_cost" not in columns:
                cursor.execute("ALTER TABLE stock_movement ADD COLUMN disposal_cost REAL DEFAULT 0.0")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processing_input'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(processing_input)")
            columns = [row[1] for row in cursor.fetchall()]
            if "batch_id" not in columns:
                cursor.execute("ALTER TABLE processing_input ADD COLUMN batch_id INTEGER")
            if "batch_number" not in columns:
                cursor.execute("ALTER TABLE processing_input ADD COLUMN batch_number TEXT")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processing_output'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(processing_output)")
            columns = [row[1] for row in cursor.fetchall()]
            if "parent_batch_id" not in columns:
                cursor.execute("ALTER TABLE processing_output ADD COLUMN parent_batch_id INTEGER")
            if "parent_batch_number" not in columns:
                cursor.execute("ALTER TABLE processing_output ADD COLUMN parent_batch_number TEXT")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='disposal_queue'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(disposal_queue)")
            columns = [row[1] for row in cursor.fetchall()]
            if "parent_batch_id" not in columns:
                cursor.execute("ALTER TABLE disposal_queue ADD COLUMN parent_batch_id INTEGER")
            if "parent_batch_number" not in columns:
                cursor.execute("ALTER TABLE disposal_queue ADD COLUMN parent_batch_number TEXT")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_invoice_item'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(sales_invoice_item)")
            columns = [row[1] for row in cursor.fetchall()]
            if "batch_id" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN batch_id INTEGER")
            if "batch_number" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN batch_number TEXT")
            if "item_type" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN item_type TEXT DEFAULT 'Goods'")
            if "description" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN description TEXT")
            if "hsn_sac" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN hsn_sac TEXT")
            if "uom" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN uom TEXT DEFAULT 'KGS'")
            if "item_reference" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN item_reference TEXT")
            if "gst_percentage" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN gst_percentage REAL DEFAULT 18.0")
            if "cgst" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN cgst REAL DEFAULT 0.0")
            if "sgst" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN sgst REAL DEFAULT 0.0")
            if "igst" not in columns:
                cursor.execute("ALTER TABLE sales_invoice_item ADD COLUMN igst REAL DEFAULT 0.0")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='number_series'")
        if cursor.fetchone():
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO number_series (series_key, prefix, suffix, starting_number, current_number, padding_length, reset_yearly, last_reset_year)
                    VALUES ('EMPLOYEE', 'EMP-', '', 1, 0, 4, 1, 2026)
                """)
                cursor.execute("""
                    INSERT OR IGNORE INTO number_series (series_key, prefix, suffix, starting_number, current_number, padding_length, reset_yearly, last_reset_year)
                    VALUES ('BATCH', 'BATCH-2026-', '', 1, 0, 5, 1, 2026)
                """)
                cursor.execute("""
                    INSERT OR IGNORE INTO number_series (series_key, prefix, suffix, starting_number, current_number, padding_length, reset_yearly, last_reset_year)
                    VALUES ('DOCUMENT', 'DOC-2026-', '', 1, 0, 5, 1, 2026)
                """)
            except Exception:
                pass


 
            conn.commit()
    finally:
        conn.close()

    # V2 inventories are backfilled exactly once from confirmed source documents.
    # Future create/edit/delete events synchronize through InventoryService.
    try:
        from services.inventory_service import bootstrap_inventory
    except ModuleNotFoundError:
        from backend.services.inventory_service import bootstrap_inventory
    bootstrap_inventory()


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
