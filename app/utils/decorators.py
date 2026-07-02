from functools import wraps
from flask import abort, request, jsonify
from flask_login import current_user
from app.models import UserRole


def require_role(*roles):
    """Usage: @require_role(UserRole.ADMIN, UserRole.BRANCH_MANAGER)"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required"}), 401
                abort(401)
            if current_user.role not in roles:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Insufficient permissions"}), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def audit_action(action_name: str):
    """Log every decorated action to audit_logs table."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                from app.services.audit_service import AuditService
                AuditService.log(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    action=action_name,
                    payload={"url": request.path, "method": request.method},
                )
            except Exception:
                pass
            return result
        return decorated
    return decorator
