import calendar
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


def get_attendance_dashboard_stats(date_str=None, conn=None):
    if not date_str:
        date_str = datetime.date.today().isoformat()

    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()

        # Total active employees
        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
        total_active = cursor.fetchone()[0]

        # Attendance breakdown for the specified date
        cursor.execute("""
            SELECT attendance_status, COUNT(*) 
            FROM employee_attendance ea
            JOIN employees e ON ea.employee_id = e.id
            WHERE ea.attendance_date = ? AND e.status = 'Active'
            GROUP BY attendance_status
        """, (date_str,))
        counts = {r[0]: r[1] for r in cursor.fetchall()}

        present = counts.get("Present", 0)
        absent = counts.get("Absent", 0)
        half_day = counts.get("Half Day", 0)
        leave = counts.get("Leave", 0)
        holiday = counts.get("Holiday", 0)
        marked_total = present + absent + half_day + leave + holiday

        # Calculate attendance percentage
        # Effective attendance = Present + (0.5 * Half Day)
        effective_present = present + (half_day * 0.5)
        attendance_pct = round((effective_present / total_active * 100), 1) if total_active > 0 else 0.0

        # Employees on leave today
        cursor.execute("""
            SELECT e.id, e.employee_code, e.full_name, e.department, ea.remarks
            FROM employee_attendance ea
            JOIN employees e ON ea.employee_id = e.id
            WHERE ea.attendance_date = ? AND ea.attendance_status = 'Leave' AND e.status = 'Active'
            ORDER BY e.full_name
        """, (date_str,))
        employees_on_leave = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

        return {
            "date": date_str,
            "total_active_employees": total_active,
            "marked_total": marked_total,
            "present_count": present,
            "absent_count": absent,
            "half_day_count": half_day,
            "leave_count": leave,
            "holiday_count": holiday,
            "attendance_percentage": attendance_pct,
            "employees_on_leave": employees_on_leave
        }
    finally:
        if close_conn:
            conn.close()


def get_daily_attendance_list(date_str, department=None, search=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = ["e.status = 'Active'"]
        params = [date_str]

        if department:
            where_clauses.append("e.department = ?")
            params.append(department)

        if search:
            search_term = f"%{search.strip()}%"
            where_clauses.append("(e.employee_code LIKE ? OR e.full_name LIKE ? OR e.mobile_number LIKE ?)")
            params.extend([search_term, search_term, search_term])

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                e.id as employee_id,
                e.employee_code,
                e.full_name,
                e.first_name,
                e.last_name,
                e.department,
                e.designation,
                e.profile_photo,
                ea.id as attendance_id,
                ea.attendance_date,
                ea.check_in_time,
                ea.check_out_time,
                COALESCE(ea.attendance_status, 'Present') as attendance_status,
                ea.remarks,
                CASE WHEN ea.id IS NOT NULL THEN 1 ELSE 0 END as is_marked
            FROM employees e
            LEFT JOIN employee_attendance ea ON e.id = ea.employee_id AND ea.attendance_date = ?
            {where_sql}
            ORDER BY e.department, e.full_name
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()


def save_bulk_attendance(records, user_name="System", conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        for rec in records:
            cursor.execute("""
                INSERT INTO employee_attendance (
                    employee_id, attendance_date, check_in_time, check_out_time,
                    attendance_status, remarks, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(employee_id, attendance_date) DO UPDATE SET
                    check_in_time = excluded.check_in_time,
                    check_out_time = excluded.check_out_time,
                    attendance_status = excluded.attendance_status,
                    remarks = excluded.remarks,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                rec["employee_id"],
                rec["attendance_date"],
                rec.get("check_in_time"),
                rec.get("check_out_time"),
                rec["attendance_status"],
                rec.get("remarks"),
                user_name
            ))
        if close_conn:
            conn.commit()
        return True
    except Exception:
        if close_conn:
            conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()


def get_employee_attendance_history(employee_id, year=None, month=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = ["employee_id = ?"]
        params = [employee_id]

        if year:
            where_clauses.append("strftime('%Y', attendance_date) = ?")
            params.append(str(year))
        if month:
            where_clauses.append("strftime('%m', attendance_date) = ?")
            params.append(f"{int(month):02d}")

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT * FROM employee_attendance
            {where_sql}
            ORDER BY attendance_date DESC
        """, params)
        records = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

        # Compute summary stats
        summary = {
            "Present": 0, "Absent": 0, "Half Day": 0, "Leave": 0, "Holiday": 0, "Total": len(records)
        }
        for r in records:
            st = r["attendance_status"]
            if st in summary:
                summary[st] += 1

        return {
            "records": records,
            "summary": summary
        }
    finally:
        if close_conn:
            conn.close()


def get_monthly_attendance_register(year, month, department=None, search=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()

        year = int(year)
        month = int(month)
        _, num_days = calendar.monthrange(year, month)

        where_clauses = ["e.status = 'Active'"]
        params = []

        if department:
            where_clauses.append("e.department = ?")
            params.append(department)

        if search:
            search_term = f"%{search.strip()}%"
            where_clauses.append("(e.employee_code LIKE ? OR e.full_name LIKE ?)")
            params.extend([search_term, search_term])

        where_sql = " WHERE " + " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT id, employee_code, full_name, department, designation
            FROM employees e
            {where_sql}
            ORDER BY department, full_name
        """, params)
        employees = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{num_days:02d}"

        cursor.execute("""
            SELECT employee_id, attendance_date, attendance_status
            FROM employee_attendance
            WHERE attendance_date BETWEEN ? AND ?
        """, (start_date, end_date))
        att_rows = cursor.fetchall()

        # Map attendance by employee_id -> day -> status
        att_map = {}
        for r in att_rows:
            emp_id = r[0]
            day = int(r[1].split("-")[2])
            status = r[2]
            if emp_id not in att_map:
                att_map[emp_id] = {}
            att_map[emp_id][day] = status

        # Abbreviation map
        abbr = {
            "Present": "P",
            "Absent": "A",
            "Half Day": "HD",
            "Leave": "L",
            "Holiday": "H"
        }

        register = []
        for emp in employees:
            emp_id = emp["id"]
            days_data = {}
            p_count, a_count, l_count, hd_count, h_count = 0, 0, 0, 0, 0

            emp_att = att_map.get(emp_id, {})
            for d in range(1, num_days + 1):
                st = emp_att.get(d)
                days_data[d] = abbr.get(st, "-")
                if st == "Present":
                    p_count += 1
                elif st == "Absent":
                    a_count += 1
                elif st == "Leave":
                    l_count += 1
                elif st == "Half Day":
                    hd_count += 1
                elif st == "Holiday":
                    h_count += 1

            register.append({
                "employee_id": emp_id,
                "employee_code": emp["employee_code"],
                "full_name": emp["full_name"],
                "department": emp["department"],
                "designation": emp["designation"],
                "days": days_data,
                "present_count": p_count,
                "absent_count": a_count,
                "leave_count": l_count,
                "half_day_count": hd_count,
                "holiday_count": h_count
            })

        return {
            "year": year,
            "month": month,
            "num_days": num_days,
            "days_list": list(range(1, num_days + 1)),
            "register": register
        }
    finally:
        if close_conn:
            conn.close()


def get_attendance_report_data(report_type, start_date=None, end_date=None, month=None, year=None, department=None, employee_id=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = ["e.status = 'Active'"]
        params = []

        if start_date:
            where_clauses.append("ea.attendance_date >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("ea.attendance_date <= ?")
            params.append(end_date)

        if month and year:
            where_clauses.append("strftime('%m', ea.attendance_date) = ?")
            params.append(f"{int(month):02d}")
            where_clauses.append("strftime('%Y', ea.attendance_date) = ?")
            params.append(str(year))

        if department:
            where_clauses.append("e.department = ?")
            params.append(department)

        if employee_id:
            where_clauses.append("e.id = ?")
            params.append(employee_id)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                ea.attendance_date,
                e.employee_code,
                e.full_name,
                e.department,
                e.designation,
                ea.attendance_status,
                ea.check_in_time,
                ea.check_out_time,
                ea.remarks
            FROM employee_attendance ea
            JOIN employees e ON ea.employee_id = e.id
            {where_sql}
            ORDER BY ea.attendance_date DESC, e.department, e.full_name
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()
