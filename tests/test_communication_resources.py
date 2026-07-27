import unittest
import json
import sqlite3
from datetime import datetime, timedelta
from backend.app import app
from backend.database import get_connection

class TestCommunicationResources(unittest.TestCase):
    def setUp(self):
        self.orig_csrf_enabled = app.config.get('WTF_CSRF_ENABLED')
        self.orig_csrf_bypass = app.config.get('CSRF_BYPASS')
        self.app = app.test_client()
        self.app.testing = True
        
        # Enable session override by mocking the user login
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'user_id': 1,
                'username': 'admin',
                'role': 'ADMIN'
            }
            sess['_csrf_token'] = 'test-token'
            
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['CSRF_BYPASS'] = True

        # Ensure test direct & group channels are seeded
        conn = get_connection()
        try:
            cursor = conn.cursor()
            # Clean up old testing records
            cursor.execute("DELETE FROM messages WHERE content LIKE 'Test Resource%' OR content LIKE '[SYSTEM ALERT%'")
            cursor.execute("DELETE FROM resource_references")
            cursor.execute("DELETE FROM document_references")
            cursor.execute("DELETE FROM task_references")
            cursor.execute("DELETE FROM location_references")
            cursor.execute("DELETE FROM system_messages")
            cursor.execute("DELETE FROM conversations WHERE name = 'Resource Share Group'")
            
            # Insert test group conversation (owned by user_id = 1)
            cursor.execute("""
                INSERT INTO conversations (type, name, description, created_by, owner_id, status)
                VALUES ('GROUP', 'Resource Share Group', 'Testing resource sharing and group controls', 1, 1, 'ACTIVE')
            """)
            self.test_group_id = cursor.lastrowid
            
            # Add participant
            cursor.execute("""
                INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status)
                VALUES (?, 1, 'ACTIVE')
            """, (self.test_group_id,))
            # Seed test document
            cursor.execute("DELETE FROM documents WHERE original_name = 'test_spec.pdf'")
            cursor.execute("""
                INSERT INTO documents (document_number, uuid, original_name, stored_name, extension, mime_type, size_bytes, checksum_sha256, storage_provider_id, storage_path, owner_user_id, status, classification)
                VALUES ('DOC-TEST-001', 'test-uuid-val-001', 'test_spec.pdf', 'test_spec_stored.pdf', 'pdf', 'application/pdf', 1048576, 'dummy_checksum', 1, 'test_spec.pdf', 1, 'ACTIVE', 'INTERNAL')
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

    def test_share_document_resource(self):
        """Test sharing an EDMS document in the chat."""
        payload = {
            "resource_type": "DOCUMENT",
            "document_id": self.test_doc_id
        }
        res = self.app.post(
            f"/api/v1/communication/conversations/{self.test_group_id}/share-resource",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])

        # Verify database logs
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_references WHERE message_id = ?", (data["message_id"],))
            ref = cursor.fetchone()
            self.assertIsNotNone(ref)
            self.assertEqual(ref["document_id"], self.test_doc_id)
        finally:
            conn.close()

    def test_share_task_resource(self):
        """Test sharing a task reference in the chat."""
        payload = {
            "resource_type": "TASK",
            "task_id": 104
        }
        res = self.app.post(
            f"/api/v1/communication/conversations/{self.test_group_id}/share-resource",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_references WHERE message_id = ?", (data["message_id"],))
            ref = cursor.fetchone()
            self.assertIsNotNone(ref)
            self.assertEqual(ref["task_id"], 104)
        finally:
            conn.close()

    def test_share_location_resource(self):
        """Test sharing coordinates and label in the chat."""
        payload = {
            "resource_type": "LOCATION",
            "address": "Andheri East Collection Center",
            "latitude": 19.1155,
            "longitude": 72.8751
        }
        res = self.app.post(
            f"/api/v1/communication/conversations/{self.test_group_id}/share-resource",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM location_references WHERE message_id = ?", (data["message_id"],))
            ref = cursor.fetchone()
            self.assertIsNotNone(ref)
            self.assertEqual(ref["latitude"], 19.1155)
            self.assertEqual(ref["address"], "Andheri East Collection Center")
        finally:
            conn.close()

    def test_document_permission_validation(self):
        """Test that document open route validates access correctly."""
        # 1. Access granted for owner (user_id = 1)
        res = self.app.get(f"/api/v1/communication/documents/{self.test_doc_id}/open")
        self.assertEqual(res.status_code, 302) # Redirect to download

        # 2. Denied access when user is a non-owner/non-admin
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'user_id': 999,
                'username': 'operator',
                'role': 'OPERATOR'
            }
        res = self.app.get(f"/api/v1/communication/documents/{self.test_doc_id}/open")
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data)
        self.assertFalse(data["success"])
        self.assertIn("You do not have permission", data["error"])

    def test_group_ownership_locks(self):
        """Test that only group owner or admin can edit details or add/remove members."""
        # Authenticated as non-owner (user_id = 2)
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'user_id': 2,
                'username': 'rahul',
                'role': 'OPERATOR'
            }
        
        # Attempt to edit group details
        payload = {
            "name": "Modified Group Name",
            "description": "Illegal edit"
        }
        res = self.app.put(
            f"/api/v1/communication/groups/{self.test_group_id}",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data)
        self.assertFalse(data["success"])

    def test_automated_system_alerts(self):
        """Test external module auto alerts publishing into targeted groups."""
        payload = {
            "event_type": "PURCHASE",
            "content": "Purchase Invoice PI-001 Created.",
            "group_name": "Resource Share Group"
        }
        res = self.app.post(
            "/api/v1/communication/system-messages",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])

        # Check database persistence
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_messages WHERE conversation_id = ?", (self.test_group_id,))
            msg = cursor.fetchone()
            self.assertIsNotNone(msg)
            self.assertEqual(msg["event_type"], "PURCHASE")
            self.assertEqual(msg["content"], "Purchase Invoice PI-001 Created.")
        finally:
            conn.close()

    def test_dashboard_stats_aggregation(self):
        """Test retrieving correct communication metrics for current user dashboard integration."""
        res = self.app.get("/api/v1/communication/dashboard-stats")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIn("unread_messages", data)
        self.assertIn("mentions", data)
        self.assertIn("shared_documents", data)
        self.assertIn("pending_tasks", data)

if __name__ == "__main__":
    unittest.main()
