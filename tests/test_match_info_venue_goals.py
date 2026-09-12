"""Match-Infos mit echtem Mehrwert (12.09.2026):

- Stadion (venue): football-data Free liefert es im Match-Payload - jetzt
  persistiert (Migration-Spalte) und im Match-Detail sichtbar; ein laufender
  Sync ohne venue-Feld loescht Bestandsdaten NICHT.
- Goal-Boost: Torschuetzen (Minute, Elfmeter-/Eigentor-Marker, Vorlage) aus
  dem optionalen API-Football-Free-Key in Match.events (JSON, kind='gf').
  Ohne Token kein Request; Fremdformate in events bleiben unangetastet;
  eigener 10-Minuten-/8-pro-Tag-Budgetwaechter.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

import minute_boost
from models import Competition, Match, Team
import sync


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _fd_match(mid, home, away, venue=None, status="SCHEDULED",
              kickoff="2026-09-05T13:30:00Z"):
    m = {"id": mid, "utcDate": kickoff, "matchday": 3, "status": status,
         "homeTeam": {"id": 10000 + mid, "name": home, "shortName": home[:3].upper(), "tla": home[:3].upper()},
         "awayTeam": {"id": 20000 + mid, "name": away, "shortName": away[:3].upper(), "tla": away[:3].upper()},
         "score": {"fullTime": {"home": None, "away": None}}}
    if venue:
        m["venue"] = venue
    return m


# --------------------------------------------------------------- Venue ----
def test_sync_stores_venue_and_keeps_it_on_later_updates(db, app):
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    data = {"matches": [_fd_match(9101, "FC TestArenA", "SV TestGegner", venue="Allianz Arena")]}
    with app.app_context():
        res = sync._process_football_data(data, comp.id, source="test")
        assert res["ok"]
        m = Match.query.filter_by(external_id="fd:9101").one()
        assert m.venue == "Allianz Arena"
        assert res["venues"] == 1 and res["venues_map"] == 0
        assert "Stadion: 1 aus Feed, 0 aus Festdaten" in res["msg"]
        # 2. Sync OHNE venue-Feld: Bestand bleibt stehen (API liefert nicht immer)
        data2 = {"matches": [_fd_match(9101, "FC TestArenA", "SV TestGegner")]}
        res2 = sync._process_football_data(data2, comp.id, source="test")
        assert Match.query.filter_by(external_id="fd:9101").one().venue == "Allianz Arena"
        assert res2["venues"] == 0 and res2["venues_map"] == 0  # Testteams nicht auf der Karte
        assert "Stadion: 0 aus Feed, 0 aus Festdaten" in res2["msg"]


# ------------------------------------------------------------ Goal-Boost ----
@pytest.fixture
def goal_env(db, app, monkeypatch):
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    bay = Team.query.filter_by(short_name="FCB").first() or Team(name="FC Bayern München", short_name="FCB", logo="x.png")
    bvb = Team.query.filter_by(short_name="BVB").first() or Team(name="Borussia Dortmund", short_name="BVB", logo="x.png")
    db.session.add_all([t for t in (bay, bvb) if t.id is None])
    db.session.commit()
    m = Match(competition_id=comp.id, matchday=3, home_team_id=bay.id, away_team_id=bvb.id,
              kickoff=datetime.now(timezone.utc) - timedelta(hours=3),
              status="finished", home_score=2, away_score=1)
    db.session.add(m)
    db.session.commit()

    calls = {"n": 0, "payload": None}

    def fake_get(url, headers=None, timeout=None, **kw):
        calls["n"] += 1
        assert "fixtures?league=181" in url
        return _Resp(calls["payload"] or {"response": [], "errors": {}})

    monkeypatch.setattr(minute_boost.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    from scoring import set_setting
    set_setting("apifootball_token", "TESTKEY")
    minute_boost._GOAL_STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    yield m, calls
    minute_boost._GOAL_STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    set_setting("apifootball_token", "")


def _af_goals_fixture(m, status="FT"):
    # API-Football-Struktur: fixture / teams / goals GESCHWISTERT auf Top-Level
    return {"response": [{
        "fixture": {"id": 555,
                    "date": m.kickoff.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "status": {"short": status, "elapsed": 90}},
        "teams": {"home": {"id": 10, "name": "Bayern München"},
                  "away": {"id": 20, "name": "Borussia Dortmund"}},
        "goals": [
            {"team": {"id": 10}, "player": {"name": "Harry Kane"},
             "assist": {"name": "Jamal Musiala"}, "type": "Goal",
             "time": {"elapsed": 23}},
            {"team": {"id": 20}, "player": {"name": "Nick Woltemade"}, "type": "Penalty",
             "time": {"elapsed": 45, "additional": 2}},
            {"team": {"id": 10}, "player": {"name": "Nico Schlotterbeck"}, "type": "Own Goal",
             "time": {"elapsed": 70}},
        ],
    }], "errors": {}}


def test_goal_boost_writes_sorted_events(app, db, goal_env):
    m, calls = goal_env
    calls["payload"] = _af_goals_fixture(m)
    with app.app_context():
        res = minute_boost.boost_goal_scorers_from_apifootball()
        assert res["updated"] == 1 and calls["n"] == 1
        dbm = Match.query.get(m.id)
        rows = json.loads(dbm.events)
        assert [r["min"] for r in rows] == [23, 45, 70]
        assert rows[0]["player"] == "Harry Kane" and rows[0]["assist"] == "Jamal Musiala"
        assert rows[0]["team"] == "home" and rows[0]["kind"] == "gf"
        assert rows[1]["penalty"] is True and rows[1]["extra"] == 2 and rows[1]["team"] == "away"
        assert rows[2]["own_goal"] is True
        # Budget-Gate: zweiter Aufruf sofort -> gedrosselt, kein zweiter HTTP-Call
        res2 = minute_boost.boost_goal_scorers_from_apifootball()
        assert res2.get("throttled") and calls["n"] == 1


def test_goal_boost_skips_without_token_and_keeps_foreign_events(app, db, goal_env, monkeypatch):
    m, calls = goal_env
    from scoring import set_setting
    set_setting("apifootball_token", "")
    with app.app_context():
        res = minute_boost.boost_goal_scorers_from_apifootball()
        assert res.get("skipped") == "no-token" and calls["n"] == 0
    # Fremdformat (live_scoring-Legat) wird nie ueberschrieben
    set_setting("apifootball_token", "TESTKEY")
    m.events = json.dumps([{"type": "card", "minute": 12}])
    db.session.commit()
    calls["payload"] = _af_goals_fixture(m)
    with app.app_context():
        res = minute_boost.boost_goal_scorers_from_apifootball()
        assert res["updated"] == 0 and calls["n"] == 0   # nicht einmal als Kandidat gelistet
        assert json.loads(Match.query.get(m.id).events)[0]["type"] == "card"


def test_goal_boost_ignores_not_finished(app, db, goal_env):
    m, calls = goal_env
    calls["payload"] = _af_goals_fixture(m, status="2H")   # live statt fertig -> ignorieren
    with app.app_context():
        res = minute_boost.boost_goal_scorers_from_apifootball()
        assert res["updated"] == 0 and m.events in (None, "")


# ------------------------------------------------------- Detail-Ansicht ----
def test_match_detail_renders_venue_and_goal_scorers(client, db, user, competition, teams, app, monkeypatch):
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    competition.is_active = True
    m = Match(competition_id=competition.id, matchday=3,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(hours=3),
              status="finished", home_score=2, away_score=1,
              venue="Allianz Arena",
              events=json.dumps([
                  {"kind": "gf", "min": 23, "extra": None, "team": "home",
                   "player": "Harry Kane", "assist": "Jamal Musiala",
                   "penalty": False, "own_goal": False},
                  {"kind": "gf", "min": 45, "extra": 2, "team": "away",
                   "player": "Nick Woltemade", "assist": None,
                   "penalty": True, "own_goal": False},
              ], ensure_ascii=False))
    db.session.add(m)
    db.session.commit()
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get(f"/match/{m.id}", follow_redirects=True).get_data(as_text=True)
    assert "📍 Allianz Arena" in html
    # ...und die Pille ist ein Google-Maps-Link (schluessellos, neuer Tab)
    assert "maps/search/?api=1&amp;query=Allianz%20Arena" in html
    assert 'rel="noopener noreferrer"' in html and 'target="_blank"' in html
    # Plus Kompass-Piktogramm fuer Direkt-Routing (Variante b, 12.09.)
    assert "🧭" in html and "maps/dir/?api=1&amp;destination=Allianz%20Arena" in html
    assert "Torschützen" in html
    assert "Harry Kane" in html and "Vorlage: Jamal Musiala" in html
    assert "45'+2" in html and "(Elfmeter)" in html
