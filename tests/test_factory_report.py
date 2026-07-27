import unittest
import sqlite3
import os
import sys
import datetime
import openpyxl
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection, initialize_database
from services.factory_report_validator import FactoryReportValidationService
from services.factory_report_service import FactoryReportService
from repositories import factory_report_repository
from document_engine.factory_report_generator import FactoryReportGenerator
from repositories.activity_log_repository import get_recent_activities


class TestFactoryReportSystem(unittest.TestCase):

    def setUp(self):
        initialize_database()
        self.conn = get_connection()
        cursor = self.conn.cursor()

        # Clean test report history
        cursor.execute("DELETE FROM factory_report_history WHERE generated_by LIKE '%Test%'")
        self.conn.commit()

        self.test_date = datetime.date.today().isoformat()

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM factory_report_history WHERE generated_by LIKE '%Test%'")
        self.conn.commit()
        self.conn.close()

    def test_validation_engine_prerequisites(self):
        is_valid, errors, warnings = FactoryReportValidationService.validate_generation_prerequisites(self.test_date)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_erp_data_aggregation(self):
        erp_data = factory_report_repository.get_erp_data_for_report(self.test_date)
        self.assertIn("company", erp_data)
        self.assertIn("attendance", erp_data)
        self.assertIn("incoming_materials", erp_data)
        self.assertIn("outgoing_materials", erp_data)
        self.assertEqual(erp_data["report_date"], self.test_date)

    def test_workbook_generation_and_formula_preservation(self):
        # Generate report
        report_id, errors, warnings = FactoryReportService.generate_factory_report(self.test_date, user_name="TestGenerator")
        self.assertEqual(errors, [])
        self.assertIsNotNone(report_id)

        report = FactoryReportService.get_report_by_id(report_id)
        self.assertIsNotNone(report)
        self.assertEqual(report["report_date"], self.test_date)

        # Inspect generated Excel file
        rel_path = report["file_path"].lstrip("/").replace("/", os.sep)
        full_path = Path(__file__).resolve().parent.parent / "backend" / rel_path
        self.assertTrue(full_path.exists())

        wb = openpyxl.load_workbook(full_path, data_only=False)
        sheets = wb.sheetnames
        self.assertIn("EwasteMaterials", sheets)
        self.assertIn("Disposal", sheets)
        self.assertIn("ScrapMaterials", sheets)
        self.assertIn("IncomingMaterial", sheets)
        self.assertIn("OutgoingMaterial", sheets)

        # Verify SUM formula in EwasteMaterials Total row
        ws1 = wb["EwasteMaterials"]
        self.assertEqual(ws1["N35"].value, "=SUM(N8:N34)")

    def test_report_history_and_regeneration(self):
        report_id, _, _ = FactoryReportService.generate_factory_report(self.test_date, user_name="TestAdmin")
        new_report_id, errors, _ = FactoryReportService.regenerate_report(report_id, user_name="TestAdmin")

        self.assertEqual(errors, [])
        self.assertIsNotNone(new_report_id)

        history = FactoryReportService.get_report_history(limit=10)
        self.assertGreaterEqual(len(history), 2)

    def test_activity_logging_integration(self):
        FactoryReportService.generate_factory_report(self.test_date, user_name="AuditTester")
        activities = get_recent_activities(limit=50)
        actions = [a["action"] for a in activities]
        self.assertIn("Factory Report Generated", actions)


if __name__ == "__main__":
    unittest.main()
