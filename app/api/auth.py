from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from app.api import auth_bp
from app.models import User
from app.extensions import db
from datetime import datetime, timezone


@auth_bp.route("/login-page", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login():
    # Support both JSON (API) and form (browser)
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    email    = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not user.check_password(password):
        if request.is_json:
            return jsonify({"error": "Invalid credentials"}), 401
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth_api.login_page"))

    login_user(user, remember=True)
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    if request.is_json:
        return jsonify({
            "user_id":   user.id,
            "role":      user.role.value,
            "name":      user.full_name,
            "branch_id": user.branch_id,
        })

    # Redirect based on role
    role = user.role.value
    if role == "admin":
        return redirect(url_for("admin_view.dashboard"))
    elif role == "branch_manager":
        return redirect(url_for("manager_view.dashboard"))
    else:
        return redirect(url_for("officer.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth_api.login_page"))


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({
        "id":        current_user.id,
        "name":      current_user.full_name,
        "email":     current_user.email,
        "role":      current_user.role.value,
        "branch_id": current_user.branch_id,
        "branch":    current_user.branch.name if current_user.branch else None,
    })


@auth_bp.post("/change-password")
@login_required
def change_password():
    data = request.get_json()
    if not current_user.check_password(data.get("current_password", "")):
        return jsonify({"error": "Current password is incorrect"}), 400
    new_pw = data.get("new_password", "")
    if len(new_pw) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    current_user.set_password(new_pw)
    db.session.commit()
    return jsonify({"message": "Password changed successfully"})
