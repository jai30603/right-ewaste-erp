"""
Audit Engine
Legal-grade immutable audit trail for every data change.
Captures field-level before/after values in the audit_log table.
"""
import json
import logging
from datetime import datetime
from flask import request, has_request_context, session
from database import get_connection

logger = logging.getLogger(__name__)


def audit_change(
    table_name: str,
    record_id,
    action: str,  # CREATE, UPDATE, DELETE, APPROVE, REJECT
    old_values: dict = None,
    new_values: dict = None,
    changed_by: str = None,
    reason: str = None,
    session_id: str = None,
    ip_address: str = None,
    conn=None
):
    """Record a field-level audit entry in audit_log matching the database schema."""
    if has_request_context():
        if not ip_address:
            try:
                ip_address = request.remote_addr
            except Exception:
                pass
        if not changed_by:
            try:
                user = session.get('user')
                if isinstance(user, dict):
                    changed_by = user.get('username') or user.get('full_name', 'System')
                elif isinstance(user, str):
                    changed_by = user
            except Exception:
                pass
        if not session_id:
            try:
                token = session.get('session_token', '')
                session_id = token[:32] if token else None
            except Exception:
                pass

    changed_by = changed_by or 'System'

    close_conn = conn is None
    if close_conn:
        conn = get_connection()

    try:
        # Save before/after values + metadata in the details field
        details_dict = {
            "old": old_values,
            "new": new_values,
            "reason": reason,
            "ip": ip_address,
            "session": session_id
        }
        details_json = json.dumps(details_dict)
        
        # Get versions if present, else None
        prev_ver = old_values.get('version') if isinstance(old_values, dict) else None
        new_ver = new_values.get('version') if isinstance(new_values, dict) else None

        conn.execute("""
            INSERT INTO audit_log (
                user_name, action, entity_type, entity_id, 
                previous_version, new_version, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            changed_by, action, table_name, str(record_id),
            prev_ver, new_ver, details_json
        ))
        if close_conn:
            conn.commit()
    except Exception as e:
        logger.warning(f"Audit write failed: {e}")
    finally:
        if close_conn:
            conn.close()


def get_audit_trail(table_name=None, record_id=None, limit=50):
    conn = get_connection()
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if table_name:
        query += " AND entity_type=?"
        params.append(table_name)
    if record_id:
        query += " AND entity_id=?"
        params.append(str(record_id))
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    trail = []
    for r in rows:
        row_dict = dict(r)
        details_val = row_dict.get('details')
        old_val = None
        new_val = None
        ip_addr = None
        sess_id = None
        
        if details_val:
            try:
                details_json = json.loads(details_val)
                if isinstance(details_json, dict):
                    old_val = details_json.get('old')
                    new_val = details_json.get('new')
                    ip_addr = details_json.get('ip')
                    sess_id = details_json.get('session')
            except Exception:
                pass
                
        trail.append({
            'table_name': row_dict.get('entity_type') or '',
            'record_id': row_dict.get('entity_id') or '',
            'action': row_dict.get('action') or '',
            'old_values': json.dumps(old_val, indent=2) if old_val else (row_dict.get('previous_version') or ''),
            'new_values': json.dumps(new_val, indent=2) if new_val else (row_dict.get('new_version') or ''),
            'changed_by': row_dict.get('user_name') or 'System',
            'session_id': sess_id or '',
            'ip_address': ip_addr or '',
            'changed_at': row_dict.get('created_at') or '',
        })
    return trail

