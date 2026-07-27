import uuid
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider

DEFAULT_COMPANY_SUBFOLDERS = [
    "Administration",
    "Finance",
    "Human Resources",
    "Legal",
    "Compliance",
    "Certificates",
    "Reports",
    "Policies",
    "SOPs",
    "Templates",
    "Marketing",
    "Software",
    "Training",
    "Shared",
    "Archive"
]

QUICK_ACCESS_FOLDER_NAMES = [
    "Administration",
    "Finance",
    "Compliance",
    "Reports",
    "Software",
    "Training"
]

class CompanyDriveService:
    """Service to handle Organizational Workspace (Company Drive) operations for EDMS."""

    def __init__(self, storage_provider=None):
        self.storage = storage_provider or LocalStorageProvider()

    def get_or_create_company_workspace(self) -> Dict[str, Any]:
        """Provisions root Company Drive folder (repository 2) without any default subfolders."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            company_path = "/company"

            # 1. Check or create root Company Drive folder
            cursor.execute("SELECT * FROM folders WHERE path = ? AND folder_type = 'COMPANY' AND repository_id = 2", (company_path,))
            root_folder = cursor.fetchone()

            if not root_folder:
                folder_uuid = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by, repository_id)
                    VALUES (?, 'Company Drive', NULL, 'COMPANY', 1, ?, 'ACTIVE', 1, 2)
                """, (folder_uuid, company_path))
                root_id = cursor.lastrowid
                self.storage.create_folder(company_path)
            else:
                root_id = root_folder['id']

            # Query existing subfolders dynamically
            cursor.execute("SELECT * FROM folders WHERE parent_folder_id = ? AND status = 'ACTIVE' ORDER BY name ASC", (root_id,))
            subfolders = [dict(r) for r in cursor.fetchall()]

            conn.commit()

            cursor.execute("SELECT * FROM folders WHERE id = ?", (root_id,))
            root_dict = dict(cursor.fetchone())
            root_dict['subfolders'] = subfolders
            return root_dict
        finally:
            conn.close()

    def get_company_quick_access_folders(self) -> List[Dict[str, Any]]:
        """Returns quick access folder shortcuts for Company Drive."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            workspace = self.get_or_create_company_workspace()
            root_id = workspace['id']

            placeholders = ','.join(['?'] * len(QUICK_ACCESS_FOLDER_NAMES))
            cursor.execute(f"""
                SELECT * FROM folders
                WHERE parent_folder_id = ? AND name IN ({placeholders}) AND status = 'ACTIVE'
                ORDER BY name ASC
            """, [root_id] + QUICK_ACCESS_FOLDER_NAMES)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_company_storage_analytics(self) -> Dict[str, Any]:
        """Calculates storage analytics and largest files for Company Drive."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            workspace = self.get_or_create_company_workspace()
            root_id = workspace['id']

            # Total company active files & size
            cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_bytes
                FROM documents
                WHERE status = 'ACTIVE'
            """)
            active = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) as count FROM folders WHERE folder_type = 'COMPANY' AND status = 'ACTIVE'")
            folders_count = cursor.fetchone()['count']

            # Largest company files
            cursor.execute("""
                SELECT d.*, f.name as folder_name
                FROM documents d
                LEFT JOIN folders f ON d.folder_id = f.id
                WHERE d.status = 'ACTIVE'
                ORDER BY d.size_bytes DESC LIMIT 5
            """)
            largest_files = [dict(r) for r in cursor.fetchall()]

            total_bytes = active['total_bytes']
            total_files = active['count']

            return {
                "total_company_files": total_files,
                "total_company_folders": folders_count,
                "total_storage_bytes": total_bytes,
                "total_storage_mb": round(total_bytes / (1024 * 1024), 2),
                "largest_files": largest_files
            }
        finally:
            conn.close()

    def search_company_drive(
        self,
        query: Optional[str] = None,
        file_type: Optional[str] = None,
        folder_id: Optional[int] = None,
        sort_by: str = 'name',
        sort_order: str = 'asc'
    ) -> List[Dict[str, Any]]:
        """Searches and filters active files inside Company Drive."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT d.*, f.name as folder_name,
                       (SELECT 1 FROM document_favorites df WHERE df.document_id = d.id AND df.user_id = 1) as is_favorite
                FROM documents d
                LEFT JOIN folders f ON d.folder_id = f.id
                WHERE d.status = 'ACTIVE' AND d.repository_id = 2
            """
            params = {}

            if query and query.strip():
                sql += " AND (d.original_name LIKE :q OR d.description LIKE :q OR d.document_number LIKE :q)"
                params["q"] = f"%{query.strip()}%"

            if folder_id:
                sql += " AND d.folder_id = :fid"
                params["fid"] = folder_id

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

            valid_sorts = {
                'name': 'd.original_name',
                'date': 'd.created_at',
                'size': 'd.size_bytes',
                'type': 'd.extension'
            }
            order_col = valid_sorts.get(sort_by.lower(), 'd.original_name')
            order_dir = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
            sql += f" ORDER BY {order_col} {order_dir}"

            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
