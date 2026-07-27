import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from backend.repositories.dashboard_repository import get_dashboard_snapshot
from backend.repositories.activity_log_repository import get_recent_activities, log_activity

class DashboardV2Test(unittest.TestCase):
    def test_dashboard_snapshot_keys(self):
        snapshot = get_dashboard_snapshot()
        self.assertIn("today_purchase_count", snapshot)
        self.assertIn("today_purchase_value", snapshot)
        self.assertIn("today_sales_count", snapshot)
        self.assertIn("today_sales_value", snapshot)
        self.assertIn("monthly_purchase_value", snapshot)
        self.assertIn("monthly_sales_value", snapshot)
        self.assertIn("total_parties", snapshot)
        self.assertIn("total_materials", snapshot)
        self.assertIn("inventory_items", snapshot)
        self.assertIn("total_purchase_invoices", snapshot)
        self.assertIn("total_sales_invoices", snapshot)
        self.assertIn("pending_processing", snapshot)
        self.assertIn("pending_certificates", snapshot)

    def test_activity_logging(self):
        log_activity("Test User", "Test Action", "Test Details")
        activities = get_recent_activities(limit=50)
        actions = [a["action"] for a in activities]
        self.assertIn("Test Action", actions)

if __name__ == "__main__":
    unittest.main()
