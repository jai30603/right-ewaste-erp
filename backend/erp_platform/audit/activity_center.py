"""
Activity Center
Human-readable timeline of all user actions across the ERP.
Every module calls log_activity() to record events here.
"""
import logging
from datetime import datetime
from flask import request, has_request_context, session
from database import get_connection

logger = logging.getLogger(__name__)


def log_activity(
    action: str,
    module: str = None,
    details: str = None,
    record_id: str = None,
    reference_number: str = None,
    before_value: str = None,
    after_value: str = None,
    severity: str = "INFO",
    user_name: str = None,
    ip_address: str = None,
    device: str = None,
    session_id: str = None,
    conn=None
):
    """
    Log a human-readable activity to activity_log.
    Falls back gracefully for old schema compatibility.
    """
    # Auto-fill from Flask request context
    if has_request_context():
        if not ip_address:
            try:
                ip_address = request.remote_addr
            except Exception:
                pass
        if not device:
            try:
                device = request.user_agent.string[:200]
            except Exception:
                pass
        if not user_name:
            try:
                user = session.get('user')
                if isinstance(user, dict):
                    user_name = user.get('username') or user.get('full_name', 'System')
                elif isinstance(user, str):
                    user_name = user
            except Exception:
                pass
        if not session_id:
            try:
                session_id = session.get('session_token', '')[:32] if session.get('session_token') else None
            except Exception:
                pass

    user_name = user_name or "System"

    close_conn = conn is None
    if close_conn:
        conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO activity_log (
                user_name, action, details, module, reference_number,
                ip_address, device, record_id, before_value, after_value,
                severity, session_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            user_name, action, details, module, reference_number,
            ip_address, device, str(record_id) if record_id else None,
            before_value, after_value, severity, session_id
        ))
        if close_conn:
            conn.commit()
    except Exception as e:
        # Graceful fallback for older schema
        logger.debug(f"Extended activity_log insert failed ({e}), using minimal fallback")
        try:
            conn.execute(
                "INSERT INTO activity_log (user_name, action, details) VALUES (?,?,?)",
                (user_name, action, details)
            )
            if close_conn:
                conn.commit()
        except Exception as e2:
            logger.warning(f"Activity log write failed: {e2}")
    finally:
        if close_conn:
            conn.close()


def get_activities(limit=50, module=None, user_name=None, severity=None):
    conn = get_connection()
    query = "SELECT * FROM activity_log WHERE 1=1"
    params = []
    if module:
        query += " AND module=?"
        params.append(module)
    if user_name:
        query += " AND user_name=?"
        params.append(user_name)
    if severity:
        query += " AND severity=?"
        params.append(severity)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cursor = conn.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_activity_stats():
    conn = get_connection()
    stats = {}
    # Today count
    r = conn.execute("SELECT COUNT(*) FROM activity_log WHERE DATE(created_at)=DATE('now')").fetchone()
    stats['today'] = r[0]
    # Total
    r = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()
    stats['total'] = r[0]
    # By module
    r = conn.execute("""
        SELECT module, COUNT(*) as cnt FROM activity_log
        WHERE module IS NOT NULL GROUP BY module ORDER BY cnt DESC LIMIT 10
    """).fetchall()
    stats['by_module'] = [{"module": row[0], "count": row[1]} for row in r]
    conn.close()
    return stats
