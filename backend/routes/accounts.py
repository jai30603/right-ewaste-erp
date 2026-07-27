from flask import Blueprint

accounts_bp = Blueprint("accounts", __name__)

@accounts_bp.route("/accounts")
def accounts():
    return "<h1>Accounts Module (Placeholder)</h1>"
