from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.views import manager_view_bp, admin_view_bp
from app.models import (QueueToken, TokenStatus, User, UserRole, Counter,
                         ServiceType, SatisfactionRating, Branch, Customer)
from app.utils.decorators import require_role
from app.extensions import db
from sqlalchemy import func
from datetime import date, timedelta


@manager_view_bp.route("/dashboard")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def dashboard():
    today     = date.today()
    branch_id = current_user.branch_id

    total     = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today).count()
    completed = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                            status=TokenStatus.COMPLETED).count()
    waiting   = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                            status=TokenStatus.WAITING).count()
    avg_r_v   = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
        QueueToken.branch_id == branch_id, QueueToken.queue_date == today).scalar()
    r_count   = (db.session.query(func.count(SatisfactionRating.id)).join(QueueToken).filter(
        QueueToken.branch_id == branch_id, QueueToken.queue_date == today).scalar()) or 0

    priority_tokens = (QueueToken.query
                       .filter_by(branch_id=branch_id, queue_date=today, is_priority=True)
                       .order_by(QueueToken.issued_at.desc()).limit(20).all())

    other_tokens = (QueueToken.query
                    .filter_by(branch_id=branch_id, queue_date=today, status=TokenStatus.WAITING)
                    .join(ServiceType).filter(ServiceType.code == "OT").all())

    # Officer performance
    officers_raw = (db.session.query(User,
                        func.count(QueueToken.id).label("served"),
                        func.avg(SatisfactionRating.rating).label("avg_rating"))
                    .join(QueueToken, QueueToken.served_by == User.id)
                    .outerjoin(SatisfactionRating, SatisfactionRating.token_id == QueueToken.id)
                    .filter(User.branch_id == branch_id,
                            QueueToken.queue_date == today,
                            QueueToken.status == TokenStatus.COMPLETED)
                    .group_by(User.id).all())

    officers = [{"user": u, "served": s,
                  "avg_rating": round(float(r or 0), 1),
                  "avg_time": 8, "is_active": True}
                for u, s, r in officers_raw]

    svc_rows = (db.session.query(ServiceType.name, ServiceType.code,
                                  func.count(QueueToken.id))
                .join(QueueToken, QueueToken.service_type_id == ServiceType.id)
                .filter(QueueToken.branch_id == branch_id, QueueToken.queue_date == today)
                .group_by(ServiceType.id).all())

    colour_map = {"AO": "#c80000", "AC": "#99c630", "FD": "#FFCB47",
                  "LN": "#4c4e54", "OT": "#d1d2d5"}
    service_stats = [{"name": n, "code": c, "count": cnt,
                       "colour": colour_map.get(c, "#888")}
                     for n, c, cnt in svc_rows]

    return render_template("manager/dashboard.html",
        branch=current_user.branch, today=today,
        stats={
            "total": total, "completed": completed, "waiting": waiting,
            "completion_pct": round(completed / total * 100) if total else 0,
            "avg_wait": 18, "avg_rating": round(float(avg_r_v or 0), 1),
            "rating_count": r_count, "delta_pct": 8,
        },
        priority_tokens=priority_tokens, other_tokens=other_tokens,
        officers=officers, service_stats=service_stats,
        service_labels=[s["name"] for s in service_stats],
        service_counts=[s["count"] for s in service_stats],
        manager_counter_id=None,
    )


@manager_view_bp.route("/officers", methods=["GET", "POST"])
@manager_view_bp.route("/officers/", methods=["GET", "POST"])
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def officers():
    branch = current_user.branch
    if not branch and current_user.role == UserRole.ADMIN:
        branch = Branch.query.get(request.args.get("branch_id", type=int))

    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role_value = request.form.get("role", "").strip().upper()

        if not all([employee_id, full_name, email, password, role_value]):
            flash("Employee ID, name, email, password and role are required.", "danger")
            return redirect(url_for("manager_view.officers"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("manager_view.officers"))

        if role_value not in {"LOBBY_OFFICER", "LOAN_OFFICER"}:
            flash("Managers can only add lobby or loan officers.", "danger")
            return redirect(url_for("manager_view.officers"))

        try:
            role = UserRole[role_value]
        except KeyError:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("manager_view.officers"))

        user = User(
            employee_id=employee_id,
            full_name=full_name,
            email=email,
            role=role,
            branch_id=branch.id if branch else None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Officer created successfully.", "success")
        return redirect(url_for("manager_view.officers"))

    officers = []
    if branch:
        officers = (
            User.query.filter_by(branch_id=branch.id, is_active=True)
            .filter(User.role.in_([UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER]))
            .order_by(User.full_name)
            .all()
        )

    return render_template(
        "manager/officers.html",
        branch=branch,
        officers=officers,
        allowed_roles=[UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER],
    )


@manager_view_bp.route("/analytics")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def analytics():
    import traceback
    try:
        today     = date.today()
        branch_id = current_user.branch_id

        total       = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today).count()
        completed   = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                                status=TokenStatus.COMPLETED).count()
        waiting     = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                                status=TokenStatus.WAITING).count()
        avg_rating  = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
            QueueToken.branch_id == branch_id, QueueToken.queue_date == today).scalar()

        service_rows = (db.session.query(ServiceType.name, ServiceType.code,
                                        func.count(QueueToken.id))
                        .join(QueueToken, QueueToken.service_type_id == ServiceType.id)
                        .filter(QueueToken.branch_id == branch_id, QueueToken.queue_date == today)
                        .group_by(ServiceType.id).all())

        daily_counts = []
        for days_ago in range(6, -1, -1):
            day = today - timedelta(days=days_ago)
            daily_counts.append({
                "label": day.strftime("%a"),
                "count": QueueToken.query.filter_by(branch_id=branch_id, queue_date=day).count(),
            })

        return render_template("manager/analytics.html",
            branch=current_user.branch,
            stats={
                "total": total,
                "completed": completed,
                "waiting": waiting,
                "avg_rating": round(float(avg_rating or 0), 1),
                "completion_pct": round(completed / total * 100) if total else 0,
            },
            service_stats=[{"name": n, "code": c, "count": cnt} for n, c, cnt in service_rows],
            other_pending=QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                                     status=TokenStatus.WAITING).join(ServiceType).filter(ServiceType.code == "OT").count(),
            daily_counts=daily_counts,
        )
    except Exception as e:
        import sys
        print(f"ERROR in analytics: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise


@manager_view_bp.route("/customers")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def customers():
    branch_id = current_user.branch_id
    page = request.args.get("page", 1, type=int)

    rows = (db.session.query(Customer, func.count(QueueToken.id).label("visits"))
            .join(QueueToken, QueueToken.customer_id == Customer.id)
            .filter(QueueToken.branch_id == branch_id)
            .group_by(Customer.id)
            .order_by(func.count(QueueToken.id).desc())
            .paginate(page=page, per_page=25, error_out=False))

    return render_template("manager/customers.html",
        branch=current_user.branch,
        customers=rows.items,
        total=rows.total,
        page=page,
        pages=rows.pages,
    )


@manager_view_bp.route("/queue/other")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def other_queue():
    today     = date.today()
    branch_id = current_user.branch_id

    other_tokens = (QueueToken.query
                    .filter_by(branch_id=branch_id, queue_date=today, status=TokenStatus.WAITING)
                    .join(ServiceType).filter(ServiceType.code == "OT")
                    .order_by(QueueToken.issued_at.asc()).all())

    return render_template("manager/other_queue.html",
        branch=current_user.branch,
        other_tokens=other_tokens,
        manager_counter_id=None,
    )


@manager_view_bp.route("/qr")
@manager_view_bp.route("/qr/")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN, UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER)
def branch_qr():
    branch = current_user.branch
    if not branch and current_user.role == UserRole.ADMIN:
        flash("Select a branch before viewing the QR code.", "danger")
        return redirect(url_for("admin_view.branches"))
    if not branch:
        flash("No branch is assigned to this account.", "danger")
        return redirect(url_for("manager_view.dashboard"))

    try:
        from app.utils.qr_generator import generate_branch_qr
        generate_branch_qr(branch)
    except Exception:
        pass

    return render_template(
        "manager/branch_qr.html",
        branch=branch,
        qr_image_url=url_for("static", filename=f"qrcodes/{branch.code}.png"),
    )
