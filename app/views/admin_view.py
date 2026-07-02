from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.views import admin_view_bp
from app.models import (Branch, User, UserRole, QueueToken, TokenStatus,
                         Customer, AuditLog, SatisfactionRating)
from app.utils.decorators import require_role
from app.extensions import db
from sqlalchemy import func
from datetime import date, timedelta


@admin_view_bp.route("/dashboard")
@login_required
@require_role(UserRole.ADMIN)
def dashboard():
    today = date.today()
    yest  = today - timedelta(days=1)

    total_branches = Branch.query.filter_by(is_active=True).count()
    tokens_today   = QueueToken.query.filter_by(queue_date=today).count()
    tokens_yest    = QueueToken.query.filter_by(queue_date=yest).count()
    today_delta    = round(((tokens_today - tokens_yest) / max(tokens_yest, 1)) * 100)
    active_users   = User.query.filter_by(is_active=True).count()

    avg_r_v     = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
        QueueToken.queue_date == today).scalar()
    rating_count = (db.session.query(func.count(SatisfactionRating.id)).join(QueueToken).filter(
        QueueToken.queue_date == today).scalar()) or 0

    top_branches_raw = (db.session.query(Branch,
                            func.count(QueueToken.id).label("cnt"),
                            func.avg(SatisfactionRating.rating).label("avg_r"))
                        .outerjoin(QueueToken, (QueueToken.branch_id == Branch.id) &
                                               (QueueToken.queue_date == today))
                        .outerjoin(SatisfactionRating,
                                   SatisfactionRating.token_id == QueueToken.id)
                        .filter(Branch.is_active == True)
                        .group_by(Branch.id)
                        .order_by(func.count(QueueToken.id).desc())
                        .limit(8).all())

    top_branches = [{
        "id": b.id,
        "code": b.code,
        "name": b.name,
        "city": b.city,
        "is_active": b.is_active,
        "tokens_today": cnt,
        "avg_rating": round(float(r or 0), 1) if r else None,
    } for b, cnt, r in top_branches_raw]

    role_counts = {
        "admin":          User.query.filter_by(is_active=True, role=UserRole.ADMIN).count(),
        "branch_manager": User.query.filter_by(is_active=True, role=UserRole.BRANCH_MANAGER).count(),
        "lobby_officer":  User.query.filter_by(is_active=True, role=UserRole.LOBBY_OFFICER).count(),
        "loan_officer":   User.query.filter_by(is_active=True, role=UserRole.LOAN_OFFICER).count(),
    }

    weekly_data, weekly_labels = [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        weekly_labels.append(d.strftime("%a"))
        weekly_data.append(QueueToken.query.filter_by(queue_date=d).count())

    recent_users    = User.query.filter_by(is_active=True).order_by(User.created_at.desc()).limit(8).all()
    audit_logs      = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()

    customers_raw = (db.session.query(Customer,
                         func.count(QueueToken.id).label("vc"))
                     .outerjoin(QueueToken, QueueToken.customer_id == Customer.id)
                     .group_by(Customer.id)
                     .order_by(func.count(QueueToken.id).desc())
                     .limit(10).all())

    recent_customers = [{"full_name": c.full_name, "mobile": c.mobile,
                          "created_at": c.created_at, "visit_count": vc,
                          "last_service": None, "last_branch": None}
                        for c, vc in customers_raw]

    return render_template("admin/dashboard.html",
        stats={
            "total_branches": total_branches, "tokens_today": tokens_today,
            "today_delta": today_delta,
            "national_rating": round(float(avg_r_v or 0), 1),
            "rating_count": rating_count, "active_users": active_users, "online_now": 0,
        },
        top_branches=top_branches, recent_users=recent_users,
        audit_logs=audit_logs, recent_customers=recent_customers,
        role_counts=role_counts,
        weekly_labels=weekly_labels, weekly_data=weekly_data,
    )


@admin_view_bp.route("/branches")
@login_required
@require_role(UserRole.ADMIN)
def branches():
    branches = Branch.query.order_by(Branch.name).all()
    return render_template("admin/branches.html", branches=branches)


@admin_view_bp.route("/branches/<int:branch_id>/qr")
@login_required
@require_role(UserRole.ADMIN)
def branch_qr(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    try:
        from app.utils.qr_generator import generate_branch_qr
        generate_branch_qr(branch)
    except Exception:
        pass
    return render_template(
        "admin/branch_qr.html",
        branch=branch,
        qr_image_url=url_for("static", filename=f"qrcodes/{branch.code}.png"),
    )


@admin_view_bp.route("/branches/new", methods=["GET", "POST"])
@login_required
@require_role(UserRole.ADMIN)
def branch_new():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip() or None
        city = request.form.get("city", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        if not code or not name:
            flash("Branch code and name are required.", "danger")
            return render_template("admin/branch_form.html", branch=None)
        if Branch.query.filter_by(code=code).first():
            flash("Branch code already exists.", "danger")
            return render_template("admin/branch_form.html", branch=None)
        branch = Branch(name=name, code=code, address=address, city=city, phone=phone)
        db.session.add(branch)
        db.session.commit()
        try:
            from app.utils.qr_generator import generate_branch_qr
            generate_branch_qr(branch)
        except Exception:
            pass
        flash("Branch created successfully.", "success")
        return redirect(url_for("admin_view.branches"))
    return render_template("admin/branch_form.html", branch=None)


@admin_view_bp.route("/branches/<int:branch_id>/edit", methods=["GET", "POST"])
@login_required
@require_role(UserRole.ADMIN)
def branch_edit(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    if request.method == "POST":
        branch.name = request.form.get("name", branch.name).strip()
        branch.address = request.form.get("address", "").strip() or None
        branch.city = request.form.get("city", "").strip() or None
        branch.phone = request.form.get("phone", "").strip() or None
        branch.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Branch updated successfully.", "success")
        return redirect(url_for("admin_view.branches"))
    return render_template("admin/branch_form.html", branch=branch)


@admin_view_bp.route("/branches/<int:branch_id>/deactivate", methods=["POST"])
@login_required
@require_role(UserRole.ADMIN)
def branch_deactivate(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    branch.is_active = False
    db.session.commit()
    flash(f"Branch {branch.name} has been deactivated.", "success")
    return redirect(url_for("admin_view.branches"))


@admin_view_bp.route("/users")
@login_required
@require_role(UserRole.ADMIN)
def users():
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    return render_template("admin/users.html", users=users)


@admin_view_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@require_role(UserRole.ADMIN)
def user_new():
    branches = Branch.query.order_by(Branch.name).all()
    roles = list(UserRole)
    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role_value = request.form.get("role")
        branch_id = request.form.get("branch_id") or None
        if not employee_id or not full_name or not email or not password or not role_value:
            flash("Employee ID, name, email, password and role are required.", "danger")
            return render_template("admin/user_form.html", user=None, branches=branches, roles=roles)
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("admin/user_form.html", user=None, branches=branches, roles=roles)
        try:
            role = UserRole[role_value]
        except KeyError:
            flash("Invalid role selected.", "danger")
            return render_template("admin/user_form.html", user=None, branches=branches, roles=roles)
        user = User(
            employee_id=employee_id,
            full_name=full_name,
            email=email,
            role=role,
            branch_id=int(branch_id) if branch_id else None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("User created successfully.", "success")
        return redirect(url_for("admin_view.users"))
    return render_template("admin/user_form.html", user=None, branches=branches, roles=roles)


@admin_view_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@require_role(UserRole.ADMIN)
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    branches = Branch.query.order_by(Branch.name).all()
    roles = list(UserRole)
    if request.method == "POST":
        user.employee_id = request.form.get("employee_id", user.employee_id).strip()
        user.full_name = request.form.get("full_name", user.full_name).strip()
        user.email = request.form.get("email", user.email).strip().lower()
        user.branch_id = int(request.form.get("branch_id")) if request.form.get("branch_id") else None
        user.is_active = bool(request.form.get("is_active"))
        role_value = request.form.get("role")
        if role_value:
            try:
                user.role = UserRole[role_value]
            except KeyError:
                flash("Invalid role selected.", "danger")
                return render_template("admin/user_form.html", user=user, branches=branches, roles=roles)
        password = request.form.get("password", "")
        if password:
            user.set_password(password)
        db.session.commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("admin_view.users"))
    return render_template("admin/user_form.html", user=user, branches=branches, roles=roles)


@admin_view_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
@require_role(UserRole.ADMIN)
def user_deactivate(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    flash(f"User {user.full_name} has been deactivated.", "success")
    return redirect(url_for("admin_view.users"))


@admin_view_bp.route("/customers")
@login_required
@require_role(UserRole.ADMIN)
def customers():
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template("admin/customers.html", customers=customers)


@admin_view_bp.route("/audit-logs")
@login_required
@require_role(UserRole.ADMIN)
def audit_logs_view():
    page = request.args.get("page", 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    return render_template("admin/audit_logs.html", logs=logs)


@admin_view_bp.route("/analytics")
@login_required
@require_role(UserRole.ADMIN)
def analytics():
    today = date.today()
    branches = Branch.query.filter_by(is_active=True).all()
    
    # Daily stats for last 30 days
    daily_stats = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        tokens = QueueToken.query.filter_by(queue_date=d).count()
        daily_stats.append({"date": d.isoformat(), "tokens": tokens})
    
    return render_template("admin/analytics.html", 
                         daily_stats=daily_stats,
                         branches=branches)
