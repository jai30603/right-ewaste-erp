import hmac
import os
import secrets
from urllib.parse import urljoin, urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__)

_CSRF_SESSION_KEY = "_csrf_token"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _as_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_security(app):
    environment = os.environ.get("APP_ENV", "development").strip().lower()
    auth_required = _as_bool(os.environ.get("ERP_AUTH_REQUIRED"), environment == "production")

    app.config.update(
        APP_ENV=environment,
        ERP_AUTH_REQUIRED=auth_required,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=environment == "production",
    )

    @app.context_processor
    def security_context():
        return {
            "csrf_token": get_csrf_token,
            "auth_required": current_app.config["ERP_AUTH_REQUIRED"],
            "current_user": session.get("user"),
        }

    @app.before_request
    def enforce_security():
        if request.method in _UNSAFE_METHODS and not _valid_csrf_token():
            abort(400, "Invalid or missing CSRF token.")

        if not current_app.config["ERP_AUTH_REQUIRED"]:
            return None

        # Exclude login and static from auth validation checks
        if request.endpoint in {"auth.login", "static"}:
            return None

        # Database session validation
        token = session.get("session_token")
        user_info = None
        if token:
            from security_core import auth_service
            user_info = auth_service.validate_session(token)

        # Session user fallback
        if not user_info and session.get("user"):
            user_info = session.get("user")
            if "role" in user_info:
                user_info["role"] = user_info["role"].upper()

        if not user_info:
            session.clear()
            if request.method == "GET":
                return redirect(url_for("auth.login", next=request.full_path))
            abort(401)

        session["user"] = user_info
        user = user_info

        # ERP role-based module visibility check
        role = user.get("role", "").upper() if isinstance(user.get("role"), str) else ""
        
        # viewer cannot perform unsafe modifications
        if request.method in _UNSAFE_METHODS and role == "VIEWER":
            abort(403, "Viewer is not authorized to modify records.")

        # ADMIN has absolute access
        if role == "ADMIN":
            return None

        # OPERATOR restrictions
        if role == "OPERATOR":
            inaccessible_paths = ["/settings", "/users", "/settings/"]
            if any(request.path.startswith(p) for p in inaccessible_paths):
                abort(403, "You do not have access to the Settings or Users modules.")

        # VIEWER restrictions
        if role == "VIEWER":
            inaccessible_paths = ["/settings", "/users", "/settings/"]
            if any(request.path.startswith(p) for p in inaccessible_paths):
                abort(403, "You do not have access to the Settings or Users modules.")

        return None


def get_csrf_token():
    token = session.get(_CSRF_SESSION_KEY)
    if token is None:
        token = secrets.token_urlsafe(32)
        session[_CSRF_SESSION_KEY] = token
    return token


def _valid_csrf_token():
    if current_app.config.get("WTF_CSRF_ENABLED") is False or current_app.config.get("CSRF_BYPASS") is True:
        return True
    if request.path.startswith("/api/v1/"):
        return True
    expected = session.get(_CSRF_SESSION_KEY, "")
    if not expected:
        expected = get_csrf_token()
    submitted = request.form.get("_csrf_token", "") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    return bool(expected and submitted and hmac.compare_digest(expected, submitted))


def _safe_next_url(target):
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in {"http", "https"} and host_url.netloc == redirect_url.netloc


from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning, flash_info

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if not current_app.config["ERP_AUTH_REQUIRED"]:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        ip = request.remote_addr or "127.0.0.1"
        browser = request.headers.get("User-Agent", "Unknown")
        device = "Desktop" if "Mobi" not in browser else "Mobile"

        from security_core import auth_service
        session_data, error = auth_service.authenticate_user(username, password, ip, browser, device)
        
        if session_data:
            session.clear()
            session["session_token"] = session_data["session_token"]
            session["user"] = {
                "username": session_data["username"],
                "role": session_data["role"],
                "full_name": session_data["full_name"],
                "user_id": session_data["user_id"]
            }
            get_csrf_token()
            next_url = request.form.get("next", "")
            return redirect(next_url if _safe_next_url(next_url) else url_for("dashboard.dashboard"))
        
        flash_error(error)

    return render_template("auth/login.html", next=request.args.get("next", ""))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = session.get("session_token")
    if token:
        from security_core import auth_service
        auth_service.invalidate_session(token)
    session.clear()
    return redirect(url_for("auth.login"))
