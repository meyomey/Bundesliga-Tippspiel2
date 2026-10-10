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
    assert keys == {"football-data", "openligadb", "olb-live", "minute",
                    "goals", "torjaeger", "the_odds_api"}


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
