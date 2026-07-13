from flask import Blueprint, render_template, request, redirect, url_for, flash

from repositories.material_repository import (
    get_all_materials,
    search_materials,
    get_material_by_id,
    add_material,
    update_material,
    delete_material,
)
from repositories.activity_log_repository import log_activity

material_bp = Blueprint("material", __name__)

CATEGORIES = [
    "Laptop", "Desktop", "Monitor", "Mobile",
    "Battery", "Cable", "PCB", "Plastic", "Metal", "Other",
]

UNITS = ["KG", "PCS", "NOS", "BOX", "LTR"]

GST_RATES = ["0", "5", "12", "18", "28"]


# ── List ──────────────────────────────────────────────────────────────────────

@material_bp.route("/material")
def material():
    q = request.args.get("q", "").strip()
    materials = search_materials(q) if q else get_all_materials()
    
    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(materials)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_materials = materials[offset : offset + per_page]
    
    return render_template(
        "material.html",
        materials=paginated_materials,
        q=q,
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
            flash("Please fix the errors below.", "danger")
            return render_template(
                "material_form.html",
                mode="add",
                material=request.form,
                categories=CATEGORIES,
                units=UNITS,
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
        log_activity("System User", "Material Added", f"Added material {request.form['material_name']} ({request.form['category']})")
        flash("Material added successfully.", "success")
        return redirect(url_for("material.material"))

    return render_template(
        "material_form.html",
        mode="add",
        material=None,
        categories=CATEGORIES,
        units=UNITS,
        gst_rates=GST_RATES,
        errors={},
    )


# ── Edit ──────────────────────────────────────────────────────────────────────

@material_bp.route("/material/edit/<int:material_id>", methods=["GET", "POST"])
def edit_material_page(material_id):
    existing = get_material_by_id(material_id)
    if not existing:
        flash("Material not found.", "danger")
        return redirect(url_for("material.material"))

    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "material_form.html",
                mode="edit",
                material=request.form,
                material_id=material_id,
                categories=CATEGORIES,
                units=UNITS,
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
        log_activity("System User", "Material Updated", f"Updated material {request.form['material_name']}")
        flash("Material updated successfully.", "success")
        return redirect(url_for("material.material"))

    return render_template(
        "material_form.html",
        mode="edit",
        material=existing,
        material_id=material_id,
        categories=CATEGORIES,
        units=UNITS,
        gst_rates=GST_RATES,
        errors={},
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@material_bp.route("/material/delete/<int:material_id>", methods=["POST"])
def delete_material_page(material_id):
    existing = get_material_by_id(material_id)
    if not existing:
        flash("Material not found.", "danger")
        return redirect(url_for("material.material"))

    delete_material(material_id)
    log_activity("System User", "Material Deleted", f"Deleted material {existing['material_name']}")
    flash(f"Material '{existing['material_name']}' deleted.", "warning")
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
