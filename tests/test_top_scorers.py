"""Torjaeger-Rangliste (12.09.2026): Cache, Parsing, Budgetwaechter, Seite.

Datenquelle ist der optionale API-Football-Free-Key (statistics/league/
top_scorers). Ohne Token kein Request; Fehlerpfade behalten den letzten
Erfolgs-Cache. Hooks/Fetches sind vollstaendig gemockt.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

import top_scorers
from models import Team
from scoring import get_setting, set_setting


def _entry(pid, name, team, goals, assists=0, ps=0, pm=0, apps=9):
    return {"player": {"id": pid, "name": name, "photo": "", "position": "Sturm",
                       "team": {"id": pid * 2, "name": team, "logo": ""}},
            "statistics": [{"goals": {"total": goals, "assists": assists},
                            "penalties": {"scored": ps, "missed": pm},
                            "games": {"appearences": apps, "minutes": apps * 90}}]}


def _payload():
    return {"errors": {}, "response": [
        _entry(1, "Harry Kane", "FC Bayern München", 12, 4, 3, 1),
        _entry(2, "Serhou Guirassy", "Borussia Dortmund", 8, 2, 1, 0),
        _entry(3, "Tim Klein", "Hannover 96", 0, 0, 0, 0),   # ohne Tor: draussen
    ]}


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


@pytest.fixture
def ts_env(app, monkeypatch):
    calls = {"n": 0, "payload": None}

    def fake_get(url, headers=None, timeout=None, **kw):
        calls["n"] += 1
        assert "players/topscorers?league=181" in url
        return _Resp(calls["payload"] or {"response": [], "errors": {}})

    monkeypatch.setattr(top_scorers.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    set_setting("apifootball_token", "TESTKEY")
    set_setting(top_scorers.CACHE_KEY, "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    top_scorers._STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    yield calls
    top_scorers._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    set_setting("apifootball_token", "")
    set_setting(top_scorers.CACHE_KEY, "")


def test_fetch_parses_sorts_and_caches(app, ts_env):
    ts_env["payload"] = _payload()
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res["ok"] and res["count"] == 2 and ts_env["n"] == 1
        data = top_scorers.load_cache()
        assert data["v"] == top_scorers.CACHE_VERSION
        rows = data["entries"]
        assert [r["name"] for r in rows] == ["Harry Kane", "Serhou Guirassy"]
        assert rows[0]["goals"] == 12 and rows[0]["assists"] == 4
        assert rows[0]["pen_scored"] == 3 and rows[0]["pen_missed"] == 1
        assert rows[0]["apps"] == 9


def test_gate_throttle_and_no_token(app, ts_env):
    ts_env["payload"] = _payload()
    with app.app_context():
        assert top_scorers.fetch_top_scorers()["ok"]
        res2 = top_scorers.fetch_top_scorers()   # 6-h-Intervall blockiert
        assert res2.get("skipped") == "throttled" and ts_env["n"] == 1
        # Budget aufgebraucht (zweiter Slot verbruacht, dritter abgelehnt)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        top_scorers._STATE_FALLBACK.update({"day": today, "count": 2, "last": 0.0})
        assert top_scorers.fetch_top_scorers().get("skipped") == "throttled"
        assert ts_env["n"] == 1
    set_setting("apifootball_token", "")
    with app.app_context():
        assert top_scorers.fetch_top_scorers(force=True).get("skipped") == "no-token"
        assert ts_env["n"] == 1


def test_listing_rich_text_and_error_keeps_cache(app, db, ts_env):
    with app.app_context():
        if not Team.query.filter_by(short_name="FCB").first():
            db.session.add(Team(name="FC Bayern München", short_name="FCB", logo="x.png"))
            db.session.commit()
        # alter Cache -> Listing loest Refresh aus; Request kaputt -> Cache bleibt sichtbar
        old = datetime.now(timezone.utc) - timedelta(hours=30)
        set_setting(top_scorers.CACHE_KEY, json.dumps({
            "v": 1, "fetched_at": old.isoformat(), "season": "2026",
            "entries": [_ := {"name": "Harry Kane", "team": "FC Bayern München",
                              "goals": 12, "assists": 4, "pen_scored": 3,
                              "pen_missed": 1, "apps": 9, "minutes": 810,
                              "player_id": 1, "photo": None, "position": "Sturm"}]}))

        def boom(url, headers=None, timeout=None, **kw):
            raise RuntimeError("Netz weg")

        ts_env["payload"] = None
        top_scorers.requests.get = boom
        try:
            entries, meta = top_scorers.top_scorers_listing()
        finally:
            top_scorers.requests.get = ts_env.get  # kein Leak auf andere Tests
        assert entries and entries[0]["name"] == "Harry Kane"
        assert entries[0]["short"] == "FCB"
        assert meta["empty"] is False and meta["has_token"] is True


def test_torjaeger_page_renders_ranking_and_hint(client, db, user, app, ts_env):
    ts_env["payload"] = _payload()
    with app.app_context():
        if not Team.query.filter_by(short_name="FCB").first():
            db.session.add(Team(name="FC Bayern München", short_name="FCB", logo="x.png"))
            db.session.commit()
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "Harry Kane" in html and ">12</strong>" in html
    assert "davon 3 Elfm" in html and "FCB" in html
    assert "Tim Klein" not in html          # Spieler ohne Tor tauchen nie auf


def test_torjaeger_page_hint_without_data(client, db, user, app, monkeypatch):
    monkeypatch.setattr(top_scorers.requests, "get",
                        lambda *a, **k: pytest.fail("ohne Token darf nicht gerufen werden"))
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "Noch keine Torjäger-Daten" in html


def test_sync_results_hook_calls_refresh(app, monkeypatch):
    """Der Sync-Cron halt die Rangliste automatisch frisch (Hook in sync_results)."""
    hits = {"n": 0}

    def spy(force=False):
        hits["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(top_scorers, "refresh_top_scorers", spy)
    import sync_openligadb as so
    monkeypatch.setattr(so, "sync_with_football_data", lambda *a, **k: {"ok": True, "msg": "stub"})
    monkeypatch.setattr(so, "_fill_missing_from_openligadb", lambda *a, **k: 0)
    monkeypatch.setattr(so, "store_sync_result", lambda *a, **k: None)
    with app.app_context():
        so.sync_results()
    assert hits["n"] == 1


def test_error_text_landed_in_activity_and_fast_retry(app, db, monkeypatch):
    """Fix 12.09.2026: echtes API-Fehlerbild im Protokoll statt Platzhalter;
    nach Fehlschlag ist der Retry nach 30 min wieder erlaubt (Erfolg: 6 h)."""
    import datasource_activity as ds
    set_setting("apifootball_token", "TESTKEY")
    set_setting("datasource_activity", "")
    set_setting(top_scorers.CACHE_KEY, "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    top_scorers._STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    seen = {"n": 0}

    class R:
        status_code = 200

        def __init__(self, payload):
            self._p = payload

        def json(self):
            return self._p

    def fake_get(url, headers=None, timeout=None, **kw):
        seen["n"] += 1
        assert "players/topscorers" in url          # korrigierter Endpoint
        return R({"response": [], "errors": {"all": "The endpoint requires a valid league"}})

    monkeypatch.setattr(top_scorers.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res.get("api_errors") is True
        act = ds.entries().get("torjaeger")
        assert act and act["ok"] is False
        assert "requires a valid league" in act["note"]   # echter Grund, nicht "pruefen"
        # unmittelbar danach: drosselt (30-min-Fenster laeuft)
        assert top_scorers.fetch_top_scorers().get("skipped") == "throttled"
        # 40 Minuten nach dem Fehlversuch: wieder erlaubt
        st = dict(top_scorers._STATE_FALLBACK)
        st["last"] = __import__("time").time() - 2400
        top_scorers._STATE_FALLBACK.update(st)
        assert top_scorers.fetch_top_scorers().get("api_errors") is True
        assert seen["n"] == 2
    set_setting("apifootball_token", "")
    set_setting("datasource_activity", "")
    set_setting(top_scorers.CACHE_KEY, "")
