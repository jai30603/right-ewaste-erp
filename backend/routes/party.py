import re
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from repositories.party_repository import (
    get_all_parties,
    add_party,
    search_party,
    update_party,
    get_party_by_id
)

from data.states import STATES

party_bp = Blueprint(
    "party",
    __name__
)


def _party_values(form):
    """Validate and normalize untrusted party form input."""
    company_name = form.get("company_name", "").strip()
    party_type = form.get("party_type", "").strip()
    phone = form.get("phone", "").strip()
    billing_address = form.get("billing_address", "").strip()
    city = form.get("city", "").strip()
    state = form.get("state", "").strip()
    gstin = form.get("gstin", "").strip().upper() or None
    email = form.get("email", "").strip() or None

    if not all((company_name, billing_address, city)):
        raise ValueError("Company name, billing address, and city are required.")
    if party_type not in {"CUSTOMER", "SUPPLIER", "BOTH"}:
        raise ValueError("Choose a valid party type.")
    if not re.fullmatch(r"\d{10}", phone):
        raise ValueError("Phone number must contain exactly 10 digits.")
    if state not in STATES:
        raise ValueError("Choose a valid state.")
    if gstin and not re.fullmatch(r"[0-9A-Z]{15}", gstin):
        raise ValueError("GSTIN must contain 15 uppercase letters or digits.")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")

    return (
        company_name,
        form.get("contact_person", "").strip() or None,
        party_type,
        gstin,
        None,
        phone,
        None,
        email,
        billing_address,
        billing_address,
        city,
        state,
        STATES[state],
        None,
        None,
    )


def _form_error(message, party=None, is_edit=False):
    flash(message, "danger")
    return render_template("add_party.html", party=party, states=STATES, is_edit=is_edit), 400


@party_bp.route("/party")
def party():

    keyword = request.args.get("search")

    if keyword:
        parties = search_party(keyword)
    else:
        parties = get_all_parties()

    return render_template(
        "party.html",
        parties=parties,
        keyword=keyword or ""
    )


@party_bp.route("/party/add", methods=["GET", "POST"])
def add_party_page():

    if request.method == "POST":
        try:
            add_party(*_party_values(request.form))
        except ValueError as error:
            return _form_error(str(error), request.form)
        except sqlite3.IntegrityError:
            return _form_error("A party with this GSTIN already exists.", request.form)

        flash("Party created.", "success")
        return redirect(url_for("party.party"))

    return render_template(
        "add_party.html",
        states=STATES
    )

@party_bp.route("/party/edit/<int:party_id>", methods=["GET", "POST"])
def edit_party(party_id):

    party = get_party_by_id(party_id)
    if party is None:
        abort(404)

    if request.method == "POST":
        try:
            updated = update_party(party_id, *_party_values(request.form))
        except ValueError as error:
            return _form_error(str(error), request.form, is_edit=True)
        except sqlite3.IntegrityError:
            return _form_error("A party with this GSTIN already exists.", request.form, is_edit=True)

        if not updated:
            abort(404)
        flash("Party updated.", "success")
        return redirect(url_for("party.party"))

    return render_template(
        "add_party.html",
        party=party,
        states=STATES,
        is_edit=True
    )
