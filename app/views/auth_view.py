from flask import redirect, url_for, flash
from flask_login import logout_user, login_required
from app.views import auth_view_bp


@auth_view_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth_api.login_page"))
