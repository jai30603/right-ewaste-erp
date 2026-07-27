import unittest

from werkzeug.security import generate_password_hash

from backend.app import app
from backend.database import get_connection


class SecurityControlsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.original_config = {
            key: app.config.get(key)
            for key in (
                "ERP_AUTH_REQUIRED",
                "ERP_ADMIN_USERNAME",
                "ERP_ADMIN_PASSWORD_HASH",
                "ERP_OPERATOR_USERNAME",
                "ERP_OPERATOR_PASSWORD_HASH",
                "ERP_VIEWER_USERNAME",
                "ERP_VIEWER_PASSWORD_HASH",
            )
        }
        app.config.update(
            ERP_AUTH_REQUIRED=True,
            ERP_ADMIN_USERNAME="admin-test",
            ERP_ADMIN_PASSWORD_HASH=generate_password_hash("correct-password"),
            ERP_OPERATOR_USERNAME="",
            ERP_OPERATOR_PASSWORD_HASH="",
            ERP_VIEWER_USERNAME="",
            ERP_VIEWER_PASSWORD_HASH="",
        )

    def tearDown(self):
        app.config.update(self.original_config)

    def _csrf_token(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            return session["_csrf_token"]

    def _login_as_admin(self):
        token = self._csrf_token()
        response = self.client.post(
            "/login",
            data={
                "_csrf_token": token,
                "username": "admin-test",
                "password": "correct-password",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_requests_redirect_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_csrf_token_is_required_for_login_and_write_requests(self):
        response = self.client.post("/login", data={})
        self.assertEqual(response.status_code, 400)

        self._login_as_admin()
        response = self.client.post("/material/add", data={})
        self.assertEqual(response.status_code, 400)

    def test_viewers_cannot_change_data(self):
        token = self._csrf_token()
        with self.client.session_transaction() as session:
            session["user"] = {"username": "viewer-test", "role": "viewer"}

        response = self.client.post("/material/add", data={"_csrf_token": token})
        self.assertEqual(response.status_code, 403)

    def test_sqlite_foreign_keys_are_enabled_for_application_connections(self):
        conn = get_connection()
        try:
            enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(enabled, 1)


if __name__ == "__main__":
    unittest.main()
