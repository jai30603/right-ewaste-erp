import unittest
import sqlite3
import os
import sys
import datetime

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection, initialize_database
from repositories import payroll_repository, attendance_repository
from services.employee_service import EmployeeService
from services.payroll_service import PayrollService
from services.payroll_validator import PayrollValidator
from repositories.activity_log_repository import get_recent_activities


class TestPayrollManagement(unittest.TestCase):

    def setUp(self):
        initialize_database()
        self.conn = get_connection()
        cursor = self.conn.cursor()

        # Clean test payroll data
        cursor.execute("DELETE FROM employee_payroll WHERE generated_by LIKE '%Test%'")
        cursor.execute("DELETE FROM employee_salary_structure WHERE employee_id IN (SELECT id FROM employees WHERE email LIKE '%@testpayroll.com%')")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testpayroll.com%' OR mobile_number LIKE '6600%'")
        self.conn.commit()

        # Create test employee 1 (active)
        emp1_data = {
            "first_name": "ActivePayroll",
            "last_name": "Worker",
            "mobile_number": "6600112233",
            "email": "activepayroll@testpayroll.com",
            "department": "Finance",
            "designation": "Accountant",
            "status": "Active"
        }
        self.emp1_id, _ = EmployeeService.create_employee(emp1_data, user_name="TestAdmin")

        # Create test employee 2 (inactive)
        emp2_data = {
            "first_name": "InactivePayroll",
            "last_name": "Worker",
            "mobile_number": "6600112234",
            "email": "inactivepayroll@testpayroll.com",
            "department": "Finance",
            "designation": "Accountant",
            "status": "Inactive"
        }
        self.emp2_id, _ = EmployeeService.create_employee(emp2_data, user_name="TestAdmin")

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employee_payroll WHERE generated_by LIKE '%Test%'")
        cursor.execute("DELETE FROM employee_salary_structure WHERE employee_id IN (SELECT id FROM employees WHERE email LIKE '%@testpayroll.com%')")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testpayroll.com%' OR mobile_number LIKE '6600%'")
        self.conn.commit()
        self.conn.close()

    def test_salary_structure_creation_and_versioning(self):
        # 1. Create initial salary structure
        form_data = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-01-01",
            "basic_salary": 40000,
            "hra": 16000,
            "conveyance_allowance": 2000,
            "medical_allowance": 1250,
            "special_allowance": 5000,
            "other_allowances": 0,
            "provident_fund": 1800,
            "professional_tax": 200,
            "income_tax": 2000,
            "other_deductions": 0
        }
        struct_id, errors = PayrollService.save_salary_structure(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])
        self.assertIsNotNone(struct_id)

        struct = PayrollService.get_salary_structure(self.emp1_id)
        self.assertEqual(struct["gross_salary"], 64250.0)
        self.assertEqual(struct["net_salary"], 60250.0)
        self.assertEqual(struct["status"], "Active")

        # 2. Revise salary structure (creates new version, supercedes old)
        form_data_v2 = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-06-01",
            "basic_salary": 50000,
            "hra": 20000,
            "conveyance_allowance": 2000,
            "medical_allowance": 1250,
            "special_allowance": 5000,
            "other_allowances": 0,
            "provident_fund": 1800,
            "professional_tax": 200,
            "income_tax": 3000,
            "other_deductions": 0
        }
        struct_id_v2, errors_v2 = PayrollService.save_salary_structure(form_data_v2, user_name="TestAdmin")
        self.assertEqual(errors_v2, [])

        history = PayrollService.get_salary_structure_history(self.emp1_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["status"], "Active")
        self.assertEqual(history[1]["status"], "Superceded")

    def test_monthly_payroll_generation_and_attendance_integration(self):
        # Setup salary structure
        form_data = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-01-01",
            "basic_salary": 30000,
            "hra": 10000,
            "provident_fund": 1000
        }
        PayrollService.save_salary_structure(form_data, user_name="TestAdmin")

        # Run payroll for January 2026
        gen_cnt, skip_cnt, errors = PayrollService.generate_monthly_payroll(1, 2026, user_name="TestAdmin")
        self.assertGreaterEqual(gen_cnt, 1)

        records = PayrollService.get_payroll_records(month=1, year=2026, search="ActivePayroll")
        self.assertEqual(len(records["records"]), 1)
        rec = records["records"][0]
        self.assertEqual(rec["gross_salary"], 40000.0)
        self.assertEqual(rec["net_salary"], 39000.0)
        self.assertEqual(rec["payroll_status"], "Generated")

    def test_duplicate_payroll_prevention_and_paid_lock(self):
        form_data = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-01-01",
            "basic_salary": 30000
        }
        PayrollService.save_salary_structure(form_data, user_name="TestAdmin")

        PayrollService.generate_monthly_payroll(2, 2026, user_name="TestAdmin")
        records = PayrollService.get_payroll_records(month=2, year=2026, search="ActivePayroll")
        pr_id = records["records"][0]["id"]

        # Mark as Paid
        success, msg = PayrollService.update_payroll_status(pr_id, "Paid", user_name="TestAdmin")
        self.assertTrue(success)

        # Regenerating month 2 should skip the paid employee
        gen_cnt, skip_cnt, errors = PayrollService.generate_monthly_payroll(2, 2026, user_name="TestAdmin")
        self.assertGreaterEqual(skip_cnt, 1)

    def test_payslip_and_report_exports(self):
        form_data = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-01-01",
            "basic_salary": 30000
        }
        PayrollService.save_salary_structure(form_data, user_name="TestAdmin")
        PayrollService.generate_monthly_payroll(3, 2026, user_name="TestAdmin")

        records = PayrollService.get_payroll_records(month=3, year=2026, search="ActivePayroll")
        pr_id = records["records"][0]["id"]

        # Payslip retrieval
        payslip_rec = PayrollService.get_payroll_by_id(pr_id)
        self.assertIsNotNone(payslip_rec)
        self.assertEqual(payslip_rec["employee_id"], self.emp1_id)

        # CSV Export
        stream, mime_type, filename = PayrollService.export_payroll_report("register", "csv", month=3, year=2026)
        self.assertEqual(mime_type, "text/csv")
        content = stream.getvalue().decode("utf-8")
        self.assertIn("ActivePayroll Worker", content)

    def test_accounting_voucher_payload_preparation(self):
        form_data = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-01-01",
            "basic_salary": 30000,
            "hra": 10000,
            "provident_fund": 1000
        }
        PayrollService.save_salary_structure(form_data, user_name="TestAdmin")
        PayrollService.generate_monthly_payroll(4, 2026, user_name="TestAdmin")

        records = PayrollService.get_payroll_records(month=4, year=2026, search="ActivePayroll")
        pr_id = records["records"][0]["id"]

        voucher = PayrollService.prepare_accounting_voucher_payload(pr_id)
        self.assertIsNotNone(voucher)
        self.assertEqual(voucher["voucher_type"], "Payroll Journal")
        self.assertEqual(voucher["debits"][0]["amount"], 40000.0)
        self.assertEqual(voucher["credits"][3]["amount"], 39000.0)

    def test_audit_log_and_events(self):
        form_data = {
            "employee_id": self.emp1_id,
            "effective_from": "2026-01-01",
            "basic_salary": 30000
        }
        PayrollService.save_salary_structure(form_data, user_name="AuditAdmin")
        PayrollService.generate_monthly_payroll(5, 2026, user_name="AuditAdmin")

        activities = get_recent_activities(limit=200)
        actions = [a["action"] for a in activities]
        self.assertIn("Salary Structure Created", actions)
        self.assertIn("Payroll Generated", actions)


if __name__ == "__main__":
    unittest.main()
