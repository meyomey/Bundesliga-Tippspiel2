"""Security-bezogene Tests."""
import pytest

from app import create_app
from config import TestConfig
from scoring import set_setting


class InsecureProductionConfig(TestConfig):
    TESTING = False
    REQUIRE_SECURE_CONFIG = True
    SECRET_KEY = TestConfig.DEFAULT_SECRET_KEY
    ADMIN_PASSWORD = 'admin123'


class SecureProductionConfig(TestConfig):
    TESTING = False
    REQUIRE_SECURE_CONFIG = True
    SECRET_KEY = 'x' * 64
    ADMIN_PASSWORD = 'very-secure-admin-password'


def test_insecure_production_config_is_blocked():
    with pytest.raises(RuntimeError):
        create_app(InsecureProductionConfig)


def test_secure_production_config_starts():
    app = create_app(SecureProductionConfig)
    assert app is not None


def test_telegram_webhook_rejects_wrong_secret(client, db):
    set_setting('telegram_webhook_secret', 'secret123')
    resp = client.post('/telegram/webhook/wrong', json={'message': {'chat': {'id': 1}, 'text': '/hilfe'}})
    assert resp.status_code == 403


def test_telegram_webhook_accepts_correct_secret(client, db, monkeypatch):
    set_setting('telegram_webhook_secret', 'secret123')
    monkeypatch.setattr('telegram_bot.send_telegram_message', lambda chat_id, text: True)
    resp = client.post('/telegram/webhook/secret123', json={'message': {'chat': {'id': 1}, 'text': '/hilfe'}})
    assert resp.status_code == 200
