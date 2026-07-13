import sqlite3

def migrate():
    conn = sqlite3.connect("database/erp.db")
    cursor = conn.cursor()
    
    columns_to_add = [
        ("eway_bill_number", "TEXT"),
        ("reference_number", "TEXT"),
        ("created_by", "TEXT"),
        ("updated_by", "TEXT"),
        ("print_count", "INTEGER DEFAULT 0"),
        ("pdf_download_count", "INTEGER DEFAULT 0")
    ]
    
    # Check existing columns in sales_invoice
    cursor.execute("PRAGMA table_info(sales_invoice)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE sales_invoice ADD COLUMN {col_name} {col_type}")
                print(f"Added column {col_name} to sales_invoice table.")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists in sales_invoice table.")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
