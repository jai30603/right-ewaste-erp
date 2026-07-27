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


def get_dashboard_stats(conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        total_employees = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
        active_employees = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Inactive'")
        inactive_employees = cursor.fetchone()[0]

        cursor.execute("""
            SELECT * FROM employees 
            ORDER BY joining_date DESC, id DESC 
            LIMIT 5
        """)
        rows = cursor.fetchall()
        recent_joinings = [_row_to_dict(cursor, r) for r in rows]

        return {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "inactive_employees": inactive_employees,
            "recent_joinings": recent_joinings
        }
    finally:
        if close_conn:
            conn.close()


def get_all_employees(
    search=None,
    department=None,
    designation=None,
    employment_type=None,
    status=None,
    page=1,
    per_page=10,
    sort_by="id",
    sort_dir="DESC"
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        where_clauses = []
        params = []

        if search:
            search_term = f"%{search.strip()}%"
            where_clauses.append("(e.employee_code LIKE ? OR e.full_name LIKE ? OR e.mobile_number LIKE ? OR e.email LIKE ?)")
            params.extend([search_term, search_term, search_term, search_term])

        if department:
            where_clauses.append("e.department = ?")
            params.append(department)

        if designation:
            where_clauses.append("e.designation = ?")
            params.append(designation)

        if employment_type:
            where_clauses.append("e.employment_type = ?")
            params.append(employment_type)

        if status:
            where_clauses.append("e.status = ?")
            params.append(status)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Allowed sort columns for safety
        allowed_sorts = {
            "id": "id",
            "employee_code": "employee_code",
            "full_name": "full_name",
            "department": "department",
            "designation": "designation",
            "joining_date": "joining_date",
            "status": "status"
        }
        order_col = allowed_sorts.get(sort_by, "id")
        order_dir = "ASC" if sort_dir.upper() == "ASC" else "DESC"

        # Count total matches
        count_query = f"SELECT COUNT(*) FROM employees e LEFT JOIN users u ON e.user_id = u.id{where_sql}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Calculate pagination
        per_page = max(1, int(per_page))
        page = max(1, int(page))
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        offset = (page - 1) * per_page

        query = f"""
            SELECT e.*, u.username as linked_username 
            FROM employees e
            LEFT JOIN users u ON e.user_id = u.id
            {where_sql}
            ORDER BY e.{order_col} {order_dir}
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()
        employees = [_row_to_dict(cursor, r) for r in rows]

        return {
            "employees": employees,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page
        }
    finally:
        conn.close()


def get_employee_by_id(emp_id, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.*, u.username as linked_username, u.erp_role as linked_user_role
            FROM employees e
            LEFT JOIN users u ON e.user_id = u.id
            WHERE e.id = ?
        """, (emp_id,))
        row = cursor.fetchone()
        if not row:
            return None
        emp_dict = _row_to_dict(cursor, row)

        # Bank details
        cursor.execute("SELECT * FROM employee_bank_details WHERE employee_id = ?", (emp_id,))
        bank_row = cursor.fetchone()
        emp_dict["bank_details"] = _row_to_dict(cursor, bank_row)

        # Emergency contacts
        cursor.execute("SELECT * FROM employee_emergency_contacts WHERE employee_id = ?", (emp_id,))
        contacts_rows = cursor.fetchall()
        emp_dict["emergency_contacts"] = [_row_to_dict(cursor, r) for r in contacts_rows]

        return emp_dict
    finally:
        if close_conn:
            conn.close()


def get_employee_by_code(emp_code, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM employees WHERE employee_code = ?", (emp_code,))
        row = cursor.fetchone()
        if row:
            return get_employee_by_id(row[0], conn=conn)
        return None
    finally:
        if close_conn:
            conn.close()


def check_uniqueness(field_name, value, exclude_id=None, conn=None):
    if not value or not str(value).strip():
        return True
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        allowed_fields = ["email", "mobile_number", "aadhaar_number", "pan_number", "employee_code"]
        if field_name not in allowed_fields:
            return True

        if exclude_id:
            query = f"SELECT id FROM employees WHERE {field_name} = ? AND id != ?"
            cursor.execute(query, (value.strip(), exclude_id))
        else:
            query = f"SELECT id FROM employees WHERE {field_name} = ?"
            cursor.execute(query, (value.strip(),))

        row = cursor.fetchone()
        return row is None
    finally:
        if close_conn:
            conn.close()


def create_employee(emp_data, bank_data=None, emergency_contacts=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO employees (
                employee_code, first_name, last_name, full_name, gender, date_of_birth,
                mobile_number, email, profile_photo, joining_date, department, designation,
                reporting_manager, employment_type, status, current_address, permanent_address,
                aadhaar_number, pan_number, user_id, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            emp_data["employee_code"],
            emp_data["first_name"],
            emp_data.get("last_name"),
            emp_data["full_name"],
            emp_data.get("gender"),
            emp_data.get("date_of_birth"),
            emp_data.get("mobile_number"),
            emp_data.get("email"),
            emp_data.get("profile_photo"),
            emp_data.get("joining_date"),
            emp_data.get("department"),
            emp_data.get("designation"),
            emp_data.get("reporting_manager"),
            emp_data.get("employment_type", "Full-Time"),
            emp_data.get("status", "Active"),
            emp_data.get("current_address"),
            emp_data.get("permanent_address"),
            emp_data.get("aadhaar_number"),
            emp_data.get("pan_number"),
            emp_data.get("user_id"),
            emp_data.get("created_by"),
            emp_data.get("updated_by")
        ))
        emp_id = cursor.lastrowid

        # Insert bank details if provided
        if bank_data and any(bank_data.values()):
            cursor.execute("""
                INSERT INTO employee_bank_details (
                    employee_id, bank_name, account_holder_name, account_number, ifsc_code, branch_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                emp_id,
                bank_data.get("bank_name"),
                bank_data.get("account_holder_name"),
                bank_data.get("account_number"),
                bank_data.get("ifsc_code"),
                bank_data.get("branch_name")
            ))

        # Insert emergency contacts if provided
        if emergency_contacts:
            for contact in emergency_contacts:
                if contact.get("contact_name") or contact.get("mobile_number"):
                    cursor.execute("""
                        INSERT INTO employee_emergency_contacts (
                            employee_id, contact_name, relationship, mobile_number
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        emp_id,
                        contact.get("contact_name"),
                        contact.get("relationship"),
                        contact.get("mobile_number")
                    ))

        # Synchronize user table employee_id link if user_id was selected
        if emp_data.get("user_id"):
            cursor.execute("""
                UPDATE users SET employee_id = ? WHERE id = ?
            """, (emp_data["employee_code"], emp_data["user_id"]))

        if close_conn:
            conn.commit()
        return emp_id
    except Exception:
        if close_conn:
            conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()


def update_employee(emp_id, emp_data, bank_data=None, emergency_contacts=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE employees SET
                first_name = ?,
                last_name = ?,
                full_name = ?,
                gender = ?,
                date_of_birth = ?,
                mobile_number = ?,
                email = ?,
                profile_photo = COALESCE(?, profile_photo),
                joining_date = ?,
                department = ?,
                designation = ?,
                reporting_manager = ?,
                employment_type = ?,
                status = ?,
                current_address = ?,
                permanent_address = ?,
                aadhaar_number = ?,
                pan_number = ?,
                user_id = ?,
                updated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            emp_data["first_name"],
            emp_data.get("last_name"),
            emp_data["full_name"],
            emp_data.get("gender"),
            emp_data.get("date_of_birth"),
            emp_data.get("mobile_number"),
            emp_data.get("email"),
            emp_data.get("profile_photo"),
            emp_data.get("joining_date"),
            emp_data.get("department"),
            emp_data.get("designation"),
            emp_data.get("reporting_manager"),
            emp_data.get("employment_type", "Full-Time"),
            emp_data.get("status", "Active"),
            emp_data.get("current_address"),
            emp_data.get("permanent_address"),
            emp_data.get("aadhaar_number"),
            emp_data.get("pan_number"),
            emp_data.get("user_id"),
            emp_data.get("updated_by"),
            emp_id
        ))

        # Bank details upsert
        if bank_data:
            cursor.execute("SELECT id FROM employee_bank_details WHERE employee_id = ?", (emp_id,))
            existing_bank = cursor.fetchone()
            if existing_bank:
                cursor.execute("""
                    UPDATE employee_bank_details SET
                        bank_name = ?, account_holder_name = ?, account_number = ?,
                        ifsc_code = ?, branch_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE employee_id = ?
                """, (
                    bank_data.get("bank_name"), bank_data.get("account_holder_name"),
                    bank_data.get("account_number"), bank_data.get("ifsc_code"),
                    bank_data.get("branch_name"), emp_id
                ))
            elif any(bank_data.values()):
                cursor.execute("""
                    INSERT INTO employee_bank_details (
                        employee_id, bank_name, account_holder_name, account_number, ifsc_code, branch_name
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    emp_id, bank_data.get("bank_name"), bank_data.get("account_holder_name"),
                    bank_data.get("account_number"), bank_data.get("ifsc_code"), bank_data.get("branch_name")
                ))

        # Emergency contacts replace
        if emergency_contacts is not None:
            cursor.execute("DELETE FROM employee_emergency_contacts WHERE employee_id = ?", (emp_id,))
            for contact in emergency_contacts:
                if contact.get("contact_name") or contact.get("mobile_number"):
                    cursor.execute("""
                        INSERT INTO employee_emergency_contacts (
                            employee_id, contact_name, relationship, mobile_number
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        emp_id, contact.get("contact_name"),
                        contact.get("relationship"), contact.get("mobile_number")
                    ))

        # Update user employee link if changed
        if emp_data.get("user_id"):
            cursor.execute("SELECT employee_code FROM employees WHERE id = ?", (emp_id,))
            code_row = cursor.fetchone()
            if code_row:
                cursor.execute("UPDATE users SET employee_id = ? WHERE id = ?", (code_row[0], emp_data["user_id"]))

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


def toggle_employee_status(emp_id, new_status, updated_by=None, conn=None):
    close_conn = False
    if not conn:
        conn = get_connection()
        close_conn = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE employees SET status = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, updated_by, emp_id))
        if close_conn:
            conn.commit()
        return True
    finally:
        if close_conn:
            conn.close()


def get_distinct_filter_options():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
        departments = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT designation FROM employees WHERE designation IS NOT NULL AND designation != '' ORDER BY designation")
        designations = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT employment_type FROM employees WHERE employment_type IS NOT NULL AND employment_type != '' ORDER BY employment_type")
        employment_types = [r[0] for r in cursor.fetchall()]

        return {
            "departments": departments,
            "designations": designations,
            "employment_types": employment_types
        }
    finally:
        conn.close()


def get_available_users(current_linked_user_id=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if current_linked_user_id:
            cursor.execute("""
                SELECT id, username, full_name, erp_role FROM users
                WHERE (id NOT IN (SELECT user_id FROM employees WHERE user_id IS NOT NULL AND id != ?) 
                       OR id = ?)
                  AND status != 'ARCHIVED'
                ORDER BY username
            """, (current_linked_user_id, current_linked_user_id))
        else:
            cursor.execute("""
                SELECT id, username, full_name, erp_role FROM users
                WHERE id NOT IN (SELECT user_id FROM employees WHERE user_id IS NOT NULL)
                  AND status != 'ARCHIVED'
                ORDER BY username
            """)
        rows = cursor.fetchall()
        return [_row_to_dict(cursor, r) for r in rows]
    finally:
        conn.close()
