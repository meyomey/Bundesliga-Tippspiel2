"""Tests Sieger-Ansage-Schalter ((118)) — Praezisierung des (117)-Masters.

Klarstellung des Nutzers: der Schalter in den Einstellungen soll NUR die
automatische WhatsApp-Verteilung der Spieltags-Sieger-Ansage steuern —
Erinnerungen, Test-Nachrichten und alles andere bleiben unangetastet
aktiv. Deshalb: keine globale Sperre im Versand-Weg (Rueckbau (117)),
stattdessen ein Gate im Cron-Hook der Ansage — aus = Spieltage werden
als erledigt markiert (kein Nachholen alter Ansagen beim spaeteren
Einschalten), ohne zu senden.
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import Match, MatchdayWinner, Prediction

from scoring import set_setting
from whatsapp import send_whatsapp_message


@pytest.fixture
def sieger_lage(db, competition, teams, user):
    m1 = Match(competition_id=competition.id, matchday=5,
               home_team_id=teams[0].id, away_team_id=teams[1].id,
               kickoff=datetime.now(timezone.utc) - timedelta(hours=3),
               status="finished", home_score=2, away_score=1)
    m2 = Match(competition_id=competition.id, matchday=5,
               home_team_id=teams[2].id, away_team_id=teams[3].id,
               kickoff=datetime.now(timezone.utc) - timedelta(hours=3),
               status="finished", home_score=0, away_score=0)
    db.session.add_all([m1, m2])
    db.session.flush()
    db.session.add(Prediction(user_id=user.id, match_id=m1.id,
                              home_tip=2, away_tip=1, points=3))
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=5,
                                  user_id=user.id, points=13, exact_count=2,
                                  is_shared=False, season="2026/27"))
    user.whatsapp_phone = "+491701111111"
    user.whatsapp_apikey = "k1"
    user.notify_whatsapp = True
    db.session.commit()
    return {"comp": competition, "user": user}


# ---- Der Schalter wirkt NUR auf die Ansage-Automatik ---------------------

def test_schalter_aus_ansage_markiert_ohne_versand(app, db, sieger_lage,
                                                   monkeypatch):
    import matchday_announce
    from matchday_announce import pruefe_und_sende_offene_sieger
    from scoring import get_setting
    monkeypatch.setitem(app.config, "COMPETITION", sieger_lage["comp"].code)
    with app.app_context():
        set_setting("whatsapp_enabled", False)
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    aufgerufe = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: aufgerufe.append(phone) or True)
    res = pruefe_und_sende_offene_sieger()
    assert res["gesendet"] == [] and aufgerufe == []
    # als erledigt markiert (sonst holt das spaetere Einschalten alte nach)
    assert get_setting("md_winner_sent_{}_5".format(sieger_lage["comp"].id))


def test_schalter_aus_dann_an_kein_nachholen(app, db, sieger_lage,
                                             monkeypatch):
    import matchday_announce
    from matchday_announce import pruefe_und_sende_offene_sieger
    monkeypatch.setitem(app.config, "COMPETITION", sieger_lage["comp"].code)
    with app.app_context():
        set_setting("whatsapp_enabled", False)
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: True)
    pruefe_und_sende_offene_sieger()
    with app.app_context():
        set_setting("whatsapp_enabled", True)
    aufgerufe = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: aufgerufe.append(phone) or True)
    res = pruefe_und_sende_offene_sieger()
    assert res["gesendet"] == [] and aufgerufe == []   # alte bleibt alt


def test_schalter_an_ansage_sendet(app, db, sieger_lage, monkeypatch):
    import matchday_announce
    from matchday_announce import pruefe_und_sende_offene_sieger
    monkeypatch.setitem(app.config, "COMPETITION", sieger_lage["comp"].code)
    with app.app_context():
        set_setting("whatsapp_enabled", True)
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    aufgerufe = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: aufgerufe.append(phone) or True)
    res = pruefe_und_sende_offene_sieger()
    assert res["gesendet"] == [5] and len(aufgerufe) == 1


# ---- Sonst bleibt ALLES aktiv (Kern der Nutzerpraezisierung) -------------

def test_schalter_aus_whatsapp_versand_selbst_laueft_weiter(app, db,
                                                            monkeypatch):
    """Der Versand-Weg ist bewusst UNGEBREMST: Erinnerungen/Test-Nachrichten
    (die alle ueber send_whatsapp_message laufen) funktionieren auch bei
    ausgeschalteter Sieger-Ansage-Automatik."""
    with app.app_context():
        set_setting("whatsapp_enabled", False)
    aufgerufe = []
    monkeypatch.setattr("whatsapp.requests.get",
                        lambda url, timeout=10: aufgerufe.append(url) or type(
                            "R", (), {"status_code": 200, "text": "Message queued"})())
    assert send_whatsapp_message("+491701111111", "k1", "Erinnerung") is True
    assert len(aufgerufe) == 1 and "callmebot" in aufgerufe[0]


def test_profil_schalter_gilt_weiter(app, db, sieger_lage, monkeypatch):
    """Unveraendert: das Mitglied regelt im Profil, OB es CallMeBot kriegt."""
    import matchday_announce
    from matchday_announce import sende_sieger_an_whatsapp
    with app.app_context():
        set_setting("whatsapp_enabled", True)
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    sieger_lage["user"].notify_whatsapp = False
    db.session.commit()
    gesendet_an = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: gesendet_an.append(phone) or True)
    g, f = sende_sieger_an_whatsapp(5, sieger_lage["comp"].id)
    assert (g, f) == (0, 0) and gesendet_an == []


# ---- Einstellungs-UX: Sektionen zu, wenn fertig ((117), unveraendert) ----

def _login_admin(client, admin_user):
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)


def test_einstellungen_sektionen_eingeklappt_wenn_fertig(client, app, db,
                                                         admin_user,
                                                         competition,
                                                         monkeypatch):
    import re
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    with app.app_context():
        set_setting("contact_email", "chef@wulmstorf.example")
        set_setting("recht_anbieter", "Vorname Nachname")
        set_setting("reminders_enabled", True)
        set_setting("whatsapp_enabled", True)
    _login_admin(client, admin_user)
    body = client.get("/admin/settings").get_data(as_text=True)

    def sektion_offen(text, emoji):
        m = re.search(r'<details class="section-group"([^>]*)>\s*<summary>[^<]*'
                      + emoji, text)
        assert m, f"Sektion {emoji} fehlt"
        return "open" in m.group(1)

    assert not sektion_offen(body, "👥 Registrierung")
    assert not sektion_offen(body, "🔔 Tipp-Erinnerungen")
    assert "🏆 Sieger-Ansage (WhatsApp)" in body
    assert not sektion_offen(body, "🏆 Sieger-Ansage")


def test_einstellungen_offen_wenn_etwas_fehlt(client, app, db, admin_user,
                                              competition, monkeypatch):
    import re
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    with app.app_context():
        set_setting("contact_email", "")
        set_setting("recht_anbieter", "")
    _login_admin(client, admin_user)
    body = client.get("/admin/settings").get_data(as_text=True)
    m = re.search(r'<details class="section-group"([^>]*)>\s*<summary>[^<]*👥',
                  body)
    assert m and "open" in m.group(1)
    assert "Nicht konfiguriert" in body
