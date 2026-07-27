import datetime
import sqlite3
from database import get_connection

def _row_to_dict(cursor, row):
    if not row:
        return None
    try:
        if hasattr(row, "keys"):
            return dict(row)
    except Exception:
        pass
    desc = [d[0] for d in cursor.description]
    return dict(zip(desc, row))


# ── Leave Types Management ───────────────────────────────────────────────────

def get_all_leave_types(active_only=False, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM employee_leave_types"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id"
        cursor.execute(query)
        return [_row_to_dict(cursor, r) for r in cursor.fetchall()]
    finally:
        if close_conn:
            conn.close()


def get_leave_type_by_id(lt_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employee_leave_types WHERE id = ?", (lt_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row)
    finally:
        if close_conn:
            conn.close()


def save_leave_type(data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        if data.get("id"):
            cursor.execute("""
                UPDATE employee_leave_types SET
                    leave_name = ?, leave_code = ?, description = ?,
                    default_days = ?, is_paid = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data["leave_name"], data["leave_code"].upper(), data.get("description"),
                float(data.get("default_days", 0)), int(data.get("is_paid", 1)),
                int(data.get("is_active", 1)), data["id"]
            ))
            lt_id = data["id"]
        else:
            cursor.execute("""
                INSERT INTO employee_leave_types (
                    leave_name, leave_code, description, default_days, is_paid, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data["leave_name"], data["leave_code"].upper(), data.get("description"),
                float(data.get("default_days", 0)), int(data.get("is_paid", 1)),
                int(data.get("is_active", 1))
            ))
            lt_id = cursor.lastrowid

        if close_conn:
            conn.commit()
        return lt_id
    finally:
        if close_conn:
            conn.close()


# ── Leave Balance Management ─────────────────────────────────────────────────

def ensure_employee_leave_balances(employee_id, financial_year=2026, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        leave_types = get_all_leave_types(active_only=True, conn=conn)

        for lt in leave_types:
            cursor.execute("""
                INSERT INTO employee_leave_balance (
                    employee_id, leave_type_id, allocated_days, used_days, remaining_days, financial_year
                ) VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(employee_id, leave_type_id, financial_year) DO NOTHING
            """, (employee_id, lt["id"], lt["default_days"], lt["default_days"], financial_year))

        if close_conn:
            conn.commit()
    finally:
        if close_conn:
            conn.close()


def get_employee_leave_balance(employee_id, financial_year=2026, conn=None):
    ensure_employee_leave_balances(employee_id, financial_year, conn=conn)
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                b.*, 
                lt.leave_name, 
                lt.leave_code, 
                lt.is_paid, 
                lt.description
            FROM employee_leave_balance b
            JOIN employee_leave_types lt ON b.leave_type_id = lt.id
            WHERE b.employee_id = ? AND b.financial_year = ?
            ORDER BY lt.id
        """, (employee_id, financial_year))
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()


# ── Leave Dashboard Stats ─────────────────────────────────────────────────────

def get_leave_dashboard_stats(conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        today_str = datetime.date.today().isoformat()

        cursor.execute("SELECT COUNT(*) FROM employee_leave_requests WHERE status = 'Pending'")
        pending_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employee_leave_requests WHERE status = 'Approved'")
        approved_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT lr.employee_id) 
            FROM employee_leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            WHERE lr.status = 'Approved' AND ? BETWEEN lr.start_date AND lr.end_date AND e.status = 'Active'
        """, (today_str,))
        on_leave_today = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM employee_leave_balance b
            JOIN employees e ON b.employee_id = e.id
            WHERE b.remaining_days <= 2 AND e.status = 'Active'
        """)
        balance_alerts = cursor.fetchone()[0]

        # Recent 5 requests
        cursor.execute("""
            SELECT 
                lr.*, 
                e.employee_code, 
                e.full_name, 
                e.department,
                lt.leave_name, 
                lt.leave_code
            FROM employee_leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            JOIN employee_leave_types lt ON lr.leave_type_id = lt.id
            ORDER BY lr.id DESC
            LIMIT 5
        """)
        recent_requests = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

        return {
            "pending_requests": pending_count,
            "approved_leaves": approved_count,
            "on_leave_today": on_leave_today,
            "balance_alerts": balance_alerts,
            "recent_requests": recent_requests
        }
    finally:
        if close_conn:
            conn.close()


# ── Overlap & Request Management ─────────────────────────────────────────────

def check_leave_overlap(employee_id, start_date, end_date, exclude_id=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        query = """
            SELECT id FROM employee_leave_requests
            WHERE employee_id = ?
              AND status IN ('Pending', 'Approved')
              AND (start_date <= ? AND end_date >= ?)
        """
        params = [employee_id, end_date, start_date]

        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)

        cursor.execute(query, params)
        return cursor.fetchone() is not None
    finally:
        if close_conn:
            conn.close()


def create_leave_request(request_data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO employee_leave_requests (
                employee_id, leave_type_id, start_date, end_date, total_days,
                reason, attachment_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (
            request_data["employee_id"],
            request_data["leave_type_id"],
            request_data["start_date"],
            request_data["end_date"],
            request_data["total_days"],
            request_data["reason"],
            request_data.get("attachment_path")
        ))
        req_id = cursor.lastrowid
        if close_conn:
            conn.commit()
        return req_id
    finally:
        if close_conn:
            conn.close()


def get_leave_request_by_id(req_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                lr.*, 
                e.employee_code, 
                e.full_name, 
                e.department, 
                e.designation,
                e.status as employee_status,
                lt.leave_name, 
                lt.leave_code, 
                lt.is_paid
            FROM employee_leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            JOIN employee_leave_types lt ON lr.leave_type_id = lt.id
            WHERE lr.id = ?
        """, (req_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row)
    finally:
        if close_conn:
            conn.close()


def get_leave_requests(status=None, employee_id=None, department=None, search=None, page=1, per_page=10, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if status:
            where_clauses.append("lr.status = ?")
            params.append(status)

        if employee_id:
            where_clauses.append("lr.employee_id = ?")
            params.append(employee_id)

        if department:
            where_clauses.append("e.department = ?")
            params.append(department)

        if search:
            search_term = f"%{search.strip()}%"
            where_clauses.append("(e.employee_code LIKE ? OR e.full_name LIKE ? OR lt.leave_name LIKE ?)")
            params.extend([search_term, search_term, search_term])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Count total
        cursor.execute(f"SELECT COUNT(*) FROM employee_leave_requests lr JOIN employees e ON lr.employee_id = e.id JOIN employee_leave_types lt ON lr.leave_type_id = lt.id{where_sql}", params)
        total_count = cursor.fetchone()[0]

        per_page = max(1, int(per_page))
        page = max(1, int(page))
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        offset = (page - 1) * per_page

        cursor.execute(f"""
            SELECT 
                lr.*, 
                e.employee_code, 
                e.full_name, 
                e.department, 
                e.designation,
                lt.leave_name, 
                lt.leave_code, 
                lt.is_paid
            FROM employee_leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            JOIN employee_leave_types lt ON lr.leave_type_id = lt.id
            {where_sql}
            ORDER BY lr.id DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset])
        rows = cursor.fetchall()
        requests = [_row_to_dict(cursor, r) for r in rows]

        return {
            "requests": requests,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page
        }
    finally:
        if close_conn:
            conn.close()


# ── Status Transition & Attendance Sync ───────────────────────────────────────

def update_leave_request_status(req_id, new_status, approved_by=None, rejection_reason=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        req = get_leave_request_by_id(req_id, conn=conn)
        if not req:
            return False, "Leave request not found."

        old_status = req["status"]
        emp_id = req["employee_id"]
        lt_id = req["leave_type_id"]
        total_days = req["total_days"]
        is_paid = req["is_paid"]

        # 1. Update request status record
        cursor.execute("""
            UPDATE employee_leave_requests SET
                status = ?,
                approved_by = ?,
                approval_date = CURRENT_TIMESTAMP,
                rejection_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, approved_by, rejection_reason, req_id))

        # 2. Handle Balance & Attendance Synchronization
        if new_status == "Approved" and old_status != "Approved":
            # Update leave balance
            cursor.execute("""
                UPDATE employee_leave_balance SET
                    used_days = used_days + ?,
                    remaining_days = remaining_days - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE employee_id = ? AND leave_type_id = ? AND financial_year = 2026
            """, (total_days, total_days, emp_id, lt_id))

            # Synchronize to Attendance
            _sync_leave_to_attendance(cursor, emp_id, req["start_date"], req["end_date"], req["reason"], approved_by)

        elif new_status in ("Rejected", "Cancelled") and old_status == "Approved":
            # Reverse leave balance
            cursor.execute("""
                UPDATE employee_leave_balance SET
                    used_days = used_days - ?,
                    remaining_days = remaining_days + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE employee_id = ? AND leave_type_id = ? AND financial_year = 2026
            """, (total_days, total_days, emp_id, lt_id))

            # Unsync from Attendance
            _unsync_leave_from_attendance(cursor, emp_id, req["start_date"], req["end_date"])

        if close_conn:
            conn.commit()
        return True, None
    except Exception as e:
        if close_conn:
            conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()


def _sync_leave_to_attendance(cursor, employee_id, start_date_str, end_date_str, reason, user_name):
    s_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    e_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()

    curr_date = s_date
    while curr_date <= e_date:
        d_str = curr_date.isoformat()
        cursor.execute("""
            INSERT INTO employee_attendance (
                employee_id, attendance_date, attendance_status, remarks, created_by
            ) VALUES (?, ?, 'Leave', ?, ?)
            ON CONFLICT(employee_id, attendance_date) DO UPDATE SET
                attendance_status = 'Leave',
                remarks = excluded.remarks,
                updated_at = CURRENT_TIMESTAMP
        """, (employee_id, d_str, f"Leave: {reason}", user_name))
        curr_date += datetime.timedelta(days=1)


def _unsync_leave_from_attendance(cursor, employee_id, start_date_str, end_date_str):
    cursor.execute("""
        DELETE FROM employee_attendance
        WHERE employee_id = ?
          AND attendance_date BETWEEN ? AND ?
          AND attendance_status = 'Leave'
    """, (employee_id, start_date_str, end_date_str))


# ── Reports Dataset ──────────────────────────────────────────────────────────

def get_leave_report_data(report_type, start_date=None, end_date=None, department=None, employee_id=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = ["e.status = 'Active'"]
        params = []

        if start_date:
            where_clauses.append("lr.start_date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("lr.end_date <= ?")
            params.append(end_date)
        if department:
            where_clauses.append("e.department = ?")
            params.append(department)
        if employee_id:
            where_clauses.append("e.id = ?")
            params.append(employee_id)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                lr.id,
                e.employee_code,
                e.full_name,
                e.department,
                lt.leave_name,
                lr.start_date,
                lr.end_date,
                lr.total_days,
                lr.status,
                lr.reason,
                lr.approved_by,
                lr.created_at
            FROM employee_leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            JOIN employee_leave_types lt ON lr.leave_type_id = lt.id
            {where_sql}
            ORDER BY lr.id DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()
