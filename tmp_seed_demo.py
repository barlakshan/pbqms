from app import create_app
from app.extensions import db
from app.models import Branch, User, UserRole

app = create_app('development')
with app.app_context():
    branch = Branch.query.filter_by(code='COL').first()
    if not branch:
        branch = Branch(code='COL', name='Colombo Main', is_active=True)
        db.session.add(branch)
        db.session.commit()

    officer = User.query.filter_by(email='officer@example.com').first()
    if not officer:
        officer = User(employee_id='OFF001', full_name='Officer One', email='officer@example.com', role=UserRole.LOBBY_OFFICER, branch_id=branch.id)
        officer.set_password('secret123')
        db.session.add(officer)
        db.session.commit()

    manager = User.query.filter_by(email='manager@example.com').first()
    if not manager:
        manager = User(employee_id='MGR001', full_name='Manager One', email='manager@example.com', role=UserRole.BRANCH_MANAGER, branch_id=branch.id)
        manager.set_password('secret123')
        db.session.add(manager)
        db.session.commit()

    print('Demo branch and users ready')
