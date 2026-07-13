"""
Dashboard Service
Assembles all dashboard data from the repository layer.
The route should call get_dashboard_data() and pass it directly to the template.
"""
from repositories.dashboard_repository import get_dashboard_snapshot
from repositories.activity_log_repository import get_recent_activities


def get_dashboard_data():
    """Assemble and return the full dashboard context dict."""
    snapshot = get_dashboard_snapshot()
    recent_activity = get_recent_activities(limit=10)
    return {
        "snapshot": snapshot,
        "recent_activity": recent_activity,
    }
