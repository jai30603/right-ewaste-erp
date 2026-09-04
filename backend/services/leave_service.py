import csv
import io
import datetime
import uuid
from pathlib import Path
from repositories import leave_repository, employee_repository
from repositories.activity_log_repository import log_activity
from erp_platform.events.event_bus import event_bus, ErpEvent
from services.leave_validator import LeaveValidator

LEAVE_UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / "static" / "uploads" / "leaves"


def save_leave_attachment(file):
    if not file or not file.filename:
        return None
    LEAVE_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "file"
    filename = f"leave_{uuid.uuid4().hex[:12]}.{ext}"
    dest_path = LEAVE_UPLOAD_FOLDER / filename
    file.save(dest_path)
    return f"/static/uploads/leaves/{filename}"


class LeaveService:

    @staticmethod
    def get_dashboard_stats():
        return leave_repository.get_leave_dashboard_stats()

    @staticmethod
    def get_leave_types(active_only=False):
        return leave_repository.get_all_leave_types(active_only=active_only)

    @staticmethod
    def save_leave_type(form_data):
        return leave_repository.save_leave_type(form_data)

    @staticmethod
    def get_leave_requests(status=None, employee_id=None, department=None, search=None, page=1, per_page=10):
        return leave_repository.get_leave_requests(status=status, employee_id=employee_id, department=department, search=search, page=page, per_page=per_page)

    @staticmethod
    def get_leave_request(req_id):
        return leave_repository.get_leave_request_by_id(req_id)

    @staticmethod
    def get_employee_balance(employee_id, financial_year=2026):
        return leave_repository.get_employee_leave_balance(employee_id, financial_year=financial_year)

    @staticmethod
    def apply_leave(form_data, attachment_file=None, user_name="System"):
        employee_id = int(form_data["employee_id"])
        leave_type_id = int(form_data["leave_type_id"])
        start_date_str = form_data["start_date"]
        end_date_str = form_data["end_date"]
        reason = (form_data.get("reason") or "").strip()

        # Validate
        is_valid, errors, total_days = LeaveValidator.validate_leave_application(
            employee_id, leave_type_id, start_date_str, end_date_str, reason
        )
        if not is_valid:
            return None, errors

        attachment_path = None
        if attachment_file:
            attachment_path = save_leave_attachment(attachment_file)

        req_data = {
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "total_days": total_days,
            "reason": reason,
            "attachment_path": attachment_path
        }

        req_id = leave_repository.create_leave_request(req_data)
        emp = employee_repository.get_employee_by_id(employee_id)
        emp_name = emp.get("full_name") if emp else f"ID #{employee_id}"

        log_activity(
            user_name=user_name,
            action="Leave Applied",
            details=f"{emp_name} applied for {total_days} days leave ({start_date_str} to {end_date_str}).",
            module="Leave",
            reference_number=f"LR-{req_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Leave Applied",
            source_module="Leave",
            payload={"request_id": req_id, "employee_id": employee_id, "total_days": total_days},
            user_name=user_name
        ))

        return req_id, []

    @staticmethod
    def approve_leave(req_id, user_name="System"):
        req = leave_repository.get_leave_request_by_id(req_id)
        if not req:
            return False, "Leave request not found."
        if req["status"] == "Approved":
            return False, "Leave request is already approved."

        # Balance check
        if req["is_paid"] == 1:
            balances = leave_repository.get_employee_leave_balance(req["employee_id"])
            lt_bal = [b for b in balances if b["leave_type_id"] == req["leave_type_id"]]
            if lt_bal and lt_bal[0]["remaining_days"] < req["total_days"]:
                return False, f"Insufficient leave balance ({lt_bal[0]['remaining_days']} days remaining)."

        success, err = leave_repository.update_leave_request_status(req_id, "Approved", approved_by=user_name)
        if not success:
            return False, err

        log_activity(
            user_name=user_name,
            action="Leave Approved",
            details=f"Approved leave request #{req_id} for {req['full_name']} ({req['total_days']} days).",
            module="Leave",
            reference_number=f"LR-{req_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Leave Approved",
            source_module="Leave",
            payload={"request_id": req_id, "employee_id": req["employee_id"], "total_days": req["total_days"]},
            user_name=user_name
        ))

        return True, "Leave request approved successfully."

    @staticmethod
    def reject_leave(req_id, rejection_reason, user_name="System"):
        req = leave_repository.get_leave_request_by_id(req_id)
        if not req:
            return False, "Leave request not found."

        success, err = leave_repository.update_leave_request_status(req_id, "Rejected", approved_by=user_name, rejection_reason=rejection_reason)
        if not success:
            return False, err

        log_activity(
            user_name=user_name,
            action="Leave Rejected",
            details=f"Rejected leave request #{req_id} for {req['full_name']}. Reason: {rejection_reason or 'None'}.",
            module="Leave",
            reference_number=f"LR-{req_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Leave Rejected",
            source_module="Leave",
            payload={"request_id": req_id, "employee_id": req["employee_id"], "reason": rejection_reason},
            user_name=user_name
        ))

        return True, "Leave request rejected."

    @staticmethod
    def cancel_leave(req_id, user_name="System"):
        req = leave_repository.get_leave_request_by_id(req_id)
        if not req:
            return False, "Leave request not found."

        success, err = leave_repository.update_leave_request_status(req_id, "Cancelled", approved_by=user_name)
        if not success:
            return False, err

        log_activity(
            user_name=user_name,
            action="Leave Cancelled",
            details=f"Cancelled leave request #{req_id} for {req['full_name']}.",
            module="Leave",
            reference_number=f"LR-{req_id}"
        )

        event_bus.publish(ErpEvent(
            event_type="Leave Cancelled",
            source_module="Leave",
            payload={"request_id": req_id, "employee_id": req["employee_id"]},
            user_name=user_name
        ))

        return True, "Leave request cancelled."

    @staticmethod
    def export_leave_report(report_type, format_type, start_date=None, end_date=None, department=None, employee_id=None):
        rows = leave_repository.get_leave_report_data(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            department=department,
            employee_id=employee_id
        )

        filename = f"leave_report_{report_type}_{datetime.date.today().isoformat()}"

        if format_type == "excel":
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Leave Report"

                headers = ["Request ID", "Employee Code", "Full Name", "Department", "Leave Type", "Start Date", "End Date", "Total Days", "Status", "Reason", "Approved By"]
                ws.append(headers)

                for r in rows:
                    ws.append([
                        r.get("id"),
                        r.get("employee_code"),
                        r.get("full_name"),
                        r.get("department"),
                        r.get("leave_name"),
                        r.get("start_date"),
                        r.get("end_date"),
                        r.get("total_days"),
                        r.get("status"),
                        r.get("reason"),
                        r.get("approved_by")
                    ])

                out = io.BytesIO()
                wb.save(out)
                out.seek(0)
                return out, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{filename}.xlsx"
            except Exception:
                format_type = "csv"

        if format_type == "csv":
            out_str = io.StringIO()
            writer = csv.writer(out_str)
            writer.writerow(["Request ID", "Employee Code", "Full Name", "Department", "Leave Type", "Start Date", "End Date", "Total Days", "Status", "Reason", "Approved By"])
            for r in rows:
                writer.writerow([
                    r.get("id"), r.get("employee_code"), r.get("full_name"),
                    r.get("department"), r.get("leave_name"), r.get("start_date"),
                    r.get("end_date"), r.get("total_days"), r.get("status"),
                    r.get("reason"), r.get("approved_by")
                ])
            mem = io.BytesIO(out_str.getvalue().encode("utf-8"))
            mem.seek(0)
            return mem, "text/csv", f"{filename}.csv"

        if format_type == "pdf":
            try:
                from backend.services.pdf_service import compile_html_to_pdf
                html_content = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 10px; }}
                        h2 {{ text-align: center; color: #1e293b; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                        th, td {{ border: 1px solid #cbd5e1; padding: 5px; text-align: left; }}
                        th {{ background-color: #f1f5f9; }}
                    </style>
                </head>
                <body>
                    <h2>Right Ewaste ERP - Leave Management Report</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Emp Code</th>
                                <th>Name</th>
                                <th>Type</th>
                                <th>Dates</th>
                                <th>Days</th>
                                <th>Status</th>
                                <th>Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>{r.get('employee_code')}</td><td>{r.get('full_name')}</td><td>{r.get('leave_name')}</td><td>{r.get('start_date')} to {r.get('end_date')}</td><td>{r.get('total_days')}</td><td>{r.get('status')}</td><td>{r.get('reason') or ''}</td></tr>" for r in rows])}
                        </tbody>
                    </table>
                </body>
                </html>
                """
                pdf_bytes = compile_html_to_pdf(html_content)
                pdf_out = io.BytesIO(pdf_bytes)
                pdf_out.seek(0)
                return pdf_out, "application/pdf", f"{filename}.pdf"
            except Exception as e:
                print("Error in leave PDF generation:", e)

            out_str = io.StringIO()
            writer = csv.writer(out_str)
            writer.writerow(["Request ID", "Employee Code", "Full Name", "Department", "Leave Type", "Start Date", "End Date", "Total Days", "Status", "Reason", "Approved By"])
            for r in rows:
                writer.writerow([
                    r.get("id"), r.get("employee_code"), r.get("full_name"),
                    r.get("department"), r.get("leave_name"), r.get("start_date"),
                    r.get("end_date"), r.get("total_days"), r.get("status"),
                    r.get("reason"), r.get("approved_by")
                ])
            mem = io.BytesIO(out_str.getvalue().encode("utf-8"))
            mem.seek(0)
            return mem, "text/csv", f"{filename}.csv"
