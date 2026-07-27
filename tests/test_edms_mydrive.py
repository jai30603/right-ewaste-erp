import io
import os
import sys
import uuid
import unittest
from pathlib import Path

# Adjust python path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database import initialize_database, get_connection
from backend.modules.documents.services.mydrive_service import MyDriveService
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.app import app

class EDMSMyDriveTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.mydrive_service = MyDriveService()
        self.doc_service = EnterpriseDocumentService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_workspace_auto_provisioning(self):
        workspace = self.mydrive_service.get_or_create_user_workspace(user_id=1)
        self.assertIsNotNone(workspace['id'])
        self.assertEqual(workspace['name'], 'My Drive')
        
        # Verify 8 default subfolders created
        subfolder_names = [f['name'] for f in workspace['subfolders']]
        self.assertIn("Documents", subfolder_names)
        self.assertIn("Images", subfolder_names)
        self.assertIn("Software", subfolder_names)
        self.assertIn("Archive", subfolder_names)

    def test_02_favorite_toggle_and_retrieval(self):
        # Upload a file
        unique_bytes = f"Favorite Test File {str(uuid.uuid4())}".encode('utf-8')
        doc = self.doc_service.upload_document(io.BytesIO(unique_bytes), "favorite_test.pdf", user_id=1)

        # Star document
        is_fav = self.mydrive_service.toggle_favorite(user_id=1, document_id=doc['id'])
        self.assertTrue(is_fav)

        # Retrieve favorites
        favs = self.mydrive_service.get_favorites(user_id=1)
        fav_doc_ids = [d['id'] for d in favs['documents']]
        self.assertIn(doc['id'], fav_doc_ids)

        # Unstar document
        is_fav_again = self.mydrive_service.toggle_favorite(user_id=1, document_id=doc['id'])
        self.assertFalse(is_fav_again)

    def test_03_recent_files_and_mydrive_search(self):
        token = str(uuid.uuid4())[:8]
        unique_bytes = f"Search Test Content {token}".encode('utf-8')
        doc = self.doc_service.upload_document(io.BytesIO(unique_bytes), f"search_{token}.pdf", user_id=1)

        # Recent files
        recents = self.mydrive_service.get_recent_files(user_id=1, limit=5)
        self.assertTrue(len(recents) > 0)

        # Search My Drive
        results = self.mydrive_service.search_mydrive(user_id=1, query=token, file_type='pdf')
        result_ids = [d['id'] for d in results]
        self.assertIn(doc['id'], result_ids)

    def test_04_mydrive_web_route_and_apis(self):
        # Test Web Route
        resp_web = self.app.get('/documents/mydrive')
        self.assertEqual(resp_web.status_code, 200)

        # Test Workspace REST API
        resp_ws = self.app.get('/api/v1/documents/mydrive/workspace')
        self.assertEqual(resp_ws.status_code, 200)
        data_ws = resp_ws.get_json()
        self.assertTrue(data_ws['success'])
        self.assertIn('workspace', data_ws)

        # Test Preview Data REST API
        unique_bytes = b"Text file preview payload content"
        doc = self.doc_service.upload_document(io.BytesIO(unique_bytes), "preview_test.txt", user_id=1)
        resp_prev = self.app.get(f'/api/v1/documents/{doc["id"]}/preview-data')
        self.assertEqual(resp_prev.status_code, 200)
        data_prev = resp_prev.get_json()
        self.assertTrue(data_prev['success'])
        self.assertEqual(data_prev['preview_type'], 'text')
        self.assertIn("preview payload", data_prev['content_text'])

    def test_05_user_creation_auto_provisioning(self):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            username = f"test_user_{uuid.uuid4().hex[:6]}"
            # Create user
            cursor.execute("""
                INSERT INTO users (employee_id, full_name, username, email, password_hash, erp_role, status)
                VALUES ('TEST', ?, ?, 'test@test.com', 'hash', 'VIEWER', 'ACTIVE')
            """, (username, username))
            user_id = cursor.lastrowid
            conn.commit()

            # Trigger auto-provisioning
            self.mydrive_service.provision_user_storage(user_id)

            # Check if user_storage was created
            cursor.execute("SELECT * FROM user_storage WHERE user_id = ?", (user_id,))
            us = cursor.fetchone()
            self.assertIsNotNone(us)

            # Check if storage_usage was created
            cursor.execute("SELECT * FROM storage_usage WHERE user_id = ?", (user_id,))
            usage = cursor.fetchone()
            self.assertIsNotNone(usage)

            # Check if My Drive folder was created
            cursor.execute("SELECT * FROM folders WHERE owner_user_id = ? AND name = 'My Drive'", (user_id,))
            folder = cursor.fetchone()
            self.assertIsNotNone(folder)
            self.assertEqual(folder['path'], f"/users/{user_id}")
        finally:
            conn.close()

    def test_06_folder_and_file_operations(self):
        # 1. Create a folder
        f1 = self.doc_service.create_folder("Folder One", folder_type='USER', user_id=1)
        self.assertEqual(f1['name'], "Folder One")

        # 2. Rename folder
        f1_renamed = self.doc_service.rename_folder(f1['id'], "Folder One Renamed", user_id=1)
        self.assertEqual(f1_renamed['name'], "Folder One Renamed")

        # 3. Create a subfolder
        sub = self.doc_service.create_folder("Subfolder", parent_folder_id=f1['id'], folder_type='USER', user_id=1)
        self.assertEqual(sub['parent_folder_id'], f1['id'])

        # 4. Move folder
        f2 = self.doc_service.create_folder("Folder Two", folder_type='USER', user_id=1)
        f2_moved = self.doc_service.move_folder(f2['id'], target_parent_id=f1['id'], user_id=1)
        self.assertEqual(f2_moved['parent_folder_id'], f1['id'])

        # 5. Upload document
        unique_bytes = b"Sample File Content"
        doc = self.doc_service.upload_document(io.BytesIO(unique_bytes), "sample.txt", folder_id=f1['id'], user_id=1)

        # 6. Copy file
        doc_copy = self.doc_service.copy_file(doc['id'], target_folder_id=f2['id'], user_id=1)
        self.assertEqual(doc_copy['folder_id'], f2['id'])
        self.assertEqual(doc_copy['original_name'], "Copy of sample.txt")

        # 7. Move file
        doc_moved = self.doc_service.move_file(doc['id'], target_folder_id=f2['id'], user_id=1)
        self.assertEqual(doc_moved['folder_id'], f2['id'])

    def test_07_recycle_bin_and_purges(self):
        f = self.doc_service.create_folder("Delete Me", folder_type='USER', user_id=1)
        doc = self.doc_service.upload_document(io.BytesIO(b"Delete me contents"), "delete_me.txt", folder_id=f['id'], user_id=1)

        # Soft delete folder (which soft deletes its files too)
        self.doc_service.soft_delete_folder(f['id'], user_id=1)

        # Retrieve trash
        trash = self.doc_service.get_trash_items(user_id=1)
        trash_folder_ids = [row['id'] for row in trash['folders']]
        trash_doc_ids = [row['id'] for row in trash['documents']]
        self.assertIn(f['id'], trash_folder_ids)
        self.assertIn(doc['id'], trash_doc_ids)

        # Restore folder
        self.doc_service.restore_folder(f['id'], user_id=1)
        
        # Verify restored
        trash_after = self.doc_service.get_trash_items(user_id=1)
        self.assertNotIn(f['id'], [row['id'] for row in trash_after['folders']])
        self.assertNotIn(doc['id'], [row['id'] for row in trash_after['documents']])

        # Empty trash
        self.doc_service.soft_delete_document(doc['id'], user_id=1)
        self.doc_service.empty_trash(user_id=1)
        trash_empty = self.doc_service.get_trash_items(user_id=1)
        self.assertEqual(len(trash_empty['folders']), 0)
        self.assertEqual(len(trash_empty['documents']), 0)

if __name__ == '__main__':
    unittest.main()
