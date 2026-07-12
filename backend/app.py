import os
import secrets

from flask import Flask, abort, session

from routes.dashboard import dashboard_bp
from routes.company import company_bp
from routes.party import party_bp
from routes.material import material_bp
from routes.sales import sales_bp
from routes.purchase import purchase_bp

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@app.context_processor
def inject_csrf_token():
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return {"csrf_token": token}


@app.before_request
def protect_post_requests():
    from flask import request

    if request.method == "POST" and request.form.get("csrf_token") != session.get("csrf_token"):
        abort(400, "Invalid or missing form token.")

app.register_blueprint(dashboard_bp)
app.register_blueprint(company_bp)
app.register_blueprint(party_bp)
app.register_blueprint(material_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(purchase_bp)

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
