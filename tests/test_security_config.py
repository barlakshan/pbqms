import pytest

from app import create_app


def test_production_requires_strong_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_root_redirects_to_login_page_when_not_authenticated():
    app = create_app("testing")
    client = app.test_client()

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/api/auth/login-page")
