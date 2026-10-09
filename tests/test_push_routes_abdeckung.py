"""Test-Runde 3 ((90)): Push-Routen & Helpers (vorher 35 % Coverage)."""
import json
import sys
import types
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Match, Prediction

from push_routes import (
    _remind_for_match,
    _remind_upcoming,
    _send_push_to_users,
    push_reminder_job,
)


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def _fake_pywebpush(monkeypatch, fail_message=None):
    """pywebpush ersetzen (Import passiert lazy in der Hilfsfunktion)."""
    calls = []

    class FakeWebPushException(Exception):
        pass

    def _webpush(subscription_info, data, vapid_private_key, vapid_claims):
        calls.append({"sub": subscription_info, "data": data,
                      "claims": vapid_claims})
        if fail_message is not None:
            raise FakeWebPushException(fail_message)

    fake = types.SimpleNamespace(webpush=_webpush,
                                 WebPushException=FakeWebPushException)
    monkeypatch.setitem(sys.modules, "pywebpush", fake)
    return calls


def test_subscribe_valide_daten(client, db, user):
    """POST /push/subscribe speichert Abo-JSON, 201 + ok."""
    _login(client, user.email, "testpass123")
    abo = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
    resp = client.post("/push/subscribe", data=json.dumps(abo),
                       content_type="application/json")
    assert resp.status_code == 201
    assert resp.get_json() == {"ok": True}
    db.session.expire(user)
    assert json.loads(user.push_subscription)["endpoint"] == abo["endpoint"]


def test_subscribe_ohne_daten_400(client, db, user):
    _login(client, user.email, "testpass123")
    resp = client.post("/push/subscribe")
    assert resp.status_code == 400


def test_unsubscribe_raeumt_abo_weg(client, db, user):
    user.push_subscription = json.dumps({"endpoint": "https://x"})
    db.session.commit()
    _login(client, user.email, "testpass123")
    resp = client.post("/push/unsubscribe")
    assert resp.status_code == 200
    db.session.expire(user)
    assert user.push_subscription is None


def test_vapid_key_503_ohne_konfig_200_mit(client, db, app, monkeypatch):
    # Bewusst via monkeypatch: die App-Config ist session-scoped und wird von
    # anderen Tests evtl. mit VAPID-Keys angereichert — nicht drauf verlassen.
    monkeypatch.setitem(app.config, "VAPID_PUBLIC_KEY", "")
    assert client.get("/push/vapid-public-key").status_code == 503
    monkeypatch.setitem(app.config, "VAPID_PUBLIC_KEY", "PUB-KEY-123")
    resp = client.get("/push/vapid-public-key")
    assert resp.status_code == 200
    assert resp.get_json()["publicKey"] == "PUB-KEY-123"


def test_push_test_admin_only(client, db, user, admin_user):
    """Nicht-Admin -> 403; Admin bekommt sent/failed-Statistik."""
    _login(client, user.email, "testpass123")
    assert client.post("/push/test").status_code == 403
    client.get("/auth/logout")
    _login(client, admin_user.email, "admin123")
    resp = client.post("/push/test")
    assert resp.status_code == 200
    assert resp.get_json() == {"sent": 0, "failed": 0}


def test_send_reminder_ohne_abonnenten(client, db, admin_user):
    _login(client, admin_user.email, "admin123")
    resp = client.post("/push/send-reminder", data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json() == {"sent": 0, "failed": 0}


def test_send_push_erfolgsfall(app, db, user, monkeypatch):
    """Mit VAPID-Keys + Fake-Modul: webpush aufgerufen, sent=1."""
    calls = _fake_pywebpush(monkeypatch)
    monkeypatch.setitem(app.config, "VAPID_PUBLIC_KEY", "PUB")
    monkeypatch.setitem(app.config, "VAPID_PRIVATE_KEY", "PRIV")
    user.push_subscription = json.dumps({"endpoint": "https://push.example/1"})
    db.session.commit()
    # Direkt aufrufen: der app-Fixture-Context ist aktiv; ein neuer
    # app_context wuerde eine NEUE DB-Session aufmachen (Flask-SQLAlchemy 3.x).
    sent, failed = _send_push_to_users([user], {"title": "t"})
    assert (sent, failed) == (1, 0)
    assert len(calls) == 1
    assert "sub" in calls[0]["claims"]


def test_send_push_410_raeumt_abo_auf(app, db, user, monkeypatch):
    """Gone-Antwort (410) loescht das tote Abo und zaehlt failed."""
    _fake_pywebpush(monkeypatch, fail_message="HTTP 410 Gone")
    monkeypatch.setitem(app.config, "VAPID_PUBLIC_KEY", "PUB")
    monkeypatch.setitem(app.config, "VAPID_PRIVATE_KEY", "PRIV")
    user.push_subscription = json.dumps({"endpoint": "https://push.example/2"})
    db.session.commit()
    sent, failed = _send_push_to_users([user], {"title": "t"})
    assert (sent, failed) == (0, 1)
    db.session.expire(user)
    assert user.push_subscription is None


def test_remind_for_match_nur_ohne_tipp(app, db, user, competition, teams,
                                        monkeypatch):
    """Nur Spieler ohne Tipp bekommen die Erinnerung; Payload passt."""
    calls = _fake_pywebpush(monkeypatch)
    monkeypatch.setitem(app.config, "VAPID_PUBLIC_KEY", "PUB")
    monkeypatch.setitem(app.config, "VAPID_PRIVATE_KEY", "PRIV")
    m = Match(competition_id=competition.id, matchday=7,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=2),
              status="scheduled")
    db.session.add(m)
    user.push_subscription = json.dumps({"endpoint": "https://push.example/3"})
    db.session.commit()

    sent, failed = _remind_for_match(m)
    assert (sent, failed) == (1, 0)
    payload = json.loads(calls[0]["data"])
    assert "Tipp-Erinnerung" in payload["title"]
    assert payload["url"] == f"/schedule/{m.matchday}"

    # Jetzt tippt der User — zweite Erinnerung findet niemanden vor.
    db.session.add(Prediction(user_id=user.id, match_id=m.id,
                              home_tip=1, away_tip=1, joker=False))
    db.session.commit()
    sent2, failed2 = _remind_for_match(m)
    assert (sent2, failed2) == (0, 0)


def test_remind_upcoming_fenster(app, db, user, competition, teams, monkeypatch):
    """Spiel im 65-Minuten-Fenster wird gefunden und erinnert."""
    calls = _fake_pywebpush(monkeypatch)
    monkeypatch.setitem(app.config, "VAPID_PUBLIC_KEY", "PUB")
    monkeypatch.setitem(app.config, "VAPID_PRIVATE_KEY", "PRIV")
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    db.session.add(Match(competition_id=competition.id, matchday=3,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime.now(timezone.utc) + timedelta(minutes=30),
                         status="scheduled"))
    user.push_subscription = json.dumps({"endpoint": "https://push.example/4"})
    db.session.commit()
    sent, failed = _remind_upcoming()
    assert (sent, failed) == (1, 0)


def test_push_reminder_job_laueft_leer(app):
    """Scheduler-Job ohne passende Spiele: kein Crash."""
    push_reminder_job(app)
