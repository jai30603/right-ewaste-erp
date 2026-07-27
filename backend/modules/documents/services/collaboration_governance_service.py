import json
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.services.content_intelligence_service import ContentIntelligenceService

class CollaborationGovernanceService:
    """Service layer for EDMS Document Sharing, Approvals, Comments, Check-In/Check-Out, Notifications, & Governance Policies."""

    def __init__(self):
        self.intel_service = ContentIntelligenceService()

    # ── 1. DOCUMENT SHARING ENGINE ──────────────────────────────────────────────
    def share_document(
        self,
        document_id: int,
        shared_with_user_id: int = 1,
        permission_level: str = 'View',
        expiry_date: Optional[str] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Shares a document with a user or role."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (document_id,))
            doc = cursor.fetchone()
            if not doc:
                raise FileNotFoundError(f"Document #{document_id} not found.")

            cursor.execute("""
                INSERT INTO document_shares (document_id, shared_with_user_id, permission_level, expiry_date, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (document_id, shared_with_user_id, permission_level, expiry_date, user_id))
            share_id = cursor.lastrowid

            # Create notification inline
            cursor.execute("""
                INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                VALUES (?, ?, ?, ?)
            """, (shared_with_user_id, document_id, 'SHARED', f"Document '{doc['original_name']}' was shared with you ({permission_level} access)."))

            conn.commit()
            cursor.execute("SELECT * FROM document_shares WHERE id = ?", (share_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_document_shares(self, document_id: int) -> List[Dict[str, Any]]:
        """Lists active shares for a document."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_shares WHERE document_id = ? AND is_revoked = 0 ORDER BY id DESC", (document_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def revoke_share(self, share_id: int) -> bool:
        """Revokes a document share."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE document_shares SET is_revoked = 1 WHERE id = ?", (share_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── 2. THREADED COMMENTS & DISCUSSIONS ENGINE ──────────────────────────────
    def add_comment(
        self,
        document_id: int,
        comment_text: str,
        parent_comment_id: Optional[int] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Adds a threaded comment to a document."""
        if not comment_text.strip():
            raise ValueError("Comment text cannot be empty.")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (document_id,))
            doc = cursor.fetchone()

            cursor.execute("""
                INSERT INTO document_comments (document_id, parent_comment_id, user_id, comment_text)
                VALUES (?, ?, ?, ?)
            """, (document_id, parent_comment_id, user_id, comment_text.strip()))
            comment_id = cursor.lastrowid

            if doc:
                cursor.execute("""
                    INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                    VALUES (?, ?, ?, ?)
                """, (1, document_id, 'COMMENT_ADDED', f"New comment on '{doc['original_name']}': {comment_text[:40]}..."))

            conn.commit()
            cursor.execute("SELECT * FROM document_comments WHERE id = ?", (comment_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_document_comments(self, document_id: int) -> List[Dict[str, Any]]:
        """Lists comments for a document in hierarchical tree format."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_comments WHERE document_id = ? ORDER BY id ASC", (document_id,))
            comments = [dict(r) for r in cursor.fetchall()]

            tree = []
            comment_map = {c['id']: c for c in comments}
            for c in comments:
                c['replies'] = []

            for c in comments:
                if c['parent_comment_id'] and c['parent_comment_id'] in comment_map:
                    comment_map[c['parent_comment_id']]['replies'].append(c)
                else:
                    tree.append(c)

            return tree
        finally:
            conn.close()

    def resolve_comment(self, comment_id: int) -> bool:
        """Marks a comment as resolved."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE document_comments SET is_resolved = 1 WHERE id = ?", (comment_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── 3. APPROVAL WORKFLOW ENGINE ─────────────────────────────────────────────
    def submit_for_approval(
        self,
        document_id: int,
        reviewer_id: int = 1,
        workflow_type: str = 'STANDARD',
        requester_id: int = 1
    ) -> Dict[str, Any]:
        """Submits a document for review and approval."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (document_id,))
            doc = cursor.fetchone()
            if not doc:
                raise FileNotFoundError(f"Document #{document_id} not found.")

            cursor.execute("""
                INSERT INTO document_approval_workflows (document_id, workflow_type, status, requester_id, reviewer_id)
                VALUES (?, ?, 'UNDER_REVIEW', ?, ?)
            """, (document_id, workflow_type, requester_id, reviewer_id))
            wf_id = cursor.lastrowid

            cursor.execute("UPDATE documents SET lifecycle_status = 'UNDER_REVIEW' WHERE id = ?", (document_id,))

            cursor.execute("""
                INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                VALUES (?, ?, ?, ?)
            """, (reviewer_id, document_id, 'APPROVAL_PENDING', f"Approval requested for document '{doc['original_name']}'."))

            conn.commit()
            cursor.execute("SELECT * FROM document_approval_workflows WHERE id = ?", (wf_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def process_approval_action(
        self,
        workflow_id: int,
        action: str = 'APPROVE',
        remarks: Optional[str] = None,
        reviewer_id: int = 1
    ) -> Dict[str, Any]:
        """Approves or rejects a document workflow."""
        action_clean = action.upper().strip()
        new_status = 'APPROVED' if action_clean == 'APPROVE' else 'REJECTED'

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_approval_workflows WHERE id = ?", (workflow_id,))
            wf = cursor.fetchone()
            if not wf:
                raise FileNotFoundError(f"Approval workflow #{workflow_id} not found.")

            wf_dict = dict(wf)
            doc_id = wf_dict['document_id']

            cursor.execute("""
                UPDATE document_approval_workflows
                SET status = ?, reviewer_remarks = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_status, remarks, workflow_id))

            cursor.execute("UPDATE documents SET lifecycle_status = ? WHERE id = ?", (new_status, doc_id))
            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (doc_id,))
            doc = cursor.fetchone()

            cursor.execute("""
                INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                VALUES (?, ?, ?, ?)
            """, (wf_dict['requester_id'], doc_id, 'APPROVED' if action_clean == 'APPROVE' else 'REJECTED', f"Document '{doc['original_name']}' was {new_status.lower()} by reviewer."))

            conn.commit()
            cursor.execute("SELECT * FROM document_approval_workflows WHERE id = ?", (workflow_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_pending_approvals(self, user_id: int = 1) -> List[Dict[str, Any]]:
        """Lists pending document approval requests."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT daw.*, d.original_name, d.document_number, d.extension as file_type
                FROM document_approval_workflows daw
                JOIN documents d ON daw.document_id = d.id
                WHERE daw.status = 'UNDER_REVIEW' AND (daw.reviewer_id = ? OR ? = 1)
                ORDER BY daw.id DESC
            """, (user_id, user_id))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ── 4. CHECK-IN / CHECK-OUT & LOCKING ENGINE ───────────────────────────────
    def check_out_document(self, document_id: int, lock_reason: str = 'Editing', user_id: int = 1) -> Dict[str, Any]:
        """Locks a document for Check-Out editing."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT is_locked FROM document_locks WHERE document_id = ? AND is_locked = 1", (document_id,))
            existing_lock = cursor.fetchone()
            if existing_lock:
                raise PermissionError(f"Document #{document_id} is already checked out and locked.")

            cursor.execute("""
                INSERT INTO document_locks (document_id, locked_by_user_id, lock_reason, is_locked)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(document_id) DO UPDATE SET locked_by_user_id = excluded.locked_by_user_id, lock_reason = excluded.lock_reason, is_locked = 1, checked_out_at = CURRENT_TIMESTAMP
            """, (document_id, user_id, lock_reason))

            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (document_id,))
            doc = cursor.fetchone()

            cursor.execute("""
                INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                VALUES (?, ?, ?, ?)
            """, (user_id, document_id, 'CHECKOUT', f"Document '{doc['original_name']}' checked out for {lock_reason}."))

            conn.commit()
            cursor.execute("SELECT * FROM document_locks WHERE document_id = ?", (document_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def check_in_document(
        self,
        document_id: int,
        file_stream=None,
        filename: Optional[str] = None,
        changelog: Optional[str] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Unlocks a document on Check-In and creates new version snapshot if file uploaded."""
        new_ver = None
        if file_stream:
            new_ver = self.intel_service.create_new_version(
                document_id=document_id,
                file_stream=file_stream,
                changelog_notes=changelog or "Checked-in edit snapshot",
                user_id=user_id
            )

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE document_locks SET is_locked = 0 WHERE document_id = ?", (document_id,))
            cursor.execute("SELECT original_name FROM documents WHERE id = ?", (document_id,))
            doc = cursor.fetchone()

            if doc:
                cursor.execute("""
                    INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                    VALUES (?, ?, ?, ?)
                """, (user_id, document_id, 'CHECKIN', f"Document '{doc['original_name']}' checked in successfully."))

            conn.commit()
            return {"success": True, "document_id": document_id, "new_version": new_ver}
        finally:
            conn.close()

    def unlock_document(self, document_id: int, user_id: int = 1) -> bool:
        """Forces unlock of a locked document."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE document_locks SET is_locked = 0 WHERE document_id = ?", (document_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_active_locks(self) -> List[Dict[str, Any]]:
        """Lists active document check-out locks."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dl.*, d.original_name, d.document_number, d.extension as file_type
                FROM document_locks dl
                JOIN documents d ON dl.document_id = d.id
                WHERE dl.is_locked = 1
                ORDER BY dl.checked_out_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ── 5. IN-APP NOTIFICATIONS ENGINE ──────────────────────────────────────────
    def create_notification(self, user_id: int, document_id: int, event_type: str, message: str) -> int:
        """Creates an in-app notification entry."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO edms_notifications (user_id, document_id, event_type, message)
                VALUES (?, ?, ?, ?)
            """, (user_id, document_id, event_type, message))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_user_notifications(self, user_id: int = 1, unread_only: bool = False) -> List[Dict[str, Any]]:
        """Lists in-app notifications for user."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM edms_notifications WHERE (user_id = ? OR user_id = 1)"
            if unread_only:
                query += " AND is_read = 0"
            query += " ORDER BY id DESC LIMIT 20"
            cursor.execute(query, (user_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def mark_notification_as_read(self, notification_id: int) -> bool:
        """Marks notification as read."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE edms_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── 6. ENTERPRISE GOVERNANCE POLICIES ──────────────────────────────────────
    def get_governance_policies(self) -> List[Dict[str, Any]]:
        """Lists active enterprise governance policies."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM edms_governance_policies ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_governance_policy(self, policy_key: str, is_enabled: bool, config_json: Optional[Dict[str, Any]] = None) -> bool:
        """Updates governance policy status and config."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if config_json:
                cursor.execute("""
                    UPDATE edms_governance_policies
                    SET is_enabled = ?, config_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE policy_key = ?
                """, (1 if is_enabled else 0, json.dumps(config_json), policy_key))
            else:
                cursor.execute("""
                    UPDATE edms_governance_policies
                    SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE policy_key = ?
                """, (1 if is_enabled else 0, policy_key))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
