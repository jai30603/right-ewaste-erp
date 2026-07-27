import os
import json
import openpyxl
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from repositories import certificate_repository, party_repository
from services import certificate_service
from common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info
from database import get_connection

certificates_bp = Blueprint("certificates", __name__)

UPLOAD_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "static", "certificates", "attachments"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def parse_excel_sheet(file_path):
    try:
        wb = openpyxl.load_workbook(file_path, read_only=True)
        sheet = wb.active
        rows = []
        for r in sheet.iter_rows(values_only=True):
            if any(r):
                rows.append([str(x) if x is not None else "" for x in r])
        return rows
    except Exception:
        return []

@certificates_bp.route("/certificates/dashboard")
def dashboard():
    summary = certificate_repository.get_dashboard_summary()
    queue = certificate_repository.get_eligible_processing_jobs()
    return render_template(
        "certificate/dashboard.html",
        summary=summary,
        queue=queue
    )

@certificates_bp.route("/certificates/register")
def register():
    search_query = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip()
    c_type = request.args.get("type", "all").strip()
    
    filters = {"status": status, "type": c_type}
    certs = certificate_repository.search_certificates(search_query, filters)
    
    return render_template(
        "certificate/certificate_register.html",
        certs=certs,
        q=search_query,
        status=status,
        c_type=c_type
    )

@certificates_bp.route("/certificates/new", methods=["GET", "POST"])
def create_certificate():
    user = session.get("user", {})
    if request.method == "POST":
        try:
            customer_id = int(request.form.get("customer_id"))
            cert_type = request.form.get("certificate_type").strip()
            template_key = request.form.get("template_key").strip()
            remarks = request.form.get("remarks", "").strip()
            
            # Ingest purchase_id directly or fallback to purchase_ids list
            purchase_id = request.form.get("purchase_id")
            purchase_ids = [int(purchase_id)] if purchase_id else []
            
            # Ingest visual template design and custom table JSON
            template_json = request.form.get("template_json")
            custom_table_json = request.form.get("custom_table_json")
            
            job_ids = [int(x) for x in request.form.getlist("processing_job_ids")]
            if not purchase_ids and request.form.getlist("purchase_ids"):
                purchase_ids = [int(x) for x in request.form.getlist("purchase_ids")]
            
            # Create Draft
            cert_id = certificate_service.create_draft_certificate(
                customer_id=customer_id,
                cert_type=cert_type,
                template_key=template_key,
                job_ids=job_ids,
                purchase_ids=purchase_ids,
                remarks=remarks,
                performed_by=user.get("username", "System"),
                template_json=template_json,
                custom_table_json=custom_table_json
            )
            
            # Check for file uploads
            file = request.files.get("asset_list")
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, f"{cert_id}_{filename}")
                file.save(file_path)
                
                a_data = {
                    "certificate_id": cert_id,
                    "file_name": filename,
                    "file_path": f"/static/certificates/attachments/{cert_id}_{filename}",
                    "file_type": filename.split(".")[-1].upper(),
                    "uploaded_by": user.get("username", "System")
                }
                certificate_repository.save_asset_attachment(a_data)
                
            flash_success("Certificate created successfully.")
            return redirect(url_for("certificates.job_details", cert_id=cert_id))
        except Exception as exc:
            flash_error(str(exc))
            
    # GET: populate form data
    pre_job_id = request.args.get("pre_job_id")
    selected_job_ids = [int(pre_job_id)] if pre_job_id else []
    
    queue = certificate_repository.get_eligible_processing_jobs()
    templates = certificate_repository.get_certificate_templates()
    parties = party_repository.get_all_parties() # retrieves all customers
    
    return render_template(
        "certificate/certificate_create.html",
        queue=queue,
        templates=templates,
        parties=parties,
        selected_job_ids=selected_job_ids
    )

@certificates_bp.route("/certificates/<int:cert_id>")
def job_details(cert_id):
    cert = certificate_repository.get_certificate(cert_id)
    if not cert:
        abort(404)
        
    # Read asset spreadsheet records if attached
    asset_rows = []
    if cert["attachments"]:
        path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", cert["attachments"][0]["file_path"].lstrip("/")))
        if os.path.exists(path):
            asset_rows = parse_excel_sheet(path)
            
    return render_template(
        "certificate/certificate_details.html",
        cert=cert,
        asset_rows=asset_rows
    )

@certificates_bp.route("/certificates/<int:cert_id>/generate", methods=["POST"])
def generate_and_lock(cert_id):
    user = session.get("user", {})
    try:
        certificate_service.generate_and_lock_certificate(cert_id, user.get("username", "System"))
        flash_success("Certificate generated and locked successfully.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("certificates.job_details", cert_id=cert_id))

@certificates_bp.route("/certificates/<int:cert_id>/cancel", methods=["POST"])
def cancel(cert_id):
    user = session.get("user", {})
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash_error("Cancellation reason is required.")
        return redirect(url_for("certificates.job_details", cert_id=cert_id))
        
    try:
        certificate_service.cancel_certificate(cert_id, reason, user.get("username", "System"))
        flash_success("Certificate cancelled successfully.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("certificates.job_details", cert_id=cert_id))

@certificates_bp.route("/certificates/<int:cert_id>/supersede", methods=["GET", "POST"])
def supersede(cert_id):
    cert = certificate_repository.get_certificate(cert_id)
    if not cert:
        abort(404)
    if cert["status"] not in ("GENERATED", "LOCKED"):
        flash_error("Only generated/locked certificates can be superseded.")
        return redirect(url_for("certificates.job_details", cert_id=cert_id))
        
    user = session.get("user", {})
    if request.method == "POST":
        try:
            template_key = request.form.get("template_key").strip()
            remarks = request.form.get("remarks", "").strip()
            
            new_id = certificate_service.supersede_certificate(cert_id, template_key, remarks, user.get("username", "System"))
            flash_success("Replacement certificate generated successfully.")
            return redirect(url_for("certificates.job_details", cert_id=new_id))
        except Exception as exc:
            flash_error(str(exc))
            
    templates = certificate_repository.get_certificate_templates()
    return render_template(
        "certificate/certificate_supersede.html",
        cert=cert,
        templates=templates
    )

@certificates_bp.route("/certificates/<int:cert_id>/pdf")
@certificates_bp.route("/certificates/download/<int:cert_id>")
def download_pdf(cert_id):
    cert = certificate_repository.get_certificate(cert_id)
    if not cert:
        abort(404)
        
    user = session.get("user", {})
    username = user.get("username", "System")
    role = user.get("role", "user")
    
    try:
        # Load complete document rendering context
        from repositories import company_repository
        company_row = company_repository.get_company()
        company = dict(company_row) if company_row else {}
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM party WHERE id = ?", (cert["customer_id"],))
        party_row = cursor.fetchone()
        party = dict(party_row) if party_row else {}
        
        purchase = {}
        if cert.get("purchase_id"):
            cursor.execute("SELECT * FROM purchase_invoice WHERE id = ?", (cert["purchase_id"],))
            pur_row = cursor.fetchone()
            purchase = dict(pur_row) if pur_row else {}
            
        render_context = {
            "company": company,
            "party": party,
            "purchase": purchase,
            "document": cert,
            "template": cert["template"],
            "materials": cert["materials"],
            "custom_table_json": cert.get("custom_table_json"),
            "document_number": cert["certificate_number"],
            "status": cert["status"],
            "generation_date": cert["generation_date"] or datetime.now().strftime("%Y-%m-%d")
        }
        
        # Render PDF bytes on the fly (checking transient render cache)
        from document_engine import render_document, audit_document_download
        pdf_bytes = render_document(render_context, user_role=role, performed_by=username)
        
        # Audit download
        audit_document_download(cert["certificate_number"], username)
        
        from io import BytesIO
        filename = f"{cert['certificate_number']}_CERTIFICATE.pdf"
        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=filename)
    except Exception as exc:
        flash_error("Could not render PDF: " + str(exc))
        return redirect(url_for("certificates.job_details", cert_id=cert_id))

@certificates_bp.route("/certificates/templates", methods=["GET", "POST"])
def templates():
    user = session.get("user", {})
    username = user.get("username", "System")
    role = user.get("role", "user")
    
    if request.method == "POST":
        # Check permissions using validation layer
        from document_engine.validators.document_validator import check_permission
        if not check_permission(role, "edit"):
            abort(403)
            
        try:
            template_key = request.form.get("template_key").strip()
            template_name = request.form.get("template_name").strip()
            title = request.form.get("title").strip()
            declaration_text = request.form.get("declaration_text").strip()
            template_json = request.form.get("template_json")
            
            t_data = {
                "template_key": template_key,
                "template_name": template_name,
                "title": title,
                "declaration_text": declaration_text,
                "show_logo": int(request.form.get("show_logo", 1)),
                "show_customer_details": int(request.form.get("show_customer_details", 1)),
                "show_purchase_references": int(request.form.get("show_purchase_references", 1)),
                "show_processing_summary": int(request.form.get("show_processing_summary", 1)),
                "show_weight_summary": int(request.form.get("show_weight_summary", 1)),
                "show_asset_list": int(request.form.get("show_asset_list", 1)),
                "show_sustainability": int(request.form.get("show_sustainability", 0)),
                "sustainability_statement": request.form.get("sustainability_statement", "").strip(),
                "signature_title": request.form.get("signature_title", "Authorized Signatory").strip(),
                "logo_path": request.form.get("logo_path", "").strip(),
                "header_text": request.form.get("header_text", "").strip(),
                "footer_text": request.form.get("footer_text", "").strip(),
                "page_layout": request.form.get("page_layout", "A4_PORTRAIT").strip(),
                "margin_top": float(request.form.get("margin_top", 36.0)),
                "margin_bottom": float(request.form.get("margin_bottom", 36.0)),
                "margin_left": float(request.form.get("margin_left", 36.0)),
                "margin_right": float(request.form.get("margin_right", 36.0)),
                "show_gst": int(request.form.get("show_gst", 1)),
                "show_cin": int(request.form.get("show_cin", 1)),
                "show_pan": int(request.form.get("show_pan", 1)),
                "show_pcb": int(request.form.get("show_pcb", 1)),
                "show_iso": int(request.form.get("show_iso", 0)),
                "show_r2": int(request.form.get("show_r2", 0)),
                "show_estewards": int(request.form.get("show_estewards", 0)),
                "status": request.form.get("status", "ACTIVE").strip(),
                "template_json": template_json
            }
            
            # Call template version control save service
            from document_engine import save_template
            save_template(t_data, username)
            flash_success("Template layout changes saved and published (new version created).")
            return redirect(url_for("certificates.templates"))
        except Exception as exc:
            flash_error(str(exc))
            
    t_list = certificate_repository.get_certificate_templates()
    return render_template(
        "certificate/templates_designer.html",
        templates=t_list
    )

@certificates_bp.route("/certificates/analytics")
def analytics():
    data = certificate_repository.get_analytics_summary()
    return render_template(
        "certificate/analytics.html",
        data=data,
        charts_json=json.dumps(data)
    )

@certificates_bp.route("/certificates/archive")
def archive():
    # Simple registry showing all archived records
    search_query = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip()
    c_type = request.args.get("type", "all").strip()
    
    filters = {"status": status, "type": c_type}
    certs = certificate_repository.search_certificates(search_query, filters)
    
    return render_template(
        "certificate/certificate_history.html",
        certs=certs,
        q=search_query,
        status=status,
        c_type=c_type
    )

@certificates_bp.route("/certificates/batch", methods=["POST"])
def batch_generate():
    user = session.get("user", {})
    try:
        job_ids = [int(x) for x in request.form.getlist("processing_job_ids")]
        template_key = request.form.get("template_key", "STANDARD").strip()
        mode = request.form.get("mode", "CONSOLIDATED").strip()
        
        generated = certificate_service.batch_generate_certificates(job_ids, template_key, user.get("username", "System"), mode)
        flash_success(f"Batch generation complete. Created {len(generated)} certificates.")
    except Exception as exc:
        flash_error(str(exc))
    return redirect(url_for("certificates.dashboard"))

@certificates_bp.route("/certificates/validate-readiness/<int:customer_id>")
def validate_readiness(customer_id):
    # API endpoints for frontend checking
    job_ids = [int(x) for x in request.args.getlist("job_ids")]
    errors = []
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT company_name, billing_address, gstin FROM party WHERE id = ?", (customer_id,))
        p_row = cursor.fetchone()
        if not p_row:
            errors.append("Invalid Customer.")
        else:
            if not p_row[1]:
                errors.append("Customer Billing Address is incomplete.")
            if not p_row[2]:
                errors.append("Customer GSTIN Number is incomplete.")
                
        # Check duplicate
        if job_ids:
            placeholders = ",".join("?" for _ in job_ids)
            cursor.execute(
                f"""SELECT c.certificate_number
                    FROM certificate_processing cp
                    JOIN certificate c ON cp.certificate_id = c.id
                    WHERE cp.processing_job_id IN ({placeholders}) AND c.status NOT IN ('CANCELLED', 'SUPERSEDED')""",
                job_ids
            )
            dups = cursor.fetchall()
            for dup in dups:
                errors.append(f"A job is already certified in certificate {dup[0]}.")
    finally:
        conn.close()
        
    return jsonify({
        "valid": len(errors) == 0,
        "errors": errors
    })

@certificates_bp.route("/certificates/parse-clipboard", methods=["POST"])
def parse_clipboard():
    try:
        data = request.get_json() or {}
        tsv_data = data.get("tsv_data", "")
        from document_engine import parse_clipboard_table
        rows = parse_clipboard_table(tsv_data)
        return jsonify({"success": True, "rows": rows})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

@certificates_bp.route("/certificates/parse-file", methods=["POST"])
def parse_file():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file.filename:
            return jsonify({"success": False, "error": "No file selected"}), 400
            
        file_bytes = file.read()
        from document_engine import parse_excel_file, parse_csv_file
        
        if file.filename.endswith(".csv"):
            rows = parse_csv_file(file_bytes)
        else:
            rows = parse_excel_file(file_bytes)
            
        return jsonify({"success": True, "rows": rows})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

@certificates_bp.route("/party/<int:party_id>/default-template", methods=["GET", "POST"])
def default_template(party_id):
    user = session.get("user", {})
    username = user.get("username", "System")
    role = user.get("role", "user")
    
    from document_engine import get_supplier_default_template, set_supplier_default_template
    
    if request.method == "POST":
        template_key = request.form.get("template_key", "").strip()
        set_supplier_default_template(party_id, template_key)
        
        # Log audit log
        from document_engine.repositories.document_repository import insert_audit_log
        insert_audit_log(
            user_name=username,
            action="SUPPLIER_DEFAULT_TEMPLATE_UPDATED",
            entity_type="party",
            entity_id=party_id,
            details=f"Assigned default template '{template_key}' to supplier ID {party_id}"
        )
        
        flash_success("Default template assigned successfully.")
        return redirect(request.referrer or url_for("party.index"))
        
    tpl = get_supplier_default_template(party_id)
    return jsonify({
        "success": True,
        "default_template_key": tpl["template_key"] if tpl else None
    })
