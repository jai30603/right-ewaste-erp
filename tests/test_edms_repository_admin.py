import io
import os
import sys
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
from backend.modules.documents.services.repository_admin_service import RepositoryAdminService
from backend.app import app

class EDMSRepositoryAdminTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self.orig_csrf_bypass = app.config.get("CSRF_BYPASS")
        app.config["CSRF_BYPASS"] = True
        app.config["TESTING"] = True
        self.app = app.test_client()
        self.app.testing = True
        self.repo_service = RepositoryAdminService()

    def tearDown(self):
        if self.orig_csrf_bypass is None:
            app.config.pop("CSRF_BYPASS", None)
        else:
            app.config["CSRF_BYPASS"] = self.orig_csrf_bypass

    def test_01_dashboard_stats_and_health_diagnostics(self):
        stats = self.repo_service.get_repository_dashboard_stats()
        self.assertIn("total_documents", stats)
        self.assertIn("total_folders", stats)
        self.assertIn("health_score", stats)

        diagnostics = self.repo_service.run_repository_health_diagnostics()
        self.assertIn("health_score", diagnostics)
        self.assertIn("status", diagnostics)
        self.assertIn("findings", diagnostics)

    def test_02_execute_maintenance_tasks(self):
        # Execute reindex maintenance
        res1 = self.repo_service.execute_maintenance_task("rebuild_search_index", user_id=1)
        self.assertTrue(res1['success'])

        # Execute clean empty folders maintenance
        res2 = self.repo_service.execute_maintenance_task("clean_empty_folders", user_id=1)
        self.assertTrue(res2['success'])

        # Retrieve maintenance logs
        logs = self.repo_service.get_maintenance_logs()
        self.assertTrue(len(logs) >= 2)

    def test_03_system_and_backup_configs(self):
        # System config update
        upd_ok = self.repo_service.update_system_config("max_upload_size_mb", "150")
        self.assertTrue(upd_ok)

        configs = self.repo_service.get_system_configs()
        self.assertEqual(configs.get("max_upload_size_mb"), "150")

        # Backup config update
        upd_b_ok = self.repo_service.update_backup_config("WEEKLY", 45)
        self.assertTrue(upd_b_ok)

        b_config = self.repo_service.get_backup_config()
        self.assertEqual(b_config.get("backup_frequency"), "WEEKLY")
        self.assertEqual(b_config.get("retention_days"), 45)

    def test_04_repository_explorer_tree(self):
        tree = self.repo_service.get_repository_explorer_tree()
        self.assertTrue(len(tree) > 0)
        root_paths = [r['path'] for r in tree]
        self.assertIn('/company', root_paths)

    def test_05_admin_web_route_and_apis(self):
        # Web Route
        resp_web = self.app.get('/documents/admin')
        self.assertEqual(resp_web.status_code, 200)

        # Dashboard REST API
        resp_dash = self.app.get('/api/v1/documents/admin/dashboard')
        self.assertEqual(resp_dash.status_code, 200)

        # Health REST API
        resp_health = self.app.get('/api/v1/documents/admin/health')
        self.assertEqual(resp_health.status_code, 200)

        # Explorer REST API
        resp_exp = self.app.get('/api/v1/documents/admin/explorer')
        self.assertEqual(resp_exp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
