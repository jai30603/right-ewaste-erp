import json
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, abort, flash
from repositories import processing_repository, material_repository, inventory_repository
from services import processing_service
from common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info
from database import get_connection

material_processing_bp = Blueprint("material_processing", __name__)

@material_processing_bp.route("/processing/dashboard")
def dashboard():
    summary = processing_repository.get_dashboard_summary()
    return render_template(
        "processing/dashboard.html",
        summary=summary,
        charts_json=json.dumps(summary["charts"])
    )

@material_processing_bp.route("/processing/jobs")
def jobs():
    search_query = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip()
    priority = request.args.get("priority", "all").strip()
    
    filters = {"status": status, "priority": priority}
    
    # Active/Draft/Ready/In Progress jobs are typically default list
    # If no filters, show only active ones (DRAFT, READY, IN_PROGRESS)
    if status == "all":
        filters["status"] = "active"
        
    all_jobs = processing_repository.search_processing_jobs(search_query, filters)
    queue = processing_repository.get_processing_queue()
    
    return render_template(
        "processing/processing_jobs.html",
        jobs=all_jobs,
        queue=queue,
        q=search_query,
        status=status,
        priority=priority
    )

@material_processing_bp.route("/processing/jobs/new", methods=["GET", "POST"])
def create_job():
    user = session.get("user", {})
    if request.method == "POST":
        try:
            operator_id = request.form.get("operator_id", user.get("username", "System Operator")).strip()
            priority = request.form.get("priority", "NORMAL").strip()
            processing_date = request.form.get("processing_date", "").strip()
            remarks = request.form.get("remarks", "").strip()
            
            # Read inputs JSON from request
            inputs_raw = request.form.get("inputs_json", "[]")
            inputs = json.loads(inputs_raw)
            if not inputs:
                raise ValueError("At least one input material must be selected.")
                
            job_data = {
                "processing_number": "",
                "processing_date": processing_date,
                "priority": priority,
                "operator_id": operator_id,
                "remarks": remarks,
            }
            
            job_id = processing_service.create_job(job_data, inputs, user.get("username", "System"))
            flash_success("Draft processing job created successfully.")
            return redirect(url_for("material_processing.job_details", job_id=job_id))
        except Exception as exc:
            flash_error(str(exc))
            
    queue = processing_repository.get_processing_queue()
    return render_template(
        "processing/processing_create.html",
        queue=queue,
        default_date=datetime.now().strftime("%Y-%m-%d")
    )

@material_processing_bp.route("/processing/jobs/<int:job_id>")
def job_details(job_id):
    job = processing_repository.get_processing_job(job_id)
    if not job:
        abort(404)
        
    # Get associated stock movements for this job
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT sm.*, m.material_name, m.material_code, m.uom
               FROM stock_movement sm
               JOIN material m ON sm.material_id = m.id
               WHERE sm.reference_type = 'PROCESSING_JOB' AND sm.reference_id = ?
               ORDER BY sm.id ASC""",
            (job_id,)
        )
        movements = [dict(row) for row in cursor.fetchall()]
        
        # Query recent purchases for each input material to show genealogy
        for item in job["inputs"]:
            cursor.execute(
                """SELECT pi.purchase_invoice_number, pi.invoice_date, pii.quantity, pii.rate, p.company_name AS supplier_name
                   FROM purchase_invoice_item pii
                   JOIN purchase_invoice pi ON pii.purchase_invoice_id = pi.id
                   JOIN party p ON pi.supplier_id = p.id
                   WHERE pii.material_id = ? AND pi.is_active = 1
                   ORDER BY pi.invoice_date DESC, pi.id DESC
                   LIMIT 3""",
                (item["material_id"],)
            )
            item["purchases"] = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
        
    return render_template(
        "processing/processing_details.html",
        job=job,
        movements=movements,
        can_complete_job=(
            not current_app.config["ERP_AUTH_REQUIRED"]
            or session.get("user", {}).get("role") in ("admin", "operator")
        ),
    )

@material_processing_bp.route("/processing/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    job = processing_repository.get_processing_job(job_id)
    if not job:
        abort(404)
    if job["status"] not in ("DRAFT", "READY"):
        flash_error("Only Draft or Ready jobs can be edited.")
        return redirect(url_for("material_processing.job_details", job_id=job_id))
        
    user = session.get("user", {})
    if request.method == "POST":
        try:
            status = request.form.get("status", "DRAFT").strip()
            operator_id = request.form.get("operator_id", job["operator_id"]).strip()
            priority = request.form.get("priority", job["priority"]).strip()
            processing_date = request.form.get("processing_date", job["processing_date"]).strip()
            remarks = request.form.get("remarks", "").strip()
            
            inputs = json.loads(request.form.get("inputs_json", "[]"))
            outputs = json.loads(request.form.get("outputs_json", "[]"))
            losses = json.loads(request.form.get("losses_json", "[]"))
            
            job_data = {
                "processing_date": processing_date,
                "status": status,
                "priority": priority,
                "operator_id": operator_id,
                "remarks": remarks,
            }
            
            processing_service.save_draft(job_id, job_data, inputs, outputs, losses, user.get("username", "System"))
            flash_success("Processing job draft saved successfully.")
            return redirect(url_for("material_processing.job_details", job_id=job_id))
        except Exception as exc:
            flash_error(str(exc))
            
    queue = processing_repository.get_processing_queue()
    all_materials = material_repository.get_all_materials()
    return render_template(
        "processing/processing_create.html",
        job=job,
        queue=queue,
        materials=all_materials
    )

@material_processing_bp.route("/processing/jobs/<int:job_id>/start", methods=["POST"])
def start_job(job_id):
    user = session.get("user", {})
    try:
        processing_service.start_job(job_id, user.get("username", "System"))
        flash_success("Processing job started successfully and inventory is reserved.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("material_processing.job_details", job_id=job_id))

@material_processing_bp.route("/processing/jobs/<int:job_id>/complete", methods=["POST"])
def complete_job(job_id):
    user = session.get("user", {})
    # Local UAT may run with authentication disabled. In authenticated
    # deployments, only admin and operator roles may complete a job.
    if (
        current_app.config["ERP_AUTH_REQUIRED"]
        and user.get("role") not in ("admin", "operator")
    ):
        abort(403)
        
    try:
        outputs = json.loads(request.form.get("outputs_json", "[]"))
        losses = json.loads(request.form.get("losses_json", "[]"))
        
        processing_service.complete_job(job_id, outputs, losses, user.get("username", "System"))
        flash_success("Processing job completed successfully. Inventory is updated.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("material_processing.job_details", job_id=job_id))

@material_processing_bp.route("/processing/jobs/<int:job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    user = session.get("user", {})
    if (
        current_app.config["ERP_AUTH_REQUIRED"]
        and user.get("role") not in ("admin", "operator")
    ):
        abort(403)
        
    try:
        processing_service.cancel_job(job_id, user.get("username", "System"))
        flash_success("Processing job cancelled and reservation released.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("material_processing.job_details", job_id=job_id))

@material_processing_bp.route("/processing/jobs/<int:job_id>/reopen", methods=["POST"])
def reopen_job(job_id):
    user = session.get("user", {})
    try:
        processing_service.reopen_job(job_id, user.get("username", "System"), user.get("role", ""))
        flash_success("Processing job reopened successfully and inventory reversed.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("material_processing.job_details", job_id=job_id))

@material_processing_bp.route("/processing/jobs/<int:job_id>/duplicate", methods=["POST"])
def duplicate_job(job_id):
    user = session.get("user", {})
    try:
        new_job_id = processing_service.duplicate_job(job_id, user.get("username", "System"))
        flash_success("Job duplicated successfully as a new draft.")
        return redirect(url_for("material_processing.job_details", job_id=new_job_id))
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("material_processing.job_details", job_id=job_id))

@material_processing_bp.route("/processing/history")
def history():
    search_query = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip()
    priority = request.args.get("priority", "all").strip()
    operator = request.args.get("operator", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    filters = {
        "status": status,
        "priority": priority,
        "operator": operator,
        "start_date": start_date,
        "end_date": end_date,
    }
    
    jobs = processing_repository.search_processing_jobs(search_query, filters)
    operators = processing_repository.get_operators()
    
    return render_template(
        "processing/processing_history.html",
        jobs=jobs,
        operators=operators,
        q=search_query,
        status=status,
        priority=priority,
        operator=operator,
        start_date=start_date,
        end_date=end_date
    )
