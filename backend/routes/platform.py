"""
Platform Service Routes
Central API endpoints for: Activity Center, Audit Engine, KPI Engine,
Notification Center, Dashboard Widgets, Event Log, Export Engine.
"""
import logging
from flask import Blueprint, request, jsonify, render_template, session

from security_core.decorators import login_required
from erp_platform.audit.activity_center import get_activities, get_activity_stats
from erp_platform.audit.audit_engine import get_audit_trail
from erp_platform.kpi.kpi_engine import compute_kpi, compute_all_kpis, get_kpi_history
from erp_platform.notifications.notification_service import (
    get_notifications, mark_read, get_unread_count
)
from erp_platform.events.event_bus import event_bus
from erp_platform.export.export_engine import export_to_csv
from database import get_connection


platform_bp = Blueprint('platform', __name__, url_prefix='/platform')
logger = logging.getLogger(__name__)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _current_user() -> str:
    user = session.get('user')
    if isinstance(user, dict):
        return user.get('username') or user.get('full_name', '')
    return user or ''


# ─── Activity Center ──────────────────────────────────────────────────────────

@platform_bp.route('/activities')
@login_required
def activities_page():
    activities = get_activities(limit=200)
    stats = get_activity_stats()
    modules = sorted({a.get('module') for a in activities if a.get('module')})
    return render_template('platform/activity_center.html',
                           activities=activities, stats=stats, modules=modules)


@platform_bp.route('/api/activities')
@login_required
def api_activities():
    limit = min(int(request.args.get('limit', 50)), 500)
    module = request.args.get('module')
    user = request.args.get('user')
    severity = request.args.get('severity')
    data = get_activities(limit=limit, module=module, user_name=user, severity=severity)
    return jsonify(data)


@platform_bp.route('/api/activities/export')
@login_required
def export_activities():
    data = get_activities(limit=5000)
    columns = ['id', 'user_name', 'action', 'module', 'reference_number',
               'details', 'severity', 'ip_address', 'created_at']
    return export_to_csv(data, 'activity_log', columns)


# ─── Audit Engine ─────────────────────────────────────────────────────────────

@platform_bp.route('/audit')
@login_required
def audit_page():
    table_name = request.args.get('table')
    record_id = request.args.get('record_id')
    trail = get_audit_trail(table_name=table_name, record_id=record_id, limit=200)
    conn = get_connection()
    tables = [t[0] for t in conn.execute(
        "SELECT DISTINCT entity_type FROM audit_log ORDER BY entity_type"
    ).fetchall()]
    conn.close()
    return render_template('platform/audit_trail.html',
                           trail=trail, tables=tables,
                           selected_table=table_name, selected_record=record_id)


@platform_bp.route('/api/audit')
@login_required
def api_audit():
    table_name = request.args.get('table')
    record_id = request.args.get('record_id')
    limit = min(int(request.args.get('limit', 50)), 500)
    data = get_audit_trail(table_name=table_name, record_id=record_id, limit=limit)
    return jsonify(data)


# ─── KPI Engine ───────────────────────────────────────────────────────────────

@platform_bp.route('/api/kpi/<kpi_key>')
@login_required
def api_single_kpi(kpi_key):
    result = compute_kpi(kpi_key)
    return jsonify(result)


@platform_bp.route('/api/kpi')
@login_required
def api_all_kpis():
    return jsonify(compute_all_kpis())


@platform_bp.route('/api/kpi/<kpi_key>/history')
@login_required
def api_kpi_history(kpi_key):
    days = min(int(request.args.get('days', 30)), 365)
    return jsonify(get_kpi_history(kpi_key, days))


# ─── Dashboard Widgets ────────────────────────────────────────────────────────

@platform_bp.route('/api/widgets')
@login_required
def api_widgets():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM dashboard_widgets WHERE is_active=1 ORDER BY sort_order"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@platform_bp.route('/api/widgets/activity_feed')
@login_required
def api_activity_feed():
    data = get_activities(limit=10)
    return jsonify(data)


# ─── Notification Center ──────────────────────────────────────────────────────

@platform_bp.route('/notifications')
@login_required
def notifications_page():
    user = _current_user()
    notifications = get_notifications(user, limit=100)
    unread = get_unread_count(user)
    return render_template('platform/notifications.html',
                           notifications=notifications, unread=unread)


@platform_bp.route('/api/notifications')
@login_required
def api_notifications():
    user = _current_user()
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    data = get_notifications(user, unread_only=unread_only)
    return jsonify(data)


@platform_bp.route('/api/notifications/count')
@login_required
def api_notification_count():
    user = _current_user()
    count = get_unread_count(user)
    return jsonify({'count': count})


@platform_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def api_mark_read():
    user = _current_user()
    notification_id = request.json.get('notification_id') if request.json else None
    mark_read(
        notification_id=int(notification_id) if notification_id else None,
        user_name=user if not notification_id else None
    )
    return jsonify({'success': True})


# ─── Event Log ────────────────────────────────────────────────────────────────

@platform_bp.route('/events')
@login_required
def events_page():
    conn = get_connection()
    events = [dict(e) for e in conn.execute(
        "SELECT * FROM platform_event_log ORDER BY created_at DESC LIMIT 200"
    ).fetchall()]
    conn.close()
    return render_template('platform/event_log.html', events=events)


@platform_bp.route('/api/events')
@login_required
def api_events():
    limit = min(int(request.args.get('limit', 50)), 500)
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM platform_event_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return jsonify(rows)


# ─── Platform Home (Admin Overview) ──────────────────────────────────────────

@platform_bp.route('/')
@login_required
def platform_home():
    stats = get_activity_stats()
    user = _current_user()
    unread = get_unread_count(user)
    handlers = event_bus.get_handlers()
    kpis = compute_all_kpis()
    return render_template('platform/platform_home.html',
                           stats=stats, unread=unread,
                           handlers=handlers, kpis=kpis)
