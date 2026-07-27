import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "erp.db"


def clean_database():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Disable foreign keys temporarily for bulk deletes
        cursor.execute("PRAGMA foreign_keys = OFF;")

        tables_to_clear = [
            "sales_invoice_item",
            "sales_invoice",
            "purchase_invoice_item",
            "purchase_invoice",
            "certificate_processing",
            "certificate_purchase",
            "certificate_asset_attachment",
            "certificate_activity",
            "certificate_pdf",
            "certificate",
            "processing_input",
            "processing_output",
            "processing_loss",
            "processing_job_activity",
            "processing_job",
            "stock_movement",
            "inventory_balance",
            "inventory_metadata",
            "activity_log",
            "audit_log",
            "party"
        ]

        print("Deleting transactional records...")
        for table in tables_to_clear:
            cursor.execute(f"DELETE FROM {table};")
            print(f"  - Cleared table: {table}")

        print("Resetting auto-increment sequences...")
        for table in tables_to_clear:
            cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = ?", (table,))
            print(f"  - Reset sequence for: {table}")
            
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

        # Vacuum to clean storage layout
        cursor.execute("VACUUM;")
        print("Database cleanup committed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Database cleanup failed: {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    clean_database()
