"""Tests Nachrichtenkanal-Sichtbarkeit + CallMeBot-Schalter ((116)).

Nutzerfragen: „Kann man sehen wer welchen Nachrichtenkanal eingerichtet
hat?", „Es soll einstellbar sein, ob man CallMeBot nutzt oder nicht",
„Am Ende soll noch ein Link zum Tippspiel in der Nachricht erscheinen,
denke am besten zur Rangliste".

1) Admin-Spielerverwaltung zeigt je Spieler 4 Kanal-Badges (E-Mail/Push/
   Telegram/CallMeBot) — farbig = eingerichtet UND im Profil aktiv.
2) Der Profil-Schalter „WhatsApp (CallMeBot)" (notify_whatsapp) gilt
   JETZT auch fuer die Spieltags-Sieger-Ansage ((115) hatte ihn noch
   ignoriert; Digest/Test-Nachricht pruefen ihn schon).
3) Die Sieger-Ansage endet mit dem Ranglisten-Link (Basis-URL aus den
   Settings; ohne Basis-URL entfaellt die Zeile).
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import Match, MatchdayWinner, Prediction


@pytest.fixture
def lage(db, competition, teams, user):
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
    db.session.commit()
    return {"comp": competition, "user": user}


def test_ansage_enthaelt_ranglisten_link(app, db, lage):
    """Mit Basis-URL endet der Text auf …/tabelle."""
    from scoring import set_setting
    from matchday_announce import sieger_text
    with app.app_context():
        set_setting("public_base_url", "https://tipp.example")
        text = sieger_text(5, lage["comp"].id)
    assert text.endswith("https://tipp.example/tabelle")
    assert "📊 Rangliste:" in text


def test_ansage_ohne_basis_url_ohne_link(app, db, lage):
    from scoring import set_setting
    from matchday_announce import sieger_text
    with app.app_context():
        set_setting("public_base_url", "")
        text = sieger_text(5, lage["comp"].id)
    assert "Rangliste:" not in text   # relativer Pfad waere in WhatsApp tot


def test_callmebot_aus_heisst_kein_versand(app, db, lage, monkeypatch):
    """DER Schalter: notify_whatsapp=False -> keine Ansage an den User."""
    import matchday_announce
    from matchday_announce import sende_sieger_an_whatsapp
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    lage["user"].notify_whatsapp = False
    db.session.commit()
    gesendet_an = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: gesendet_an.append(phone) or True)
    g, f = sende_sieger_an_whatsapp(5, lage["comp"].id)
    assert (g, f) == (0, 0)
    assert gesendet_an == []


def test_callmebot_an_versendet(app, db, lage, monkeypatch):
    import matchday_announce
    from matchday_announce import sende_sieger_an_whatsapp
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    lage["user"].notify_whatsapp = True
    db.session.commit()
    gesendet_an = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: gesendet_an.append(phone) or True)
    g, f = sende_sieger_an_whatsapp(5, lage["comp"].id)
    assert (g, f) == (1, 0)


def test_admin_sieht_kanal_badges(client, app, db, admin_user, lage,
                                  monkeypatch):
    """Spielerverwaltung: 4 Badges, aktive CallMeBot-Zelle markiert 'on'."""
    monkeypatch.setitem(app.config, "COMPETITION", lage["comp"].code)
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    body = client.get("/admin/users").get_data(as_text=True)
    assert "kanal-badges" in body
    assert 'title="WhatsApp/CallMeBot aktiv"' in body
    assert 'title="E-Mail aktiv"' in body
    # Push/Telegram nicht eingerichtet -> aus-Markierung existiert
    assert 'title="Push aus"' in body or 'title="Telegram aus"' in body


def test_profil_label_nennt_callmebot(client, app, db, user):
    """Profil: der Schalter heisst „WhatsApp (CallMeBot)“ — klar, WAS da
    ein-/ausgeschaltet wird."""
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    body = client.get("/profil").get_data(as_text=True)
    assert "WhatsApp (CallMeBot)" in body
