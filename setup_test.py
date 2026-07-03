import sys
sys.path.insert(0, '.')

from app import create_app
from app.extensions import db
from app.models import Branch, User, UserRole, ServiceType

app = create_app('development')

with app.app_context():
    # Seed service types
    if ServiceType.query.count() == 0:
        services = [
            ServiceType(code="AO", name="Account Opening",  prefix="A", avg_service_min=12),
            ServiceType(code="AC", name="Account Closing",  prefix="C", avg_service_min=8),
            ServiceType(code="FD", name="Fixed Deposits",   prefix="F", avg_service_min=10),
            ServiceType(code="LN", name="Loans",            prefix="L", avg_service_min=15),
            ServiceType(code="OT", name="Other",            prefix="O", avg_service_min=10),
        ]
        for s in services:
            db.session.add(s)
        db.session.commit()
        print("Service types seeded")

    # Create a test branch
    branch = Branch.query.filter_by(code='TEST').first()
    if not branch:
        branch = Branch(code='TEST', name='Test Branch', is_active=True)
        db.session.add(branch)
        db.session.commit()
        print(f"Created branch: {branch.id}")

    # Create a test manager
    manager = User.query.filter_by(email='testmanager@test.com').first()
    if not manager:
        manager = User(
            employee_id='MGR001',
            full_name='Test Manager',
            email='testmanager@test.com',
            role=UserRole.BRANCH_MANAGER,
            branch_id=branch.id,
        )
        manager.set_password('test123')
        db.session.add(manager)
        db.session.commit()
        print(f"Created manager: {manager.id}")
    else:
        print(f"Manager already exists: {manager.id}")

print("Setup complete!")
