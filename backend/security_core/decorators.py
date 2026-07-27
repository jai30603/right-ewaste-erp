import functools
from flask import session, redirect, url_for, abort, request, current_app
from backend.common.utils.flash_helpers import flash_warning

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.config.get("ERP_AUTH_REQUIRED", True):
            return f(*args, **kwargs)
        if "user" not in session:
            if request.path.startswith("/api/"):
                abort(401, "Authentication required.")
            return redirect(url_for("auth.login", next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function

def require_role(role_code):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_app.config.get("ERP_AUTH_REQUIRED", True):
                return f(*args, **kwargs)
            user = session.get("user")
            if not user:
                return redirect(url_for("auth.login", next=request.full_path))
            if user["role"] != "ADMIN" and user["role"] != role_code:
                if request.path.startswith("/api/"):
                    abort(403, "Access denied.")
                flash_warning("You do not have authorization to access this section.")
                return redirect(url_for("dashboard.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(module_name, permission_code):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_app.config.get("ERP_AUTH_REQUIRED", True):
                return f(*args, **kwargs)
            user = session.get("user")
            if not user:
                return redirect(url_for("auth.login", next=request.full_path))
                
            # Super Admin has access to all modules and permissions
            if user["role"] == "ADMIN":
                return f(*args, **kwargs)
                
            from security_core import permission_service
            if not permission_service.has_permission(user["role"], module_name, permission_code):
                if request.path.startswith("/api/"):
                    abort(403, "Permission denied.")
                flash_warning(f"You do not have permission to perform this action ({permission_code} on {module_name}).")
                return redirect(url_for("dashboard.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
