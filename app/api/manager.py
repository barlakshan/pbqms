from flask import request, jsonify
from flask_login import login_required, current_user
from app.api import manager_bp
from app.models import (QueueToken, TokenStatus, UserRole, SatisfactionRating,
                          ServiceType, User, Counter)
from app.utils.decorators import require_role
from app.extensions import db
from sqlalchemy import func
from datetime import date, timedelta


@manager_bp.get("/dashboard")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def dashboard():
    today     = date.today()
    branch_id = current_user.branch_id
    total     = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today).count()
    done      = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                            status=TokenStatus.COMPLETED).count()
    waiting   = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                            status=TokenStatus.WAITING).count()
    avg_r     = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
        QueueToken.branch_id == branch_id, QueueToken.queue_date == today).scalar()
    return jsonify({
        "total_today":     total,
        "completed":       done,
        "waiting":         waiting,
        "avg_rating":      round(float(avg_r or 0), 1),
        "completion_pct":  round(done / total * 100) if total else 0,
    })


@manager_bp.get("/analytics/today")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def analytics_today():
    today     = date.today()
    branch_id = current_user.branch_id
    by_service = (db.session.query(ServiceType.name, ServiceType.code,
                                    func.count(QueueToken.id))
                  .join(QueueToken, QueueToken.service_type_id == ServiceType.id)
                  .filter(QueueToken.branch_id == branch_id,
                           QueueToken.queue_date == today)
                  .group_by(ServiceType.id).all())
    return jsonify({
        "by_service": [{"service": n, "code": c, "count": cnt}
                       for n, c, cnt in by_service]
    })


@manager_bp.get("/analytics/range")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def analytics_range():
    days      = request.args.get("days", 7, type=int)
    branch_id = current_user.branch_id
    today     = date.today()
    result    = []
    for i in range(days - 1, -1, -1):
        d   = today - timedelta(days=i)
        cnt = QueueToken.query.filter_by(branch_id=branch_id, queue_date=d).count()
        result.append({"date": d.isoformat(), "count": cnt})
    return jsonify(result)


@manager_bp.get("/officers/performance")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def officer_performance():
    today     = date.today()
    branch_id = current_user.branch_id
    rows = (db.session.query(User,
                func.count(QueueToken.id).label("served"),
                func.avg(SatisfactionRating.rating).label("avg_rating"))
            .join(QueueToken, QueueToken.served_by == User.id)
            .outerjoin(SatisfactionRating, SatisfactionRating.token_id == QueueToken.id)
            .filter(User.branch_id == branch_id,
                    QueueToken.queue_date == today,
                    QueueToken.status == TokenStatus.COMPLETED)
            .group_by(User.id).all())
    return jsonify([{
        "id": u.id, "name": u.full_name, "role": u.role.value,
        "served": s, "avg_rating": round(float(r or 0), 1),
    } for u, s, r in rows])


@manager_bp.post("/token/<int:token_id>/transfer")
@login_required
@require_role(UserRole.BRANCH_MANAGER)
def transfer_token(token_id):
    data    = request.get_json(force=True)
    token   = QueueToken.query.get_or_404(token_id)
    counter = Counter.query.get_or_404(data["counter_id"])
    token.counter_id = counter.id
    db.session.commit()
    return jsonify({"message": f"Token {token.token_number} transferred to {counter.label}"})


@manager_bp.get("/customers")
@login_required
@require_role(UserRole.BRANCH_MANAGER, UserRole.ADMIN)
def branch_customers():
    from app.models import Customer
    branch_id = current_user.branch_id
    page  = request.args.get("page", 1, type=int)
    rows  = (db.session.query(Customer, func.count(QueueToken.id).label("visits"))
             .join(QueueToken, QueueToken.customer_id == Customer.id)
             .filter(QueueToken.branch_id == branch_id)
             .group_by(Customer.id)
             .order_by(func.count(QueueToken.id).desc())
             .paginate(page=page, per_page=30, error_out=False))
    return jsonify({
        "items": [{"name": c.full_name, "mobile": c.mobile, "visits": v}
                  for c, v in rows.items],
        "total": rows.total,
    })
