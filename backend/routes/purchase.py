from flask import Blueprint

purchase_bp = Blueprint(
    "purchase",
    __name__
)


@purchase_bp.route("/purchase")
def purchase():

    return "<h1>Purchase Invoice Module</h1>"