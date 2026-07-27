import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename

from repositories import employee_repository, settings_repository
from repositories.activity_log_repository import log_activity
from erp_platform.events.event_bus import event_bus, ErpEvent
from services.employee_validator import EmployeeValidator

UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / "static" / "uploads" / "employees"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_profile_photo(file):
    if not file or not file.filename:
        return None
    if not _allowed_file(file.filename):
        raise ValueError("Invalid photo file type. Allowed formats: PNG, JPG, JPEG, WEBP.")

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"emp_{uuid.uuid4().hex[:12]}.{ext}"
    dest_path = UPLOAD_FOLDER / unique_filename
    file.save(dest_path)
    return f"/static/uploads/employees/{unique_filename}"


class EmployeeService:

    @staticmethod
    def get_dashboard_data():
        return employee_repository.get_dashboard_stats()

    @staticmethod
    def get_employees_list(search=None, department=None, designation=None, employment_type=None, status=None, page=1, per_page=10, sort_by="id", sort_dir="DESC"):
        return employee_repository.get_all_employees(
            search=search,
            department=department,
            designation=designation,
            employment_type=employment_type,
            status=status,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_dir=sort_dir
        )

    @staticmethod
    def get_employee(emp_id):
        return employee_repository.get_employee_by_id(emp_id)

    @staticmethod
    def create_employee(form_data, photo_file=None, user_name="System"):
        first_name = (form_data.get("first_name") or "").strip()
        last_name = (form_data.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip()

        emp_data = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "gender": form_data.get("gender"),
            "date_of_birth": form_data.get("date_of_birth") or None,
            "mobile_number": (form_data.get("mobile_number") or "").strip() or None,
            "email": (form_data.get("email") or "").strip().lower() or None,
            "joining_date": form_data.get("joining_date") or None,
            "department": (form_data.get("department") or "").strip() or None,
            "designation": (form_data.get("designation") or "").strip() or None,
            "reporting_manager": (form_data.get("reporting_manager") or "").strip() or None,
            "employment_type": form_data.get("employment_type", "Full-Time"),
            "status": form_data.get("status", "Active"),
            "current_address": (form_data.get("current_address") or "").strip() or None,
            "permanent_address": (form_data.get("permanent_address") or "").strip() or None,
            "aadhaar_number": (form_data.get("aadhaar_number") or "").strip() or None,
            "pan_number": (form_data.get("pan_number") or "").strip().upper() or None,
            "user_id": int(form_data["user_id"]) if form_data.get("user_id") and str(form_data["user_id"]).isdigit() else None,
            "created_by": user_name,
            "updated_by": user_name,
        }

        # Validate
        is_valid, errors = EmployeeValidator.validate(emp_data)
        if not is_valid:
            return None, errors

        # Handle Photo Upload
        if photo_file:
            photo_url = save_profile_photo(photo_file)
            if photo_url:
                emp_data["profile_photo"] = photo_url

        # Auto-generate Employee Code via Number Series
        emp_code = settings_repository.increment_and_get_number("EMPLOYEE")
        emp_data["employee_code"] = emp_code

        # Bank details
        bank_data = {
            "bank_name": (form_data.get("bank_name") or "").strip(),
            "account_holder_name": (form_data.get("account_holder_name") or "").strip(),
            "account_number": (form_data.get("account_number") or "").strip(),
            "ifsc_code": (form_data.get("ifsc_code") or "").strip().upper(),
            "branch_name": (form_data.get("branch_name") or "").strip(),
        }

        # Emergency contact
        emergency_contacts = []
        c_name = (form_data.get("emergency_contact_name") or "").strip()
        c_rel = (form_data.get("emergency_relationship") or "").strip()
        c_mob = (form_data.get("emergency_mobile") or "").strip()
        if c_name or c_mob:
            emergency_contacts.append({
                "contact_name": c_name,
                "relationship": c_rel,
                "mobile_number": c_mob
            })

        emp_id = employee_repository.create_employee(emp_data, bank_data, emergency_contacts)

        # Audit System & Event Bus Integration
        log_activity(
            user_name=user_name,
            action="Employee Created",
            details=f"Created employee {full_name} ({emp_code}) in {emp_data.get('department', 'N/A')}.",
            module="Employee",
            reference_number=emp_code
        )

        event_bus.publish(ErpEvent(
            event_type="Employee Created",
            source_module="Employee",
            payload={"employee_id": emp_id, "employee_code": emp_code, "full_name": full_name, "department": emp_data.get("department")},
            user_name=user_name
        ))

        return emp_id, []

    @staticmethod
    def update_employee(emp_id, form_data, photo_file=None, user_name="System"):
        existing = employee_repository.get_employee_by_id(emp_id)
        if not existing:
            return False, ["Employee not found."]

        first_name = (form_data.get("first_name") or "").strip()
        last_name = (form_data.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip()

        emp_data = {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "gender": form_data.get("gender"),
            "date_of_birth": form_data.get("date_of_birth") or None,
            "mobile_number": (form_data.get("mobile_number") or "").strip() or None,
            "email": (form_data.get("email") or "").strip().lower() or None,
            "joining_date": form_data.get("joining_date") or None,
            "department": (form_data.get("department") or "").strip() or None,
            "designation": (form_data.get("designation") or "").strip() or None,
            "reporting_manager": (form_data.get("reporting_manager") or "").strip() or None,
            "employment_type": form_data.get("employment_type", "Full-Time"),
            "status": form_data.get("status", "Active"),
            "current_address": (form_data.get("current_address") or "").strip() or None,
            "permanent_address": (form_data.get("permanent_address") or "").strip() or None,
            "aadhaar_number": (form_data.get("aadhaar_number") or "").strip() or None,
            "pan_number": (form_data.get("pan_number") or "").strip().upper() or None,
            "user_id": int(form_data["user_id"]) if form_data.get("user_id") and str(form_data["user_id"]).isdigit() else None,
            "updated_by": user_name,
        }

        # Validate
        is_valid, errors = EmployeeValidator.validate(emp_data, emp_id=emp_id)
        if not is_valid:
            return False, errors

        # Handle Photo Upload if updated
        if photo_file:
            photo_url = save_profile_photo(photo_file)
            if photo_url:
                emp_data["profile_photo"] = photo_url

        # Bank details
        bank_data = {
            "bank_name": (form_data.get("bank_name") or "").strip(),
            "account_holder_name": (form_data.get("account_holder_name") or "").strip(),
            "account_number": (form_data.get("account_number") or "").strip(),
            "ifsc_code": (form_data.get("ifsc_code") or "").strip().upper(),
            "branch_name": (form_data.get("branch_name") or "").strip(),
        }

        # Emergency contact
        emergency_contacts = []
        c_name = (form_data.get("emergency_contact_name") or "").strip()
        c_rel = (form_data.get("emergency_relationship") or "").strip()
        c_mob = (form_data.get("emergency_mobile") or "").strip()
        if c_name or c_mob:
            emergency_contacts.append({
                "contact_name": c_name,
                "relationship": c_rel,
                "mobile_number": c_mob
            })

        employee_repository.update_employee(emp_id, emp_data, bank_data, emergency_contacts)

        emp_code = existing["employee_code"]

        log_activity(
            user_name=user_name,
            action="Employee Updated",
            details=f"Updated employee record for {full_name} ({emp_code}).",
            module="Employee",
            reference_number=emp_code
        )

        event_bus.publish(ErpEvent(
            event_type="Employee Updated",
            source_module="Employee",
            payload={"employee_id": emp_id, "employee_code": emp_code, "full_name": full_name},
            user_name=user_name
        ))

        return True, []

    @staticmethod
    def toggle_status(emp_id, user_name="System"):
        emp = employee_repository.get_employee_by_id(emp_id)
        if not emp:
            return False, "Employee not found."

        new_status = "Inactive" if emp["status"] == "Active" else "Active"
        employee_repository.toggle_employee_status(emp_id, new_status, updated_by=user_name)

        action_name = "Employee Activated" if new_status == "Active" else "Employee Deactivated"
        log_activity(
            user_name=user_name,
            action=action_name,
            details=f"Toggled status of {emp['full_name']} ({emp['employee_code']}) to {new_status}.",
            module="Employee",
            reference_number=emp["employee_code"]
        )

        event_bus.publish(ErpEvent(
            event_type=action_name,
            source_module="Employee",
            payload={"employee_id": emp_id, "employee_code": emp["employee_code"], "new_status": new_status},
            user_name=user_name
        ))

        return True, f"Employee {emp['full_name']} has been set to {new_status}."

    @staticmethod
    def get_filter_options():
        return employee_repository.get_distinct_filter_options()

    @staticmethod
    def get_available_users(current_linked_user_id=None):
        return employee_repository.get_available_users(current_linked_user_id)
