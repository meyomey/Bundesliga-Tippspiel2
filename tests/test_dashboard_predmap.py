"""Tests fuer den Dashboard-N+1-Fix ((90)): pred_map statt Query je Zeile."""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Match, Prediction


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def _spiel(db, competition, teams, spieltag, stunden_bis):
    m = Match(competition_id=competition.id, matchday=spieltag,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=stunden_bis),
              status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def test_routes_guards_predmap():
    """Selbstbeweis: Lambda weg, pred_map in Route UND Template."""
    route = open('routes_main.py', encoding='utf-8').read()
    tpl = open('templates/dashboard.html', encoding='utf-8').read()
    assert 'get_user_prediction=lambda' not in route
    assert 'pred_map=pred_map' in route
    assert 'get_user_prediction' not in tpl
    assert 'pred_map.get(m.id)' in tpl


def test_dashboard_zeigt_tipp_aus_predmap(client, app, db, user,
                                          competition, teams, monkeypatch):
    """Tipp am kommenden Spiel erscheint genau wie vorher (2:1-Muster)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    m = _spiel(db, competition, teams, 5, 24)
    db.session.add(Prediction(user_id=user.id, match_id=m.id,
                              home_tip=3, away_tip=1, joker=False))
    db.session.commit()
    _login(client, user.email, "testpass123")
    resp = client.get("/dashboard")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert '3 : 1' in body


def test_dashboard_ohne_tipps_laefert_200(client, app, db, user,
                                          competition, teams, monkeypatch):
    """Kein Tipp -> leeres pred_map.get -> 'vs'-Zweig, kein Crash."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _login(client, user.email, "testpass123")
    resp = client.get("/dashboard")
    assert resp.status_code == 200
