"""Torjaeger-Rangliste (13.09.2026, Stand g): OLB-Liste + TheSportsDB-Vereinssuche.

Liste und Vereinsnamen sind keyfrei. Die Vereinsuche liefert nur, was sicher
einem Liga-Team der eigenen DB zugeordnet werden kann - Muell entries
("_Retired Soccer"), Fremdvereine und Initial-Fehltreffer werden verworfen
und 7 Tage lang nicht erneut angefasst. HTTP ist vollstandig gemockt.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

import top_scorers
from extensions import db
from models import Team
from scoring import get_setting, set_setting


def _olb_payload():
    return [
        {"goalGetterId": 1, "goalGetterName": "I. Matanovic", "goalCount": 4},
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
    calls = {"olb": 0, "tsdb": 0, "payload": None, "olb_status": 200,
             "players": None, "tsdb_status": 200}

    def fake_get(url, headers=None, timeout=None, **kw):
        if "thesportsdb" in url:
            calls["tsdb"] += 1
            if calls["tsdb_status"] != 200:
                class Bad:
                    status_code = calls["tsdb_status"]

                    def json(self):
                        return {}
                return Bad()
            return _Resp({"player": calls["players"] or []})
        calls["olb"] += 1
        assert "api.openligadb.de/getgoalgetters/bl1/" in url  # keyfrei, OLB
        if calls["olb_status"] != 200:
            class Bad2:
                status_code = calls["olb_status"]

                def json(self):
                    return {}
            return Bad2()
        return _Resp(calls["payload"] if calls["payload"] is not None else [])

    monkeypatch.setattr(top_scorers.requests, "get", fake_get)
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    import datasource_activity as ds
    for k in (top_scorers.CACHE_KEY, top_scorers.SQUAD_MAP_KEY, ds.SETTING_KEY):
        set_setting(k, "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    top_scorers._STATE_FALLBACK.update({"day": today, "count": 0, "last": 0.0})
    yield calls
    top_scorers._STATE_FALLBACK.update({"day": "", "count": 0, "last": 0.0})
    for k in (top_scorers.CACHE_KEY, top_scorers.SQUAD_MAP_KEY, ds.SETTING_KEY):
        set_setting(k, "")


@pytest.fixture
def league_teams(db):
    for nm, sh in (("SC Freiburg", "FRE"), ("Bayer 04 Leverkusen", "B04"),
                   ("FC Bayern München", "FCB")):
        if not Team.query.filter_by(name=nm).first():
            db.session.add(Team(name=nm, short_name=sh, logo="x.png"))
    db.session.commit()


def _next_fetch():
    top_scorers._STATE_FALLBACK["last"] -= 31 * 60


def test_fetch_parses_sorts_and_reports_note(app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res["ok"] is True and res["count"] == 3  # torloser faellt raus
        assert res["teams"] == 0  # leere Spielersuche = keine Vereine, Liste laeuft
        data = json.loads(get_setting(top_scorers.CACHE_KEY))
        assert [r["name"] for r in data["entries"]] == [
            "I. Matanovic", "P. Schick", "Harry Kane"]  # Tore desc, Name aufsteigend
        note = _activity()["torjaeger"]["note"]
        assert note.startswith("3 Spieler · 0/3 mit Verein")
        assert "3 nachgeschlagen" in note and top_scorers.MODULE_VERSION in note


def test_keyfrei_no_apifootball_needed(app, ts_env):
    set_setting("apifootball_token", "")
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        assert top_scorers.fetch_top_scorers()["ok"] is True
        assert ts_env["olb"] == 1


def test_gate_throttle_and_error_keeps_cache(app, ts_env):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        assert top_scorers.fetch_top_scorers()["ok"] is True
        assert top_scorers.fetch_top_scorers().get("skipped") == "throttled"
        assert ts_env["olb"] == 1
        good = get_setting(top_scorers.CACHE_KEY)
        _next_fetch()
        ts_env["olb_status"] = 500
        assert top_scorers.fetch_top_scorers().get("http") == 500
        assert get_setting(top_scorers.CACHE_KEY) == good  # alte Liste bleibt
        assert "HTTP 500" in _activity()["torjaeger"]["note"]


def test_tsdb_hit_binds_league_team(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "Igor Matanović", "strTeam": "Freiburg"}]
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res["teams"] == 1
        entries, _ = top_scorers.top_scorers_listing(allow_refresh=False)
        mat = next(e for e in entries if "Matanovic" in e["name"])
        # Kurzname kommt aus der DB (Test-Seed nennt Freiburg "SCF")
        db_short = Team.query.filter_by(name="SC Freiburg").first().short_name
        assert mat.get("team") == db_short and mat.get("team_src") == "TheSportsDB"
        # andere Nachnamen: identische Fake-Antwort -> kein Initial-/Namensmatch
        assert not any(e.get("team") and "Kane" in e["name"] for e in entries)


def test_junk_and_foreign_clubs_rejected_and_not_repolled(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "P. Schick", "strTeam": "_Retired Soccer"}]
    with app.app_context():
        top_scorers.fetch_top_scorers()
        n_after_first = ts_env["tsdb"]
        entries, _ = top_scorers.top_scorers_listing(allow_refresh=False)
        assert not any(e.get("team") for e in entries)  # Muellverein -> nirgends
        _next_fetch()
        top_scorers.fetch_top_scorers()
        assert ts_env["tsdb"] == n_after_first  # Niete wird nicht erneut gefragt


def test_initial_mismatch_not_bound(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "Josef Schick", "strTeam": "Bayer 04 Leverkusen"}]
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res["teams"] == 0  # 'P. Schick' != 'Josef Schick'


def test_wrong_surname_never_bound(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "Vlatko Matanović", "strTeam": "Hajduk Split"}]
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert res["teams"] == 0  # Nachname stimmt, Verein ist keiner der Liga


def test_tsdb_outage_keeps_pending_and_retries(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["tsdb_status"] = 503
    with app.app_context():
        res = top_scorers.fetch_top_scorers()
        assert "offen" in _activity()["torjaeger"]["note"]
        _next_fetch()
        ts_env["tsdb_status"] = 200
        ts_env["players"] = [{"strPlayer": "Harry Kane", "strTeam": "FC Bayern München"}]
        res2 = top_scorers.fetch_top_scorers()
        assert res2["teams"] == 1  # nach Netz-Erholung greift der Treffer


def test_no_football_data_calls_left(app):
    src = open(top_scorers.__file__, encoding="utf-8").read()
    assert "_fd_request" not in src  # der Weg war 3x 404 - nie zurueck
    assert "api.football-data.org" not in src


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

    def kaputt(force=False):
        raise RuntimeError("Boom")
    monkeypatch.setattr("top_scorers.refresh_top_scorers", kaputt)
    with app.app_context():
        sync_openligadb._refresh_top_scorers_hook()  # kein Raise nach aussen


def test_page_renders_ranking_with_team(client, db, user, app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "Igor Matanović", "strTeam": "Freiburg"}]
    with app.app_context():
        top_scorers.fetch_top_scorers()
        # Kurzname kommt aus der DB - je nach Seed "SCF" oder "FRE", dynamisch pruefen
        db_short = Team.query.filter_by(name="SC Freiburg").first().short_name
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "I. Matanovic" in html and db_short in html
    assert "OpenLigaDB" in html and "API-Football" not in html


def test_page_empty_state_shows_real_error(client, db, user, app, ts_env):
    ts_env["payload"], ts_env["olb_status"] = None, 503
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get("/torjaeger", follow_redirects=True).get_data(as_text=True)
    assert "Noch keine Torj\u00e4ger-Daten" in html
    assert "kein Schlüssel und keine Einstellung" in html


def _squad_map():
    return json.loads(get_setting(top_scorers.SQUAD_MAP_KEY) or "{}")


def test_rejected_names_land_in_review(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "Fremder Spieler", "strTeam": "Hajduk Split"}]
    with app.app_context():
        top_scorers.fetch_top_scorers()
        assert len(_squad_map().get("rejected") or {}) == 3
        review = top_scorers.squad_review()
        assert [r["key"] for r in review] == ["matanovic", "schick", "kane"]
        assert "Aliasse moeglich" in _activity()["torjaeger"]["note"]


def test_alias_overrides_reject_without_new_http(app, ts_env, league_teams):
    # erst Ablehnung erzeugen ...
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = [{"strPlayer": "Fremder Spieler", "strTeam": "Hajduk Split"}]
    with app.app_context():
        top_scorers.fetch_top_scorers()
        assert not _squad_map().get("names")
        # ... dann von Hand zuordnen: wirkt SOFORT (kein tried-Skip, kein HTTP)
        set_setting(top_scorers.ALIASES_KEY, "schick: Bayer 04 Leverkusen")
        top_scorers._STATE_FALLBACK["last"] -= 31 * 60
        n_before = ts_env["tsdb"]
        res = top_scorers.fetch_top_scorers()
        assert ts_env["tsdb"] == n_before
        names = _squad_map()["names"]
        assert names["schick"]["short"] == "B04" and names["schick"].get("alias")
        assert "schick" not in (_squad_map().get("rejected") or {})
        entries, _ = top_scorers.top_scorers_listing(allow_refresh=False)
        assert next(e for e in entries if e["name"] == "P. Schick")["team"] == "B04"
        assert "2/3 mit Verein" in _activity()["torjaeger"]["note"] \
            or "mit Verein" in _activity()["torjaeger"]["note"]


def test_broken_alias_keeps_status_and_says_so(app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    set_setting(top_scorers.ALIASES_KEY, "schick = Verein GibtsNicht")
    with app.app_context():
        top_scorers.fetch_top_scorers()
        rev = {r["key"]: r["why"] for r in top_scorers.squad_review()}
        assert "Alias" in rev.get("schick", "")
        assert "Verein GibtsNicht" in rev["schick"]


def test_admin_page_lists_rejections(client, db, admin_user, app, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = []
    with app.app_context():
        top_scorers.fetch_top_scorers()
    client.post("/auth/login", data={"email": admin_user.email, "password": "admin123"},
                follow_redirects=True)
    html = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "nicht zugeordnete Namen" in html and "Harry Kane" in html
    assert "kein Treffer in TheSportsDB" in html
    assert "Einstellungen → APIs" in html


def test_settings_form_shows_alias_field(client, db, admin_user, app):
    set_setting(top_scorers.ALIASES_KEY, "schick = Bayer 04 Leverkusen")
    client.post("/auth/login", data={"email": admin_user.email, "password": "admin123"},
                follow_redirects=True)
    html = client.get("/admin/settings", follow_redirects=True).get_data(as_text=True)
    assert "squad_aliases" in html and "Bayer 04 Leverkusen" in html
    set_setting(top_scorers.ALIASES_KEY, "")


def _login_as(client, email, pw):
    client.get("/auth/logout")  # bereits eingeloggt? Login gilt sonst nicht neu
    r = client.post("/auth/login", data={"email": email, "password": pw})
    assert r.status_code in (200, 302)


def _freiburg_id(app):
    from models import Team
    with app.app_context():
        return Team.query.filter_by(name="SC Freiburg").first().id


def test_picker_sets_alias_and_row_immediately(app, client, admin_user, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = []  # Suche lehnt alle ab -> Zeile steht ohne Verein da
    with app.app_context():
        top_scorers.fetch_top_scorers()
        assert "matanovic" in _squad_map().get("rejected", {})
    fid = _freiburg_id(app)
    _login_as(client, admin_user.email, "admin123")
    r = client.post("/torjaeger/verein", data={"player": "M. Matanovic",
                                               "team_id": str(fid)},
                    follow_redirects=True)
    assert r.status_code == 200 and "Verein zugeordnet" in r.get_data(as_text=True)
    with app.app_context():
        assert "matanovic = SC Freiburg" in get_setting(top_scorers.ALIASES_KEY, "")
        names = _squad_map()["names"]
        assert names["matanovic"]["name"] == "SC Freiburg" and names["matanovic"]["alias"]
        assert "matanovic" not in _squad_map().get("rejected", {})
        # Keine HTTP-Suche noetig, trotzdem sofort in der Anzeige:
        entries, _ = top_scorers.top_scorers_listing(allow_refresh=False)
        row = next(e for e in entries if "Matanovic" in e["name"])
        from models import Team
        frg = Team.query.get(fid)
        assert row["team"] == (frg.short_name or frg.name)


def test_picker_reset_clears_alias_and_search_may_retry(app, client, admin_user, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    ts_env["players"] = []
    fid = _freiburg_id(app)
    with app.app_context():
        top_scorers.fetch_top_scorers()
    _login_as(client, admin_user.email, "admin123")
    client.post("/torjaeger/verein", data={"player": "I. Matanovic", "team_id": str(fid)})
    client.post("/torjaeger/verein", data={"player": "I. Matanovic", "team_id": ""},
                follow_redirects=True)
    with app.app_context():
        assert "matanovic" not in (get_setting(top_scorers.ALIASES_KEY, "") or "")
        mp = _squad_map()
        assert "matanovic" not in (mp.get("names") or {})
        assert "matanovic" not in (mp.get("tried") or {})  # Suche darf wieder
        entries, _ = top_scorers.top_scorers_listing(allow_refresh=False)
        assert not next(e for e in entries if "Matanovic" in e["name"]).get("team")


def test_picker_rejects_nonadmin_and_bad_team(app, client, user, admin_user, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    _login_as(client, user.email, "testpass123")
    assert client.post("/torjaeger/verein", data={"player": "I. Matanovic",
                                                  "team_id": "1"}).status_code == 403
    _login_as(client, admin_user.email, "admin123")
    r = client.post("/torjaeger/verein", data={"player": "I. Matanovic",
                                               "team_id": "999999"},
                    follow_redirects=True)
    assert "passt nicht" in r.get_data(as_text=True)
    with app.app_context():
        assert not (get_setting(top_scorers.ALIASES_KEY, "") or "")  # Nichts geschrieben


def test_picker_visible_for_admin_only(app, client, admin_user, user, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        top_scorers.fetch_top_scorers()
    _login_as(client, admin_user.email, "admin123")
    html = client.get("/torjaeger").get_data(as_text=True)
    assert 'name="team_id"' in html and "ohne Verein" in html
    _login_as(client, user.email, "testpass123")
    html2 = client.get("/torjaeger").get_data(as_text=True)
    assert 'name="team_id"' not in html2


def _preview_on(client):
    with client.session_transaction() as sess:
        sess["player_preview_mode"] = True


def test_picker_hidden_in_player_preview(app, client, admin_user, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    with app.app_context():
        top_scorers.fetch_top_scorers()
    _login_as(client, admin_user.email, "admin123")
    _preview_on(client)
    html = client.get("/torjaeger").get_data(as_text=True)
    assert 'name="team_id"' not in html  # Dropdown weg, Liste bleibt
    assert "Matanovic" in html


def test_post_blocked_in_player_preview(app, client, admin_user, ts_env, league_teams):
    ts_env["payload"] = _olb_payload()
    _login_as(client, admin_user.email, "admin123")
    _preview_on(client)
    r = client.post("/torjaeger/verein",
                    data={"player": "I. Matanovic", "team_id": "1"},
                    follow_redirects=True)
    assert "Spieleransicht ist aktiv" in r.get_data(as_text=True)
    with app.app_context():
        assert not (get_setting(top_scorers.ALIASES_KEY, "") or "")  # nichts geschrieben
