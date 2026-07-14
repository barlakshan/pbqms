import pytest

from app import create_app


def test_sms_provider_accepts_textlk_alias(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "textlk")
    monkeypatch.setenv("TEXTLK_API_TOKEN", "test-token")

    app = create_app("testing")

    assert app.config["SMS_PROVIDER"] == "textlk"


def test_sms_provider_accepts_textlk_url(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "https://app.text.lk/api/http/sms/send")
    monkeypatch.setenv("TEXTLK_API_TOKEN", "test-token")

    app = create_app("testing")

    assert app.config["SMS_PROVIDER"] == "textlk"
