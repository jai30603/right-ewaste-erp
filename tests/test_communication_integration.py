import unittest
import json
import sqlite3
from datetime import datetime, timedelta
from backend.app import app
from backend.database import get_connection

class TestCommunicationIntegration(unittest.TestCase):
    def setUp(self):
        self.orig_csrf_enabled = app.config.get('WTF_CSRF_ENABLED')
        self.orig_csrf_bypass = app.config.get('CSRF_BYPASS')
        self.app = app.test_client()
        self.app.testing = True
        
        # Mock user login session details
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'user_id': 1,
                'username': 'admin',
                'role': 'ADMIN'
            }
            sess['_csrf_token'] = 'test-token'
            
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['CSRF_BYPASS'] = True

        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # Clean old test data
            cursor.execute("DELETE FROM messages WHERE content LIKE 'Shared resource%' OR content LIKE '[SYSTEM ALERT%'")
            cursor.execute("DELETE FROM shared_resources")
            cursor.execute("DELETE FROM conversations WHERE name = 'Integration Test Group'")
            cursor.execute("DELETE FROM module_registry WHERE module_name = 'TestBillingModule'")
            cursor.execute("DELETE FROM resource_registry WHERE resource_type = 'TEST_INVOICE'")
            
            # Insert Test Group
            cursor.execute("""
                INSERT INTO conversations (type, name, description, created_by, owner_id, status)
                VALUES ('GROUP', 'Integration Test Group', 'Testing Phase 4 integration features', 1, 1, 'ACTIVE')
            """)
            self.test_group_id = cursor.lastrowid
            
            # Add participant
            cursor.execute("""
                INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status)
                VALUES (?, 1, 'ACTIVE')
            """, (self.test_group_id,))

            # Seed a test document in EDMS
            cursor.execute("DELETE FROM documents WHERE original_name = 'integration_spec.pdf'")
            cursor.execute("""
                INSERT INTO documents (document_number, uuid, original_name, stored_name, extension, mime_type, size_bytes, checksum_sha256, storage_provider_id, storage_path, owner_user_id, status, classification)
                VALUES ('DOC-INT-001', 'uuid-int-001', 'integration_spec.pdf', 'integration_stored.pdf', 'pdf', 'application/pdf', 50000, 'sha256_val', 1, 'integration_spec.pdf', 1, 'ACTIVE', 'INTERNAL')
            """)
            self.test_doc_id = cursor.lastrowid

            cursor.close()
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        if self.orig_csrf_enabled is not None:
            app.config['WTF_CSRF_ENABLED'] = self.orig_csrf_enabled
        else:
            app.config.pop('WTF_CSRF_ENABLED', None)
            
        if self.orig_csrf_bypass is not None:
            app.config['CSRF_BYPASS'] = self.orig_csrf_bypass
        else:
            app.config.pop('CSRF_BYPASS', None)

    def test_module_and_resource_registration(self):
        """Test registering custom modules and resource types with the registry framework."""
        # 1. Register module
        payload_mod = {
            "module_name": "TestBillingModule",
            "module_icon": "bi bi-cash-coin",
            "config": {"description": "Custom test billing engine"}
        }
        res_mod = self.app.post('/api/v1/communication/modules/register',
                                data=json.dumps(payload_mod),
                                content_type='application/json')
        self.assertEqual(res_mod.status_code, 201)
        data_mod = json.loads(res_mod.data)
        self.assertTrue(data_mod['success'])

        # 2. Register resource type
        payload_res = {
            "resource_type": "TEST_INVOICE",
            "source_module": "TestBillingModule",
            "config": {"deep_link_template": "/billing/invoices/{id}"}
        }
        res_res = self.app.post('/api/v1/communication/resources/register',
                                data=json.dumps(payload_res),
                                content_type='application/json')
        self.assertEqual(res_res.status_code, 201)
        data_res = json.loads(res_res.data)
        self.assertTrue(data_res['success'])

    def test_generic_resource_sharing_engine(self):
        """Test sharing a generic registered resource using the resource reference engine."""
        payload = {
            "resource_type": "TEST_INVOICE",
            "resource_id": "TI-999",
            "display_title": "Test Invoice TI-999",
            "subtitle": "TestBillingModule",
            "preview_metadata": {"total": "120000 INR", "status": "UNPAID"},
            "deep_link": "/billing/invoices/999"
        }
        res = self.app.post(f'/api/v1/communication/conversations/{self.test_group_id}/share-resource-v2',
                            data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('shared_resource_id', data)

    def test_deep_linking_router_with_permissions(self):
        """Test that deep links validate roles and permissions correctly."""
        # Share a restricted resource first
        payload = {
            "resource_type": "PURCHASE_INVOICE",
            "resource_id": "101",
            "display_title": "Purchase Invoice PI-101",
            "subtitle": "Purchase Module",
            "preview_metadata": {"amount": "45000 INR"},
            "deep_link": "/purchase/invoices/101"
        }
        res_share = self.app.post(f'/api/v1/communication/conversations/{self.test_group_id}/share-resource-v2',
                                  data=json.dumps(payload),
                                  content_type='application/json')
        shared_ref_id = json.loads(res_share.data)['shared_resource_id']

        # 1. Access by Admin should pass (redirects to the deep link)
        res_open_admin = self.app.get(f'/api/v1/communication/resources/{shared_ref_id}/open')
        self.assertEqual(res_open_admin.status_code, 302) # Redirect
        self.assertIn('/purchase/invoices/101', res_open_admin.headers['Location'])

        # 2. Access by VIEWER role should fail
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET erp_role = 'VIEWER' WHERE id = 1")
            conn.commit()
        finally:
            conn.close()

        try:
            res_open_viewer = self.app.get(f'/api/v1/communication/resources/{shared_ref_id}/open')
            self.assertEqual(res_open_viewer.status_code, 403)
            self.assertIn('permission', json.loads(res_open_viewer.data)['error'].lower())
        finally:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET erp_role = 'ADMIN' WHERE id = 1")
                conn.commit()
            finally:
                conn.close()

    def test_shared_resources_history_v2(self):
        """Test retrieving list of shared resources inside a group conversation."""
        # Share document
        payload = {
            "resource_type": "DOCUMENT",
            "resource_id": str(self.test_doc_id),
            "display_title": "integration_spec.pdf",
            "subtitle": "EDMS Document",
            "preview_metadata": {"size": "50 KB"},
            "deep_link": f"/api/v1/documents/{self.test_doc_id}/download"
        }
        self.app.post(f'/api/v1/communication/conversations/{self.test_group_id}/share-resource-v2',
                      data=json.dumps(payload),
                      content_type='application/json')

        res = self.app.get(f'/api/v1/communication/conversations/{self.test_group_id}/shared-resources-v2')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['resources']), 1)
        self.assertEqual(data['resources'][0]['resource_type'], 'DOCUMENT')

    def test_advanced_categorized_search(self):
        """Test that advanced search returns results categorized by Messages, Groups, Users, and Resources."""
        # Seed a searchable message
        self.app.post(f'/api/v1/communication/conversations/{self.test_group_id}/messages',
                      data=json.dumps({"content": "Integration searchable string keyword"}),
                      content_type='application/json')

        res = self.app.get('/api/v1/communication/search-advanced?q=Integration')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('messages', data)
        self.assertIn('groups', data)
        self.assertIn('users', data)
        self.assertIn('resources', data)
        self.assertTrue(any(m['content'].contains("searchable") if hasattr(m['content'], "contains") else "searchable" in m['content'] for m in data['messages']))

    def test_dashboard_stats_api(self):
        """Test retrieving dashboard counters including direct messages and groups."""
        res = self.app.get('/api/v1/communication/dashboard-stats')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('unread_messages', data)
        self.assertIn('unread_direct', data)
        self.assertIn('unread_groups', data)
        self.assertIn('mentions', data)
        self.assertIn('shared_documents', data)

if __name__ == '__main__':
    unittest.main()
