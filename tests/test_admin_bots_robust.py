"""Robustheitstests fuer die Admin-Bot-Routen ((82), Kandidat 5).

Deckt die bisher ungetesteten Pfade ab: Rollenschutz aller /admin/bots-*
Routen, Toggle-Verhalten inkl. Setting, unbekannte Bot-IDs, Reset-Loeschung,
Bot-Anlage (erfolgreich/Duplikat/unbekannt) sowie tip-all ohne aktive Bots.
Muster: EIN Client, Rollenwechsel ausschliesslich ueber /auth/logout
(Doppel-Login short-circuitet — siehe Runde 82, Telegram/Live-Fund).
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import Match, Prediction, User
from scoring import get_setting


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


@pytest.fixture
def bot_user(db):
    bot = User(username="ProBot", email="probot@bot.local", is_admin=False)
    bot.set_password("botgeheim123")
    db.session.add(bot)
    db.session.commit()
    return bot


@pytest.fixture
def kommendes_spiel(db, competition, teams):
    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=5),
              status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture
def gepinnt(app, competition, monkeypatch):
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)


def test_admin_bots_rollenschutz(app, client, db, user, admin_user, gepinnt):
    """Anonym → 302 zum Login, Spieler → 403, Admin → 200."""
    assert client.get("/admin/bots").status_code == 302
    _login(client, user.email, "testpass123")
    assert client.get("/admin/bots").status_code == 403
    client.get("/auth/logout")
    _login(client, admin_user.email, "admin123")
    assert client.get("/admin/bots").status_code == 200


def test_bot_toggle_setting_und_unbekannt(app, client, db, admin_user, gepinnt):
    """Toggle schreibt bot_active_<Bot> als '1'/'0', unbekannter Bot faellt
    auf die Fehlermeldung (nie still falsch)."""
    _login(client, admin_user.email, "admin123")
    client.post("/admin/bots/toggle", data={"bot_name": "ProBot"})
    assert get_setting("bot_active_ProBot", None) == "1"
    client.post("/admin/bots/toggle", data={"bot_name": "ProBot"})
    assert get_setting("bot_active_ProBot", None) == "0"
    resp = client.post("/admin/bots/toggle", data={"bot_name": "NichtsBot"},
                       follow_redirects=True)
    assert "Unbekannter Bot" in resp.get_data(as_text=True)


def test_bot_tip_single_unbekannter_bot(app, client, db, admin_user, gepinnt):
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/bots/tip-single", data={"bot_id": "999999"},
                       follow_redirects=True)
    assert "Bot nicht gefunden" in resp.get_data(as_text=True)


def test_bot_tip_single_echter_bot_tippt(app, client, db, admin_user, bot_user,
                                         kommendes_spiel, gepinnt):
    """Echter Bot-User + offenes Spiel → Tipps erscheinen in der DB."""
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/bots/tip-single",
                       data={"bot_id": str(bot_user.id)},
                       follow_redirects=True)
    text = resp.get_data(as_text=True)
    assert ("Tipps für Spieltag" in text) or ("Fehler" in text)
    anzahl = Prediction.query.filter_by(user_id=bot_user.id,
                                        match_id=kommendes_spiel.id).count()
    assert anzahl >= 1


def test_bot_tip_all_ohne_aktive_bots(app, client, db, admin_user, kommendes_spiel, gepinnt):
    """Kein Bot aktiv → Info-Flash, keine Predictions, kein Crash."""
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/bots/tip-all", data={"matchday": "1"},
                       follow_redirects=True)
    text = resp.get_data(as_text=True)
    assert "Keine neuen Tipps" in text
    assert Prediction.query.filter_by(match_id=kommendes_spiel.id).count() == 0


def test_bot_reset_loescht_tipps_des_spieltags(app, client, db, admin_user,
                                               bot_user, kommendes_spiel, gepinnt):
    """Reset wirft genau die Bot-Tipps des Spieltags weg; unbekannter Bot
    wird abgewiesen."""
    db.session.add(Prediction(user_id=bot_user.id,
                              match_id=kommendes_spiel.id,
                              home_tip=1, away_tip=0, joker=False))
    db.session.commit()
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/bots/reset",
                       data={"bot_id": str(bot_user.id), "matchday": "1"},
                       follow_redirects=True)
    assert "gelöscht" in resp.get_data(as_text=True)
    assert Prediction.query.filter_by(user_id=bot_user.id).count() == 0
    resp = client.post("/admin/bots/reset", data={"bot_id": "999999"},
                       follow_redirects=True)
    assert "Bot nicht gefunden" in resp.get_data(as_text=True)


def test_bot_create_anlegen_duplikat_unbekannt(app, client, db, admin_user, gepinnt):
    """create legt Bot-User an (@bot.local, Schalter auf 0), Duplikat und
    unbekannter Name werden sauber abgefangen."""
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/bots/create", data={"bot_name": "ExpertBot"},
                       follow_redirects=True)
    assert "angelegt" in resp.get_data(as_text=True)
    bot = User.query.filter_by(username="ExpertBot").first()
    assert bot is not None and bot.email == "expertbot@bot.local"
    assert get_setting("bot_active_ExpertBot", None) == "0"
    resp = client.post("/admin/bots/create", data={"bot_name": "ExpertBot"},
                       follow_redirects=True)
    assert "existiert bereits" in resp.get_data(as_text=True)
    resp = client.post("/admin/bots/create", data={"bot_name": "HerrX"},
                       follow_redirects=True)
    assert "Unbekannter Bot" in resp.get_data(as_text=True)
