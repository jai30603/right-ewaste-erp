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
from backend.modules.documents.providers.local_storage_provider import LocalStorageProvider
from backend.modules.documents.validators.document_validator import DocumentValidator
from backend.modules.documents.services.duplicate_service import DuplicateDetector
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.app import app

class EDMSFoundationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.storage = LocalStorageProvider()
        self.doc_service = EnterpriseDocumentService(storage_provider=self.storage)

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_local_storage_provider(self):
        sample_data = b"Hello Right Ewaste ERP EDMS Foundation"
        file_stream = io.BytesIO(sample_data)
        key = "temp/test_sample_01.txt"

        # Upload
        uploaded_key = self.storage.upload_file(file_stream, key)
        self.assertEqual(uploaded_key, key)
        self.assertTrue(self.storage.file_exists(key))

        # Download & Check Content
        downloaded_stream = self.storage.download_file(key)
        self.assertEqual(downloaded_stream.read(), sample_data)

        # Move
        new_key = "company/test_sample_01_moved.txt"
        self.storage.move_file(key, new_key)
        self.assertFalse(self.storage.file_exists(key))
        self.assertTrue(self.storage.file_exists(new_key))

        # Delete
        self.storage.delete_file(new_key)
        self.assertFalse(self.storage.file_exists(new_key))

    def test_02_document_validator(self):
        # Valid PDF
        valid, msg = DocumentValidator.validate_upload("factory_report.pdf", 1024)
        self.assertTrue(valid)

        # Executable extension rejection
        valid, msg = DocumentValidator.validate_upload("malware.exe", 2048)
        self.assertFalse(valid)
        self.assertIn("Security Violation", msg)

        # Empty file rejection
        valid, msg = DocumentValidator.validate_upload("empty.txt", 0)
        self.assertFalse(valid)
        self.assertIn("empty file", msg)

    def test_03_document_upload_duplicate_softdelete_restore(self):
        unique_token = str(uuid.uuid4())
        sample_bytes = f"EDMS Document Unique Content {unique_token} Batch Test".encode('utf-8')
        file_stream = io.BytesIO(sample_bytes)
        filename = "recycle_cert_001.pdf"

        # 1. Upload Document
        doc = self.doc_service.upload_document(file_stream, filename, user_id=1, description="Test Certificate")
        self.assertIsNotNone(doc['id'])
        self.assertEqual(doc['original_name'], filename)
        self.assertFalse(doc['is_duplicate'])

        # 2. Upload Identical Document (Duplicate Check)
        duplicate_stream = io.BytesIO(sample_bytes)
        dup_doc = self.doc_service.upload_document(duplicate_stream, "recycle_cert_001_copy.pdf", user_id=1)
        self.assertTrue(dup_doc['is_duplicate'])
        self.assertIsNotNone(dup_doc['duplicate_warning'])

        # 3. Soft Delete to Trash
        delete_success = self.doc_service.soft_delete_document(doc['id'], user_id=1)
        self.assertTrue(delete_success)

        # Verify status is TRASH
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT status FROM documents WHERE id = ?", (doc['id'],))
        self.assertEqual(c.fetchone()['status'], 'TRASH')
        conn.close()

        # 4. Restore Document from Trash
        restore_success = self.doc_service.restore_document(doc['id'], user_id=1)
        self.assertTrue(restore_success)

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT status FROM documents WHERE id = ?", (doc['id'],))
        self.assertEqual(c.fetchone()['status'], 'ACTIVE')
        conn.close()

    def test_04_folder_creation_and_contents(self):
        folder_name = f"Compliance Certificates {str(uuid.uuid4())[:8]}"
        folder = self.doc_service.create_folder(folder_name, parent_folder_id=None, folder_type="COMPANY")
        self.assertIsNotNone(folder['id'])
        self.assertEqual(folder['name'], folder_name)

        contents = self.doc_service.get_folder_contents(folder['id'])
        self.assertIsNotNone(contents['current_folder'])
        self.assertEqual(contents['current_folder']['id'], folder['id'])

    def test_05_storage_statistics_and_rest_api(self):
        # Test Stats Service
        stats = self.doc_service.get_storage_statistics()
        self.assertIn("total_active_files", stats)
        self.assertIn("total_storage_used_bytes", stats)

        # Test REST API Stats
        resp = self.app.get('/api/v1/documents/stats')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('stats', data)

        # Test REST API Upload
        api_bytes = f"REST API Upload File Stream {str(uuid.uuid4())}".encode('utf-8')
        resp_upload = self.app.post(
            '/api/v1/documents/upload',
            data={
                'file': (io.BytesIO(api_bytes), "api_test.pdf"),
                'description': 'REST Upload Test'
            }
        )
        if resp_upload.status_code != 201:
            print("UPLOAD API FAIL RESPONSE:", resp_upload.get_json())
        self.assertEqual(resp_upload.status_code, 201)
        res_json = resp_upload.get_json()
        self.assertTrue(res_json['success'])
        doc_id = res_json['document']['id']

        # Test REST API Download
        resp_dl = self.app.get(f'/api/v1/documents/{doc_id}/download')
        self.assertEqual(resp_dl.status_code, 200)

        # Test REST API Delete
        resp_del = self.app.delete(f'/api/v1/documents/{doc_id}')
        self.assertEqual(resp_del.status_code, 200)

if __name__ == '__main__':
    unittest.main()
