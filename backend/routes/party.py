from flask import Blueprint, render_template, request, redirect, url_for
import sqlite3

from repositories.party_repository import (
    get_all_parties,
    search_parties,
    get_party_by_id,
    add_party,
    update_party,
    delete_party,
    get_customer_top_materials,
)
from data.states import STATES
from repositories.activity_log_repository import log_activity
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info

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
        "party/party.html",
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
            flash_error("Please fix the errors below.")
            return render_template(
                "party/party_form.html",
                mode="add",
                party=request.form,
                states=STATES,
                errors=errors,
            )

        try:
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
            log_activity(
                "System User", "Party Added", 
                details=f"Added party {request.form['company_name']}",
                module="Party", reference_number=request.form['company_name'],
                remarks=f"Type: {request.form['party_type']}"
            )
            flash_success("Party added successfully.")
            return redirect(url_for("party.party"))
        except sqlite3.IntegrityError as e:
            flash_error(f"Database error: {e}. Check if GSTIN or Party Code is duplicated.")
            errors = {"db_error": str(e)}
            return render_template(
                "party/party_form.html",
                mode="add",
                party=request.form,
                states=STATES,
                errors=errors,
            )

    return render_template(
        "party/party_form.html",
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
        flash_error("Party not found.")
        return redirect(url_for("party.party"))

    if request.method == "POST":
        errors = _validate(request.form)
        if errors:
            flash_error("Please fix the errors below.")
            return render_template(
                "party/party_form.html",
                mode="edit",
                party=request.form,
                party_id=party_id,
                states=STATES,
                errors=errors,
            )

        try:
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
            log_activity(
                "System User", "Party Updated", 
                details=f"Updated party {request.form['company_name']}",
                module="Party", reference_number=request.form['company_name']
            )
            flash_success("Party updated successfully.")
            return redirect(url_for("party.party"))
        except sqlite3.IntegrityError as e:
            flash_error(f"Database error: {e}. Check if GSTIN is duplicated.")
            errors = {"db_error": str(e)}
            return render_template(
                "party/party_form.html",
                mode="edit",
                party=request.form,
                party_id=party_id,
                states=STATES,
                errors=errors,
            )

    return render_template(
        "party/party_form.html",
        mode="edit",
        party=existing,
        party_id=party_id,
        states=STATES,
        errors={},
    )


# ── Customer Ledger ──────────────────────────────────────────────────────────

@party_bp.route("/party/<int:party_id>/ledger")
def customer_ledger(party_id):
    party = get_party_by_id(party_id)
    if not party:
        flash_error("Party not found.")
        return redirect(url_for("party.party"))
        
    from repositories.sales_repository import get_all_invoices
    
    invoices = get_all_invoices(customer_id=party_id)
    
    total_invoices = len(invoices)
    total_purchase_val = sum(float(inv["grand_total"] or 0) for inv in invoices)
    last_purchase_date = invoices[0]["invoice_date"] if invoices else "—"
    
    top_materials = get_customer_top_materials(party_id)
    
    from repositories.certificate_repository import get_customer_certificates
    certificates = get_customer_certificates(party_id)
    
    return render_template(
        "party/customer_ledger.html",
        party=party,
        invoices=invoices,
        total_invoices=total_invoices,
        total_purchase_val=total_purchase_val,
        last_purchase_date=last_purchase_date,
        top_materials=top_materials,
        certificates=certificates
    )


# ── Delete ───────────────────────────────────────────────────────────────────

@party_bp.route("/party/<int:party_id>/delete", methods=["POST"])
def delete_party_page(party_id):
    existing = get_party_by_id(party_id)
    if not existing:
        flash_error("Party not found.")
        return redirect(url_for("party.party"))

    delete_party(party_id)
    log_activity(
        "System User", "Party Deleted", 
        details=f"Deleted party {existing['company_name']}",
        module="Party", reference_number=existing['company_name']
    )
    flash_warning(f"Party '{existing['company_name']}' deleted.")
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
