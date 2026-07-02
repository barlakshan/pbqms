from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.views import officer_bp
from app.models import QueueToken, TokenStatus, Counter, UserRole, SatisfactionRating, ServiceType
from app.utils.decorators import require_role
from app.extensions import db
from sqlalchemy import func
from datetime import date, datetime


@officer_bp.route("/dashboard")
@login_required
@require_role(UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER)
def dashboard():
    today      = date.today()
    branch_id  = current_user.branch_id
    counter    = Counter.query.filter_by(user_id=current_user.id, is_active=True).first()

    # Build a dummy counter if none assigned
    if not counter:
        counter = type("Counter", (), {"id": 0, "label": "Counter 1"})()

    # My stats
    served_today = QueueToken.query.filter_by(
        branch_id=branch_id, served_by=current_user.id,
        queue_date=today, status=TokenStatus.COMPLETED,
    ).count()

    waiting = QueueToken.query.filter_by(
        branch_id=branch_id, status=TokenStatus.WAITING, queue_date=today,
    ).count()

    priority_waiting = QueueToken.query.filter_by(
        branch_id=branch_id, status=TokenStatus.WAITING,
        queue_date=today, is_priority=True,
    ).count()

    avg_rating_v = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
        QueueToken.branch_id == branch_id,
        QueueToken.served_by == current_user.id,
        QueueToken.queue_date == today,
    ).scalar()
    avg_rating   = round(float(avg_rating_v or 0), 1)
    rating_count = (db.session.query(func.count(SatisfactionRating.id))
                    .join(QueueToken)
                    .filter(QueueToken.served_by == current_user.id, QueueToken.queue_date == today)
                    .scalar()) or 0

    # Hourly chart — last 8 hours
    current_hour  = datetime.now().hour
    start_hour    = max(8, current_hour - 7)

    completed_today = (QueueToken.query
                        .filter(
                            QueueToken.branch_id == branch_id,
                            QueueToken.served_by == current_user.id,
                            QueueToken.queue_date == today,
                            QueueToken.status == TokenStatus.COMPLETED,
                            QueueToken.completed_at.isnot(None),
                        ).all())
    counts_by_hour = {}
    for t in completed_today:
        counts_by_hour[t.completed_at.hour] = counts_by_hour.get(t.completed_at.hour, 0) + 1

    hourly_labels = []
    hourly_data   = []
    for h in range(start_hour, current_hour + 1):
        label = f"{h}am" if h < 12 else (f"{h-12}pm" if h > 12 else "12pm")
        hourly_labels.append(label)
        hourly_data.append(counts_by_hour.get(h, 0))
    peak_hour = hourly_data.index(max(hourly_data)) if hourly_data and max(hourly_data) > 0 else 0

    # Recent completed
    recent = (QueueToken.query
              .filter_by(served_by=current_user.id, queue_date=today, status=TokenStatus.COMPLETED)
              .order_by(QueueToken.completed_at.desc())
              .limit(8).all())

    stats = {
        "served_today": served_today, "served_delta": 3,
        "waiting": waiting, "priority_waiting": priority_waiting,
        "avg_service_min": 8, "avg_rating": avg_rating,
        "rating_count": rating_count,
    }
    return render_template("officer/dashboard.html",
        counter=counter, branch=current_user.branch,
        stats=stats, recent_tokens=recent,
        hourly_labels=hourly_labels, hourly_data=hourly_data, peak_hour=peak_hour,
    )
