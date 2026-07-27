import sqlite3
from database import get_connection

def get_templates_list():
    """
    Retrieves latest version records for all unique template series in the library.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t1.* FROM document_template t1
            INNER JOIN (
                SELECT template_key, MAX(version) AS max_ver
                FROM document_template
                GROUP BY template_key
            ) t2 ON t1.template_key = t2.template_key AND t1.version = t2.max_ver
            ORDER BY t1.template_name
        """)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def get_template_by_key(template_key, version=None):
    """
    Loads a template by its key. If version is not specified, loads the latest version.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if version:
            cursor.execute(
                "SELECT * FROM document_template WHERE template_key = ? AND version = ?",
                (template_key, version)
            )
        else:
            cursor.execute(
                "SELECT * FROM document_template WHERE template_key = ? ORDER BY version DESC LIMIT 1",
                (template_key,)
            )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_supplier_default_template(party_id):
    """
    Queries supplier record default template preference.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT default_template_key FROM party WHERE id = ?", (party_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return get_template_by_key(row[0])
        return None
    finally:
        conn.close()

def set_supplier_default_template(party_id, template_key):
    """
    Updates a party's default template preference.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE party SET default_template_key = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (template_key, party_id)
        )
        conn.commit()
    finally:
        conn.close()

def save_template_version(t_data):
    """
    Immutable template versioning.
    Always inserts a new row with incremented version number, never overwrites!
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        
        # 1. Fetch current max version
        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) FROM document_template WHERE template_key = ?",
            (t_data["template_key"],)
        )
        current_max = cursor.fetchone()[0]
        next_ver = current_max + 1
        
        # 2. Insert new version row
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
            t_data["template_key"], t_data["template_name"], t_data["title"], t_data["declaration_text"],
            t_data.get("show_logo", 1), t_data.get("show_customer_details", 1),
            t_data.get("show_purchase_references", 1), t_data.get("show_processing_summary", 1),
            t_data.get("show_weight_summary", 1), t_data.get("show_asset_list", 1),
            t_data.get("show_sustainability", 0), t_data.get("sustainability_statement"),
            t_data.get("signature_title", "Authorized Signatory"), t_data.get("logo_path"),
            t_data.get("header_text"), t_data.get("footer_text"), t_data.get("page_layout", "A4_PORTRAIT"),
            t_data.get("margin_top", 36.0), t_data.get("margin_bottom", 36.0), t_data.get("margin_left", 36.0),
            t_data.get("margin_right", 36.0), t_data.get("show_gst", 1), t_data.get("show_cin", 1),
            t_data.get("show_pan", 1), t_data.get("show_pcb", 1), t_data.get("show_iso", 0),
            t_data.get("show_r2", 0), t_data.get("show_estewards", 0), t_data.get("status", "ACTIVE"),
            next_ver, t_data.get("template_json"), t_data.get("created_by", "System")
        ))
        
        conn.commit()
        return next_ver
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
