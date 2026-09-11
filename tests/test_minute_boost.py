"""Minute-Boost ueber API-Football (11.09.2026): echte Live-Minute, 0 EUR.

Wichtigste Eigenschaften: ohne Token komplett inaktiv; 90s-/Budget-Drosselung
(Tagesbudget 90 von 100); keine Beruehrung fremder Spiele; HT setzt die
verbindliche Pause; FT raeumt die Uhr. Die Uhr-Semantik (feed=ohne "≈",
Struktur=mit "≈") bleibt unveraendert.
"""
from datetime import datetime, timedelta, timezone

import pytest

from models import Competition, Match, Team
from routes_api import live_clock_for

import minute_boost


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _af_item(m, short="1H", elapsed=34, hs=2, as_=1,
              home="Bayern München", away="Borussia Dortmund"):
    date = m.kickoff.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return {"fixture": {"id": 4711, "date": date,
                        "status": {"long": "First Half", "short": short, "elapsed": elapsed}},
            "league": {"id": 181},
            "teams": {"home": {"name": home}, "away": {"name": away}},
            "goals": {"home": hs, "away": as_}}


@pytest.fixture
def boost_env(db, monkeypatch):
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    bay = Team(name="FC Bayern München", short_name="FCB", logo="x.png")
    bvb = Team(name="Borussia Dortmund", short_name="BVB", logo="x.png")
    db.session.add_all([bay, bvb])
    db.session.commit()
    m = Match(competition_id=comp.id, matchday=3, home_team_id=bay.id, away_team_id=bvb.id,
              kickoff=datetime.now(timezone.utc) - timedelta(minutes=34), status="scheduled")
    db.session.add(m)
    db.session.commit()

    calls = {"n": 0, "payload": {"response": [], "errors": {}}}

    def fake_get(url, headers=None, timeout=None, **kw):
        calls["n"] += 1
        calls["headers"] = headers
        return _Resp(calls["payload"])

    monkeypatch.setattr(minute_boost.requests, "get", fake_get)
    from scoring import set_setting
    set_setting("apifootball_token", "TESTKEY")
    minute_boost._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    yield m, calls
    minute_boost._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})


def _set_payload(calls, item):
    calls["payload"] = {"response": [item], "errors": {}}


def test_live_minute_written_without_approx_sign(boost_env):
    m, calls = boost_env
    _set_payload(calls, _af_item(m, "1H", 34, 2, 1))
    r = minute_boost.boost_minutes_from_apifootball()
    assert r["updated"] == 1 and calls["headers"]["x-apisports-key"] == "TESTKEY"
    dbm = Match.query.get(m.id)
    assert (dbm.status, dbm.home_score, dbm.away_score, dbm.minute, dbm.live_phase) \
        == ("live", 2, 1, 34, "IN_PLAY")
    lc = live_clock_for(dbm)
    assert lc["minute"] == 34 and lc["derived"] is False   # echtes Feed-Datum -> ohne "≈"


def test_halftime_sets_authoritative_pause(boost_env):
    m, calls = boost_env
    _set_payload(calls, _af_item(m, "HT", 45, 2, 1))
    assert minute_boost.boost_minutes_from_apifootball()["updated"] == 1
    lc = live_clock_for(Match.query.get(m.id))
    assert lc["halftime"] == "feed" and lc["minute"] is None


def test_finished_clears_clock_and_locks_result(boost_env):
    m, calls = boost_env
    m.status, m.home_score, m.away_score, m.minute, m.live_phase = "live", 2, 1, 80, "IN_PLAY"
    from extensions import db as _db
    _db.session.commit()
    _set_payload(calls, _af_item(m, "FT", 92, 3, 1))
    assert minute_boost.boost_minutes_from_apifootball()["updated"] == 1
    dbm = Match.query.get(m.id)
    assert dbm.status == "finished" and (dbm.home_score, dbm.away_score) == (3, 1)
    assert dbm.minute is None and dbm.live_phase is None


def test_no_token_means_zero_http(boost_env):
    from scoring import set_setting
    set_setting("apifootball_token", "")
    _m, calls = boost_env
    r = minute_boost.boost_minutes_from_apifootball()
    assert r["skipped"] == "no-token" and calls["n"] == 0


def test_throttle_and_daily_budget(boost_env, monkeypatch):
    m, calls = boost_env
    _set_payload(calls, _af_item(m, "1H", 10, 1, 0))
    assert minute_boost.boost_minutes_from_apifootball()["updated"] == 1
    assert minute_boost.boost_minutes_from_apifootball().get("throttled")
    assert calls["n"] == 1                                  # zweiter Aufruf: kein HTTP
    monkeypatch.setattr(minute_boost, "_DAILY_BUDGET", 1)   # Budget aufgebraucht
    minute_boost._STATE_FALLBACK["last"] = 0.0              # Intervall ignorieren
    r = minute_boost.boost_minutes_from_apifootball()
    assert r.get("budget") == "day-exhausted" and calls["n"] == 1


def test_foreign_or_ambiguous_payload_is_ignored(boost_env):
    m, calls = boost_env
    _set_payload(calls, _af_item(m, "1H", 20, 1, 1, home="Arsenal", away="Chelsea"))
    assert minute_boost.boost_minutes_from_apifootball()["updated"] == 0
    dbm = Match.query.get(m.id)
    assert dbm.status == "scheduled" and dbm.minute is None
    calls["payload"] = {"response": [], "errors": {"rate limit": "reached"}}
    minute_boost._STATE_FALLBACK["last"] = 0.0
    assert minute_boost.boost_minutes_from_apifootball().get("api_errors") is True
