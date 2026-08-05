import os
import sys
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, request, send_from_directory, render_template, redirect, url_for, session
from backend.common.utils.flash_helpers import flash_warning

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from routes.dashboard import dashboard_bp
from routes.company import company_bp
from routes.party import party_bp
from routes.material import material_bp
from routes.sales import sales_bp
from routes.purchase import purchase_bp
from routes.inventory import inventory_bp
from routes.material_processing import material_processing_bp
from routes.certificates import certificates_bp
from routes.reports import reports_bp
from routes.employees import employees_bp
from routes.accounts import accounts_bp
from routes.settings import settings_bp
from routes.users import users_bp
from routes.platform import platform_bp
from routes.factory_report import factory_report_bp
from routes.disposal import disposal_bp
from routes.masters import masters_bp
from routes.traceability import traceability_bp
from routes.documents import documents_bp
from routes.communication import communication_bp
from database import initialize_database
from security import auth_bp, configure_security
from config.business import PROCESSING_WEIGHT_TOLERANCE

app = Flask(__name__)
environment = os.environ.get("APP_ENV", "development").strip().lower()
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    if environment == "production":
        raise RuntimeError("SESSION_SECRET must be set when APP_ENV=production.")
    session_secret = os.urandom(32).hex()
app.config["SECRET_KEY"] = session_secret
app.config["PROCESSING_WEIGHT_TOLERANCE"] = PROCESSING_WEIGHT_TOLERANCE
configure_security(app)
initialize_database()

@app.route('/sw.js')
def pwa_service_worker():
    return send_from_directory('static/js', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
@app.route('/manifest.webmanifest')
def pwa_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/offline')
def pwa_offline():
    return render_template('shared/offline.html')

@app.route('/documents/mydrive')
def mydrive_page():
    return render_template('documents/mydrive.html')

@app.route('/documents/companydrive')
def companydrive_page():
    return render_template('documents/companydrive.html')

@app.route('/documents/chatfiles')
def chatfiles_page():
    return render_template('documents/chatfiles.html')

@app.route('/documents/storage-providers')
def storage_providers_page():
    user = session.get("user", {})
    role = user.get("role", "User")
    if app.config.get("ERP_AUTH_REQUIRED", True) and role not in ["ADMIN", "SUPER ADMIN", "Super Admin", "Admin"]:
        flash_warning("Access Denied: Only Super Administrators can view Storage Providers configuration.")
        return redirect('/documents/mydrive')
    return render_template('documents/storage_providers.html')

@app.route('/documents/search')
def document_search_page():
    flash_warning("Content Search & Intel is disabled in this phase.")
    return redirect('/documents/mydrive')

@app.route('/documents/admin')
def edms_admin_page():
    flash_warning("EDMS Admin & Repository is disabled in this phase.")
    return redirect('/documents/mydrive')

@app.route('/documents/multicloud')
def edms_multicloud_page():
    flash_warning("Multi-Cloud & Migration is disabled in this phase.")
    return redirect('/documents/mydrive')

@app.route('/documents/collaboration')
def edms_collaboration_page():
    flash_warning("Collaboration & Governance is disabled in this phase.")
    return redirect('/documents/mydrive')

@app.context_processor
def utility_processor():
    def modify_query(**new_values):
        args = request.args.to_dict()
        for key, value in new_values.items():
            args[key] = str(value)
        return urlencode(args)
    from routes.communication import get_global_unread_count
    return dict(modify_query=modify_query, unread_chat_count=get_global_unread_count)

app.register_blueprint(dashboard_bp)
app.register_blueprint(company_bp)
app.register_blueprint(party_bp)
app.register_blueprint(material_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(purchase_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(material_processing_bp)
app.register_blueprint(disposal_bp)
app.register_blueprint(masters_bp)
app.register_blueprint(certificates_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(employees_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(users_bp)
app.register_blueprint(platform_bp)
app.register_blueprint(factory_report_bp)
app.register_blueprint(traceability_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(communication_bp)

if __name__ == "__main__":
    # Keep the reloader off by default so the application can run reliably
    # in a normal/background process. Set FLASK_DEBUG=1 for local debugging.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
