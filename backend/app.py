import os
import sys
from pathlib import Path

from flask import Flask

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
from database import initialize_database

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
initialize_database()

from flask import request
from urllib.parse import urlencode

@app.context_processor
def utility_processor():
    def modify_query(**new_values):
        args = request.args.to_dict()
        for key, value in new_values.items():
            args[key] = str(value)
        return urlencode(args)
    return dict(modify_query=modify_query)

app.register_blueprint(dashboard_bp)
app.register_blueprint(company_bp)
app.register_blueprint(party_bp)
app.register_blueprint(material_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(purchase_bp)
app.register_blueprint(inventory_bp)

if __name__ == "__main__":
    # Keep the reloader off by default so the application can run reliably
    # in a normal/background process. Set FLASK_DEBUG=1 for local debugging.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
