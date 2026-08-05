from flask import Blueprint, render_template, request, redirect, url_for

from repositories.material_repository import (
    get_all_materials,
    search_materials,
    get_material_by_id,
    add_material,
    update_material,
    delete_material,
)
from repositories.activity_log_repository import log_activity
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info

material_bp = Blueprint("material", __name__)

def get_categories():
    from repositories import settings_repository
    try:
        cats = [c["name"] for c in settings_repository.get_all_categories() if c["is_active"] == 1]
        return cats if cats else [
            "Laptop", "Desktop", "Monitor", "Mobile",
            "Battery", "Cable", "PCB", "Plastic", "Metal", "Other",
        ]
    except Exception:
        return [
            "Laptop", "Desktop", "Monitor", "Mobile",
            "Battery", "Cable", "PCB", "Plastic", "Metal", "Other",
        ]

def get_units():
    from repositories import settings_repository
    try:
        units = [u["name"] for u in settings_repository.get_all_units() if u["is_active"] == 1]
        return units if units else ["KG", "PCS", "NOS", "BOX", "LTR"]
    except Exception:
        return ["KG", "PCS", "NOS", "BOX", "LTR"]

GST_RATES = ["0", "5", "12", "18", "28"]


# ── List ──────────────────────────────────────────────────────────────────────

@material_bp.route("/material")
def material():
    q = request.args.get("q", "").strip()
    category_filter = request.args.get("category_filter", "all").strip()
    gst_filter = request.args.get("gst_filter", "all").strip()

    all_materials = search_materials(q) if q else get_all_materials()

    # Filter by category / GST (URL-persistent, no backend change)
    if category_filter and category_filter != "all":
        all_materials = [m for m in all_materials if m["category"] == category_filter]
    if gst_filter and gst_filter != "all":
        all_materials = [m for m in all_materials if str(m["gst_percentage"]) == gst_filter]

    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(all_materials)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_materials = all_materials[offset : offset + per_page]

    return render_template(
        "material/material.html",
        materials=paginated_materials,
        q=q,
        category_filter=category_filter,
        gst_filter=gst_filter,
        categories=get_categories(),
        gst_rates=GST_RATES,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )


# ── Add ───────────────────────────────────────────────────────────────────────

@material_bp.route("/material/add", methods=["GET", "POST"])
def add_material_page():
    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            flash_error("Please fix the errors below.")
            return render_template(
                "material/material_form.html",
                mode="add",
                material=request.form,
                categories=get_categories(),
                units=get_units(),
                gst_rates=GST_RATES,
                errors=errors,
            )

        add_material(
            request.form["material_name"],
            request.form["category"],
            request.form.get("hsn_code"),
            request.form["uom"],
            request.form["gst_percentage"],
            request.form.get("description"),
            request.form.get("tracking_type", "BOTH")
        )
        log_activity(
            "System User", "Material Added", 
            details=f"Added material {request.form['material_name']}",
            module="Material", reference_number=request.form['material_name'],
            remarks=f"Category: {request.form['category']}"
        )
        flash_success("Material added successfully.")
        return redirect(url_for("material.material"))

    return render_template(
        "material/material_form.html",
        mode="add",
        material=None,
        categories=get_categories(),
        units=get_units(),
        gst_rates=GST_RATES,
        errors={},
    )


# ── Edit ──────────────────────────────────────────────────────────────────────

@material_bp.route("/material/edit/<int:material_id>", methods=["GET", "POST"])
def edit_material_page(material_id):
    existing = get_material_by_id(material_id)
    if not existing:
        flash_error("Material not found.")
        return redirect(url_for("material.material"))

    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            flash_error("Please fix the errors below.")
            return render_template(
                "material/material_form.html",
                mode="edit",
                material=request.form,
                material_id=material_id,
                categories=get_categories(),
                units=get_units(),
                gst_rates=GST_RATES,
                errors=errors,
            )

        update_material(
            material_id,
            request.form["material_name"],
            request.form["category"],
            request.form.get("hsn_code"),
            request.form["uom"],
            request.form["gst_percentage"],
            request.form.get("description"),
            request.form.get("tracking_type", "BOTH")
        )
        log_activity(
            "System User", "Material Updated", 
            details=f"Updated material {request.form['material_name']}",
            module="Material", reference_number=request.form['material_name']
        )
        flash_success("Material updated successfully.")
        return redirect(url_for("material.material"))

    return render_template(
        "material/material_form.html",
        mode="edit",
        material=existing,
        material_id=material_id,
        categories=get_categories(),
        units=get_units(),
        gst_rates=GST_RATES,
        errors={},
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@material_bp.route("/material/delete/<int:material_id>", methods=["POST"])
def delete_material_page(material_id):
    existing = get_material_by_id(material_id)
    if not existing:
        flash_error("Material not found.")
        return redirect(url_for("material.material"))

    delete_material(material_id)
    log_activity(
        "System User", "Material Deleted", 
        details=f"Deleted material {existing['material_name']}",
        module="Material", reference_number=existing['material_name']
    )
    flash_warning(f"Material '{existing['material_name']}' deleted.")
    return redirect(url_for("material.material"))


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(form):
    errors = {}

    if not form.get("material_name", "").strip():
        errors["material_name"] = "Material name is required."

    if not form.get("category", "").strip():
        errors["category"] = "Category is required."

    if not form.get("hsn_code", "").strip():
        errors["hsn_code"] = "HSN code is required."

    if not form.get("uom", "").strip():
        errors["uom"] = "Unit is required."

    if not form.get("gst_percentage", "").strip():
        errors["gst_percentage"] = "GST percentage is required."

    return errors
