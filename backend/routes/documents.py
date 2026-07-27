from io import BytesIO
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, render_template, session, redirect, flash, url_for, current_app

def get_current_user_id():
    if "user" in session and isinstance(session["user"], dict):
        return session["user"].get("user_id", 1)
    return 1

def check_repository_permission(repository_id, action):
    role = "Super Admin"
    if "user" in session and isinstance(session["user"], dict):
        role = session["user"].get("role", "User")
    
    if role in ["Super Admin", "ADMIN", "SUPER ADMIN", "Admin"]:
        return True
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT can_{action} FROM repository_permissions WHERE repository_id = ? AND role = ?", (repository_id, role))
        row = cursor.fetchone()
        if row:
            return bool(row[0])
        return False
    finally:
        conn.close()

def has_document_access(doc_id, user_id):
    # Retrieve user role
    role = "Super Admin"
    if "user" in session and isinstance(session["user"], dict):
        role = session["user"].get("role", "User")
        
    if role in ["Super Admin", "ADMIN", "SUPER ADMIN", "Admin"]:
        return True
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT repository_id, owner_user_id, status FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row:
            return False
            
        repo_id, owner_id, status = row['repository_id'], row['owner_user_id'], row['status']
        
        # Inactive/Trashed files are not downloadable by normal users
        if status != 'ACTIVE':
            return False
            
        if repo_id == 2:
            # Company Storage: check repository permission
            cursor.execute("SELECT can_download FROM repository_permissions WHERE repository_id = 2 AND role = ?", (role,))
            perm_row = cursor.fetchone()
            if perm_row:
                return bool(perm_row[0])
            return False
        else:
            # My Drive: check ownership or sharing
            if owner_id == user_id:
                return True
                
            # Check document_shares
            cursor.execute("SELECT 1 FROM document_shares WHERE document_id = ? AND shared_with_user_id = ? AND is_revoked = 0", (doc_id, user_id))
            if cursor.fetchone():
                return True
                
            # Check chat references (if shared in a chat participant is part of)
            cursor.execute("""
                SELECT 1 FROM chat_file_reference cfr
                JOIN conversation_participants cp ON cfr.conversation_id = cp.conversation_id
                WHERE cfr.document_id = ? AND cp.user_id = ? AND cp.status = 'ACTIVE'
            """, (doc_id, user_id))
            if cursor.fetchone():
                return True
                
            return False
    finally:
        conn.close()

from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.modules.documents.services.mydrive_service import MyDriveService
from backend.modules.documents.services.companydrive_service import CompanyDriveService
from backend.modules.documents.services.business_document_service import BusinessDocumentService
from backend.modules.documents.services.content_intelligence_service import ContentIntelligenceService
from backend.modules.documents.services.repository_admin_service import RepositoryAdminService
from backend.modules.documents.managers.storage_provider_manager import StorageProviderManager
from backend.modules.documents.services.storage_migration_service import StorageMigrationService
from backend.modules.documents.services.collaboration_governance_service import CollaborationGovernanceService

from backend.database import get_connection

documents_bp = Blueprint("documents", __name__, url_prefix="/api/v1/documents")
doc_service = EnterpriseDocumentService()
mydrive_service = MyDriveService()
companydrive_service = CompanyDriveService()
biz_doc_service = BusinessDocumentService()
intel_service = ContentIntelligenceService()
repo_admin_service = RepositoryAdminService()
provider_mgr = StorageProviderManager()
migration_service = StorageMigrationService(provider_mgr)
collab_service = CollaborationGovernanceService()

# ── Collaboration, Approvals & Governance REST API ────────────────────────────
@documents_bp.route("/<int:doc_id>/share", methods=["POST"])
def share_document_api(doc_id):
    data = request.get_json() or {}
    level = data.get("permission_level", "View")
    exp = data.get("expiry_date")
    try:
        res = collab_service.share_document(doc_id, shared_with_user_id=1, permission_level=level, expiry_date=exp, user_id=1)
        return jsonify({"success": True, "share": res}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/shares", methods=["GET"])
def get_document_shares_api(doc_id):
    shares = collab_service.get_document_shares(doc_id)
    return jsonify({"success": True, "shares": shares})

@documents_bp.route("/shares/<int:share_id>", methods=["DELETE"])
def revoke_share_api(share_id):
    ok = collab_service.revoke_share(share_id)
    return jsonify({"success": ok})

@documents_bp.route("/<int:doc_id>/comments", methods=["POST"])
def add_comment_api(doc_id):
    data = request.get_json() or {}
    text = data.get("comment_text")
    parent_id = data.get("parent_comment_id")
    if not text:
        return jsonify({"success": False, "error": "comment_text is required"}), 400
    try:
        c = collab_service.add_comment(doc_id, text, parent_comment_id=parent_id, user_id=1)
        return jsonify({"success": True, "comment": c}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/comments", methods=["GET"])
def get_comments_api(doc_id):
    comments = collab_service.get_document_comments(doc_id)
    return jsonify({"success": True, "comments": comments})

@documents_bp.route("/<int:doc_id>/approvals/submit", methods=["POST"])
def submit_approval_api(doc_id):
    data = request.get_json() or {}
    wf_type = data.get("workflow_type", "STANDARD")
    try:
        wf = collab_service.submit_for_approval(doc_id, reviewer_id=1, workflow_type=wf_type, requester_id=1)
        return jsonify({"success": True, "workflow": wf}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/approvals/pending", methods=["GET"])
def get_pending_approvals_api():
    apps = collab_service.get_pending_approvals(user_id=1)
    return jsonify({"success": True, "approvals": apps})

@documents_bp.route("/approvals/<int:workflow_id>/action", methods=["POST"])
def process_approval_action_api(workflow_id):
    data = request.get_json() or {}
    action = data.get("action", "APPROVE")
    remarks = data.get("remarks")
    try:
        wf = collab_service.process_approval_action(workflow_id, action=action, remarks=remarks, reviewer_id=1)
        return jsonify({"success": True, "workflow": wf})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/checkout", methods=["POST"])
def checkout_document_api(doc_id):
    data = request.get_json() or {}
    reason = data.get("lock_reason", "Editing")
    try:
        lock = collab_service.check_out_document(doc_id, lock_reason=reason, user_id=1)
        return jsonify({"success": True, "lock": lock})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@documents_bp.route("/<int:doc_id>/checkin", methods=["POST"])
def checkin_document_api(doc_id):
    changelog = request.form.get("changelog", "Checked-in edit snapshot")
    file_item = request.files.get("file")
    stream = BytesIO(file_item.read()) if file_item else None
    filename = file_item.filename if file_item else None

    try:
        res = collab_service.check_in_document(doc_id, file_stream=stream, filename=filename, changelog=changelog, user_id=1)
        return jsonify({"success": True, "res": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/locks", methods=["GET"])
def get_active_locks_api():
    locks = collab_service.get_active_locks()
    return jsonify({"success": True, "locks": locks})

@documents_bp.route("/notifications", methods=["GET"])
def get_notifications_api():
    notifs = collab_service.get_user_notifications(user_id=1)
    return jsonify({"success": True, "notifications": notifs})

@documents_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
def mark_notification_read_api(notif_id):
    ok = collab_service.mark_notification_as_read(notif_id)
    return jsonify({"success": ok})

@documents_bp.route("/governance/policies", methods=["GET"])
def get_governance_policies_api():
    pols = collab_service.get_governance_policies()
    return jsonify({"success": True, "policies": pols})

@documents_bp.route("/governance/policies", methods=["PUT"])
def update_governance_policy_api():
    data = request.get_json() or {}
    key = data.get("policy_key")
    enabled = data.get("is_enabled", False)
    if not key:
        return jsonify({"success": False, "error": "policy_key is required"}), 400
    try:
        collab_service.update_governance_policy(key, enabled)
        pols = collab_service.get_governance_policies()
        return jsonify({"success": True, "policies": pols})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── Multi-Cloud & Storage Migration REST API ──────────────────────────────────
@documents_bp.route("/admin/providers", methods=["GET"])
def get_legacy_storage_providers_api():
    providers = provider_mgr.get_all_providers_status()
    return jsonify({"success": True, "providers": providers})

@documents_bp.route("/admin/providers/test", methods=["POST"])
def test_legacy_storage_provider_api():
    data = request.get_json() or {}
    provider_id = data.get("provider_id", 1)
    try:
        inst = provider_mgr.get_provider_by_id(provider_id)
        health = inst.health_check()
        return jsonify({"success": True, "health": health})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/admin/policies", methods=["GET"])
def get_routing_policies_api():
    policies = provider_mgr.get_routing_policies()
    return jsonify({"success": True, "policies": policies})

@documents_bp.route("/admin/policies", methods=["PUT"])
def update_routing_policy_api():
    data = request.get_json() or {}
    scope = data.get("scope")
    target_provider_id = data.get("target_provider_id")
    if not scope or not target_provider_id:
        return jsonify({"success": False, "error": "scope and target_provider_id are required"}), 400
    try:
        provider_mgr.update_routing_policy(scope, int(target_provider_id))
        policies = provider_mgr.get_routing_policies()
        return jsonify({"success": True, "policies": policies, "message": f"Policy for '{scope}' updated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/admin/migrations", methods=["GET"])
def get_migration_jobs_api():
    jobs = migration_service.get_migration_jobs()
    return jsonify({"success": True, "jobs": jobs})

@documents_bp.route("/admin/migrations", methods=["POST"])
def create_migration_job_api():
    data = request.get_json() or {}
    name = data.get("job_name", "Storage Provider Migration")
    src_id = data.get("source_provider_id")
    dst_id = data.get("destination_provider_id")
    if not src_id or not dst_id:
        return jsonify({"success": False, "error": "source_provider_id and destination_provider_id are required"}), 400

    try:
        job = migration_service.create_migration_job(name, int(src_id), int(dst_id), user_id=1)
        return jsonify({"success": True, "job": job}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/admin/migrations/<int:job_id>/execute", methods=["POST"])
def execute_migration_job_api(job_id):
    try:
        job = migration_service.execute_migration_job(job_id)
        return jsonify({"success": True, "job": job})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── Repository Administration REST API Endpoints ──────────────────────────────
@documents_bp.route("/admin/dashboard", methods=["GET"])
def get_repo_admin_dashboard_api():
    stats = repo_admin_service.get_repository_dashboard_stats()
    return jsonify({"success": True, "stats": stats})

@documents_bp.route("/admin/health", methods=["GET"])
def get_repo_health_diagnostics_api():
    diagnostics = repo_admin_service.run_repository_health_diagnostics()
    return jsonify({"success": True, "diagnostics": diagnostics})

@documents_bp.route("/admin/maintenance", methods=["POST"])
def execute_repo_maintenance_api():
    data = request.get_json() or {}
    action = data.get("action")
    if not action:
        return jsonify({"success": False, "error": "action is required"}), 400
    try:
        res = repo_admin_service.execute_maintenance_task(action, user_id=1)
        logs = repo_admin_service.get_maintenance_logs()
        return jsonify({"success": True, "result": res, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/admin/configs", methods=["GET"])
def get_system_configs_api():
    configs = repo_admin_service.get_system_configs()
    return jsonify({"success": True, "configs": configs})

@documents_bp.route("/admin/configs", methods=["PUT"])
def update_system_configs_api():
    data = request.get_json() or {}
    for k, v in data.items():
        repo_admin_service.update_system_config(k, str(v))
    configs = repo_admin_service.get_system_configs()
    return jsonify({"success": True, "configs": configs, "message": "Configurations updated."})

@documents_bp.route("/admin/backup-config", methods=["GET"])
def get_backup_config_api():
    config = repo_admin_service.get_backup_config()
    return jsonify({"success": True, "backup_config": config})

@documents_bp.route("/admin/backup-config", methods=["PUT"])
def update_backup_config_api():
    data = request.get_json() or {}
    frequency = data.get("backup_frequency", "DAILY")
    retention_days = data.get("retention_days", 30)
    repo_admin_service.update_backup_config(frequency, int(retention_days))
    config = repo_admin_service.get_backup_config()
    return jsonify({"success": True, "backup_config": config, "message": "Backup configuration updated."})

@documents_bp.route("/admin/explorer", methods=["GET"])
def get_repo_explorer_api():
    tree = repo_admin_service.get_repository_explorer_tree()
    return jsonify({"success": True, "tree": tree})

# ── Content Intelligence REST API Endpoints ────────────────────────────────────
@documents_bp.route("/<int:doc_id>/versions", methods=["POST"])
def upload_document_version_api(doc_id):
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file stream provided"}), 400
    uploaded_file = request.files["file"]
    changelog = request.form.get("changelog")
    try:
        updated_doc = intel_service.create_new_version(
            document_id=doc_id,
            file_stream=uploaded_file,
            changelog_notes=changelog,
            user_id=1
        )
        return jsonify({"success": True, "document": updated_doc}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/versions", methods=["GET"])
def get_document_versions_api(doc_id):
    versions = intel_service.get_version_history(doc_id)
    return jsonify({"success": True, "versions": versions})

@documents_bp.route("/<int:doc_id>/versions/<int:version_number>/restore", methods=["POST"])
def restore_document_version_api(doc_id, version_number):
    try:
        intel_service.restore_version(doc_id, version_number, user_id=1)
        return jsonify({"success": True, "message": f"Restored document #{doc_id} to V{version_number}."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/tags", methods=["POST"])
def add_document_tag_api(doc_id):
    data = request.get_json() or {}
    tag_name = data.get("tag_name")
    color_hex = data.get("color_hex")
    if not tag_name:
        return jsonify({"success": False, "error": "tag_name is required"}), 400
    try:
        tag = intel_service.add_tag_to_document(doc_id, tag_name, color_hex)
        return jsonify({"success": True, "tag": tag}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/tags/<int:tag_id>", methods=["DELETE"])
def remove_document_tag_api(doc_id, tag_id):
    intel_service.remove_tag_from_document(doc_id, tag_id)
    return jsonify({"success": True, "message": "Tag removed from document."})

@documents_bp.route("/tags", methods=["GET"])
def get_all_tags_api():
    tags = intel_service.get_all_tags()
    return jsonify({"success": True, "tags": tags})

@documents_bp.route("/<int:doc_id>/classification", methods=["PUT"])
def update_classification_api(doc_id):
    data = request.get_json() or {}
    classification = data.get("classification")
    if not classification:
        return jsonify({"success": False, "error": "classification is required"}), 400
    try:
        intel_service.update_classification(doc_id, classification)
        return jsonify({"success": True, "message": "Classification updated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/lifecycle", methods=["PUT"])
def update_lifecycle_api(doc_id):
    data = request.get_json() or {}
    status = data.get("status")
    if not status:
        return jsonify({"success": False, "error": "status is required"}), 400
    try:
        intel_service.update_lifecycle_status(doc_id, status)
        return jsonify({"success": True, "message": "Lifecycle status updated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/relationships", methods=["POST"])
def link_relationship_api():
    data = request.get_json() or {}
    source_id = data.get("source_document_id")
    target_id = data.get("target_document_id")
    rel_type = data.get("relationship_type", "Related")
    desc = data.get("description")
    if not source_id or not target_id:
        return jsonify({"success": False, "error": "source_document_id and target_document_id are required"}), 400
    try:
        intel_service.link_document_relationship(source_id, target_id, rel_type, desc)
        return jsonify({"success": True, "message": "Document relationship established."}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/relationships", methods=["GET"])
def get_relationships_api(doc_id):
    relationships = intel_service.get_document_relationships(doc_id)
    return jsonify({"success": True, "relationships": relationships})

@documents_bp.route("/intelligence/search", methods=["GET"])
def unified_intelligence_search_api():
    q = request.args.get("q")
    scope = request.args.get("scope", default="ALL")
    category = request.args.get("category")
    classification = request.args.get("classification")
    tag = request.args.get("tag")
    lifecycle_status = request.args.get("lifecycle_status")
    file_type = request.args.get("file_type")
    sort_by = request.args.get("sort_by", default="date")
    sort_order = request.args.get("sort_order", default="desc")

    results = intel_service.unified_search(
        query=q,
        scope=scope,
        category=category,
        classification=classification,
        tag=tag,
        lifecycle_status=lifecycle_status,
        file_type=file_type,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return jsonify({"success": True, "results": results})

# ── Business Record Attachments REST API ──────────────────────────────────────
@documents_bp.route("/attachments/link", methods=["POST"])
def link_attachment_api():
    data = request.get_json() or {}
    document_id = data.get("document_id")
    module_name = data.get("module_name")
    record_id = data.get("record_id")
    record_type = data.get("record_type", "record")
    category = data.get("category", "Other")
    description = data.get("description")

    if not document_id or not module_name or not record_id:
        return jsonify({"success": False, "error": "document_id, module_name, and record_id are required"}), 400

    try:
        link = biz_doc_service.link_document_to_record(
            document_id=document_id,
            module_name=module_name,
            record_id=record_id,
            record_type=record_type,
            category=category,
            description=description,
            user_id=1
        )
        return jsonify({"success": True, "link": link}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/attachments/upload-and-link", methods=["POST"])
def upload_and_link_attachment_api():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file stream provided"}), 400

    uploaded_file = request.files["file"]
    module_name = request.form.get("module_name")
    record_id = request.form.get("record_id", type=int)
    record_type = request.form.get("record_type", "record")
    category = request.form.get("category", "Other")
    description = request.form.get("description")

    if not module_name or not record_id:
        return jsonify({"success": False, "error": "module_name and record_id are required"}), 400

    try:
        link = biz_doc_service.upload_and_link_document(
            file_stream=uploaded_file,
            original_name=uploaded_file.filename,
            module_name=module_name,
            record_id=record_id,
            record_type=record_type,
            category=category,
            description=description,
            user_id=1
        )
        return jsonify({"success": True, "attachment": link}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/attachments/<int:link_id>", methods=["DELETE"])
def unlink_attachment_api(link_id):
    try:
        biz_doc_service.unlink_document_from_record(link_id, user_id=1)
        return jsonify({"success": True, "message": f"Attachment #{link_id} unlinked."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/attachments/<module_name>/<int:record_id>", methods=["GET"])
def get_record_attachments_api(module_name, record_id):
    category = request.args.get("category")
    attachments = biz_doc_service.get_record_documents(module_name, record_id, category=category)
    return jsonify({"success": True, "attachments": attachments})

@documents_bp.route("/attachments/<module_name>/<int:record_id>/timeline", methods=["GET"])
def get_record_attachment_timeline_api(module_name, record_id):
    timeline = biz_doc_service.get_record_document_timeline(module_name, record_id)
    return jsonify({"success": True, "timeline": timeline})

# ── Web UI Routes ─────────────────────────────────────────────────────────────
@documents_bp.route("/mydrive-ui", methods=["GET"])
def mydrive_page_redirect():
    return render_template("documents/mydrive.html")

# ── Company Drive REST API Endpoints ─────────────────────────────────────────
@documents_bp.route("/companydrive/workspace", methods=["GET"])
def get_companydrive_workspace_api():
    workspace = companydrive_service.get_or_create_company_workspace()
    folder_id = request.args.get("folder_id", type=int) or workspace['id']
    contents = doc_service.get_folder_contents(folder_id)
    stats = doc_service.get_storage_statistics(repository_id=2)
    return jsonify({
        "success": True,
        "workspace": workspace,
        "current_contents": contents,
        "stats": stats
    })

@documents_bp.route("/companydrive/analytics", methods=["GET"])
def get_companydrive_analytics_api():
    analytics = companydrive_service.get_company_storage_analytics()
    return jsonify({"success": True, "analytics": analytics})

@documents_bp.route("/companydrive/quick-access", methods=["GET"])
def get_companydrive_quick_access_api():
    folders = companydrive_service.get_company_quick_access_folders()
    return jsonify({"success": True, "quick_access": folders})

@documents_bp.route("/companydrive/search", methods=["GET"])
def search_companydrive_api():
    q = request.args.get("q")
    file_type = request.args.get("file_type")
    folder_id = request.args.get("folder_id", type=int)
    sort_by = request.args.get("sort_by", default="name")
    sort_order = request.args.get("sort_order", default="asc")
    results = companydrive_service.search_company_drive(query=q, file_type=file_type, folder_id=folder_id, sort_by=sort_by, sort_order=sort_order)
    return jsonify({"success": True, "results": results})

# ── REST API Endpoints ─────────────────────────────────────────────────────────
@documents_bp.route("/mydrive/workspace", methods=["GET"])
def get_mydrive_workspace_api():
    uid = get_current_user_id()
    workspace = mydrive_service.get_or_create_user_workspace(user_id=uid)
    folder_id = request.args.get("folder_id", type=int) or workspace['id']
    contents = doc_service.get_folder_contents(folder_id)
    stats = doc_service.get_storage_statistics(user_id=uid)
    return jsonify({
        "success": True,
        "workspace": workspace,
        "current_contents": contents,
        "stats": stats
    })

@documents_bp.route("/favorites/toggle", methods=["POST"])
def toggle_favorite_api():
    data = request.get_json() or {}
    doc_id = data.get("document_id")
    folder_id = data.get("folder_id")
    uid = get_current_user_id()
    try:
        is_fav = mydrive_service.toggle_favorite(user_id=uid, document_id=doc_id, folder_id=folder_id)
        return jsonify({"success": True, "is_favorite": is_fav})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@documents_bp.route("/favorites", methods=["GET"])
def get_favorites_api():
    uid = get_current_user_id()
    favs = mydrive_service.get_favorites(user_id=uid)
    return jsonify({"success": True, "data": favs})

@documents_bp.route("/recent", methods=["GET"])
def get_recent_api():
    limit = request.args.get("limit", default=10, type=int)
    uid = get_current_user_id()
    recents = mydrive_service.get_recent_files(user_id=uid, limit=limit)
    return jsonify({"success": True, "data": recents})

@documents_bp.route("/mydrive/search", methods=["GET"])
def search_mydrive_api():
    q = request.args.get("q")
    file_type = request.args.get("file_type")
    folder_id = request.args.get("folder_id", type=int)
    sort_by = request.args.get("sort_by", default="name")
    sort_order = request.args.get("sort_order", default="asc")
    uid = get_current_user_id()
    results = mydrive_service.search_mydrive(user_id=uid, query=q, file_type=file_type, folder_id=folder_id, sort_by=sort_by, sort_order=sort_order)
    return jsonify({"success": True, "results": results})

@documents_bp.route("/<doc_id>/preview-data", methods=["GET"])
def get_preview_data_api(doc_id):
    uid = get_current_user_id()
    if not has_document_access(doc_id, uid):
        return jsonify({"success": False, "error": "Unauthorized to access this document"}), 403
    try:
        stream, doc = doc_service.download_document(doc_id)
        mime = doc['mime_type'].lower()
        ext = doc['extension'].lower()
        content_text = None

        if ext in ['txt', 'json', 'csv', 'md', 'xml'] or 'text' in mime or 'json' in mime or 'csv' in mime:
            try:
                content_text = stream.read().decode('utf-8', errors='replace')
            except Exception:
                content_text = None

        return jsonify({
            "success": True,
            "document": doc,
            "preview_type": "text" if content_text is not None else ("image" if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'] or 'image' in mime else ("pdf" if ext == 'pdf' else "unsupported")),
            "content_text": content_text
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/upload", methods=["POST"])
def upload_document_api():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file stream provided in request"}), 400
    
    uploaded_file = request.files["file"]
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"success": False, "error": "No selected file"}), 400

    folder_id = request.form.get("folder_id", type=int)
    description = request.form.get("description")
    remarks = request.form.get("remarks")
    repository_id = request.form.get("repository_id", type=int)
    uid = get_current_user_id()

    try:
        result = doc_service.upload_document(
            file_stream=uploaded_file,
            original_name=uploaded_file.filename,
            user_id=uid,
            folder_id=folder_id,
            description=description,
            remarks=remarks,
            repository_id=repository_id
        )
        return jsonify({"success": True, "document": result}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 422
    except Exception as e:
        return jsonify({"success": False, "error": f"Upload failed: {str(e)}"}), 500

@documents_bp.route("/<doc_id>/download", methods=["GET"])
def download_document_api(doc_id):
    uid = get_current_user_id()
    if not has_document_access(doc_id, uid):
        return jsonify({"success": False, "error": "Unauthorized to access this document"}), 403
    try:
        stream, doc = doc_service.download_document(doc_id)
        return send_file(
            stream,
            as_attachment=True,
            download_name=doc['original_name'],
            mimetype=doc['mime_type']
        )
    except FileNotFoundError as fnf:
        return jsonify({"success": False, "error": str(fnf)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<doc_id>", methods=["DELETE"])
def delete_document_api(doc_id):
    uid = get_current_user_id()
    try:
        doc_service.soft_delete_document(doc_id, user_id=uid)
        return jsonify({"success": True, "message": f"Document '{doc_id}' moved to Trash."})
    except FileNotFoundError as fnf:
        return jsonify({"success": False, "error": str(fnf)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<doc_id>/restore", methods=["POST"])
def restore_document_api(doc_id):
    uid = get_current_user_id()
    try:
        doc_service.restore_document(doc_id, user_id=uid)
        return jsonify({"success": True, "message": f"Document '{doc_id}' restored from Trash."})
    except FileNotFoundError as fnf:
        return jsonify({"success": False, "error": str(fnf)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/folders", methods=["GET"])
def get_folders_api():
    folder_id = request.args.get("folder_id", type=int)
    contents = doc_service.get_folder_contents(folder_id)
    return jsonify({"success": True, "data": contents})

@documents_bp.route("/folders", methods=["POST"])
def create_folder_api():
    data = request.get_json() or {}
    name = data.get("name")
    parent_folder_id = data.get("parent_folder_id")
    folder_type = data.get("folder_type", "USER")
    repository_id = data.get("repository_id")
    if repository_id is not None:
        try:
            repository_id = int(repository_id)
        except ValueError:
            repository_id = None
    uid = get_current_user_id()

    if not name:
        return jsonify({"success": False, "error": "Folder name is required"}), 400

    try:
        folder = doc_service.create_folder(name, parent_folder_id, folder_type, user_id=uid, repository_id=repository_id)
        return jsonify({"success": True, "folder": folder}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/stats", methods=["GET"])
def get_stats_api():
    uid = get_current_user_id()
    stats = doc_service.get_storage_statistics(user_id=uid)
    return jsonify({"success": True, "stats": stats})

@documents_bp.route("/folders/all", methods=["GET"])
def get_all_active_folders_api():
    uid = get_current_user_id()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, path FROM folders WHERE owner_user_id = ? AND status = 'ACTIVE' AND folder_type = 'USER' ORDER BY name ASC", (uid,))
        folders = [dict(r) for r in cursor.fetchall()]
        return jsonify({"success": True, "folders": folders})
    finally:
        conn.close()

# ── Folder Operations ──
@documents_bp.route("/folders/<int:folder_id>/rename", methods=["PUT"])
def rename_folder_api(folder_id):
    data = request.get_json() or {}
    new_name = data.get("name")
    if not new_name:
        return jsonify({"success": False, "error": "New name is required"}), 400
    uid = get_current_user_id()
    try:
        folder = doc_service.rename_folder(folder_id, new_name, user_id=uid)
        return jsonify({"success": True, "folder": folder})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/folders/<int:folder_id>/move", methods=["POST"])
def move_folder_api(folder_id):
    data = request.get_json() or {}
    target_parent_id = data.get("target_parent_id")
    uid = get_current_user_id()
    try:
        folder = doc_service.move_folder(folder_id, target_parent_id, user_id=uid)
        return jsonify({"success": True, "folder": folder})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/folders/<int:folder_id>/copy", methods=["POST"])
def copy_folder_api(folder_id):
    data = request.get_json() or {}
    target_parent_id = data.get("target_parent_id")
    uid = get_current_user_id()
    try:
        folder = doc_service.copy_folder(folder_id, target_parent_id, user_id=uid)
        return jsonify({"success": True, "folder": folder})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/folders/<int:folder_id>", methods=["DELETE"])
def delete_folder_api(folder_id):
    uid = get_current_user_id()
    try:
        doc_service.soft_delete_folder(folder_id, user_id=uid)
        return jsonify({"success": True, "message": "Folder moved to Trash."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── File Operations ──
@documents_bp.route("/<int:doc_id>/rename", methods=["PUT"])
def rename_file_api(doc_id):
    data = request.get_json() or {}
    new_name = data.get("name")
    if not new_name:
        return jsonify({"success": False, "error": "New name is required"}), 400
    uid = get_current_user_id()
    try:
        doc = doc_service.rename_file(doc_id, new_name, user_id=uid)
        return jsonify({"success": True, "document": doc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/move", methods=["POST"])
def move_file_api(doc_id):
    data = request.get_json() or {}
    target_folder_id = data.get("target_folder_id")
    if not target_folder_id:
        return jsonify({"success": False, "error": "Target folder_id is required"}), 400
    uid = get_current_user_id()
    try:
        doc = doc_service.move_file(doc_id, int(target_folder_id), user_id=uid)
        return jsonify({"success": True, "document": doc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/<int:doc_id>/copy", methods=["POST"])
def copy_file_api(doc_id):
    data = request.get_json() or {}
    target_folder_id = data.get("target_folder_id")
    if not target_folder_id:
        return jsonify({"success": False, "error": "Target folder_id is required"}), 400
    uid = get_current_user_id()
    try:
        doc = doc_service.copy_file(doc_id, int(target_folder_id), user_id=uid)
        return jsonify({"success": True, "document": doc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── Trash / Recycle Bin Operations ──
@documents_bp.route("/trash", methods=["GET"])
def get_trash_items_api():
    uid = get_current_user_id()
    items = doc_service.get_trash_items(user_id=uid)
    return jsonify({"success": True, "data": items})

@documents_bp.route("/trash/<string:item_type>/<int:item_id>/restore", methods=["POST"])
def restore_trash_item_api(item_type, item_id):
    uid = get_current_user_id()
    try:
        if item_type.upper() == 'FOLDER':
            doc_service.restore_folder(item_id, user_id=uid)
        else:
            doc_service.restore_document(item_id, user_id=uid)
        return jsonify({"success": True, "message": "Item restored successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/trash/<string:item_type>/<int:item_id>/permanent", methods=["DELETE"])
def permanent_delete_trash_item_api(item_type, item_id):
    uid = get_current_user_id()
    try:
        if item_type.upper() == 'FOLDER':
            doc_service.permanent_delete_folder(item_id, user_id=uid)
        else:
            doc_service.permanent_delete_file(item_id, user_id=uid)
        return jsonify({"success": True, "message": "Item permanently deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/trash/empty", methods=["DELETE"])
def empty_trash_api():
    uid = get_current_user_id()
    try:
        doc_service.empty_trash(user_id=uid)
        return jsonify({"success": True, "message": "Recycle Bin emptied successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@documents_bp.route("/chatfiles/workspace", methods=["GET"])
def get_chatfiles_workspace_api():
    uid = get_current_user_id()
    
    # Extract query params
    q = request.args.get("q", "").strip()
    channel = request.args.get("channel", "").strip()  # 'direct', 'group'
    direction = request.args.get("direction", "").strip()  # 'sent', 'received'
    file_category = request.args.get("category", "").strip()  # 'image', 'document', 'video', 'archive'
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    sort_by = request.args.get("sort_by", "newest").strip()  # 'newest', 'oldest', 'name', 'size'
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Build query
        sql = """
            FROM chat_file_reference cfr
            JOIN documents d ON cfr.document_id = d.id
            JOIN messages m ON cfr.message_id = m.id
            JOIN conversations c ON cfr.conversation_id = c.id
            JOIN users sender ON cfr.sender_id = sender.id
            JOIN conversation_participants cp ON cfr.conversation_id = cp.conversation_id
            WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND d.status = 'ACTIVE'
        """
        params = [uid]
        
        # Apply filters
        if q:
            sql += """ AND (
                d.original_name LIKE ?
                OR sender.full_name LIKE ?
                OR c.name LIKE ?
                OR d.extension LIKE ?
                OR (c.type = 'DIRECT' AND EXISTS (
                    SELECT 1 FROM conversation_participants cp2
                    JOIN users u2 ON cp2.user_id = u2.id
                    WHERE cp2.conversation_id = cfr.conversation_id AND cp2.user_id != ? AND u2.full_name LIKE ?
                ))
            )"""
            like_val = f"%{q}%"
            params.extend([like_val, like_val, like_val, like_val, uid, like_val])
            
        if channel == 'direct':
            sql += " AND c.type = 'DIRECT'"
        elif channel == 'group':
            sql += " AND c.type = 'GROUP'"
            
        if direction == 'sent':
            sql += " AND cfr.sender_id = ?"
            params.append(uid)
        elif direction == 'received':
            sql += " AND cfr.sender_id != ?"
            params.append(uid)
            
        if file_category == 'image':
            sql += " AND d.extension IN ('png', 'jpg', 'jpeg', 'gif', 'webp', 'svg')"
        elif file_category == 'document':
            sql += " AND d.extension IN ('pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'csv', 'json', 'xml', 'md')"
        elif file_category == 'video':
            sql += " AND d.extension IN ('mp4', 'mov', 'avi', 'mkv', 'webm')"
        elif file_category == 'archive':
            sql += " AND d.extension IN ('zip', 'rar', 'tar', 'gz', '7z')"
            
        if start_date:
            sql += " AND cfr.shared_at >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            sql += " AND cfr.shared_at <= ?"
            params.append(f"{end_date} 23:59:59")
            
        # Select fields
        select_clause = """
            SELECT cfr.id, cfr.document_id, cfr.message_id, cfr.conversation_id, cfr.sender_id, cfr.shared_at,
                   d.original_name, d.extension, d.size_bytes, d.repository_id,
                   sender.full_name as sender_name,
                   c.type as conversation_type, c.name as conversation_name
        """
        
        # Sorting
        if sort_by == 'oldest':
            order_clause = " ORDER BY cfr.shared_at ASC"
        elif sort_by == 'name':
            order_clause = " ORDER BY d.original_name ASC"
        elif sort_by == 'size':
            order_clause = " ORDER BY d.size_bytes DESC"
        else: # 'newest'
            order_clause = " ORDER BY cfr.shared_at DESC"
            
        # Run main query
        cursor.execute(select_clause + sql + order_clause, params)
        rows = cursor.fetchall()
        
        # Fetch other user names for direct chats
        cursor.execute("""
            SELECT cp.conversation_id, u.full_name
            FROM conversation_participants cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.conversation_id IN (
                SELECT conversation_id FROM conversation_participants WHERE user_id = ? AND cp.status = 'ACTIVE'
            ) AND cp.user_id != ? AND cp.status = 'ACTIVE'
        """, (uid, uid))
        direct_targets = {row[0]: row[1] for row in cursor.fetchall()}
        
        results = []
        for r in rows:
            cfr_id, doc_id, msg_id, conv_id, sender_id, shared_at, name, ext, size, repo_id, sname, ctype, cname = r
            
            # Construct detail text
            if ctype == 'GROUP':
                detail = f"Shared in {cname}"
            else:
                other_name = direct_targets.get(conv_id, "Someone")
                if sender_id == uid:
                    detail = f"Sent to {other_name}"
                else:
                    detail = f"Received from {sname}"
                    
            results.append({
                "id": cfr_id,
                "document_id": doc_id,
                "message_id": msg_id,
                "conversation_id": conv_id,
                "sender_id": sender_id,
                "shared_at": shared_at,
                "original_name": name,
                "extension": ext,
                "size_bytes": size,
                "repository_id": repo_id,
                "sender_name": sname,
                "conversation_type": ctype,
                "conversation_name": cname,
                "detail_text": detail
            })
            
        # Get Chat Files specific stats
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(d.size_bytes), 0) FROM chat_file_reference cfr JOIN documents d ON cfr.document_id = d.id JOIN conversation_participants cp ON cfr.conversation_id = cp.conversation_id WHERE cp.user_id = ? AND cp.status = 'ACTIVE' AND d.status = 'ACTIVE'", (uid,))
        total_shared_files, total_shared_bytes = cursor.fetchone()
        
        stats = {
            "total_active_files": total_shared_files,
            "total_storage_used_bytes": total_shared_bytes,
            "total_storage_used_mb": round(total_shared_bytes / (1024 * 1024), 2),
            "total_folders": 0,
            "trash_files": 0
        }
        
        return jsonify({
            "success": True,
            "results": results,
            "stats": stats
        })
        return jsonify({
            "success": True,
            "results": results,
            "stats": stats
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


from backend.modules.documents.services.workspace_service import EDMSWorkspaceService
from backend.modules.documents.services.storage_service import xor_crypt, xor_decrypt

workspace_service = EDMSWorkspaceService()

@documents_bp.route("/storage-providers", methods=["GET"])
def get_storage_providers_api():
    user = session.get("user", {})
    role = user.get("role", "User")
    if current_app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, provider_key, provider_name, provider_type, config_json, is_active, status, health_status, last_connection_test, last_synchronization 
            FROM storage_providers
        """)
        rows = cursor.fetchall()
        providers = []
        for r in rows:
            pid, pkey, pname, ptype, crypt_json, is_active, status, health, last_test, last_sync = r
            
            # Decrypt configuration
            try:
                decrypted_str = xor_decrypt(crypt_json)
                config = json.loads(decrypted_str)
            except Exception:
                config = {}
                
            # Obfuscate sensitive credentials
            obfuscated_config = {}
            for k, v in config.items():
                if any(sec in k.lower() for sec in ["key", "secret", "password", "token", "credentials"]):
                    obfuscated_config[k] = "********"
                else:
                    obfuscated_config[k] = v
                    
            # Fetch storage health metrics
            cursor.execute("""
                SELECT connection_status, bucket_availability, last_successful_connection, last_error, total_files, total_folders, storage_usage_bytes 
                FROM storage_health WHERE provider_id = ?
            """, (pid,))
            h_row = cursor.fetchone()
            health_details = {}
            if h_row:
                health_details = {
                    "connection_status": h_row[0],
                    "bucket_availability": h_row[1],
                    "last_successful_connection": h_row[2],
                    "last_error": h_row[3],
                    "total_files": h_row[4],
                    "total_folders": h_row[5],
                    "storage_usage_bytes": h_row[6]
                }

            providers.append({
                "id": pid,
                "provider_key": pkey,
                "provider_name": pname,
                "provider_type": ptype,
                "config": obfuscated_config,
                "is_active": bool(is_active),
                "status": status,
                "health_status": health,
                "last_connection_test": last_test,
                "last_synchronization": last_sync,
                "health_details": health_details
            })
            
        return jsonify({"success": True, "providers": providers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@documents_bp.route("/storage-providers/save", methods=["POST"])
def save_storage_provider_api():
    user = session.get("user", {})
    role = user.get("role", "User")
    if current_app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json() or {}
    provider_id = data.get("provider_id")
    config = data.get("config", {})

    if not provider_id:
        return jsonify({"success": False, "error": "Missing provider_id"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Load existing config to check for unchanged masked fields
        cursor.execute("SELECT config_json FROM storage_providers WHERE id = ?", (provider_id,))
        row = cursor.fetchone()
        existing_config = {}
        if row:
            try:
                decrypted_str = xor_decrypt(row[0])
                existing_config = json.loads(decrypted_str)
            except Exception:
                pass
                
        # Merge credentials: if the value is "********", keep the old value!
        final_config = {}
        for k, v in config.items():
            if v == "********":
                final_config[k] = existing_config.get(k, "")
            else:
                final_config[k] = v

        crypt_json = xor_crypt(json.dumps(final_config))
        cursor.execute("""
            UPDATE storage_providers 
            SET config_json = ?, updated_at = ? 
            WHERE id = ?
        """, (crypt_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider_id))
        
        conn.commit()
        return jsonify({"success": True, "message": "Configuration saved successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@documents_bp.route("/storage-providers/test", methods=["POST"])
def test_storage_provider_api():
    user = session.get("user", {})
    role = user.get("role", "User")
    if current_app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json() or {}
    provider_id = data.get("provider_id")
    config = data.get("config", {})

    if not provider_id:
        return jsonify({"success": False, "error": "Missing provider_id"}), 400

    # Load existing config for masked merges
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT config_json FROM storage_providers WHERE id = ?", (provider_id,))
        row = cursor.fetchone()
        existing_config = {}
        if row:
            try:
                decrypted_str = xor_decrypt(row[0])
                existing_config = json.loads(decrypted_str)
            except Exception:
                pass
    finally:
        conn.close()

    final_config = {}
    for k, v in config.items():
        if v == "********":
            final_config[k] = existing_config.get(k, "")
        else:
            final_config[k] = v

    # Instantiate provider class
    provider_instance = None
    try:
        from backend.modules.documents.providers.s3_storage_provider import AWSS3StorageProvider
        from backend.modules.documents.providers.azure_storage_provider import AzureBlobStorageProvider
        from backend.modules.documents.providers.gcs_storage_provider import GCSStorageProvider
        
        cursor_conn = get_connection()
        cursor = cursor_conn.cursor()
        cursor.execute("SELECT provider_key FROM storage_providers WHERE id = ?", (provider_id,))
        pkey = cursor.fetchone()[0]
        cursor_conn.close()

        if pkey in ['aws_s3', 's3']:
            aws_config = {
                "bucket": final_config.get("bucket_name", "right-ewaste-docs"),
                "region": final_config.get("aws_region", "ap-south-1"),
                "access_key": final_config.get("aws_access_key_id", "MOCK_KEY"),
                "secret_key": final_config.get("aws_secret_access_key", "MOCK_SECRET"),
            }
            provider_instance = AWSS3StorageProvider(config=aws_config)
        elif pkey == 'azure_blob':
            provider_instance = AzureBlobStorageProvider(config=final_config)
        elif pkey == 'gcs':
            provider_instance = GCSStorageProvider(config=final_config)

        if not provider_instance:
            return jsonify({"success": False, "error": "Unknown provider key"}), 400

        # Validate connection
        is_valid = provider_instance.validate_connection()
        if not is_valid:
            raise ValueError("Authentication credentials failed verification.")
            
        # Update connection test timestamp in database
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE storage_providers 
                SET last_connection_test = ?, status = 'CONNECTED', health_status = 'HEALTHY', updated_at = ? 
                WHERE id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider_id))
            
            cursor.execute("""
                INSERT INTO storage_health (provider_id, connection_status, bucket_availability, last_successful_connection, last_error, updated_at)
                VALUES (?, 'CONNECTED', 1, ?, NULL, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    connection_status = 'CONNECTED',
                    bucket_availability = 1,
                    last_successful_connection = excluded.last_successful_connection,
                    last_error = NULL,
                    updated_at = excluded.updated_at
            """, (provider_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "message": "Connection test successful."})
    except Exception as e:
        # Log failure
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE storage_providers 
                SET status = 'ERROR', health_status = 'UNHEALTHY', updated_at = ? 
                WHERE id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider_id))
            cursor.execute("""
                INSERT INTO storage_health (provider_id, connection_status, bucket_availability, last_error, updated_at)
                VALUES (?, 'ERROR', 0, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    connection_status = 'ERROR',
                    bucket_availability = 0,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
            """, (provider_id, str(e), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": False, "error": f"Connection failed: {str(e)}"}), 400

@documents_bp.route("/storage-providers/activate", methods=["POST"])
def activate_storage_provider_api():
    user = session.get("user", {})
    role = user.get("role", "User")
    if current_app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json() or {}
    provider_id = data.get("provider_id")

    if not provider_id:
        return jsonify({"success": False, "error": "Missing provider_id"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Verify provider status
        cursor.execute("SELECT status FROM storage_providers WHERE id = ?", (provider_id,))
        row = cursor.fetchone()
        if not row or row[0] != 'CONNECTED':
            return jsonify({"success": False, "error": "Before activating, the provider must be successfully connected and tested."}), 400

        # Deactivate all other providers
        cursor.execute("UPDATE storage_providers SET is_active = 0")
        # Activate target
        cursor.execute("UPDATE storage_providers SET is_active = 1 WHERE id = ?", (provider_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Storage provider activated successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@documents_bp.route("/storage-providers/disable", methods=["POST"])
def disable_storage_provider_api():
    user = session.get("user", {})
    role = user.get("role", "User")
    if current_app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json() or {}
    provider_id = data.get("provider_id")

    if not provider_id:
        return jsonify({"success": False, "error": "Missing provider_id"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE storage_providers SET is_active = 0 WHERE id = ?", (provider_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Storage provider disabled."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@documents_bp.route("/storage-providers/initialize", methods=["POST"])
def initialize_workspace_api():
    user = session.get("user", {})
    role = user.get("role", "User")
    if current_app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json() or {}
    provider_id = data.get("provider_id")

    if not provider_id:
        return jsonify({"success": False, "error": "Missing provider_id"}), 400

    # Save configuration first if provided
    config = data.get("config")
    if config:
        # Merge and save
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT config_json FROM storage_providers WHERE id = ?", (provider_id,))
            row = cursor.fetchone()
            existing_config = {}
            if row:
                try:
                    decrypted_str = xor_decrypt(row[0])
                    existing_config = json.loads(decrypted_str)
                except Exception:
                    pass
            final_config = {}
            for k, v in config.items():
                if v == "********":
                    final_config[k] = existing_config.get(k, "")
                else:
                    final_config[k] = v

            crypt_json = xor_crypt(json.dumps(final_config))
            cursor.execute("""
                UPDATE storage_providers 
                SET config_json = ?, updated_at = ? 
                WHERE id = ?
            """, (crypt_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), provider_id))
            conn.commit()
        finally:
            conn.close()

    success = workspace_service.initialize_workspace(provider_id)
    if success:
        return jsonify({"success": True, "message": "Workspace initialized and folder structure created for all existing users successfully."})
    else:
        return jsonify({"success": False, "error": "Failed to initialize workspace. Please check provider connection status and configurations."}), 400


