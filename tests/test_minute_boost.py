"""Minute-Boost ueber API-Football (11.09.2026): echte Live-Minute, 0 EUR.

Wichtigste Eigenschaften: ohne Token komplett inaktiv; 90s-/Budget-Drosselung
(Tagesbudget 90 von 100); keine Beruehrung fremder Spiele; HT setzt die
verbindliche Pause; FT raeumt die Uhr. Die Uhr-Semantik (feed=ohne "≈",
Struktur=mit "≈") bleibt unveraendert.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
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
    dbm = db.session.get(Match, m.id)
    assert (dbm.status, dbm.home_score, dbm.away_score, dbm.minute, dbm.live_phase) \
        == ("live", 2, 1, 34, "IN_PLAY")
    assert dbm.live_synced_at is not None  # (105) Frische-Guard-Stempel
    lc = live_clock_for(dbm)
    assert lc["minute"] == 34 and lc["derived"] is False   # echtes Feed-Datum -> ohne "≈"


def test_halftime_sets_authoritative_pause(boost_env):
    m, calls = boost_env
    _set_payload(calls, _af_item(m, "HT", 45, 2, 1))
    assert minute_boost.boost_minutes_from_apifootball()["updated"] == 1
    lc = live_clock_for(db.session.get(Match, m.id))
    assert lc["halftime"] == "feed" and lc["minute"] is None


def test_finished_clears_clock_and_locks_result(boost_env):
    m, calls = boost_env
    m.status, m.home_score, m.away_score, m.minute, m.live_phase = "live", 2, 1, 80, "IN_PLAY"
    from extensions import db as _db
    _db.session.commit()
    _set_payload(calls, _af_item(m, "FT", 92, 3, 1))
    assert minute_boost.boost_minutes_from_apifootball()["updated"] == 1
    dbm = db.session.get(Match, m.id)
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
    dbm = db.session.get(Match, m.id)
    assert dbm.status == "scheduled" and dbm.minute is None
    calls["payload"] = {"response": [], "errors": {"rate limit": "reached"}}
    minute_boost._STATE_FALLBACK["last"] = 0.0
    assert minute_boost.boost_minutes_from_apifootball().get("api_errors") is True


# --------------------------- (133) Goal-Boost 2.0: Tore/Karten/Wechsel ----
# Vor (133) las der Parser `item["goals"]` (nur das Score-Objekt {home,away})
# statt `events[]` - der Boost hat deshalb NIE etwas gespeichert. Jetzt:
# Tore (mit Vorlage) + Karten + Auswechslungen, Events-Nachladen je Spiel.


@pytest.fixture
def goal_env(db, app, monkeypatch):
    """Wie boost_env, aber: Spiel beendet + fake_get mit URL-Dispatch."""
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
    m = Match(competition_id=comp.id, matchday=7, home_team_id=bay.id,
              away_team_id=bvb.id,
              kickoff=datetime.now(timezone.utc) - timedelta(hours=2),
              status="finished", home_score=2, away_score=1)
    db.session.add(m)
    db.session.commit()

    calls = {"urls": [], "discovery": None, "events": None}

    def fake_get(url, headers=None, timeout=None, **kw):
        calls["urls"].append(url)
        if "/fixtures/events" in url:
            return _Resp(calls["events"] or {"response": [], "errors": {}})
        return _Resp(calls["discovery"] or {"response": [], "errors": {}})

    monkeypatch.setattr(minute_boost.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    from scoring import set_setting
    set_setting("apifootball_token", "TESTKEY")
    minute_boost._GOAL_STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    cache_obj = minute_boost._gate_cache()
    if cache_obj is not None:
        # Full-Suite: fruehere Tests (test_match_info) hinterlassen Gate-State
        # im Cache -> sonst Drossel-Fehlschlag (< 600 s).
        cache_obj.set(minute_boost._GOAL_GATE_KEY,
                      {"day": "", "count": 0, "last": 0.0}, ttl=3600)
    yield m, calls
    minute_boost._GOAL_STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})


def _ft_item(m, mid=4711, with_events=True):
    item = {"fixture": {"id": mid, "date": m.kickoff.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                        "status": {"short": "FT"}},
            "league": {"id": 181},
            "teams": {"home": {"id": 10, "name": "Bayern München"},
                      "away": {"id": 11, "name": "Borussia Dortmund"}},
            "goals": {"home": 2, "away": 1}}
    if with_events:
        item["events"] = [
            {"time": {"elapsed": 12, "additional": None},
             "team": {"id": 10}, "player": {"name": "M. Musiala"},
             "assist": {"name": "H. Kane"}, "type": "Goal", "detail": "Normal Goal"},
            {"time": {"elapsed": 39, "additional": None},
             "team": {"id": 10}, "player": {"name": "H. Kane"},
             "assist": {"name": None}, "type": "Goal", "detail": "Penalty"},
            {"time": {"elapsed": 45, "additional": None},
             "team": {"id": 10}, "player": {"name": "H. Kane"},
             "assist": {"name": None}, "type": "Goal", "detail": "Missed Penalty"},
            {"time": {"elapsed": 55, "additional": None},
             "team": {"id": 10}, "player": {"name": "E. Can"},
             "assist": {"name": None}, "type": "Card", "detail": "Yellow Card"},
            {"time": {"elapsed": 70, "additional": None},
             "team": {"id": 11}, "player": {"name": "N. Schlotterbeck"},
             "assist": {"name": None}, "type": "Card", "detail": "Second Yellow card"},
            {"time": {"elapsed": 80, "additional": None},
             "team": {"id": 11}, "player": {"name": "E. Can"},
             "assist": {"name": None}, "type": "Card", "detail": "Red Card"},
            {"time": {"elapsed": 60, "additional": None},
             "team": {"id": 10}, "player": {"name": "X. Yz"},
             "assist": {"name": None}, "type": "Var", "detail": "Goal cancelled"},
            {"time": {"elapsed": 75, "additional": 2},
             "team": {"id": 10}, "player": {"name": "T. Müller"},
             "assist": {"name": "J. Musiala"}, "type": "Subst",
             "detail": "Substitution 2"},
            {"time": {"elapsed": 90, "additional": None},
             "team": {"id": 11}, "player": {"name": "N. Schlotterbeck"},
             "assist": {"name": None}, "type": "Goal", "detail": "Own Goal"},
        ]
    return item


def test_goal_boost_liest_events_inkl_karten_wechsel_133(goal_env):
    m, calls = goal_env
    calls["discovery"] = {"response": [_ft_item(m)], "errors": {}}
    r = minute_boost.boost_goal_scorers_from_apifootball()
    assert r["updated"] == 1
    rows = json.loads(m.events)
    gf = [x for x in rows if x["kind"] == "gf"]
    cards = [x for x in rows if x.get("type") == "card"]
    subs = [x for x in rows if x["kind"] == "sub"]
    assert len(gf) == 3 and len(cards) == 3 and len(subs) == 1
    assert not any(x.get("player") == "X. Yz" for x in rows)      # VAR raus
    assert not any(x.get("min") == 45 for x in gf)                # verschossener Elfer raus
    assert gf[0]["player"] == "M. Musiala" and gf[0]["assist"] == "H. Kane"
    assert gf[1]["penalty"] is True and gf[2]["own_goal"] is True
    assert gf[2]["team"] == "away"
    assert {c["card"] for c in cards} == {"gelb", "yellow_red", "rot"}
    assert cards[0]["team"] == "home" and cards[1]["team"] == "away"
    assert subs[0]["player"] == "T. Müller" and subs[0]["assist"] == "J. Musiala"
    assert subs[0]["extra"] == 2 and subs[0]["team"] == "home"
    # zweiter Lauf: Events-JSON vorhanden -> Gate sperrt, kein zweiter Request
    r2 = minute_boost.boost_goal_scorers_from_apifootball()
    assert r2["updated"] == 0 and len(calls["urls"]) == 1


def test_goal_boost_ladt_events_nach_133(goal_env):
    """Liste-Query ohne events[] -> einmal /fixtures/events je Spiel."""
    m, calls = goal_env
    calls["discovery"] = {"response": [_ft_item(m, with_events=False)], "errors": {}}
    calls["events"] = {"response": [
        {"time": {"elapsed": 5, "additional": None}, "team": {"id": 10},
         "player": {"name": "L. Goretzka"}, "assist": {"name": None},
         "type": "Goal", "detail": "Normal Goal"}], "errors": {}}
    r = minute_boost.boost_goal_scorers_from_apifootball()
    assert r["updated"] == 1
    assert any("/fixtures/events?fixture=4711" in u for u in calls["urls"])
    assert len(calls["urls"]) == 2
    rows = json.loads(m.events)
    assert rows[0]["player"] == "L. Goretzka" and rows[0]["team"] == "home"


def test_goal_boost_ohne_token_inaktiv_133(goal_env):
    from scoring import set_setting
    set_setting("apifootball_token", "")
    m, calls = goal_env
    calls["discovery"] = {"response": [_ft_item(m)], "errors": {}}
    r = minute_boost.boost_goal_scorers_from_apifootball()
    assert r["skipped"] == "no-token" and calls["urls"] == []


def test_goal_boost_events_fehler_laesst_match_offen_133(goal_env, monkeypatch):
    """HTTP-Fehler beim Nachladen: kein Crash, Match bleibt nachladbar."""
    m, calls = goal_env
    calls["discovery"] = {"response": [_ft_item(m, with_events=False)], "errors": {}}

    def fake_403(url, headers=None, timeout=None, **kw):
        calls["urls"].append(url)
        if "/fixtures/events" in url:
            return _Resp({"response": [], "errors": {}}, status=403)
        return _Resp(calls["discovery"])

    monkeypatch.setattr(minute_boost.requests, "get", fake_403)
    r = minute_boost.boost_goal_scorers_from_apifootball()
    assert r["updated"] == 0 and m.events in (None, "")


def test_match_detail_ereignis_sektionen_133():
    """Template zeigt Auswechslungen + beide Ereignis-Quellen."""
    t = open("templates/match_detail.html", encoding="utf-8").read()
    assert "🔄 Auswechslungen" in t and "sub_rows" in t
    assert "rein ⇄ raus" in t
    assert "API-Football / OpenLigaDB" in t


def test_af_goal_boost_laeuft_im_cron_takt_136():
    """(136) Der API-Football-Ereignis-Boost (Karten/Wechsel) haengt nicht nur
    am Live-Center-Polling, sondern auch am Cron-Sync - sonst bekommen ferlige
    Spiele ohne Center-Besuch nie Karten/Auswechslungen."""
    src = open("sync_openligadb.py", encoding="utf-8").read()
    assert "boost_goal_scorers_from_apifootball()" in src
    assert "AF-Events:" in src
    # Der Polling-Pfad bleibt unberuehrt (schnelle Fuellung bei offener Seite)
    poll = open("sync_football_data.py", encoding="utf-8").read()
    assert "boost_goal_scorers_from_apifootball" in poll
