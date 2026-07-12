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
        
        # 2. Run idempotent migration to add is_active to sales_invoice if it exists but is missing is_active
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_invoice'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(sales_invoice)")
            columns = [row[1] for row in cursor.fetchall()]
            if "is_active" not in columns:
                cursor.execute("ALTER TABLE sales_invoice ADD COLUMN is_active INTEGER DEFAULT 1")
        
        conn.commit()
    finally:
        conn.close()


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn