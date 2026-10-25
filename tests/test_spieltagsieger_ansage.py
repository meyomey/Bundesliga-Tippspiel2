"""Tests Spieltags-Sieger-Ansage ((115)).

Nutzerwunsch: nach Abschluss aller Spiele den Spieltagssieger (+ Top 3
der Gesamtrangliste) in die WhatsApp-Gruppe posten. CallMeBot kann keine
Gruppen — deshalb: automatischer Einzelversand per Cron (privater Chat)
+ Kopier-Text im Admin fuer die Gruppe. Datenquelle ist die vorhandene
matchday_winners-Tabelle (Punkte/Exaktheit/geteilter Sieg schon drin).
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import Match, MatchdayWinner, Prediction, User


@pytest.fixture(autouse=True)
def _pin_comp(monkeypatch, competition):
    """(162) wie in Produktion: der aktive Wettbewerb ist gepinnt — sonst
    sieht recompute_matchday_winners hier den BL1-Conftest-Bestand statt
    der Test-Comp und die (159)-Heilung "tut nichts" (Audit-Befund).
    WICHTIG: scoring importiert den Namen modul-top-level, deshalb BOTH
    Bindungen patchen (competition_helpers UND scoring)."""
    import competition_helpers
    import scoring
    monkeypatch.setattr(competition_helpers, "get_active_competition",
                        lambda: competition)
    monkeypatch.setattr(scoring, "get_active_competition",
                        lambda: competition)


def _fertig(db, competition, teams, user):
    """Spieltag 5 komplett (2 Spiele), Spieltag 6 laeuft noch."""
    for hs, as_ in ((2, 1), (0, 0)):
        db.session.add(Match(competition_id=competition.id, matchday=5,
                             home_team_id=teams[0].id, away_team_id=teams[1].id,
                             kickoff=datetime.now(timezone.utc) - timedelta(hours=3),
                             status="finished", home_score=hs, away_score=as_))
    db.session.add(Match(competition_id=competition.id, matchday=6,
                         home_team_id=teams[1].id, away_team_id=teams[0].id,
                         kickoff=datetime.now(timezone.utc) - timedelta(minutes=10),
                         status="live", home_score=1, away_score=0))
    # Tipps MIT gespeicherten Punkten (recompute_matchday_winners summiert sie)
    for u, pts in ((user, 6), None, None):
        pass
    db.session.flush()
    user_pts = [(user, 6)]
    return user_pts


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
    live = Match(competition_id=competition.id, matchday=6,
                 home_team_id=teams[1].id, away_team_id=teams[0].id,
                 kickoff=datetime.now(timezone.utc) - timedelta(minutes=10),
                 status="live", home_score=1, away_score=0)
    db.session.add_all([m1, m2, live])
    db.session.flush()

    u2 = User(username="zweit", email="zweit@example.com")
    u2.set_password("testpass123")
    u3 = User(username="dritt", email="dritt@example.com")
    u3.set_password("testpass123")
    db.session.add_all([u2, u3])
    db.session.flush()

    # Gespeicherte Punkte: user gewinnt MD5 klar (recompute summiert sie)
    db.session.add_all([
        Prediction(user_id=user.id, match_id=m1.id, home_tip=2, away_tip=1, points=3),
        Prediction(user_id=user.id, match_id=m2.id, home_tip=0, away_tip=0, points=3),
        Prediction(user_id=u2.id, match_id=m1.id, home_tip=2, away_tip=0, points=1),
        Prediction(user_id=u2.id, match_id=m2.id, home_tip=1, away_tip=1, points=0),
        Prediction(user_id=u3.id, match_id=m1.id, home_tip=0, away_tip=2, points=0),
    ])
    # (159) absichtlich FALSCH hinterlegte Alt-Zeile (falscher User, falsche
    # Punkte - wie ein Teilstand-Sieger): sieger_text MUSS neu rechnen und
    # den echten Sieger ansagen, nicht die Stale-Zeile einfrieren.
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=5,
                                  user_id=u2.id, points=13, exact_count=0,
                                  is_shared=False, season="2026/27"))
    # (162) wie in Produktion: aktuelle Saison ist gesetzt (sonst targetiert
    # die (159)-Heilung die falsche Season und Stale-Zeilen ueberleben).
    from scoring import set_setting
    set_setting("current_season", "2026/27")
    # user mit WhatsApp, u2 ohne, u3 als Bot mit WA-Konfig
    user.whatsapp_phone = "+491701111111"
    user.whatsapp_apikey = "k1"
    u3.email = "dritt@bot.local"
    u3.whatsapp_phone = "+491703333333"
    u3.whatsapp_apikey = "k3"
    db.session.commit()
    return {"comp": competition, "user": user, "u2": u2, "u3": u3}


def test_text_enthaelt_sieger_und_top3(app, db, lage):
    from matchday_announce import sieger_text
    text = sieger_text(5, lage["comp"].id)
    assert text and "Spieltag 5 ist durch" in text
    # (159) Heilung: die falsche Alt-Zeile (u2, 13 Pkt.) wurde neu
    # berechnet - echter Sieger ist `user` mit 3+3=6 Punkten.
    assert f"Spieltagssieger: {lage['user'].username}" in text
    assert "6 Pkt." in text
    assert "13 Pkt." not in text
    assert "Top 3 der Gesamtrangliste" in text
    assert "1. " in text


def test_unvollstaendiger_spieltag_nicht_gelistet(app, db, lage):
    from matchday_announce import abgeschlossene_spieltage
    assert abgeschlossene_spieltage(lage["comp"].id) == [5]


def test_versand_nur_an_konfigurierte_ohne_bots(app, db, lage, monkeypatch):
    import matchday_announce
    from matchday_announce import sende_sieger_an_whatsapp
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    gesendet_an = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: gesendet_an.append(phone) or True)
    g, f = sende_sieger_an_whatsapp(5, lage["comp"].id)
    assert (g, f) == (1, 0)
    assert gesendet_an == ["+491701111111"]


def test_cron_sendet_einmalig_und_markiert(app, db, lage, monkeypatch):
    import matchday_announce
    from matchday_announce import pruefe_und_sende_offene_sieger
    from scoring import get_setting
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    aufrufe = []
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: aufrufe.append(phone) or True)

    res = pruefe_und_sende_offene_sieger()
    assert res["gesendet"] == [5]
    n_erster = len(aufrufe)
    assert n_erster == 1
    assert get_setting("md_winner_sent_{}_5".format(lage["comp"].id))

    res2 = pruefe_und_sende_offene_sieger()
    assert res2["gesendet"] == []
    assert len(aufrufe) == n_erster  # kein doppelter Versand


def test_sendefehler_wird_wiederholt(app, db, lage, monkeypatch):
    import matchday_announce
    from matchday_announce import pruefe_und_sende_offene_sieger
    monkeypatch.setattr(matchday_announce.time, "sleep", lambda s: None)
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: False)  # CallMeBot down
    res = pruefe_und_sende_offene_sieger()
    assert res["gesendet"] == []       # nicht markiert
    from scoring import get_setting
    assert not get_setting("md_winner_sent_{}_5".format(lage["comp"].id))


def test_admin_sync_zeigt_gruppentext(client, app, db, admin_user, lage,
                                      monkeypatch):
    monkeypatch.setitem(app.config, "COMPETITION", lage["comp"].code)
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    body = client.get("/admin/sync").get_data(as_text=True)
    assert "Spieltags-Sieger" in body
    assert "mdWinnerText" in body
    assert lage["user"].username in body


def test_cron_verdrahtung_ruft_ansage(app, db, lage, monkeypatch, capsys):
    import cron_jobs
    import utils
    aufgerufe = []
    monkeypatch.setattr(utils, "sync_results",
                        lambda: {"ok": True, "msg": "sync ok"})
    monkeypatch.setattr("matchday_announce.pruefe_und_sende_offene_sieger",
                        lambda: aufgerufe.append(1) or {"gesendet": [5]})
    cron_jobs.run_sync()
    assert aufgerufe == [1]
    assert "SPIELTAGSSIEGER" in capsys.readouterr().out
