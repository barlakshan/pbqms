import pytest

from app import create_app


def test_production_requires_strong_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")
