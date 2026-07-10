from flask import Blueprint

company_bp = Blueprint(
    "company",
    __name__
)


@company_bp.route("/company")
def company():

    return "<h1>Company Module</h1>"