"""
Central Notification Service
All modules use this to send in-app notifications to users.
"""
import logging
from datetime import datetime
from database import get_connection

logger = logging.getLogger(__name__)


def send_notification(
    user_name: str,
    title: str,
    message: str,
    notification_type: str = 'INFO',  # INFO, SUCCESS, WARNING, ERROR, SYSTEM
    related_module: str = None,
    related_id: str = None,
    conn=None
):
    """Send an in-app notification to a specific user."""
    close_conn = conn is None
    if close_conn:
        conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO notifications (
                user_name, title, message, notification_type,
                related_module, related_id, is_read, created_at
            ) VALUES (?,?,?,?,?,?,0,?)
        """, (
            user_name, title, message, notification_type,
            related_module, str(related_id) if related_id else None,
            datetime.now().isoformat()
        ))
        if close_conn:
            conn.commit()
    except Exception as e:
        logger.warning(f"Notification send failed: {e}")
    finally:
        if close_conn:
            conn.close()


def broadcast_notification(
    title: str,
    message: str,
    notification_type: str = 'INFO',
    related_module: str = None,
    conn=None
):
    """Send notification to all active users."""
    close_conn = conn is None
    if close_conn:
        conn = get_connection()
    try:
        # Try erp_users first (Module 2 table), fallback to users table
        try:
            users = conn.execute("SELECT username FROM erp_users WHERE is_active=1").fetchall()
        except Exception:
            try:
                users = conn.execute("SELECT username FROM users WHERE status='ACTIVE'").fetchall()
            except Exception:
                users = []
        for user in users:
            send_notification(user[0], title, message, notification_type, related_module, conn=conn)
        if close_conn:
            conn.commit()
    except Exception as e:
        logger.warning(f"Broadcast failed: {e}")
    finally:
        if close_conn:
            conn.close()


def get_notifications(user_name: str, unread_only: bool = False, limit: int = 50):
    conn = get_connection()
    query = "SELECT * FROM notifications WHERE user_name=?"
    params = [user_name]
    if unread_only:
        query += " AND is_read=0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows


def mark_read(notification_id: int = None, user_name: str = None):
    conn = get_connection()
    if notification_id:
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notification_id,))
    elif user_name:
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_name=?", (user_name,))
    conn.commit()
    conn.close()


def get_unread_count(user_name: str) -> int:
    if not user_name:
        return 0
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_name=? AND is_read=0",
            (user_name,)
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()
