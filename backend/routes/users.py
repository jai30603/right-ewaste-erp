from flask import Blueprint, render_template, request, redirect, url_for, session, abort
from database import get_connection
from security_core.decorators import login_required, require_role, require_permission
from security_core import auth_service, permission_service
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning
from werkzeug.security import generate_password_hash

users_bp = Blueprint("users", __name__)

# ── User List (Admin Only) ───────────────────────────────────────────────────

@users_bp.route("/users")
@require_role("ADMIN")
def users_list():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Load all users (except archived)
        cursor.execute("SELECT * FROM users WHERE status != 'ARCHIVED' ORDER BY id DESC")
        desc = [d[0] for d in cursor.description]
        users = [dict(zip(desc, r)) for r in cursor.fetchall()]
        
        # Load roles
        cursor.execute("SELECT * FROM erp_roles WHERE is_active = 1")
        roles = [dict(r) for r in cursor.fetchall()]
        
        # Load online user sessions
        cursor.execute("""
            SELECT user_id, COUNT(*) as session_count 
            FROM user_sessions 
            WHERE is_active = 1 
            GROUP BY user_id
        """)
        online_sessions = {r[0]: r[1] for r in cursor.fetchall()}
        
        return render_template(
            "user/users.html",
            users=users,
            roles=roles,
            online_sessions=online_sessions
        )
    finally:
        conn.close()

@users_bp.route("/users/add", methods=["POST"])
@require_role("ADMIN")
def add_user():
    username = request.form.get("username", "").strip()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    erp_role = request.form.get("erp_role", "VIEWER")
    emp_id = request.form.get("employee_id", "").strip()
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()

    if not username or not full_name or not password:
        flash_error("Username, Full Name, and Password are required.")
        return redirect(url_for("users.users_list"))

    conn = get_connection()
    try:
        cursor = conn.cursor()
        p_hash = generate_password_hash(password)
        import uuid as uuid_gen
        u_uuid = str(uuid_gen.uuid4())
        cursor.execute("""
            INSERT INTO users (employee_id, full_name, username, email, phone, password_hash, erp_role, department, designation, status, uuid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
        """, (emp_id or None, full_name, username, email or None, phone or None, p_hash, erp_role, department or None, designation or None, u_uuid))
        
        user_id = cursor.lastrowid
        # Seed initial password history
        cursor.execute("INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)", (user_id, p_hash))
        
        # Log activity
        from repositories.activity_log_repository import log_activity
        log_activity(session["user"]["username"], "User Created", f"Created user {username}", module="Security", conn=conn)
        
        conn.commit()

        # Auto-provision personal storage workspace (EDMS Phase 1)
        try:
            from backend.modules.documents.services.mydrive_service import MyDriveService
            MyDriveService().provision_user_storage(user_id)
        except Exception as prov_err:
            print(f"Auto-provisioning failed for user {user_id}: {prov_err}")

        flash_success(f"User '{username}' created successfully.")
    except Exception as e:
        flash_error(f"Failed to create user: {e}")
    finally:
        conn.close()
        
    return redirect(url_for("users.users_list"))

@users_bp.route("/users/edit/<int:user_id>", methods=["POST"])
@require_role("ADMIN")
def edit_user(user_id):
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    erp_role = request.form.get("erp_role", "VIEWER")
    status = request.form.get("status", "ACTIVE")
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()

    if not full_name:
        flash_error("Full Name is required.")
        return redirect(url_for("users.users_list"))

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET full_name = ?, email = ?, phone = ?, erp_role = ?, status = ?, department = ?, designation = ?, updated_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (full_name, email or None, phone or None, erp_role, status, department or None, designation or None, user_id))
        
        # Log activity
        from repositories.activity_log_repository import log_activity
        log_activity(session["user"]["username"], "User Updated", f"Updated user ID {user_id}", module="Security", conn=conn)
        
        conn.commit()
        flash_success("User details updated successfully.")
    except Exception as e:
        flash_error(f"Failed to update user: {e}")
    finally:
        conn.close()
        
    return redirect(url_for("users.users_list"))

@users_bp.route("/users/lock/<int:user_id>", methods=["POST"])
@require_role("ADMIN")
def lock_toggle(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username, status FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            flash_error("User not found.")
            return redirect(url_for("users.users_list"))
            
        username, current_status = row
        new_status = "LOCKED" if current_status == "ACTIVE" else "ACTIVE"
        cursor.execute("UPDATE users SET status = ?, failed_login_attempts = 0 WHERE id = ?", (new_status, user_id))
        
        # Log activity
        from repositories.activity_log_repository import log_activity
        action = "User Locked" if new_status == "LOCKED" else "User Unlocked"
        log_activity(session["user"]["username"], action, f"{action} user {username}", module="Security", conn=conn)
        
        conn.commit()
        flash_success(f"User '{username}' status updated to {new_status}.")
    except Exception as e:
        flash_error(f"Error toggling lock state: {e}")
    finally:
        conn.close()
    return redirect(url_for("users.users_list"))

@users_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@require_role("ADMIN")
def delete_user(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Soft delete: set status to ARCHIVED
        cursor.execute("UPDATE users SET status = 'ARCHIVED' WHERE id = ?", (user_id,))
        
        # Terminate active sessions
        cursor.execute("UPDATE user_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        
        # Log activity
        from repositories.activity_log_repository import log_activity
        log_activity(session["user"]["username"], "User Archived", f"Archived user ID {user_id}", module="Security", conn=conn)
        
        conn.commit()
        flash_warning("User archived successfully (Soft Deleted).")
    except Exception as e:
        flash_error(f"Failed to archive user: {e}")
    finally:
        conn.close()
    return redirect(url_for("users.users_list"))

# ── User Profile (Log-in Required) ───────────────────────────────────────────

@users_bp.route("/profile")
@login_required
def profile():
    user_id = session["user"]["user_id"]
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        desc = [d[0] for d in cursor.description]
        user_row = cursor.fetchone()
        user = dict(zip(desc, user_row))
        
        # Get active sessions
        cursor.execute("""
            SELECT * FROM user_sessions 
            WHERE user_id = ? AND is_active = 1 
            ORDER BY last_activity DESC
        """, (user_id,))
        desc_sess = [d[0] for d in cursor.description]
        sessions = [dict(zip(desc_sess, r)) for r in cursor.fetchall()]
        
        # Get login history (last 10 entries)
        cursor.execute("""
            SELECT * FROM login_history 
            WHERE user_id = ? 
            ORDER BY login_time DESC 
            LIMIT 10
        """, (user_id,))
        desc_hist = [d[0] for d in cursor.description]
        login_history = [dict(zip(desc_hist, r)) for r in cursor.fetchall()]
        
        # Get user preferences
        cursor.execute("SELECT preference_key, preference_value FROM user_preferences WHERE user_id = ?", (user_id,))
        prefs = {r[0]: r[1] for r in cursor.fetchall()}
        
        return render_template(
            "user/profile.html",
            user=user,
            sessions=sessions,
            login_history=login_history,
            preferences=prefs
        )
    finally:
        conn.close()

@users_bp.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    user_id = session["user"]["user_id"]
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    theme = request.form.get("theme", "light")
    timezone = request.form.get("timezone", "UTC")

    if not full_name:
        flash_error("Full name is required.")
        return redirect(url_for("users.profile"))

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET full_name = ?, email = ?, phone = ?, updated_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (full_name, email or None, phone or None, user_id))
        
        # Update user preferences
        cursor.execute("""
            INSERT INTO user_preferences (user_id, preference_key, preference_value)
            VALUES (?, 'theme', ?)
            ON CONFLICT(user_id, preference_key) DO UPDATE SET preference_value = excluded.preference_value
        """, (user_id, theme))
        cursor.execute("""
            INSERT INTO user_preferences (user_id, preference_key, preference_value)
            VALUES (?, 'timezone', ?)
            ON CONFLICT(user_id, preference_key) DO UPDATE SET preference_value = excluded.preference_value
        """, (user_id, timezone))
        
        conn.commit()
        flash_success("Profile updated successfully.")
    except Exception as e:
        flash_error(f"Failed to update profile: {e}")
    finally:
        conn.close()
        
    return redirect(url_for("users.profile"))

@users_bp.route("/profile/password", methods=["POST"])
@login_required
def update_password():
    user_id = session["user"]["user_id"]
    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not old_password or not new_password or not confirm_password:
        flash_error("All password fields are required.")
        return redirect(url_for("users.profile"))

    if new_password != confirm_password:
        flash_error("New password and confirm password do not match.")
        return redirect(url_for("users.profile"))

    error = auth_service.change_password(user_id, old_password, new_password, session["user"]["username"])
    if error:
        flash_error(error)
    else:
        flash_success("Password changed successfully.")
        
    return redirect(url_for("users.profile"))

@users_bp.route("/profile/session/revoke/<session_token>", methods=["POST"])
@login_required
def revoke_session(session_token):
    user_id = session["user"]["user_id"]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Ensure session belongs to user
        cursor.execute("SELECT 1 FROM user_sessions WHERE session_token = ? AND user_id = ?", (session_token, user_id))
        if cursor.fetchone():
            cursor.execute("UPDATE user_sessions SET is_active = 0 WHERE session_token = ?", (session_token,))
            conn.commit()
            flash_success("Session terminated successfully.")
        else:
            flash_error("Session not found or unauthorized.")
    except Exception as e:
        flash_error(f"Error terminating session: {e}")
    finally:
        conn.close()
    return redirect(url_for("users.profile"))

# ── Role Permissions Matrix (Admin Only) ─────────────────────────────────────

@users_bp.route("/users/permissions")
@require_role("ADMIN")
def permissions_matrix():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Load all roles
        cursor.execute("SELECT role_code, role_name FROM erp_roles WHERE is_active = 1")
        roles = [dict(r) for r in cursor.fetchall()]
        
        # Load all permissions grouped by module
        cursor.execute("SELECT * FROM erp_permissions ORDER BY module_name, permission_code")
        desc = [d[0] for d in cursor.description]
        permissions = [dict(zip(desc, r)) for r in cursor.fetchall()]
        
        # Load existing role permissions mapping
        cursor.execute("SELECT role_code, permission_code FROM erp_role_permissions")
        mapping_rows = cursor.fetchall()
        
        # Build mapping dict
        mapping = {}
        for role_code, perm_code in mapping_rows:
            if role_code not in mapping:
                mapping[role_code] = set()
            mapping[role_code].add(perm_code)
            
        return render_template(
            "user/permissions.html",
            roles=roles,
            permissions=permissions,
            mapping=mapping
        )
    finally:
        conn.close()

@users_bp.route("/users/permissions/update", methods=["POST"])
@require_role("ADMIN")
def update_permissions():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        # Clear existing role permissions mappings except for ADMIN role (ADMIN is absolute)
        cursor.execute("DELETE FROM erp_role_permissions WHERE role_code != 'ADMIN'")
        
        # Retrieve all checked role permissions from form
        # Form inputs should be named like `role_permissions[ROLE_CODE][PERMISSION_CODE]`
        for key in request.form:
            if key.startswith("perm_"):
                # key format: perm_ROLECODE_PERMISSIONCODE
                parts = key.split("_", 2)
                if len(parts) == 3:
                    role_code = parts[1]
                    perm_code = parts[2]
                    cursor.execute("""
                        INSERT INTO erp_role_permissions (role_code, permission_code)
                        VALUES (?, ?)
                        ON CONFLICT(role_code, permission_code) DO NOTHING
                    """, (role_code, perm_code))
                    
        # Log activity
        from repositories.activity_log_repository import log_activity
        log_activity(session["user"]["username"], "Permissions Updated", "Updated Role-Based Access Control matrix mappings.", module="Security", conn=conn)
        
        conn.commit()
        flash_success("Permissions matrix updated successfully.")
    except Exception as e:
        conn.rollback()
        flash_error(f"Failed to update permissions: {e}")
    finally:
        conn.close()
    return redirect(url_for("users.permissions_matrix"))
