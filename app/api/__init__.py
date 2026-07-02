from flask import Blueprint

auth_bp    = Blueprint("auth_api",    __name__, url_prefix="/api/auth")
queue_bp   = Blueprint("queue_api",   __name__, url_prefix="/api/queue")
admin_bp   = Blueprint("admin_api",   __name__, url_prefix="/api/admin")
manager_bp = Blueprint("manager_api", __name__, url_prefix="/api/manager")

from app.api import auth, queue, admin, manager  # noqa: E402, F401
