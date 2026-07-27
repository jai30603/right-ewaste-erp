import sqlite3
import html
import re
import json
import time
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, session, abort, redirect, url_for
from database import get_connection
from security import get_csrf_token

try:
    from erp_platform.notifications.notification_service import send_notification
except ImportError:
    try:
        from backend.erp_platform.notifications.notification_service import send_notification
    except ImportError:
        def send_notification(*args, **kwargs):
            pass

communication_bp = Blueprint("communication", __name__)

# ── Dynamic Module & Resource Registration Engine ───────────────────────────

class ModuleRegistryManager:
    @staticmethod
    def register_module(name, icon, config=None):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO module_registry (module_name, module_icon, config_json)
                VALUES (?, ?, ?)
                ON CONFLICT(module_name) DO UPDATE SET module_icon = ?, config_json = ?
            """, (name, icon, json.dumps(config or {}), icon, json.dumps(config or {})))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    def register_resource_type(rtype, source_module, config=None):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO resource_registry (resource_type, source_module, config_json)
                VALUES (?, ?, ?)
                ON CONFLICT(resource_type) DO UPDATE SET source_module = ?, config_json = ?
            """, (rtype, source_module, json.dumps(config or {}), source_module, json.dumps(config or {})))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

def get_current_user_id():
    """Helper to get current logged in user ID, defaulting to 1 for admin fallback."""
    if "user" in session and isinstance(session["user"], dict):
        return session["user"].get("user_id", 1)
    return 1

def determine_online_status(last_activity_str, is_active):
    """Determine user online status based on last activity and session active state."""
    if not is_active or not last_activity_str:
        return "Offline"
    try:
        last_act = datetime.strptime(last_activity_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
        diff = datetime.utcnow() - last_act
        if diff < timedelta(minutes=5):
            return "Online"
        elif diff < timedelta(minutes=15):
            return "Away"
        else:
            return "Offline"
    except Exception:
        return "Online" if is_active else "Offline"

def get_global_unread_count():
    """Context processor helper to get global unread count for current user across direct & group conversations."""
    user_id = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM messages m
            JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
            WHERE cp.user_id = ? AND m.sender_id != ?
              AND cp.status = 'ACTIVE'
              AND m.id > COALESCE(cp.last_read_message_id, 0)
        """, (user_id, user_id))
        return cursor.fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()

def validate_edms_document_access(doc_id, user_id):
    """EDMS Permission Validation Engine. Single source of truth for file authorization."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Query document folder type, owner, and classification
        cursor.execute("""
            SELECT d.owner_user_id, f.folder_type, d.classification
            FROM documents d
            LEFT JOIN folders f ON d.folder_id = f.id
            WHERE d.id = ?
        """, (int(doc_id),))
        doc = cursor.fetchone()
        if not doc:
            return False
            
        owner_id, folder_type, classification = doc
        
        # 1. Document Owner always has access
        if owner_id == user_id:
            return True
            
        # 2. Super Admin always has full access
        cursor.execute("SELECT erp_role FROM users WHERE id = ?", (user_id,))
        urow = cursor.fetchone()
        if urow and urow[0] == 'ADMIN':
            return True

        # 3. Explicit Document Shares
        cursor.execute("""
            SELECT id FROM document_shares 
            WHERE document_id = ? AND shared_with_user_id = ? AND is_revoked = 0
        """, (int(doc_id), user_id))
        if cursor.fetchone():
            return True

        # 4. Company Drive Folders (Visible to active employees if classification is INTERNAL or PUBLIC)
        if folder_type == 'COMPANY' and classification in ('INTERNAL', 'PUBLIC'):
            return True

        return False
    except Exception:
        return False
    finally:
        conn.close()

# ── Rate Limiter Implementation ──────────────────────────────────────────────

RATE_LIMIT_TIMESTAMPS = {} # user_id -> list of unix timestamps

def check_rate_limit(user_id):
    """Allow maximum 60 messages per user per minute in production."""
    now = time.time()
    if user_id not in RATE_LIMIT_TIMESTAMPS:
        RATE_LIMIT_TIMESTAMPS[user_id] = []
    # Retain only timestamps from the last 60 seconds
    RATE_LIMIT_TIMESTAMPS[user_id] = [t for t in RATE_LIMIT_TIMESTAMPS[user_id] if now - t < 60]
    if len(RATE_LIMIT_TIMESTAMPS[user_id]) >= 60:
        return False
    RATE_LIMIT_TIMESTAMPS[user_id].append(now)
    return True

# ── Web UI Route ─────────────────────────────────────────────────────────────

@communication_bp.route("/communication", methods=["GET"])
def communication_page():
    return render_template("communication/chat.html")

# ── Module Registration API ──────────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/modules/register", methods=["POST"])
def register_module_api():
    """Register or update an ERP module dynamically with the framework."""
    data = request.get_json() or {}
    name = data.get("module_name", "").strip()
    icon = data.get("module_icon", "").strip()
    config = data.get("config", {})

    if not name or not icon:
        return jsonify({"success": False, "error": "module_name and module_icon are required"}), 400

    ok = ModuleRegistryManager.register_module(name, icon, config)
    if ok:
        return jsonify({"success": True, "message": f"Module '{name}' registered successfully."}), 201
    return jsonify({"success": False, "error": "Registration failed"}), 500

@communication_bp.route("/api/v1/communication/resources/register", methods=["POST"])
def register_resource_type_api():
    """Register or update a resource type dynamically with the framework."""
    data = request.get_json() or {}
    rtype = data.get("resource_type", "").strip().upper()
    source_module = data.get("source_module", "").strip()
    config = data.get("config", {})

    if not rtype or not source_module:
        return jsonify({"success": False, "error": "resource_type and source_module are required"}), 400

    ok = ModuleRegistryManager.register_resource_type(rtype, source_module, config)
    if ok:
        return jsonify({"success": True, "message": f"Resource type '{rtype}' registered."}), 201
    return jsonify({"success": False, "error": "Registration failed"}), 500

# ── REST API Endpoints ────────────────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/users", methods=["GET"])
def discover_users():
    """Fetch all active users from database for user discovery, excluding current user."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.full_name, u.email, u.department, u.designation,
                   us.last_activity, us.is_active
            FROM users u
            LEFT JOIN (
                SELECT user_id, MAX(last_activity) as last_activity, MAX(is_active) as is_active
                FROM user_sessions
                GROUP BY user_id
            ) us ON u.id = us.user_id
            WHERE u.status = 'ACTIVE' AND u.id != ?
            ORDER BY u.full_name ASC
        """, (current_uid,))
        
        users_list = []
        for row in cursor.fetchall():
            status = determine_online_status(row[6], row[7])
            users_list.append({
                "id": row[0],
                "username": row[1],
                "full_name": row[2],
                "email": row[3],
                "department": row[4],
                "designation": row[5],
                "status": status
            })
        return jsonify({"success": True, "users": users_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations", methods=["GET"])
def get_conversations():
    """Fetch all active conversations (direct & group) for current user."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.id, c.type, c.name, c.description, c.created_by, c.status as group_status,
                   c.updated_at, cp.is_pinned, cp.last_read_message_id, c.owner_id
            FROM conversations c
            JOIN conversation_participants cp ON c.id = cp.conversation_id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND c.status != 'DELETED'
            ORDER BY cp.is_pinned DESC, c.updated_at DESC
        """, (current_uid,))
        
        convs = []
        for row in cursor.fetchall():
            conv_id = row[0]
            ctype = row[1]
            gname = row[2]
            gdesc = row[3]
            gcreated_by = row[4]
            gstatus = row[5]
            updated_at = row[6]
            is_pinned = row[7]
            last_read_id = row[8] or 0
            owner_id = row[9] or 1

            other_user = None
            member_count = 0

            if ctype == 'GROUP':
                cursor.execute("""
                    SELECT COUNT(*) FROM conversation_participants 
                    WHERE conversation_id = ? AND status = 'ACTIVE'
                """, (conv_id,))
                member_count = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    SELECT u.id, u.full_name, u.username, u.department, u.designation, u.email,
                           us.last_activity, us.is_active
                    FROM conversation_participants cp
                    JOIN users u ON cp.user_id = u.id
                    LEFT JOIN (
                        SELECT user_id, MAX(last_activity) as last_activity, MAX(is_active) as is_active
                        FROM user_sessions
                        GROUP BY user_id
                    ) us ON u.id = us.user_id
                    WHERE cp.conversation_id = ? AND cp.user_id != ?
                """, (conv_id, current_uid))
                ou = cursor.fetchone()
                if ou:
                    status = determine_online_status(ou[6], ou[7])
                    other_user = {
                        "id": ou[0],
                        "full_name": ou[1],
                        "username": ou[2],
                        "department": ou[3],
                        "designation": ou[4],
                        "email": ou[5],
                        "status": status
                    }
                else:
                    continue

            # Get last message
            cursor.execute("""
                SELECT m.id, m.content, m.sender_id, m.created_at, m.status, u.full_name
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.conversation_id = ?
                ORDER BY m.id DESC LIMIT 1
            """, (conv_id,))
            last_msg_row = cursor.fetchone()
            
            last_msg = None
            if last_msg_row:
                last_msg_content = last_msg_row[1] if last_msg_row[4] != 'DELETED' else "This message was deleted"
                last_msg = {
                    "id": last_msg_row[0],
                    "content": last_msg_content,
                    "sender_id": last_msg_row[2],
                    "created_at": last_msg_row[3],
                    "status": last_msg_row[4],
                    "sender_name": last_msg_row[5]
                }

            # Unread messages count
            cursor.execute("""
                SELECT COUNT(*) FROM messages 
                WHERE conversation_id = ? AND sender_id != ? AND id > ?
            """, (conv_id, current_uid, last_read_id))
            unread_count = cursor.fetchone()[0]

            convs.append({
                "id": conv_id,
                "type": ctype,
                "name": gname if ctype == 'GROUP' else (other_user["full_name"] if other_user else ""),
                "description": gdesc,
                "created_by": gcreated_by,
                "owner_id": owner_id,
                "group_status": gstatus,
                "updated_at": updated_at,
                "is_pinned": bool(is_pinned),
                "unread_count": unread_count,
                "last_message": last_msg,
                "other_user": other_user,
                "member_count": member_count
            })
        return jsonify({"success": True, "conversations": convs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Generic Resource Reference Engine & Deep Linking ─────────────────────────

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/share-resource-v2", methods=["POST"])
def share_resource_v2(conv_id):
    """Share any registered ERP resource in the conversation through the Generic Engine."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    rtype = data.get("resource_type", "").upper()
    resource_id = data.get("resource_id")
    display_title = data.get("display_title", "").strip()
    subtitle = data.get("subtitle", "").strip()
    preview_metadata = data.get("preview_metadata", {})
    deep_link = data.get("deep_link", "").strip()

    if not rtype or not display_title or not deep_link:
        return jsonify({"success": False, "error": "resource_type, display_title, and deep_link are required"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Verify participation
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        # Insert message wrapper (stores system alert for resources)
        msg_content = f"Shared resource: {display_title}"
        cursor.execute("""
            INSERT INTO messages (conversation_id, sender_id, content, status)
            VALUES (?, ?, ?, 'ACTIVE')
        """, (conv_id, current_uid, msg_content))
        message_id = cursor.lastrowid

        # Insert record in central shared_resources catalog
        cursor.execute("""
            INSERT INTO shared_resources (message_id, resource_type, resource_id, display_title, subtitle, preview_metadata, deep_link, shared_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (message_id, rtype, str(resource_id), display_title, subtitle, json.dumps(preview_metadata), deep_link, current_uid))
        shared_ref_id = cursor.lastrowid

        # Populate legacy Phase 3 tables to maintain absolute backward compatibility
        if rtype == 'DOCUMENT' and resource_id:
            cursor.execute("""
                INSERT INTO resource_references (message_id, resource_type, resource_id)
                VALUES (?, 'DOCUMENT', ?)
            """, (message_id, str(resource_id)))
            cursor.execute("""
                INSERT INTO document_references (message_id, document_id)
                VALUES (?, ?)
            """, (message_id, int(resource_id)))

            # Populate Phase 3 tables
            cursor.execute("""
                INSERT INTO chat_file_reference (document_id, message_id, conversation_id, sender_id)
                VALUES (?, ?, ?, ?)
            """, (int(resource_id), message_id, conv_id, current_uid))
            cursor.execute("""
                INSERT INTO conversation_attachment (conversation_id, message_id, document_id)
                VALUES (?, ?, ?)
            """, (conv_id, message_id, int(resource_id)))
            cursor.execute("SELECT repository_id, extension, size_bytes FROM documents WHERE id = ?", (int(resource_id),))
            doc_row = cursor.fetchone()
            repo_id = doc_row['repository_id'] if doc_row else 1
            file_ext = doc_row['extension'] if doc_row else ""
            fsize = doc_row['size_bytes'] if doc_row else 0
            cursor.execute("""
                INSERT INTO attachment_metadata (document_id, original_repository_id, file_type, file_size, sender_id)
                VALUES (?, ?, ?, ?, ?)
            """, (int(resource_id), repo_id, file_ext, fsize, current_uid))
        elif rtype == 'TASK' and resource_id:
            cursor.execute("""
                INSERT INTO resource_references (message_id, resource_type, resource_id)
                VALUES (?, 'TASK', ?)
            """, (message_id, str(resource_id)))
            cursor.execute("""
                INSERT INTO task_references (message_id, task_id, title, assignee)
                VALUES (?, ?, ?, ?)
            """, (message_id, int(resource_id), display_title, subtitle))
        elif rtype == 'LOCATION':
            cursor.execute("""
                INSERT INTO resource_references (message_id, resource_type, resource_id)
                VALUES (?, 'LOCATION', NULL)
            """, (message_id,))
            lat = preview_metadata.get("latitude", 0.0)
            lng = preview_metadata.get("longitude", 0.0)
            cursor.execute("""
                INSERT INTO location_references (message_id, latitude, longitude, address)
                VALUES (?, ?, ?, ?)
            """, (message_id, lat, lng, display_title))

        # Log event in Platform activity log
        from repositories.activity_log_repository import log_activity
        cursor.execute("SELECT username, full_name FROM users WHERE id = ?", (current_uid,))
        urow = cursor.fetchone()
        log_activity(urow[0] if urow else "System", "Resource Shared", f"Shared {rtype} '{display_title}'", module="Communication", conn=conn)

        # Notify participants
        cursor.execute("""
            SELECT u.username FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.conversation_id = ? AND cp.user_id != ? AND cp.status = 'ACTIVE'
        """, (conv_id, current_uid))
        for u in cursor.fetchall():
            send_notification(
                user_name=u[0],
                title="Resource Shared",
                message=f"{urow[1] if urow else 'Someone'} shared a {rtype.lower()} with you.",
                notification_type='INFO',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )

        conn.commit()
        return jsonify({
            "success": True, 
            "message_id": message_id, 
            "shared_resource_id": shared_ref_id,
            "message": "Resource reference registered & shared successfully."
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/share-resource", methods=["POST"])
def share_resource_legacy(conv_id):
    """Legacy Phase 3 resource sharing API (for backward compatibility)."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    rtype = data.get("resource_type", "").upper()
    
    display_title = "Shared Resource"
    subtitle = "ERP Module"
    resource_id = None
    deep_link = "#"
    preview_metadata = {}

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Verify participation
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        if rtype == 'DOCUMENT':
            resource_id = data.get("document_id")
            # Fetch doc name
            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (int(resource_id),))
            doc_row = cursor.fetchone()
            display_title = doc_row[0] if doc_row else "EDMS Document"
            subtitle = "EDMS Module"
            deep_link = f"/api/v1/documents/{resource_id}/download"
        elif rtype == 'TASK':
            resource_id = data.get("task_id")
            # Fetch task title
            cursor.execute("SELECT title, assignee_name FROM tasks WHERE id = ?", (int(resource_id),))
            task_row = cursor.fetchone()
            display_title = task_row[0] if task_row else f"Task #{resource_id}"
            subtitle = f"Assignee: {task_row[1]}" if task_row and task_row[1] else "ERP Task"
            deep_link = f"/tasks/view/{resource_id}"
        elif rtype == 'LOCATION':
            display_title = data.get("address", "Shared Location")
            subtitle = "Google Maps"
            preview_metadata = {
                "latitude": data.get("latitude", 0.0),
                "longitude": data.get("longitude", 0.0)
            }
            deep_link = f"https://www.google.com/maps/search/?api=1&query={data.get('latitude')},{data.get('longitude')}"
            
        cursor.close()
    finally:
        conn.close()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        msg_content = f"Shared resource: {display_title}"
        cursor.execute("""
            INSERT INTO messages (conversation_id, sender_id, content, status)
            VALUES (?, ?, ?, 'ACTIVE')
        """, (conv_id, current_uid, msg_content))
        message_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO shared_resources (message_id, resource_type, resource_id, display_title, subtitle, preview_metadata, deep_link, shared_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (message_id, rtype, str(resource_id) if resource_id else None, display_title, subtitle, json.dumps(preview_metadata), deep_link, current_uid))
        shared_ref_id = cursor.lastrowid

        # Insert to legacy reference tables for Phase 3 checks
        if rtype == 'DOCUMENT':
            cursor.execute("""
                INSERT INTO resource_references (message_id, resource_type, resource_id)
                VALUES (?, 'DOCUMENT', ?)
            """, (message_id, str(resource_id)))
            cursor.execute("""
                INSERT INTO document_references (message_id, document_id)
                VALUES (?, ?)
            """, (message_id, int(resource_id)))

            # Populate Phase 3 tables
            cursor.execute("""
                INSERT INTO chat_file_reference (document_id, message_id, conversation_id, sender_id)
                VALUES (?, ?, ?, ?)
            """, (int(resource_id), message_id, conv_id, current_uid))
            cursor.execute("""
                INSERT INTO conversation_attachment (conversation_id, message_id, document_id)
                VALUES (?, ?, ?)
            """, (conv_id, message_id, int(resource_id)))
            cursor.execute("SELECT repository_id, extension, size_bytes FROM documents WHERE id = ?", (int(resource_id),))
            doc_row = cursor.fetchone()
            repo_id = doc_row['repository_id'] if doc_row else 1
            file_ext = doc_row['extension'] if doc_row else ""
            fsize = doc_row['size_bytes'] if doc_row else 0
            cursor.execute("""
                INSERT INTO attachment_metadata (document_id, original_repository_id, file_type, file_size, sender_id)
                VALUES (?, ?, ?, ?, ?)
            """, (int(resource_id), repo_id, file_ext, fsize, current_uid))
        elif rtype == 'TASK':
            cursor.execute("""
                INSERT INTO resource_references (message_id, resource_type, resource_id)
                VALUES (?, 'TASK', ?)
            """, (message_id, str(resource_id)))
            cursor.execute("""
                INSERT INTO task_references (message_id, task_id, title, assignee)
                VALUES (?, ?, ?, ?)
            """, (message_id, int(resource_id), display_title, subtitle))
        elif rtype == 'LOCATION':
            cursor.execute("""
                INSERT INTO resource_references (message_id, resource_type, resource_id)
                VALUES (?, 'LOCATION', NULL)
            """, (message_id,))
            cursor.execute("""
                INSERT INTO location_references (message_id, latitude, longitude, address)
                VALUES (?, ?, ?, ?)
            """, (message_id, preview_metadata["latitude"], preview_metadata["longitude"], display_title))

        # Log & Notify
        from repositories.activity_log_repository import log_activity
        cursor.execute("SELECT username, full_name FROM users WHERE id = ?", (current_uid,))
        urow = cursor.fetchone()
        log_activity(urow[0] if urow else "System", "Resource Shared", f"Shared {rtype} '{display_title}'", module="Communication", conn=conn)

        # Notify participants
        cursor.execute("""
            SELECT u.username FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.conversation_id = ? AND cp.user_id != ? AND cp.status = 'ACTIVE'
        """, (conv_id, current_uid))
        for u in cursor.fetchall():
            send_notification(
                user_name=u[0],
                title="Resource Shared",
                message=f"{urow[1] if urow else 'Someone'} shared a {rtype.lower()} with you.",
                notification_type='INFO',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )

        conn.commit()
        return jsonify({
            "success": True, 
            "message_id": message_id, 
            "shared_resource_id": shared_ref_id,
            "message": "Resource shared successfully."
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/resources/<int:ref_id>/open", methods=["GET"])
def open_shared_resource(ref_id):
    """Deep Linking Permission Evaluator. Verifies access control rules before routing redirect."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT resource_type, resource_id, deep_link FROM shared_resources WHERE id = ?", (ref_id,))
        ref = cursor.fetchone()
        if not ref:
            return jsonify({"success": False, "error": "Shared resource reference not found"}), 404
        
        rtype, resource_id, deep_link = ref

        # Evaluate permissions by resource type
        if rtype == 'DOCUMENT':
            if not validate_edms_document_access(resource_id, current_uid):
                return jsonify({"success": False, "error": "You do not have permission to access this document."}), 403
        elif rtype in ('PURCHASE_ORDER', 'PURCHASE_INVOICE', 'SALES_ORDER', 'SALES_INVOICE'):
            # Restrict billing modules access to ADMIN & OPERATOR roles
            cursor.execute("SELECT erp_role FROM users WHERE id = ?", (current_uid,))
            role = cursor.fetchone()[0]
            if role == 'VIEWER':
                return jsonify({"success": False, "error": "You do not have permission to view billing documents."}), 403
        
        # Grant routing redirect
        return redirect(deep_link)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Shared Resource History History ──────────────────────────────────────────

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/shared-resources-v2", methods=["GET"])
def get_shared_resources_history(conv_id):
    """Retrieve categorized resource reference history for Right Panel tabs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sr.id, sr.resource_type, sr.resource_id, sr.display_title, sr.subtitle, sr.preview_metadata, sr.deep_link, sr.shared_at, u.full_name
            FROM shared_resources sr
            JOIN messages m ON sr.message_id = m.id
            JOIN users u ON sr.shared_by = u.id
            WHERE m.conversation_id = ?
            ORDER BY sr.id DESC
        """, (conv_id,))
        
        resources = []
        for r in cursor.fetchall():
            resources.append({
                "id": r[0],
                "resource_type": r[1],
                "resource_id": r[2],
                "display_title": r[3],
                "subtitle": r[4],
                "preview_metadata": json.loads(r[5] or '{}'),
                "deep_link": r[6],
                "shared_at": r[7],
                "shared_by": r[8]
            })
        return jsonify({"success": True, "resources": resources})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Categorized Advanced Search ──────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/search-advanced", methods=["GET"])
def search_advanced():
    """Search messages, groups, users, and shared ERP resources, returning grouped categories."""
    current_uid = get_current_user_id()
    query = request.args.get("q", default="", type=str).strip()
    if not query:
        return jsonify({"success": True, "messages": [], "groups": [], "users": [], "resources": []})

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Search Messages
        cursor.execute("""
            SELECT m.id, m.conversation_id, m.content, m.created_at, u.full_name, c.name
            FROM messages m
            JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
            JOIN conversations c ON m.conversation_id = c.id
            JOIN users u ON m.sender_id = u.id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND m.status != 'DELETED'
              AND m.content LIKE ?
            ORDER BY m.id DESC LIMIT 15
        """, (current_uid, f"%{query}%"))
        messages = [{
            "id": r[0], "conversation_id": r[1], "content": r[2], "created_at": r[3], "sender_name": r[4], "conversation_name": r[5] or "Direct Message"
        } for r in cursor.fetchall()]

        # 2. Search Groups
        cursor.execute("""
            SELECT c.id, c.name, c.description, c.created_at
            FROM conversations c
            JOIN conversation_participants cp ON c.id = cp.conversation_id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND c.type = 'GROUP'
              AND (c.name LIKE ? OR c.description LIKE ?)
            LIMIT 10
        """, (current_uid, f"%{query}%", f"%{query}%"))
        groups = [{
            "id": r[0], "name": r[1], "description": r[2], "created_at": r[3]
        } for r in cursor.fetchall()]

        # 3. Search ERP Users
        cursor.execute("""
            SELECT u.id, u.full_name, u.username, u.department, u.designation
            FROM users u
            WHERE u.status = 'ACTIVE' AND u.id != ?
              AND (u.full_name LIKE ? OR u.username LIKE ? OR u.department LIKE ?)
            LIMIT 10
        """, (current_uid, f"%{query}%", f"%{query}%", f"%{query}%"))
        users = [{
            "id": r[0], "full_name": r[1], "username": r[2], "department": r[3], "designation": r[4]
        } for r in cursor.fetchall()]

        # 4. Search Shared Resources
        cursor.execute("""
            SELECT sr.id, sr.resource_type, sr.display_title, sr.subtitle, sr.deep_link, sr.shared_at, u.full_name
            FROM shared_resources sr
            JOIN messages m ON sr.message_id = m.id
            JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
            JOIN users u ON sr.shared_by = u.id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE'
              AND (sr.display_title LIKE ? OR sr.subtitle LIKE ?)
            LIMIT 15
        """, (current_uid, f"%{query}%", f"%{query}%"))
        resources = [{
            "id": r[0], "resource_type": r[1], "display_title": r[2], "subtitle": r[3], "deep_link": r[4], "shared_at": r[5], "shared_by": r[6]
        } for r in cursor.fetchall()]

        return jsonify({
            "success": True,
            "messages": messages,
            "groups": groups,
            "users": users,
            "resources": resources
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Dashboard Statistics Widget API updates ─────────────────────────────────

@communication_bp.route("/api/v1/communication/dashboard-stats", methods=["GET"])
def get_dashboard_stats():
    """Retrieve comprehensive communication widget statistics for current user dashboard integration."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Unread messages count
        unread_count = get_global_unread_count()

        # 2. Unread direct messages
        cursor.execute("""
            SELECT COUNT(*) FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
            WHERE cp.user_id = ? AND m.sender_id != ? AND c.type = 'DIRECT'
              AND cp.status = 'ACTIVE' AND m.id > COALESCE(cp.last_read_message_id, 0)
        """, (current_uid, current_uid))
        unread_direct = cursor.fetchone()[0]

        # 3. Unread group messages
        cursor.execute("""
            SELECT COUNT(*) FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
            WHERE cp.user_id = ? AND m.sender_id != ? AND c.type = 'GROUP'
              AND cp.status = 'ACTIVE' AND m.id > COALESCE(cp.last_read_message_id, 0)
        """, (current_uid, current_uid))
        unread_groups = cursor.fetchone()[0]

        # 4. Unread mentions
        cursor.execute("""
            SELECT COUNT(*) FROM mentions m
            JOIN messages msg ON m.message_id = msg.id
            JOIN conversation_participants cp ON msg.conversation_id = cp.conversation_id
            WHERE m.user_id = ? AND cp.user_id = ? AND cp.status = 'ACTIVE'
              AND msg.id > COALESCE(cp.last_read_message_id, 0)
        """, (current_uid, current_uid))
        mentions_count = cursor.fetchone()[0]

        # 5. Recent shared documents (last 24 hours) in user's groups
        day_ago = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT COUNT(*) FROM shared_resources sr
            JOIN messages msg ON sr.message_id = msg.id
            JOIN conversation_participants cp ON msg.conversation_id = cp.conversation_id
            WHERE cp.user_id = ? AND sr.resource_type = 'DOCUMENT'
              AND cp.status = 'ACTIVE' AND sr.shared_at >= ?
        """, (current_uid, day_ago))
        recent_docs_count = cursor.fetchone()[0]

        # 6. Pending shared tasks
        cursor.execute("""
            SELECT COUNT(*) FROM task_references tr
            JOIN messages msg ON tr.message_id = msg.id
            JOIN conversation_participants cp ON msg.conversation_id = cp.conversation_id
            JOIN tasks t ON tr.task_id = t.id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND t.status = 'PENDING'
        """, (current_uid,))
        tasks_count = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "unread_messages": unread_count,
            "unread_direct": unread_direct,
            "unread_groups": unread_groups,
            "mentions": mentions_count,
            "shared_documents": recent_docs_count,
            "pending_tasks": tasks_count
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Pinned Messages Endpoints ────────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/pin-message/<int:msg_id>", methods=["POST"])
def pin_message(conv_id, msg_id):
    """Pin a message inside a group or conversation."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Not authorized"}), 403

        cursor.execute("""
            INSERT OR IGNORE INTO pinned_messages (conversation_id, message_id, pinned_by_user_id)
            VALUES (?, ?, ?)
        """, (conv_id, msg_id, current_uid))

        cursor.execute("SELECT name FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        conv_name = conv_row[0] if conv_row else "Group"
        
        cursor.execute("SELECT full_name FROM users WHERE id = ?", (current_uid,))
        pinner_name = cursor.fetchone()[0]

        cursor.execute("""
            SELECT u.username FROM conversation_participants cp 
            JOIN users u ON cp.user_id = u.id 
            WHERE cp.conversation_id = ? AND cp.user_id != ? AND cp.status = 'ACTIVE'
        """, (conv_id, current_uid))
        
        for u in cursor.fetchall():
            send_notification(
                user_name=u[0],
                title="New Pinned Message",
                message=f"{pinner_name} pinned a new message in '{conv_name}'.",
                notification_type='INFO',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )

        # Log event in activity audit
        from repositories.activity_log_repository import log_activity
        log_activity(pinner_name, "Message Pinned", f"Pinned message #{msg_id} in conversation #{conv_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Message pinned successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/pin-message/<int:msg_id>", methods=["DELETE"])
def unpin_message(conv_id, msg_id):
    """Unpin a message."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Not authorized"}), 403

        cursor.execute("""
            DELETE FROM pinned_messages 
            WHERE conversation_id = ? AND message_id = ?
        """, (conv_id, msg_id))
        
        conn.commit()
        return jsonify({"success": True, "message": "Message unpinned."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/pinned-messages", methods=["GET"])
def get_pinned_messages(conv_id):
    """Fetch all pinned messages for a conversation."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pm.message_id, pm.pinned_at, m.content, m.sender_id, u.full_name 
            FROM pinned_messages pm
            JOIN messages m ON pm.message_id = m.id
            JOIN users u ON m.sender_id = u.id
            WHERE pm.conversation_id = ? AND m.status != 'DELETED'
            ORDER BY pm.id DESC
        """, (conv_id,))
        
        pinned = []
        for r in cursor.fetchall():
            pinned.append({
                "message_id": r[0],
                "pinned_at": r[1],
                "content": r[2],
                "sender_id": r[3],
                "sender_name": r[4]
            })
        return jsonify({"success": True, "pinned_messages": pinned})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Message Seen By Readers ──────────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/messages/<int:msg_id>/seen", methods=["GET"])
def get_message_seen_by(msg_id):
    """Fetch list of ERP user full names who have seen this message."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT conversation_id, sender_id FROM messages WHERE id = ?", (msg_id,))
        m_row = cursor.fetchone()
        if not m_row:
            return jsonify({"success": False, "error": "Message not found"}), 404
        conv_id, sender_id = m_row

        cursor.execute("""
            SELECT u.full_name FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.conversation_id = ? AND cp.last_read_message_id >= ? AND cp.user_id != ?
              AND cp.status = 'ACTIVE'
        """, (conv_id, msg_id, sender_id))
        
        seen_users = [r[0] for r in cursor.fetchall()]
        return jsonify({"success": True, "seen_by": seen_users})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Mentions Parsing Helper ──────────────────────────────────────────────────

def parse_and_process_mentions(msg_id, sender_id, content, conv_id, conn):
    """Regex parse @username patterns in message content, log mentions, and send alerts."""
    usernames = re.findall(r'@([a-zA-Z0-9_\-]+)', content)
    if not usernames:
        return

    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM users WHERE id = ?", (sender_id,))
    sender_row = cursor.fetchone()
    sender_name = sender_row[0] if sender_row else "Someone"

    for uname in set(usernames):
        cursor.execute("SELECT id, username FROM users WHERE username = ? AND status = 'ACTIVE'", (uname,))
        u_row = cursor.fetchone()
        if u_row:
            target_uid = u_row[0]
            cursor.execute("""
                SELECT id FROM conversation_participants 
                WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
            """, (conv_id, target_uid))
            
            if cursor.fetchone():
                cursor.execute("""
                    INSERT OR IGNORE INTO mentions (message_id, user_id, mentioned_by_user_id)
                    VALUES (?, ?, ?)
                """, (msg_id, target_uid, sender_id))
                
                send_notification(
                    user_name=u_row[1],
                    title="New Mention",
                    message=f"{sender_name} mentioned you in a chat.",
                    notification_type='INFO',
                    related_module='communication',
                    related_id=conv_id,
                    conn=conn
                )

# ── REST API Endpoints modifications for Phase 1 compatibility ────────────────

@communication_bp.route("/api/v1/communication/conversations", methods=["POST"])
def start_conversation():
    """Start or retrieve direct conversation with another user."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    other_user_id = data.get("other_user_id")
    if not other_user_id or int(other_user_id) == current_uid:
        return jsonify({"success": False, "error": "Invalid other_user_id"}), 400

    other_user_id = int(other_user_id)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cp1.conversation_id 
            FROM conversation_participants cp1
            JOIN conversation_participants cp2 ON cp1.conversation_id = cp2.conversation_id
            JOIN conversations c ON cp1.conversation_id = c.id
            WHERE cp1.user_id = ? AND cp2.user_id = ?
              AND c.type = 'DIRECT' AND c.status = 'ACTIVE'
        """, (current_uid, other_user_id))
        row = cursor.fetchone()
        
        if row:
            conv_id = row[0]
            cursor.execute("""
                UPDATE conversation_participants 
                SET status = 'ACTIVE' 
                WHERE conversation_id = ?
            """, (conv_id,))
            conn.commit()
            return jsonify({"success": True, "conversation_id": conv_id})

        cursor.execute("INSERT INTO conversations (type, owner_id) VALUES ('DIRECT', 1)")
        conv_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO conversation_participants (conversation_id, user_id)
            VALUES (?, ?)
        """, (conv_id, current_uid))
        cursor.execute("""
            INSERT INTO conversation_participants (conversation_id, user_id)
            VALUES (?, ?)
        """, (conv_id, other_user_id))
        
        # Log event
        from repositories.activity_log_repository import log_activity
        cursor.execute("SELECT username FROM users WHERE id = ?", (current_uid,))
        uname = cursor.fetchone()[0]
        log_activity(uname, "Conversation Started", f"Started direct chat #{conv_id} with user #{other_user_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "conversation_id": conv_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    """Soft delete a conversation for the current user."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ?
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Not authorized"}), 403

        cursor.execute("""
            UPDATE conversation_participants 
            SET status = 'DELETED' 
            WHERE conversation_id = ? AND user_id = ?
        """, (conv_id, current_uid))
        
        conn.commit()
        return jsonify({"success": True, "message": "Conversation deleted."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/pin", methods=["POST"])
def pin_conversation(conv_id):
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversation_participants 
            SET is_pinned = 1 
            WHERE conversation_id = ? AND user_id = ?
        """, (conv_id, current_uid))
        if cursor.rowcount == 0:
            return jsonify({"success": False, "error": "Not participant or conversation not found"}), 404
        conn.commit()
        return jsonify({"success": True, "message": "Conversation pinned."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/unpin", methods=["POST"])
def unpin_conversation(conv_id):
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE conversation_participants 
            SET is_pinned = 0 
            WHERE conversation_id = ? AND user_id = ?
        """, (conv_id, current_uid))
        if cursor.rowcount == 0:
            return jsonify({"success": False, "error": "Not participant or conversation not found"}), 404
        conn.commit()
        return jsonify({"success": True, "message": "Conversation unpinned."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/messages", methods=["GET"])
def get_messages(conv_id):
    """Fetch message history for a conversation. Support cursors and offset pagination for scale."""
    current_uid = get_current_user_id()
    since_id = request.args.get("since_id", default=0, type=int)
    before_id = request.args.get("before_id", default=0, type=int)
    limit = request.args.get("limit", default=50, type=int)
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Not authorized to view this conversation"}), 403

        # Build paginated query
        query_base = """
            SELECT m.id, m.sender_id, m.content, m.status, m.created_at, m.updated_at,
                   u.full_name as sender_name, u.username as sender_username,
                   sr.resource_type as gen_type, sr.resource_id as gen_id, sr.display_title, sr.subtitle, sr.preview_metadata, sr.deep_link, sr.id as sr_ref_id,
                   rr.resource_type, rr.resource_id,
                   dr.document_id, d.original_name, d.extension, d.size_bytes,
                   tr.task_id, tr.title, tr.assignee,
                   lr.latitude, lr.longitude, lr.address
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            LEFT JOIN shared_resources sr ON m.id = sr.message_id
            LEFT JOIN resource_references rr ON m.id = rr.message_id
            LEFT JOIN document_references dr ON m.id = dr.message_id
            LEFT JOIN documents d ON dr.document_id = d.id
            LEFT JOIN task_references tr ON m.id = tr.message_id
            LEFT JOIN location_references lr ON m.id = lr.message_id
        """

        if before_id > 0:
            # Paginate backwards to load old messages (scroll up)
            cursor.execute(query_base + """
                WHERE m.conversation_id = ? AND m.id < ?
                ORDER BY m.id DESC LIMIT ?
            """, (conv_id, before_id, limit))
            rows = cursor.fetchall()
            rows.reverse() # Restore timeline order
        else:
            # Normal fetch (new items polling or first load)
            cursor.execute(query_base + """
                WHERE m.conversation_id = ? AND m.id > ?
                ORDER BY m.id ASC LIMIT ?
            """, (conv_id, since_id, limit))
            rows = cursor.fetchall()
        
        messages = []
        message_ids = []
        for row in rows:
            m_id = row[0]
            message_ids.append(m_id)
            sender_id = row[1]
            content = row[2] if row[3] != 'DELETED' else "This message was deleted"
            msg_status = row[3]
            created_at = row[4]
            updated_at = row[5]
            sender_name = row[6]
            
            # Reactions
            cursor.execute("""
                SELECT user_id, reaction FROM message_reactions WHERE message_id = ?
            """, (m_id,))
            reactions = []
            for rx in cursor.fetchall():
                reactions.append({"user_id": rx[0], "reaction": rx[1]})

            # Receipts
            cursor.execute("SELECT type FROM conversations WHERE id = ?", (conv_id,))
            conv_type = cursor.fetchone()[0]
            
            receipt_status = "SENT"
            if conv_type == 'DIRECT':
                cursor.execute("""
                    SELECT status FROM message_receipts 
                    WHERE message_id = ? AND user_id != ?
                """, (m_id, sender_id))
                rc_row = cursor.fetchone()
                receipt_status = rc_row[0] if rc_row else "SENT"
            else:
                receipt_status = "GROUP"

            # Check if this message is pinned
            cursor.execute("SELECT id FROM pinned_messages WHERE message_id = ?", (m_id,))
            is_pinned = cursor.fetchone() is not None

            # Resource data payload (Prioritize new Generic Resource model)
            resource = None
            if row[8]: # gen_type is present
                resource = {
                    "resource_type": row[8],
                    "resource_id": row[9],
                    "display_title": row[10],
                    "subtitle": row[11],
                    "preview_metadata": json.loads(row[12] or '{}'),
                    "deep_link": row[13],
                    "shared_resource_id": row[14]
                }
            elif row[15]: # legacy resource_type is present
                resource = {
                    "resource_type": row[15],
                    "resource_id": row[16]
                }
                if row[15] == 'DOCUMENT':
                    resource["document"] = {
                        "id": row[17],
                        "name": row[18],
                        "extension": row[19],
                        "file_size": row[20]
                    }
                elif row[15] == 'TASK':
                    resource["task"] = {
                        "id": row[21],
                        "title": row[22],
                        "assignee": row[23]
                    }
                elif row[15] == 'LOCATION':
                    resource["location"] = {
                        "latitude": row[24],
                        "longitude": row[25],
                        "address": row[26]
                    }

            messages.append({
                "id": m_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "content": content,
                "status": msg_status,
                "created_at": created_at,
                "updated_at": updated_at,
                "reactions": reactions,
                "receipt_status": receipt_status,
                "is_pinned": is_pinned,
                "resource": resource
            })

        if message_ids and before_id == 0:
            max_id = max(message_ids)
            cursor.execute("""
                UPDATE conversation_participants 
                SET last_read_message_id = ? 
                WHERE conversation_id = ? AND user_id = ?
            """, (max_id, conv_id, current_uid))
            
            cursor.execute("SELECT type FROM conversations WHERE id = ?", (conv_id,))
            c_row = cursor.fetchone()
            if c_row and c_row[0] == 'DIRECT':
                for mid in message_ids:
                    cursor.execute("""
                        INSERT INTO message_receipts (message_id, user_id, status)
                        VALUES (?, ?, 'READ')
                        ON CONFLICT(message_id, user_id) DO UPDATE SET status = 'READ', updated_at = CURRENT_TIMESTAMP
                    """, (mid, current_uid))
            conn.commit()

        return jsonify({"success": True, "messages": messages})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/messages", methods=["POST"])
def send_message(conv_id):
    """Send a new message to the conversation with production rate limiting."""
    current_uid = get_current_user_id()
    
    # Apply Rate Limiting
    if not check_rate_limit(current_uid):
        return jsonify({"success": False, "error": "Too many requests. Please wait before sending more messages."}), 429

    data = request.get_json() or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "error": "Message content cannot be empty"}), 400

    sanitized_content = html.escape(content)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Not participant or conversation deleted"}), 403

        cursor.execute("SELECT type, name, status FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row:
            return jsonify({"success": False, "error": "Conversation not found"}), 404
        conv_type, conv_name, conv_status = conv_row
        if conv_status == 'ARCHIVED':
            return jsonify({"success": False, "error": "Cannot send messages to archived groups"}), 403

        cursor.execute("""
            INSERT INTO messages (conversation_id, sender_id, content, status)
            VALUES (?, ?, ?, 'ACTIVE')
        """, (conv_id, current_uid, sanitized_content))
        message_id = cursor.lastrowid

        cursor.execute("""
            UPDATE conversations 
            SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (conv_id,))

        parse_and_process_mentions(message_id, current_uid, content, conv_id, conn)

        receipt_status = "SENT"
        if conv_type == 'DIRECT':
            cursor.execute("""
                SELECT user_id FROM conversation_participants 
                WHERE conversation_id = ? AND user_id != ?
            """, (conv_id, current_uid))
            other_row = cursor.fetchone()
            if other_row:
                other_uid = other_row[0]
                cursor.execute("""
                    SELECT is_active, last_activity 
                    FROM user_sessions 
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY last_activity DESC LIMIT 1
                """, (other_uid,))
                session_row = cursor.fetchone()
                if session_row:
                    status = determine_online_status(session_row[1], session_row[0])
                    if status == "Online":
                        receipt_status = "DELIVERED"
                cursor.execute("""
                    INSERT INTO message_receipts (message_id, user_id, status)
                    VALUES (?, ?, ?)
                """, (message_id, other_uid, receipt_status))

        conn.commit()
        return jsonify({
            "success": True, 
            "message": {
                "id": message_id,
                "sender_id": current_uid,
                "content": sanitized_content,
                "status": "ACTIVE",
                "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "receipt_status": receipt_status
            }
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/messages/<int:msg_id>", methods=["PUT"])
def edit_message(msg_id):
    """Edit a message. Allowed only for own messages within a 5-minute window."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    new_content = data.get("content", "").strip()
    if not new_content:
        return jsonify({"success": False, "error": "New content cannot be empty"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sender_id, created_at, status 
            FROM messages WHERE id = ?
        """, (msg_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Message not found"}), 404
        
        sender_id, created_at_str, status = row
        if sender_id != current_uid:
            return jsonify({"success": False, "error": "Unauthorized"}), 403
        if status == 'DELETED':
            return jsonify({"success": False, "error": "Cannot edit a deleted message"}), 400

        try:
            created_at = datetime.strptime(created_at_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            if datetime.utcnow() - created_at > timedelta(minutes=5):
                return jsonify({"success": False, "error": "Editing window (5 minutes) has expired"}), 400
        except Exception:
            pass

        sanitized = html.escape(new_content)
        cursor.execute("""
            UPDATE messages 
            SET content = ?, status = 'EDITED', updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (sanitized, msg_id))

        # Log event in activity audit
        from repositories.activity_log_repository import log_activity
        cursor.execute("SELECT username FROM users WHERE id = ?", (current_uid,))
        uname = cursor.fetchone()[0]
        log_activity(uname, "Message Edited", f"Edited message #{msg_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Message edited successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/messages/<int:msg_id>", methods=["DELETE"])
def delete_message(msg_id):
    """Soft delete a message."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sender_id FROM messages WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Message not found"}), 404
        
        sender_id = row[0]
        if sender_id != current_uid:
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        cursor.execute("""
            UPDATE messages 
            SET status = 'DELETED', updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (msg_id,))

        # Log event in activity audit
        from repositories.activity_log_repository import log_activity
        cursor.execute("SELECT username FROM users WHERE id = ?", (current_uid,))
        uname = cursor.fetchone()[0]
        log_activity(uname, "Message Deleted", f"Soft-deleted message #{msg_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Message soft-deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/messages/<int:msg_id>/reactions", methods=["POST"])
def react_to_message(msg_id):
    """Add or update an emoji reaction on a message."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    reaction = data.get("reaction", "").strip()
    
    allowed_reactions = {"👍", "❤️", "😂", "😮", "👏", "🎉"}
    if reaction not in allowed_reactions:
        return jsonify({"success": False, "error": "Invalid reaction emoji"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM messages WHERE id = ?", (msg_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Message not found"}), 404

        cursor.execute("""
            INSERT INTO message_reactions (message_id, user_id, reaction)
            VALUES (?, ?, ?)
            ON CONFLICT(message_id, user_id) DO UPDATE SET reaction = ?, created_at = CURRENT_TIMESTAMP
        """, (msg_id, current_uid, reaction, reaction))
        
        conn.commit()
        return jsonify({"success": True, "message": "Reaction updated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/messages/<int:msg_id>/reactions", methods=["DELETE"])
def remove_reaction(msg_id):
    """Remove reaction."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM message_reactions WHERE message_id = ? AND user_id = ?
        """, (msg_id, current_uid))
        conn.commit()
        return jsonify({"success": True, "message": "Reaction removed."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Unified legacy search route compatibility ───────────────────────────────

@communication_bp.route("/api/v1/communication/search", methods=["GET"])
def search_messages():
    """Unified search over direct & group message content, names, and references."""
    current_uid = get_current_user_id()
    query = request.args.get("q", default="", type=str).strip()
    if not query:
        return jsonify({"success": True, "results": []})

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.conversation_id, m.content, m.created_at, m.status,
                   u.full_name as sender_name, c.type as conv_type, c.name as conv_name,
                   rr.resource_type, rr.resource_id
            FROM messages m
            JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
            JOIN conversations c ON m.conversation_id = c.id
            JOIN users u ON m.sender_id = u.id
            LEFT JOIN resource_references rr ON m.id = rr.message_id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND m.status != 'DELETED'
              AND (m.content LIKE ? OR c.name LIKE ? OR u.full_name LIKE ? OR rr.resource_type LIKE ?)
            ORDER BY m.id DESC
        """, (current_uid, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "message_id": row[0],
                "conversation_id": row[1],
                "content": row[2],
                "created_at": row[3],
                "sender_name": row[5],
                "conversation_type": row[6],
                "conversation_name": row[7] or "Direct Message",
                "resource_type": row[8],
                "resource_id": row[9]
            })
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Shared Resource History (Phase 3 legacy Compatibility) ───────────────────

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/shared-resources", methods=["GET"])
def get_shared_resources(conv_id):
    """Retrieve lists of shared documents, tasks, and locations inside the conversation for the Right Panel."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Shared Documents list
        cursor.execute("""
            SELECT dr.document_id, d.original_name, d.extension, d.size_bytes, m.created_at
            FROM document_references dr
            JOIN documents d ON dr.document_id = d.id
            JOIN messages m ON dr.message_id = m.id
            WHERE m.conversation_id = ?
            ORDER BY m.id DESC
        """, (conv_id,))
        docs = []
        for r in cursor.fetchall():
            docs.append({
                "document_id": r[0],
                "name": r[1],
                "extension": r[2],
                "file_size": r[3],
                "shared_at": r[4]
            })

        # Shared Tasks list
        cursor.execute("""
            SELECT tr.task_id, tr.title, tr.assignee, m.created_at
            FROM task_references tr
            JOIN messages m ON tr.message_id = m.id
            WHERE m.conversation_id = ?
            ORDER BY m.id DESC
        """, (conv_id,))
        tasks = []
        for r in cursor.fetchall():
            tasks.append({
                "task_id": r[0],
                "title": r[1],
                "assignee": r[2],
                "shared_at": r[3]
            })

        # Shared Locations list
        cursor.execute("""
            SELECT lr.latitude, lr.longitude, lr.address, m.created_at
            FROM location_references lr
            JOIN messages m ON lr.message_id = m.id
            WHERE m.conversation_id = ?
            ORDER BY m.id DESC
        """, (conv_id,))
        locations = []
        for r in cursor.fetchall():
            locations.append({
                "latitude": r[0],
                "longitude": r[1],
                "address": r[2],
                "shared_at": r[3]
            })

        return jsonify({
            "success": True,
            "documents": docs,
            "tasks": tasks,
            "locations": locations
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/documents/<int:doc_id>/open", methods=["GET"])
def open_shared_document(doc_id):
    """Validate document access permissions via EDMS before downloading or viewing."""
    current_uid = get_current_user_id()
    if not validate_edms_document_access(doc_id, current_uid):
        return jsonify({"success": False, "error": "You do not have permission to access this document."}), 403

    # Redirect to the native EDMS download URL
    return redirect(f"/api/v1/documents/{doc_id}/download")

# ── Group Ownership & Permissions Updates ─────────────────────────────────────

@communication_bp.route("/api/v1/communication/groups", methods=["POST"])
def create_group():
    """Create a new group conversation and automatically add selected ERP user members."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    member_ids = data.get("member_ids", [])  # list of user IDs

    if not name:
        return jsonify({"success": False, "error": "Group name is required"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, full_name FROM users WHERE id = ?", (current_uid,))
        creator_row = cursor.fetchone()
        creator_name = creator_row[1] if creator_row else "Administrator"

        # Insert Group Conversation (creator owns the group: owner_id = current_uid)
        cursor.execute("""
            INSERT INTO conversations (type, name, description, created_by, owner_id, status)
            VALUES ('GROUP', ?, ?, ?, ?, 'ACTIVE')
        """, (name, description, current_uid, current_uid))
        conv_id = cursor.lastrowid

        # Always add creator as participant
        cursor.execute("""
            INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id)
            VALUES (?, ?)
        """, (conv_id, current_uid))

        # Add other members
        added_members = set(member_ids)
        added_members.discard(current_uid)
        
        for uid in added_members:
            cursor.execute("""
                INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id)
                VALUES (?, ?)
            """, (conv_id, int(uid)))
            
            cursor.execute("SELECT username FROM users WHERE id = ?", (uid,))
            user_row = cursor.fetchone()
            if user_row:
                send_notification(
                    user_name=user_row[0],
                    title="Added to Group",
                    message=f"You were added to the group '{name}' by {creator_name}.",
                    notification_type='INFO',
                    related_module='communication',
                    related_id=conv_id,
                    conn=conn
                )

        # Log system/activity center group created event
        from repositories.activity_log_repository import log_activity
        log_activity(creator_row[0] if creator_row else "System", "Group Created", f"Created group conversation '{name}'", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "conversation_id": conv_id, "message": "Group created successfully."}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/groups/<int:conv_id>", methods=["PUT"])
def edit_group(conv_id):
    """Edit group metadata. Restricted to Owner or Super Admin."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not name:
        return jsonify({"success": False, "error": "Group name is required"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT owner_id, type FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row or conv_row[1] != 'GROUP':
            return jsonify({"success": False, "error": "Group not found"}), 404
            
        cursor.execute("SELECT erp_role, username FROM users WHERE id = ?", (current_uid,))
        user_row = cursor.fetchone()
        role = user_row[0] if user_row else "VIEWER"

        if conv_row[0] != current_uid and role != 'ADMIN':
            return jsonify({"success": False, "error": "Only group owner or admin can edit group details"}), 403

        cursor.execute("""
            UPDATE conversations 
            SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (name, description, conv_id))
        
        # Audit log event
        from repositories.activity_log_repository import log_activity
        log_activity(user_row[1] if user_row else "System", "Group Updated", f"Updated group metadata for group #{conv_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Group details updated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/groups/<int:conv_id>/archive", methods=["POST"])
def archive_group(conv_id):
    """Archive a group conversation. Restricted to Owner or Super Admin."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, owner_id, type FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row or conv_row[2] != 'GROUP':
            return jsonify({"success": False, "error": "Group not found"}), 404
        
        cursor.execute("SELECT erp_role, username, full_name FROM users WHERE id = ?", (current_uid,))
        user_row = cursor.fetchone()
        role = user_row[0] if user_row else "VIEWER"
        owner_name = user_row[2] if user_row else "Administrator"

        if conv_row[1] != current_uid and role != 'ADMIN':
            return jsonify({"success": False, "error": "Unauthorized to archive group"}), 403

        cursor.execute("UPDATE conversations SET status = 'ARCHIVED' WHERE id = ?", (conv_id,))
        
        # Notify members
        cursor.execute("""
            SELECT u.username FROM conversation_participants cp 
            JOIN users u ON cp.user_id = u.id 
            WHERE cp.conversation_id = ? AND cp.status = 'ACTIVE'
        """, (conv_id,))
        for u in cursor.fetchall():
            send_notification(
                user_name=u[0],
                title="Group Archived",
                message=f"Group '{conv_row[0]}' has been archived by {owner_name}.",
                notification_type='WARNING',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )
        
        # Audit log event
        from repositories.activity_log_repository import log_activity
        log_activity(user_row[1] if user_row else "System", "Group Archived", f"Archived group conversation #{conv_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Group archived."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/groups/<int:conv_id>/restore", methods=["POST"])
def restore_group(conv_id):
    """Restore an archived group conversation. Restricted to Owner or Super Admin."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, owner_id, type FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row or conv_row[2] != 'GROUP':
            return jsonify({"success": False, "error": "Group not found"}), 404
        
        cursor.execute("SELECT erp_role, username FROM users WHERE id = ?", (current_uid,))
        user_row = cursor.fetchone()
        role = user_row[0] if user_row else "VIEWER"

        if conv_row[1] != current_uid and role != 'ADMIN':
            return jsonify({"success": False, "error": "Unauthorized to restore group"}), 403

        cursor.execute("UPDATE conversations SET status = 'ACTIVE' WHERE id = ?", (conv_id,))

        # Audit log event
        from repositories.activity_log_repository import log_activity
        log_activity(user_row[1] if user_row else "System", "Group Restored", f"Restored group conversation #{conv_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Group restored."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/groups/<int:conv_id>/members", methods=["GET"])
def get_group_members(conv_id):
    """Fetch active member list of a group."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.full_name, u.username, u.department, u.designation, u.email,
                   us.last_activity, us.is_active
            FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            LEFT JOIN (
                SELECT user_id, MAX(last_activity) as last_activity, MAX(is_active) as is_active
                FROM user_sessions
                GROUP BY user_id
            ) us ON u.id = us.user_id
            WHERE cp.conversation_id = ? AND cp.status = 'ACTIVE'
            ORDER BY u.full_name ASC
        """, (conv_id,))
        
        members = []
        for row in cursor.fetchall():
            status = determine_online_status(row[6], row[7])
            members.append({
                "id": row[0],
                "full_name": row[1],
                "username": row[2],
                "department": row[3],
                "designation": row[4],
                "email": row[5],
                "status": status
            })
        return jsonify({"success": True, "members": members})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/groups/<int:conv_id>/members", methods=["POST"])
def add_group_member(conv_id):
    """Add a member to a group. Restricted to Owner or Super Admin."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "user_id is required"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, owner_id FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row:
            return jsonify({"success": False, "error": "Group not found"}), 404
            
        cursor.execute("SELECT erp_role, full_name, username FROM users WHERE id = ?", (current_uid,))
        c_user = cursor.fetchone()
        role = c_user[0] if c_user else "VIEWER"
        owner_name = c_user[1] if c_user else "Administrator"

        if conv_row[1] != current_uid and role != 'ADMIN':
            return jsonify({"success": False, "error": "Only group owner or admin can add members"}), 403

        cursor.execute("""
            INSERT INTO conversation_participants (conversation_id, user_id, status)
            VALUES (?, ?, 'ACTIVE')
            ON CONFLICT(conversation_id, user_id) DO UPDATE SET status = 'ACTIVE'
        """, (conv_id, int(user_id)))

        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        u_row = cursor.fetchone()
        if u_row:
            send_notification(
                user_name=u_row[0],
                title="Added to Group",
                message=f"You were added to group '{conv_row[0]}' by {owner_name}.",
                notification_type='INFO',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )
            
        # Audit log event
        from repositories.activity_log_repository import log_activity
        log_activity(c_user[2] if c_user else "System", "Group Member Added", f"Added user #{user_id} to group #{conv_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Member added to group."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/groups/<int:conv_id>/members/<int:user_id>", methods=["DELETE"])
def remove_group_member(conv_id, user_id):
    """Remove a member from a group. Restricted to Owner or Super Admin."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, owner_id FROM conversations WHERE id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row:
            return jsonify({"success": False, "error": "Group not found"}), 404
            
        cursor.execute("SELECT erp_role, full_name, username FROM users WHERE id = ?", (current_uid,))
        c_user = cursor.fetchone()
        role = c_user[0] if c_user else "VIEWER"
        owner_name = c_user[1] if c_user else "Administrator"

        if conv_row[1] != current_uid and role != 'ADMIN':
            return jsonify({"success": False, "error": "Only group owner or admin can remove members"}), 403

        cursor.execute("""
            UPDATE conversation_participants 
            SET status = 'DELETED' 
            WHERE conversation_id = ? AND user_id = ?
        """, (conv_id, user_id))

        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        u_row = cursor.fetchone()
        if u_row:
            send_notification(
                user_name=u_row[0],
                title="Removed from Group",
                message=f"You were removed from group '{conv_row[0]}' by {owner_name}.",
                notification_type='WARNING',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )
            
        # Audit log event
        from repositories.activity_log_repository import log_activity
        log_activity(c_user[2] if c_user else "System", "Group Member Removed", f"Removed user #{user_id} from group #{conv_id}", module="Communication", conn=conn)

        conn.commit()
        return jsonify({"success": True, "message": "Member removed from group."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── ERP Automated System Messages & Logging ─────────────────────────────────

@communication_bp.route("/api/v1/communication/system-messages", methods=["POST"])
def create_system_message():
    """ERP modules publish automated updates to a target group (defaults to General)."""
    data = request.get_json() or {}
    event_type = data.get("event_type", "").upper() # 'PURCHASE', 'SALES', 'INVENTORY', 'PROCESSING', 'HR'
    content = data.get("content", "").strip()
    group_name = data.get("group_name", "General").strip()

    if not event_type or not content:
        return jsonify({"success": False, "error": "event_type and content are required"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Find General or specified group conversation
        cursor.execute("SELECT id FROM conversations WHERE type='GROUP' AND name=?", (group_name,))
        conv_row = cursor.fetchone()
        if not conv_row:
            return jsonify({"success": False, "error": f"Group '{group_name}' not found"}), 404
        conv_id = conv_row[0]

        # Insert system message (sender_id = 1, System Administrator fallback)
        cursor.execute("""
            INSERT INTO messages (conversation_id, sender_id, content, status)
            VALUES (?, 1, ?, 'ACTIVE')
        """, (conv_id, f"[SYSTEM ALERT - {event_type}] {content}"))
        message_id = cursor.lastrowid

        # Record in system_messages table
        cursor.execute("""
            INSERT INTO system_messages (conversation_id, event_type, content)
            VALUES (?, ?, ?)
        """, (conv_id, event_type, content))

        # Log system message via activity / audit log
        from repositories.activity_log_repository import log_activity
        log_activity("System Alert", f"System message posted: {event_type}", content, module="Communication", conn=conn)

        # Notify participants
        cursor.execute("""
            SELECT u.username FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.conversation_id = ? AND cp.status = 'ACTIVE'
        """, (conv_id,))
        for u in cursor.fetchall():
            send_notification(
                user_name=u[0],
                title=f"System Update: {event_type}",
                message=content,
                notification_type='SYSTEM',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )

        conn.commit()
        return jsonify({"success": True, "message_id": message_id, "message": "System alert published successfully."}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── User Notification Preferences ────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/preferences", methods=["GET"])
def get_preferences():
    """Retrieve current logged in user notification settings."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT preferences_json FROM notification_preferences WHERE user_id = ?", (current_uid,))
        row = cursor.fetchone()
        if row and row[0]:
            return jsonify({"success": True, "preferences": json.loads(row[0])})
        
        # Fallback default preferences
        defaults = {
            "messages": True,
            "mentions": True,
            "groups": True,
            "system_alerts": True
        }
        return jsonify({"success": True, "preferences": defaults})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/preferences", methods=["POST"])
def save_preferences():
    """Save user notification preference changes."""
    current_uid = get_current_user_id()
    data = request.get_json() or {}
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notification_preferences (user_id, preferences_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET preferences_json = EXCLUDED.preferences_json, updated_at = CURRENT_TIMESTAMP
        """, (current_uid, json.dumps(data)))
        conn.commit()
        return jsonify({"success": True, "message": "Notification preferences updated successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Super Admin Dashboard console & Monitoring Metrics ───────────────────────

@communication_bp.route("/communication/admin", methods=["GET"])
def admin_page():
    """Access Communication module Admin console. Restrict to Admin role."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT erp_role FROM users WHERE id = ?", (current_uid,))
        urow = cursor.fetchone()
        if not urow or urow[0] != 'ADMIN':
            abort(403)
        return render_template("communication/admin.html")
    except Exception:
        abort(403)
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/admin/stats", methods=["GET"])
def get_admin_stats():
    """Admin monitoring endpoint reporting scale stats."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT erp_role FROM users WHERE id = ?", (current_uid,))
        urow = cursor.fetchone()
        if not urow or urow[0] != 'ADMIN':
            return jsonify({"success": False, "error": "Unauthorized Access"}), 403

        cursor.execute("SELECT COUNT(*) FROM conversations")
        tot_convs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conversations WHERE type = 'GROUP'")
        tot_groups = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM messages")
        tot_msgs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_sessions WHERE is_active = 1")
        active_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM shared_resources")
        tot_resources = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM module_registry")
        tot_modules = cursor.fetchone()[0]

        return jsonify({
            "success": True,
            "total_conversations": tot_convs,
            "total_groups": tot_groups,
            "total_messages": tot_msgs,
            "active_users": active_users,
            "total_shared_resources": tot_resources,
            "total_registered_modules": tot_modules
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Pinned Messages Endpoints ────────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/pinned-messages", methods=["GET"])
def get_pinned_messages_legacy(conv_id):
    """Fetch all pinned messages for a conversation (legacy compatibility)."""
    return get_pinned_messages(conv_id)

# ── Message Seen By Readers ──────────────────────────────────────────────────

@communication_bp.route("/api/v1/communication/messages/<int:msg_id>/seen", methods=["GET"])
def get_message_seen_by_legacy(msg_id):
    """Fetch list of ERP user full names who have seen this message (legacy compatibility)."""
    return get_message_seen_by(msg_id)

# ── REST API Endpoints modifications for Phase 1 compatibility ────────────────

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/read", methods=["POST"])
def mark_read_legacy(conv_id):
    """Explicitly mark all messages in a conversation as READ for the current user (legacy compatibility)."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM messages WHERE conversation_id = ?", (conv_id,))
        max_id_row = cursor.fetchone()
        if max_id_row and max_id_row[0]:
            cursor.execute("""
                UPDATE conversation_participants 
                SET last_read_message_id = ? 
                WHERE conversation_id = ? AND user_id = ?
            """, (max_id_row[0], conv_id, current_uid))
            conn.commit()
        return jsonify({"success": True, "message": "Conversation read."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# ── Dynamic Sharing Lookup Endpoints (EDMS & Tasks integration) ─────────────

@communication_bp.route("/api/v1/communication/edms-files", methods=["GET"])
def get_edms_files():
    """Retrieve EDMS files that the active user is authorized to share in chat."""
    current_uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.id, d.original_name, d.extension, d.size_bytes, d.document_number
            FROM documents d
            LEFT JOIN folders f ON d.folder_id = f.id
            WHERE d.status = 'ACTIVE' AND (
                d.owner_user_id = ? OR 
                f.folder_type = 'COMPANY' OR
                d.id IN (SELECT document_id FROM document_shares WHERE shared_with_user_id = ? AND is_revoked = 0)
            )
            ORDER BY d.id DESC
        """, (current_uid, current_uid))
        
        files = []
        for r in cursor.fetchall():
            files.append({
                "id": r[0],
                "name": r[1],
                "extension": r[2],
                "size_bytes": r[3],
                "document_number": r[4]
            })
        return jsonify({"success": True, "files": files})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/conversations/<int:conv_id>/upload-to-edms", methods=["POST"])
def upload_file_to_edms(conv_id):
    """Triggers browser uploads directly into EDMS storage provider without storing locally in chat."""
    current_uid = get_current_user_id()
    
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400

    try:
        from backend.modules.documents.services.document_service import EnterpriseDocumentService
        doc_service = EnterpriseDocumentService()
    except ImportError:
        try:
            from modules.documents.services.document_service import EnterpriseDocumentService
            doc_service = EnterpriseDocumentService()
        except ImportError:
            return jsonify({"success": False, "error": "EDMS service is not loaded"}), 500

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM conversation_participants 
            WHERE conversation_id = ? AND user_id = ? AND status = 'ACTIVE'
        """, (conv_id, current_uid))
        if not cursor.fetchone():
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        import io
        stream = io.BytesIO(file.read())
        doc = doc_service.upload_document(stream, file.filename, user_id=current_uid, description="Uploaded via Chat")
        doc_id = doc['id']

        msg_content = f"Uploaded document: {file.filename}"
        cursor.execute("""
            INSERT INTO messages (conversation_id, sender_id, content, status)
            VALUES (?, ?, ?, 'ACTIVE')
        """, (conv_id, current_uid, msg_content))
        message_id = cursor.lastrowid

        # Central shared_resources catalog insert
        cursor.execute("""
            INSERT INTO shared_resources (message_id, resource_type, resource_id, display_title, subtitle, preview_metadata, deep_link, shared_by)
            VALUES (?, 'DOCUMENT', ?, ?, 'EDMS Document', '{}', ?, ?)
        """, (message_id, str(doc_id), file.filename, f"/api/v1/documents/{doc_id}/download", current_uid))
        shared_ref_id = cursor.lastrowid

        # Legacy references support
        cursor.execute("""
            INSERT INTO resource_references (message_id, resource_type, resource_id)
            VALUES (?, 'DOCUMENT', ?)
        """, (message_id, str(doc_id)))
        cursor.execute("""
            INSERT INTO document_references (message_id, document_id)
            VALUES (?, ?)
        """, (message_id, int(doc_id)))

        # Populate Phase 3 tables
        cursor.execute("""
            INSERT INTO chat_file_reference (document_id, message_id, conversation_id, sender_id)
            VALUES (?, ?, ?, ?)
        """, (int(doc_id), message_id, conv_id, current_uid))
        cursor.execute("""
            INSERT INTO conversation_attachment (conversation_id, message_id, document_id)
            VALUES (?, ?, ?)
        """, (conv_id, message_id, int(doc_id)))
        cursor.execute("SELECT repository_id, extension, size_bytes FROM documents WHERE id = ?", (int(doc_id),))
        doc_row = cursor.fetchone()
        repo_id = doc_row['repository_id'] if doc_row else 1
        file_ext = doc_row['extension'] if doc_row else ""
        fsize = doc_row['size_bytes'] if doc_row else 0
        cursor.execute("""
            INSERT INTO attachment_metadata (document_id, original_repository_id, file_type, file_size, sender_id)
            VALUES (?, ?, ?, ?, ?)
        """, (int(doc_id), repo_id, file_ext, fsize, current_uid))

        # Log & Notify
        from repositories.activity_log_repository import log_activity
        cursor.execute("SELECT username, full_name FROM users WHERE id = ?", (current_uid,))
        urow = cursor.fetchone()
        log_activity(urow[0] if urow else "System", "Resource Shared", f"Uploaded and shared file '{file.filename}'", module="Communication", conn=conn)

        # Notify participants
        cursor.execute("""
            SELECT u.username FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.conversation_id = ? AND cp.user_id != ? AND cp.status = 'ACTIVE'
        """, (conv_id, current_uid))
        for u in cursor.fetchall():
            send_notification(
                user_name=u[0],
                title="Resource Shared",
                message=f"{urow[1] if urow else 'Someone'} uploaded a document in your chat.",
                notification_type='INFO',
                related_module='communication',
                related_id=conv_id,
                conn=conn
            )

        conn.commit()
        return jsonify({
            "success": True, 
            "message_id": message_id, 
            "shared_resource_id": shared_ref_id,
            "document_id": doc_id,
            "message": "File uploaded and shared successfully."
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@communication_bp.route("/api/v1/communication/tasks", methods=["GET"])
def get_tasks_list():
    """Retrieve tasks that can be shared in chat."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, assignee_name, status FROM tasks ORDER BY id DESC")
        tasks = []
        for r in cursor.fetchall():
            tasks.append({
                "id": r[0],
                "title": r[1],
                "assignee_name": r[2],
                "status": r[3]
            })
        return jsonify({"success": True, "tasks": tasks})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
