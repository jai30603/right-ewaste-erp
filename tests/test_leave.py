import unittest
import sqlite3
import os
import sys
import datetime

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection, initialize_database
from repositories import leave_repository, attendance_repository
from services.employee_service import EmployeeService
from services.leave_service import LeaveService
from services.leave_validator import LeaveValidator
from repositories.activity_log_repository import get_recent_activities


class TestLeaveManagement(unittest.TestCase):

    def setUp(self):
        initialize_database()
        self.conn = get_connection()
        cursor = self.conn.cursor()

        # Clean test leave and attendance data
        cursor.execute("DELETE FROM employee_leave_requests WHERE reason LIKE '%TestLeave%'")
        cursor.execute("DELETE FROM employee_attendance WHERE remarks LIKE '%TestLeave%'")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testleave.com%' OR mobile_number LIKE '7700%'")
        self.conn.commit()

        # Create active test employee
        emp1_data = {
            "first_name": "ActiveLeave",
            "last_name": "User",
            "mobile_number": "7700112233",
            "email": "activeleave@testleave.com",
            "department": "Engineering",
            "designation": "Developer",
            "status": "Active"
        }
        self.emp1_id, _ = EmployeeService.create_employee(emp1_data, user_name="TestAdmin")

        # Create inactive test employee
        emp2_data = {
            "first_name": "InactiveLeave",
            "last_name": "User",
            "mobile_number": "7700112234",
            "email": "inactiveleave@testleave.com",
            "department": "Engineering",
            "designation": "Developer",
            "status": "Inactive"
        }
        self.emp2_id, _ = EmployeeService.create_employee(emp2_data, user_name="TestAdmin")

        # Get Casual Leave type id (CL)
        cursor.execute("SELECT id FROM employee_leave_types WHERE leave_code = 'CL'")
        row = cursor.fetchone()
        self.cl_type_id = row[0] if row else 1

        # Get Unpaid Leave type id (LWP)
        cursor.execute("SELECT id FROM employee_leave_types WHERE leave_code = 'LWP'")
        row = cursor.fetchone()
        self.lwp_type_id = row[0] if row else 4

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employee_leave_requests WHERE reason LIKE '%TestLeave%'")
        cursor.execute("DELETE FROM employee_attendance WHERE remarks LIKE '%TestLeave%'")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testleave.com%' OR mobile_number LIKE '7700%'")
        self.conn.commit()
        self.conn.close()

    def test_leave_application_creation_and_balance_initialization(self):
        # Ensure initial balance auto-allocates 12 days CL
        balances = LeaveService.get_employee_balance(self.emp1_id)
        cl_bal = [b for b in balances if b["leave_code"] == "CL"][0]
        self.assertEqual(cl_bal["allocated_days"], 12.0)
        self.assertEqual(cl_bal["remaining_days"], 12.0)

        # Apply 2 days Casual Leave
        today = datetime.date.today()
        start_str = today.isoformat()
        end_str = (today + datetime.timedelta(days=1)).isoformat()

        form_data = {
            "employee_id": self.emp1_id,
            "leave_type_id": self.cl_type_id,
            "start_date": start_str,
            "end_date": end_str,
            "reason": "Personal work TestLeave"
        }

        req_id, errors = LeaveService.apply_leave(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])
        self.assertIsNotNone(req_id)

        req = LeaveService.get_leave_request(req_id)
        self.assertEqual(req["status"], "Pending")
        self.assertEqual(req["total_days"], 2.0)

    def test_validation_rules(self):
        today = datetime.date.today()
        start_str = today.isoformat()
        end_str = (today + datetime.timedelta(days=1)).isoformat()

        # 1. Inactive employee application fails
        form_data_inactive = {
            "employee_id": self.emp2_id,
            "leave_type_id": self.cl_type_id,
            "start_date": start_str,
            "end_date": end_str,
            "reason": "TestLeave inactive test"
        }
        req_id, errors = LeaveService.apply_leave(form_data_inactive, user_name="TestAdmin")
        self.assertIsNone(req_id)
        self.assertTrue(any("inactive" in e for e in errors))

        # 2. End date < Start date fails
        form_data_invalid_dates = {
            "employee_id": self.emp1_id,
            "leave_type_id": self.cl_type_id,
            "start_date": end_str,
            "end_date": start_str,
            "reason": "TestLeave date error"
        }
        req_id2, errors2 = LeaveService.apply_leave(form_data_invalid_dates, user_name="TestAdmin")
        self.assertIsNone(req_id2)
        self.assertTrue(any("before" in e for e in errors2))

    def test_leave_approval_and_attendance_synchronization(self):
        today = datetime.date.today()
        start_str = today.isoformat()
        end_str = (today + datetime.timedelta(days=1)).isoformat()

        form_data = {
            "employee_id": self.emp1_id,
            "leave_type_id": self.cl_type_id,
            "start_date": start_str,
            "end_date": end_str,
            "reason": "Vacation TestLeave"
        }
        req_id, errors = LeaveService.apply_leave(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])

        # Approve Leave
        success, msg = LeaveService.approve_leave(req_id, user_name="ApproverAdmin")
        self.assertTrue(success)

        # Check balance deduction (12 - 2 = 10)
        balances = LeaveService.get_employee_balance(self.emp1_id)
        cl_bal = [b for b in balances if b["leave_code"] == "CL"][0]
        self.assertEqual(cl_bal["used_days"], 2.0)
        self.assertEqual(cl_bal["remaining_days"], 10.0)

        # Check attendance synchronization
        daily_att = attendance_repository.get_daily_attendance_list(start_str)
        emp_att = [a for a in daily_att if a["employee_id"] == self.emp1_id][0]
        self.assertEqual(emp_att["attendance_status"], "Leave")
        self.assertIn("TestLeave", emp_att["remarks"])

    def test_leave_cancellation_and_reversal(self):
        today = datetime.date.today()
        start_str = today.isoformat()

        form_data = {
            "employee_id": self.emp1_id,
            "leave_type_id": self.cl_type_id,
            "start_date": start_str,
            "end_date": start_str,
            "reason": "Short trip TestLeave"
        }
        req_id, errors = LeaveService.apply_leave(form_data, user_name="TestAdmin")
        self.assertEqual(errors, [])

        LeaveService.approve_leave(req_id, user_name="ApproverAdmin")

        # Cancel Leave
        success, msg = LeaveService.cancel_leave(req_id, user_name="TestAdmin")
        self.assertTrue(success)

        req = LeaveService.get_leave_request(req_id)
        self.assertEqual(req["status"], "Cancelled")

        # Verify balance restored
        balances = LeaveService.get_employee_balance(self.emp1_id)
        cl_bal = [b for b in balances if b["leave_code"] == "CL"][0]
        self.assertEqual(cl_bal["used_days"], 0.0)
        self.assertEqual(cl_bal["remaining_days"], 12.0)

    def test_leave_report_export(self):
        today_str = datetime.date.today().isoformat()
        form_data = {
            "employee_id": self.emp1_id,
            "leave_type_id": self.cl_type_id,
            "start_date": today_str,
            "end_date": today_str,
            "reason": "Report TestLeave"
        }
        LeaveService.apply_leave(form_data, user_name="TestAdmin")

        # Export CSV report
        stream, mime_type, filename = LeaveService.export_leave_report(
            report_type="register",
            format_type="csv",
            start_date=today_str,
            end_date=today_str
        )
        self.assertEqual(mime_type, "text/csv")
        self.assertTrue(filename.endswith(".csv"))

        content = stream.getvalue().decode("utf-8")
        self.assertIn("ActiveLeave User", content)
        self.assertIn("Casual Leave", content)

    def test_audit_log_and_events(self):
        today_str = datetime.date.today().isoformat()
        form_data = {
            "employee_id": self.emp1_id,
            "leave_type_id": self.cl_type_id,
            "start_date": today_str,
            "end_date": today_str,
            "reason": "Audit TestLeave"
        }
        req_id, _ = LeaveService.apply_leave(form_data, user_name="AuditAdmin")
        LeaveService.approve_leave(req_id, user_name="AuditAdmin")

        activities = get_recent_activities(limit=200)
        actions = [a["action"] for a in activities]
        self.assertIn("Leave Applied", actions)
        self.assertIn("Leave Approved", actions)


if __name__ == "__main__":
    unittest.main()
