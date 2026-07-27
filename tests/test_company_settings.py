import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from app import app
from database import get_connection
from repositories.company_repository import get_company


class CompanySettingsTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.orig_csrf = self.app.config.get("WTF_CSRF_ENABLED")
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        if hasattr(self, "orig_csrf"):
            if self.orig_csrf is None:
                self.app.config.pop("WTF_CSRF_ENABLED", None)
            else:
                self.app.config["WTF_CSRF_ENABLED"] = self.orig_csrf
        self.app_context.pop()

    def test_company_profile_get_and_post(self):
        # Test GET request
        response = self.client.get("/company")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Company Information", response.data)

        # Retrieve current company name to restore later
        original_company = get_company()
        orig_name = original_company["company_name"] if original_company else "Right Ewaste Recycle Pvt Ltd"
        orig_gstin = original_company["gstin"] if original_company else "27AAACR1234A1Z1"
        orig_pan = original_company["pan"] if original_company else "AAACR1234A"

        # Test POST update request
        post_data = {
            "company_name": "Updated Test Company Legal Name",
            "address_line_1": "123 New Tech Way",
            "address_line_2": "Suite 500",
            "city": "Mumbai",
            "state": "Maharashtra",
            "state_code": "27",
            "pincode": "400001",
            "gstin": orig_gstin,
            "pan": orig_pan,
            "cin": "U12345MH2026PTC123456",
            "phone": "+91 22 1234 5678",
            "email": "info@testcompany.com",
            "website": "www.testcompany.com"
        }
        post_response = self.client.post("/company", data=post_data, follow_redirects=True)
        self.assertEqual(post_response.status_code, 200)
        self.assertIn(b"Company profile updated successfully.", post_response.data)

        # Verify updated values in DB
        updated_company = get_company()
        self.assertEqual(updated_company["company_name"], "Updated Test Company Legal Name")
        self.assertEqual(updated_company["email"], "info@testcompany.com")

        # Restore original company profile to keep database clean
        restore_data = {
            "company_name": orig_name,
            "address_line_1": original_company["address_line_1"] if original_company else "Plot 101, Industrial Area",
            "address_line_2": original_company["address_line_2"] if original_company else "",
            "city": original_company["city"] if original_company else "Mumbai",
            "state": original_company["state"] if original_company else "Maharashtra",
            "state_code": original_company["state_code"] if original_company else "27",
            "pincode": original_company["pincode"] if original_company else "400001",
            "gstin": orig_gstin,
            "pan": orig_pan,
            "cin": original_company["cin"] if original_company else "",
            "phone": original_company["phone"] if original_company else "+91 22 5555 1234",
            "email": original_company["email"] if original_company else "info@rightewaste.com",
            "website": original_company["website"] if original_company else "www.rightewaste.com"
        }
        self.client.post("/company", data=restore_data, follow_redirects=True)

    def test_settings_get_and_post(self):
        # Test GET request
        response = self.client.get("/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"System Configurations", response.data)

        # Test POST configuration save request
        post_data = {
            "default_currency": "INR",
            "default_timezone": "Asia/Kolkata",
            "enable_audit": "on",
            "purchase_prefix": "PURCH-",
            "sales_prefix": "SALE-",
            "cert_prefix": "CERT-",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": "587",
            "smtp_sender": "noreply@rightewaste.com"
        }
        post_response = self.client.post("/settings", data=post_data, follow_redirects=True)
        self.assertEqual(post_response.status_code, 200)
        self.assertIn(b"System settings saved successfully.", post_response.data)


if __name__ == "__main__":
    unittest.main()
