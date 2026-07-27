from flask import Blueprint, render_template, request, redirect, url_for
from repositories.company_repository import get_company, update_company
from repositories.activity_log_repository import log_activity
from backend.common.utils.flash_helpers import flash_success, flash_error

company_bp = Blueprint("company", __name__)

@company_bp.route("/company", methods=["GET", "POST"])
def company():
    if request.method == "POST":
        data = {
            "company_name": request.form.get("company_name", "").strip(),
            "address_line_1": request.form.get("address_line_1", "").strip(),
            "address_line_2": request.form.get("address_line_2", "").strip(),
            "city": request.form.get("city", "").strip(),
            "state": request.form.get("state", "").strip(),
            "state_code": request.form.get("state_code", "").strip(),
            "pincode": request.form.get("pincode", "").strip(),
            "gstin": request.form.get("gstin", "").strip().upper(),
            "pan": request.form.get("pan", "").strip().upper(),
            "cin": request.form.get("cin", "").strip().upper(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "website": request.form.get("website", "").strip(),
        }
        
        # Simple validations
        if not data["company_name"] or not data["gstin"] or not data["pan"]:
            flash_error("Company name, GSTIN, and PAN are required fields.")
            return redirect(url_for("company.company"))
            
        try:
            update_company(data)
            log_activity("System Administrator", "Company Profile Updated", f"Updated company details for {data['company_name']}", module="Company")
            flash_success("Company profile updated successfully.")
        except Exception as e:
            flash_error(f"Failed to update company profile: {str(e)}")
            
        return redirect(url_for("company.company"))

    comp = get_company()
    return render_template("company/company.html", company=comp)