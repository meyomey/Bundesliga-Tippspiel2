"""Torjaeger-Rangliste (13.09.2026): OpenLigaDB-Quelle, Cache, Taktung, Seite.

Die Liste laeuft seit dem OLB-Umstieg KEYFREI (API-Football-Free-Plan konnte
die aktuelle Saison nicht liefern). Hier werden Parsing/Sortierung,
30-min-Taktung inkl. Fehler-Schnellwiederholung, Cache-Ehrlichkeit bei
Ausfall und die Seitendarstellung gegen gemockte HTTP-Antworten geprueft.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

import top_scorers
from scoring import get_setting, set_setting


def _olb_payload():
    return [
        {"goalGetterId": 1, "goalGetterName": "Younes Ebnoutalib", "goalCount": 4},
        {"goalGetterId": 2, "goalGetterName": "P. Schick", "goalCount": 4},
        {"goalGetterId": 3, "goalGetterName": "Harry Kane", "goalCount": 3},
        {"goalGetterId": 4, "goalGetterName": "Torlos Nobody", "goalCount": 0},
    ]


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def _activity():
    import datasource_activity as ds
    return ds.entries()


@pytest.fixture
def ts_env(app, monkeypatch):
    calls = {"n": 0, "payload": None, "status": 200}

    def fake_get(url, timeout=None, **kw):
        calls["n"] += 1
        assert "api.openligadb.de/getgoalgetters/bl1/" in url  # keyfrei, OLB
        if calls["status"] != 200:
            class Bad:
                status_code = calls["status"]

                def json(self):
                    return {}
            return Bad()
        return _Resp(calls["payload"] if calls["payload"] is not None else [])

    monkeypatch.setattr(top_scorers.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    import datasource_activity as ds
    set_setting(top_scorers.CACHE_KEY, "")
    set_setting(ds.SETTING_KEY, "")
    set_setting("apifootball_token", "")  # Modul darf keinen Key mehr brauchen
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    top_scorers._STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    yield calls
    top_scorers._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    set_setting(top_scorers.CACHE_KEY, "")
    set_setting(ds.SETTING_KEY, "")


def test_fetch_parses_sorts_and_caches(app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res == {"ok": True, "count": 3}  # torloser Eintrag faellt raus
        data = json.loads(get_setting(top_scorers.CACHE_KEY))
        assert data["v"] == top_scorers.CACHE_VERSION
        names = [r["name"] for r in data["entries"]]
        # Tore desc, bei Gleichstand alphabetisch (redlich, keine Kuenstelordnung)
        assert names == ["P. Schick", "Younes Ebnoutalib", "Harry Kane"]
        assert data["entries"][0]["goals"] == 4
        act = _activity()
        assert act["torjaeger"]["ok"] is True and "3 Spieler" in act["torjaeger"]["note"]


def test_keyfrei_no_token_needed(app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        assert get_setting("apifootball_token", "") == ""
        assert top_scorers.fetch_top_scorers()["ok"] is True
        assert ts_env["n"] == 1


def test_gate_throttle_and_fast_retry_after_error(app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        assert top_scorers.fetch_top_scorers()["ok"] is True
        # direkt danach: getaktet, kein zweiter HTTP-Versuch
        assert top_scorers.fetch_top_scorers().get("skipped") == "throttled"
        assert ts_env["n"] == 1
        # 31 min spaeter naechster Versuch, der fehlschlaegt (503) ...
        ts_env["payload"], ts_env["status"] = None, 503
        top_scorers._STATE_FALLBACK["last"] -= 31 * 60
        assert top_scorers.fetch_top_scorers().get("http") == 503
        assert ts_env["n"] == 2
        assert _activity()["torjaeger"]["ok"] is False
        assert "HTTP 503" in _activity()["torjaeger"]["note"]
        # ...und dank Fehlerprotokoll gilt nur noch die 10-min-Regel (kein 30-min-Brachliegen)
        top_scorers._STATE_FALLBACK["last"] -= 11 * 60
        ts_env["payload"], ts_env["status"] = _olb_payload(), 200
        assert top_scorers.fetch_top_scorers()["ok"] is True
        assert ts_env["n"] == 3


def test_error_keeps_last_good_cache(app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        top_scorers.fetch_top_scorers()
        good = get_setting(top_scorers.CACHE_KEY)
        top_scorers._STATE_FALLBACK["last"] -= 31 * 60  # Intervall vorbei
        ts_env["payload"], ts_env["status"] = None, 500
        assert top_scorers.fetch_top_scorers().get("http") == 500
        assert get_setting(top_scorers.CACHE_KEY) == good  # alte Liste bleibt stehen


def test_page_renders_ranking_without_any_key(client, db, user, app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        top_scorers.fetch_top_scorers()
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "Younes Ebnoutalib" in html and "OpenLigaDB" in html
    assert "Noch keine Torj\u00e4ger-Daten" not in html
    # API-Football wird auf der Seite nicht mehr als Quelle behauptet
    assert "API-Football" not in html


def test_page_empty_state_shows_real_error(client, db, user, app, ts_env, monkeypatch):
    # Allow-refresh drosseln: fetch im Request wirft 503, Cache leer -> Hinweistext
    ts_env["payload"], ts_env["status"] = None, 503
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "Noch keine Torj\u00e4ger-Daten" in html
    assert "kein Schlüssel und keine Einstellung" in html   # keine Key-Sackgasse mehr


def test_sync_hook_calls_refresh(app, monkeypatch):
    seen = {"hits": 0}

    def spy(force=False):
        seen["hits"] += 1
        return {"ok": True}

    import sync_openligadb
    monkeypatch.setattr("top_scorers.refresh_top_scorers", spy)
    with app.app_context():
        sync_openligadb._refresh_top_scorers_hook()
    assert seen["hits"] == 1

    # ...und der Hook ist Fehler-sicher: kaputter Feed darf den Sync nicht kippen
    def kaputt(force=False):
        raise RuntimeError("Boom")
    monkeypatch.setattr("top_scorers.refresh_top_scorers", kaputt)
    with app.app_context():
        sync_openligadb._refresh_top_scorers_hook()  # kein Raise nach aussen
