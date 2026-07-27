import unittest
import sqlite3
import os
import sys
import io
import datetime
from werkzeug.datastructures import FileStorage

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection, initialize_database
from services.employee_service import EmployeeService
from services.employee_document_service import EmployeeDocumentService
from services.employee_analytics_service import EmployeeAnalyticsService
from services.employee_report_service import EmployeeReportService
from repositories.employee_report_repository import get_employee_directory_report
from erp_platform.search.search_service import GlobalSearchService
from repositories.dashboard_repository import get_dashboard_snapshot


class TestEmployeeReportsAnalytics(unittest.TestCase):

    def setUp(self):
        initialize_database()
        self.conn = get_connection()
        cursor = self.conn.cursor()

        # Clean test document & employee data
        cursor.execute("DELETE FROM employee_documents WHERE document_name LIKE '%testdoc%'")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testanalytics.com%' OR mobile_number LIKE '5500%'")
        self.conn.commit()

        # Create active test employee
        emp1_data = {
            "first_name": "AnalyticsUser",
            "last_name": "One",
            "mobile_number": "5500112233",
            "email": "user1@testanalytics.com",
            "department": "IT & Software",
            "designation": "System Admin",
            "employment_type": "Permanent",
            "status": "Active"
        }
        self.emp1_id, _ = EmployeeService.create_employee(emp1_data, user_name="TestAdmin")

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employee_documents WHERE document_name LIKE '%testdoc%'")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testanalytics.com%' OR mobile_number LIKE '5500%'")
        self.conn.commit()
        self.conn.close()

    def test_employee_document_upload_and_delete(self):
        fake_stream = io.BytesIO(b"Fake PDF content for test")
        fake_file = FileStorage(stream=fake_stream, filename="testdoc_aadhaar.pdf")

        # Upload document
        doc_id, errors = EmployeeDocumentService.upload_document(
            self.emp1_id, "Aadhaar", fake_file, user_name="TestAdmin"
        )
        self.assertEqual(errors, [])
        self.assertIsNotNone(doc_id)

        # Retrieve documents
        docs = EmployeeDocumentService.get_employee_documents(self.emp1_id)
        self.assertGreaterEqual(len(docs), 1)
        self.assertEqual(docs[0]["document_category"], "Aadhaar")

        # Delete document
        success, msg = EmployeeDocumentService.delete_document(doc_id, user_name="TestAdmin")
        self.assertTrue(success)

        docs_after = EmployeeDocumentService.get_employee_documents(self.emp1_id)
        self.assertEqual(len(docs_after), 0)

    def test_workforce_analytics_calculations(self):
        analytics = EmployeeAnalyticsService.get_analytics()
        self.assertIn("total_employees", analytics)
        self.assertIn("department_distribution", analytics)
        self.assertIn("employment_type_distribution", analytics)

        self.assertGreaterEqual(analytics["total_employees"], 1)
        self.assertIn("IT & Software", analytics["department_distribution"])

    def test_consolidated_reports_export(self):
        stream, mime_type, filename = EmployeeReportService.export_employee_directory("csv", search="AnalyticsUser")
        self.assertEqual(mime_type, "text/csv")
        content = stream.getvalue().decode("utf-8")
        self.assertIn("AnalyticsUser One", content)

    def test_global_search_integration(self):
        results = GlobalSearchService.global_search("AnalyticsUser")
        emp_results = [r for r in results if r["type"] == "Employee"]
        self.assertGreaterEqual(len(emp_results), 1)
        self.assertIn("AnalyticsUser One", emp_results[0]["title"])

    def test_dashboard_snapshot_employee_metrics(self):
        snapshot = get_dashboard_snapshot()
        self.assertIn("total_employees", snapshot)
        self.assertIn("present_today", snapshot)
        self.assertIn("employees_on_leave", snapshot)
        self.assertGreaterEqual(snapshot["total_employees"], 1)


if __name__ == "__main__":
    unittest.main()
