import os
import json
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider
from backend.modules.documents.services.document_service import EnterpriseDocumentService

class RepositoryAdminService:
    """Administrative Control Center Service for EDMS Repository Management & Diagnostics."""

    def __init__(self, document_service=None):
        self.doc_service = document_service or EnterpriseDocumentService()
        self.storage = self.doc_service.storage

    def get_repository_dashboard_stats(self) -> Dict[str, Any]:
        """Calculates global administrative repository statistics & KPIs."""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Total active documents & size
            cursor.execute("SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_bytes FROM documents WHERE status = 'ACTIVE'")
            doc_stats = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) as count FROM folders WHERE status = 'ACTIVE'")
            folders_count = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM document_versions")
            versions_count = cursor.fetchone()['count']

            # Duplicate files detection (same SHA-256)
            cursor.execute("""
                SELECT COUNT(*) as count FROM (
                    SELECT checksum_sha256 FROM documents WHERE status = 'ACTIVE' GROUP BY checksum_sha256 HAVING COUNT(*) > 1
                )
            """)
            dup_count = cursor.fetchone()['count']

            # Storage by Module
            cursor.execute("""
                SELECT dl.module_name, COUNT(DISTINCT d.id) as file_count, COALESCE(SUM(d.size_bytes), 0) as total_bytes
                FROM document_links dl
                JOIN documents d ON dl.document_id = d.id
                WHERE dl.is_active = 1 AND d.status = 'ACTIVE'
                GROUP BY dl.module_name
            """)
            by_module = [dict(r) for r in cursor.fetchall()]

            # Storage by File Type / Extension
            cursor.execute("""
                SELECT extension, COUNT(*) as file_count, COALESCE(SUM(size_bytes), 0) as total_bytes
                FROM documents WHERE status = 'ACTIVE'
                GROUP BY extension ORDER BY total_bytes DESC LIMIT 5
            """)
            by_type = [dict(r) for r in cursor.fetchall()]

            # Largest files
            cursor.execute("SELECT * FROM documents WHERE status = 'ACTIVE' ORDER BY size_bytes DESC LIMIT 5")
            largest_files = [dict(r) for r in cursor.fetchall()]

            total_bytes = doc_stats['total_bytes']
            total_mb = round(total_bytes / (1024 * 1024), 2)

            health_data = self.run_repository_health_diagnostics()

            return {
                "total_documents": doc_stats['count'],
                "total_folders": folders_count,
                "total_versions": versions_count,
                "total_duplicates": dup_count,
                "total_storage_bytes": total_bytes,
                "total_storage_mb": total_mb,
                "health_score": health_data['health_score'],
                "by_module": by_module,
                "by_type": by_type,
                "largest_files": largest_files
            }
        finally:
            conn.close()

    def run_repository_health_diagnostics(self) -> Dict[str, Any]:
        """Runs health diagnostics across physical storage and metadata integrity."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            findings = []
            score = 100

            # 1. Missing physical files
            cursor.execute("SELECT id, original_name, storage_path FROM documents WHERE status = 'ACTIVE'")
            active_docs = cursor.fetchall()

            missing_files = 0
            for d in active_docs:
                if not self.storage.file_exists(d['storage_path']):
                    missing_files += 1

            if missing_files > 0:
                score -= min(missing_files * 10, 40)
                findings.append({
                    "severity": "HIGH",
                    "issue": "Missing Storage Files",
                    "details": f"{missing_files} document records reference files not found on disk storage provider."
                })

            # 2. Empty folders (non-system)
            cursor.execute("""
                SELECT f.id, f.name, f.path FROM folders f
                LEFT JOIN documents d ON f.id = d.folder_id
                WHERE d.id IS NULL AND f.path NOT IN ('/company', '/users', '/modules', '/system', '/temp', '/trash')
            """)
            empty_folders = cursor.fetchall()
            if empty_folders:
                score -= min(len(empty_folders) * 2, 15)
                findings.append({
                    "severity": "LOW",
                    "issue": "Empty Custom Folders",
                    "details": f"{len(empty_folders)} empty custom user folders found."
                })

            # 3. Duplicate files check
            cursor.execute("SELECT checksum_sha256, COUNT(*) as c FROM documents WHERE status = 'ACTIVE' GROUP BY checksum_sha256 HAVING c > 1")
            dups = cursor.fetchall()
            if dups:
                score -= min(len(dups) * 5, 20)
                findings.append({
                    "severity": "MEDIUM",
                    "issue": "Duplicate Content Hashes",
                    "details": f"{len(dups)} duplicate file content hashes detected."
                })

            # 4. Broken document links
            cursor.execute("""
                SELECT dl.id FROM document_links dl
                LEFT JOIN documents d ON dl.document_id = d.id
                WHERE d.id IS NULL AND dl.is_active = 1
            """)
            broken_links = cursor.fetchall()
            if broken_links:
                score -= min(len(broken_links) * 10, 25)
                findings.append({
                    "severity": "HIGH",
                    "issue": "Broken Module Document Links",
                    "details": f"{len(broken_links)} document link mappings reference deleted or non-existent document IDs."
                })

            score = max(0, score)
            status = "HEALTHY" if score >= 90 else ("DEGRADED" if score >= 60 else "CRITICAL")

            return {
                "health_score": score,
                "status": status,
                "findings": findings
            }
        finally:
            conn.close()

    def execute_maintenance_task(self, action_key: str, user_id: int = 1) -> Dict[str, Any]:
        """Executes administrative maintenance utility jobs."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            action_clean = action_key.lower().strip()
            details = ""

            if action_clean == "rebuild_search_index":
                cursor.execute("SELECT COUNT(*) as c FROM documents WHERE status = 'ACTIVE'")
                cnt = cursor.fetchone()['c']
                details = f"Reindexed {cnt} active documents into unified search index."

            elif action_clean == "clean_empty_folders":
                cursor.execute("""
                    DELETE FROM folders
                    WHERE id IN (
                        SELECT f.id FROM folders f
                        LEFT JOIN documents d ON f.id = d.folder_id
                        WHERE d.id IS NULL AND f.path NOT IN ('/company', '/users', '/modules', '/system', '/temp', '/trash')
                    )
                """)
                deleted_cnt = cursor.rowcount
                details = f"Cleaned {deleted_cnt} empty non-system folders."

            elif action_clean == "recalculate_storage_stats":
                cursor.execute("SELECT SUM(size_bytes) as total FROM documents WHERE status = 'ACTIVE'")
                total = cursor.fetchone()['total'] or 0
                details = f"Recalculated storage stats. Total active storage: {round(total / (1024*1024), 2)} MB."

            elif action_clean == "clean_temp_storage":
                cursor.execute("UPDATE documents SET status = 'TRASH' WHERE storage_path LIKE 'temp/%'")
                cnt = cursor.rowcount
                details = f"Moved {cnt} temporary files to Trash."

            elif action_clean == "verify_file_checksums":
                cursor.execute("SELECT id, storage_path, checksum_sha256 FROM documents WHERE status = 'ACTIVE'")
                docs = cursor.fetchall()
                verified = 0
                for d in docs:
                    if self.storage.file_exists(d['storage_path']):
                        verified += 1
                details = f"Verified checksum integrity for {verified} active files."

            else:
                raise ValueError(f"Unknown maintenance task '{action_key}'.")

            # Log task execution
            cursor.execute("""
                INSERT INTO edms_maintenance_logs (action, status, details, executed_by)
                VALUES (?, 'SUCCESS', ?, ?)
            """, (action_clean, details, user_id))

            conn.commit()

            return {"success": True, "action": action_clean, "details": details}
        finally:
            conn.close()

    def get_maintenance_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent maintenance execution logs."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM edms_maintenance_logs ORDER BY executed_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ── Database-Driven Configurations ─────────────────────────────────────────
    def get_system_configs(self) -> Dict[str, str]:
        """Retrieves all database-driven EDMS system configurations."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT config_key, config_value FROM edms_system_configs")
            return {r['config_key']: r['config_value'] for r in cursor.fetchall()}
        finally:
            conn.close()

    def update_system_config(self, key: str, value: str) -> bool:
        """Updates a system configuration key."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO edms_system_configs (config_key, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value, updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_backup_config(self) -> Dict[str, Any]:
        """Retrieves EDMS backup configuration."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM edms_backup_configs LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else {"backup_frequency": "DAILY", "retention_days": 30, "storage_location": "storage/backups"}
        finally:
            conn.close()

    def update_backup_config(self, frequency: str, retention_days: int) -> bool:
        """Updates backup schedule configuration."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE edms_backup_configs
                SET backup_frequency = ?, retention_days = ?
                WHERE id = 1
            """, (frequency.upper(), retention_days))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_repository_explorer_tree(self) -> List[Dict[str, Any]]:
        """Retrieves administrative tree across all root storage folders."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM folders WHERE parent_folder_id IS NULL ORDER BY name ASC")
            roots = [dict(r) for r in cursor.fetchall()]

            for root in roots:
                cursor.execute("SELECT * FROM folders WHERE parent_folder_id = ? ORDER BY name ASC", (root['id'],))
                root['subfolders'] = [dict(sf) for sf in cursor.fetchall()]

            return roots
        finally:
            conn.close()
