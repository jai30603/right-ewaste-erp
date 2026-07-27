import unittest
import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

# Insert backend directory in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection
from security_core import auth_service, permission_service, config_service

class SecurityCoreTest(unittest.TestCase):
    def setUp(self):
        # We will insert a test user into the live db for isolated testing
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        
        # Clean existing test user if any
        self.cursor.execute("DELETE FROM users WHERE username = 'test_security_user'")
        
        # Insert fresh test user
        self.password_raw = "password123"
        self.p_hash = generate_password_hash(self.password_raw)
        self.cursor.execute("""
            INSERT INTO users (employee_id, full_name, username, email, password_hash, erp_role, status)
            VALUES ('EMP-TEST', 'Test User', 'test_security_user', 'test@example.com', ?, 'OPERATOR', 'ACTIVE')
        """, (self.p_hash,))
        self.user_id = self.cursor.lastrowid
        
        # Seed password history
        self.cursor.execute("INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)", (self.user_id, self.p_hash))
        
        self.conn.commit()

    def tearDown(self):
        # Clean up test records
        self.cursor.execute("DELETE FROM users WHERE username = 'test_security_user'")
        self.cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (self.user_id,))
        self.cursor.execute("DELETE FROM password_history WHERE user_id = ?", (self.user_id,))
        self.cursor.execute("DELETE FROM login_history WHERE user_id = ?", (self.user_id,))
        self.conn.commit()
        self.conn.close()

    def test_successful_authentication(self):
        session_data, error = auth_service.authenticate_user("test_security_user", self.password_raw)
        self.assertIsNotNone(session_data)
        self.assertNil(error)
        self.assertEqual(session_data["username"], "test_security_user")
        self.assertEqual(session_data["role"], "OPERATOR")
        self.assertIsNotNone(session_data["session_token"])

    def test_failed_authentication_and_locking(self):
        # 1. Failed attempt with invalid password
        session_data, error = auth_service.authenticate_user("test_security_user", "wrong_password")
        self.assertIsNone(session_data)
        self.assertEqual(error, "Invalid username or password.")
        
        # 2. Lock account on 5 consecutive failures
        for _ in range(4):
            auth_service.authenticate_user("test_security_user", "wrong_password")
            
        # 3. Next attempt should show locked error
        session_data, error = auth_service.authenticate_user("test_security_user", self.password_raw)
        self.assertIsNone(session_data)
        self.assertIn("locked", error.lower())

    def test_session_validation_and_revocation(self):
        session_data, error = auth_service.authenticate_user("test_security_user", self.password_raw)
        token = session_data["session_token"]
        
        # Validate active session
        val = auth_service.validate_session(token)
        self.assertIsNotNone(val)
        self.assertEqual(val["username"], "test_security_user")
        
        # Revoke session
        auth_service.invalidate_session(token)
        val_after = auth_service.validate_session(token)
        self.assertIsNone(val_after)

    def test_password_history_constraints(self):
        # Change password to new value
        err1 = auth_service.change_password(self.user_id, self.password_raw, "new_pass_123", "test_security_user")
        self.assertNil(err1)
        
        # Try to change back to old password (should fail due to history)
        err2 = auth_service.change_password(self.user_id, "new_pass_123", self.password_raw, "test_security_user")
        self.assertIsNotNone(err2)
        self.assertIn("reuse", err2.lower())

    def test_permission_service(self):
        # Check standard operators permission map (seeded in migration)
        # Operator has view_purchase permission
        has_view = permission_service.has_permission("OPERATOR", "Purchase", "VIEW_PURCHASE")
        self.assertTrue(has_view)
        
        # Operator does NOT have settings permission
        has_settings = permission_service.has_permission("OPERATOR", "Settings", "VIEW_SETTINGS")
        self.assertFalse(has_settings)
        
        # Admin has settings permission
        has_admin_settings = permission_service.has_permission("ADMIN", "Settings", "VIEW_SETTINGS")
        self.assertTrue(has_admin_settings)

    def assertNil(self, val):
        self.assertIsNone(val)

if __name__ == "__main__":
    unittest.main()
