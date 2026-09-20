"""Robustheitstests fuer das Live-Scoring ((82), Kandidat 5).

Deckt bisher ungetestete Pfade ab: LiveMatchManager (leer, kaputtes
Events-JSON, Update scheduled->live, Abschluss mit Punkteberechnung,
Tipp-Verteilung/Top-Tipps) sowie die /live-Routen inkl. Rollen-Schutz
(anonym, Spieler, Admin) und Fehlerfaelle (unbekanntes Spiel -> 404/400).
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from live_scoring import LiveMatchManager, live_manager
from models import Match, Prediction


@pytest.fixture
def live_match(db, competition, teams):
    """Spiel im Live-Zustand (2:1, 34. Minute, mit Tor-Event)."""
    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(hours=1),
              status="live", is_live=True, home_score=2, away_score=1,
              minute=34, events=json.dumps([{"kind": "gf", "team": "home"}]))
    db.session.add(m)
    db.session.commit()
    return m


def test_leere_liv_liste_ohne_spiele(app, gepinnt_lives):
    with app.app_context():
        assert live_manager.get_live_matches() == []


def test_format_vertraegt_kaputtes_events_json_und_leere_werte(app, db, competition, teams):
    """Kaputtes JSON und None-Werte duerfen die Live-Ansicht nicht killen."""
    m = Match(competition_id=competition.id, matchday=2,
              home_team_id=teams[2].id, away_team_id=teams[3].id,
              kickoff=datetime.now(timezone.utc), status="live",
              is_live=True, events="{niemals json")
    db.session.add(m)
    db.session.commit()
    with app.app_context():
        daten = live_manager._format_live_match(m)
    assert daten["events"] == []
    assert daten["score"] == {"home": 0, "away": 0}
    assert daten["minute"] == 0


def test_update_scheduled_wird_live(app, db, match):
    with app.app_context():
        assert live_manager.update_match(match.id, 1, 0, minute=12,
                                         events=[{"kind": "gf"}]) is True
        frisch = db.session.get(Match, match.id)
        assert frisch.status == "live" and frisch.is_live is True
        assert json.loads(frisch.events) == [{"kind": "gf"}]
        assert live_manager.update_match(999999, 0, 0) is False


def test_abschluss_berechnet_punkte(app, db, user, live_match):
    """2:1 exakt getippt -> nach dem Abschluss 4 Punkte (Joker verdoppelt)."""
    pred = Prediction(user_id=user.id, match_id=live_match.id,
                      home_tip=2, away_tip=1, joker=False)
    db.session.add(pred)
    db.session.commit()
    mgr = LiveMatchManager()
    with app.app_context():
        assert mgr.finish_match(live_match.id, 2, 1) is True
        frisch = db.session.get(Match, live_match.id)
        neu = db.session.get(Prediction, pred.id)
        assert frisch.status == "finished" and frisch.minute == 90
        assert neu.points == 4
        assert mgr.finish_match(999999, 0, 0) is False


def test_statistik_verteilung_und_top_tipps(app, db, competition, teams, user, live_match):
    from models import User as U
    andere = U(username="zweituser", email="zweit@example.com")
    andere.set_password("geheim123")
    db.session.add(andere)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=live_match.id,
                              home_tip=2, away_tip=1, joker=False))
    db.session.add(Prediction(user_id=andere.id, match_id=live_match.id,
                              home_tip=1, away_tip=1, joker=False))
    db.session.commit()
    mgr = LiveMatchManager()
    with app.app_context():
        stats = mgr.get_match_stats(live_match.id)
        assert stats["predictions_count"] == 2
        assert stats["tip_distribution"] == {"1": 1, "X": 1, "2": 0}
        # Spiel laeuft noch -> keine Top-Tipps
        assert stats["top_tips"] == []
        mgr.finish_match(live_match.id, 2, 1)
        top = mgr.get_match_stats(live_match.id)["top_tips"]
        assert top and top[0]["user"] == user.username and top[0]["points"] == 4
        assert mgr.get_match_stats(999999) is None


# ------------------------------------------------------------ Routen

@pytest.fixture
def gepinnt_lives(app, competition, monkeypatch):
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)


def test_route_liv_matches_oeffentlich(app, client, gepinnt_lives):
    resp = client.get("/live/matches")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0


def test_route_detail_unbekannt_404(app, client):
    assert client.get("/live/match/999999").status_code == 404


def test_route_eigene_tipps_rollen(app, client, db, user, live_match, gepinnt_lives):
    anonym = client.get("/live/user/predictions")
    assert anonym.status_code == 302          # login_required
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    db.session.add(Prediction(user_id=user.id, match_id=live_match.id,
                              home_tip=2, away_tip=1, joker=False))
    db.session.commit()
    resp = client.get("/live/user/predictions")
    daten = resp.get_json()["predictions"]
    assert len(daten) == 1
    assert daten[0]["my_tip"] == "2:1"
    assert daten[0]["current_score"] == "2:1"


def test_route_admin_update_rollen_und_fehler(app, client, db, user, admin_user, live_match):
    assert client.post("/live/admin/update/%d" % live_match.id).status_code == 302
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    assert client.post("/live/admin/update/%d" % live_match.id).status_code == 403
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    ok = client.post("/live/admin/update/%d" % live_match.id,
                   data={"home_score": "3", "away_score": "1", "minute": "55"})
    assert ok.status_code == 200 and ok.get_json()["success"] is True
    with app.app_context():
        frisch = db.session.get(Match, live_match.id)
        assert frisch.home_score == 3 and frisch.minute == 55
    assert client.post("/live/admin/update/999999",
                     data={"home_score": "1", "away_score": "0"}).status_code == 400


def test_route_admin_abschluss(app, client, db, user, admin_user, live_match):
    """Abschluss per Route berechnet Punkte direkt mit (Form-POST ohne
    JSON-Header darf nicht mehr mit 415 platzen — (82)-Fix get_json(silent))."""
    db.session.add(Prediction(user_id=user.id, match_id=live_match.id,
                              home_tip=2, away_tip=1, joker=False))
    db.session.commit()
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    assert client.post("/live/admin/finish/999999",
                       data={"home_score": "0", "away_score": "0"}).status_code == 400
    ok = client.post("/live/admin/finish/%d" % live_match.id,
                     data={"home_score": "2", "away_score": "1"})
    assert ok.status_code == 200
    pred = db.session.get(Prediction, Prediction.query.filter_by(
        user_id=user.id, match_id=live_match.id).first().id)
    assert pred.points == 4
