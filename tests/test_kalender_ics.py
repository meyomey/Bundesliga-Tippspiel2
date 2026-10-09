"""Tests fuer den ICS-Kalender-Feed ((91)): /kalender/<token>.ics.

Der Feed ist oeffentlich (Kalender-Apps koennen keine Session-Logins),
aber token-geschuetzt und enthaelt KEINE Tipps — nur Paarungen, Anstoss-
zeiten (UTC) und Endergebnisse.
"""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Match, Team, User
from schema_migrations import _migration_user_calendar_token


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def test_feed_oeffentlich_mit_token(client, app, db, user, competition,
                                    teams, monkeypatch):
    """Anonym + Token -> 200, text/calendar, VCALENDAR mit UTC-Anstoss."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    user.calendar_token = "a" * 32
    db.session.add(Match(competition_id=competition.id, matchday=9,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime(2026, 10, 3, 16, 30,
                                          tzinfo=timezone.utc),
                         status="scheduled"))
    db.session.commit()

    resp = client.get(f"/kalender/{user.calendar_token}.ics")
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    raw = resp.get_data()
    assert b"BEGIN:VCALENDAR" in raw
    assert b"\r\n" in raw                       # RFC 5545: CRLF-Zeilenden
    assert b"DTSTART:20261003T163000Z" in raw   # naive-UTC-Konvention
    assert b"UID:match-" in raw
    assert b"X-WR-CALNAME:Wulmstoerper Tipprunde" in raw


def test_feed_404_bei_falschem_oder_kurzem_token(client, db, user):
    user.calendar_token = "b" * 32
    db.session.commit()
    assert client.get("/kalender/" + "c" * 32 + ".ics").status_code == 404
    assert client.get("/kalender/zu-kurz.ics").status_code == 404


def test_feed_zeigt_ergebnis_und_ort(client, app, db, user, competition,
                                     teams, monkeypatch):
    """Fertiges Spiel: Summary mit Endstand, LOCATION mit Stadion."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    user.calendar_token = "d" * 32
    db.session.add(Match(competition_id=competition.id, matchday=2,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime.now(timezone.utc) - timedelta(days=7),
                         status="finished", home_score=2, away_score=1,
                         venue="Volksparkstadion"))
    db.session.commit()
    resp = client.get(f"/kalender/{user.calendar_token}.ics")
    body = resp.get_data(as_text=True)
    assert "2:1" in body
    assert "LOCATION:Volksparkstadion" in body


def test_feed_escaped_sonderzeichen(client, app, db, user, competition,
                                    monkeypatch):
    """Komma im Teamnamen wird RFC-5545-gerecht als \\, Escaped."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    user.calendar_token = "e" * 32
    heim = Team(name="Test, United", short_name="T,U", logo="t.png")
    gast = Team(name="Gast FC", short_name="GFC", logo="g.png")
    db.session.add_all([heim, gast])
    db.session.commit()
    db.session.add(Match(competition_id=competition.id, matchday=1,
                         home_team_id=heim.id, away_team_id=gast.id,
                         kickoff=datetime.now(timezone.utc) + timedelta(days=3),
                         status="scheduled"))
    db.session.commit()
    resp = client.get(f"/kalender/{user.calendar_token}.ics")
    body = resp.get_data(as_text=True)
    assert "T\\,U - GFC (ST 1)" in body  # Komma RFC-5545-escapet


def test_profil_zeigt_kalender_link_und_token_lazy(client, db, user):
    """Profilbesuch legt fehlenden Token an; Card + Link sichtbar."""
    assert user.calendar_token is None
    _login(client, user.email, "testpass123")
    resp = client.get("/profil")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Kalender-Abo" in body
    db.session.expire(user)
    token = user.calendar_token
    assert token and len(token) == 32
    assert f"/kalender/{token}.ics" in body


def test_token_neu_generieren_macht_altlink_tot(client, db, user):
    """Regenerate-POST: neuer Token, alter Feed-Link -> 404, neuer -> 200."""
    user.calendar_token = "f" * 32
    db.session.commit()
    _login(client, user.email, "testpass123")
    resp = client.post("/profil", data={"calendar_regenerate": "1"},
                       follow_redirects=True)
    assert resp.status_code == 200
    db.session.expire(user)
    neu = user.calendar_token
    assert neu and neu != "f" * 32
    assert client.get("/kalender/" + "f" * 32 + ".ics").status_code == 404
    assert client.get(f"/kalender/{neu}.ics").status_code == 200


def test_migration_backfillt_token(app, db, user):
    """Migration setzt fehlende Spalte voraus und fuellt Token nach."""
    user.calendar_token = None
    db.session.commit()
    meldung = _migration_user_calendar_token()
    db.session.expire_all()
    frisch = db.session.get(User, user.id)
    assert frisch.calendar_token and len(frisch.calendar_token) == 32
    assert "nachgefuellt" in meldung
