import sqlite3
from flask import request, has_request_context
from database import get_connection

def log_activity(
    user_name, action, details=None, 
    module=None, reference_number=None, remarks=None, 
    ip_address=None, approval=None, device=None,
    conn=None
):
    """
    Records a standardized activity log in the database.
    Attempts to write to advanced schema columns first. Fallbacks to details formatting on error.
    Automatically resolves remote IP address and User Agent if inside Flask context.
    """
    # Auto-resolve from Flask request context if available
    if has_request_context():
        if not ip_address:
            try:
                ip_address = request.remote_addr
            except Exception:
                pass
        if not device:
            try:
                device = request.user_agent.string
            except Exception:
                pass

    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO activity_log (
                user_name, action, details, module, reference_number, remarks, ip_address, approval, device
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_name or "System User", action, details, module, reference_number, remarks, ip_address, approval, device
        ))
    except sqlite3.OperationalError:
        # Fallback for old schema compatibility (if migrations haven't run)
        fallback_details = details or ""
        extra = []
        if module:
            extra.append(f"Module: {module}")
        if reference_number:
            extra.append(f"Ref: {reference_number}")
        if remarks:
            extra.append(f"Remarks: {remarks}")
        if extra:
            fallback_details = f"{fallback_details} | " + " | ".join(extra)
            
        cursor.execute("""
            INSERT INTO activity_log (user_name, action, details)
            VALUES (?, ?, ?)
        """, (user_name or "System User", action, fallback_details))
        
    if close_conn:
        conn.commit()
        conn.close()

def get_all_activities(limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM activity_log
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_recent_activities(limit=10):
    """Return the most recent activity log entries for the dashboard feed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, action, details, module, reference_number, remarks, ip_address, approval, device,
               strftime('%d %b %Y, %H:%M', created_at) AS formatted_time,
               created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
