import io
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
from services.employee_service import EmployeeService
from services.attendance_service import AttendanceService
from services.leave_service import LeaveService
from services.payroll_service import PayrollService
from services.employee_document_service import EmployeeDocumentService
from services.employee_analytics_service import EmployeeAnalyticsService
from services.employee_report_service import EmployeeReportService
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning

employees_bp = Blueprint("employees", __name__)


def _get_current_user_name():
    if "user" in session and isinstance(session["user"], dict):
        return session["user"].get("username") or session["user"].get("full_name") or "System User"
    return "System User"


@employees_bp.route("/employees/dashboard")
def dashboard():
    stats = EmployeeService.get_dashboard_data()
    attendance_stats = AttendanceService.get_dashboard_stats()
    leave_stats = LeaveService.get_dashboard_stats()
    payroll_stats = PayrollService.get_dashboard_stats()
    return render_template(
        "employee/dashboard.html",
        stats=stats,
        attendance_stats=attendance_stats,
        leave_stats=leave_stats,
        payroll_stats=payroll_stats
    )


@employees_bp.route("/employees")
def list_employees():
    search = request.args.get("search", "").strip()
    department = request.args.get("department", "").strip()
    designation = request.args.get("designation", "").strip()
    employment_type = request.args.get("employment_type", "").strip()
    status = request.args.get("status", "").strip()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "DESC")

    result = EmployeeService.get_employees_list(
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

    filter_options = EmployeeService.get_filter_options()

    return render_template(
        "employee/list.html",
        employees=result["employees"],
        total_count=result["total_count"],
        total_pages=result["total_pages"],
        current_page=result["current_page"],
        per_page=result["per_page"],
        filter_options=filter_options,
        search=search,
        selected_department=department,
        selected_designation=designation,
        selected_employment_type=employment_type,
        selected_status=status,
        sort_by=sort_by,
        sort_dir=sort_dir
    )


@employees_bp.route("/employees/add", methods=["GET", "POST"])
def add_employee():
    if request.method == "POST":
        photo_file = request.files.get("profile_photo")
        user_name = _get_current_user_name()
        emp_id, errors = EmployeeService.create_employee(request.form, photo_file=photo_file, user_name=user_name)
        if errors:
            for err in errors:
                flash_error(err)
            available_users = EmployeeService.get_available_users()
            return render_template("employee/form.html", form_data=request.form, available_users=available_users, is_edit=False)

        flash_success("Employee created successfully!")
        return redirect(url_for("employees.view_employee", emp_id=emp_id))

    available_users = EmployeeService.get_available_users()
    return render_template("employee/form.html", form_data={}, available_users=available_users, is_edit=False)


@employees_bp.route("/employees/<int:emp_id>")
def view_employee(emp_id):
    employee = EmployeeService.get_employee(emp_id)
    if not employee:
        flash_error("Employee not found.")
        return redirect(url_for("employees.list_employees"))

    attendance_history = AttendanceService.get_employee_history(emp_id)
    leave_balance = LeaveService.get_employee_balance(emp_id)
    leave_history = LeaveService.get_leave_requests(employee_id=emp_id)
    salary_structure = PayrollService.get_salary_structure(emp_id)
    payroll_history = PayrollService.get_payroll_records(search=employee.get("employee_code"))
    documents = EmployeeDocumentService.get_employee_documents(emp_id)

    return render_template(
        "employee/profile.html",
        employee=employee,
        attendance_history=attendance_history,
        leave_balance=leave_balance,
        leave_history=leave_history["requests"],
        salary_structure=salary_structure,
        payroll_history=payroll_history["records"],
        documents=documents
    )


@employees_bp.route("/employees/<int:emp_id>/edit", methods=["GET", "POST"])
def edit_employee(emp_id):
    employee = EmployeeService.get_employee(emp_id)
    if not employee:
        flash_error("Employee not found.")
        return redirect(url_for("employees.list_employees"))

    if request.method == "POST":
        photo_file = request.files.get("profile_photo")
        user_name = _get_current_user_name()
        success, errors = EmployeeService.update_employee(emp_id, request.form, photo_file=photo_file, user_name=user_name)
        if errors:
            for err in errors:
                flash_error(err)
            available_users = EmployeeService.get_available_users(current_linked_user_id=employee.get("user_id"))
            return render_template("employee/form.html", form_data=request.form, employee=employee, available_users=available_users, is_edit=True)

        flash_success("Employee profile updated successfully!")
        return redirect(url_for("employees.view_employee", emp_id=emp_id))

    available_users = EmployeeService.get_available_users(current_linked_user_id=employee.get("user_id"))
    return render_template("employee/form.html", employee=employee, form_data=employee, available_users=available_users, is_edit=True)


@employees_bp.route("/employees/<int:emp_id>/toggle-status", methods=["POST"])
def toggle_status(emp_id):
    user_name = _get_current_user_name()
    success, msg = EmployeeService.toggle_status(emp_id, user_name=user_name)
    if success:
        flash_success(msg)
    else:
        flash_error(msg)
    return redirect(request.referrer or url_for("employees.list_employees"))


@employees_bp.route("/employees/export")
def export_employees():
    result = EmployeeService.get_employees_list(per_page=5000)
    employees = result["employees"]

    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Employees"

        headers = [
            "Employee Code", "Full Name", "Gender", "DOB", "Mobile", "Email",
            "Joining Date", "Department", "Designation", "Employment Type",
            "Status", "Current Address", "Aadhaar", "PAN"
        ]
        ws.append(headers)

        for emp in employees:
            ws.append([
                emp.get("employee_code"),
                emp.get("full_name"),
                emp.get("gender"),
                emp.get("date_of_birth"),
                emp.get("mobile_number"),
                emp.get("email"),
                emp.get("joining_date"),
                emp.get("department"),
                emp.get("designation"),
                emp.get("employment_type"),
                emp.get("status"),
                emp.get("current_address"),
                emp.get("aadhaar_number"),
                emp.get("pan_number")
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="employees_export.xlsx"
        )
    except Exception:
        # Fallback to CSV format
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        headers = ["Employee Code", "Full Name", "Gender", "DOB", "Mobile", "Email", "Department", "Designation", "Status"]
        writer.writerow(headers)
        for emp in employees:
            writer.writerow([
                emp.get("employee_code"), emp.get("full_name"), emp.get("gender"),
                emp.get("date_of_birth"), emp.get("mobile_number"), emp.get("email"),
                emp.get("department"), emp.get("designation"), emp.get("status")
            ])
        mem = io.BytesIO()
        mem.write(output.getvalue().encode("utf-8"))
        mem.seek(0)
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name="employees_export.csv"
        )


# ── Attendance Management Routes ──────────────────────────────────────────────

@employees_bp.route("/employees/attendance/dashboard")
def attendance_dashboard():
    date_str = request.args.get("date") or datetime.date.today().isoformat()
    stats = AttendanceService.get_dashboard_stats(date_str)
    return render_template("attendance/dashboard.html", stats=stats)


@employees_bp.route("/employees/attendance/daily", methods=["GET", "POST"])
def daily_attendance():
    date_str = request.args.get("date") or request.form.get("attendance_date") or datetime.date.today().isoformat()
    department = request.args.get("department", "").strip()
    search = request.args.get("search", "").strip()

    if request.method == "POST":
        # Parse submitted attendance data: attendance[emp_id][status], attendance[emp_id][check_in], etc.
        attendance_payload = {}
        for key, value in request.form.items():
            if key.startswith("status_"):
                emp_id = key.replace("status_", "")
                if emp_id not in attendance_payload:
                    attendance_payload[emp_id] = {}
                attendance_payload[emp_id]["status"] = value
            elif key.startswith("check_in_"):
                emp_id = key.replace("check_in_", "")
                if emp_id not in attendance_payload:
                    attendance_payload[emp_id] = {}
                attendance_payload[emp_id]["check_in_time"] = value
            elif key.startswith("check_out_"):
                emp_id = key.replace("check_out_", "")
                if emp_id not in attendance_payload:
                    attendance_payload[emp_id] = {}
                attendance_payload[emp_id]["check_out_time"] = value
            elif key.startswith("remarks_"):
                emp_id = key.replace("remarks_", "")
                if emp_id not in attendance_payload:
                    attendance_payload[emp_id] = {}
                attendance_payload[emp_id]["remarks"] = value

        user_name = _get_current_user_name()
        success, errors = AttendanceService.mark_bulk_attendance(date_str, attendance_payload, user_name=user_name)
        if errors:
            for err in errors:
                flash_error(err)
        else:
            flash_success(f"Attendance for {date_str} saved successfully!")
            return redirect(url_for("employees.daily_attendance", date=date_str, department=department))

    daily_records = AttendanceService.get_daily_attendance(date_str, department=department, search=search)
    filter_options = EmployeeService.get_filter_options()
    today_str = datetime.date.today().isoformat()

    return render_template(
        "attendance/daily.html",
        daily_records=daily_records,
        date_str=date_str,
        today_str=today_str,
        filter_options=filter_options,
        selected_department=department,
        search=search
    )


@employees_bp.route("/employees/attendance/register")
def attendance_register():
    today = datetime.date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    department = request.args.get("department", "").strip()
    search = request.args.get("search", "").strip()

    register_data = AttendanceService.get_monthly_register(year, month, department=department, search=search)
    filter_options = EmployeeService.get_filter_options()

    return render_template(
        "attendance/register.html",
        register_data=register_data,
        selected_year=year,
        selected_month=month,
        selected_department=department,
        search=search,
        filter_options=filter_options,
        current_year=today.year
    )


@employees_bp.route("/employees/attendance/calendar/<int:emp_id>")
def attendance_calendar(emp_id):
    employee = EmployeeService.get_employee(emp_id)
    if not employee:
        flash_error("Employee not found.")
        return redirect(url_for("employees.list_employees"))

    today = datetime.date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    history = AttendanceService.get_employee_history(emp_id, year=year, month=month)

    # Build calendar grid
    import calendar as cal_mod
    cal = cal_mod.Calendar(firstweekday=0) # Monday first
    month_days = cal.monthdatescalendar(year, month)

    att_by_date = {r["attendance_date"]: r for r in history["records"]}

    return render_template(
        "attendance/calendar.html",
        employee=employee,
        history=history,
        month_days=month_days,
        att_by_date=att_by_date,
        selected_year=year,
        selected_month=month,
        today_str=today.isoformat()
    )


@employees_bp.route("/employees/attendance/reports")
def attendance_reports():
    today = datetime.date.today()
    filter_options = EmployeeService.get_filter_options()
    employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]
    return render_template(
        "attendance/reports.html",
        filter_options=filter_options,
        employees=employees_list,
        today_str=today.isoformat()
    )


@employees_bp.route("/employees/attendance/export")
def export_attendance():
    report_type = request.args.get("report_type", "daily")
    format_type = request.args.get("format", "csv").lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    month = request.args.get("month")
    year = request.args.get("year")
    department = request.args.get("department")
    employee_id = request.args.get("employee_id")

    file_stream, mime_type, filename = AttendanceService.export_attendance_report(
        report_type=report_type,
        format_type=format_type,
        start_date=start_date,
        end_date=end_date,
        month=month,
        year=year,
        department=department,
        employee_id=employee_id
    )

    return send_file(
        file_stream,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )


# ── Leave Management Routes ───────────────────────────────────────────────────

@employees_bp.route("/employees/leave/dashboard")
def leave_dashboard():
    stats = LeaveService.get_dashboard_stats()
    return render_template("leave/dashboard.html", stats=stats)


@employees_bp.route("/employees/leave/types", methods=["GET", "POST"])
def leave_types():
    if request.method == "POST":
        LeaveService.save_leave_type(request.form)
        flash_success("Leave type configuration saved.")
        return redirect(url_for("employees.leave_types"))

    leave_types_list = LeaveService.get_leave_types()
    return render_template("leave/types.html", leave_types=leave_types_list)


@employees_bp.route("/employees/leave/apply", methods=["GET", "POST"])
def apply_leave():
    if request.method == "POST":
        attachment_file = request.files.get("attachment")
        user_name = _get_current_user_name()
        req_id, errors = LeaveService.apply_leave(request.form, attachment_file=attachment_file, user_name=user_name)
        if errors:
            for err in errors:
                flash_error(err)
            employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]
            leave_types_list = LeaveService.get_leave_types(active_only=True)
            return render_template("leave/apply.html", form_data=request.form, employees=employees_list, leave_types=leave_types_list)

        flash_success("Leave application submitted successfully!")
        return redirect(url_for("employees.leave_requests"))

    employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]
    leave_types_list = LeaveService.get_leave_types(active_only=True)
    today_str = datetime.date.today().isoformat()

    return render_template(
        "leave/apply.html",
        form_data={},
        employees=employees_list,
        leave_types=leave_types_list,
        today_str=today_str
    )


@employees_bp.route("/employees/leave/requests")
def leave_requests():
    status = request.args.get("status", "").strip()
    department = request.args.get("department", "").strip()
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))

    result = LeaveService.get_leave_requests(status=status, department=department, search=search, page=page)
    filter_options = EmployeeService.get_filter_options()

    return render_template(
        "leave/requests.html",
        requests=result["requests"],
        total_count=result["total_count"],
        total_pages=result["total_pages"],
        current_page=result["current_page"],
        filter_options=filter_options,
        selected_status=status,
        selected_department=department,
        search=search
    )


@employees_bp.route("/employees/leave/requests/<int:req_id>/action", methods=["POST"])
def leave_action(req_id):
    action = request.form.get("action")
    user_name = _get_current_user_name()
    rejection_reason = request.form.get("rejection_reason", "").strip()

    if action == "approve":
        success, msg = LeaveService.approve_leave(req_id, user_name=user_name)
    elif action == "reject":
        success, msg = LeaveService.reject_leave(req_id, rejection_reason=rejection_reason, user_name=user_name)
    elif action == "cancel":
        success, msg = LeaveService.cancel_leave(req_id, user_name=user_name)
    else:
        success, msg = False, "Invalid action."

    if success:
        flash_success(msg)
    else:
        flash_error(msg)

    return redirect(request.referrer or url_for("employees.leave_requests"))


@employees_bp.route("/employees/leave/calendar")
def leave_calendar():
    today = datetime.date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    department = request.args.get("department", "").strip()
    leave_type_id = request.args.get("leave_type_id", "").strip()

    # Fetch all leave requests for month
    start_date = f"{year:04d}-{month:02d}-01"
    import calendar as cal_mod
    _, num_days = cal_mod.monthrange(year, month)
    end_date = f"{year:04d}-{month:02d}-{num_days:02d}"

    result = LeaveService.get_leave_requests(status="Approved", department=department, per_page=1000)

    filter_options = EmployeeService.get_filter_options()
    leave_types_list = LeaveService.get_leave_types()

    return render_template(
        "leave/calendar.html",
        approved_requests=result["requests"],
        selected_year=year,
        selected_month=month,
        selected_department=department,
        selected_leave_type_id=leave_type_id,
        filter_options=filter_options,
        leave_types=leave_types_list,
        today_str=today.isoformat(),
        num_days=num_days
    )


@employees_bp.route("/employees/leave/reports")
def leave_reports():
    today = datetime.date.today()
    filter_options = EmployeeService.get_filter_options()
    employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]
    return render_template(
        "leave/reports.html",
        filter_options=filter_options,
        employees=employees_list,
        today_str=today.isoformat()
    )


@employees_bp.route("/employees/leave/export")
def export_leave():
    report_type = request.args.get("report_type", "register")
    format_type = request.args.get("format", "csv").lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    department = request.args.get("department")
    employee_id = request.args.get("employee_id")

    file_stream, mime_type, filename = LeaveService.export_leave_report(
        report_type=report_type,
        format_type=format_type,
        start_date=start_date,
        end_date=end_date,
        department=department,
        employee_id=employee_id
    )

    return send_file(
        file_stream,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )


# ── Payroll Management Routes ─────────────────────────────────────────────────

@employees_bp.route("/employees/payroll/dashboard")
def payroll_dashboard():
    stats = PayrollService.get_dashboard_stats()
    return render_template("payroll/dashboard.html", stats=stats)


@employees_bp.route("/employees/payroll/structure", methods=["GET", "POST"])
def payroll_structure():
    if request.method == "POST":
        user_name = _get_current_user_name()
        struct_id, errors = PayrollService.save_salary_structure(request.form, user_name=user_name)
        if errors:
            for err in errors:
                flash_error(err)
        else:
            flash_success("Salary structure saved successfully!")

        selected_emp_id = request.form.get("employee_id")
        return redirect(url_for("employees.payroll_structure", employee_id=selected_emp_id))

    emp_id = request.args.get("employee_id")
    employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]

    selected_emp = None
    structure = None
    history = []

    if emp_id:
        selected_emp = EmployeeService.get_employee(int(emp_id))
        structure = PayrollService.get_salary_structure(int(emp_id))
        history = PayrollService.get_salary_structure_history(int(emp_id))
    elif employees_list:
        first_id = employees_list[0]["id"]
        return redirect(url_for("employees.payroll_structure", employee_id=first_id))

    today_str = datetime.date.today().isoformat()

    return render_template(
        "payroll/structure.html",
        employees=employees_list,
        selected_employee=selected_emp,
        structure=structure,
        history=history,
        today_str=today_str
    )


@employees_bp.route("/employees/payroll/generate", methods=["GET", "POST"])
def payroll_generate():
    today = datetime.date.today()
    if request.method == "POST":
        month = int(request.form.get("month", today.month))
        year = int(request.form.get("year", today.year))
        user_name = _get_current_user_name()

        gen_cnt, skip_cnt, errors = PayrollService.generate_monthly_payroll(month, year, user_name=user_name)
        if errors:
            for err in errors:
                flash_error(err)
        if gen_cnt > 0:
            flash_success(f"Successfully generated payroll for {gen_cnt} employee(s).")
        elif skip_cnt > 0:
            flash_warning(f"Skipped {skip_cnt} employee(s) with already Paid payroll.")
        else:
            flash_warning("No active employees with valid salary structure processed.")

        return redirect(url_for("employees.payroll_records", month=month, year=year))

    return render_template(
        "payroll/generate.html",
        current_month=today.month,
        current_year=today.year
    )


@employees_bp.route("/employees/payroll/records")
def payroll_records():
    today = datetime.date.today()
    month = request.args.get("month", str(today.month))
    year = request.args.get("year", str(today.year))
    department = request.args.get("department", "").strip()
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))

    m_val = int(month) if month.isdigit() else None
    y_val = int(year) if year.isdigit() else None

    result = PayrollService.get_payroll_records(
        month=m_val, year=y_val, department=department, status=status, search=search, page=page
    )

    filter_options = EmployeeService.get_filter_options()

    return render_template(
        "payroll/records.html",
        records=result["records"],
        total_count=result["total_count"],
        total_pages=result["total_pages"],
        current_page=result["current_page"],
        filter_options=filter_options,
        selected_month=m_val,
        selected_year=y_val,
        selected_department=department,
        selected_status=status,
        search=search,
        current_year=today.year
    )


@employees_bp.route("/employees/payroll/records/<int:payroll_id>/status", methods=["POST"])
def payroll_status_update(payroll_id):
    new_status = request.form.get("status")
    user_name = _get_current_user_name()
    success, msg = PayrollService.update_payroll_status(payroll_id, new_status, user_name=user_name)
    if success:
        flash_success(msg)
    else:
        flash_error(msg)
    return redirect(request.referrer or url_for("employees.payroll_records"))


@employees_bp.route("/employees/payroll/payslip/<int:payroll_id>")
def view_payslip(payroll_id):
    rec = PayrollService.get_payroll_by_id(payroll_id)
    if not rec:
        flash_error("Payslip not found.")
        return redirect(url_for("employees.payroll_records"))

    month_name = datetime.date(rec["payroll_year"], rec["payroll_month"], 1).strftime("%B %Y")
    return render_template("payroll/payslip.html", rec=rec, month_name=month_name)


@employees_bp.route("/employees/payroll/payslip/<int:payroll_id>/pdf")
def download_payslip_pdf(payroll_id):
    pdf_stream, err = PayrollService.render_payslip_pdf(payroll_id)
    if err:
        flash_error(err)
        return redirect(url_for("employees.view_payslip", payroll_id=payroll_id))

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"payslip_{payroll_id}.pdf"
    )


@employees_bp.route("/employees/payroll/reports")
def payroll_reports():
    today = datetime.date.today()
    filter_options = EmployeeService.get_filter_options()
    employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]
    return render_template(
        "payroll/reports.html",
        filter_options=filter_options,
        employees=employees_list,
        today_str=today.isoformat(),
        current_month=today.month,
        current_year=today.year
    )


@employees_bp.route("/employees/payroll/export")
def export_payroll():
    report_type = request.args.get("report_type", "register")
    format_type = request.args.get("format", "csv").lower()
    month = request.args.get("month")
    year = request.args.get("year")
    department = request.args.get("department")
    employee_id = request.args.get("employee_id")

    m_val = int(month) if month and month.isdigit() else None
    y_val = int(year) if year and year.isdigit() else None

    file_stream, mime_type, filename = PayrollService.export_payroll_report(
        report_type=report_type,
        format_type=format_type,
        month=m_val,
        year=y_val,
        department=department,
        employee_id=employee_id
    )

    return send_file(
        file_stream,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )


# ── Analytics, Documents & Consolidated Reports Routes ─────────────────────────

@employees_bp.route("/employees/analytics")
def analytics():
    data = EmployeeAnalyticsService.get_analytics()
    return render_template("employee/analytics.html", analytics=data)


@employees_bp.route("/employees/reports")
def reports():
    filter_options = EmployeeService.get_filter_options()
    employees_list = EmployeeService.get_employees_list(per_page=1000)["employees"]
    today_str = datetime.date.today().isoformat()
    return render_template("employee/reports.html", filter_options=filter_options, employees=employees_list, today_str=today_str)


@employees_bp.route("/employees/<int:emp_id>/documents/upload", methods=["POST"])
def upload_document(emp_id):
    category = request.form.get("document_category")
    doc_file = request.files.get("document_file")
    user_name = _get_current_user_name()

    doc_id, errors = EmployeeDocumentService.upload_document(emp_id, category, doc_file, user_name=user_name)
    if errors:
        for err in errors:
            flash_error(err)
    else:
        flash_success(f"Uploaded '{category}' document successfully.")

    return redirect(url_for("employees.view_employee", emp_id=emp_id) + "#documents")


@employees_bp.route("/employees/<int:emp_id>/documents/<int:doc_id>/delete", methods=["POST"])
def delete_document(emp_id, doc_id):
    user_name = _get_current_user_name()
    success, msg = EmployeeDocumentService.delete_document(doc_id, user_name=user_name)
    if success:
        flash_success(msg)
    else:
        flash_error(msg)

    return redirect(url_for("employees.view_employee", emp_id=emp_id) + "#documents")


@employees_bp.route("/employees/export/directory")
def export_directory():
    format_type = request.args.get("format", "csv").lower()
    department = request.args.get("department")
    status = request.args.get("status")
    search = request.args.get("search")

    file_stream, mime_type, filename = EmployeeReportService.export_employee_directory(
        format_type=format_type, department=department, status=status, search=search
    )

    return send_file(
        file_stream,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )




