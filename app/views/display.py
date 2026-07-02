from flask import render_template, redirect, url_for
from flask_login import login_required
from flask_socketio import join_room
from app.views import display_bp
from app.models import Branch
from app.extensions import socketio


@display_bp.route("/")
def display_redirect():
    """Redirect to branch selection or dashboard."""
    return redirect(url_for("index"))


@display_bp.route("/<string:branch_code>")
def screen(branch_code):
    branch = Branch.query.filter_by(code=branch_code.upper(), is_active=True).first_or_404()
    return render_template("display/screen.html", branch=branch)


@socketio.on("join_branch_display")
def on_join_display(data):
    branch_code = data.get("branch_code", "").upper()
    branch = Branch.query.filter_by(code=branch_code).first()
    if branch:
        join_room(f"branch_{branch.id}")


@socketio.on("join_branch")
def on_join_branch(data):
    branch_id = data.get("branch_id")
    if branch_id:
        join_room(f"branch_{branch_id}")
