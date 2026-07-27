import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "erp.db"

def verify():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    tables = [
        "sales_invoice",
        "sales_invoice_item",
        "purchase_invoice",
        "purchase_invoice_item",
        "certificate",
        "certificate_pdf",
        "certificate_processing",
        "certificate_purchase",
        "certificate_asset_attachment",
        "certificate_activity",
        "processing_job",
        "processing_input",
        "processing_output",
        "processing_loss",
        "processing_job_activity",
        "stock_movement",
        "inventory_balance",
        "inventory_metadata",
        "activity_log",
        "audit_log",
        "party"
    ]
    print("Verification results:")
    all_clean = True
    for t in tables:
        try:
            count = cursor.execute(f"SELECT count(1) FROM {t}").fetchone()[0]
            print(f"  {t}: {count}")
            if count > 0:
                all_clean = False
        except Exception as e:
            print(f"  {t}: ERROR ({e})")
            all_clean = False
            
    conn.close()
    
    if all_clean:
        print("SUCCESS: Database is fully cleaned!")
    else:
        print("WARNING: Some tables still contain operational records!")

if __name__ == "__main__":
    verify()
