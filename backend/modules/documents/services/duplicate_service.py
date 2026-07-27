from typing import Optional, Dict, Any
from backend.database import get_connection

class DuplicateDetector:
    """Service to detect duplicate content via SHA-256 checksums."""

    @staticmethod
    def check_duplicate_by_hash(checksum_sha256: str) -> Optional[Dict[str, Any]]:
        """Checks if an active document with the identical SHA-256 hash exists in database."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.id, d.document_number, d.uuid, d.original_name, d.size_bytes, d.folder_id, f.name as folder_name
                FROM documents d
                LEFT JOIN folders f ON d.folder_id = f.id
                WHERE d.checksum_sha256 = ? AND d.status = 'ACTIVE'
                ORDER BY d.id ASC LIMIT 1
            """, (checksum_sha256,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
