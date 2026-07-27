import uuid
import json
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider
from backend.modules.documents.validators.document_validator import DocumentValidator
from backend.modules.documents.services.document_service import EnterpriseDocumentService

DOCUMENT_CLASSIFICATIONS = [
    "PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED",
    "FINANCIAL", "LEGAL", "OPERATIONAL", "TECHNICAL", "COMPLIANCE", "SAFETY"
]

LIFECYCLE_STATUSES = [
    "DRAFT", "UPLOADED", "UNDER_REVIEW", "APPROVED",
    "REJECTED", "SUPERSEDED", "ARCHIVED", "EXPIRED"
]

class ContentIntelligenceService:
    """Service for EDMS Content Intelligence, Versioning, Tagging, and Unified Search."""

    def __init__(self, document_service=None):
        self.doc_service = document_service or EnterpriseDocumentService()
        self.storage = self.doc_service.storage

    def create_new_version(
        self,
        document_id: int,
        file_stream: Any,
        changelog_notes: Optional[str] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Uploads a new version of a document, saving V1 in document_versions table."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            doc = cursor.fetchone()
            if not doc:
                raise FileNotFoundError(f"Document #{document_id} not found.")

            doc_dict = dict(doc)
            curr_version = doc_dict.get('version', 1) or 1
            next_version = curr_version + 1

            # 1. Preserve current version record in document_versions
            cursor.execute("""
                INSERT OR IGNORE INTO document_versions (document_id, version_number, storage_path, size_bytes, checksum_sha256, changelog_notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_dict['id'],
                curr_version,
                doc_dict['storage_path'],
                doc_dict['size_bytes'],
                doc_dict['checksum_sha256'],
                f"Version {curr_version} snapshot",
                doc_dict.get('created_by', 1)
            ))

            # 2. Process new file stream
            if hasattr(file_stream, 'stream'):
                raw_stream = file_stream.stream
            else:
                raw_stream = file_stream

            raw_stream.seek(0, 2)
            size_bytes = raw_stream.tell()
            raw_stream.seek(0)

            checksum_sha256 = LocalStorageProvider.calculate_sha256(raw_stream)
            ext = doc_dict['extension']
            new_stored_name = f"{doc_dict['uuid']}_v{next_version}.{ext}"

            # Category dir from old storage_path
            category_dir = doc_dict['storage_path'].split('/')[0] if '/' in doc_dict['storage_path'] else 'company'
            new_storage_key = f"{category_dir}/{new_stored_name}"

            # Upload to physical storage
            self.storage.upload_file(raw_stream, new_storage_key, {"mime_type": doc_dict['mime_type']})

            # 3. Update main document record to new version
            cursor.execute("""
                UPDATE documents
                SET stored_name = ?, storage_path = ?, size_bytes = ?, checksum_sha256 = ?,
                    version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_stored_name, new_storage_key, size_bytes, checksum_sha256, next_version, document_id))

            # 4. Insert new version record
            cursor.execute("""
                INSERT INTO document_versions (document_id, version_number, storage_path, size_bytes, checksum_sha256, changelog_notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (document_id, next_version, new_storage_key, size_bytes, checksum_sha256, changelog_notes or f"Uploaded Version {next_version}", user_id))

            # 5. Log activity
            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, resource_path, details_json)
                VALUES (?, 'VERSION_CREATED', ?, ?, ?)
            """, (document_id, user_id, new_storage_key, json.dumps({
                "version_number": next_version,
                "changelog": changelog_notes
            })))

            conn.commit()

            cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_version_history(self, document_id: int) -> List[Dict[str, Any]]:
        """Retrieves complete version history for a document."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dv.*, u.full_name as author_name
                FROM document_versions dv
                LEFT JOIN users u ON dv.created_by = u.id
                WHERE dv.document_id = ?
                ORDER BY dv.version_number DESC
            """, (document_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def restore_version(self, document_id: int, version_number: int, user_id: int = 1) -> bool:
        """Restores document state to a previous version number."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_versions WHERE document_id = ? AND version_number = ?", (document_id, version_number))
            ver = cursor.fetchone()
            if not ver:
                raise FileNotFoundError(f"Version V{version_number} for document #{document_id} not found.")

            v_dict = dict(ver)
            cursor.execute("""
                UPDATE documents
                SET storage_path = ?, size_bytes = ?, checksum_sha256 = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (v_dict['storage_path'], v_dict['size_bytes'], v_dict['checksum_sha256'], version_number, document_id))

            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, resource_path, details_json)
                VALUES (?, 'VERSION_RESTORED', ?, ?, ?)
            """, (document_id, user_id, v_dict['storage_path'], json.dumps({"restored_version": version_number})))

            conn.commit()
            return True
        finally:
            conn.close()

    # ── Tagging Engine ─────────────────────────────────────────────────────────
    def add_tag_to_document(self, document_id: int, tag_name: str, color_hex: Optional[str] = None) -> Dict[str, Any]:
        """Ensures tag exists and links it to document."""
        clean_tag = tag_name.strip()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, tag_name, color_hex FROM document_tags WHERE LOWER(tag_name) = LOWER(?)", (clean_tag,))
            tag_row = cursor.fetchone()

            if not tag_row:
                cursor.execute("INSERT INTO document_tags (tag_name, color_hex) VALUES (?, ?)", (clean_tag, color_hex or '#3b82f6'))
                tag_id = cursor.lastrowid
            else:
                tag_id = tag_row['id']

            cursor.execute("INSERT OR IGNORE INTO document_tag_mappings (document_id, tag_id) VALUES (?, ?)", (document_id, tag_id))
            conn.commit()

            cursor.execute("SELECT id, tag_name, color_hex FROM document_tags WHERE id = ?", (tag_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def remove_tag_from_document(self, document_id: int, tag_id: int) -> bool:
        """Removes a tag mapping from document."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_tag_mappings WHERE document_id = ? AND tag_id = ?", (document_id, tag_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_document_tags(self, document_id: int) -> List[Dict[str, Any]]:
        """Lists all tags associated with a document."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dt.* FROM document_tags dt
                JOIN document_tag_mappings dtm ON dt.id = dtm.tag_id
                WHERE dtm.document_id = ?
                ORDER BY dt.tag_name ASC
            """, (document_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """Lists all available document tags in system."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_tags ORDER BY tag_name ASC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ── Classification & Lifecycle ──────────────────────────────────────────────
    def update_classification(self, document_id: int, classification: str) -> bool:
        """Updates document classification level."""
        clean_class = classification.upper().strip()
        if clean_class not in DOCUMENT_CLASSIFICATIONS:
            raise ValueError(f"Invalid classification '{classification}'. Allowed: {', '.join(DOCUMENT_CLASSIFICATIONS)}")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE documents SET classification = ? WHERE id = ?", (clean_class, document_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def update_lifecycle_status(self, document_id: int, status: str) -> bool:
        """Updates document lifecycle status."""
        clean_status = status.upper().strip()
        if clean_status not in LIFECYCLE_STATUSES:
            raise ValueError(f"Invalid lifecycle status '{status}'. Allowed: {', '.join(LIFECYCLE_STATUSES)}")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE documents SET lifecycle_status = ? WHERE id = ?", (clean_status, document_id))
            conn.commit()
            return True
        finally:
            conn.close()

    # ── Document Relationships Graph ──────────────────────────────────────────
    def link_document_relationship(self, source_doc_id: int, target_doc_id: int, relationship_type: str = 'Related', description: Optional[str] = None) -> bool:
        """Links a relationship between two EDMS documents."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO document_relationships (source_document_id, target_document_id, relationship_type, description)
                VALUES (?, ?, ?, ?)
            """, (source_doc_id, target_doc_id, relationship_type, description))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_document_relationships(self, document_id: int) -> List[Dict[str, Any]]:
        """Fetches all related documents for a given document."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dr.id as rel_id, dr.relationship_type, dr.description as rel_description,
                       d.id, d.document_number, d.original_name, d.extension, d.size_bytes, d.mime_type
                FROM document_relationships dr
                JOIN documents d ON dr.target_document_id = d.id
                WHERE dr.source_document_id = ?
                UNION
                SELECT dr.id as rel_id, dr.relationship_type, dr.description as rel_description,
                       d.id, d.document_number, d.original_name, d.extension, d.size_bytes, d.mime_type
                FROM document_relationships dr
                JOIN documents d ON dr.source_document_id = d.id
                WHERE dr.target_document_id = ?
            """, (document_id, document_id))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ── Unified Intelligent Search Engine ─────────────────────────────────────
    def unified_search(
        self,
        query: Optional[str] = None,
        scope: str = 'ALL', # ALL, MYDRIVE, COMPANY, ATTACHMENTS
        category: Optional[str] = None,
        classification: Optional[str] = None,
        tag: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
        file_type: Optional[str] = None,
        sort_by: str = 'date',
        sort_order: str = 'desc'
    ) -> List[Dict[str, Any]]:
        """Unified Enterprise Search indexing across My Drive, Company Drive & ERP Attachments."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT DISTINCT d.*, f.name as folder_name, f.folder_type,
                       dl.module_name, dl.record_id, dl.category as attachment_category,
                       GROUP_CONCAT(dt.tag_name) as tag_names
                FROM documents d
                LEFT JOIN folders f ON d.folder_id = f.id
                LEFT JOIN document_links dl ON d.id = dl.document_id AND dl.is_active = 1
                LEFT JOIN document_tag_mappings dtm ON d.id = dtm.document_id
                LEFT JOIN document_tags dt ON dtm.tag_id = dt.id
                WHERE d.status = 'ACTIVE'
            """
            params = {}

            # Scope Filtering
            scope_clean = scope.upper()
            if scope_clean == 'MYDRIVE':
                sql += " AND f.folder_type = 'USER'"
            elif scope_clean == 'COMPANY':
                sql += " AND f.folder_type = 'COMPANY'"
            elif scope_clean == 'ATTACHMENTS':
                sql += " AND dl.id IS NOT NULL"

            # Query Search across original_name, document_number, description, OCR text & module names
            if query and query.strip():
                sql += """ AND (
                    d.original_name LIKE :q OR
                    d.document_number LIKE :q OR
                    d.description LIKE :q OR
                    d.ocr_text LIKE :q OR
                    dl.module_name LIKE :q
                )"""
                params["q"] = f"%{query.strip()}%"

            if category and category.lower() != 'all':
                sql += " AND dl.category = :cat"
                params["cat"] = category

            if classification and classification.lower() != 'all':
                sql += " AND d.classification = :cls"
                params["cls"] = classification.upper()

            if lifecycle_status and lifecycle_status.lower() != 'all':
                sql += " AND d.lifecycle_status = :lcs"
                params["lcs"] = lifecycle_status.upper()

            if tag and tag.strip():
                sql += " AND dt.tag_name = :tag"
                params["tag"] = tag.strip()

            if file_type and file_type.lower() != 'all':
                ft = file_type.lower()
                if ft == 'image':
                    sql += " AND d.extension IN ('png', 'jpg', 'jpeg', 'gif', 'webp', 'svg')"
                elif ft == 'pdf':
                    sql += " AND d.extension = 'pdf'"
                elif ft in ['spreadsheet', 'excel', 'csv']:
                    sql += " AND d.extension IN ('xls', 'xlsx', 'csv')"
                elif ft in ['document', 'word', 'text']:
                    sql += " AND d.extension IN ('doc', 'docx', 'txt', 'json', 'xml', 'md')"

            sql += " GROUP BY d.id"

            # Sorting
            valid_sorts = {
                'name': 'd.original_name',
                'date': 'd.created_at',
                'size': 'd.size_bytes',
                'version': 'd.version'
            }
            order_col = valid_sorts.get(sort_by.lower(), 'd.created_at')
            order_dir = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
            sql += f" ORDER BY {order_col} {order_dir}"

            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ── OCR & AI Readiness Extensions ──────────────────────────────────────────
    def set_ocr_extracted_text(self, document_id: int, text: str) -> bool:
        """Stores extracted OCR text for document search indexing."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE documents SET ocr_text = ? WHERE id = ?", (text, document_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def set_ai_summary(self, document_id: int, summary: str) -> bool:
        """Stores AI-generated document summary."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE documents SET ai_summary = ? WHERE id = ?", (summary, document_id))
            conn.commit()
            return True
        finally:
            conn.close()
