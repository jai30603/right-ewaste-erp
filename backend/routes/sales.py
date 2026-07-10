from flask import Blueprint

sales_bp = Blueprint(
    "sales",
    __name__
)


@sales_bp.route("/sales")
def sales():

    return "<h1>Sales Invoice Module</h1>"