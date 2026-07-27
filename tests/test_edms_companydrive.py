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
from backend.modules.documents.services.companydrive_service import CompanyDriveService
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.app import app

class EDMSCompanyDriveTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.company_service = CompanyDriveService()
        self.doc_service = EnterpriseDocumentService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_company_workspace_auto_provisioning(self):
        workspace = self.company_service.get_or_create_company_workspace()
        self.assertIsNotNone(workspace['id'])
        self.assertEqual(workspace['name'], 'Company Drive')

        # Verify 15 default company subfolders created
        subfolder_names = [f['name'] for f in workspace['subfolders']]
        self.assertIn("Administration", subfolder_names)
        self.assertIn("Finance", subfolder_names)
        self.assertIn("Compliance", subfolder_names)
        self.assertIn("Certificates", subfolder_names)
        self.assertIn("Policies", subfolder_names)
        self.assertIn("SOPs", subfolder_names)
        self.assertIn("Software", subfolder_names)

    def test_02_company_quick_access_and_analytics(self):
        quick_folders = self.company_service.get_company_quick_access_folders()
        self.assertTrue(len(quick_folders) >= 5)

        analytics = self.company_service.get_company_storage_analytics()
        self.assertIn("total_company_files", analytics)
        self.assertIn("total_storage_mb", analytics)

    def test_03_company_drive_search(self):
        token = str(uuid.uuid4())[:8]
        unique_bytes = f"Company Policy File {token}".encode('utf-8')
        doc = self.doc_service.upload_document(io.BytesIO(unique_bytes), f"sop_{token}.pdf", user_id=1)

        results = self.company_service.search_company_drive(query=token, file_type='pdf')
        result_ids = [d['id'] for d in results]
        self.assertIn(doc['id'], result_ids)

    def test_04_companydrive_web_route_and_apis(self):
        # Test Web Route
        resp_web = self.app.get('/documents/companydrive')
        self.assertEqual(resp_web.status_code, 200)

        # Test Workspace REST API
        resp_ws = self.app.get('/api/v1/documents/companydrive/workspace')
        self.assertEqual(resp_ws.status_code, 200)
        data_ws = resp_ws.get_json()
        self.assertTrue(data_ws['success'])
        self.assertIn('workspace', data_ws)

        # Test Analytics REST API
        resp_ana = self.app.get('/api/v1/documents/companydrive/analytics')
        self.assertEqual(resp_ana.status_code, 200)
        data_ana = resp_ana.get_json()
        self.assertTrue(data_ana['success'])

if __name__ == '__main__':
    unittest.main()
