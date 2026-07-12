from flask import Blueprint, render_template, request, redirect, url_for, flash

from repositories.party_repository import (
    get_all_parties,
    search_parties,
    get_party_by_id,
    add_party,
    update_party,
    delete_party,
)
from data.states import STATES

party_bp = Blueprint("party", __name__)


# ── List ─────────────────────────────────────────────────────────────────────

@party_bp.route("/party")
def party():
    q = request.args.get("q", "").strip()
    parties = search_parties(q) if q else get_all_parties()
    
    page = int(request.args.get("page", 1))
    per_page = 15
    total_items = len(parties)
    total_pages = (total_items + per_page - 1) // per_page
    offset = (page - 1) * per_page
    paginated_parties = parties[offset : offset + per_page]
    
    return render_template(
        "party.html",
        parties=paginated_parties,
        q=q,
        page=page,
        total_pages=total_pages,
        total_items=total_items
    )


# ── Add ──────────────────────────────────────────────────────────────────────

@party_bp.route("/party/add", methods=["GET", "POST"])
def add_party_page():
    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "party_form.html",
                mode="add",
                party=request.form,
                states=STATES,
                errors=errors,
            )

        add_party(
            request.form["company_name"],
            request.form.get("contact_person"),
            request.form["party_type"],
            request.form.get("gstin"),
            request.form.get("pan"),
            request.form["phone"],
            request.form.get("alternate_phone"),
            request.form.get("email"),
            request.form["billing_address"],
            request.form.get("shipping_address"),
            request.form["city"],
            request.form["state"],
            request.form["state_code"],
            request.form.get("pincode"),
            request.form.get("remarks"),
        )
        flash("Party added successfully.", "success")
        return redirect(url_for("party.party"))

    return render_template(
        "party_form.html",
        mode="add",
        party=None,
        states=STATES,
        errors={},
    )


# ── Edit ─────────────────────────────────────────────────────────────────────

@party_bp.route("/party/<int:party_id>/edit", methods=["GET", "POST"])
def edit_party_page(party_id):
    existing = get_party_by_id(party_id)
    if not existing:
        flash("Party not found.", "danger")
        return redirect(url_for("party.party"))

    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "party_form.html",
                mode="edit",
                party=request.form,
                party_id=party_id,
                states=STATES,
                errors=errors,
            )

        update_party(
            party_id,
            request.form["company_name"],
            request.form.get("contact_person"),
            request.form["party_type"],
            request.form.get("gstin"),
            request.form.get("pan"),
            request.form["phone"],
            request.form.get("alternate_phone"),
            request.form.get("email"),
            request.form["billing_address"],
            request.form.get("shipping_address"),
            request.form["city"],
            request.form["state"],
            request.form["state_code"],
            request.form.get("pincode"),
            request.form.get("remarks"),
        )
        flash("Party updated successfully.", "success")
        return redirect(url_for("party.party"))

    return render_template(
        "party_form.html",
        mode="edit",
        party=existing,
        party_id=party_id,
        states=STATES,
        errors={},
    )


# ── Delete ───────────────────────────────────────────────────────────────────

@party_bp.route("/party/<int:party_id>/delete", methods=["POST"])
def delete_party_page(party_id):
    existing = get_party_by_id(party_id)
    if not existing:
        flash("Party not found.", "danger")
        return redirect(url_for("party.party"))

    delete_party(party_id)
    flash(f"Party '{existing['company_name']}' deleted.", "warning")
    return redirect(url_for("party.party"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate(form):
    errors = {}

    if not form.get("company_name", "").strip():
        errors["company_name"] = "Company name is required."

    if not form.get("phone", "").strip():
        errors["phone"] = "Phone number is required."
    elif not form["phone"].strip().isdigit():
        errors["phone"] = "Phone must contain numbers only."

    if not form.get("party_type", "").strip():
        errors["party_type"] = "Party type is required."

    if not form.get("state", "").strip():
        errors["state"] = "State is required."

    if not form.get("city", "").strip():
        errors["city"] = "City is required."

    if not form.get("billing_address", "").strip():
        errors["billing_address"] = "Billing address is required."

    gstin = form.get("gstin", "").strip()
    if gstin and len(gstin) > 15:
        errors["gstin"] = "GSTIN must be 15 characters or less."

    email = form.get("email", "").strip()
    if email and "@" not in email:
        errors["email"] = "Enter a valid email address."

    return errors
