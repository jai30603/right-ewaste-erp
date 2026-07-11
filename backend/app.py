import os
from flask import Flask

from routes.dashboard import dashboard_bp
from routes.company import company_bp
from routes.party import party_bp
from routes.material import material_bp
from routes.sales import sales_bp
from routes.purchase import purchase_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-change-me")

app.register_blueprint(dashboard_bp)
app.register_blueprint(company_bp)
app.register_blueprint(party_bp)
app.register_blueprint(material_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(purchase_bp)

if __name__ == "__main__":
    app.run(debug=True)