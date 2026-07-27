import unittest
import sqlite3
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection, initialize_database
from repositories import employee_repository, settings_repository
from services.employee_service import EmployeeService
from services.employee_validator import EmployeeValidator
from repositories.activity_log_repository import get_recent_activities


class TestEmployeeManagement(unittest.TestCase):

    def setUp(self):
        initialize_database()
        self.conn = get_connection()
        cursor = self.conn.cursor()
        # Clean test employees if present
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testemployee.com%' OR mobile_number LIKE '9900%'")
        cursor.execute("DELETE FROM employee_bank_details WHERE employee_id NOT IN (SELECT id FROM employees)")
        cursor.execute("DELETE FROM employee_emergency_contacts WHERE employee_id NOT IN (SELECT id FROM employees)")
        self.conn.commit()

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testemployee.com%' OR mobile_number LIKE '9900%'")
        cursor.execute("DELETE FROM employee_bank_details WHERE employee_id NOT IN (SELECT id FROM employees)")
        cursor.execute("DELETE FROM employee_emergency_contacts WHERE employee_id NOT IN (SELECT id FROM employees)")
        self.conn.commit()
        self.conn.close()

    def test_employee_creation_and_code_generation(self):
        form_data = {
            "first_name": "Vikram",
            "last_name": "Singh",
            "gender": "Male",
            "date_of_birth": "1990-05-15",
            "mobile_number": "9900112233",
            "email": "vikram@testemployee.com",
            "joining_date": "2026-01-10",
            "department": "Operations",
            "designation": "Plant Supervisor",
            "employment_type": "Full-Time",
            "status": "Active",
            "bank_name": "HDFC Bank",
            "account_holder_name": "Vikram Singh",
            "account_number": "50100234567890",
            "ifsc_code": "HDFC0001234",
            "branch_name": "Main Branch",
            "emergency_contact_name": "Suresh Singh",
            "emergency_relationship": "Father",
            "emergency_mobile": "9900112299"
        }

        emp_id, errors = EmployeeService.create_employee(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])
        self.assertIsNotNone(emp_id)

        # Retrieve employee
        emp = EmployeeService.get_employee(emp_id)
        self.assertIsNotNone(emp)
        self.assertEqual(emp["full_name"], "Vikram Singh")
        self.assertTrue(emp["employee_code"].startswith("EMP-2026-"))
        self.assertEqual(emp["status"], "Active")

        # Verify bank details
        self.assertIsNotNone(emp["bank_details"])
        self.assertEqual(emp["bank_details"]["bank_name"], "HDFC Bank")

        # Verify emergency contacts
        self.assertTrue(len(emp["emergency_contacts"]) > 0)
        self.assertEqual(emp["emergency_contacts"][0]["contact_name"], "Suresh Singh")

    def test_duplicate_validations(self):
        form_data = {
            "first_name": "Anita",
            "last_name": "Roy",
            "mobile_number": "9900554433",
            "email": "anita@testemployee.com",
            "aadhaar_number": "123456789012",
            "pan_number": "ABCDE1234F"
        }

        emp_id, errors = EmployeeService.create_employee(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])

        # Duplicate email
        dup_email_form = form_data.copy()
        dup_email_form["mobile_number"] = "9900554434"
        dup_email_form["aadhaar_number"] = "123456789013"
        dup_email_form["pan_number"] = "ABCDE1234G"
        _, dup_errors = EmployeeService.create_employee(dup_email_form, user_name="TestAdmin")
        self.assertTrue(any("email" in e for e in dup_errors))

        # Duplicate mobile
        dup_mobile_form = form_data.copy()
        dup_mobile_form["email"] = "anita2@testemployee.com"
        dup_mobile_form["aadhaar_number"] = "123456789013"
        dup_mobile_form["pan_number"] = "ABCDE1234G"
        _, dup_errors = EmployeeService.create_employee(dup_mobile_form, user_name="TestAdmin")
        self.assertTrue(any("mobile" in e for e in dup_errors))

        # Duplicate Aadhaar
        dup_aadhaar_form = form_data.copy()
        dup_aadhaar_form["email"] = "anita3@testemployee.com"
        dup_aadhaar_form["mobile_number"] = "9900554435"
        dup_aadhaar_form["pan_number"] = "ABCDE1234G"
        _, dup_errors = EmployeeService.create_employee(dup_aadhaar_form, user_name="TestAdmin")
        self.assertTrue(any("Aadhaar" in e for e in dup_errors))

        # Duplicate PAN
        dup_pan_form = form_data.copy()
        dup_pan_form["email"] = "anita4@testemployee.com"
        dup_pan_form["mobile_number"] = "9900554436"
        dup_pan_form["aadhaar_number"] = "123456789014"
        _, dup_errors = EmployeeService.create_employee(dup_pan_form, user_name="TestAdmin")
        self.assertTrue(any("PAN" in e for e in dup_errors))

    def test_employee_update_and_deactivation(self):
        form_data = {
            "first_name": "Rohan",
            "last_name": "Mehta",
            "mobile_number": "9900998877",
            "email": "rohan@testemployee.com",
            "department": "IT",
            "designation": "Engineer",
            "status": "Active"
        }
        emp_id, errors = EmployeeService.create_employee(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])

        # Update designation and department
        update_form = form_data.copy()
        update_form["designation"] = "Lead Engineer"
        update_form["department"] = "Technology"
        success, update_errors = EmployeeService.update_employee(emp_id, update_form, user_name="TestAdmin")
        self.assertTrue(success)
        self.assertEqual(update_errors, [])

        updated_emp = EmployeeService.get_employee(emp_id)
        self.assertEqual(updated_emp["designation"], "Lead Engineer")
        self.assertEqual(updated_emp["department"], "Technology")

        # Deactivate
        toggle_success, msg = EmployeeService.toggle_status(emp_id, user_name="TestAdmin")
        self.assertTrue(toggle_success)
        self.assertIn("Inactive", msg)

        deactivated_emp = EmployeeService.get_employee(emp_id)
        self.assertEqual(deactivated_emp["status"], "Inactive")

    def test_dashboard_stats_and_filtering(self):
        # Create Active employee
        emp1_data = {
            "first_name": "TestActive",
            "mobile_number": "9900123456",
            "email": "active@testemployee.com",
            "department": "Finance",
            "designation": "Accountant",
            "employment_type": "Full-Time",
            "status": "Active"
        }
        EmployeeService.create_employee(emp1_data, user_name="TestAdmin")

        # Create Inactive employee
        emp2_data = {
            "first_name": "TestInactive",
            "mobile_number": "9900123457",
            "email": "inactive@testemployee.com",
            "department": "Logistics",
            "designation": "Driver",
            "employment_type": "Contract",
            "status": "Inactive"
        }
        EmployeeService.create_employee(emp2_data, user_name="TestAdmin")

        stats = EmployeeService.get_dashboard_data()
        self.assertGreaterEqual(stats["total_employees"], 2)
        self.assertGreaterEqual(stats["active_employees"], 1)
        self.assertGreaterEqual(stats["inactive_employees"], 1)

        # Filtering test
        res = EmployeeService.get_employees_list(department="Finance")
        self.assertTrue(all(e["department"] == "Finance" for e in res["employees"]))

        res_inactive = EmployeeService.get_employees_list(status="Inactive")
        self.assertTrue(all(e["status"] == "Inactive" for e in res_inactive["employees"]))

    def test_audit_log_integration(self):
        form_data = {
            "first_name": "AuditUser",
            "mobile_number": "9900887766",
            "email": "audit@testemployee.com",
            "department": "Audit",
            "designation": "Auditor"
        }
        emp_id, _ = EmployeeService.create_employee(form_data, user_name="AuditAdmin")

        activities = get_recent_activities(limit=200)
        actions = [a["action"] for a in activities]
        self.assertIn("Employee Created", actions)


if __name__ == "__main__":
    unittest.main()
