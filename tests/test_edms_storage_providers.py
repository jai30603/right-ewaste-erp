import unittest
import json
import uuid
import sqlite3
from backend.app import app
from backend.database import get_connection, initialize_database
from backend.modules.documents.services.storage_service import EDMSStorageService, xor_decrypt
from backend.modules.documents.services.workspace_service import EDMSWorkspaceService

class EDMSStorageProvidersTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.storage_service = EDMSStorageService()
        cls.workspace_service = EDMSWorkspaceService()
        cls.app = app.test_client()
        
        cls.orig_csrf_enabled = app.config.get('WTF_CSRF_ENABLED')
        cls.orig_csrf_bypass = app.config.get('CSRF_BYPASS')
        cls.orig_auth_required = app.config.get('ERP_AUTH_REQUIRED')
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['CSRF_BYPASS'] = True
        app.config['ERP_AUTH_REQUIRED'] = True

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'orig_csrf_enabled') and cls.orig_csrf_enabled is not None:
            app.config['WTF_CSRF_ENABLED'] = cls.orig_csrf_enabled
        if hasattr(cls, 'orig_csrf_bypass') and cls.orig_csrf_bypass is not None:
            app.config['CSRF_BYPASS'] = cls.orig_csrf_bypass
        if hasattr(cls, 'orig_auth_required') and cls.orig_auth_required is not None:
            app.config['ERP_AUTH_REQUIRED'] = cls.orig_auth_required

    def setUp(self):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")
            # Deactivate all providers
            cursor.execute("UPDATE storage_providers SET is_active = 0, status = 'NOT_CONNECTED'")
            # Remove any test health or initializations
            cursor.execute("DELETE FROM storage_health")
            cursor.execute("DELETE FROM workspace_initialization")
            conn.commit()
        finally:
            conn.close()

    def test_admin_access_restricted(self):
        """Verify that non-Super Admin users cannot access Storage Providers routes."""
        # Test GET page as normal user
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 2, 'role': 'User', 'username': 'user2'}
            resp = c.get('/documents/storage-providers')
            self.assertEqual(resp.status_code, 302) # Redirect to mydrive
            self.assertIn('/documents/mydrive', resp.headers['Location'])

        # Test API endpoints as normal user
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 2, 'role': 'User', 'username': 'user2'}
            resp = c.get('/api/v1/documents/storage-providers')
            self.assertEqual(resp.status_code, 403)

    def test_super_admin_access_granted(self):
        """Verify that Super Admin users can successfully fetch Storage Providers list."""
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 1, 'role': 'Super Admin', 'username': 'admin'}
            resp = c.get('/api/v1/documents/storage-providers')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data['success'])
            self.assertGreater(len(data['providers']), 0)

    def test_save_and_obfuscate_credentials(self):
        """Verify that configuration is encrypted when saved and masked when retrieved."""
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 1, 'role': 'Super Admin', 'username': 'admin'}
            
            # Save test config for aws_s3 (id = 2)
            payload = {
                "provider_id": 2,
                "config": {
                    "aws_access_key_id": "test_access_key_123",
                    "aws_secret_access_key": "test_secret_key_456",
                    "aws_region": "ap-south-1",
                    "bucket_name": "test-bucket"
                }
            }
            resp = c.post('/api/v1/documents/storage-providers/save', 
                           data=json.dumps(payload), 
                           content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            
            # Retrieve provider config and verify keys are masked as '********'
            resp = c.get('/api/v1/documents/storage-providers')
            data = resp.get_json()
            aws_prov = next(p for p in data['providers'] if p['id'] == 2)
            self.assertEqual(aws_prov['config']['aws_access_key_id'], '********')
            self.assertEqual(aws_prov['config']['aws_secret_access_key'], '********')
            self.assertEqual(aws_prov['config']['aws_region'], 'ap-south-1')
            self.assertEqual(aws_prov['config']['bucket_name'], 'test-bucket')

            # Verify encrypted value in database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT config_json FROM storage_providers WHERE id = 2")
            crypt_json = cursor.fetchone()[0]
            conn.close()
            
            decrypted = xor_decrypt(crypt_json)
            config = json.loads(decrypted)
            self.assertEqual(config['aws_access_key_id'], 'test_access_key_123')
            self.assertEqual(config['aws_secret_access_key'], 'test_secret_key_456')

    def test_test_connection_validation(self):
        """Verify connection test updates health logs and status."""
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 1, 'role': 'Super Admin', 'username': 'admin'}
            
            payload = {
                "provider_id": 3, # Azure Blob
                "config": {
                    "account_name": "azure_test_acc",
                    "container_name": "azure_test_cont",
                    "account_key": "MOCK_AZURE_KEY"
                }
            }
            resp = c.post('/api/v1/documents/storage-providers/test', 
                           data=json.dumps(payload), 
                           content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            
            # Fetch providers and verify status updated to CONNECTED
            resp = c.get('/api/v1/documents/storage-providers')
            data = resp.get_json()
            azure_prov = next(p for p in data['providers'] if p['id'] == 3)
            self.assertEqual(azure_prov['status'], 'CONNECTED')
            self.assertEqual(azure_prov['health_status'], 'HEALTHY')

    def test_activate_and_provider_routing(self):
        """Verify that activating a provider routes EDMS calls dynamically."""
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 1, 'role': 'Super Admin', 'username': 'admin'}
            
            # First set connected status
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE storage_providers SET status = 'CONNECTED' WHERE id = 3")
            conn.commit()
            conn.close()
            
            # Activate Azure Blob provider
            resp = c.post('/api/v1/documents/storage-providers/activate', 
                           data=json.dumps({"provider_id": 3}), 
                           content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            
            # Verify active provider inside EDMSStorageService
            active_prov = self.storage_service.get_active_provider()
            from backend.modules.documents.providers.azure_storage_provider import AzureBlobStorageProvider
            self.assertIsInstance(active_prov, AzureBlobStorageProvider)

    def test_workspace_initialization_sync(self):
        """Verify that workspace initialization provisions storage structures for all existing users."""
        conn = get_connection()
        cursor = conn.cursor()
        # Seed an existing test user
        test_uuid = str(uuid.uuid4())
        cursor.execute("DELETE FROM users WHERE username = 'existing_test'")
        cursor.execute("""
            INSERT INTO users (employee_id, full_name, username, email, password_hash, erp_role, uuid, status)
            VALUES ('T-999', 'Existing Test User', 'existing_test', 'ex@test.com', 'p_hash', 'User', ?, 'ACTIVE')
        """, (test_uuid,))
        conn.commit()
        conn.close()

        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 1, 'role': 'Super Admin', 'username': 'admin'}
            
            resp = c.post('/api/v1/documents/storage-providers/initialize', 
                           data=json.dumps({"provider_id": 2, "config": {}}), 
                           content_type='application/json')
            self.assertEqual(resp.status_code, 200)

            # Check folders exist in db for user
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = 'existing_test'")
            uid = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM folders WHERE owner_user_id = ? AND path = ?", (uid, f"/users/{test_uuid}"))
            self.assertIsNotNone(cursor.fetchone())
            cursor.execute("SELECT id FROM folders WHERE owner_user_id = ? AND path = ?", (uid, f"/users/{test_uuid}/chatfiles"))
            self.assertIsNotNone(cursor.fetchone())
            conn.close()

    def test_future_user_auto_provisioning(self):
        """Verify that creating a new user dynamically provisions their My Drive and Chat Files folders."""
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user'] = {'user_id': 1, 'role': 'ADMIN', 'username': 'admin'}
            
            unique_username = f"new_test_user_{str(uuid.uuid4())[:8]}"
            payload = {
                "employee_id": "T-777",
                "full_name": "New Test User",
                "username": unique_username,
                "email": f"{unique_username}@test.com",
                "phone": "9999999999",
                "password": "SecurePassword123!",
                "erp_role": "VIEWER",
                "department": "IT",
                "designation": "Staff"
            }
            resp = c.post('/users/add', data=payload)
            self.assertEqual(resp.status_code, 302) # Redirects on successful user add

            # Verify that user has been created with a UUID and folders provisioned
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, uuid FROM users WHERE username = ?", (unique_username,))
            user_row = cursor.fetchone()
            self.assertIsNotNone(user_row)
            uid, u_uuid = user_row
            self.assertIsNotNone(u_uuid)
            
            # Check logical folders
            cursor.execute("SELECT id FROM folders WHERE owner_user_id = ? AND path = ?", (uid, f"/users/{u_uuid}"))
            self.assertIsNotNone(cursor.fetchone())
            cursor.execute("SELECT id FROM folders WHERE owner_user_id = ? AND path = ?", (uid, f"/users/{u_uuid}/chatfiles"))
            self.assertIsNotNone(cursor.fetchone())
            conn.close()

if __name__ == '__main__':
    unittest.main()
