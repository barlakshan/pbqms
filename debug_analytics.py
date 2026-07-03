import sys
sys.path.insert(0, '.')

from app import create_app
from app.extensions import db
from app.models import Branch, User, UserRole, QueueToken, ServiceType

app = create_app('development')

with app.app_context():
    # Get the test manager
    user = User.query.filter_by(email='testmanager@test.com').first()
    print(f"User: {user}")
    print(f"Branch ID: {user.branch_id}")
    print(f"Branch: {user.branch}")
    
    # Try to simulate what analytics() does
    from datetime import date
    from sqlalchemy import func
    from app.models import SatisfactionRating, TokenStatus
    
    today = date.today()
    branch_id = user.branch_id
    
    print(f"\nToday: {today}")
    print(f"Branch ID: {branch_id}")
    
    # Test individual queries
    try:
        total = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today).count()
        print(f"Total: {total}")
    except Exception as e:
        print(f"ERROR in total query: {e}")
    
    try:
        completed = QueueToken.query.filter_by(branch_id=branch_id, queue_date=today, status=TokenStatus.COMPLETED).count()
        print(f"Completed: {completed}")
    except Exception as e:
        print(f"ERROR in completed query: {e}")
    
    try:
        avg_rating = db.session.query(func.avg(SatisfactionRating.rating)).join(QueueToken).filter(
            QueueToken.branch_id == branch_id, QueueToken.queue_date == today).scalar()
        print(f"Avg Rating: {avg_rating}")
    except Exception as e:
        print(f"ERROR in avg_rating query: {e}")
    
    try:
        service_rows = (db.session.query(ServiceType.name, ServiceType.code,
                                        func.count(QueueToken.id))
                        .join(QueueToken, QueueToken.service_type_id == ServiceType.id)
                        .filter(QueueToken.branch_id == branch_id, QueueToken.queue_date == today)
                        .group_by(ServiceType.id).all())
        print(f"Service Rows: {service_rows}")
    except Exception as e:
        print(f"ERROR in service_rows query: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nAll queries completed successfully!")
