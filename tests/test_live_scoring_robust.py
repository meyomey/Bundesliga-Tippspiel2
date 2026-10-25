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


def test_remis_getippt_anderes_remis_ist_tendenz_2punkte_158():
    """(158) Regel-Anker: Tipp 1:1 bei Ergebnis 0:0 = Richtige Tendenz
    (gleiche Differenz 0, aber kein 'echter' Tordiff-Fall, da Unent-
    schieden) -> die TENDENZ-Punktzahl (Konfig: 2), nie 3 oder 0.
    Nutzer-Regelseite: 'Auch Tipp 1:1, Ergebnis 2:2 zählt als Tendenz.'"""
    from types import SimpleNamespace
    from scoring import calculate_points_for_score, classify_prediction_live

    tipp = SimpleNamespace(home_tip=1, away_tip=1, joker=False)
    # Live (laufendes Spiel, 0:0) UND Final-Zweig muessen identisch liegen:
    assert classify_prediction_live(tipp, SimpleNamespace(
        status="live", home_score=0, away_score=0)) == "tendency"
    assert calculate_points_for_score(tipp, 0, 0) == 2

    # Gegenprobe: echtes Remis exakt (1:1 bei 1:1) = 4, Torsieg-Diff bleibt
    # Sieg-Statistik vorbehalten (Regelseite: 'nur bei Siegen').
    assert calculate_points_for_score(SimpleNamespace(
        home_tip=1, away_tip=1, joker=False), 1, 1) == 4
    assert classify_prediction_live(SimpleNamespace(
        home_tip=2, away_tip=0, joker=False), SimpleNamespace(
        status="live", home_score=0, away_score=0)) == "wrong"


def test_zweiter_joker_antwort_nennt_das_spiel_163(app, client, db, user,
                                                  competition, teams):
    """(163) Der Joker-Konflikt nennt konkret das Spiel, in dem der Joker
    steckt - statt einer austauschbaren Floskel (Nutzer-Feedback
    "Netzwerkfehler ist nicht aussagekraeftig")."""
    from datetime import datetime, timedelta, timezone as tz
    from models import Match, Prediction
    from scoring import set_setting
    set_setting("current_season", "2026/27")
    now = datetime.now(tz.utc)
    a = Match(competition_id=competition.id, matchday=8,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=now - timedelta(hours=2), status="live",
              home_score=1, away_score=0)
    b = Match(competition_id=competition.id, matchday=8,
              home_team_id=teams[2].id, away_team_id=teams[3].id,
              kickoff=now + timedelta(hours=3), status="scheduled")
    db.session.add_all([a, b]); db.session.flush()
    db.session.add(Prediction(user_id=user.id, match_id=a.id,
                              home_tip=1, away_tip=0, joker=True, points=0))
    db.session.commit()

    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = competition.code
    r = client.post(f"/api/tip/{b.id}",
                    json={"home_tip": 2, "away_tip": 1, "joker": True})
    assert r.status_code == 400
    body = r.get_json()
    assert body["ok"] is False
    assert "steckt im bereits gestarteten Spiel" in body["error"]
    assert f"{teams[0].short_name}-{teams[1].short_name}" in body["error"]


def test_tip_fehler_anzeigen_sind_spezifisch_163():
    """(163) Beide Tipp-Formulare zeigen die echte Ursache: Server-JSON-
    Fehler als Text, Session/429/Serverfehler je eigener Hinweis statt
    pauschalem "Netzwerkfehler"/"Fehler beim Speichern"."""
    md = open("static/js/match_detail.js", encoding="utf-8").read()
    assert "res.status === 429" in md
    assert "res.status === 401" in md
    assert "res.status >= 500" in md
    assert "Sitzung abgelaufen" in md
    assert "'❌ Netzwerkfehler'" not in md
    qt = open("static/js/quick_tip.js", encoding="utf-8").read()
    assert "res.status === 429" in qt
    assert "data.error" in qt
    assert "'Fehler beim Speichern'" not in qt


def test_embed_shell_hat_csrf_meta_164():
    """(164) Die Embed-Shell (Popup) traegt das csrf-token-Meta - sonst
    schickt jedes Match-Detail-Speichern aus dem Popup einen LEEREN
    CSRF-Header und scheitert immer mit 400 (Nutzer-Case 25.10.)."""
    emb = open("templates/base_embed.html", encoding="utf-8").read()
    assert 'name="csrf-token"' in emb
    md = open("static/js/match_detail.js", encoding="utf-8").read()
    # Text-erst-Lesen + CSRF-Erkennung statt pauschaler 400-Meldung
    assert "await res.text()" in md
    assert "/csrf/i" in md
    assert "Sicherheitstoken abgelaufen" in md
    qt = open("static/js/quick_tip.js", encoding="utf-8").read()
    assert "await res.text()" in qt
    assert "/csrf/i" in qt


def test_csrf_token_ohne_zeitlimit_164(app):
    """(164) Der CSRF-Token hat kein 1h-Zeitlimit mehr: Tippseiten stehen
    beim Countdown stundenlang offen; der Standard-WTF_CSRF_TIME_LIMIT
    (3600) liess das Speichern dann mit 400 sterben."""
    from config import Config
    assert Config.WTF_CSRF_TIME_LIMIT is None


def test_joker_klick_erklaert_speichern_164():
    """(164) Der Joker-Klick meldet konkret 'Joker aktiv – bitte
    speichern' statt des generischen 'Änderungen ungespeichert'."""
    md = open("static/js/match_detail.js", encoding="utf-8").read()
    assert "Joker aktiv – bitte speichern" in md
    assert "Joker entfernt – bitte speichern" in md
