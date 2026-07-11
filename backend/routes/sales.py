from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash

from repositories.sales_repository import (
    get_all_invoices,
    get_invoice_by_id,
    get_invoice_items,
    create_sales_invoice,
)
from repositories.party_repository import get_all_parties
from repositories.material_repository import get_all_materials

sales_bp = Blueprint("sales", __name__)

PAYMENT_MODES = ["Cash", "NEFT", "RTGS", "UPI", "Cheque", "Credit"]


# ── List ──────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales")
def sales():
    invoices = get_all_invoices()
    return render_template("sales.html", invoices=invoices)


# ── Add ───────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales/add", methods=["GET", "POST"])
def add_sales_invoice():
    parties   = get_all_parties()
    materials = get_all_materials()

    if request.method == "POST":
        errors = _validate_header(request.form)

        # Parse items
        material_ids = request.form.getlist("material_id[]")
        qtys         = request.form.getlist("qty[]")
        weights      = request.form.getlist("weight[]")
        pieces_list  = request.form.getlist("pieces[]")
        rates        = request.form.getlist("rate[]")
        amounts      = request.form.getlist("amount[]")

        items = []
        for i in range(len(material_ids)):
            mid = material_ids[i].strip()
            if not mid:
                continue
            items.append({
                "material_id": int(mid),
                "qty":     float(qtys[i]    or 0),
                "weight":  float(weights[i] or 0),
                "pieces":  int(pieces_list[i] or 0),
                "rate":    float(rates[i]   or 0),
                "amount":  float(amounts[i] or 0),
            })

        if not items:
            errors["items"] = "Add at least one item."

        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "sales_form.html",
                form=request.form,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                errors=errors,
                today=date.today().isoformat(),
            )

        create_sales_invoice(
            party_id      = request.form["party_id"],
            invoice_date  = request.form["invoice_date"],
            payment_mode  = request.form.get("payment_mode"),
            transporter   = request.form.get("transporter"),
            vehicle_number= request.form.get("vehicle_number"),
            remarks       = request.form.get("remarks"),
            items         = items,
        )
        flash("Sales invoice created successfully.", "success")
        return redirect(url_for("sales.sales"))

    return render_template(
        "sales_form.html",
        form=None,
        parties=parties,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        errors={},
        today=date.today().isoformat(),
    )


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_header(form):
    errors = {}
    if not form.get("party_id", "").strip():
        errors["party_id"] = "Customer is required."
    if not form.get("invoice_date", "").strip():
        errors["invoice_date"] = "Invoice date is required."
    return errors
