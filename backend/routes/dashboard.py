from flask import Blueprint, render_template
from datetime import date
from services.dashboard_service import get_dashboard_data

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def dashboard():
    data = get_dashboard_data()
    return render_template(
        "dashboard/dashboard.html",
        snapshot=data["snapshot"],
        recent_activity=data["recent_activity"],
        today=date.today().strftime("%A, %d %B %Y"),
    )
