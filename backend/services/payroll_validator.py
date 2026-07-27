import datetime
from repositories import employee_repository, payroll_repository


class PayrollValidator:

    @staticmethod
    def validate_salary_structure(form_data):
        errors = []

        employee_id = form_data.get("employee_id")
        if not employee_id:
            errors.append("Employee is required.")
        else:
            emp = employee_repository.get_employee_by_id(employee_id)
            if not emp:
                errors.append("Employee not found.")
            elif emp.get("status") != "Active":
                errors.append(f"Employee '{emp.get('full_name')}' is inactive and cannot have salary structure updated.")

        try:
            basic = float(form_data.get("basic_salary", 0))
            if basic < 0:
                errors.append("Basic salary cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Invalid basic salary amount.")

        for field in ["hra", "conveyance_allowance", "medical_allowance", "special_allowance", "other_allowances", "provident_fund", "professional_tax", "income_tax", "other_deductions"]:
            val = form_data.get(field)
            if val:
                try:
                    num = float(val)
                    if num < 0:
                        errors.append(f"{field.replace('_', ' ').title()} cannot be negative.")
                except (ValueError, TypeError):
                    errors.append(f"Invalid amount for {field.replace('_', ' ').title()}.")

        effective_from = form_data.get("effective_from")
        if effective_from:
            try:
                datetime.datetime.strptime(effective_from, "%Y-%m-%d")
            except ValueError:
                errors.append("Effective date must be in YYYY-MM-DD format.")

        return len(errors) == 0, errors

    @staticmethod
    def validate_payroll_generation(month, year):
        errors = []
        try:
            m = int(month)
            if not (1 <= m <= 12):
                errors.append("Month must be between 1 and 12.")
        except (ValueError, TypeError):
            errors.append("Invalid month selected.")

        try:
            y = int(year)
            if y < 2020 or y > 2035:
                errors.append("Invalid year selected.")
        except (ValueError, TypeError):
            errors.append("Invalid year selected.")

        return len(errors) == 0, errors
