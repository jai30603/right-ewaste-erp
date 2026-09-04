import csv
import io
import datetime
from repositories import employee_report_repository, attendance_repository, leave_repository, payroll_repository


class EmployeeReportService:

    @staticmethod
    def export_employee_directory(format_type, department=None, status=None, search=None):
        rows = employee_report_repository.get_employee_directory_report(department=department, status=status, search=search)
        filename = f"employee_directory_{datetime.date.today().isoformat()}"

        if format_type == "excel":
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Employee Directory"
                headers = ["Code", "Full Name", "Department", "Designation", "Mobile", "Email", "Joining Date", "Status"]
                ws.append(headers)
                for r in rows:
                    ws.append([
                        r.get("employee_code"), r.get("full_name"), r.get("department"),
                        r.get("designation"), r.get("mobile_number"), r.get("email"),
                        r.get("joining_date"), r.get("status")
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
            writer.writerow(["Code", "Full Name", "Department", "Designation", "Mobile", "Email", "Joining Date", "Status"])
            for r in rows:
                writer.writerow([
                    r.get("employee_code"), r.get("full_name"), r.get("department"),
                    r.get("designation"), r.get("mobile_number"), r.get("email"),
                    r.get("date_of_joining"), r.get("status")
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
                    <h2>Right Ewaste ERP - Employee Directory</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Code</th>
                                <th>Name</th>
                                <th>Department</th>
                                <th>Designation</th>
                                <th>Mobile</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>{r.get('employee_code')}</td><td>{r.get('full_name')}</td><td>{r.get('department') or ''}</td><td>{r.get('designation') or ''}</td><td>{r.get('mobile_number')}</td><td>{r.get('status')}</td></tr>" for r in rows])}
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
                print("Error in employee PDF generation:", e)

            out_str = io.StringIO()
            writer = csv.writer(out_str)
            writer.writerow(["Code", "Full Name", "Department", "Designation", "Mobile", "Email", "Joining Date", "Status"])
            for r in rows:
                writer.writerow([
                    r.get("employee_code"), r.get("full_name"), r.get("department"),
                    r.get("designation"), r.get("mobile_number"), r.get("email"),
                    r.get("date_of_joining"), r.get("status")
                ])
            mem = io.BytesIO(out_str.getvalue().encode("utf-8"))
            mem.seek(0)
            return mem, "text/csv", f"{filename}.csv"
