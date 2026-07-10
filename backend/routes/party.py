from flask import Blueprint, render_template, request, redirect

from repositories.party_repository import (
    get_all_parties,
    add_party
)

from data.states import STATES

party_bp = Blueprint(
    "party",
    __name__
)


@party_bp.route("/party")
def party():

    parties = get_all_parties()

    return render_template(
        "party.html",
        parties=parties
    )


@party_bp.route("/party/add", methods=["GET", "POST"])
def add_party_page():

    if request.method == "POST":

        add_party(

            request.form["company_name"],

            request.form["contact_person"],

            request.form["party_type"],

            request.form["gstin"] or None,

            None,

            request.form["phone"],

            None,

            request.form["email"] or None,

            request.form["billing_address"],

            request.form["billing_address"],

            request.form["city"],

            request.form["state"],

            request.form["state_code"],

            None,

            None

        )

        return redirect("/party")

    return render_template(
        "add_party.html",
        states=STATES
    )