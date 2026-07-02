from flask import Blueprint

auth_view_bp    = Blueprint("auth_view",     __name__, url_prefix="/auth")
customer_bp     = Blueprint("customer",      __name__)
display_bp      = Blueprint("display",       __name__, url_prefix="/display")
officer_bp      = Blueprint("officer",       __name__, url_prefix="/officer")
admin_view_bp   = Blueprint("admin_view",    __name__, url_prefix="/admin")
manager_view_bp = Blueprint("manager_view",  __name__, url_prefix="/manager")

from app.views import auth_view, customer, display, officer, admin_view, manager_view  # noqa
