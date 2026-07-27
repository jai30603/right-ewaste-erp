import datetime
import calendar
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


# ── Salary Structure Operations ──────────────────────────────────────────────

def get_salary_structure(employee_id, active_only=True, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM employee_salary_structure WHERE employee_id = ?"
        if active_only:
            query += " AND status = 'Active'"
        query += " ORDER BY id DESC LIMIT 1"
        cursor.execute(query, (employee_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row)
    finally:
        if close_conn:
            conn.close()


def get_salary_structure_history(employee_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM employee_salary_structure 
            WHERE employee_id = ? 
            ORDER BY effective_from DESC, id DESC
        """, (employee_id,))
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()


def save_salary_structure(data, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        emp_id = int(data["employee_id"])

        basic = float(data.get("basic_salary", 0))
        hra = float(data.get("hra", 0))
        conv = float(data.get("conveyance_allowance", 0))
        med = float(data.get("medical_allowance", 0))
        spec = float(data.get("special_allowance", 0))
        other_all = float(data.get("other_allowances", 0))

        pf = float(data.get("provident_fund", 0))
        pt = float(data.get("professional_tax", 0))
        it = float(data.get("income_tax", 0))
        other_ded = float(data.get("other_deductions", 0))

        gross = round(basic + hra + conv + med + spec + other_all, 2)
        total_ded = round(pf + pt + it + other_ded, 2)
        net = round(max(0.0, gross - total_ded), 2)
        effective_from = data.get("effective_from") or datetime.date.today().isoformat()

        # Supercede previous active structures for this employee
        cursor.execute("""
            UPDATE employee_salary_structure 
            SET status = 'Superceded', updated_at = CURRENT_TIMESTAMP
            WHERE employee_id = ? AND status = 'Active'
        """, (emp_id,))

        cursor.execute("""
            INSERT INTO employee_salary_structure (
                employee_id, effective_from, basic_salary, hra, conveyance_allowance,
                medical_allowance, special_allowance, other_allowances,
                provident_fund, professional_tax, income_tax, other_deductions,
                gross_salary, net_salary, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        """, (
            emp_id, effective_from, basic, hra, conv, med, spec, other_all,
            pf, pt, it, other_ded, gross, net
        ))

        struct_id = cursor.lastrowid
        if close_conn:
            conn.commit()
        return struct_id
    finally:
        if close_conn:
            conn.close()


# ── Attendance & Leave Summary for Payroll ───────────────────────────────────

def calculate_employee_attendance_summary(employee_id, month, year, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        _, total_working_days = calendar.monthrange(year, month)

        start_date = f"{year:04d}-{month:02d}-01"
        end_date = f"{year:04d}-{month:02d}-{total_working_days:02d}"

        cursor.execute("""
            SELECT attendance_status, COUNT(*) as cnt
            FROM employee_attendance
            WHERE employee_id = ? AND attendance_date BETWEEN ? AND ?
            GROUP BY attendance_status
        """, (employee_id, start_date, end_date))

        status_counts = {r[0]: r[1] for r in cursor.fetchall()}

        if not status_counts:
            # Default to full month present if no daily attendance logged
            return {
                "working_days": total_working_days,
                "present_days": float(total_working_days),
                "leave_days": 0.0,
                "absent_days": 0.0
            }

        p_cnt = status_counts.get("Present", 0) + (0.5 * status_counts.get("Half Day", 0))
        l_cnt = status_counts.get("Leave", 0) + status_counts.get("Holiday", 0)
        a_cnt = status_counts.get("Absent", 0)

        # Unmarked days count as present by default
        logged_days = status_counts.get("Present", 0) + status_counts.get("Half Day", 0) + status_counts.get("Leave", 0) + status_counts.get("Holiday", 0) + status_counts.get("Absent", 0)
        unmarked = max(0, total_working_days - logged_days)
        p_cnt += unmarked

        return {
            "working_days": total_working_days,
            "present_days": float(p_cnt),
            "leave_days": float(l_cnt),
            "absent_days": float(a_cnt)
        }
    finally:
        if close_conn:
            conn.close()


# ── Payroll Generation & Management ──────────────────────────────────────────

def generate_monthly_payroll(month, year, user_name="System", conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        # Fetch active employees
        cursor.execute("SELECT id, full_name, employee_code FROM employees WHERE status = 'Active'")
        active_employees = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

        generated_count = 0
        skipped_count = 0
        errors = []

        for emp in active_employees:
            emp_id = emp["id"]
            # Check if payroll already exists for month/year
            cursor.execute("""
                SELECT id, payroll_status FROM employee_payroll 
                WHERE employee_id = ? AND payroll_month = ? AND payroll_year = ?
            """, (emp_id, month, year))
            existing = cursor.fetchone()

            if existing:
                if existing[1] == "Paid":
                    skipped_count += 1
                    continue
                else:
                    # Delete draft to regenerate
                    cursor.execute("DELETE FROM employee_payroll WHERE id = ?", (existing[0],))

            # Fetch active salary structure
            struct = get_salary_structure(emp_id, active_only=True, conn=conn)
            if not struct:
                errors.append(f"Employee '{emp['full_name']}' ({emp['employee_code']}) has no salary structure configured.")
                continue

            att_summary = calculate_employee_attendance_summary(emp_id, month, year, conn=conn)

            working_days = att_summary["working_days"]
            payable_days = att_summary["present_days"] + att_summary["leave_days"]
            ratio = min(1.0, max(0.0, payable_days / working_days)) if working_days > 0 else 1.0

            gross_salary = round(struct["gross_salary"] * ratio, 2)
            total_allowances = round((struct["hra"] + struct["conveyance_allowance"] + struct["medical_allowance"] + struct["special_allowance"] + struct["other_allowances"]) * ratio, 2)
            total_deductions = round(struct["provident_fund"] + struct["professional_tax"] + struct["income_tax"] + struct["other_deductions"], 2)
            net_salary = round(max(0.0, gross_salary - total_deductions), 2)

            cursor.execute("""
                INSERT INTO employee_payroll (
                    employee_id, payroll_month, payroll_year, working_days,
                    present_days, leave_days, absent_days, gross_salary,
                    total_allowances, total_deductions, net_salary,
                    payroll_status, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Generated', ?)
            """, (
                emp_id, month, year, working_days,
                att_summary["present_days"], att_summary["leave_days"], att_summary["absent_days"],
                gross_salary, total_allowances, total_deductions, net_salary,
                user_name
            ))
            generated_count += 1

        if close_conn:
            conn.commit()
        return generated_count, skipped_count, errors
    finally:
        if close_conn:
            conn.close()


def get_payroll_records(month=None, year=None, department=None, status=None, search=None, page=1, per_page=10, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if month:
            where_clauses.append("p.payroll_month = ?")
            params.append(month)
        if year:
            where_clauses.append("p.payroll_year = ?")
            params.append(year)
        if department:
            where_clauses.append("e.department = ?")
            params.append(department)
        if status:
            where_clauses.append("p.payroll_status = ?")
            params.append(status)
        if search:
            search_term = f"%{search.strip()}%"
            where_clauses.append("(e.employee_code LIKE ? OR e.full_name LIKE ?)")
            params.extend([search_term, search_term])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cursor.execute(f"SELECT COUNT(*) FROM employee_payroll p JOIN employees e ON p.employee_id = e.id{where_sql}", params)
        total_count = cursor.fetchone()[0]

        per_page = max(1, int(per_page))
        page = max(1, int(page))
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        offset = (page - 1) * per_page

        cursor.execute(f"""
            SELECT 
                p.*, 
                e.employee_code, 
                e.full_name, 
                e.department, 
                e.designation
            FROM employee_payroll p
            JOIN employees e ON p.employee_id = e.id
            {where_sql}
            ORDER BY p.payroll_year DESC, p.payroll_month DESC, p.id DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset])

        rows = cursor.fetchall()
        records = [_row_to_dict(cursor, r) for r in rows]

        return {
            "records": records,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page
        }
    finally:
        if close_conn:
            conn.close()


def get_payroll_by_id(payroll_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.*, 
                e.employee_code, 
                e.first_name, 
                e.last_name, 
                e.full_name, 
                e.department, 
                e.designation,
                e.pan_number,
                e.aadhaar_number,
                b.bank_name,
                b.account_number,
                b.ifsc_code,
                s.basic_salary,
                s.hra,
                s.conveyance_allowance,
                s.medical_allowance,
                s.special_allowance,
                s.other_allowances,
                s.provident_fund,
                s.professional_tax,
                s.income_tax,
                s.other_deductions
            FROM employee_payroll p
            JOIN employees e ON p.employee_id = e.id
            LEFT JOIN employee_bank_details b ON e.id = b.employee_id
            LEFT JOIN employee_salary_structure s ON e.id = s.employee_id AND s.status = 'Active'
            WHERE p.id = ?
        """, (payroll_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row)
    finally:
        if close_conn:
            conn.close()


def update_payroll_status(payroll_id, new_status, user_name="System", conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT payroll_status FROM employee_payroll WHERE id = ?", (payroll_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Payroll record not found."
        if row[0] == "Paid" and new_status != "Paid":
            return False, "Payroll is marked as Paid and locked."

        cursor.execute("""
            UPDATE employee_payroll 
            SET payroll_status = ?, generated_by = ?
            WHERE id = ?
        """, (new_status, user_name, payroll_id))

        if close_conn:
            conn.commit()
        return True, None
    finally:
        if close_conn:
            conn.close()


def get_payroll_dashboard_stats(month=None, year=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        today = datetime.date.today()
        m = month or today.month
        y = year or today.year

        cursor.execute("SELECT COUNT(*) FROM employee_payroll WHERE payroll_month = ? AND payroll_year = ?", (m, y))
        processed_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employee_payroll WHERE payroll_month = ? AND payroll_year = ? AND payroll_status = 'Generated'", (m, y))
        pending_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employee_payroll WHERE payroll_month = ? AND payroll_year = ? AND payroll_status = 'Paid'", (m, y))
        paid_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(net_salary), AVG(net_salary) FROM employee_payroll WHERE payroll_month = ? AND payroll_year = ?", (m, y))
        sum_avg = cursor.fetchone()
        total_monthly_payroll = sum_avg[0] or 0.0
        avg_salary = sum_avg[1] or 0.0

        # Recent payroll runs
        cursor.execute("""
            SELECT 
                p.*, 
                e.employee_code, 
                e.full_name, 
                e.department
            FROM employee_payroll p
            JOIN employees e ON p.employee_id = e.id
            ORDER BY p.id DESC
            LIMIT 5
        """)
        recent_runs = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

        return {
            "month": m,
            "year": y,
            "employees_processed": processed_count,
            "pending_payroll": pending_count,
            "employees_paid": paid_count,
            "total_monthly_payroll": round(total_monthly_payroll, 2),
            "average_salary": round(avg_salary, 2),
            "recent_runs": recent_runs
        }
    finally:
        if close_conn:
            conn.close()


def get_payroll_report_data(report_type, month=None, year=None, department=None, employee_id=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if month:
            where_clauses.append("p.payroll_month = ?")
            params.append(month)
        if year:
            where_clauses.append("p.payroll_year = ?")
            params.append(year)
        if department:
            where_clauses.append("e.department = ?")
            params.append(department)
        if employee_id:
            where_clauses.append("e.id = ?")
            params.append(employee_id)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
            SELECT 
                p.id,
                e.employee_code,
                e.full_name,
                e.department,
                e.designation,
                p.payroll_month,
                p.payroll_year,
                p.working_days,
                p.present_days,
                p.leave_days,
                p.absent_days,
                p.gross_salary,
                p.total_allowances,
                p.total_deductions,
                p.net_salary,
                p.payroll_status,
                p.generated_by,
                p.generated_at
            FROM employee_payroll p
            JOIN employees e ON p.employee_id = e.id
            {where_sql}
            ORDER BY p.payroll_year DESC, p.payroll_month DESC, e.full_name ASC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        if close_conn:
            conn.close()
