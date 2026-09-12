"""API-Football im Admin-Dashboard (12.09.2026): Aktivitaets-Tracking,
Budget-Anzeige und Checks-Kachel - der dritte Datenstrang soll sichtbar sein
(Letzter-Abruf je Booster + heutigiger Verbrauch), ohne jemals zwingend zu wirken.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

import minute_boost
import sync as sync_mod
import top_scorers
from models import Competition, Match, Team
from scoring import get_setting, set_setting


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status
        self.ok = status == 200

    def json(self):
        return self._p


@pytest.fixture
def af_env(app, monkeypatch):
    """Token gesetzt, Aktivitaets-Key leer, alle Gates frisch, HTTP gemockt."""
    calls = {"n": 0, "resp": None, "url": ""}

    def fake_get(url, headers=None, timeout=None, **kw):
        calls["n"] += 1
        calls["url"] = url
        return calls["resp"] or _Resp({"response": [], "errors": {}})

    monkeypatch.setattr(minute_boost.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    set_setting("apifootball_token", "TESTKEY")
    set_setting("apifootball_activity", "")
    set_setting("apifootball_plan_block", "")
    set_setting("datasource_activity", "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    minute_boost._STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    minute_boost._GOAL_STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    top_scorers._STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    set_setting(top_scorers.CACHE_KEY, "")
    yield calls
    minute_boost._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    minute_boost._GOAL_STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    top_scorers._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    set_setting("apifootball_token", "")
    set_setting("apifootball_activity", "")
    set_setting("apifootball_plan_block", "")
    set_setting("datasource_activity", "")
    set_setting(top_scorers.CACHE_KEY, "")


def _activity():
    import datasource_activity as ds
    return ds.entries()


def test_record_roundtrip_and_truncation(app, af_env):
    with app.app_context():
        minute_boost.record_apifootball_activity("minute", True, "3 Spiele aktualisiert")
        minute_boost.record_apifootball_activity("goals", False, "X" * 300)
        act = _activity()
        assert act["minute"]["ok"] is True and act["minute"]["note"] == "3 Spiele aktualisiert"
        assert act["goals"]["ok"] is False and len(act["goals"]["note"]) == 140
        summary = minute_boost.apifootball_activity_summary()
        assert summary["token"] is True
        assert set(summary["entries"]) == {"minute", "goals"}
        assert set(summary["calls"]) == {"minute", "goals", "torjaeger"}
        assert summary["caps"]["minute"] == 90


def test_minute_and_torjaeger_attempt_get_recorded(app, db, monkeypatch, af_env):
    comp = Competition.query.filter_by(code="BL1").first() or Competition(
        code="BL1", name="Bundesliga", season="2026", matchdays=34, teams_count=18, is_active=True)
    db.session.add(comp)
    db.session.commit()
    bay = Team.query.filter_by(short_name="FCB").first() or Team(name="FC Bayern München", short_name="FCB", logo="x.png")
    bvb = Team.query.filter_by(short_name="BVB").first() or Team(name="Borussia Dortmund", short_name="BVB", logo="x.png")
    db.session.add_all([t for t in (bay, bvb) if t.id is None])
    db.session.commit()
    m = Match(competition_id=comp.id, matchday=3, home_team_id=bay.id, away_team_id=bvb.id,
              kickoff=datetime.now(timezone.utc) + timedelta(minutes=10), status="scheduled")
    db.session.add(m)
    db.session.commit()

    with app.app_context():
        # 1) Live-Fenster -> Minute-Boost ruft ab, leerer Feed = ok mit 0
        res = minute_boost.boost_minutes_from_apifootball()
        assert res["ok"] and af_env["n"] == 1
        act = _activity()
        assert act["minute"]["ok"] is True and "aktualisiert" in act["minute"]["note"]
        # 2) Torjaeger-Abruf mit HTTP-Fehler -> Fehlerpfad protokolliert
        af_env["resp"] = _Resp({"errors": {}}, status=401)
        res2 = top_scorers.fetch_top_scorers()
        assert res2.get("http") == 401
        act = _activity()
        assert act["torjaeger"]["ok"] is False and "HTTP 401" in act["torjaeger"]["note"]
        # Budget zaehlt pro Gate getrennt
        summary = minute_boost.apifootball_activity_summary()
        assert summary["calls"]["minute"] == 1 and summary["calls"]["torjaeger"] == 1


# ---------------- gemeinsamer Versuchs-Speicher: fd/OLB + Seite ----------------
# ---------------- Plan-Absage: Feed pausiert, Grund bleibt sichtbar ----------------
_PLAN_MSG = ('{"plan": "Free plans do not have access to this season, '
             'try from 2022 to 2024."}')


def test_plan_rejection_pauses_feed_for_the_day(app, monkeypatch, af_env):
    import datasource_activity as ds

    class R:
        status_code = 200
        ok = True

        def json(self):
            return {"response": [], "errors": {"plan": _PLAN_MSG}}

    # NUR den Counter im af_env-Fixture umhangen, damit die Calls zahlbar bleiben
    af_env["resp"] = R()
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res.get("api_errors") is True            # echter Versuch
        assert af_env["n"] == 1
        res2 = top_scorers.fetch_top_scorers()
        assert res2.get("skipped") == "plan-blocked"    # zweiter Versuch: Pause, kein HTTP
        assert af_env["n"] == 1
        # Und der Minute-Feed kassiert dieselbe Absage -> pausiert ebenfalls (1 Call)
        res3 = minute_boost.boost_minutes_from_apifootball()
        assert res3.get("skipped") in (None, "plan-blocked")
        assert "plan" in (_activity().get("torjaeger", {}).get("note", "")).lower()
        # Grund steht als Text im Protokoll (Originalwortlaut, nicht "pruefen")
        assert "2022 to 2024" in _activity()["torjaeger"]["note"]


def test_torjaeger_page_shows_last_reason(client, db, user, app, monkeypatch):
    import datasource_activity as ds
    set_setting("apifootball_token", "TESTKEY")
    set_setting("apifootball_plan_block", __import__("json").dumps(
        {"torjaeger": datetime.now(timezone.utc).strftime("%Y-%m-%d")}))
    with app.app_context():
        ds.record("torjaeger", False,
                   'API: {"plan": "Free plans do not have access to this season, '
                   'try from 2022 to 2024."}')
        set_setting(top_scorers.CACHE_KEY, "")
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "Noch keine Torj\u00e4ger-Daten" in html
    assert "2022 to 2024" in html                     # echter Grund sichtbar
    assert "wird heute nicht weiter versucht" in html  # Selbstheilungs-Hinweis
    set_setting("apifootball_token", "")
    set_setting("apifootball_plan_block", "")
    set_setting("datasource_activity", "")


def test_fd_and_olb_attempts_recorded(app, monkeypatch):
    set_setting("apifootball_token", "")       # Torjaeger-Hook bleibt still
    set_setting("datasource_activity", "")
    import sync_openligadb as so
    monkeypatch.setattr(so, "sync_with_football_data",
                        lambda *a, **k: {"ok": False, "msg": "Kein Token gesetzt"})
    monkeypatch.setattr(so, "sync_with_openligadb",
                        lambda *a, **k: {"ok": False, "msg": "OpenLigaDB: HTTP 404"})
    with app.app_context():
        res = so.sync_results()
        assert res.get("ok") is not True
        import datasource_activity as ds
        act = ds.entries()
        assert act["football-data"]["ok"] is False and "Token" in act["football-data"]["note"]
        assert act["openligadb"]["ok"] is False and "HTTP 404" in act["openligadb"]["note"]


def test_admin_page_shows_attempt_table(app, client, db, admin_user, monkeypatch):
    class Resp:
        status_code = 200
        ok = True

        def json(self):
            return {}

    monkeypatch.setattr(sync_mod.requests, "get", lambda *a, **k: Resp())
    with app.app_context():
        import datasource_activity as ds
        ds.record("football-data", False, "HTTP 429 Rate-Limit")
    client.post("/auth/login", data={"email": admin_user.email, "password": "admin123"},
                follow_redirects=True)
    html = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "Versuche je Quelle" in html
    assert "HTTP 429 Rate-Limit" in html
    assert "noch nicht protokolliert" in html


def test_diagnostics_and_admin_page(app, client, db, admin_user, monkeypatch, af_env):
    # OLB-Ping im Diagnostics klemmen wir ab (kein echtes Netz im Test)
    monkeypatch.setattr(sync_mod.requests, "get",
                        lambda *a, **k: _Resp({}, status=200))
    with app.app_context():
        diag = sync_mod.get_sync_diagnostics()
        assert diag["checks"]["apifootball_token"] is True
        assert "apifootball" in diag
    client.post("/auth/login", data={"email": admin_user.email, "password": "admin123"},
                follow_redirects=True)
    html = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "API-Football · Booster" in html
    assert "Key hinterlegt" in html
    assert "noch kein Abruf" in html          # kein Activity-Eintrag -> neutral
    assert "Heutiger Verbrauch" in html

    # Ohne Key: Kachel wechselt auf Info-Optik, Karte erklaert den Free-Key
    set_setting("apifootball_token", "")
    html2 = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "ℹ️ Kein Key" in html2
    assert "api-football.com" in html2
