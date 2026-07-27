import os
import sys
import sqlite3

# Insert backend directory in path so database module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection

def run_migration():
    print("Starting database schema migration for Document Engine V3.0...")
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Create audit_log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        previous_version INTEGER,
        new_version INTEGER,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("[OK] Audit log table created or verified.")

    # 2. Create document_template table for versioned templates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_key TEXT NOT NULL,
        template_name TEXT NOT NULL,
        title TEXT NOT NULL,
        declaration_text TEXT NOT NULL,
        show_logo INTEGER NOT NULL DEFAULT 1,
        show_customer_details INTEGER NOT NULL DEFAULT 1,
        show_purchase_references INTEGER NOT NULL DEFAULT 1,
        show_processing_summary INTEGER NOT NULL DEFAULT 1,
        show_weight_summary INTEGER NOT NULL DEFAULT 1,
        show_asset_list INTEGER NOT NULL DEFAULT 1,
        show_sustainability INTEGER NOT NULL DEFAULT 0,
        sustainability_statement TEXT,
        signature_title TEXT NOT NULL DEFAULT 'Authorized Signatory',
        logo_path TEXT,
        header_text TEXT,
        footer_text TEXT,
        page_layout TEXT NOT NULL DEFAULT 'A4_PORTRAIT',
        margin_top REAL NOT NULL DEFAULT 36.0,
        margin_bottom REAL NOT NULL DEFAULT 36.0,
        margin_left REAL NOT NULL DEFAULT 36.0,
        margin_right REAL NOT NULL DEFAULT 36.0,
        show_gst INTEGER NOT NULL DEFAULT 1,
        show_cin INTEGER NOT NULL DEFAULT 1,
        show_pan INTEGER NOT NULL DEFAULT 1,
        show_pcb INTEGER NOT NULL DEFAULT 1,
        show_iso INTEGER NOT NULL DEFAULT 0,
        show_r2 INTEGER NOT NULL DEFAULT 0,
        show_estewards INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        version INTEGER NOT NULL DEFAULT 1,
        template_json TEXT,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(template_key, version)
    )
    """)
    print("[OK] Versioned document_template table created or verified.")

    # 3. Import default templates if document_template is empty
    cursor.execute("SELECT COUNT(*) FROM document_template")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT * FROM certificate_template")
        old_templates = cursor.fetchall()
        for ot in old_templates:
            # certificate_template columns:
            # id, template_key, template_name, title, declaration_text, show_logo, show_customer_details, 
            # show_purchase_references, show_processing_summary, show_weight_summary, show_asset_list,
            # show_sustainability, sustainability_statement, signature_title, logo_path, header_text,
            # footer_text, page_layout, margin_top, margin_bottom, margin_left, margin_right, 
            # show_gst, show_cin, show_pan, show_pcb, show_iso, show_r2, show_estewards, status, version,
            # created_by, created_at, updated_at
            
            # Map columns by index (sqlite3.Row behaves like dict or tuple, so we can convert to dict)
            d = dict(ot)
            
            # Create a simple template_json representing this template's visual configuration
            # containing left, right, top, and center canvas items.
            import json
            default_layout = {
                "layout": d.get("page_layout", "A4_PORTRAIT"),
                "margins": {
                    "top": d.get("margin_top", 36.0),
                    "bottom": d.get("margin_bottom", 36.0),
                    "left": d.get("margin_left", 36.0),
                    "right": d.get("margin_right", 36.0)
                },
                "elements": [
                    {"type": "header", "content": d.get("header_text", ""), "styles": {"font-size": "10px", "color": "#475569"}},
                    {"type": "logo", "visible": d.get("show_logo", 1) == 1, "path": d.get("logo_path", "")},
                    {"type": "title", "content": d.get("title", ""), "styles": {"font-size": "24px", "font-weight": "bold", "text-align": "center", "color": "#1e3a8a"}},
                    {"type": "text", "content": d.get("declaration_text", ""), "styles": {"font-size": "12px", "line-height": "1.6", "text-align": "justify"}},
                    {"type": "dynamic_table", "visible": d.get("show_processing_summary", 1) == 1},
                    {"type": "signature", "title": d.get("signature_title", "Authorized Signatory"), "styles": {"text-align": "right"}}
                ]
            }
            d["template_json"] = json.dumps(default_layout)
            
            cursor.execute("""
            INSERT INTO document_template (
                template_key, template_name, title, declaration_text, show_logo, show_customer_details,
                show_purchase_references, show_processing_summary, show_weight_summary, show_asset_list,
                show_sustainability, sustainability_statement, signature_title, logo_path, header_text,
                footer_text, page_layout, margin_top, margin_bottom, margin_left, margin_right,
                show_gst, show_cin, show_pan, show_pcb, show_iso, show_r2, show_estewards, status, version,
                template_json, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d["template_key"], d["template_name"], d["title"], d["declaration_text"], d["show_logo"], d["show_customer_details"],
                d["show_purchase_references"], d["show_processing_summary"], d["show_weight_summary"], d["show_asset_list"],
                d["show_sustainability"], d["sustainability_statement"], d["signature_title"], d["logo_path"], d["header_text"],
                d["footer_text"], d["page_layout"], d["margin_top"], d["margin_bottom"], d["margin_left"], d["margin_right"],
                d["show_gst"], d["show_cin"], d["show_pan"], d["show_pcb"], d["show_iso"], d["show_r2"], d["show_estewards"],
                d["status"], d["version"], d["template_json"], d["created_by"]
            ))
        print("[OK] Ported existing templates to versioned document_template table.")

    # 4. Alter certificate table to add new columns
    # Check current columns in certificate table
    cursor.execute("PRAGMA table_info(certificate)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "purchase_id" not in columns:
        cursor.execute("ALTER TABLE certificate ADD COLUMN purchase_id INTEGER REFERENCES purchase_invoice(id)")
        print("[OK] Added purchase_id column to certificate table.")
    if "template_version" not in columns:
        cursor.execute("ALTER TABLE certificate ADD COLUMN template_version INTEGER DEFAULT 1")
        print("[OK] Added template_version column to certificate table.")
    if "template_json" not in columns:
        cursor.execute("ALTER TABLE certificate ADD COLUMN template_json TEXT")
        print("[OK] Added template_json column to certificate table.")
    if "custom_table_json" not in columns:
        cursor.execute("ALTER TABLE certificate ADD COLUMN custom_table_json TEXT")
        print("[OK] Added custom_table_json column to certificate table.")

    # 5. Alter party table to add default_template_key
    cursor.execute("PRAGMA table_info(party)")
    party_columns = [row[1] for row in cursor.fetchall()]
    if "default_template_key" not in party_columns:
        cursor.execute("ALTER TABLE party ADD COLUMN default_template_key TEXT")
        print("[OK] Added default_template_key column to party table.")

    # 6. Backfill purchase_id for existing certificates where possible
    # We look at certificate_purchase table
    cursor.execute("SELECT certificate_id, purchase_id FROM certificate_purchase")
    links = cursor.fetchall()
    backfilled_count = 0
    for link in links:
        cursor.execute("UPDATE certificate SET purchase_id = ? WHERE id = ? AND purchase_id IS NULL", (link[1], link[0]))
        if cursor.rowcount > 0:
            backfilled_count += 1
    if backfilled_count > 0:
        print(f"[OK] Backfilled {backfilled_count} certificates with purchase_id links.")

    conn.commit()
    conn.close()
    print("Database schema migration completed successfully.")

if __name__ == "__main__":
    run_migration()
