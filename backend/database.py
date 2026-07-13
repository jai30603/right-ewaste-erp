import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE = BASE_DIR / "database" / "erp.db"

print("Database Path:", str(DATABASE.resolve()))


def initialize_database():
    conn = sqlite3.connect(DATABASE)
    try:
        cursor = conn.cursor()
        
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
        
        conn.commit()
    finally:
        conn.close()


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn