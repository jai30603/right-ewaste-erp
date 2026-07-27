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
        
        # Pre-schema migration for storage_providers columns if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='storage_providers'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(storage_providers)")
            cols = [row[1] for row in cursor.fetchall()]
            if "provider_type" not in cols:
                cursor.execute("ALTER TABLE storage_providers ADD COLUMN provider_type TEXT")
            if "is_active" not in cols:
                cursor.execute("ALTER TABLE storage_providers ADD COLUMN is_active INTEGER DEFAULT 0")
            if "health_status" not in cols:
                cursor.execute("ALTER TABLE storage_providers ADD COLUMN health_status TEXT DEFAULT 'UNKNOWN'")
            if "last_connection_test" not in cols:
                cursor.execute("ALTER TABLE storage_providers ADD COLUMN last_connection_test DATETIME")
            if "last_synchronization" not in cols:
                cursor.execute("ALTER TABLE storage_providers ADD COLUMN last_synchronization DATETIME")
            if "updated_at" not in cols:
                cursor.execute("ALTER TABLE storage_providers ADD COLUMN updated_at DATETIME")

        # 1. Run all schema SQL scripts dynamically from database/schema
        schema_dir = BASE_DIR / "database" / "schema"
        if schema_dir.is_dir():
            sql_files = sorted(schema_dir.glob("*.sql"))
            for sql_file in sql_files:
                with open(sql_file, "r", encoding="utf-8") as f:
                    sql_script = f.read()
                cursor.executescript(sql_script)
        
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

        # Seed EDMS Storage Provider & Root Folders
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='storage_providers'")
        if cursor.fetchone():
            cursor.execute("""
                INSERT OR IGNORE INTO storage_providers (id, provider_key, provider_name, status, config_json, is_default)
                VALUES (1, 'local', 'Local Storage Provider', 'ACTIVE', '{"base_dir": "storage"}', 1)
            """)

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folders'")
        if cursor.fetchone():
            import uuid
            root_folders = [
                ('Company Drive', 'COMPANY', '/company'),
                ('Users', 'USER', '/users'),
                ('Modules', 'MODULE', '/modules'),
                ('System', 'SYSTEM', '/system'),
                ('Temporary', 'TEMPORARY', '/temp'),
                ('Trash', 'TRASH', '/trash')
            ]
        # Idempotent Migrations for multi-repository support
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folders'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(folders)")
            cols = [row[1] for row in cursor.fetchall()]
            if "repository_id" not in cols:
                cursor.execute("ALTER TABLE folders ADD COLUMN repository_id INTEGER")
                cursor.execute("UPDATE folders SET repository_id = 1")
                cursor.execute("UPDATE folders SET repository_id = 2 WHERE path = '/company' OR path LIKE '/company/%'")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(documents)")
            cols = [row[1] for row in cursor.fetchall()]
            if "repository_id" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN repository_id INTEGER")
                cursor.execute("UPDATE documents SET repository_id = 1")
                cursor.execute("UPDATE documents SET repository_id = 2 WHERE folder_id IN (SELECT id FROM folders WHERE repository_id = 2)")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recycle_bin'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(recycle_bin)")
            cols = [row[1] for row in cursor.fetchall()]
            if "repository_id" not in cols:
                cursor.execute("ALTER TABLE recycle_bin ADD COLUMN repository_id INTEGER")
                cursor.execute("UPDATE recycle_bin SET repository_id = 1")

        # Migrations for documents table (Content Intelligence)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(documents)")
            cols = [row[1] for row in cursor.fetchall()]
            if "version" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN version INTEGER DEFAULT 1")
            if "classification" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN classification TEXT DEFAULT 'INTERNAL'")
            if "lifecycle_status" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN lifecycle_status TEXT DEFAULT 'UPLOADED'")
            if "ocr_text" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN ocr_text TEXT")
            if "ai_summary" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN ai_summary TEXT")
            if "retention_until" not in cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN retention_until TIMESTAMP")

        # Users UUID migration
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(users)")
            cols = [row[1] for row in cursor.fetchall()]
            if "uuid" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN uuid TEXT")
            
            cursor.execute("SELECT id, uuid FROM users")
            users_list = cursor.fetchall()
            import uuid
            for u in users_list:
                if not u[1]:
                    cursor.execute("UPDATE users SET uuid = ? WHERE id = ?", (str(uuid.uuid4()), u[0]))

        # Storage providers config backfill
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='storage_providers'")
        if cursor.fetchone():
            cursor.execute("UPDATE storage_providers SET config_json = 'KTQ=' WHERE config_json = '{}'")

        # Seed Document Tags
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_tags'")
        if cursor.fetchone():
            initial_tags = [
                ('GST', '#10b981'),
                ('Invoice', '#3b82f6'),
                ('Vendor', '#6366f1'),
                ('Certificate', '#8b5cf6'),
                ('Hazardous', '#ef4444'),
                ('Internal', '#64748b'),
                ('Audit', '#f59e0b'),
                ('Compliance', '#14b8a6'),
                ('Safety', '#ec4899'),
                ('Legal', '#06b6d4')
            ]
            for tag_name, color in initial_tags:
                cursor.execute("INSERT OR IGNORE INTO document_tags (tag_name, color_hex) VALUES (?, ?)", (tag_name, color))

        # Migrations for conversations table to support groups
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(conversations)")
            cols = [row[1] for row in cursor.fetchall()]
            if "type" not in cols:
                cursor.execute("ALTER TABLE conversations ADD COLUMN type TEXT DEFAULT 'DIRECT'")
            if "name" not in cols:
                cursor.execute("ALTER TABLE conversations ADD COLUMN name TEXT")
            if "description" not in cols:
                cursor.execute("ALTER TABLE conversations ADD COLUMN description TEXT")
            if "created_by" not in cols:
                cursor.execute("ALTER TABLE conversations ADD COLUMN created_by INTEGER")
            if "owner_id" not in cols:
                cursor.execute("ALTER TABLE conversations ADD COLUMN owner_id INTEGER")

        # Seed default groups
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
        if cursor.fetchone():
            default_groups = [
                ('General', 'Company-wide general discussions'),
                ('Purchase Team', 'Purchases and supplier discussions'),
                ('Sales Team', 'Sales and customer invoices'),
                ('Processing Team', 'Processing jobs and e-waste processing'),
                ('Inventory Team', 'Stock, warehouse, and material balance'),
                ('Warehouse', 'Warehouse logistics and material movements'),
                ('HR', 'HR, payroll, and leave management'),
                ('Management', 'ERP management and business decisions')
            ]
            for gname, desc in default_groups:
                cursor.execute("SELECT id FROM conversations WHERE type='GROUP' AND name=?", (gname,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO conversations (type, name, description, created_by, owner_id, status)
                        VALUES ('GROUP', ?, ?, 1, 1, 'ACTIVE')
                    """, (gname, desc))
                    conv_id = cursor.lastrowid
                    
                    # Auto-add all active users to default groups
                    cursor.execute("SELECT id FROM users WHERE status='ACTIVE'")
                    for urow in cursor.fetchall():
                        cursor.execute("""
                            INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id)
                            VALUES (?, ?)
                        """, (conv_id, urow[0]))

        # Seed default modules in module_registry
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_registry'")
        if cursor.fetchone():
            default_modules = [
                ('EDMS', 'bi bi-folder-symlink-fill', '{"description": "Enterprise Document Management System"}'),
                ('Tasks', 'bi bi-clipboard-check-fill', '{"description": "ERP Operations Tasks"}'),
                ('Purchase', 'bi bi-cart-fill', '{"description": "Purchase Inward Module"}'),
                ('Sales', 'bi bi-receipt', '{"description": "Sales Invoices Module"}'),
                ('Inventory', 'bi bi-boxes', '{"description": "Inventory Stock & Warehouse"}')
            ]
            for mname, micon, mconfig in default_modules:
                cursor.execute("SELECT id FROM module_registry WHERE module_name = ?", (mname,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO module_registry (module_name, module_icon, config_json)
                        VALUES (?, ?, ?)
                    """, (mname, micon, mconfig))

            # Seed default resource registries
            default_resources = [
                ('DOCUMENT', 'EDMS', '{"deep_link_template": "/api/v1/documents/{id}/download", "label": "EDMS Document"}'),
                ('TASK', 'Tasks', '{"deep_link_template": "/tasks/view/{id}", "label": "ERP Task"}'),
                ('PURCHASE_ORDER', 'Purchase', '{"deep_link_template": "/purchase/orders/view/{id}", "label": "Purchase Order"}'),
                ('INVENTORY_ITEM', 'Inventory', '{"deep_link_template": "/inventory/items/view/{id}", "label": "Inventory Item"}')
            ]
            for rtype, smod, rconfig in default_resources:
                cursor.execute("SELECT id FROM resource_registry WHERE resource_type = ?", (rtype,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO resource_registry (resource_type, source_module, config_json)
                        VALUES (?, ?, ?)
                    """, (rtype, smod, rconfig))            # Backfill Phase 3 tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_file_reference'")
            if cursor.fetchone():
                cursor.execute("""
                    INSERT INTO chat_file_reference (document_id, message_id, conversation_id, sender_id, shared_at)
                    SELECT CAST(sr.resource_id AS INTEGER), sr.message_id, m.conversation_id, sr.shared_by, sr.shared_at
                    FROM shared_resources sr
                    JOIN messages m ON sr.message_id = m.id
                    JOIN documents d ON CAST(sr.resource_id AS INTEGER) = d.id
                    JOIN users u ON sr.shared_by = u.id
                    WHERE sr.resource_type = 'DOCUMENT'
                      AND NOT EXISTS (
                          SELECT 1 FROM chat_file_reference cfr
                          WHERE cfr.message_id = sr.message_id AND cfr.document_id = CAST(sr.resource_id AS INTEGER)
                      );
                """)
                cursor.execute("""
                    INSERT INTO conversation_attachment (conversation_id, message_id, document_id)
                    SELECT m.conversation_id, sr.message_id, CAST(sr.resource_id AS INTEGER)
                    FROM shared_resources sr
                    JOIN messages m ON sr.message_id = m.id
                    JOIN documents d ON CAST(sr.resource_id AS INTEGER) = d.id
                    WHERE sr.resource_type = 'DOCUMENT'
                      AND NOT EXISTS (
                          SELECT 1 FROM conversation_attachment ca
                          WHERE ca.message_id = sr.message_id AND ca.document_id = CAST(sr.resource_id AS INTEGER)
                      );
                """)
                cursor.execute("""
                    INSERT INTO attachment_metadata (document_id, original_repository_id, file_type, file_size, sender_id, shared_at)
                    SELECT CAST(sr.resource_id AS INTEGER), COALESCE(d.repository_id, 1), d.extension, d.size_bytes, sr.shared_by, sr.shared_at
                    FROM shared_resources sr
                    JOIN documents d ON CAST(sr.resource_id AS INTEGER) = d.id
                    JOIN users u ON sr.shared_by = u.id
                    WHERE sr.resource_type = 'DOCUMENT'
                      AND NOT EXISTS (
                          SELECT 1 FROM attachment_metadata am
                          WHERE am.document_id = CAST(sr.resource_id AS INTEGER)
                      );
                """)
 
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
