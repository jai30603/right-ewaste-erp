import unittest
import sqlite3
import os
import sys
import datetime

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import get_connection, initialize_database
from repositories import employee_repository, attendance_repository
from services.employee_service import EmployeeService
from services.attendance_service import AttendanceService
from services.attendance_validator import AttendanceValidator
from repositories.activity_log_repository import get_recent_activities


class TestAttendanceManagement(unittest.TestCase):

    def setUp(self):
        initialize_database()
        self.conn = get_connection()
        cursor = self.conn.cursor()

        # Clean test attendance records
        cursor.execute("DELETE FROM employee_attendance WHERE attendance_date >= '2026-01-01'")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testattendance.com%' OR mobile_number LIKE '8800%'")
        self.conn.commit()

        # Create two test employees (one active, one inactive)
        emp1_data = {
            "first_name": "ActiveAtt",
            "last_name": "Test",
            "mobile_number": "8800112233",
            "email": "activeatt@testattendance.com",
            "department": "Production",
            "designation": "Operator",
            "status": "Active"
        }
        self.emp1_id, _ = EmployeeService.create_employee(emp1_data, user_name="TestAdmin")

        emp2_data = {
            "first_name": "InactiveAtt",
            "last_name": "Test",
            "mobile_number": "8800112234",
            "email": "inactiveatt@testattendance.com",
            "department": "Production",
            "designation": "Operator",
            "status": "Inactive"
        }
        self.emp2_id, _ = EmployeeService.create_employee(emp2_data, user_name="TestAdmin")

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employee_attendance WHERE attendance_date >= '2026-01-01'")
        cursor.execute("DELETE FROM employees WHERE email LIKE '%@testattendance.com%' OR mobile_number LIKE '8800%'")
        self.conn.commit()
        self.conn.close()

    def test_bulk_attendance_marking_and_upsert(self):
        today_str = datetime.date.today().isoformat()
        payload = {
            str(self.emp1_id): {
                "status": "Present",
                "check_in_time": "09:15",
                "check_out_time": "18:00",
                "remarks": "On time"
            }
        }

        success, errors = AttendanceService.mark_bulk_attendance(today_str, payload, user_name="TestAdmin")
        self.assertTrue(success)
        self.assertEqual(errors, [])

        # Check attendance list
        records = AttendanceService.get_daily_attendance(today_str)
        emp1_rec = [r for r in records if r["employee_id"] == self.emp1_id][0]
        self.assertEqual(emp1_rec["attendance_status"], "Present")
        self.assertEqual(emp1_rec["check_in_time"], "09:15")

        # Test duplicate prevention (upsert): update same date to 'Half Day'
        payload_update = {
            str(self.emp1_id): {
                "status": "Half Day",
                "check_in_time": "09:15",
                "check_out_time": "13:00",
                "remarks": "Half day leave"
            }
        }
        success_upd, errors_upd = AttendanceService.mark_bulk_attendance(today_str, payload_update, user_name="TestAdmin")
        self.assertTrue(success_upd)
        self.assertEqual(errors_upd, [])

        records_upd = AttendanceService.get_daily_attendance(today_str)
        emp1_rec_upd = [r for r in records_upd if r["employee_id"] == self.emp1_id][0]
        self.assertEqual(emp1_rec_upd["attendance_status"], "Half Day")
        self.assertEqual(emp1_rec_upd["check_out_time"], "13:00")

    def test_future_date_validation(self):
        tomorrow_str = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        payload = {
            str(self.emp1_id): {
                "status": "Present"
            }
        }

        success, errors = AttendanceService.mark_bulk_attendance(tomorrow_str, payload, user_name="TestAdmin")
        self.assertFalse(success)
        self.assertTrue(any("future" in e for e in errors))

    def test_deactivated_employee_exclusion(self):
        today_str = datetime.date.today().isoformat()
        payload = {
            str(self.emp2_id): {
                "status": "Present"
            }
        }

        success, errors = AttendanceService.mark_bulk_attendance(today_str, payload, user_name="TestAdmin")
        self.assertFalse(success)
        self.assertTrue(any("deactivated" in e for e in errors))

    def test_dashboard_stats_calculation(self):
        today_str = datetime.date.today().isoformat()

        # Mark emp1 Present today
        payload = {
            str(self.emp1_id): {
                "status": "Present",
                "check_in_time": "09:00",
                "check_out_time": "18:00"
            }
        }
        AttendanceService.mark_bulk_attendance(today_str, payload, user_name="TestAdmin")

        stats = AttendanceService.get_dashboard_stats(today_str)
        self.assertEqual(stats["date"], today_str)
        self.assertGreaterEqual(stats["total_active_employees"], 1)
        self.assertEqual(stats["present_count"], 1)
        self.assertGreater(stats["attendance_percentage"], 0.0)

    def test_monthly_attendance_register(self):
        today = datetime.date.today()
        today_str = today.isoformat()

        payload = {
            str(self.emp1_id): {
                "status": "Present"
            }
        }
        AttendanceService.mark_bulk_attendance(today_str, payload, user_name="TestAdmin")

        reg_data = AttendanceService.get_monthly_register(today.year, today.month, department="Production")
        self.assertEqual(reg_data["year"], today.year)
        self.assertEqual(reg_data["month"], today.month)

        emp1_row = [r for r in reg_data["register"] if r["employee_id"] == self.emp1_id][0]
        self.assertEqual(emp1_row["days"][today.day], "P")
        self.assertEqual(emp1_row["present_count"], 1)

    def test_attendance_report_export(self):
        today_str = datetime.date.today().isoformat()
        payload = {
            str(self.emp1_id): {
                "status": "Present",
                "remarks": "On Duty"
            }
        }
        AttendanceService.mark_bulk_attendance(today_str, payload, user_name="TestAdmin")

        # Test CSV export
        csv_stream, mime_type, filename = AttendanceService.export_attendance_report(
            report_type="daily",
            format_type="csv",
            start_date=today_str,
            end_date=today_str
        )
        self.assertEqual(mime_type, "text/csv")
        self.assertTrue(filename.endswith(".csv"))

        content = csv_stream.getvalue().decode("utf-8")
        self.assertIn("ActiveAtt Test", content)
        self.assertIn("Present", content)

    def test_audit_log_integration(self):
        today_str = datetime.date.today().isoformat()
        payload = {
            str(self.emp1_id): {
                "status": "Present"
            }
        }
        AttendanceService.mark_bulk_attendance(today_str, payload, user_name="AuditAdmin")

        activities = get_recent_activities(limit=200)
        actions = [a["action"] for a in activities]
        self.assertIn("Bulk Attendance Completed", actions)


if __name__ == "__main__":
    unittest.main()
