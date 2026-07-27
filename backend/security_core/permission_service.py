from database import get_connection

def has_permission(role_code, module_name, permission_code):
    """
    Checks if a role has the specified permission on a module.
    """
    # ADMIN role always has all permissions
    if role_code == "ADMIN":
        return True
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 
            FROM erp_role_permissions rp
            JOIN erp_permissions p ON rp.permission_code = p.permission_code
            WHERE rp.role_code = ? AND p.module_name = ? AND rp.permission_code = ?
        """, (role_code, module_name, permission_code))
        return cursor.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()

def get_role_permissions(role_code):
    """
    Returns list of permission codes assigned to a role.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT permission_code FROM erp_role_permissions WHERE role_code = ?", (role_code,))
        return [r[0] for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def assign_permission(role_code, permission_code):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO erp_role_permissions (role_code, permission_code)
            VALUES (?, ?)
            ON CONFLICT(role_code, permission_code) DO NOTHING
        """, (role_code, permission_code))
        conn.commit()
    finally:
        conn.close()

def revoke_permission(role_code, permission_code):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM erp_role_permissions 
            WHERE role_code = ? AND permission_code = ?
        """, (role_code, permission_code))
        conn.commit()
    finally:
        conn.close()
