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
from backend.modules.documents.providers.s3_storage_provider import AWSS3StorageProvider
from backend.modules.documents.managers.storage_provider_manager import StorageProviderManager
from backend.modules.documents.services.storage_migration_service import StorageMigrationService
from backend.modules.documents.services.document_service import EnterpriseDocumentService
from backend.app import app

class EDMSMultiCloudMigrationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.provider_mgr = StorageProviderManager()
        self.migration_service = StorageMigrationService(self.provider_mgr)
        self.doc_service = EnterpriseDocumentService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_s3_storage_provider_contract(self):
        s3_provider = AWSS3StorageProvider()
        test_payload = b"AWS S3 Contract Verification Content"

        # Upload
        up_res = s3_provider.upload_file(io.BytesIO(test_payload), "test/s3_contract.pdf")
        self.assertEqual(up_res['provider'], 's3')
        self.assertIsNotNone(up_res['checksum_sha256'])

        # Download
        down_stream = s3_provider.download_file("test/s3_contract.pdf")
        content = down_stream.read()
        self.assertEqual(content, test_payload)

        # Health Check
        health = s3_provider.health_check()
        self.assertEqual(health['status'], 'HEALTHY')

        # Delete
        del_ok = s3_provider.delete_file("test/s3_contract.pdf")
        self.assertTrue(del_ok)

    def test_02_storage_provider_manager_routing(self):
        # Resolve policy
        res = self.provider_mgr.resolve_provider_for_upload("COMPANY")
        self.assertIsNotNone(res['provider_id'])

        # Update routing policy
        upd_ok = self.provider_mgr.update_routing_policy("COMPANY", 2)
        self.assertTrue(upd_ok)

        res_s3 = self.provider_mgr.resolve_provider_for_upload("COMPANY")
        self.assertEqual(res_s3['provider_id'], 2)

        # Restore policy to 1
        self.provider_mgr.update_routing_policy("COMPANY", 1)

    def test_03_storage_migration_engine(self):
        token = str(uuid.uuid4())[:8]
        doc_bytes = f"Migration Test File Content {token}".encode('utf-8')
        doc = self.doc_service.upload_document(io.BytesIO(doc_bytes), f"mig_{token}.pdf", user_id=1)

        # Create Migration Job: Local (#1) -> AWS S3 (#2)
        job = self.migration_service.create_migration_job(
            job_name=f"Migrate_{token}",
            source_provider_id=1,
            destination_provider_id=2,
            user_id=1
        )
        self.assertIsNotNone(job['id'])

        # Execute Migration
        exec_job = self.migration_service.execute_migration_job(job['id'])
        self.assertEqual(exec_job['status'], 'COMPLETED')
        self.assertTrue(exec_job['processed_files'] >= 1)

    def test_04_multicloud_web_route_and_apis(self):
        # Web Route
        resp_web = self.app.get('/documents/multicloud')
        self.assertEqual(resp_web.status_code, 200)

        # Providers REST API
        resp_prov = self.app.get('/api/v1/documents/admin/providers')
        self.assertEqual(resp_prov.status_code, 200)

        # Test Provider API
        resp_test = self.app.post('/api/v1/documents/admin/providers/test', json={'provider_id': 2})
        self.assertEqual(resp_test.status_code, 200)

        # Policies REST API
        resp_pol = self.app.get('/api/v1/documents/admin/policies')
        self.assertEqual(resp_pol.status_code, 200)

if __name__ == '__main__':
    unittest.main()
