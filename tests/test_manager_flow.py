import pytest

from app import create_app
from app.extensions import db
from app.models import Branch, User, UserRole


@pytest.fixture()
def client():
    app = create_app("testing")
    app.config.update(TESTING=True)

    with app.app_context():
        db.drop_all()
        db.create_all()

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.drop_all()


def test_manager_can_manage_officers_for_own_branch(client):
    with client.application.app_context():
        branch = Branch(code="COL", name="Colombo", is_active=True)
        db.session.add(branch)
        db.session.commit()

        manager = User(
            employee_id="MGR001",
            full_name="Manager Silva",
            email="manager@example.com",
            role=UserRole.BRANCH_MANAGER,
            branch_id=branch.id,
        )
        manager.set_password("secret123")
        db.session.add(manager)
        db.session.commit()

    login_response = client.post(
        "/api/auth/login",
        data={"email": "manager@example.com", "password": "secret123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    officers_page = client.get("/manager/officers")
    assert officers_page.status_code == 200
    assert b"Officer Management" in officers_page.data

    create_response = client.post(
        "/manager/officers",
        data={
            "employee_id": "OFF001",
            "full_name": "Nimal Perera",
            "email": "nimal@example.com",
            "password": "secret123",
            "role": "LOBBY_OFFICER",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    with client.application.app_context():
        created = User.query.filter_by(email="nimal@example.com").first()
        assert created is not None
        assert created.branch_id == 1
        assert created.role == UserRole.LOBBY_OFFICER


def test_manager_can_open_branch_qr_page_for_own_branch(client):
    with client.application.app_context():
        branch = Branch(code="KUR", name="Kurunegala", is_active=True)
        db.session.add(branch)
        db.session.commit()

        manager = User(
            employee_id="MGR002",
            full_name="Manager Perera",
            email="manager2@example.com",
            role=UserRole.BRANCH_MANAGER,
            branch_id=branch.id,
        )
        manager.set_password("secret123")
        db.session.add(manager)
        db.session.commit()

    client.post(
        "/api/auth/login",
        data={"email": "manager2@example.com", "password": "secret123"},
        follow_redirects=False,
    )

    response = client.get("/manager/qr")
    assert response.status_code == 200
    assert b"Branch registration QR" in response.data
