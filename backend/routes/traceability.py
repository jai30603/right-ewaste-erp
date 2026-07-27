import logging
from flask import Blueprint, render_template, request, jsonify
from services.traceability_service import build_batch_genealogy, search_traceability
from services.reconciliation_service import get_system_reconciliation_summary, reconcile_processing_job
from document_engine.production_report_engine import ProductionReportEngine as ProductionReportingEngine
from repositories import batch_repository
from repositories.activity_log_repository import log_activity

logger = logging.getLogger(__name__)
traceability_bp = Blueprint("traceability", __name__)


@traceability_bp.route("/inventory/batches")
def batch_list():
    query = request.args.get("q", "")
    status = request.args.get("status", "all")
    material_id = request.args.get("material_id")
    batches = batch_repository.get_all_batches(query=query, status=status, material_id=material_id)
    return render_template("inventory/batch_list.html", batches=batches, query=query, status=status)


@traceability_bp.route("/inventory/batch/<batch_number>")
def batch_details(batch_number):
    genealogy = build_batch_genealogy(batch_number)
    if not genealogy:
        return render_template("shared/404.html", message=f"Batch {batch_number} not found."), 404
    return render_template("inventory/batch_details.html", genealogy=genealogy, batch_number=batch_number)


@traceability_bp.route("/inventory/timeline")
def material_timeline():
    query = request.args.get("q", "")
    search_results = None
    if query:
        search_results = search_traceability(query)
    return render_template("inventory/material_timeline.html", query=query, search_results=search_results)


@traceability_bp.route("/inventory/material-flow-dashboard")
def material_flow_dashboard():
    import datetime
    report_date = request.args.get("date", datetime.date.today().isoformat())
    daily_summary = ProductionReportingEngine.generate_daily_production_summary(report_date)
    reconciliation = get_system_reconciliation_summary()
    return render_template(
        "inventory/material_flow_dashboard.html",
        daily_summary=daily_summary,
        reconciliation=reconciliation,
        report_date=report_date
    )


# ── API Endpoints (AI Readiness) ──────────────────────────────────────────────

@traceability_bp.route("/platform/api/traceability/search")
def api_traceability_search():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    results = search_traceability(query)
    return jsonify(results)


@traceability_bp.route("/platform/api/traceability/batch/<batch_number>")
def api_batch_genealogy(batch_number):
    genealogy = build_batch_genealogy(batch_number)
    if not genealogy:
        return jsonify({"error": f"Batch {batch_number} not found"}), 404
    return jsonify(genealogy)


@traceability_bp.route("/platform/api/reconciliation/summary")
def api_reconciliation_summary():
    summary = get_system_reconciliation_summary()
    return jsonify(summary)


@traceability_bp.route("/platform/api/reconciliation/job/<int:job_id>")
def api_job_reconciliation(job_id):
    result = reconcile_processing_job(job_id)
    return jsonify(result)


@traceability_bp.route("/platform/api/production-report")
def api_production_report():
    import datetime
    report_date = request.args.get("date", datetime.date.today().isoformat())
    summary = ProductionReportingEngine.generate_daily_production_summary(report_date)
    return jsonify(summary)
