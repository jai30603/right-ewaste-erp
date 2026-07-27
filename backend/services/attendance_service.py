import csv
import io
import datetime
from repositories import attendance_repository
from repositories.activity_log_repository import log_activity
from erp_platform.events.event_bus import event_bus, ErpEvent
from services.attendance_validator import AttendanceValidator


class AttendanceService:

    @staticmethod
    def get_dashboard_stats(date_str=None):
        return attendance_repository.get_attendance_dashboard_stats(date_str)

    @staticmethod
    def get_daily_attendance(date_str, department=None, search=None):
        return attendance_repository.get_daily_attendance_list(date_str, department=department, search=search)

    @staticmethod
    def mark_bulk_attendance(date_str, attendance_records, user_name="System"):
        # Validate every employee & date first
        records_to_save = []
        for emp_id, data in attendance_records.items():
            if not str(emp_id).isdigit():
                continue
            records_to_save.append({
                "employee_id": int(emp_id),
                "attendance_date": date_str,
                "attendance_status": data.get("status", "Present"),
                "check_in_time": data.get("check_in_time") or None,
                "check_out_time": data.get("check_out_time") or None,
                "remarks": data.get("remarks") or None
            })

        is_valid, errors = AttendanceValidator.validate_bulk(records_to_save)
        if not is_valid:
            return False, errors

        attendance_repository.save_bulk_attendance(records_to_save, user_name=user_name)

        # Audit & Event Log
        log_activity(
            user_name=user_name,
            action="Bulk Attendance Completed",
            details=f"Marked attendance for {len(records_to_save)} employees for date {date_str}.",
            module="Attendance",
            reference_number=date_str
        )

        event_bus.publish(ErpEvent(
            event_type="Bulk Attendance Completed",
            source_module="Attendance",
            payload={"attendance_date": date_str, "total_records": len(records_to_save)},
            user_name=user_name
        ))

        return True, []

    @staticmethod
    def get_monthly_register(year, month, department=None, search=None):
        return attendance_repository.get_monthly_attendance_register(year, month, department=department, search=search)

    @staticmethod
    def get_employee_history(employee_id, year=None, month=None):
        return attendance_repository.get_employee_attendance_history(employee_id, year=year, month=month)

    @staticmethod
    def export_attendance_report(report_type, format_type, start_date=None, end_date=None, month=None, year=None, department=None, employee_id=None):
        rows = attendance_repository.get_attendance_report_data(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            month=month,
            year=year,
            department=department,
            employee_id=employee_id
        )

        filename = f"attendance_{report_type}_{datetime.date.today().isoformat()}"

        if format_type == "excel":
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Attendance Report"

                headers = ["Date", "Employee Code", "Full Name", "Department", "Designation", "Status", "Check In", "Check Out", "Remarks"]
                ws.append(headers)

                for r in rows:
                    ws.append([
                        r.get("attendance_date"),
                        r.get("employee_code"),
                        r.get("full_name"),
                        r.get("department"),
                        r.get("designation"),
                        r.get("attendance_status"),
                        r.get("check_in_time"),
                        r.get("check_out_time"),
                        r.get("remarks")
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
            writer.writerow(["Date", "Employee Code", "Full Name", "Department", "Designation", "Status", "Check In", "Check Out", "Remarks"])
            for r in rows:
                writer.writerow([
                    r.get("attendance_date"), r.get("employee_code"), r.get("full_name"),
                    r.get("department"), r.get("designation"), r.get("attendance_status"),
                    r.get("check_in_time"), r.get("check_out_time"), r.get("remarks")
                ])
            mem = io.BytesIO(out_str.getvalue().encode("utf-8"))
            mem.seek(0)
            return mem, "text/csv", f"{filename}.csv"

        if format_type == "pdf":
            try:
                from xhtml2pdf import pisa
                html_content = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10px; }}
                        h2 {{ text-align: center; color: #1e293b; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                        th, td {{ border: 1px solid #cbd5e1; padding: 5px; text-align: left; }}
                        th {{ background-color: #f1f5f9; }}
                    </style>
                </head>
                <body>
                    <h2>Right Ewaste ERP - Attendance Report</h2>
                    <p>Report Period: {start_date or 'N/A'} to {end_date or 'N/A'}</p>
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Code</th>
                                <th>Employee</th>
                                <th>Department</th>
                                <th>Status</th>
                                <th>Remarks</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>{r.get('attendance_date')}</td><td>{r.get('employee_code')}</td><td>{r.get('full_name')}</td><td>{r.get('department')}</td><td>{r.get('attendance_status')}</td><td>{r.get('remarks') or ''}</td></tr>" for r in rows])}
                        </tbody>
                    </table>
                </body>
                </html>
                """
                pdf_out = io.BytesIO()
                pisa_status = pisa.CreatePDF(html_content, dest=pdf_out)
                if not pisa_status.err:
                    pdf_out.seek(0)
                    return pdf_out, "application/pdf", f"{filename}.pdf"
            except Exception:
                pass

            # Fallback to CSV if PDF generation fails
            out_str = io.StringIO()
            writer = csv.writer(out_str)
            writer.writerow(["Date", "Employee Code", "Full Name", "Department", "Designation", "Status", "Check In", "Check Out", "Remarks"])
            for r in rows:
                writer.writerow([
                    r.get("attendance_date"), r.get("employee_code"), r.get("full_name"),
                    r.get("department"), r.get("designation"), r.get("attendance_status"),
                    r.get("check_in_time"), r.get("check_out_time"), r.get("remarks")
                ])
            mem = io.BytesIO(out_str.getvalue().encode("utf-8"))
            mem.seek(0)
            return mem, "text/csv", f"{filename}.csv"
