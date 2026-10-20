"""(138) TheSportsDB-Ereignis-Boost: Karten & Auswechslungen key-frei.

Ausloeser: API-Football verweist den Free-Key fuer 2026 ("Free plans do not
have access to this season"), OLB pflegt keine Karten. TheSportsDB (Test-Key
"123", alter Key "3" permanent disabled) liefert die Timeline. Die Payloads
in den Tests sind Auszuege der Live-Probe vom 18.10.2026 (ST 6).
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import tsdb_events as te
from extensions import db
from models import Competition, Match, Team

# --- echte Timeline (Live-Probe lookuptimeline id=2508383, Schalke-Mainz) --
_SCHALKE_MAINZ_TIMELINE = [
    {"strTimeline": "Goal", "strTimelineDetail": "Normal Goal", "strHome": "No",
     "strPlayer": "Phillip Tietz", "strAssist": "Anthony Caci", "intTime": "24",
     "idTeam": "133665", "strTeam": "Mainz", "strComment": "NULL"},
    {"strTimeline": "Card", "strTimelineDetail": "Yellow Card", "strHome": "No",
     "strPlayer": "Nadiem Amiri", "strAssist": "0", "intTime": "42",
     "idTeam": "133665", "strTeam": "Mainz", "strComment": "Foul"},
    {"strTimeline": "Card", "strTimelineDetail": "Yellow Card", "strHome": "No",
     "strPlayer": "Kaishū Sano", "strAssist": "", "intTime": "45",
     "idTeam": "133665", "strTeam": "Mainz", "strComment": "Foul"},
    {"strTimeline": "subst", "strTimelineDetail": "Substitution 1",
     "strHome": "Yes", "strPlayer": "Edin Džeko", "strAssist": "Hee-chan Hwang",
     "intTime": "60", "idTeam": "133661", "strTeam": "Schalke 04",
     "strComment": "NULL"},
    {"strTimeline": "subst", "strTimelineDetail": "Substitution 2",
     "strHome": "Yes", "strPlayer": "Adrian Gantenbein",
     "strAssist": "Eric Junior Dina Ebimbe", "intTime": "60",
     "idTeam": "133661", "strTeam": "Schalke 04", "strComment": "NULL"},
]

# --- echtes Round-Item (Live-Probe eventsround r=6) -------------------------
_SCHALKE_MAINZ_EVENT = {
    "idEvent": "2508383", "strTimestamp": "2026-10-17T13:30:00",
    "strEvent": "Schalke 04 vs Mainz", "strHomeTeam": "Schalke 04",
    "strAwayTeam": "Mainz", "intRound": "6", "intHomeScore": "0",
    "intAwayScore": "1", "strStatus": "FT",
}


def test_rows_aus_timeline_138():
    rows = te.rows_from_timeline(_SCHALKE_MAINZ_TIMELINE)
    gf = [r for r in rows if r["kind"] == "gf"]
    cards = [r for r in rows if r.get("type") == "card"]
    subs = [r for r in rows if r["kind"] == "sub"]
    assert len(gf) == 1 and len(cards) == 2 and len(subs) == 2
    assert gf[0] == {"kind": "gf", "min": 24, "team": "away",
                     "player": "Phillip Tietz", "assist": "Anthony Caci",
                     "penalty": False, "own_goal": False, "src": "tsdb"}
    assert cards[0]["player"] == "Nadiem Amiri" and cards[0]["card"] == "gelb"
    assert cards[1]["team"] == "away"
    assert subs[0]["player"] == "Edin Džeko" and subs[0]["assist"] == "Hee-chan Hwang"
    assert all(r["min"] >= 1 for r in rows)


def test_rows_filter_var_und_verweigerte_karten_138():
    rows = te.rows_from_timeline([
        {"strTimeline": "Var", "strTimelineDetail": "Goal cancelled",
         "strHome": "Yes", "intTime": "30"},
        {"strTimeline": "Goal", "strTimelineDetail": "Missed Penalty",
         "strHome": "Yes", "strPlayer": "X", "intTime": "31"},
        {"strTimeline": "Card", "strTimelineDetail": "Missing Yellow Card",
         "strHome": "Yes", "strPlayer": "Y", "intTime": "32"},
        {"strTimeline": "Goal", "strTimelineDetail": "Penalty",
         "strHome": "No", "strPlayer": "Z", "intTime": "33"},
        {"strTimeline": "Goal", "strTimelineDetail": "Own Goal",
         "strHome": "No", "strPlayer": "W", "intTime": "34"},
        {"strTimeline": "Card", "strTimelineDetail": "Second Yellow card",
         "strHome": "No", "strPlayer": "V", "intTime": "35"},
        {"strTimeline": "Card", "strTimelineDetail": "Red Card",
         "strHome": "No", "strPlayer": "U", "intTime": "36"},
        {"strTimeline": "Card", "strTimelineDetail": "Yellow Card",
         "strHome": "Maybe", "strPlayer": "?", "intTime": "37"},  # Seite unklar
    ])
    kinds = [(r["kind"], r.get("card"), r.get("min")) for r in rows]
    assert kinds == [("gf", None, 33), ("gf", None, 34),
                     ("olb", "yellow_red", 35), ("olb", "rot", 36)]
    pen = next(r for r in rows if r["min"] == 33)
    og = next(r for r in rows if r["min"] == 34)
    assert pen["penalty"] is True and pen["team"] == "away"
    assert og["own_goal"] is True


def test_merge_nur_leere_vorlage_wird_ergaenzt_138():
    m = SimpleNamespace(events=json.dumps([
        {"kind": "gf", "min": 24, "team": "away", "player": "Phillip Tietz",
         "assist": None, "penalty": False, "own_goal": False, "src": "olb"},
        {"kind": "gf", "min": 70, "team": "home", "player": "Kane",
         "assist": "Musiala", "penalty": False, "own_goal": False, "src": "af"},
    ]))
    assert te._merge_rows(m, te.rows_from_timeline(_SCHALKE_MAINZ_TIMELINE)) is True
    rows = json.loads(m.events)
    tor24 = next(r for r in rows if r["min"] == 24)
    assert tor24["assist"] == "Anthony Caci"       # leere Vorlage nachgefuellt
    assert tor24["player"] == "Phillip Tietz"      # Schuetze unangetastet
    tor70 = next(r for r in rows if r["min"] == 70)
    assert tor70["assist"] == "Musiala"            # stehende Zeile unberuehrt
    assert len([r for r in rows if r.get("type") == "card"]) == 2
    assert len([r for r in rows if r["kind"] == "sub"]) == 2
    # Idempotenz: zweiter Lauf aendert nichts
    snapshot = m.events
    assert te._merge_rows(m, te.rows_from_timeline(_SCHALKE_MAINZ_TIMELINE)) is False
    assert m.events == snapshot


@pytest.fixture
def tsdb_env(app, db, monkeypatch):
    comp = Competition.query.filter_by(code="BL1").first() or Competition(
        code="BL1", name="Bundesliga", season="2026", matchdays=34,
        teams_count=18, is_active=True)
    db.session.add(comp)
    db.session.commit()
    home = Team(name="FC Schalke 04", short_name="S04", logo="x.png")
    away = Team(name="1. FSV Mainz 05", short_name="M05", logo="x.png")
    db.session.add_all([home, away])
    db.session.commit()
    kickoff = datetime(2026, 10, 17, 13, 30, tzinfo=timezone.utc)
    m = Match(competition_id=comp.id, matchday=6, home_team_id=home.id,
              away_team_id=away.id, kickoff=kickoff,
              status="finished", home_score=0, away_score=1)
    db.session.add(m)
    db.session.commit()

    calls = {"urls": []}

    def fake_get(url, timeout=None, **kw):
        calls["urls"].append(url)
        if "eventsround" in url:
            return _Resp({"events": [_SCHALKE_MAINZ_EVENT]})
        return _Resp({"timeline": _SCHALKE_MAINZ_TIMELINE})

    monkeypatch.setattr(te.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    monkeypatch.setattr(te, "current_sync_season_code",
                        lambda: "2026", raising=False)
    import sync_shared
    monkeypatch.setattr(sync_shared, "current_sync_season_code", lambda: "2026")
    te._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    cache_obj = te._gate_cache()
    if cache_obj is not None:
        cache_obj.set(te._GATE_KEY, {"day": "", "count": 0, "last": 0.0}, ttl=3600)
    yield m, calls
    te._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_boost_laueft_key_frei_138(app, tsdb_env):
    m, calls = tsdb_env
    with app.app_context():
        r = te.boost_events_from_thesportsdb(
            now=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc))
    assert r["updated"] == 1
    assert any("eventsround" in u for u in calls["urls"])
    assert any("lookuptimeline" in u for u in calls["urls"])
    rows = json.loads(m.events)
    assert [x for x in rows if x.get("type") == "card"]
    assert [x for x in rows if x["kind"] == "sub"]
    # zweiter Lauf sofort -> Drossel
    with app.app_context():
        assert te.boost_events_from_thesportsdb(
            now=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)).get("throttled")


def test_boost_matcht_nicht_ohne_token_overlap_138(app, tsdb_env):
    m, calls = tsdb_env
    # Fremdspiel im Payload: anderes Team -> kein Match, keine Timeline-Call-Realloka...
    m2_home = Team(name="Bayer 04 Leverkusen", short_name="Werk", logo="y.png")
    db.session.add(m2_home)
    db.session.commit()
    m2 = Match(competition_id=m.competition_id, matchday=6,
               home_team_id=m2_home.id, away_team_id=m.away_team_id,
               kickoff=m.kickoff, status="finished", home_score=1, away_score=0)
    db.session.add(m2)
    db.session.commit()
    with app.app_context():
        r = te.boost_events_from_thesportsdb(
            now=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc))
    # Schalke-Mainz bleibt eindeutig (Leverkusen-Mainz teilt nur 'mainz' ->
    # Heim-Overlap fehlt) -> genau unser Spiel wurde aktualisiert
    assert r["updated"] == 1
    m2_events = db.session.get(Match, m2.id).events
    assert m2_events in (None, "", "[]")


def test_season_label_und_cron_hook_138():
    assert te._season_label("2026") == "2026-2027"
    src = open("sync_openligadb.py", encoding="utf-8").read()
    assert "boost_events_from_thesportsdb" in src
    assert "TSDB-Events:" in src
    top = open("top_scorers.py", encoding="utf-8").read()
    assert "/json/123/" in top and "/json/3/" not in top
