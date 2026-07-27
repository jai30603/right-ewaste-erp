import os
import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, flash
from services.factory_report_service import FactoryReportService
from services.factory_report_validator import FactoryReportValidationService
from repositories.activity_log_repository import log_activity
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning

factory_report_bp = Blueprint("factory_report", __name__)


def _get_current_user_name():
    if "user" in session and isinstance(session["user"], dict):
        return session["user"].get("username") or session["user"].get("full_name") or "System User"
    return "System User"


@factory_report_bp.route("/factory-reports")
def index():
    today_str = datetime.date.today().isoformat()
    history = FactoryReportService.get_report_history(limit=50)
    is_valid, errors, warnings = FactoryReportValidationService.validate_generation_prerequisites(today_str)

    return render_template(
        "reports/factory_reports.html",
        today_str=today_str,
        history=history,
        is_system_ready=is_valid,
        system_errors=errors,
        system_warnings=warnings
    )


@factory_report_bp.route("/factory-reports/generate", methods=["POST"])
def generate():
    report_date = request.form.get("report_date", "").strip()
    user_name = _get_current_user_name()

    report_id, errors, warnings = FactoryReportService.generate_factory_report(report_date, user_name=user_name)

    if errors:
        for err in errors:
            flash_error(err)
    else:
        for warn in warnings:
            flash_warning(warn)
        flash_success(f"Factory Report generated successfully for date '{report_date}'!")

    return redirect(url_for("factory_report.index"))


@factory_report_bp.route("/factory-reports/<int:report_id>/download")
def download(report_id):
    report = FactoryReportService.get_report_by_id(report_id)
    if not report:
        flash_error("Factory report record not found.")
        return redirect(url_for("factory_report.index"))

    user_name = _get_current_user_name()
    rel_path = report["file_path"].lstrip("/").replace("/", os.sep)
    full_path = Path(__file__).resolve().parent.parent / rel_path

    if not full_path.exists():
        flash_error("Report workbook file is missing from storage.")
        return redirect(url_for("factory_report.index"))

    log_activity(
        user_name=user_name,
        action="Factory Report Downloaded",
        details=f"Downloaded Factory Report workbook for date '{report['report_date']}'.",
        module="FactoryReport",
        reference_number=f"FR-{report_id}"
    )

    return send_file(
        full_path,
        as_attachment=True,
        download_name=report["file_name"],
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@factory_report_bp.route("/factory-reports/<int:report_id>/regenerate", methods=["POST"])
def regenerate(report_id):
    user_name = _get_current_user_name()
    new_report_id, errors, warnings = FactoryReportService.regenerate_report(report_id, user_name=user_name)

    if errors:
        for err in errors:
            flash_error(err)
    else:
        flash_success("Factory Report regenerated successfully!")

    return redirect(url_for("factory_report.index"))
