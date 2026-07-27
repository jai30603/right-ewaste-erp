import unittest
import json
import sqlite3
from backend.app import app
from backend.database import get_connection

class TestCommunicationProduction(unittest.TestCase):
    def setUp(self):
        self.orig_csrf_enabled = app.config.get('WTF_CSRF_ENABLED')
        self.orig_csrf_bypass = app.config.get('CSRF_BYPASS')
        self.app = app.test_client()
        self.app.testing = True

        # Clear rate limit state in all imported module instances
        import sys
        for name, module in list(sys.modules.items()):
            if 'communication' in name:
                if hasattr(module, 'RATE_LIMIT_TIMESTAMPS'):
                    getattr(module, 'RATE_LIMIT_TIMESTAMPS').clear()

        # Session override
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
            cursor.execute("DELETE FROM messages WHERE content LIKE 'ProdTest%'")
            cursor.execute("DELETE FROM conversations WHERE name = 'Production Test Group'")
            
            # Create group
            cursor.execute("""
                INSERT INTO conversations (type, name, description, created_by, owner_id, status)
                VALUES ('GROUP', 'Production Test Group', 'Verifying production features', 1, 1, 'ACTIVE')
            """)
            self.test_group_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT OR IGNORE INTO conversation_participants (conversation_id, user_id, status)
                VALUES (?, 1, 'ACTIVE')
            """, (self.test_group_id,))

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

    def test_cursor_based_pagination(self):
        """Test that fetching messages supports before_id cursor limits."""
        # Insert 3 messages
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (conversation_id, sender_id, content) VALUES (?, 1, 'ProdTest Msg 1')", (self.test_group_id,))
            msg1_id = cursor.lastrowid
            cursor.execute("INSERT INTO messages (conversation_id, sender_id, content) VALUES (?, 1, 'ProdTest Msg 2')", (self.test_group_id,))
            msg2_id = cursor.lastrowid
            cursor.execute("INSERT INTO messages (conversation_id, sender_id, content) VALUES (?, 1, 'ProdTest Msg 3')", (self.test_group_id,))
            msg3_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        # Fetch messages before msg3_id
        res = self.app.get(f'/api/v1/communication/conversations/{self.test_group_id}/messages?before_id={msg3_id}&limit=2')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        # Should return msg1 and msg2
        self.assertEqual(len(data['messages']), 2)
        self.assertEqual(data['messages'][0]['id'], msg1_id)
        self.assertEqual(data['messages'][1]['id'], msg2_id)

    def test_message_creation_rate_limiting(self):
        """Test rate limiting prevents message spam (max 60 messages/min)."""
        # Call 60 times
        for i in range(60):
            res = self.app.post(f'/api/v1/communication/conversations/{self.test_group_id}/messages',
                                data=json.dumps({"content": f"ProdTest spam {i}"}),
                                content_type='application/json')
            self.assertEqual(res.status_code, 201)

        # 61st call should trigger 429 Too Many Requests
        res_limit = self.app.post(f'/api/v1/communication/conversations/{self.test_group_id}/messages',
                                  data=json.dumps({"content": "ProdTest final spam"}),
                                  content_type='application/json')
        self.assertEqual(res_limit.status_code, 429)

    def test_notification_preferences_endpoints(self):
        """Test getting and saving user notification preferences configuration."""
        # 1. Get preferences
        res_get = self.app.get('/api/v1/communication/preferences')
        self.assertEqual(res_get.status_code, 200)
        data_get = json.loads(res_get.data)
        self.assertTrue(data_get['success'])
        self.assertIn('preferences', data_get)

        # 2. Save preferences
        payload = {
            "messages": False,
            "mentions": True,
            "groups": False,
            "system_alerts": True
        }
        res_save = self.app.post('/api/v1/communication/preferences',
                                 data=json.dumps(payload),
                                 content_type='application/json')
        self.assertEqual(res_save.status_code, 200)
        
        # Verify saved preferences values
        res_verify = self.app.get('/api/v1/communication/preferences')
        data_verify = json.loads(res_verify.data)['preferences']
        self.assertFalse(data_verify['messages'])
        self.assertTrue(data_verify['mentions'])

    def test_admin_metrics_access_controls(self):
        """Test that Admin stats route restricts access based on Super Admin role."""
        # 1. Admin user role should pass
        res_admin = self.app.get('/api/v1/communication/admin/stats')
        self.assertEqual(res_admin.status_code, 200)
        self.assertTrue(json.loads(res_admin.data)['success'])

        # 2. Viewer user role should fail
        # Temporarily mock role VIEWER in database for user 1
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET erp_role = 'VIEWER' WHERE id = 1")
            conn.commit()
        finally:
            conn.close()

        try:
            res_viewer = self.app.get('/api/v1/communication/admin/stats')
            self.assertEqual(res_viewer.status_code, 403)
        finally:
            # Restore ADMIN
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET erp_role = 'ADMIN' WHERE id = 1")
                conn.commit()
            finally:
                conn.close()

if __name__ == '__main__':
    unittest.main()
