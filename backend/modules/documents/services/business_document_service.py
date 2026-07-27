import io
import json
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.services.document_service import EnterpriseDocumentService

DOCUMENT_CATEGORIES = [
    "Invoice",
    "Quotation",
    "Photo",
    "Certificate",
    "Government",
    "Legal",
    "Financial",
    "Technical",
    "Compliance",
    "Warranty",
    "Agreement",
    "Report",
    "Other"
]

class BusinessDocumentService:
    """Service to handle Business Document Attachments & Links for ERP Records."""

    def __init__(self, document_service=None):
        self.doc_service = document_service or EnterpriseDocumentService()

    def link_document_to_record(
        self,
        document_id: int,
        module_name: str,
        record_id: int,
        record_type: str = 'record',
        category: str = 'Other',
        description: Optional[str] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Links an existing EDMS document to a specific ERP module record."""
        clean_module = module_name.lower().strip()
        clean_category = category if category in DOCUMENT_CATEGORIES else 'Other'

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO document_links (document_id, module_name, record_type, record_id, category, description, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (document_id, clean_module, record_type, record_id, clean_category, description, user_id))
            link_id = cursor.lastrowid

            # Log Document Activity
            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, details_json)
                VALUES (?, 'LINK', ?, ?)
            """, (document_id, user_id, json.dumps({
                "module_name": clean_module,
                "record_id": record_id,
                "category": clean_category
            })))

            conn.commit()

            cursor.execute("""
                SELECT dl.*, d.document_number, d.original_name, d.extension, d.mime_type, d.size_bytes, d.checksum_sha256, d.created_at
                FROM document_links dl
                JOIN documents d ON dl.document_id = d.id
                WHERE dl.id = ?
            """, (link_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def upload_and_link_document(
        self,
        file_stream: Any,
        original_name: str,
        module_name: str,
        record_id: int,
        record_type: str = 'record',
        category: str = 'Other',
        description: Optional[str] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Uploads a file to EDMS (under /modules folder) and links it to the ERP record."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM folders WHERE path = '/modules' LIMIT 1")
            mod_folder = cursor.fetchone()
            folder_id = mod_folder['id'] if mod_folder else 3
        finally:
            conn.close()

        # 1. Upload to EDMS
        doc = self.doc_service.upload_document(
            file_stream=file_stream,
            original_name=original_name,
            user_id=user_id,
            folder_id=folder_id,
            description=f"Attached to {module_name} record #{record_id}",
            remarks=description
        )

        # 2. Link to ERP Record
        return self.link_document_to_record(
            document_id=doc['id'],
            module_name=module_name,
            record_id=record_id,
            record_type=record_type,
            category=category,
            description=description,
            user_id=user_id
        )

    def store_and_link_generated_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        module_name: str,
        record_id: int,
        record_type: str = 'generated_pdf',
        category: str = 'Invoice',
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Stores a generated ERP PDF (Invoice, Certificate, Report) into EDMS and links it."""
        stream = io.BytesIO(pdf_bytes)
        return self.upload_and_link_document(
            file_stream=stream,
            original_name=filename,
            module_name=module_name,
            record_id=record_id,
            record_type=record_type,
            category=category,
            description="Automatically archived ERP generated PDF document",
            user_id=user_id
        )

    def unlink_document_from_record(self, link_id: int, user_id: int = 1) -> bool:
        """Deinstantiates a document link from an ERP record."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_links WHERE id = ?", (link_id,))
            link = cursor.fetchone()
            if not link:
                raise FileNotFoundError(f"Document link #{link_id} not found.")

            cursor.execute("UPDATE document_links SET is_active = 0 WHERE id = ?", (link_id,))

            # Log Document Activity
            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, details_json)
                VALUES (?, 'UNLINK', ?, ?)
            """, (link['document_id'], user_id, json.dumps({
                "module_name": link['module_name'],
                "record_id": link['record_id'],
                "link_id": link_id
            })))

            conn.commit()
            return True
        finally:
            conn.close()

    def get_record_documents(self, module_name: str, record_id: int, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves all active documents linked to an ERP record."""
        clean_module = module_name.lower().strip()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT dl.id as link_id, dl.category, dl.record_type, dl.description as link_description, dl.uploaded_on as linked_on,
                       d.*
                FROM document_links dl
                JOIN documents d ON dl.document_id = d.id
                WHERE dl.module_name = ? AND dl.record_id = ? AND dl.is_active = 1 AND d.status = 'ACTIVE'
            """
            params = [clean_module, record_id]

            if category and category.lower() != 'all':
                sql += " AND dl.category = ?"
                params.append(category)

            sql += " ORDER BY dl.id DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_record_document_timeline(self, module_name: str, record_id: int) -> List[Dict[str, Any]]:
        """Retrieves chronological document timeline for an ERP record."""
        clean_module = module_name.lower().strip()
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dl.id as link_id, dl.category, dl.record_type, dl.uploaded_on,
                       d.id as document_id, d.document_number, d.original_name, d.extension, d.size_bytes
                FROM document_links dl
                JOIN documents d ON dl.document_id = d.id
                WHERE dl.module_name = ? AND dl.record_id = ?
                ORDER BY dl.uploaded_on ASC
            """, (clean_module, record_id))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
