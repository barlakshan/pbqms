import pytest

from app import create_app
from app.extensions import db
from app.models import Branch, QueueToken, SatisfactionRating, ServiceType, TokenStatus, User, UserRole


@pytest.fixture()
def client():
    app = create_app("testing")
    app.config.update(TESTING=True)

    with app.app_context():
        db.drop_all()
        db.create_all()
        for service in [
            ServiceType(code="AO", name="Account Opening", prefix="A", avg_service_min=12),
            ServiceType(code="AC", name="Account Closing", prefix="C", avg_service_min=8),
            ServiceType(code="FD", name="Fixed Deposits", prefix="F", avg_service_min=10),
            ServiceType(code="LN", name="Loans", prefix="L", avg_service_min=15),
            ServiceType(code="OT", name="Other", prefix="O", avg_service_min=10),
        ]:
            db.session.add(service)
        db.session.commit()

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.drop_all()


def test_public_display_route_renders_live_screen(client):
    with client.application.app_context():
        branch = Branch(code="COL", name="Colombo", is_active=True)
        db.session.add(branch)
        db.session.commit()

    response = client.get("/display")
    assert response.status_code == 200
    assert b"Queue Display" in response.data
    assert b"Colombo" in response.data


def test_customer_registration_and_queue_lifecycle(client):
    with client.application.app_context():
        branch = Branch(code="COL", name="Colombo", is_active=True)
        db.session.add(branch)
        db.session.commit()
        officer = User(
            employee_id="OFF001",
            full_name="Officer One",
            email="officer@example.com",
            role=UserRole.LOBBY_OFFICER,
            branch_id=branch.id,
        )
        officer.set_password("secret123")
        db.session.add(officer)
        db.session.commit()
        service = ServiceType.query.filter_by(code="AO").first()
        branch_id = branch.id
        service_id = service.id

    login_response = client.post(
        "/api/auth/login",
        json={"email": "officer@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    register_response = client.post(
        "/api/queue/register",
        json={
            "branch_id": branch_id,
            "full_name": "Nimal Perera",
            "mobile": "0771234567",
            "service_type_id": service_id,
        },
    )
    assert register_response.status_code == 201
    payload = register_response.get_json()
    assert payload["token_number"].startswith("A")
    assert payload["position"] >= 0

    with client.application.app_context():
        token = QueueToken.query.get(payload["token_id"])
        assert token is not None
        assert token.status == TokenStatus.WAITING
        assert token.estimated_wait_min >= 0

    status_response = client.get(f"/api/queue/token/{payload['token_id']}/status")
    assert status_response.status_code == 200
    assert status_response.get_json()["status"] == "waiting"

    call_response = client.post("/api/queue/call-next", json={"counter_id": 1})
    assert call_response.status_code == 200

    start_response = client.post(f"/api/queue/token/{payload['token_id']}/start")
    assert start_response.status_code == 200

    complete_response = client.post(f"/api/queue/token/{payload['token_id']}/complete")
    assert complete_response.status_code == 200

    rating_response = client.post(
        f"/api/queue/token/{payload['token_id']}/rate",
        json={"rating": 5, "comment": "Great service"},
    )
    assert rating_response.status_code == 200

    with client.application.app_context():
        token = QueueToken.query.get(payload["token_id"])
        assert token.status == TokenStatus.COMPLETED
        assert SatisfactionRating.query.filter_by(token_id=token.id).count() == 1


def test_admin_can_manage_branches_and_users(client):
    with client.application.app_context():
        admin = User(
            employee_id="ADM001",
            full_name="Admin One",
            email="admin@example.com",
            role=UserRole.ADMIN,
        )
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    dashboard_response = client.get("/admin/dashboard")
    assert dashboard_response.status_code == 200

    branches_response = client.get("/api/admin/branches")
    assert branches_response.status_code == 200

    create_branch_response = client.post(
        "/api/admin/branches",
        json={"name": "Galle", "code": "GAL"},
    )
    assert create_branch_response.status_code == 201

    users_response = client.get("/api/admin/users")
    assert users_response.status_code == 200


def test_manager_can_manage_officers_and_open_qr(client):
    with client.application.app_context():
        branch = Branch(code="KUR", name="Kurunegala", is_active=True)
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
        json={"email": "manager@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    officers_page = client.get("/manager/officers")
    assert officers_page.status_code == 200

    create_response = client.post(
        "/manager/officers",
        data={
            "employee_id": "OFF005",
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
        assert created.branch_id is not None
        assert created.role == UserRole.LOBBY_OFFICER

    qr_response = client.get("/manager/qr")
    assert qr_response.status_code == 200


def test_officer_can_view_dashboard_and_queue(client):
    with client.application.app_context():
        branch = Branch(code="MAT", name="Matara", is_active=True)
        db.session.add(branch)
        db.session.commit()
        officer = User(
            employee_id="OFF010",
            full_name="Officer Matara",
            email="officer2@example.com",
            role=UserRole.LOBBY_OFFICER,
            branch_id=branch.id,
        )
        officer.set_password("secret123")
        db.session.add(officer)
        db.session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={"email": "officer2@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    dashboard_response = client.get("/officer/dashboard")
    assert dashboard_response.status_code == 200

    queue_response = client.get("/officer/queue")
    assert queue_response.status_code == 200

    history_response = client.get("/officer/history")
    assert history_response.status_code == 200


def test_manager_cannot_access_admin_routes(client):
    with client.application.app_context():
        branch = Branch(code="BAD", name="Badulla", is_active=True)
        db.session.add(branch)
        db.session.commit()
        manager = User(
            employee_id="MGR010",
            full_name="Manager Badulla",
            email="manager2@example.com",
            role=UserRole.BRANCH_MANAGER,
            branch_id=branch.id,
        )
        manager.set_password("secret123")
        db.session.add(manager)
        db.session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={"email": "manager2@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200

    admin_dashboard_response = client.get("/admin/dashboard")
    assert admin_dashboard_response.status_code == 403

    admin_branches_response = client.get("/api/admin/branches")
    assert admin_branches_response.status_code == 403
