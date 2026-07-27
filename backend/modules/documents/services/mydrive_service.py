import uuid
from typing import Dict, Any, List, Optional
from backend.database import get_connection
from backend.modules.documents.services.storage_service import EDMSStorageService
from backend.modules.documents.validators.document_validator import DocumentValidator

DEFAULT_MYDRIVE_SUBFOLDERS = [
    "Documents",
    "Images",
    "Software",
    "Downloads",
    "Personal",
    "Templates",
    "Notes",
    "Archive"
]

class MyDriveService:
    """Service to handle Personal Workspace (My Drive) operations for EDMS."""

    def __init__(self, storage_provider=None):
        self.storage = storage_provider or EDMSStorageService()

    def provision_user_storage(self, user_id: int) -> bool:
        """Provisions personal user_storage, storage_usage, and root My Drive folders for a new user."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # 1. Create user_storage entry
            cursor.execute("INSERT OR IGNORE INTO user_storage (user_id) VALUES (?)", (user_id,))
            # 2. Create storage_usage entry
            cursor.execute("INSERT OR IGNORE INTO storage_usage (user_id) VALUES (?)", (user_id,))
            conn.commit()
            
            # 3. Create My Drive folder structure
            self.get_or_create_user_workspace(user_id)
            return True
        except Exception as e:
            print(f"Error provisioning user storage: {e}")
            return False
        finally:
            conn.close()

    def get_or_create_user_workspace(self, user_id: int = 1) -> Dict[str, Any]:
        """Provisions root My Drive folder and default subfolders for user if not existing."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT uuid FROM users WHERE id = ?", (user_id,))
            u_row = cursor.fetchone()
            u_uuid = u_row[0] if (u_row and u_row[0]) else str(user_id)
            user_path = f"/users/{u_uuid}"

            # 1. Check or create root My Drive folder
            cursor.execute("SELECT * FROM folders WHERE path = ? AND folder_type = 'USER'", (user_path,))
            root_folder = cursor.fetchone()

            if not root_folder:
                folder_uuid = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by)
                    VALUES (?, 'My Drive', NULL, 'USER', ?, ?, 'ACTIVE', ?)
                """, (folder_uuid, user_id, user_path, user_id))
                root_id = cursor.lastrowid
                self.storage.create_folder(user_path)

                # Also create Chat Files logical and physical folder
                chat_uuid = str(uuid.uuid4())
                chat_path = f"{user_path}/chatfiles"
                cursor.execute("""
                    INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by, repository_id)
                    VALUES (?, 'Chat Files', NULL, 'USER', ?, ?, 'ACTIVE', ?, 3)
                """, (chat_uuid, user_id, chat_path, user_id))
                self.storage.create_folder(chat_path)
            else:
                root_id = root_folder['id']

            # 2. Provision default subfolders
            subfolders = []
            for sub_name in DEFAULT_MYDRIVE_SUBFOLDERS:
                sub_path = f"{user_path}/{sub_name.lower()}"
                cursor.execute("SELECT * FROM folders WHERE parent_folder_id = ? AND name = ?", (root_id, sub_name))
                sub_row = cursor.fetchone()
                if not sub_row:
                    sub_uuid = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO folders (uuid, name, parent_folder_id, folder_type, owner_user_id, path, status, created_by)
                        VALUES (?, ?, ?, 'USER', ?, ?, 'ACTIVE', ?)
                    """, (sub_uuid, sub_name, root_id, user_id, sub_path, user_id))
                    sub_id = cursor.lastrowid
                    self.storage.create_folder(sub_path)
                    cursor.execute("SELECT * FROM folders WHERE id = ?", (sub_id,))
                    sub_row = cursor.fetchone()

                subfolders.append(dict(sub_row))

            conn.commit()

            cursor.execute("SELECT * FROM folders WHERE id = ?", (root_id,))
            root_dict = dict(cursor.fetchone())
            root_dict['subfolders'] = subfolders
            return root_dict
        finally:
            conn.close()

    def toggle_favorite(self, user_id: int = 1, document_id: Optional[int] = None, folder_id: Optional[int] = None) -> bool:
        """Stars or unstars a document or folder for the given user."""
        if not document_id and not folder_id:
            raise ValueError("Either document_id or folder_id must be provided")

        conn = get_connection()
        try:
            cursor = conn.cursor()
            if document_id:
                cursor.execute("SELECT id FROM document_favorites WHERE user_id = ? AND document_id = ?", (user_id, document_id))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("DELETE FROM document_favorites WHERE id = ?", (existing['id'],))
                    is_fav = False
                else:
                    cursor.execute("INSERT INTO document_favorites (user_id, document_id) VALUES (?, ?)", (user_id, document_id))
                    is_fav = True
            else:
                cursor.execute("SELECT id FROM document_favorites WHERE user_id = ? AND folder_id = ?", (user_id, folder_id))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("DELETE FROM document_favorites WHERE id = ?", (existing['id'],))
                    is_fav = False
                else:
                    cursor.execute("INSERT INTO document_favorites (user_id, folder_id) VALUES (?, ?)", (user_id, folder_id))
                    is_fav = True

            conn.commit()
            return is_fav
        finally:
            conn.close()

    def get_favorites(self, user_id: int = 1) -> Dict[str, Any]:
        """Fetches all favorited files and folders for user."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, f.name as folder_name, 1 as is_favorite
                FROM document_favorites df
                JOIN documents d ON df.document_id = d.id
                LEFT JOIN folders f ON d.folder_id = f.id
                WHERE df.user_id = ? AND d.status = 'ACTIVE'
                ORDER BY df.created_at DESC
            """, (user_id,))
            fav_docs = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT f.*, 1 as is_favorite
                FROM document_favorites df
                JOIN folders f ON df.folder_id = f.id
                WHERE df.user_id = ? AND f.status = 'ACTIVE'
                ORDER BY df.created_at DESC
            """, (user_id,))
            fav_folders = [dict(r) for r in cursor.fetchall()]

            return {"documents": fav_docs, "folders": fav_folders}
        finally:
            conn.close()

    def get_recent_files(self, user_id: int = 1, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches recently created/uploaded files for user."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, f.name as folder_name,
                       (SELECT 1 FROM document_favorites df WHERE df.document_id = d.id AND df.user_id = ?) as is_favorite
                FROM documents d
                LEFT JOIN folders f ON d.folder_id = f.id
                WHERE d.owner_user_id = ? AND d.status = 'ACTIVE'
                ORDER BY d.created_at DESC LIMIT ?
            """, (user_id, user_id, limit))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def search_mydrive(
        self,
        user_id: int = 1,
        query: Optional[str] = None,
        file_type: Optional[str] = None,
        folder_id: Optional[int] = None,
        sort_by: str = 'name',
        sort_order: str = 'asc'
    ) -> List[Dict[str, Any]]:
        """Searches and filters active files inside My Drive."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT d.*, f.name as folder_name,
                       (SELECT 1 FROM document_favorites df WHERE df.document_id = d.id AND df.user_id = :uid) as is_favorite
                FROM documents d
                LEFT JOIN folders f ON d.folder_id = f.id
                WHERE d.owner_user_id = :uid AND d.status = 'ACTIVE' AND d.repository_id = 1
            """
            params = {"uid": user_id}

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

            # Sorting
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
