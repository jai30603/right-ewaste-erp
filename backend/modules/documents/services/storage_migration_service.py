import json
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.managers.storage_provider_manager import StorageProviderManager

class StorageMigrationService:
    """Zero-Downtime Storage Migration Engine for EDMS."""

    def __init__(self, manager=None):
        self.manager = manager or StorageProviderManager()

    def create_migration_job(
        self,
        job_name: str,
        source_provider_id: int,
        destination_provider_id: int,
        scope_filter: Optional[Dict[str, Any]] = None,
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Creates a new storage migration job entry."""
        if source_provider_id == destination_provider_id:
            raise ValueError("Source and destination storage providers must be different.")

        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Count eligible documents
            cursor.execute("SELECT COUNT(*) as cnt FROM documents WHERE storage_provider_id = ? AND status = 'ACTIVE'", (source_provider_id,))
            total_files = cursor.fetchone()['cnt']

            cursor.execute("""
                INSERT INTO storage_migration_jobs (job_name, source_provider_id, destination_provider_id, scope_json, total_files, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (job_name, source_provider_id, destination_provider_id, json.dumps(scope_filter or {}), total_files, user_id))
            job_id = cursor.lastrowid
            conn.commit()

            cursor.execute("SELECT * FROM storage_migration_jobs WHERE id = ?", (job_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def execute_migration_job(self, job_id: int) -> Dict[str, Any]:
        """Executes provider-to-provider document migration with SHA-256 checksum verification."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM storage_migration_jobs WHERE id = ?", (job_id,))
            job = cursor.fetchone()
            if not job:
                raise FileNotFoundError(f"Migration job #{job_id} not found.")

            j_dict = dict(job)
            src_p_id = j_dict['source_provider_id']
            dst_p_id = j_dict['destination_provider_id']

            src_provider = self.manager.get_provider_by_id(src_p_id)
            dst_provider = self.manager.get_provider_by_id(dst_p_id)

            cursor.execute("UPDATE storage_migration_jobs SET status = 'IN_PROGRESS', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()

            cursor.execute("SELECT * FROM documents WHERE storage_provider_id = ? AND status = 'ACTIVE'", (src_p_id,))
            docs = cursor.fetchall()
            total = len(docs)
            processed = 0
            failed = 0
            errors = []

            for doc in docs:
                d_dict = dict(doc)
                doc_id = d_dict['id']
                storage_key = d_dict['storage_path']

                try:
                    # 1. Download stream from source provider
                    file_stream = src_provider.download_file(storage_key)

                    # 2. Upload stream to destination provider
                    dst_result = dst_provider.upload_file(file_stream, storage_key, {"original_name": d_dict['original_name']})

                    # 3. Integrity verification: Checksum SHA-256 matching
                    if dst_result['checksum_sha256'] != d_dict['checksum_sha256']:
                        raise ValueError(f"Integrity Mismatch for document #{doc_id}: expected {d_dict['checksum_sha256']}, got {dst_result['checksum_sha256']}")

                    # 4. Update document storage_provider_id in DB
                    cursor.execute("""
                        UPDATE documents
                        SET storage_provider_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (dst_p_id, doc_id))

                    # 5. Remove from old source provider
                    try:
                        src_provider.delete_file(storage_key)
                    except Exception:
                        pass

                    processed += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Doc #{doc_id} ('{d_dict['original_name']}'): {str(e)}")

                progress = int((processed + failed) / max(total, 1) * 100)
                cursor.execute("""
                    UPDATE storage_migration_jobs
                    SET processed_files = ?, failed_files = ?, progress_percent = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (processed, failed, progress, job_id))
                conn.commit()

            final_status = "COMPLETED" if failed == 0 else "COMPLETED_WITH_ERRORS"
            err_log_str = "\n".join(errors) if errors else None

            cursor.execute("""
                UPDATE storage_migration_jobs
                SET status = ?, error_log = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (final_status, err_log_str, job_id))
            conn.commit()

            cursor.execute("SELECT * FROM storage_migration_jobs WHERE id = ?", (job_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_migration_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Lists migration execution jobs."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT smj.*,
                       sp1.provider_name as source_provider_name,
                       sp2.provider_name as destination_provider_name
                FROM storage_migration_jobs smj
                JOIN storage_providers sp1 ON smj.source_provider_id = sp1.id
                JOIN storage_providers sp2 ON smj.destination_provider_id = sp2.id
                ORDER BY smj.id DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
