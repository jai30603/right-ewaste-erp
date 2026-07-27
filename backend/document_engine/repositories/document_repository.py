import sqlite3
from database import get_connection

def insert_audit_log(user_name, action, entity_type, entity_id, previous_version=None, new_version=None, details=None, conn=None):
    """
    Inserts a row into the audit_log table.
    """
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log (
                user_name, action, entity_type, entity_id, previous_version, new_version, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_name, action, entity_type, str(entity_id), previous_version, new_version, details))
        if close_conn:
            conn.commit()
        return cursor.lastrowid
    finally:
        if close_conn:
            conn.close()

def get_audit_logs(entity_type=None, entity_id=None, limit=50):
    """
    Retrieves audit logs.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(str(entity_id))
            
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
