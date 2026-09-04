import csv
import io
import datetime
from repositories import payroll_repository, employee_repository
from repositories.activity_log_repository import log_activity
from erp_platform.events.event_bus import event_bus, ErpEvent
from services.payroll_validator import PayrollValidator


class PayrollService:

    @staticmethod
    def get_dashboard_stats(month=None, year=None):
        return payroll_repository.get_payroll_dashboard_stats(month=month, year=year)

    @staticmethod
    def get_salary_structure(employee_id, active_only=True):
        return payroll_repository.get_salary_structure(employee_id, active_only=active_only)

    @staticmethod
    def get_salary_structure_history(employee_id):
        return payroll_repository.get_salary_structure_history(employee_id)

    @staticmethod
    def save_salary_structure(form_data, user_name="System"):
        is_valid, errors = PayrollValidator.validate_salary_structure(form_data)
        if not is_valid:
            return None, errors

        emp_id = int(form_data["employee_id"])
        existing = payroll_repository.get_salary_structure(emp_id, active_only=True)
        is_update = existing is not None

        struct_id = payroll_repository.save_salary_structure(form_data)
        emp = employee_repository.get_employee_by_id(emp_id)
        emp_name = emp.get("full_name") if emp else f"ID #{emp_id}"

        event_name = "Salary Structure Updated" if is_update else "Salary Structure Created"
        log_activity(
            user_name=user_name,
            action=event_name,
            details=f"{event_name} for {emp_name} (Gross: {form_data.get('basic_salary', 0)}).",
            module="Payroll",
            reference_number=f"SAL-{struct_id}"
        )

        event_bus.publish(ErpEvent(
            event_type=event_name,
            source_module="Payroll",
            payload={"structure_id": struct_id, "employee_id": emp_id},
            user_name=user_name
        ))

        return struct_id, []

    @staticmethod
    def generate_monthly_payroll(month, year, user_name="System"):
        is_valid, errors = PayrollValidator.validate_payroll_generation(month, year)
        if not is_valid:
            return 0, 0, errors

        month = int(month)
        year = int(year)

        generated_count, skipped_count, gen_errors = payroll_repository.generate_monthly_payroll(month, year, user_name=user_name)
        if gen_errors:
            errors.extend(gen_errors)

        if generated_count > 0:
            month_name = datetime.date(year, month, 1).strftime("%B %Y")
            log_activity(
                user_name=user_name,
                action="Payroll Generated",
                details=f"Generated payroll for {generated_count} employees for {month_name}.",
                module="Payroll",
                reference_number=f"PR-{year}-{month:02d}"
            )

            event_bus.publish(ErpEvent(
                event_type="Payroll Generated",
                source_module="Payroll",
                payload={"month": month, "year": year, "count": generated_count},
                user_name=user_name
            ))

        return generated_count, skipped_count, errors

    @staticmethod
    def get_payroll_records(month=None, year=None, department=None, status=None, search=None, page=1, per_page=10):
        return payroll_repository.get_payroll_records(
            month=month, year=year, department=department, status=status, search=search, page=page, per_page=per_page
        )

    @staticmethod
    def get_payroll_by_id(payroll_id):
        return payroll_repository.get_payroll_by_id(payroll_id)

    @staticmethod
    def update_payroll_status(payroll_id, status, user_name="System"):
        success, err = payroll_repository.update_payroll_status(payroll_id, status, user_name=user_name)
        if not success:
            return False, err

        rec = payroll_repository.get_payroll_by_id(payroll_id)
        emp_name = rec["full_name"] if rec else f"ID #{payroll_id}"

        log_activity(
            user_name=user_name,
            action=f"Payroll {status}",
            details=f"Updated payroll #{payroll_id} status for {emp_name} to '{status}'.",
            module="Payroll",
            reference_number=f"PR-{payroll_id}"
        )

        event_bus.publish(ErpEvent(
            event_type=f"Payroll {status}",
            source_module="Payroll",
            payload={"payroll_id": payroll_id, "status": status},
            user_name=user_name
        ))

        return True, f"Payroll status updated to {status}."

    @staticmethod
    def render_payslip_pdf(payroll_id):
        rec = payroll_repository.get_payroll_by_id(payroll_id)
        if not rec:
            return None, "Payroll record not found."

        try:
            from backend.services.pdf_service import compile_html_to_pdf
            month_name = datetime.date(rec["payroll_year"], rec["payroll_month"], 1).strftime("%B %Y")

            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; color: #1e293b; padding: 20px; }}
                    .header {{ text-align: center; border-bottom: 2px solid #2563eb; padding-bottom: 10px; margin-bottom: 20px; }}
                    .title {{ font-size: 18px; font-weight: bold; color: #1e3a8a; }}
                    .subtitle {{ font-size: 12px; color: #64748b; margin-top: 5px; }}
                    .meta-table, .payslip-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                    .meta-table td {{ padding: 4px; vertical-align: top; }}
                    .payslip-table th, .payslip-table td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
                    .payslip-table th {{ background-color: #f8fafc; font-weight: bold; }}
                    .section-title {{ font-size: 12px; font-weight: bold; color: #1e3a8a; margin-top: 15px; margin-bottom: 8px; }}
                    .box {{ border: 1px solid #e2e8f0; padding: 12px; border-radius: 4px; margin-bottom: 15px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <div class="title">RIGHT EWASTE RECYCLING PVT LTD</div>
                    <div class="subtitle">Salary Payslip for {month_name}</div>
                </div>

                <div class="section-title">Employee Details</div>
                <table class="meta-table">
                    <tr>
                        <td><strong>Employee Name:</strong> {rec.get('full_name')}</td>
                        <td><strong>Employee Code:</strong> {rec.get('employee_code')}</td>
                    </tr>
                    <tr>
                        <td><strong>Department:</strong> {rec.get('department') or '—'}</td>
                        <td><strong>Designation:</strong> {rec.get('designation') or '—'}</td>
                    </tr>
                    <tr>
                        <td><strong>Pay Period:</strong> {month_name}</td>
                        <td><strong>Paid Days:</strong> {rec.get('paid_days', 30)}</td>
                    </tr>
                </table>

                <div class="section-title">Salary Breakup</div>
                <table class="payslip-table">
                    <thead>
                        <tr>
                            <th>Earnings</th>
                            <th>Amount (₹)</th>
                            <th>Deductions</th>
                            <th>Amount (₹)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Basic Salary</td>
                            <td>{rec.get('basic_salary', 0):,.2f}</td>
                            <td>Provident Fund (PF)</td>
                            <td>{rec.get('provident_fund', 0):,.2f}</td>
                        </tr>
                        <tr>
                            <td>HRA</td>
                            <td>{rec.get('hra', 0):,.2f}</td>
                            <td>Professional Tax (PT)</td>
                            <td>{rec.get('professional_tax', 0):,.2f}</td>
                        </tr>
                        <tr>
                            <td>Special Allowance</td>
                            <td>{rec.get('special_allowance', 0):,.2f}</td>
                            <td>TDS / Income Tax</td>
                            <td>{rec.get('income_tax', 0):,.2f}</td>
                        </tr>
                        <tr>
                            <td>Overtime Pay</td>
                            <td>{rec.get('overtime_pay', 0):,.2f}</td>
                            <td>Other Deductions</td>
                            <td>{rec.get('other_deductions', 0):,.2f}</td>
                        </tr>
                        <tr style="font-weight: bold; background-color: #f8fafc;">
                            <td>Total Earnings</td>
                            <td>{rec.get('gross_salary', 0):,.2f}</td>
                            <td>Total Deductions</td>
                            <td>{rec.get('total_deductions', 0):,.2f}</td>
                        </tr>
                    </tbody>
                </table>

                <div class="box" style="background-color: #ecfdf5; border-color: #a7f3d0; text-align: center;">
                    <div style="font-size: 14px; font-weight: bold; color: #065f46;">
                        NET PAYABLE SALARY: ₹{rec.get('net_salary', 0):,.2f}
                    </div>
                </div>

                <div style="text-align: center; margin-top: 30px; font-size: 9px; color: #94a3b8;">
                    This is a computer-generated payslip from Right Ewaste ERP v4.0. No signature required.
                </div>
            </body>
            </html>
            """
            pdf_bytes = compile_html_to_pdf(html_content)
            pdf_out = io.BytesIO(pdf_bytes)
            pdf_out.seek(0)
            return pdf_out, None
        except Exception as e:
            print("Error generating payslip PDF:", e)
            pass

        return None, "Failed to render PDF."

    @staticmethod
    def prepare_accounting_voucher_payload(payroll_id):
        rec = payroll_repository.get_payroll_by_id(payroll_id)
        if not rec:
            return None

        m_name = datetime.date(rec["payroll_year"], rec["payroll_month"], 1).strftime("%B %Y")
        return {
            "voucher_type": "Payroll Journal",
            "voucher_date": datetime.date.today().isoformat(),
            "reference": f"PAYROLL-{rec['payroll_year']}-{rec['payroll_month']:02d}-{rec['employee_code']}",
            "narration": f"Salary disbursement for {rec['full_name']} for {m_name}",
            "debits": [
                {"account": "Salaries & Wages Expense", "amount": rec["gross_salary"]}
            ],
            "credits": [
                {"account": "Provident Fund Payable", "amount": rec.get("provident_fund", 0)},
                {"account": "TDS / Income Tax Payable", "amount": rec.get("income_tax", 0)},
                {"account": "Professional Tax Payable", "amount": rec.get("professional_tax", 0)},
                {"account": "Salary Payable / Bank Account", "amount": rec["net_salary"]}
            ]
        }

    @staticmethod
    def export_payroll_report(report_type, format_type, month=None, year=None, department=None, employee_id=None):
        rows = payroll_repository.get_payroll_report_data(
            report_type=report_type, month=month, year=year, department=department, employee_id=employee_id
        )

        filename = f"payroll_report_{report_type}_{datetime.date.today().isoformat()}"

        if format_type == "excel":
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Payroll Report"

                headers = ["ID", "Emp Code", "Full Name", "Department", "Designation", "Month/Year", "Working Days", "Present", "Leave", "Absent", "Gross Salary", "Total Deductions", "Net Salary", "Status"]
                ws.append(headers)

                for r in rows:
                    ws.append([
                        r.get("id"), r.get("employee_code"), r.get("full_name"),
                        r.get("department"), r.get("designation"), f"{r.get('payroll_month')}/{r.get('payroll_year')}",
                        r.get("working_days"), r.get("present_days"), r.get("leave_days"), r.get("absent_days"),
                        r.get("gross_salary"), r.get("total_deductions"), r.get("net_salary"), r.get("payroll_status")
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
            writer.writerow(["ID", "Emp Code", "Full Name", "Department", "Designation", "Month/Year", "Working Days", "Present", "Leave", "Absent", "Gross Salary", "Total Deductions", "Net Salary", "Status"])
            for r in rows:
                writer.writerow([
                    r.get("id"), r.get("employee_code"), r.get("full_name"),
                    r.get("department"), r.get("designation"), f"{r.get('payroll_month')}/{r.get('payroll_year')}",
                    r.get("working_days"), r.get("present_days"), r.get("leave_days"), r.get("absent_days"),
                    r.get("gross_salary"), r.get("total_deductions"), r.get("net_salary"), r.get("payroll_status")
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
                    <h2>Right Ewaste ERP - Monthly Payroll Register</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Emp Code</th>
                                <th>Name</th>
                                <th>Dept</th>
                                <th>Gross (₹)</th>
                                <th>Deductions (₹)</th>
                                <th>Net (₹)</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>{r.get('employee_code')}</td><td>{r.get('full_name')}</td><td>{r.get('department') or ''}</td><td>₹{r.get('gross_salary'):,.2f}</td><td>₹{r.get('total_deductions'):,.2f}</td><td>₹{r.get('net_salary'):,.2f}</td><td>{r.get('payroll_status')}</td></tr>" for r in rows])}
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
                print("Error in payroll register PDF generation:", e)

            out_str = io.StringIO()
            writer = csv.writer(out_str)
            writer.writerow(["ID", "Emp Code", "Full Name", "Department", "Designation", "Month/Year", "Working Days", "Present", "Leave", "Absent", "Gross Salary", "Total Deductions", "Net Salary", "Status"])
            for r in rows:
                writer.writerow([
                    r.get("id"), r.get("employee_code"), r.get("full_name"),
                    r.get("department"), r.get("designation"), f"{r.get('payroll_month')}/{r.get('payroll_year')}",
                    r.get("working_days"), r.get("present_days"), r.get("leave_days"), r.get("absent_days"),
                    r.get("gross_salary"), r.get("total_deductions"), r.get("net_salary"), r.get("payroll_status")
                ])
            mem = io.BytesIO(out_str.getvalue().encode("utf-8"))
            mem.seek(0)
            return mem, "text/csv", f"{filename}.csv"
