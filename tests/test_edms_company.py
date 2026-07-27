import unittest
import io
import json
import uuid
import sqlite3
from typing import Dict, Any
from backend.app import app
from backend.database import get_connection, initialize_database
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.modules.documents.services.companydrive_service import CompanyDriveService
from backend.routes.documents import check_repository_permission

class EDMSCompanyStorageTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Assure database is initialized
        initialize_database()
        cls.doc_service = EnterpriseDocumentService()
        cls.company_service = CompanyDriveService()
        cls.app = app.test_client()

    def setUp(self):
        # Empty all company records to start fresh
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")
            # Delete folders in repository 2 except the root company drive workspace folder
            cursor.execute("SELECT id FROM folders WHERE path = '/company' AND repository_id = 2")
            root_row = cursor.fetchone()
            root_id = root_row['id'] if root_row else None
            
            if root_id:
                cursor.execute("DELETE FROM folders WHERE repository_id = 2 AND id != ?", (root_id,))
            else:
                cursor.execute("DELETE FROM folders WHERE repository_id = 2")
                
            cursor.execute("DELETE FROM documents WHERE repository_id = 2")
            cursor.execute("DELETE FROM recycle_bin WHERE repository_id = 2")
            
            # Reset company storage usage tracking
            cursor.execute("UPDATE company_storage_usage SET folders_count = 0, files_count = 0, bytes_used = 0 WHERE repository_id = 2")
            
            cursor.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
        finally:
            conn.close()

    def test_01_company_workspace_starts_completely_empty(self):
        """Verify that the Company Storage repository starts completely empty on creation."""
        workspace = self.company_service.get_or_create_company_workspace()
        self.assertEqual(workspace['path'], '/company')
        self.assertEqual(workspace['repository_id'], 2)
        # Verify subfolders is empty (no predefined HR, Finance folders!)
        self.assertEqual(len(workspace['subfolders']), 0)

        # Verify statistics return 0 items
        stats = self.doc_service.get_storage_statistics(repository_id=2)
        self.assertEqual(stats['total_active_files'], 0)
        self.assertEqual(stats['total_folders'], 0)
        self.assertEqual(stats['trash_files'], 0)
        self.assertEqual(stats['total_storage_used_bytes'], 0)

    def test_02_folder_crud_operations(self):
        """Verify folders can be created, renamed, moved, and copied in Company Storage."""
        # 1. Create root company folder
        f1 = self.doc_service.create_folder("Legal", folder_type='COMPANY', repository_id=2)
        self.assertEqual(f1['name'], "Legal")
        self.assertEqual(f1['repository_id'], 2)

        # 2. Rename folder
        f1_renamed = self.doc_service.rename_folder(f1['id'], "Legal & Compliance", user_id=1)
        self.assertEqual(f1_renamed['name'], "Legal _ Compliance")

        # 3. Create nested subfolder inheriting repository_id
        sub = self.doc_service.create_folder("Contracts", parent_folder_id=f1['id'], folder_type='COMPANY')
        self.assertEqual(sub['parent_folder_id'], f1['id'])
        self.assertEqual(sub['repository_id'], 2)

        # 4. Create another folder and move f1 inside it
        f2 = self.doc_service.create_folder("Admin", folder_type='COMPANY', repository_id=2)
        f1_moved = self.doc_service.move_folder(f1['id'], target_parent_id=f2['id'], user_id=1)
        self.assertEqual(f1_moved['parent_folder_id'], f2['id'])

    def test_03_file_upload_download_and_properties(self):
        """Verify documents can be uploaded, fetched, and previewed in Company Storage."""
        workspace = self.company_service.get_or_create_company_workspace()
        
        # 1. Upload a file to root
        unique_bytes = b"Company Policy Content 2026"
        doc = self.doc_service.upload_document(
            file_stream=io.BytesIO(unique_bytes),
            original_name="Policy.pdf",
            user_id=1,
            folder_id=workspace['id'],
            repository_id=2
        )
        self.assertEqual(doc['original_name'], "Policy.pdf")
        self.assertEqual(doc['repository_id'], 2)

        # 2. Get folder contents
        contents = self.doc_service.get_folder_contents(workspace['id'])
        doc_names = [d['original_name'] for d in contents['documents']]
        self.assertIn("Policy.pdf", doc_names)

        # 3. Verify statistics updated
        stats = self.doc_service.get_storage_statistics(repository_id=2)
        self.assertEqual(stats['total_active_files'], 1)
        self.assertEqual(stats['total_storage_used_bytes'], len(unique_bytes))

    def test_04_recycle_bin_independent_operations(self):
        """Verify soft-delete, restore, and purges operate independently in Company Storage."""
        workspace = self.company_service.get_or_create_company_workspace()
        f = self.doc_service.create_folder("Marketing", folder_type='COMPANY', repository_id=2)
        doc = self.doc_service.upload_document(
            file_stream=io.BytesIO(b"Marketing asset"),
            original_name="logo.png",
            user_id=1,
            folder_id=f['id'],
            repository_id=2
        )

        # 1. Soft delete
        self.doc_service.soft_delete_folder(f['id'], user_id=1)
        
        # 2. Retrieve trash for repository 2 (Company)
        trash = self.doc_service.get_trash_items(user_id=1, repository_id=2)
        trash_folder_ids = [row['id'] for row in trash['folders']]
        trash_doc_ids = [row['id'] for row in trash['documents']]
        self.assertIn(f['id'], trash_folder_ids)
        self.assertIn(doc['id'], trash_doc_ids)

        # Verify My Drive trash is unaffected
        mydrive_trash = self.doc_service.get_trash_items(user_id=1, repository_id=1)
        self.assertNotIn(f['id'], [row['id'] for row in mydrive_trash['folders']])

        # 3. Empty Trash
        self.doc_service.empty_trash(user_id=1, repository_id=2)
        
        # Verify completely deleted from company trash
        trash_empty = self.doc_service.get_trash_items(user_id=1, repository_id=2)
        self.assertEqual(len(trash_empty['folders']), 0)
        self.assertEqual(len(trash_empty['documents']), 0)

    def test_05_permission_architecture(self):
        """Verify role based permissions map successfully for My Drive vs Company Storage."""
        # Active session context mock is tested through check_repository_permission
        with app.test_request_context():
            # Setup session
            from flask import session
            session["user"] = {"role": "User", "user_id": 1, "username": "test_user"}
            
            # User can create/upload/download but cannot delete/move
            self.assertTrue(check_repository_permission(2, 'create'))
            self.assertTrue(check_repository_permission(2, 'upload'))
            self.assertTrue(check_repository_permission(2, 'download'))
            self.assertFalse(check_repository_permission(2, 'delete'))
            self.assertFalse(check_repository_permission(2, 'move'))

            # Super Admin has full rights
            session["user"]["role"] = "Super Admin"
            self.assertTrue(check_repository_permission(2, 'delete'))
            self.assertTrue(check_repository_permission(2, 'move'))

if __name__ == "__main__":
    unittest.main()
