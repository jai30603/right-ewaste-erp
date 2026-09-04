import os
import sys
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, request, send_from_directory, render_template

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
from routes.reports import reports_bp
from routes.settings import settings_bp
from routes.users import users_bp
from routes.masters import masters_bp
from database import initialize_database
from security import auth_bp, configure_security
from config.business import PROCESSING_WEIGHT_TOLERANCE

app = Flask(__name__)


def _inr_words(amount):
    """Convert a number to Indian Rupees in words (display helper)."""
    from services.calculation_service import number_to_inr_words
    return number_to_inr_words(amount)

environment = os.environ.get("APP_ENV", "development").strip().lower()
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    if environment == "production":
        raise RuntimeError("SESSION_SECRET must be set when APP_ENV=production.")
    session_secret = os.urandom(32).hex()
app.config["SECRET_KEY"] = session_secret
app.config["PROCESSING_WEIGHT_TOLERANCE"] = PROCESSING_WEIGHT_TOLERANCE
configure_security(app)
app.jinja_env.filters['inr_words'] = _inr_words
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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('shared/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('shared/500.html'), 500

@app.context_processor
def utility_processor():
    def modify_query(**new_values):
        args = request.args.to_dict()
        for key, value in new_values.items():
            args[key] = str(value)
        return urlencode(args)
    return dict(modify_query=modify_query)

# Register Focused Production Blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(company_bp)
app.register_blueprint(party_bp)
app.register_blueprint(material_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(purchase_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(masters_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(users_bp)

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

