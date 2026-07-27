import re
from repositories import employee_repository

class EmployeeValidator:

    @staticmethod
    def validate(emp_data, emp_id=None):
        errors = []

        # Required fields
        first_name = (emp_data.get("first_name") or "").strip()
        if not first_name:
            errors.append("First Name is required.")

        mobile = (emp_data.get("mobile_number") or "").strip()
        if not mobile:
            errors.append("Mobile Number is required.")
        elif not re.match(r"^\+?\d{10,15}$", mobile):
            errors.append("Mobile Number must contain 10 to 15 digits.")

        email = (emp_data.get("email") or "").strip()
        if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            errors.append("Invalid email format.")

        aadhaar = (emp_data.get("aadhaar_number") or "").strip()
        if aadhaar and not re.match(r"^\d{12}$", aadhaar):
            errors.append("Aadhaar Number must be exactly 12 digits.")

        pan = (emp_data.get("pan_number") or "").strip().upper()
        if pan and not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan):
            errors.append("PAN Number format must be 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).")

        # Uniqueness validations
        if email and not employee_repository.check_uniqueness("email", email, exclude_id=emp_id):
            errors.append(f"An employee with email '{email}' already exists.")

        if mobile and not employee_repository.check_uniqueness("mobile_number", mobile, exclude_id=emp_id):
            errors.append(f"An employee with mobile number '{mobile}' already exists.")

        if aadhaar and not employee_repository.check_uniqueness("aadhaar_number", aadhaar, exclude_id=emp_id):
            errors.append(f"An employee with Aadhaar number '{aadhaar}' already exists.")

        if pan and not employee_repository.check_uniqueness("pan_number", pan, exclude_id=emp_id):
            errors.append(f"An employee with PAN number '{pan}' already exists.")

        return len(errors) == 0, errors
