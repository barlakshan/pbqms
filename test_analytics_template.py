import sys
sys.path.insert(0, '.')

from app import create_app
from app.extensions import db
from app.models import Branch, User, UserRole, QueueToken, ServiceType, SatisfactionRating, TokenStatus
from datetime import date, timedelta
from sqlalchemy import func
from flask import render_template

app = create_app('development')

with app.app_context():
    # Get the test manager
    user = User.query.filter_by(email='testmanager@test.com').first()
    
    today = date.today()
    branch_id = user.branch_id
    
    total = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today).count()
    completed = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                           status=TokenStatus.COMPLETED).count()
    waiting = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today,
                                         status=TokenStatus.WAITING).count()
    avg_rating = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
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
    
    # Now try to render the template
    try:
        html = render_template("manager/analytics.html",
            branch=user.branch,
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
        print("Template rendered successfully!")
        print(f"HTML length: {len(html)}")
    except Exception as e:
        print(f"ERROR rendering template: {e}")
        import traceback
        traceback.print_exc()
