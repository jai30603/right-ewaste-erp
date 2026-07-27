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


def get_analytics_data(conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        today_str = datetime.date.today().isoformat()
        thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

        # Workforce Totals
        cursor.execute("SELECT COUNT(*) FROM employees")
        total_emp = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
        active_emp = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Inactive'")
        inactive_emp = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE joining_date >= ?", (thirty_days_ago,))
        new_joinings = cursor.fetchone()[0]

        # Department Distribution
        cursor.execute("""
            SELECT COALESCE(department, 'Unassigned') as dept, COUNT(*) as cnt
            FROM employees WHERE status = 'Active'
            GROUP BY COALESCE(department, 'Unassigned')
            ORDER BY cnt DESC
        """)
        dept_dist = {r[0]: r[1] for r in cursor.fetchall()}

        # Employment Type Distribution
        cursor.execute("""
            SELECT COALESCE(employment_type, 'Full Time') as emp_type, COUNT(*) as cnt
            FROM employees WHERE status = 'Active'
            GROUP BY COALESCE(employment_type, 'Full Time')
            ORDER BY cnt DESC
        """)
        type_dist = {r[0]: r[1] for r in cursor.fetchall()}

        # Attendance Stats Today
        cursor.execute("SELECT COUNT(*) FROM employee_attendance WHERE attendance_date = ? AND attendance_status = 'Present'", (today_str,))
        present_today = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT lr.employee_id) 
            FROM employee_leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            WHERE lr.status = 'Approved' AND ? BETWEEN lr.start_date AND lr.end_date AND e.status = 'Active'
        """, (today_str,))
        on_leave_today = cursor.fetchone()[0]

        att_pct = round((present_today / active_emp * 100.0), 1) if active_emp > 0 else 0.0

        # Current Month Payroll Stats
        today = datetime.date.today()
        cursor.execute("SELECT SUM(net_salary), AVG(net_salary), COUNT(*) FROM employee_payroll WHERE payroll_month = ? AND payroll_year = ?", (today.month, today.year))
        pr_row = cursor.fetchone()
        monthly_payroll = pr_row[0] or 0.0
        avg_salary = pr_row[1] or 0.0
        paid_count = pr_row[2] or 0

        return {
            "total_employees": total_emp,
            "active_employees": active_emp,
            "inactive_employees": inactive_emp,
            "new_joinings": new_joinings,
            "department_distribution": dept_dist,
            "employment_type_distribution": type_dist,
            "present_today": present_today,
            "on_leave_today": on_leave_today,
            "attendance_percentage": att_pct,
            "monthly_payroll": round(monthly_payroll, 2),
            "average_salary": round(avg_salary, 2),
            "employees_paid": paid_count
        }
    finally:
        if close_conn:
            conn.close()


def get_employee_directory_report(department=None, status=None, search=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if department:
            where_clauses.append("department = ?")
            params.append(department)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if search:
            s = f"%{search.strip()}%"
            where_clauses.append("(employee_code LIKE ? OR full_name LIKE ? OR email LIKE ?)")
            params.extend([s, s, s])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"SELECT * FROM employees {where_sql} ORDER BY employee_code ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()
