import os
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from repositories import disposal_repository, party_repository
from common.utils.flash_helpers import flash_success, flash_error, flash_warning
from database import get_connection

disposal_bp = Blueprint("disposal", __name__)
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "disposal"


def _allowed_file(filename):
    allowed_exts = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xlsx"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_exts


@disposal_bp.route("/processing/disposal-queue")
def disposal_queue():
    query = request.args.get("q", "").strip()
    disposal_type_filter = request.args.get("disposal_type", "all").strip()

    pending_items = disposal_repository.get_pending_disposal_queue(query=query)
    history_items = disposal_repository.get_disposal_history(query=query, disposal_type=disposal_type_filter)
    disposal_types = disposal_repository.get_all_disposal_types()

    # Fetch vendors from party repository (SUPPLIER, CUSTOMER, BOTH)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, company_name, party_code, party_type FROM party WHERE is_active = 1 ORDER BY company_name ASC")
        vendors = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    return render_template(
        "processing/disposal_queue.html",
        pending_items=pending_items,
        history_items=history_items,
        disposal_types=disposal_types,
        vendors=vendors,
        q=query,
        disposal_type_filter=disposal_type_filter
    )


@disposal_bp.route("/processing/disposal-queue/<int:item_id>/dispose", methods=["POST"])
def execute_disposal(item_id):
    user = session.get("user", {})
    performed_by = user.get("username", "System Operator")

    try:
        queue_item = disposal_repository.get_disposal_queue_item(item_id)
        if not queue_item:
            flash_error("Disposal Queue item not found.")
            return redirect(url_for("disposal.disposal_queue"))

        disposal_type = request.form.get("disposal_type", "").strip()
        vendor_id = request.form.get("vendor_id", "").strip()
        transport_details = request.form.get("transport_details", "").strip()
        remarks = request.form.get("remarks", "").strip()

        if not disposal_type:
            raise ValueError("Disposal Type must be selected.")

        vendor_name = ""
        v_id_val = None
        if vendor_id:
            try:
                v_id_val = int(vendor_id)
                party = party_repository.get_party_by_id(v_id_val)
                if party:
                    vendor_name = party.get("company_name", "")
            except Exception:
                pass

        doc_path = ""
        if "supporting_document" in request.files:
            file = request.files["supporting_document"]
            if file and file.filename and _allowed_file(file.filename):
                UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                s_filename = f"disposal_{item_id}_{secure_filename(file.filename)}"
                save_path = UPLOAD_DIR / s_filename
                file.save(save_path)
                doc_path = f"/static/uploads/disposal/{s_filename}"

        disposal_repository.execute_disposal_item(
            queue_id=item_id,
            disposal_type=disposal_type,
            vendor_id=v_id_val,
            vendor_name=vendor_name,
            transport_details=transport_details,
            document_path=doc_path,
            remarks=remarks,
            disposed_by=performed_by
        )

        from repositories.activity_log_repository import log_activity
        log_activity(
            performed_by,
            "Disposal Executed",
            f"Disposed {queue_item['weight']} {queue_item['unit']} of {queue_item['material_name']} via {disposal_type}",
            module="Disposal Queue",
            reference_number=queue_item["processing_number"]
        )

        flash_success(f"Item '{queue_item['material_name']}' successfully marked as Disposed.")
    except Exception as exc:
        flash_error(str(exc))

    return redirect(url_for("disposal.disposal_queue"))


@disposal_bp.route("/masters/disposal-materials", methods=["GET", "POST"])
def disposal_materials_master():
    if request.method == "POST":
        try:
            code = request.form.get("material_code", "").strip()
            name = request.form.get("material_name", "").strip()
            cat = request.form.get("category", "Hazardous E-Waste").strip()
            is_haz = 1 if request.form.get("is_hazardous") else 0
            unit = request.form.get("default_unit", "KGS").strip()
            desc = request.form.get("description", "").strip()

            if not code or not name:
                raise ValueError("Material Code and Name are required.")

            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO disposal_material_master
                       (material_code, material_name, category, is_hazardous, default_unit, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (code, name, cat, is_haz, unit, desc)
                )
                conn.commit()
            finally:
                conn.close()

            flash_success(f"Disposal Material '{name}' created successfully.")
            return redirect(url_for("disposal.disposal_materials_master"))
        except Exception as exc:
            flash_error(str(exc))

    materials = disposal_repository.get_all_disposal_materials()
    return render_template("masters/disposal_materials.html", materials=materials)


@disposal_bp.route("/masters/disposal-types", methods=["GET", "POST"])
def disposal_types_master():
    if request.method == "POST":
        try:
            name = request.form.get("type_name", "").strip()
            desc = request.form.get("description", "").strip()
            if not name:
                raise ValueError("Disposal Type Name is required.")

            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO disposal_types_master (type_name, description) VALUES (?, ?)",
                    (name, desc)
                )
                conn.commit()
            finally:
                conn.close()

            flash_success(f"Disposal Type '{name}' added successfully.")
            return redirect(url_for("disposal.disposal_types_master"))
        except Exception as exc:
            flash_error(str(exc))

    types = disposal_repository.get_all_disposal_types()
    return render_template("masters/disposal_types.html", types=types)
