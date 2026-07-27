import uuid
import mimetypes
import json
from io import BytesIO
from typing import BinaryIO, Dict, Any, List, Optional, Tuple

from backend.database import get_connection
from backend.modules.documents.services.storage_service import EDMSStorageService
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider
from backend.modules.documents.validators.document_validator import DocumentValidator
from backend.modules.documents.services.duplicate_service import DuplicateDetector

class EnterpriseDocumentService:
    """Centralized Document Management Service for Right Ewaste ERP V5.0."""

    def __init__(self, storage_provider=None):
        self.storage = storage_provider or EDMSStorageService()

    def _generate_document_number(self, cursor) -> str:
        """Generates document number via number_series or fallback."""
        cursor.execute("SELECT current_number, prefix, padding_length FROM number_series WHERE series_key = 'DOCUMENT'")
        row = cursor.fetchone()
        if row:
            next_num = row['current_number'] + 1
            cursor.execute("UPDATE number_series SET current_number = ? WHERE series_key = 'DOCUMENT'", (next_num,))
            prefix = row['prefix']
            padding = row['padding_length']
            return f"{prefix}{str(next_num).zfill(padding)}"
        else:
            doc_uuid = str(uuid.uuid4())[:8].upper()
            return f"DOC-2026-{doc_uuid}"

    def upload_document(
        self,
        file_stream: Any,
        original_name: str,
        user_id: int = 1,
        folder_id: Optional[int] = None,
        description: Optional[str] = None,
        remarks: Optional[str] = None,
        repository_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validates, deduplicates, stores physically, and records document metadata."""
        if hasattr(file_stream, 'stream'):
            raw_stream = file_stream.stream
        else:
            raw_stream = file_stream

        raw_stream.seek(0, 2)
        size_bytes = raw_stream.tell()
        raw_stream.seek(0)

        # 1. Centralized Validation
        is_valid, msg = DocumentValidator.validate_upload(original_name, size_bytes)
        if not is_valid:
            raise ValueError(msg)

        clean_original = DocumentValidator.sanitize_filename(original_name)
        ext = clean_original.rsplit('.', 1)[1].lower()
        mime_type = mimetypes.guess_type(clean_original)[0] or 'application/octet-stream'

        # 2. Calculate SHA-256 Checksum
        checksum_sha256 = LocalStorageProvider.calculate_sha256(file_stream)

        # 3. Check for Duplicate Content
        duplicate_info = DuplicateDetector.check_duplicate_by_hash(checksum_sha256)

        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Default to Company Drive root folder if none provided
            if not folder_id:
                if repository_id == 2:
                    cursor.execute("SELECT id FROM folders WHERE path = '/company' LIMIT 1")
                    f_row = cursor.fetchone()
                    folder_id = f_row['id'] if f_row else 1
                else:
                    cursor.execute("SELECT uuid FROM users WHERE id = ?", (user_id,))
                    u_row = cursor.fetchone()
                    u_uuid = u_row[0] if (u_row and u_row[0]) else str(user_id)
                    cursor.execute("SELECT id FROM folders WHERE owner_user_id = ? AND path = ?", (user_id, f"/users/{u_uuid}"))
                    f_row = cursor.fetchone()
                    folder_id = f_row['id'] if f_row else 1

            cursor.execute("SELECT path, folder_type, repository_id FROM folders WHERE id = ?", (folder_id,))
            folder_row = cursor.fetchone()
            folder_path = folder_row['path'] if folder_row else '/company'
            folder_type = folder_row['folder_type'].lower() if folder_row else 'company'
            if not repository_id and folder_row:
                repository_id = folder_row['repository_id']
            if not repository_id:
                repository_id = 2 if folder_type == 'company' else 1

            doc_number = self._generate_document_number(cursor)
            doc_uuid = str(uuid.uuid4())
            stored_name = f"{doc_uuid}.{ext}"

            # Relative physical storage key
            category_dir = folder_type if folder_type in ["company", "users", "modules", "system", "temp", "trash"] else "company"
            storage_key = f"{category_dir}/{stored_name}"

            # 4. Upload to Physical Storage
            self.storage.upload_file(file_stream, storage_key, {"mime_type": mime_type})

            # 5. Insert Metadata Record
            cursor.execute("""
                INSERT INTO documents (
                    document_number, uuid, original_name, stored_name, extension, mime_type,
                    size_bytes, checksum_sha256, storage_provider_id, storage_path, owner_user_id,
                    folder_id, status, description, remarks, created_by, repository_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
            """, (
                doc_number, doc_uuid, clean_original, stored_name, ext, mime_type,
                size_bytes, checksum_sha256, storage_key, user_id, folder_id,
                description, remarks, user_id, repository_id
            ))
            doc_id = cursor.lastrowid

            # 6. Log Document Activity
            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, resource_path, details_json)
                VALUES (?, 'UPLOAD', ?, ?, ?)
            """, (doc_id, user_id, storage_key, json.dumps({
                "original_name": clean_original,
                "size_bytes": size_bytes,
                "is_duplicate": duplicate_info is not None,
                "duplicate_of": duplicate_info['document_number'] if duplicate_info else None
            })))

            conn.commit()

            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            result = dict(cursor.fetchone())
            result['is_duplicate'] = duplicate_info is not None
            result['duplicate_warning'] = f"Identical file content already uploaded as {duplicate_info['document_number']} ({duplicate_info['original_name']})" if duplicate_info else None
            return result
        finally:
            conn.close()

    def download_document(self, doc_identifier: Any) -> Tuple[BinaryIO, Dict[str, Any]]:
        """Retrieves binary stream and metadata for download."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if isinstance(doc_identifier, int) or str(doc_identifier).isdigit():
                cursor.execute("SELECT * FROM documents WHERE id = ?", (int(doc_identifier),))
            else:
                cursor.execute("SELECT * FROM documents WHERE uuid = ?", (str(doc_identifier),))
            doc = cursor.fetchone()
            if not doc:
                raise FileNotFoundError(f"Document record '{doc_identifier}' not found in database.")
            
            doc_dict = dict(doc)
            stream = self.storage.download_file(doc_dict['storage_path'])

            # Log Download activity
            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, resource_path)
                VALUES (?, 'DOWNLOAD', ?, ?)
            """, (doc_dict['id'], 1, doc_dict['storage_path']))
            conn.commit()

            return stream, doc_dict
        finally:
            conn.close()

    def soft_delete_document(self, doc_identifier: Any, user_id: int = 1, cursor=None) -> bool:
        """Moves file to Trash folder in storage and updates database status to TRASH."""
        local_conn = None
        if not cursor:
            local_conn = get_connection()
            cursor = local_conn.cursor()
        try:
            if isinstance(doc_identifier, int) or str(doc_identifier).isdigit():
                cursor.execute("SELECT * FROM documents WHERE id = ?", (int(doc_identifier),))
            else:
                cursor.execute("SELECT * FROM documents WHERE uuid = ?", (str(doc_identifier),))
            doc = cursor.fetchone()
            if not doc:
                raise FileNotFoundError(f"Document record '{doc_identifier}' not found.")

            doc_dict = dict(doc)
            current_key = doc_dict['storage_path']
            trash_key = f"trash/{doc_dict['stored_name']}"

            # Move physical file to storage/trash
            if self.storage.file_exists(current_key):
                self.storage.move_file(current_key, trash_key)

            cursor.execute("""
                UPDATE documents SET status = 'TRASH', storage_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (trash_key, doc_dict['id']))

            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, resource_path, details_json)
                VALUES (?, 'DELETE', ?, ?, ?)
            """, (doc_dict['id'], user_id, trash_key, json.dumps({"previous_path": current_key})))

            if local_conn:
                local_conn.commit()
            return True
        finally:
            if local_conn:
                local_conn.close()

    def restore_document(self, doc_identifier: Any, user_id: int = 1, cursor=None) -> bool:
        """Restores file from Trash back to its original folder directory."""
        local_conn = None
        if not cursor:
            local_conn = get_connection()
            cursor = local_conn.cursor()
        try:
            if isinstance(doc_identifier, int) or str(doc_identifier).isdigit():
                cursor.execute("SELECT d.*, f.folder_type FROM documents d LEFT JOIN folders f ON d.folder_id = f.id WHERE d.id = ?", (int(doc_identifier),))
            else:
                cursor.execute("SELECT d.*, f.folder_type FROM documents d LEFT JOIN folders f ON d.folder_id = f.id WHERE d.uuid = ?", (str(doc_identifier),))
            doc = cursor.fetchone()
            if not doc:
                raise FileNotFoundError(f"Document record '{doc_identifier}' not found.")

            doc_dict = dict(doc)
            trash_key = doc_dict['storage_path']
            category_dir = doc_dict['folder_type'].lower() if doc_dict.get('folder_type') else 'company'
            if category_dir not in ["company", "users", "modules", "system", "temp"]:
                category_dir = "company"
            restored_key = f"{category_dir}/{doc_dict['stored_name']}"

            if self.storage.file_exists(trash_key):
                self.storage.move_file(trash_key, restored_key)

            cursor.execute("""
                UPDATE documents SET status = 'ACTIVE', storage_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (restored_key, doc_dict['id']))

            cursor.execute("""
                INSERT INTO document_activity (document_id, action, user_id, resource_path, details_json)
                VALUES (?, 'RESTORE', ?, ?, ?)
            """, (doc_dict['id'], user_id, restored_key, json.dumps({"trash_path": trash_key})))

            if local_conn:
                local_conn.commit()
            return True
        finally:
            if local_conn:
                local_conn.close()

    def create_folder(self, name: str, parent_folder_id: Optional[int] = None, folder_type: str = 'COMPANY', user_id: int = 1, repository_id: Optional[int] = None) -> Dict[str, Any]:
        """Creates a virtual and physical storage folder."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            parent_path = ""
            if parent_folder_id:
                cursor.execute("SELECT path, repository_id FROM folders WHERE id = ?", (parent_folder_id,))
                p_row = cursor.fetchone()
                if p_row:
                    parent_path = p_row['path']
                    if not repository_id:
                        repository_id = p_row['repository_id']

            if not repository_id:
                repository_id = 2 if folder_type.upper() == 'COMPANY' else 1

            folder_uuid = str(uuid.uuid4())
            clean_name = DocumentValidator.sanitize_filename(name)
            folder_path = f"{parent_path}/{clean_name.lower().replace(' ', '_')}" if parent_path else f"/{clean_name.lower().replace(' ', '_')}"

            # Create physical directory
            self.storage.create_folder(folder_path)

            cursor.execute("""
                INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by, repository_id)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (folder_uuid, clean_name, parent_folder_id, folder_type.upper(), user_id, folder_path, user_id, repository_id))
            folder_id = cursor.lastrowid
            conn.commit()

            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_folder_contents(self, folder_id: Optional[int] = None) -> Dict[str, Any]:
        """Lists active subfolders and documents inside a folder."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if folder_id:
                cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
                current_folder = cursor.fetchone()
                parent_id = folder_id
            else:
                cursor.execute("SELECT * FROM folders WHERE path = '/company' LIMIT 1")
                current_folder = cursor.fetchone()
                parent_id = current_folder['id'] if current_folder else None

            # Fetch subfolders
            if parent_id:
                cursor.execute("SELECT * FROM folders WHERE parent_folder_id = ? AND status = 'ACTIVE' ORDER BY name ASC", (parent_id,))
            else:
                cursor.execute("SELECT * FROM folders WHERE parent_folder_id IS NULL AND status = 'ACTIVE' ORDER BY name ASC")
            subfolders = [dict(r) for r in cursor.fetchall()]

            # Fetch documents
            if parent_id:
                cursor.execute("SELECT * FROM documents WHERE folder_id = ? AND status = 'ACTIVE' ORDER BY id DESC", (parent_id,))
            else:
                cursor.execute("SELECT * FROM documents WHERE status = 'ACTIVE' ORDER BY id DESC")
            docs = [dict(r) for r in cursor.fetchall()]

            # Build folder ancestry path for breadcrumbs
            ancestry = []
            if current_folder:
                curr = dict(current_folder)
                ancestry.append(curr)
                pid = curr['parent_folder_id']
                while pid:
                    cursor.execute("SELECT * FROM folders WHERE id = ?", (pid,))
                    p_row = cursor.fetchone()
                    if p_row:
                        p_dict = dict(p_row)
                        ancestry.append(p_dict)
                        pid = p_dict['parent_folder_id']
                    else:
                        break
                ancestry.reverse()

            return {
                "current_folder": dict(current_folder) if current_folder else None,
                "subfolders": subfolders,
                "documents": docs,
                "ancestry": ancestry
            }
        finally:
            conn.close()

    def get_storage_statistics(self, user_id: Optional[int] = None, repository_id: int = 1) -> Dict[str, Any]:
        """Calculates storage usage and statistics, scoped to a repository and optionally user."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if repository_id == 2:
                # Company Storage is shared company-wide, not scoped by user_id
                cursor.execute("SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_bytes FROM documents WHERE status = 'ACTIVE' AND repository_id = 2")
                active = cursor.fetchone()

                cursor.execute("SELECT COUNT(*) as count FROM folders WHERE status = 'ACTIVE' AND repository_id = 2 AND parent_folder_id IS NOT NULL")
                folders_count = cursor.fetchone()['count']

                cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'TRASH' AND repository_id = 2")
                trash_count = cursor.fetchone()['count']
            else:
                # My Drive repository 1
                if user_id:
                    cursor.execute("SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_bytes FROM documents WHERE status = 'ACTIVE' AND owner_user_id = ? AND repository_id = 1", (user_id,))
                    active = cursor.fetchone()

                    cursor.execute("SELECT COUNT(*) as count FROM folders WHERE status = 'ACTIVE' AND owner_user_id = ? AND repository_id = 1 AND parent_folder_id IS NOT NULL", (user_id,))
                    folders_count = cursor.fetchone()['count']

                    cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'TRASH' AND owner_user_id = ? AND repository_id = 1", (user_id,))
                    trash_count = cursor.fetchone()['count']
                else:
                    cursor.execute("SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_bytes FROM documents WHERE status = 'ACTIVE' AND repository_id = 1")
                    active = cursor.fetchone()

                    cursor.execute("SELECT COUNT(*) as count FROM folders WHERE status = 'ACTIVE' AND repository_id = 1 AND parent_folder_id IS NOT NULL")
                    folders_count = cursor.fetchone()['count']

                    cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'TRASH' AND repository_id = 1")
                    trash_count = cursor.fetchone()['count']

            total_bytes = active['total_bytes']
            total_files = active['count']
            avg_size = (total_bytes / total_files) if total_files > 0 else 0

            return {
                "total_active_files": total_files,
                "total_folders": folders_count,
                "trash_files": trash_count,
                "total_storage_used_bytes": total_bytes,
                "total_storage_used_mb": round(total_bytes / (1024 * 1024), 2),
                "average_file_size_bytes": round(avg_size, 2)
            }
        finally:
            conn.close()

    def rename_folder(self, folder_id: int, new_name: str, user_id: int) -> Dict[str, Any]:
        """Renames a virtual folder."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            clean_name = DocumentValidator.sanitize_filename(new_name)
            cursor.execute("UPDATE folders SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_user_id = ?", (clean_name, folder_id, user_id))
            conn.commit()
            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def move_folder(self, folder_id: int, target_parent_id: Optional[int], user_id: int) -> Dict[str, Any]:
        """Moves a virtual folder and updates its path representation."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if folder_id == target_parent_id:
                raise ValueError("Cannot move a folder into itself.")
            
            parent_path = ""
            if target_parent_id:
                cursor.execute("SELECT path FROM folders WHERE id = ?", (target_parent_id,))
                p_row = cursor.fetchone()
                if p_row:
                    parent_path = p_row['path']

            cursor.execute("SELECT name, path FROM folders WHERE id = ?", (folder_id,))
            folder = cursor.fetchone()
            if not folder:
                raise ValueError("Folder not found.")

            clean_name = folder['name']
            new_path = f"{parent_path}/{clean_name.lower().replace(' ', '_')}" if parent_path else f"/{clean_name.lower().replace(' ', '_')}"

            cursor.execute("""
                UPDATE folders 
                SET parent_folder_id = ?, path = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ? AND owner_user_id = ?
            """, (target_parent_id, new_path, folder_id, user_id))

            conn.commit()
            cursor.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def copy_folder(self, folder_id: int, target_parent_id: Optional[int], user_id: int) -> Dict[str, Any]:
        """Recursively copies a folder and all its nested subfolders and documents."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            def recurse_copy(fid, parent_id):
                cursor.execute("SELECT * FROM folders WHERE id = ?", (fid,))
                folder_row = cursor.fetchone()
                if not folder_row:
                    return None
                
                f_dict = dict(folder_row)
                new_folder = self.create_folder(f_dict['name'], parent_id, f_dict['folder_type'], user_id)
                new_fid = new_folder['id']

                # Copy subfolders
                cursor.execute("SELECT id FROM folders WHERE parent_folder_id = ? AND status = 'ACTIVE'", (fid,))
                subfolder_ids = [r['id'] for r in cursor.fetchall()]
                for sfid in subfolder_ids:
                    recurse_copy(sfid, new_fid)

                # Copy documents
                cursor.execute("SELECT * FROM documents WHERE folder_id = ? AND status = 'ACTIVE'", (fid,))
                doc_rows = [dict(r) for r in cursor.fetchall()]
                for d in doc_rows:
                    doc_number = self._generate_document_number(cursor)
                    doc_uuid = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO documents (
                            document_number, uuid, original_name, stored_name, extension, mime_type,
                            size_bytes, checksum_sha256, storage_provider_id, storage_path, owner_user_id,
                            folder_id, status, description, remarks, created_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
                    """, (
                        doc_number, doc_uuid, d['original_name'], d['stored_name'], d['extension'], d['mime_type'],
                        d['size_bytes'], d['checksum_sha256'], d['storage_provider_id'], d['storage_path'], user_id,
                        new_fid, d['description'], d['remarks'], user_id
                    ))
                return new_folder

            result = recurse_copy(folder_id, target_parent_id)
            conn.commit()
            return result
        finally:
            conn.close()

    def soft_delete_folder(self, folder_id: int, user_id: int) -> bool:
        """Moves a virtual folder and all its contents to Trash."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            folder_ids = [folder_id]
            
            def gather_subfolders(fid):
                cursor.execute("SELECT id FROM folders WHERE parent_folder_id = ? AND status = 'ACTIVE'", (fid,))
                sub_ids = [r['id'] for r in cursor.fetchall()]
                for sfid in sub_ids:
                    folder_ids.append(sfid)
                    gather_subfolders(sfid)

            gather_subfolders(folder_id)

            # Soft delete all nested files
            for fid in folder_ids:
                cursor.execute("SELECT id FROM documents WHERE folder_id = ? AND status = 'ACTIVE'", (fid,))
                doc_ids = [r['id'] for r in cursor.fetchall()]
                for doc_id in doc_ids:
                    self.soft_delete_document(doc_id, user_id, cursor=cursor)

            # Update folders to TRASH
            cursor.execute("SELECT repository_id FROM folders WHERE id = ?", (folder_id,))
            f_row = cursor.fetchone()
            repo_id = f_row['repository_id'] if f_row else 1

            for fid in folder_ids:
                if repo_id == 2:
                    cursor.execute("UPDATE folders SET status = 'TRASH', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (fid,))
                else:
                    cursor.execute("UPDATE folders SET status = 'TRASH', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_user_id = ?", (fid, user_id))

            conn.commit()
            return True
        finally:
            conn.close()

    def restore_folder(self, folder_id: int, user_id: int) -> bool:
        """Restores a virtual folder and all its nested files from Trash."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            folder_ids = [folder_id]
            
            def gather_subfolders(fid):
                cursor.execute("SELECT id FROM folders WHERE parent_folder_id = ? AND status = 'TRASH'", (fid,))
                sub_ids = [r['id'] for r in cursor.fetchall()]
                for sfid in sub_ids:
                    folder_ids.append(sfid)
                    gather_subfolders(sfid)

            gather_subfolders(folder_id)

            # Restore folders to ACTIVE
            cursor.execute("SELECT repository_id FROM folders WHERE id = ?", (folder_id,))
            f_row = cursor.fetchone()
            repo_id = f_row['repository_id'] if f_row else 1

            for fid in folder_ids:
                if repo_id == 2:
                    cursor.execute("UPDATE folders SET status = 'ACTIVE', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (fid,))
                else:
                    cursor.execute("UPDATE folders SET status = 'ACTIVE', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_user_id = ?", (fid, user_id))

            # Restore documents to ACTIVE
            for fid in folder_ids:
                cursor.execute("SELECT id FROM documents WHERE folder_id = ? AND status = 'TRASH'", (fid,))
                doc_ids = [r['id'] for r in cursor.fetchall()]
                for doc_id in doc_ids:
                    self.restore_document(doc_id, user_id, cursor=cursor)

            conn.commit()
            return True
        finally:
            conn.close()

    def rename_file(self, doc_id: int, new_name: str, user_id: int) -> Dict[str, Any]:
        """Renames a document file name."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            clean_name = DocumentValidator.sanitize_filename(new_name)
            ext = clean_name.rsplit('.', 1)[1].lower() if '.' in clean_name else ""
            
            cursor.execute("SELECT extension FROM documents WHERE id = ?", (doc_id,))
            doc_row = cursor.fetchone()
            if doc_row and not ext:
                clean_name = f"{clean_name}.{doc_row['extension']}"
                
            cursor.execute("UPDATE documents SET original_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_user_id = ?", (clean_name, doc_id, user_id))
            conn.commit()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def move_file(self, doc_id: int, target_folder_id: int, user_id: int) -> Dict[str, Any]:
        """Moves a document file to another target folder."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE documents SET folder_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND owner_user_id = ?", (target_folder_id, doc_id, user_id))
            conn.commit()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def copy_file(self, doc_id: int, target_folder_id: int, user_id: int) -> Dict[str, Any]:
        """Copies/duplicates a document file reference to a target folder."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            d = cursor.fetchone()
            if not d:
                raise ValueError("File not found.")
            
            d_dict = dict(d)
            doc_number = self._generate_document_number(cursor)
            doc_uuid = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO documents (
                    document_number, uuid, original_name, stored_name, extension, mime_type,
                    size_bytes, checksum_sha256, storage_provider_id, storage_path, owner_user_id,
                    folder_id, status, description, remarks, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """, (
                doc_number, doc_uuid, f"Copy of {d_dict['original_name']}", d_dict['stored_name'], d_dict['extension'], d_dict['mime_type'],
                d_dict['size_bytes'], d_dict['checksum_sha256'], d_dict['storage_provider_id'], d_dict['storage_path'], user_id,
                target_folder_id, d_dict['description'], d_dict['remarks'], user_id
            ))
            new_id = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (new_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_trash_items(self, user_id: int, repository_id: int = 1) -> Dict[str, Any]:
        """Lists all files and folders marked as status TRASH for the current user/repository."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if repository_id == 2:
                cursor.execute("SELECT * FROM folders WHERE status = 'TRASH' AND repository_id = 2 ORDER BY name ASC")
                folders = [dict(r) for r in cursor.fetchall()]
                cursor.execute("SELECT d.*, f.name as folder_name FROM documents d LEFT JOIN folders f ON d.folder_id = f.id WHERE d.status = 'TRASH' AND d.repository_id = 2 ORDER BY d.id DESC")
                docs = [dict(r) for r in cursor.fetchall()]
            else:
                cursor.execute("SELECT * FROM folders WHERE status = 'TRASH' AND owner_user_id = ? AND repository_id = 1 ORDER BY name ASC", (user_id,))
                folders = [dict(r) for r in cursor.fetchall()]
                cursor.execute("SELECT d.*, f.name as folder_name FROM documents d LEFT JOIN folders f ON d.folder_id = f.id WHERE d.status = 'TRASH' AND d.owner_user_id = ? AND d.repository_id = 1 ORDER BY d.id DESC", (user_id,))
                docs = [dict(r) for r in cursor.fetchall()]
            
            return {
                "folders": folders,
                "documents": docs
            }
        finally:
            conn.close()

    def permanent_delete_file(self, doc_id: int, user_id: int, cursor=None) -> bool:
        """Permanently purges a document file from storage and the metadata database."""
        local_conn = None
        if not cursor:
            local_conn = get_connection()
            cursor = local_conn.cursor()
        try:
            cursor.execute("SELECT storage_path, repository_id FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            if row:
                repo_id = row['repository_id']
                if repo_id != 2:
                    cursor.execute("SELECT storage_path FROM documents WHERE id = ? AND owner_user_id = ?", (doc_id, user_id))
                    if not cursor.fetchone():
                        return False
                try:
                    self.storage.delete_file(row['storage_path'])
                except Exception:
                    pass
                cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                if local_conn:
                    local_conn.commit()
                return True
            return False
        finally:
            if local_conn:
                local_conn.close()

    def permanent_delete_folder(self, folder_id: int, user_id: int, cursor=None) -> bool:
        """Permanently purges a virtual folder and all its contents recursively."""
        local_conn = None
        if not cursor:
            local_conn = get_connection()
            cursor = local_conn.cursor()
        try:
            folder_ids = [folder_id]
            
            def gather_subfolders(fid):
                cursor.execute("SELECT id FROM folders WHERE parent_folder_id = ? AND status = 'TRASH'", (fid,))
                sub_ids = [r['id'] for r in cursor.fetchall()]
                for sfid in sub_ids:
                    folder_ids.append(sfid)
                    gather_subfolders(sfid)

            gather_subfolders(folder_id)

            # Purge files
            for fid in folder_ids:
                cursor.execute("SELECT id FROM documents WHERE folder_id = ? AND status = 'TRASH'", (fid,))
                doc_ids = [r['id'] for r in cursor.fetchall()]
                for doc_id in doc_ids:
                    self.permanent_delete_file(doc_id, user_id, cursor=cursor)

            # Purge folders
            for fid in folder_ids:
                cursor.execute("DELETE FROM folders WHERE id = ?", (fid,))

            if local_conn:
                local_conn.commit()
            return True
        finally:
            if local_conn:
                local_conn.close()

    def empty_trash(self, user_id: int, repository_id: int = 1) -> bool:
        """Empties all trash folders and files for the repository."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if repository_id == 2:
                cursor.execute("SELECT id FROM folders WHERE status = 'TRASH' AND repository_id = 2")
                folder_ids = [r['id'] for r in cursor.fetchall()]
                for fid in folder_ids:
                    self.permanent_delete_folder(fid, user_id, cursor=cursor)
                    
                cursor.execute("SELECT id FROM documents WHERE status = 'TRASH' AND repository_id = 2")
                doc_ids = [r['id'] for r in cursor.fetchall()]
                for doc_id in doc_ids:
                    self.permanent_delete_file(doc_id, user_id, cursor=cursor)
            else:
                cursor.execute("SELECT id FROM folders WHERE status = 'TRASH' AND owner_user_id = ? AND repository_id = 1", (user_id,))
                folder_ids = [r['id'] for r in cursor.fetchall()]
                for fid in folder_ids:
                    self.permanent_delete_folder(fid, user_id, cursor=cursor)
                    
                cursor.execute("SELECT id FROM documents WHERE status = 'TRASH' AND owner_user_id = ? AND repository_id = 1", (user_id,))
                doc_ids = [r['id'] for r in cursor.fetchall()]
                for doc_id in doc_ids:
                    self.permanent_delete_file(doc_id, user_id, cursor=cursor)
                
            conn.commit()
            return True
        finally:
            conn.close()
