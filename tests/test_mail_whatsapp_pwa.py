"""Tests fuer Mail-/WhatsApp-/PWA-Helfer."""
from mail_helpers import (
    generate_reset_token, verify_reset_token, apply_mail_settings,
    send_email, send_password_reset, apply_vapid_settings,
)
from scoring import set_setting
from whatsapp import send_whatsapp_message, send_whatsapp_test


def test_reset_token_roundtrip(app, db, user):
    with app.app_context():
        token = generate_reset_token(user.id)
        resolved = verify_reset_token(token)
        assert resolved.id == user.id
        assert verify_reset_token('invalid-token') is None


def test_send_email_and_password_reset(monkeypatch, app, user):
    sent = []

    def fake_send(msg):
        sent.append(msg)

    monkeypatch.setattr('mail_helpers.mail.send', fake_send)
    with app.app_context():
        assert send_email('Betreff', [user.email], 'Body') is True
        send_password_reset(user)
    assert len(sent) == 2
    assert sent[0].subject == 'Betreff'


def test_apply_mail_and_vapid_settings(app, db):
    with app.app_context():
        set_setting('mail_server', 'smtp.example.test')
        set_setting('mail_port', 2525)
        set_setting('mail_username', 'user')
        set_setting('mail_password', 'pw')
        set_setting('mail_default_sender', 'noreply@example.test')
        set_setting('mail_use_tls', False)
        set_setting('mail_use_ssl', True)
        set_setting('vapid_public', 'pub')
        set_setting('vapid_private', 'priv')
        apply_mail_settings()
        apply_vapid_settings()
        assert app.config['MAIL_SERVER'] == 'smtp.example.test'
        assert app.config['MAIL_PORT'] == 2525
        assert app.config['MAIL_USE_SSL'] is True
        assert app.config['VAPID_PUBLIC_KEY'] == 'pub'
        assert app.config['VAPID_PRIVATE_KEY'] == 'priv'


def test_whatsapp_send_success_and_test(monkeypatch, app, user):
    class Resp:
        status_code = 200
        text = 'Message queued'

    calls = []
    def fake_get(url, timeout=10):
        calls.append(url)
        return Resp()

    monkeypatch.setattr('whatsapp.requests.get', fake_get)
    with app.app_context():
        assert send_whatsapp_message('+49 170 1234567', '123', 'Hallo') is True
        user.whatsapp_phone = '+491701234567'
        user.whatsapp_apikey = '123'
        assert send_whatsapp_test(user) is True
    assert len(calls) == 2


def test_pwa_routes(client):
    assert client.get('/offline').status_code == 200
    ping = client.get('/api/ping')
    assert ping.status_code == 200
    assert ping.get_json()['ok'] is True
