"""(144) Bundesliga-Livetabelle: laufende Spiele werden eingerechnet.

Vor (144) zählte compute_live_standings nur fertige Spiele - waehrend des
Spieltags stand die Seite still (football-data.org aktualisiert erst nach
Spielschluss). Jetzt: die DB-Staende (OLB-Live-Boost) fliessen ein,
betroffene Team-Zeilen sind markiert (in_play), die Seite schaltet bei
laufenden Spielen auf die lokale Livetabelle (Auto-Refresh 30s).
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import Match
from stats_live import compute_live_standings, count_live_matches


@pytest.fixture(autouse=True)
def _pin_test_comp(monkeypatch, competition):
    """Bare-Tests ohne Request-Context wuerden auf den ersten aktiven
    Wettbewerb (BL1-Season-Fixture) laufen - hier explizit die Test-Comp."""
    import competition_helpers as ch
    monkeypatch.setattr(ch, "get_active_competition", lambda: competition)


@pytest.fixture(autouse=True)
def _fake_scorers(monkeypatch):
    """Topscorer-Tab: keine echten OLB-Abrufe im Test."""
    import top_scorers as ts
    monkeypatch.setattr(ts, "top_scorers_listing",
                        lambda allow_refresh=True: (
                            [{"name": "Harry Kane", "goals": 9,
                              "team": "FCB", "logo": None}],
                            {"empty": False, "fetched_at":
                             "2026-10-24T11:00:00", "last_error": None}))


def _match(db, competition, teams, md, h, a, status, hs=None, as_=None,
           days_ago=0):
    m = Match(competition_id=competition.id, matchday=md,
              home_team_id=teams[h].id, away_team_id=teams[a].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=days_ago),
              status=status, home_score=hs, away_score=as_)
    db.session.add(m)
    db.session.commit()
    return m


def _names(rows):
    return {r["team"].short_name: r for r in rows}


def test_compute_rechnet_laufende_spiele_ein(db, competition, teams):
    # Fertig: FCB 2:0 BVB  |  FCB 1:1 B04
    _match(db, competition, teams, 5, 0, 1, "finished", 2, 0, days_ago=7)
    _match(db, competition, teams, 5, 0, 2, "finished", 1, 1, days_ago=6)
    # Live: FCB 1:0 B04 (laeuft jetzt)  |  BVB - B04 geplant
    _match(db, competition, teams, 6, 0, 2, "live", 1, 0, days_ago=0)
    _match(db, competition, teams, 6, 1, 2, "scheduled")

    rows = _names(compute_live_standings())
    fcb = rows["FCB"]
    assert (fcb["played"], fcb["won"], fcb["drawn"], fcb["lost"]) == (3, 2, 1, 0)
    assert fcb["points"] == 7                       # 3+1+3
    assert fcb["goals_for"] == 4 and fcb["goals_against"] == 1
    assert fcb["in_play"] is True                   # laeuft gerade
    b04 = rows["B04"]
    assert b04["played"] == 2 and b04["points"] == 1  # 1:1 + 0:1 (live)
    assert b04["in_play"] is True
    bvb = rows["BVB"]
    assert bvb["played"] == 1 and bvb["in_play"] is False  # kein Live-Spiel


def test_compute_ohne_live_spiele_unveraendert(db, competition, teams):
    _match(db, competition, teams, 5, 0, 1, "finished", 3, 1, days_ago=7)
    _match(db, competition, teams, 6, 0, 1, "scheduled", days_ago=-3)
    rows = _names(compute_live_standings())
    assert rows["FCB"]["played"] == 1 and rows["FCB"]["points"] == 3
    assert count_live_matches() == 0


def test_count_live_matches(db, competition, teams):
    _match(db, competition, teams, 6, 0, 1, "live", 1, 0)
    _match(db, competition, teams, 6, 2, 3, "live", 0, 0)
    _match(db, competition, teams, 6, 0, 2, "scheduled")
    assert count_live_matches() == 2


def test_route_schaltet_auf_livetabelle(client, db, admin_user, competition,
                                        teams, monkeypatch):
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"
    _match(db, competition, teams, 6, 0, 1, "live", 1, 0)
    html = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert "Livetabelle" in html
    assert "/api/standings/computed" in html        # Auto-Refresh-Endpoint
    assert "30000" in html                          # 30s-Takt


def test_route_behaelt_fd_ohne_live_spiele(client, db, admin_user, competition,
                                           teams, monkeypatch):
    """(146) Tabs sind immer da - ohne laufende Spiele ist GESAMT default."""
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"
    _match(db, competition, teams, 5, 0, 1, "finished", 2, 1, days_ago=7)
    import main_stats_routes as msr

    def fake_fd():
        return None, "fd down"
    monkeypatch.setattr(msr, "fetch_live_standings", fake_fd)
    html = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert "lokal berechnet" in html                # fd-Fallback im Kopf
    assert 'data-default-tab="gesamt"' in html
    assert 'data-tab="gesamt" data-active' in html
    assert 'id="tab-gesamt"' in html and 'id="tab-live" hidden' in html


def test_computed_endpoint_shape(client, db, admin_user, competition, teams):
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"
    _match(db, competition, teams, 6, 0, 1, "live", 1, 0)
    data = client.get("/api/standings/computed").get_json()
    assert data["ok"] is True
    assert data["source"] == "lokal (Livetabelle)"
    fcb = next(r for r in data["table"] if r["team_short"] == "FCB")
    assert fcb["in_play"] is True and fcb["points"] == 3
    assert {"rank", "team_name", "played", "goal_diff", "points",
            "in_play"} <= set(fcb.keys())


def test_standings_js_interpoliert_regulaer_145():
    """(145) Regression „${r.team_name} als Text nach Refresh": der Python-
    Patch hatte \\$ ins JS-Template geschrieben - in Template-Literalen
    bedeutet \\$ aber buchstabloser Text, nicht Interpolation."""
    t = open("templates/standings.html", encoding="utf-8").read()
    assert "\\${" not in t
    assert "${r.team_name}${livePill}" in t
    assert "${r.team_short}" in t


# ---------------------- (146) Tabs: Live / Gesamt / Topscorer -------------

def test_compute_ohne_live_ist_gesamttabelle_146(db, competition, teams):
    _match(db, competition, teams, 5, 0, 1, "finished", 2, 0, days_ago=7)
    _match(db, competition, teams, 6, 0, 1, "live", 5, 0)
    rows_mit = _names(compute_live_standings())
    rows_ohne = _names(compute_live_standings(include_live=False))
    assert rows_mit["FCB"]["points"] == 6            # 3 (2:0) + 3 (5:0 live)
    assert rows_ohne["FCB"]["points"] == 3           # nur fertig
    assert rows_ohne["FCB"]["in_play"] is False


def test_route_drei_tabs_default_live_146(client, db, admin_user, competition,
                                          teams):
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"
    _match(db, competition, teams, 6, 0, 1, "live", 1, 0)
    html = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert 'data-default-tab="live"' in html
    assert 'data-tab="live" data-active' in html
    assert 'id="tab-live"' in html and 'id="tab-gesamt" hidden' in html
    # (161) Topscorer-Tab ENTFERNT (doppelt zur Torjaeger-Seite) ...
    assert 'id="tab-scorer"' not in html
    assert 'data-tab="scorer"' not in html
    # ... aber die Torjaeger-Seite bleibt verlinkt (Header-Button).
    assert "torjaeger" in html
    # Beide Tabellen serverseitig vorgeneriert (sofort sichtbar, kein Blinken)
    assert 'id="standingsBody"' in html and 'id="gesamtBody"' in html


def test_route_ohne_topscorer_kein_olb_abruf_161(client, db, admin_user,
                                                 competition, teams,
                                                 monkeypatch):
    """(161) Die Tabelle-Seite ruft KEINE Torjaeger-Daten mehr ab (der Tab
    ist weg) - OLB-Abrufe passieren nur noch auf /torjaeger."""
    import main_stats_routes as msr

    aufgerufen = []
    import sys as _sys
    top_modul = _sys.modules.get("top_scorers")
    if top_modul is not None:
        monkeypatch.setattr(top_modul, "top_scorers_listing",
                            lambda *a, **k: aufgerufen.append(1) or (
                                [], {"empty": True}))
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"
    html = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert html
    assert aufgerufen == []


def test_tabs_css_146():
    css = open("static/css/style.css", encoding="utf-8").read()
    assert ".tab-row" in css and ".tab-btn[data-active]" in css


# ------------------- (148) Platzverschiebung (▲/▼) in der Livetabelle ----

def test_prev_rank_map_referenz_letzter_vollstaendiger_st_148(db, competition,
                                                              teams):
    """Referenz = letzter vollstaendiger Spieltag: fertige Spiele DES
    laufenden Spieltags veraendern die Referenz nicht ((119)/(120))."""
    # ST 5 fertig: FCB 2:0 BVB, B04 1:1 RBL
    _match(db, competition, teams, 5, 0, 1, "finished", 2, 0, days_ago=7)
    _match(db, competition, teams, 5, 2, 3, "finished", 1, 1, days_ago=7)
    # ST 6: zwei Spiele bereits FERTIG (wuerden Referenz faelschlich
    # verschieben, wenn sie einbezogen wuerden) + eines laeuft
    _match(db, competition, teams, 6, 0, 1, "finished", 5, 0, days_ago=0)
    _match(db, competition, teams, 6, 2, 3, "live", 0, 0)
    m = _prev(competition)
    # Ohne das fertige ST-6-Spiel: FCB hat 3 Pkt -> Platz 1, BVB 0 -> hinten
    assert set(m) == {teams[i].id for i in range(4)}
    fcb_rank = m[teams[0].id]
    assert fcb_rank == 1
    # Sicherstellen, dass das 5:0 von ST 6 NICHT eingeflossen ist:
    # sonst waere BVB (0:5) trotzdem letzter - Differenz pruefen wir über
    # die Punktzahl-Ordnung: B04 (1 Pkt) muss VOR RBL/BVB (je 0) liegen
    assert m[teams[2].id] < m[teams[3].id]


def _prev(competition):
    from stats_live import prev_rank_map
    import competition_helpers as ch
    orig = ch.get_active_competition
    ch.get_active_competition = lambda: competition
    try:
        return prev_rank_map()
    finally:
        ch.get_active_competition = orig


def test_prev_rank_map_leer_ohne_live_148(db, competition, teams):
    _match(db, competition, teams, 5, 0, 1, "finished", 2, 0, days_ago=7)
    assert _prev(competition) == {}               # kein laufendes ST -> keine Pfeile


def test_route_und_endpoint_liefern_delta_148(client, db, admin_user,
                                              competition, teams):
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"
    # ST 5 fertig, ST 6 live: FCB fuehrt live -> Delta +? / BVB faellt
    _match(db, competition, teams, 5, 0, 1, "finished", 0, 0, days_ago=7)
    _match(db, competition, teams, 5, 2, 3, "finished", 0, 0, days_ago=7)
    _match(db, competition, teams, 6, 0, 1, "live", 3, 0)   # FCB zieht vorbei
    html = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert "rk-up" in html and "rk-down" in html     # serverseitig gerendert
    data = client.get("/api/standings/computed").get_json()
    rows = {r["team_short"]: r for r in data["table"]}
    assert rows["FCB"]["rank_delta"] == 2            # von 3 auf 1 (2 Teams ueberholt)
    assert rows["B04"]["rank_delta"] == -1           # von 1 auf 2
    assert rows["RBL"]["rank_delta"] == 1            # von 4 auf 3 (BVB-SchlechTDifferenz)
    assert rows["BVB"]["rank_delta"] == -2           # von 2 auf 4 (0:3 -> TD -3)


def test_delta_semantik_positiv_ist_aufwaerts_148():
    """▲ = delta > 0 (weniger Platzierungspunkte = hoeher), ▼ = delta < 0."""
    js = open("static/js/match_detail.js", encoding="utf-8").read()  # smoke
    t = open("templates/standings.html", encoding="utf-8").read()
    assert "'rk-up' if r.rank_delta > 0 else 'rk-down'" in t
    assert "r.rank_delta > 0 ? 'rk-up' : 'rk-down'" in t
    assert "r.rank + r.rank_delta" in t              # Titel: frueherer Platz


def test_css_pfeile_148():
    css = open("static/css/style.css", encoding="utf-8").read()
    assert ".rk-delta" in css and ".rk-up" in css and ".rk-down" in css


# ------------------ (151) Mobile Live-Tabelle: Scopes + volle Namen -------

def test_live_tabelle_mobile_scopes_und_volle_namen_151():
    """(151) Smartphone: Spaltenbreiten pro Tabellentyp gescopet (die
    (148)-Delta-Spalte hatte die nth-child-Regeln verschoben) und die
    Vereinsnamen voll sichtbar (kein 54px-Ellipsis, keine Kurzform-Dupe)."""
    tpl = open("templates/standings.html", encoding="utf-8").read()
    assert 'bl-table bl-live' in tpl          # Live-Tabelle (mit Delta-Spalte)
    assert 'bl-table bl-gesamt' in tpl        # Gesamt-Tabelle (Referenz-Look)
    assert 'bl-table bl-ts' not in tpl        # (161) Topscorer-Tab entfernt
    css = open("static/css/style.css", encoding="utf-8").read()
    # (152) Live: Verein = Spalte 3 bleibt flexibel, Delta-Spalte schmal -
    # mit !important, damit die alten (144)-Block-Regeln nicht gewinnen.
    assert ".bl-live td:nth-child(2) { width: 30px !important; }" in css
    assert ".bl-live td:nth-child(4) { width: 26px !important; }" in css
    # ... Gesamt unveraendert wie bisher (Original-26px-Set) ...
    assert ".bl-gesamt td:nth-child(3) { width: 28px !important; }" in css
    # ... und es gibt KEINE globalen .bl-table-nth-child-Breiten mehr: die
    # trafen in der Live-Tabelle (11 Spalten) den Verein auf Pos. 3.
    assert ".bl-table td:nth-child(3)" not in css
    assert ".bl-table td:nth-child(2)" not in css
    # Volle Namen mobil: Umbrech statt Ellipsis, Kurzform ausgeblendet.
    assert "white-space: normal; overflow-wrap: break-word; }" in css
    assert ".bl-table .bl-team-short { display: none; }" in css
    # JS-Pfad baut dieselben 11 Zellen (Delta an Position 2) weiter.
    assert '<td class="rk-delta">' in tpl
