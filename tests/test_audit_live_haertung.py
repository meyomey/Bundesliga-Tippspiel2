"""Tests Live-Daten-Audit-Haertung ((111)).

Audit 10.10.2026 (komplettes Audit aller Live-Datenwege) fand drei Luecken:
1. das (106)-Protokoll schrieb „olb-live“, aber die Admin-Quellenliste
   SOURCES kannte den Kind nicht -> der Boost war im Admin unsichtbar
   (genau deshalb fehlte er in der Nutzer-Statuszeile);
2. Live-API-Antworten hatten keinen Cache-Control-Header (Proxy-/Browser-
   Cache koennte veraltete Tore/Minuten/Tabelle ausliefern);
3. die Live-GETs hatten kein Rate-Limit (Upstreams gut geschuetzt, die
   App-DB selbst nicht). -> 120/min auf die drei Polling-Endpunkte.
"""
import json

from datasource_activity import SOURCES, record
from sync import _source_activity

OLB_LIVE = ("olb-live", "OpenLigaDB · Live-Boost (Zwischenstände)")


def test_olb_live_steht_in_der_quellenliste():
    """F1: (106)-Kind muss im Admin sichtbar sein (SOURCES = Render-Vertrag)."""
    assert OLB_LIVE in SOURCES


def test_alle_bekannten_kinds_gelistet(app, db):
    """Vertrags-Test: jedes protokollierte Kind hat eine Admin-Zeile."""
    keys = {k for k, _label in SOURCES}
    # (139) + tsdb_events (Karten/Wechsel key-frei) + olb-events (Torschützen-
    # Nachzug) - beides Cron-Boosts, die nach echtem HTTP-Kontakt protokollieren.
    assert keys == {"football-data", "openligadb", "olb-live", "minute",
                    "goals", "tsdb_events", "olb-events", "torjaeger",
                    "the_odds_api"}


def test_olb_live_erscheint_in_source_activity(app, db):
    """Ende-Ende: record() -> entries() -> _source_activity() rendert den
    Eintrag (so sieht ihn das Admin-Dashboard)."""
    record("olb-live", True, "2 Spiel(e) aktualisiert")
    zeilen = {z["key"]: z for z in _source_activity()}
    assert "olb-live" in zeilen
    e = zeilen["olb-live"]["entry"]
    assert isinstance(e, dict) and e.get("ok") is True
    assert "2 Spiel(e) aktualisiert" in (e.get("note") or "")


def test_live_endpunkte_ohne_store_cache(client, app, db, user, competition,
                                         teams, monkeypatch):
    """F2: Live-Antworten tragen Cache-Control: no-store (public UND login)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    r = client.get("/api/matches/5")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store"

    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = competition.code
    r2 = client.get("/api/live/center")
    assert r2.status_code == 200
    assert r2.headers.get("Cache-Control") == "no-store"
    body = r2.get_json()
    assert body["ok"] is True


def test_live_html_seiten_ohne_store_cache_150(client, app, db, user,
                                               competition, monkeypatch):
    """(150) Auch die HTML-Seiten selbst nicht cachen: nach Menue -> Zurueck
    (Browser-Cache/bfcache) durfte sonst der alte Punktestand stehen."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = competition.code
    for pfad in ("/live", "/bundesliga-tabelle", "/api/standings/computed"):
        r = client.get(pfad)
        assert r.status_code == 200, pfad
        assert r.headers.get("Cache-Control") == "no-store", pfad


def test_live_center_live_anzeige_mit_final_basis_154(client, app, db,
                                                      user, competition,
                                                      monkeypatch):
    """(153)/(154) /live rendert die Rangliste aus get_live_leaderboard
    (dynamisch inkl. laufender Spiele) UND liefert get_leaderboard
    (Final-Stand) als Delta-Basis. Vor (154) war der erste Live-Stand die
    eigene Basis -> ▲/+ blieben unsichtbar; vor (153) war die Anzeige der
    gecachte Final-Stand -> alter Punktestand beim Zurueckkommen."""
    import main_stats_routes as msr

    live_rows = [{
        "user": user, "points": 83, "match_points": 83,
        "special_points": 0, "tips": 3, "exact": 1, "diff": 1,
        "tendency": 1, "wrong": 0, "pending": 0, "joker_used": 0,
        "exact_quote": 33, "rank": 5,
    }]
    base_rows = [{
        "user": user, "points": 81, "match_points": 81,
        "special_points": 0, "tips": 3, "exact": 1, "diff": 1,
        "tendency": 1, "wrong": 0, "pending": 0, "joker_used": 0,
        "exact_quote": 33, "rank": 6,
    }]
    gesehen = {}
    monkeypatch.setattr(msr, "get_live_leaderboard",
                        lambda *a, **k: gesehen.setdefault("live", live_rows))
    monkeypatch.setattr(msr, "get_leaderboard",
                        lambda *a, **k: gesehen.setdefault("base", base_rows))
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = competition.code
    r = client.get("/live")
    assert r.status_code == 200
    assert "live" in gesehen            # Anzeige: LIVE-Quelle
    assert "base" in gesehen            # Delta-Basis: Final-Quelle


def test_live_js_zieht_nach_ruecksprung_sofort_nach_150():
    """(150) live.js hoert auf pageshow (bfcache) + visibilitychange und
    holt dann sofort, nicht erst beim naechsten 20s-Tick."""
    js = open("static/js/live.js", encoding="utf-8").read()
    assert "addEventListener('pageshow'" in js
    assert "e.persisted" in js
    assert "addEventListener('visibilitychange'" in js
    assert "document.hidden" in js
    # (154) Delta-Basis aus data-base-* vorbelegen, sonst ist der erste
    # Live-Stand die eigene Basis und ▲/+ bleiben leer.
    assert "dataset.baseRank" in js
    assert "dataset.basePoints" in js
    # (155) sichtbarer Null-Zustand bei laufenden Spielen
    assert "delta-zero" in js
    assert "liveActive ?" in js
    # (156)/(157) Basis aus der API-Payload - serverautorisitativ ZUERST
    assert "r.base_rank" in js
    assert "apiBase" in js
    assert "const base = apiBase || baseLb[r.user_id]" in js
    # (153) erster Abruf sofort beim Start, nicht erst nach 20s
    import re as _re
    assert _re.search(
        r"function startPolling\(\) \{[^}]*?refresh\(\);[^}]*?setInterval\(refresh, POLL\);",
        js)


def test_live_html_traegt_final_basis_attribute_154(client, app, db, user,
                                                    competition, teams,
                                                    monkeypatch):
    """(154)-Beweis: die Ranglisten-Zeilen der /live-Seite tragen den
    Final-Stand (ohne laufende Spiele) als data-base-rank/-points, hier
    mit auseinanderliegenden Werten (Final 81/P6 vs. Live 83/P5)."""
    from datetime import datetime, timedelta, timezone as _tz
    from models import Match
    import main_stats_routes as msr

    now = datetime.now(_tz.utc)
    m = Match(home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=now - timedelta(minutes=50), status="live",
              home_score=0, away_score=0, matchday=7,
              competition_id=competition.id)
    db.session.add(m)
    db.session.commit()

    def _live(*a, **k):
        return [{"user": user, "points": 83, "match_points": 83,
                 "special_points": 0, "tips": 4, "exact": 1, "diff": 1,
                 "tendency": 1, "wrong": 1, "pending": 0, "joker_used": 0,
                 "exact_quote": 25, "rank": 5}]

    def _base(*a, **k):
        return [{"user": user, "points": 81, "match_points": 81,
                 "special_points": 0, "tips": 4, "exact": 1, "diff": 1,
                 "tendency": 1, "wrong": 1, "pending": 0, "joker_used": 0,
                 "exact_quote": 25, "rank": 6}]

    monkeypatch.setattr(msr, "get_live_leaderboard", _live)
    monkeypatch.setattr(msr, "get_leaderboard", _base)
    monkeypatch.setattr("routes_api.fetch_live_match_updates",
                        lambda *a, **k: {"ok": False})
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = competition.code
    r = client.get("/live")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert 'data-base-rank="6"' in html       # Final-Platz (nicht 5!)
    assert 'data-base-points="81"' in html    # Final-Punkte (nicht 83!)


def test_live_center_api_liefert_final_basis_mit_156(client, app, db, user,
                                                     competition, teams,
                                                     monkeypatch):
    """(156) /api/live/center liefert pro Zeile base_rank/base_points aus
    der Final-Tabelle (ohne laufende Spiele) - die Deltas vergleichen
    gegen diesen Stand, egal welchen Zustand der Browser hat."""
    from datetime import datetime, timedelta, timezone as _tz
    from models import Match
    import routes_api as ra

    now = datetime.now(_tz.utc)
    m = Match(home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=now - timedelta(minutes=50), status="live",
              home_score=0, away_score=0, matchday=7,
              competition_id=competition.id)
    db.session.add(m)
    db.session.commit()

    def _live(*a, **k):
        return [{"user": user, "points": 82, "match_points": 82,
                 "special_points": 0, "tips": 4, "exact": 1, "diff": 1,
                 "tendency": 1, "wrong": 1, "pending": 0, "joker_used": 0,
                 "exact_quote": 25, "rank": 5}]

    def _base(*a, **k):
        return [{"user": user, "points": 81, "match_points": 81,
                 "special_points": 0, "tips": 4, "exact": 1, "diff": 1,
                 "tendency": 1, "wrong": 1, "pending": 0, "joker_used": 0,
                 "exact_quote": 25, "rank": 6}]

    monkeypatch.setattr(ra, "get_live_leaderboard", _live)
    monkeypatch.setattr(ra, "get_leaderboard", _base)
    monkeypatch.setattr(ra, "fetch_live_match_updates",
                        lambda *a, **k: {"ok": False})
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = competition.code
    r = client.get("/api/live/center")
    assert r.status_code == 200
    zeile = r.get_json()["leaderboard"][0]
    assert zeile["points"] == 82        # LIVE-Wert
    assert zeile["base_points"] == 81   # Final-Basis
    assert zeile["base_rank"] == 6
