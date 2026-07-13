from database import get_connection

def log_activity(user_name, action, details=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO activity_log (user_name, action, details)
        VALUES (?,?,?)
    """, (user_name or "System", action, details))
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
        SELECT id, user_name, action, details,
               strftime('%d %b %Y, %H:%M', created_at) AS formatted_time,
               created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

