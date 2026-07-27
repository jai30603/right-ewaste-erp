import datetime
from repositories import employee_repository, leave_repository


class LeaveValidator:

    @staticmethod
    def validate_leave_application(employee_id, leave_type_id, start_date_str, end_date_str, reason):
        errors = []

        # Active employee check
        emp = employee_repository.get_employee_by_id(employee_id)
        if not emp:
            errors.append("Employee not found.")
            return False, errors, 0.0
        elif emp.get("status") != "Active":
            errors.append(f"Employee '{emp.get('full_name')}' is inactive and cannot apply for leave.")
            return False, errors, 0.0

        # Leave type check
        lt = leave_repository.get_leave_type_by_id(leave_type_id)
        if not lt:
            errors.append("Invalid leave type selected.")
            return False, errors, 0.0

        # Date validations
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if end_date < start_date:
                errors.append("End date cannot be before Start date.")
            total_days = float((end_date - start_date).days + 1)
        except (ValueError, TypeError):
            errors.append("Invalid start or end date format. Must be YYYY-MM-DD.")
            total_days = 0.0

        # Reason check
        if not reason or not reason.strip():
            errors.append("Reason for leave is required.")

        if errors:
            return False, errors, total_days

        # Overlap check
        if leave_repository.check_leave_overlap(employee_id, start_date_str, end_date_str):
            errors.append("Leave dates overlap with another pending or approved leave request.")

        # Paid leave balance check
        if lt.get("is_paid") == 1:
            balances = leave_repository.get_employee_leave_balance(employee_id)
            lt_bal = [b for b in balances if b["leave_type_id"] == int(leave_type_id)]
            if lt_bal:
                rem = lt_bal[0]["remaining_days"]
                if rem < total_days:
                    errors.append(f"Insufficient {lt['leave_name']} balance. Required: {total_days} days, Remaining: {rem} days.")

        return len(errors) == 0, errors, total_days
