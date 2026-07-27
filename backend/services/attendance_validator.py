import datetime
from repositories import employee_repository

ALLOWED_STATUSES = {"Present", "Absent", "Half Day", "Leave", "Holiday"}


class AttendanceValidator:

    @staticmethod
    def validate_record(employee_id, date_str, status):
        errors = []

        # Validate date format & future date check
        try:
            att_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.date.today()
            if att_date > today:
                errors.append(f"Attendance date ({date_str}) cannot be in the future.")
        except (ValueError, TypeError):
            errors.append(f"Invalid date format: '{date_str}'. Must be YYYY-MM-DD.")

        # Validate status
        if status not in ALLOWED_STATUSES:
            errors.append(f"Invalid attendance status: '{status}'. Allowed: Present, Absent, Half Day, Leave, Holiday.")

        # Validate employee is active
        emp = employee_repository.get_employee_by_id(employee_id)
        if not emp:
            errors.append(f"Employee ID {employee_id} not found.")
        elif emp.get("status") != "Active":
            errors.append(f"Employee '{emp.get('full_name')}' ({emp.get('employee_code')}) is deactivated and cannot receive attendance.")

        return len(errors) == 0, errors

    @staticmethod
    def validate_bulk(records):
        all_errors = []
        for idx, rec in enumerate(records, 1):
            emp_id = rec.get("employee_id")
            att_date = rec.get("attendance_date")
            status = rec.get("attendance_status")

            is_valid, errors = AttendanceValidator.validate_record(emp_id, att_date, status)
            if not is_valid:
                for err in errors:
                    all_errors.append(f"Record {idx}: {err}")

        return len(all_errors) == 0, all_errors
