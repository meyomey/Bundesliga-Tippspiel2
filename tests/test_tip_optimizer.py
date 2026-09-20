"""Tests für den Admin-Tipp-Optimizer (Dixon-Coles-EP-Optimierung, 4/3/2).

Deckt ab: Seiten-Rendering (Aktiv-Spieltag aus der DB, Spieltag-Wechsel,
leerer Spieltag), Admin-Gate, den The-Odds-API-Quoten-Endpunkt (Key-Gate,
Budgetwächter, Parsing mit Konsens-Quoten + Namens-Normalisierung,
Fehlergrund im datasource-Protokoll) und das Settings-Verhalten des Keys.
"""
import json
from datetime import datetime, timedelta, timezone

from models import Match
from scoring import get_setting, set_setting
from stats import get_current_matchday


def _login(client, user, password="admin123"):
    client.post("/auth/login", data={"email": user.email, "password": password},
                follow_redirects=True)


def _use_test_comp(client):
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"


def _mk_match(db, competition, teams, matchday, hours_from_now):
    m = Match(
        competition_id=competition.id,
        matchday=matchday,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=hours_from_now),
        status="scheduled",
    )
    db.session.add(m)
    db.session.commit()
    return m


class _FakeResp:
    def __init__(self, status, json_data=None, headers=None):
        self.status_code = status
        self._json = json_data
        self.headers = headers or {}
        self.ok = 200 <= status < 300

    def json(self):
        if self._json is None:
            raise ValueError("keine JSON-Antwort")
        return self._json


_ODDS_EVENTS = [{
    "home_team": "Bayern Munich", "away_team": "Borussia Dortmund",
    "commence_time": "2026-09-19T18:30:00Z",
    "bookmakers": [
        {"markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 1.90},
                {"name": "Draw", "price": 3.60},
                {"name": "Borussia Dortmund", "price": 3.40}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "point": 2.5, "price": 1.85},
                {"name": "Under", "point": 2.5, "price": 1.95}]}
        ]},
        {"markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 1.88},
                {"name": "Draw", "price": 3.70},
                {"name": "Borussia Dortmund", "price": 3.50}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "point": 2.5, "price": 1.87}]}
        ]}
    ]
}]


def test_seite_zeigt_spieltag_und_spiele_aus_der_db(client, db, admin_user, competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    md = get_current_matchday()
    _mk_match(db, competition, teams, md, 24)
    r = client.get("/admin/tip-optimizer")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "FC Bayern München" in html and "Borussia Dortmund" in html
    assert 'id="to-config"' in html
    # Tippliste zum Übertragen wurde auf Wunsch entfernt (keine Regression)
    assert 'id="to-tiplist"' not in html and "Tippliste zum Übertragen" not in html
    assert "Quoten online laden" in html
    # aktueller Spieltag ist Default
    assert f'"md": {md}' in html
    # Saison + Anstoss-ISO in der Config (für Jahreswechsel-tauglichen
    # Speicher-Schlüssel und Ortszeit-Umrechnung im Browser)
    assert '"season": "2025/26"' in html
    assert 'data-kick="2' in html


def test_seite_ist_nur_fuer_admin(client, db, user, competition, teams):
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    assert client.get("/admin/tip-optimizer").status_code == 403
    assert client.get("/admin/tip-optimizer/odds").status_code == 403


def test_spieltagwechsel_per_param(client, db, admin_user, competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    m_a = _mk_match(db, competition, teams, 3, 24)
    _mk_match(db, competition, teams, 5, 48)
    html_a = client.get("/admin/tip-optimizer?md=3").get_data(as_text=True)
    html_b = client.get("/admin/tip-optimizer?md=5").get_data(as_text=True)
    assert 'data-idx="0"' in html_a and 'value="3" selected' in html_a
    assert 'value="5" selected' in html_b
    assert "Keine Spiele" not in html_a and "Keine Spiele" not in html_b
    assert m_a.home_team.name in html_a


def test_leerer_spieltag_meldet_keine_spiele(client, db, admin_user, competition):
    _login(client, admin_user)
    _use_test_comp(client)
    html = client.get("/admin/tip-optimizer?md=99").get_data(as_text=True)
    assert "Keine Spiele für Spieltag 99" in html


def test_odds_endpunkt_ohne_key_treibt_kein_http(client, db, admin_user, monkeypatch):
    import admin_tip_optimizer_routes as to_mod
    calls = []

    def _bohn(*a, **k):
        calls.append(1)
        raise AssertionError("ohne Key darf kein HTTP-Versuch stattfinden")

    monkeypatch.setattr(to_mod.requests, "get", _bohn)
    _login(client, admin_user)
    r = client.get("/admin/tip-optimizer/odds")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is False and d["stage"] == "no-key"
    assert "The-Odds-API" in d["msg"]
    assert calls == []


def test_odds_endpunkt_parsen_protokoll_und_budget(client, db, admin_user, monkeypatch):
    import admin_tip_optimizer_routes as to_mod
    from datasource_activity import entries
    calls = []
    monkeypatch.setattr(to_mod.requests, "get",
                        lambda *a, **k: calls.append(1) or
                        _FakeResp(200, _ODDS_EVENTS, {"x-requests-remaining": "412"}))
    set_setting(to_mod.SETTINGS_KEY, "TESTKEY")
    _login(client, admin_user)
    r = client.get("/admin/tip-optimizer/odds")
    d = r.get_json()
    assert d["ok"] is True and calls == [1]
    m = d["matches"][0]
    # Konsens über beide Buchmacher + Namens-Normalisierung auf die DB-Form
    assert m["h"] == "FC Bayern München" and m["a"] == "Borussia Dortmund"
    assert m["o1"] == 1.89 and m["ox"] == 3.65 and m["o2"] == 3.45 and m["ou25"] == 1.86
    assert m["books"] == 2 and "19.09." in m["kick"]
    assert d["credits_remaining"] == 412 and d["budget"] == 1
    # Server-Zeitstempel für die „Quotenstand“-Anzeige
    assert "ts" in d and d["ts"].endswith("Z")
    # Versuchs-Protokoll + Monatsbudget
    assert entries().get("the_odds_api", {}).get("ok") is True
    budget = json.loads(get_setting(to_mod.BUDGET_KEY, "{}"))
    assert budget["used"] == 1 and budget["remaining"] == 412


def test_odds_http_fehler_liefert_grund_im_protokoll(client, db, admin_user, monkeypatch):
    import admin_tip_optimizer_routes as to_mod
    from datasource_activity import entries
    monkeypatch.setattr(to_mod.requests, "get",
                        lambda *a, **k: _FakeResp(429, {"message": "Insufficient credits"}))
    set_setting(to_mod.SETTINGS_KEY, "TESTKEY")
    _login(client, admin_user)
    d = client.get("/admin/tip-optimizer/odds").get_json()
    assert d["ok"] is False and "429" in d["msg"]
    e = entries().get("the_odds_api", {})
    assert e.get("ok") is False and "429" in e.get("note", "")


def test_odds_budget_waechter_ruht_beim_cap(client, db, admin_user, monkeypatch):
    import admin_tip_optimizer_routes as to_mod
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    set_setting(to_mod.SETTINGS_KEY, "TESTKEY")
    set_setting(to_mod.BUDGET_KEY, json.dumps({"month": month, "used": 60, "remaining": 300}))
    calls = []

    def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("beim Budget-Cap darf kein HTTP-Versuch stattfinden")

    monkeypatch.setattr(to_mod.requests, "get", _boom)
    _login(client, admin_user)
    d = client.get("/admin/tip-optimizer/odds").get_json()
    assert d["ok"] is False and d["stage"] == "budget"
    assert calls == []


def test_settings_speichert_odds_key_nur_wenn_gefuellt(client, db, admin_user):
    _login(client, admin_user)
    r = client.post("/admin/settings", data={"the_odds_api_key": "TESTKEY123"}, follow_redirects=True)
    assert r.status_code == 200
    assert get_setting("the_odds_api_key", "") == "TESTKEY123"
    # leer übergeben = Key bleibt unverändert (Muster wie die anderen Tokens)
    client.post("/admin/settings", data={}, follow_redirects=True)
    assert get_setting("the_odds_api_key", "") == "TESTKEY123"


def test_sync_seite_listet_neue_quelle(client, db, admin_user):
    _login(client, admin_user)
    html = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "The-Odds-API · Tipp-Optimizer-Quoten" in html


def test_odds_median_ignoriert_ausreisser_buchmacher():
    """Konsens-Quoten sind der Median: eine Sonderquote eines kleinen
    Buchmachers (hier 4,00 statt ~1,90) darf den Konsens nicht verziehen."""
    import admin_tip_optimizer_routes as to_mod
    events = [{
        "home_team": "Bayern Munich", "away_team": "Borussia Dortmund",
        "commence_time": "2026-09-19T18:30:00Z",
        "bookmakers": [
            {"markets": [{"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 1.88},
                {"name": "Draw", "price": 3.60},
                {"name": "Borussia Dortmund", "price": 3.40}]}]},
            {"markets": [{"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 1.90},
                {"name": "Draw", "price": 3.70},
                {"name": "Borussia Dortmund", "price": 3.50}]}]},
            {"markets": [{"key": "h2h", "outcomes": [
                {"name": "Bayern Munich", "price": 4.00},  # Ausreißer
                {"name": "Draw", "price": 3.65},
                {"name": "Borussia Dortmund", "price": 3.45}]}]},
        ]
    }]
    m = to_mod._parse_odds_events(events)[0]
    assert m["o1"] == 1.90 and m["ox"] == 3.65 and m["o2"] == 3.45
    assert m["books"] == 3
    # Zum Vergleich: arithmetisches Mittel hätte 2,593 / 3,65 / 3,45 ergeben.


def _mk_finished(db, competition, teams, home_i, away_i, hs, as_):
    m = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[home_i].id,
        away_team_id=teams[away_i].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status="finished",
        home_score=hs,
        away_score=as_,
    )
    db.session.add(m)
    db.session.commit()
    return m


def _strong_league(db, competition, teams):
    """8 fertige Spiele: Team 0 (A) stark, Team 3 (D) schwach, Rest dazwischen."""
    _mk_finished(db, competition, teams, 0, 1, 3, 0)
    _mk_finished(db, competition, teams, 0, 2, 4, 1)
    _mk_finished(db, competition, teams, 0, 3, 5, 0)
    _mk_finished(db, competition, teams, 1, 3, 2, 0)
    _mk_finished(db, competition, teams, 2, 3, 3, 0)
    _mk_finished(db, competition, teams, 1, 2, 1, 1)
    _mk_finished(db, competition, teams, 3, 0, 0, 3)
    _mk_finished(db, competition, teams, 3, 1, 0, 2)


def test_saisondaten_fit_teamstaerken_und_priors(db, competition, teams):
    """Aus den fertigen Spielen entstehen Teamstärken und λ-Priors:
    die starke Mannschaft bekommt höhere λ-Priors, die schwache niedrigere."""
    from tip_optimizer_model import fit_season_model, prior_lambdas
    _strong_league(db, competition, teams)
    model = fit_season_model(list(
        Match.query.filter_by(competition_id=competition.id).all()))
    assert model["fitted"] is True and model["n"] == 8
    # Faktoren und Torsumme aus den Daten (nicht mehr die Defaults)
    assert all(0.5 <= r <= 1.8 for r in model["rho"])
    assert 2.0 <= model["goal_prior"] <= 4.5
    a, d = model["strengths"][teams[0].name], model["strengths"][teams[3].name]
    assert a[0] > 1.0 > d[0], "Angriff: A über, D unter Ligaschnitt"
    assert a[1] < 1.0 < d[1], "Abwehr: A besser, D schlechter als Ligaschnitt"
    p_ad = prior_lambdas(model, teams[0].name, teams[3].name)
    p_da = prior_lambdas(model, teams[3].name, teams[0].name)
    assert p_ad[0] > 2.0 and p_ad[1] < 0.8, "A–D: hoher Heim-λ, niedriger Gast-λ"
    assert p_da[0] < 1.0 and p_da[1] > 2.0, "D–A: umgekehrt (D als Heim unter Schnitt)"
    assert p_ad[0] > p_da[1] and p_ad[1] < p_da[0], "starke Seite: höheres λ in beiden Rollen"


def test_saisondaten_fit_fallback_ohne_spiele(db, competition, teams):
    """Zu wenige fertige Spiele => statische Defaults, kein Fit."""
    from tip_optimizer_model import fit_season_model
    model = fit_season_model(list(
        Match.query.filter_by(competition_id=competition.id).all()))
    assert model["fitted"] is False
    assert model["rho"] == [1.0, 1.09, 0.97]
    assert model["goal_prior"] == 3.20
    assert model["strengths"] == {}


def _config_island(html):
    """#to-config-Insel parsen (tojson escaping unangreifbar machen)."""
    import re
    m = re.search(r'id="to-config">\s*(\{.*?\})\s*</script>', html, re.S)
    assert m, "Config-Insel fehlt"
    return json.loads(m.group(1))


def test_seite_trägt_saisondaten_anker_im_config(client, db, admin_user, competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    md = get_current_matchday()
    _mk_match(db, competition, teams, md, 24)
    _strong_league(db, competition, teams)
    html = client.get("/admin/tip-optimizer").get_data(as_text=True)
    cfg = _config_island(html)
    assert "goal_prior" in cfg and "rho" in cfg and "priors" in cfg
    assert "FC Bayern München|Borussia Dortmund" in cfg["priors"], "Prior-Schlüssel = Heim|Gast"
    assert len(cfg["priors"]["FC Bayern München|Borussia Dortmund"]) == 2
    assert "aus den 8 fertigen Spielen" in html, "Anzahl der Datenquelle wird genannt"


def test_seite_ohne_saisondaten_zeigt_default_hinweis(client, db, admin_user, competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    md = get_current_matchday()
    _mk_match(db, competition, teams, md, 24)
    html = client.get("/admin/tip-optimizer").get_data(as_text=True)
    assert "Noch keine Saisondaten-Anker" in html
    assert _config_island(html)["rho"] == [1.0, 1.09, 0.97]


def test_js_engine_modul_und_anbindung():
    """Engine steht in to_engine.js (node-testbar, UMD-Export) und die UI
    bezieht sie über TOEngine inkl. Saisondaten-Ankern."""
    eng = open("static/js/to_engine.js", encoding="utf-8").read()
    ui = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    assert "function fitLambdas(target, ex, rho, prior, goalPrior)" in eng
    assert "module.exports = api" in eng
    assert "TOEngine" in ui and "priorFor" in ui and "CFG.priors" in ui
    # Engine-Skript wird VOR der UI geladen
    assert tpl.index("to_engine.js") < tpl.index("js/tip_optimizer.js")


def test_js_hygiene_und_joker_logik_im_quelltext():
    """Quelltext-Guard für die Browser-Seite (wie bei live.js/leaderboard):
    Saison-Speicher-Schlüssel, Ortszeit, Quoten-Stempel, Methodenvergleich,
    Plausibilitäts-Warnung und Joker-Regel müssen erhalten bleiben."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    # E: Jahreswechsel-tauglicher Speicher-Schlüssel
    assert '"to_" + (CFG.season || "x") + "_md_" + CFG.md' in js
    # G: Anstoss in der Ortszeit des Browsers
    assert 'querySelector(".to-kick")' in js and "toLocaleTimeString" in js
    # F: Quoten-Stempel aus dem letzten Online-Abruf
    assert '"_load"' in js and "loadStamp" in js
    # D: Methodenvergleich Power vs. proportional
    assert "AAlt" in js and "Methode-empfindlich" in js
    # H: Plausibilitäts-Warnung bei unplausiblen Marge/Mini-Quoten
    assert "oddWarn" in js
    # C: Joker-Vorschlag = Spiel mit höchstem Erwartungswert
    assert "#to-joker" in js and "analyzed[ji].ep" in js
    # Online-Quoten: Spiele, die beim Online-Laden ohne 1X2 zurückbleiben,
    # werden im Statuszeilen-Text sichtbar (stille Ausfälle nicht mehr)
    assert "unmatched" in js and "Nicht zugeordnet (Name)" in js


# ============================================================
# Modellgüte (Runde 58): Walk-Forward-Backtest + Vorhersage-Speicherung
# ============================================================

def test_ep_tabelle_stimmt_mit_bruttosumme_ueberein():
    """Die O(N²)-EP-Tabelle muss exakt der Brutto-Summe über die ganze
    Treffermatrix entsprechen (sonst würde der Optimizer andere Tipps als
    die JS-Engine liefern)."""
    from tip_optimizer_model import build_matrix, ep_table, tip_points
    M = build_matrix(1.6, 1.2, 0.97, 0.02, 0.01)
    T = ep_table(M)  # dict {(th, ta): ep}, Gitter 0..7 wie die Engine
    worst = 0.0
    for (th, ta), ep in T.items():
        # M[Heim][Auswärts] – Indexkonvention wie to_engine.js:69
        brutto = sum(tip_points(h, a, th, ta) * M[h][a] for a in range(12) for h in range(12))
        worst = max(worst, abs(ep - brutto))
    assert len(T) == 64 and worst < 1e-9


def _fertige_saison_machen(db, competition, teams, n_matchdays=4, pro_md=4):
    """Bestimmte, reproduzierbare Saisondaten (alle fertig, Ergebnis nach
    Muster – kein Zufall, damit der Test stabil bleibt)."""
    scores = [(2, 1), (0, 0), (1, 0), (3, 2), (2, 0), (1, 1), (0, 1), (2, 1),
              (1, 0), (0, 2), (2, 2), (3, 0), (1, 2), (2, 1), (0, 0), (1, 1)]
    now = datetime.now(timezone.utc)
    for md in range(1, n_matchdays + 1):
        for i in range(pro_md):
            hg, ag = scores[(md - 1) * pro_md + i]
            m = Match(
                competition_id=competition.id, matchday=md,
                home_team_id=teams[i % 4].id, away_team_id=teams[(i + 1) % 4].id,
                kickoff=now - timedelta(days=(n_matchdays - md) * 8 + 1, hours=i),
                status="finished", home_score=hg, away_score=ag)
            db.session.add(m)
    db.session.commit()


def test_backtest_walk_forward_bewertet_nach_acht_vorgaengern(db, competition, teams):
    """Walk-Forward: Spieltage 1+2 (zu wenige Vorgänger) werden übersprungen,
    ST 3+4 werden bewertet; alle Kennzahlen + Baselines müssen stehen."""
    from tip_optimizer_model import backtest
    _fertige_saison_machen(db, competition, teams)
    matches = Match.query.filter_by(competition_id=competition.id).all()
    res = backtest(matches)
    assert res["n_matches"] == 8 and res["n_matchdays"] == 2
    assert [r["md"] for r in res["per_md"]] == [3, 4]
    for key in ("ep_per_match", "pge2_rate", "top1_rate", "top3_rate",
                "goals_mae", "hit1x2", "hit1x2_immer_heim", "brier",
                "brier_immer_heim", "brier_liga", "brier_zufall", "note"):
        assert key in res
    assert 0.0 <= res["hit1x2"] <= 1.0
    assert "Ohne Odds-Anker" in res["note"]


def test_backtest_zu_wenig_spiele_liefert_hinweis(db, competition, teams):
    """Unter der Mindestanzahl gibt es eine saubere Meldung statt Zahlen."""
    from tip_optimizer_model import backtest
    _fertige_saison_machen(db, competition, teams, n_matchdays=2, pro_md=3)
    matches = Match.query.filter_by(competition_id=competition.id).all()
    res = backtest(matches)
    assert res["n_matches"] == 0 and "8 fertige Spiele" in res["message"]


def test_backtest_endpunkt_verlangt_admin(client, db, admin_user, user, competition, teams):
    """Der Backtest-Endpunkt ist wie der Rest der Seite Admin-only."""
    _fertige_saison_machen(db, competition, teams)
    _login(client, user, password="testpass123")
    _use_test_comp(client)
    r = client.get("/admin/tip-optimizer/backtest")
    assert r.status_code == 403
    client.get("/auth/logout", follow_redirects=True)
    _login(client, admin_user)
    r = client.get("/admin/tip-optimizer/backtest")
    assert r.status_code == 200
    assert r.get_json()["n_matches"] == 8


def _vorhersage_run_speichern(client, matchday, items):
    return client.post("/admin/tip-optimizer/snapshot",
                       data=json.dumps({"matchday": matchday, "items": items}),
                       content_type="application/json")


def test_snapshot_endpunkt_speichert_nur_gueltige_spiele(client, db, admin_user, competition, teams):
    """Snapshot akzeptiert nur Matches des angegebenen Spieltags in der
    aktiven Competition (Cap 20) und lehnt krumme Nutzlasten ab."""
    now = datetime.now(timezone.utc)
    m_a = Match(competition_id=competition.id, matchday=3,
                home_team_id=teams[0].id, away_team_id=teams[1].id,
                kickoff=now - timedelta(days=2), status="finished",
                home_score=2, away_score=1)
    m_b = Match(competition_id=competition.id, matchday=3,
                home_team_id=teams[2].id, away_team_id=teams[3].id,
                kickoff=now - timedelta(days=2), status="finished",
                home_score=0, away_score=0)
    m_c = Match(competition_id=competition.id, matchday=5,
                home_team_id=teams[0].id, away_team_id=teams[2].id,
                kickoff=now + timedelta(days=2), status="scheduled")
    db.session.add_all([m_a, m_b, m_c])
    db.session.commit()
    _login(client, admin_user)
    _use_test_comp(client)

    full = {"ep": 1.5, "p1": 0.5, "px": 0.25, "p2": 0.25,
            "pge2": 0.75, "pge3": 0.2, "pex": 0.15,
            "lh": 2.0, "la": 0.9, "o1": 1.9, "ox": 3.3, "o2": 4.2}
    r = _vorhersage_run_speichern(client, 3, [
        dict(match_id=m_a.id, tip_h=2, tip_a=1, **full),
        dict(match_id=m_b.id, tip_h=0, tip_a=0, **full),
        dict(match_id=m_c.id, tip_h=1, tip_a=0, **full),      # falscher Spieltag
        dict(match_id=999999, tip_h=1, tip_a=1, **full),      # unbekanntes Match
    ])
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["count"] == 2

    # Krumme Nutzlasten:
    assert _vorhersage_run_speichern(client, 99, [{"match_id": m_a.id, "tip_h": 1, "tip_a": 1}]).status_code == 400
    assert _vorhersage_run_speichern(client, 3, []).status_code == 400

    from models import OptimizerRun, OptimizerRunTip
    runs = OptimizerRun.query.all()
    assert len(runs) == 1 and runs[0].matchday == 3
    tips = OptimizerRunTip.query.all()
    assert len(tips) == 2
    tip_a = [t for t in tips if t.match_id == m_a.id][0]
    assert (tip_a.tip_h, tip_a.tip_a) == (2, 1)
    assert abs(tip_a.ep - 1.5) < 1e-9 and abs(tip_a.pge2 - 0.75) < 1e-9
    assert tip_a.match is m_a  # Beziehung zur Auswertung


def test_modellguete_rechnet_abgeschlossenen_spieltag_ab(client, db, admin_user, competition, teams):
    """Gespeicherte Vorhersagen eines abgelaufenen Spieltags erscheinen nach
    Abschluss mit Erwartung vs. Realität auf der Admin-Seite."""
    now = datetime.now(timezone.utc)
    m3 = Match(competition_id=competition.id, matchday=3,
               home_team_id=teams[0].id, away_team_id=teams[1].id,
               kickoff=now - timedelta(days=2), status="finished",
               home_score=2, away_score=1)
    m5 = Match(competition_id=competition.id, matchday=5,
               home_team_id=teams[2].id, away_team_id=teams[3].id,
               kickoff=now + timedelta(days=2), status="scheduled")
    db.session.add_all([m3, m5])
    db.session.commit()
    _login(client, admin_user)
    _use_test_comp(client)

    r = _vorhersage_run_speichern(client, 3, [{
        "match_id": m3.id, "tip_h": 2, "tip_a": 1,
        "ep": 1.5, "p1": 0.5, "px": 0.25, "p2": 0.25,
        "pge2": 0.75, "pge3": 0.2, "pex": 0.15,
        "lh": 2.0, "la": 0.9, "o1": 1.9, "ox": 3.3, "o2": 4.2}])
    assert r.status_code == 200 and r.get_json()["ok"] is True

    html = client.get("/admin/tip-optimizer", follow_redirects=True).get_data(as_text=True)
    assert "Modellgüte" in html and "ST 3" in html
    # Tipp 2:1, Endstand 2:1 → exakt → 4 P real; Brier (3-Wege):
    # (0.5−1)² + 0.25² + 0.25² = 0.375
    assert "4.00" in html and "0.375" in html and "100 %" in html


def test_evaluate_run_tips_bis_zum_spieltagsende_none():
    """Keine Auswertung, während auch nur ein Match offen ist; danach exakt."""
    from types import SimpleNamespace
    from models import OptimizerRunTip
    from tip_optimizer_model import evaluate_run_tips
    tip = OptimizerRunTip(tip_h=2, tip_a=1, ep=1.5, p1=0.5, pge2=0.75)
    tip.match = None
    assert evaluate_run_tips([tip]) is None
    tip.match = SimpleNamespace(status="finished", home_score=2, away_score=1)
    res = evaluate_run_tips([tip])
    assert res["n"] == 1 and res["ep_real"] == 4.0  # Tipp 2:1 exakt → 4 Punkte
    assert res["pge2_rate"] == 1.0 and abs(res["brier"] - 0.25) < 1e-9


def test_js_modellguete_anbindung():
    """Quelltext-Guard: Snapshot-/Backtest-Buttons, Voll-Zustand pro Spiel
    (data-match-id) und beide Endpunkte müssen verdrahtet sein."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    assert "to-btn-snapshot" in js and "to-btn-backtest" in js
    assert "lastFull" in js and "data-match-id" in js
    assert "/admin/tip-optimizer/snapshot" in js and "/admin/tip-optimizer/backtest" in js
    assert 'data-match-id="{{ m.id }}"' in tpl and 'id="to-backtest"' in tpl
    assert 'id="to-btn-snapshot"' in tpl and 'id="to-btn-backtest"' in tpl


def test_smartphone_anpassungen_der_optimizer_seite():
    """Mobile-First-Guard: Auf schmalen Screens Buttons vollflaechig
    uebereinander (griffgaeste Taps), Modellguete-Zusammenfassung als
    Stats-Raster statt dichter Zeile, weite Tabellen behalten eine
    Mindestbreite und bleiben wischbar statt gequetscht."""
    css = open("static/css/style.css", encoding="utf-8").read()
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    assert ".to-statgrid" in css and "flex-direction: column" in css
    assert ".btnrow .btn-primary, .btnrow .btn-ghost { width: 100%; }" in css
    assert "-webkit-overflow-scrolling: touch" in css
    assert "min-width: 640px" in css and "min-width: 460px" in css
    assert "to-statgrid" in tpl and "to-tblwide" in tpl
    assert "to-tblwide-narrow" in js
    # Tippliste zum Übertragen entfernt (Nutzerwunsch (63)): kein Textfeld,
    # kein Copy-Button mehr — Snapshot-Button bleibt in der Ergebniskarte
    assert "to-tiplist" not in js and "to-btn-copy" not in js
    assert "to-btn-snapshot" in tpl
    # Info-Block „So funktioniert’s“ einklappbar (spart Smartphone-Platz)
    assert '<details class="card to-info">' in tpl and "<summary>" in tpl
    assert "to-info[open] summary::before" in css
    # Unklare Abkürzungen erklärt: Glossar im Info-Block + Tooltips an
    # den Spaltenköpfen (λ, EP, Sicherheit, Brier, …)
    assert "Abkürzungen" in tpl and "to-abbrev" in tpl
    assert "Expected Points" in tpl and "Beide Teams treffen" in tpl
    assert "title=" in js and "Vom Modell erwartete Tore" in js
    assert ".to-abbrev-body dt" in css
    # Brier konkret erklärt (mit Beispiel) — Glossar + alle Brier-Anzeigen
    assert "Beispiel: Schreibt es 70 %" in tpl
    assert "Zuverlässigkeit der 1X2-Prozentzahlen" in tpl  # Stat-Karte
    assert "Zuverlässigkeit der Prozentzahlen" in js  # Backtest-Vergleichszeile


def test_odds_namen_alias_trifft_den_db_namen():
    """The-Odds-API-Namen werden auf die echten DB-Vereinsnamen gemappt –
    inkl. Elversberg: Das frühere Mapping auf 'SV Elversberg' traf nicht
    den DB-Namen 'SV 07 Elversberg' (das '07' bricht auch die Teilstring-
    Übereinstimmung), wodurch das Schalke-Spiel beim Online-Laden stumm
    ohne Quoten blieb."""
    import admin_tip_optimizer_routes as to_mod
    events = [{
        "home_team": "FC Schalke 04", "away_team": "SV Elversberg",
        "commence_time": "2026-09-19T15:30:00Z",
        "bookmakers": [{"markets": [{"key": "h2h", "outcomes": [
            {"name": "FC Schalke 04", "price": 2.10},
            {"name": "Draw", "price": 3.50},
            {"name": "SV Elversberg", "price": 3.30}]}]}],
    }]
    m = to_mod._parse_odds_events(events)[0]
    assert m["h"] == "FC Schalke 04" and m["a"] == "SV 07 Elversberg"


# ============================================================
# Quoten-Bewegung (Runde 62): Zeitstempel-Stände + Endpunkt + Anzeige
# ============================================================

def _mk_match_md(db, competition, teams, matchday, hours_from_now):
    m = Match(
        competition_id=competition.id, matchday=matchday,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=hours_from_now),
        status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def _post_odds_log(client, matchday, items):
    return client.post("/admin/tip-optimizer/odds-log",
                       data=json.dumps({"matchday": matchday, "items": items}),
                       content_type="application/json")


def test_odds_log_endpunkt_speichert_quoten_staende(client, db, admin_user, competition, teams):
    """Der Odds-Log-Endpunkt nimmt nur Matches des angegebenen Spieltags in
    der aktiven Competition an (Cap 20) und legt einen Zeitstempel-Stand an."""
    from models import OddsSnapshot
    m_a = _mk_match_md(db, competition, teams, 4, 48)
    m_b = _mk_match_md(db, competition, teams, 4, 50)
    m_c = _mk_match_md(db, competition, teams, 5, 96)
    _login(client, admin_user)
    _use_test_comp(client)

    r = _post_odds_log(client, 4, [
        {"match_id": m_a.id, "o1": 1.90, "ox": 3.30, "o2": 4.20, "ou25": 1.85},
        {"match_id": m_b.id, "o1": 2.50, "ox": 3.10, "o2": 2.90},
        {"match_id": m_c.id, "o1": 2.00, "ox": 3.00, "o2": 3.60},   # falscher Spieltag
        {"match_id": 999999, "o1": 2.00, "ox": 3.00, "o2": 3.60},   # unbekannt
    ])
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["count"] == 2
    assert _post_odds_log(client, 99, [{"match_id": m_a.id, "o1": 2.0, "ox": 3.0, "o2": 3.0}]).status_code == 400
    assert _post_odds_log(client, 4, []).status_code == 400

    snaps = OddsSnapshot.query.order_by(OddsSnapshot.id).all()
    assert len(snaps) == 2
    s_a = [s for s in snaps if s.match_id == m_a.id][0]
    assert abs(s_a.o1 - 1.90) < 1e-9 and abs(s_a.ou25 - 1.85) < 1e-9
    assert s_a.source == "online" and s_a.match is m_a and s_a.matchday == 4
    assert s_a.created_at is not None


def test_odds_log_endpunkt_verlangt_admin(client, db, admin_user, user, competition, teams):
    """Wie der Rest der Optimizer-Seite: nur für Admins."""
    m = _mk_match_md(db, competition, teams, 4, 48)
    _login(client, user, password="testpass123")
    _use_test_comp(client)
    assert _post_odds_log(client, 4, [{"match_id": m.id, "o1": 2.0, "ox": 3.0, "o2": 3.0}]).status_code == 403
    client.get("/auth/logout", follow_redirects=True)
    _login(client, admin_user)
    assert _post_odds_log(client, 4, [{"match_id": m.id, "o1": 2.0, "ox": 3.0, "o2": 3.0}]).status_code == 200


def test_seite_zeigt_quoten_bewegung_mit_einzelstaende(client, db, admin_user, competition, teams):
    """Zwei Stände desselben Spiels zeigen die Bewegung (↓/↑), ein einzelner
    Stand nur den Wert; ohne Historie der ℹ️-Hinweis."""
    from models import OddsSnapshot
    m_a = _mk_match_md(db, competition, teams, 4, 48)
    m_b = _mk_match_md(db, competition, teams, 4, 50)
    _mk_match_md(db, competition, teams, 6, 120)  # Fallback-Prüfung: Spiel ohne Historie
    t0 = datetime.now(timezone.utc) - timedelta(hours=3)
    t1 = datetime.now(timezone.utc)
    db.session.add(OddsSnapshot(competition_id=competition.id, match_id=m_a.id,
                                matchday=4, created_at=t0, o1=1.90, ox=3.30, o2=4.20))
    db.session.add(OddsSnapshot(competition_id=competition.id, match_id=m_a.id,
                                matchday=4, created_at=t1, o1=1.70, ox=3.40, o2=4.50))
    db.session.add(OddsSnapshot(competition_id=competition.id, match_id=m_b.id,
                                matchday=4, created_at=t1, o1=2.50, ox=3.10, o2=2.90))
    db.session.commit()
    _login(client, admin_user)
    _use_test_comp(client)

    html = client.get("/admin/tip-optimizer?md=4", follow_redirects=True).get_data(as_text=True)
    assert "Quoten-Bewegung" in html
    assert "1,90 → 1,70" in html and "3,30 → 3,40" in html
    assert "↓" in html and "↑" in html
    assert "2 · " in html  # Stände-Zelle mit Zeitstempel

    html6 = client.get("/admin/tip-optimizer?md=6", follow_redirects=True).get_data(as_text=True)
    assert "Noch keine Quoten-Historie" in html6


def test_js_quoten_historie_anbindung():
    """Quelltext-Guard: Online-Quoten werden nach dem Befüllen als
    Zeitstempel-Stand gemerkt (mit Hinweis, wenn das Loggen scheitert)."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    assert "/admin/tip-optimizer/odds-log" in js and "logItems" in js
    assert "Historie:" in js
    assert "Quoten-Bewegung" in tpl


def test_snapshot_endpunkt_serverfehler_liefert_json(client, db, admin_user, competition, teams, monkeypatch):
    """Ein DB-Fehler (z. B. fehlende Tabelle) liefert JSON mit Ursache statt
    HTML-500 — sonst zeigt die UI nur 'Speichern nicht möglich' ohne Grund."""
    m = _mk_match_md(db, competition, teams, 4, 48)
    _login(client, admin_user)
    _use_test_comp(client)

    def boom(*a, **k):
        raise RuntimeError('sqlite3.OperationalError: no such table: optimizer_runs')

    monkeypatch.setattr(db.session, "flush", boom)
    r = client.post("/admin/tip-optimizer/snapshot",
                    data=json.dumps({"matchday": 4,
                                     "items": [{"match_id": m.id, "tip_h": 2, "tip_a": 1, "ep": 1.5}]}),
                    content_type="application/json")
    assert r.status_code == 500
    body = r.get_json()
    assert body["ok"] is False
    assert "Serverfehler" in body["msg"] and "no such table" in body["msg"]


def test_json_endpunkte_funktionieren_mit_csrf_wie_in_produktion(client, app, db, admin_user, competition, teams):
    """TestConfig schaltet CSRF AUS, Produktion (config.py) hat es AN: Mit
    aktivem CSRF dürfen die beiden fetch()-Endpunkte (exempt) trotzdem
    funktionieren — sonst 'The CSRF token is missing' (HTTP 400)."""
    m = _mk_match_md(db, competition, teams, 4, 48)
    _login(client, admin_user)
    _use_test_comp(client)
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        # Kontrolle: Ein NICHT-exempter POST ohne Token scheitert wirklich
        r_ctrl = client.post("/admin/purge-demo")
        assert r_ctrl.status_code == 400 and "CSRF" in r_ctrl.get_data(as_text=True)
        r = client.post("/admin/tip-optimizer/odds-log",
                        data=json.dumps({"matchday": 4,
                                         "items": [{"match_id": m.id, "o1": 2.0, "ox": 3.0, "o2": 3.0}]}),
                        content_type="application/json")
        assert r.status_code == 200 and r.get_json()["ok"] is True
        r2 = client.post("/admin/tip-optimizer/snapshot",
                         data=json.dumps({"matchday": 4,
                                          "items": [{"match_id": m.id, "tip_h": 2, "tip_a": 1, "ep": 1.5}]}),
                         content_type="application/json")
        assert r2.status_code == 200 and r2.get_json()["ok"] is True
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_snapshot_meldung_steht_bei_button_nicht_unten():
    """Die Save-Meldung (Erfolg UND Fehler) erscheint direkt neben dem
    Button (#to-snap-msg) — kein Fix-Toast am unteren Rand mehr (Nutzerwunsch)."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    css = open("static/css/style.css", encoding="utf-8").read()
    assert 'id="to-snap-msg"' in tpl
    # Kein Bottom-Toast mehr
    assert 'id="to-toast"' not in tpl and "#to-toast" not in css
    assert "toast(" not in js
    # Erfolg + Fehler + Warnung laufen über die Inline-Meldung beim Button
    assert "snapMsg" in js and "to-snap-msg" in js
    assert "Gespeichert (" in js
    assert 'setStatus("Nichts zu speichern' not in js  # nicht mehr oben im Status


def test_js_dateien_haben_valide_syntax():
    """Syntaxfehler in den Optimizer-Dateien töten die GANZE Seite (kein
    Button funktioniert) — deshalb harter Syntax-Check statt nur String-
    Guards. (Fall aus (67): verwaiste Klammer nach toast()-Entfernung.)"""
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("node nicht verfügbar")
    for f in ("static/js/tip_optimizer.js", "static/js/to_engine.js"):
        r = subprocess.run([node, "--check", f], capture_output=True, text=True, cwd=".")
        assert r.returncode == 0, "JS-Syntaxfehler in %s:\n%s" % (f, r.stderr[:400])


def test_abschnitte_anordnung_ergebnis_zuerst_eingabe_einklappbar():
    """Seiten-Logik (Nutzerwunsch (70)): Ergebnis zuerst, die lange Quoten-
    Eingabe einklappbar (automatisch offen ohne Quoten, geschlossen mit
    Quoten), Hilfese/Erweitert ans Ende."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    css = open("static/css/style.css", encoding="utf-8").read()
    # Struktur: Ergebnis → Quoten-Fold → Modellgüte/Backtest → Hilfe/Erweitert
    assert 'id="to-input-fold"' in tpl and 'id="to-fold-state"' in tpl
    i_summary = tpl.index('id="to-summary-card"')
    i_fold = tpl.index('id="to-input-fold"')
    i_model = tpl.index("Modellgüte – gespeicherte Vorhersagen")
    i_help = tpl.index("So funktioniert’s")
    i_adv = tpl.index("card to-advanced")
    assert i_summary < i_fold < i_model < i_help < i_adv
    # Karten stehen IM Fold
    assert tpl.index('data-match-id="') > i_fold
    # JS: Auto-Regel (nur einmal), Live-Zähler, Aktionen öffnen den Fold
    assert "foldInitialized" in js and "to-fold-state" in js
    assert js.count('foldC.open = true') >= 1  # Alle Felder leeren
    assert "foldL.open = true" in js  # Quoten online laden
    # Stil des Folds
    assert ".to-input-fold summary" in css


def test_quotenstand_mit_datum_besser_findbar():
    """Nutzerwunsch (71): Das Datum des letzten Quoten-Stands war nur als
    reine Uhrzeit in der Statuszeile versteckt. Jetzt: Datum + Uhrzeit in
    der Statuszeile UND ein persistenter, immer sichtbarer Chip in der
    Aktionszeile (oben), der sich nach jedem Online-Abruf aktualisiert."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    # Persistenter Chip oben
    assert 'id="to-load-chip"' in tpl
    assert "renderLoadChip" in js
    # Datum (nicht nur Uhrzeit)
    assert "toLocaleDateString" in js
    assert "Quotenstand: " in js
    # Chip wird beim Laden UND nach dem Online-Laden aktualisiert
    assert js.count("renderLoadChip()") >= 2


def test_zeitstempel_lokal_konsistent_dargestellt():
    """(72) Nutzer-Fund: Chip zeigte „14:04“ (lokal), Quoten-Bewegungs-Karte
    „12:04“ (UTC) für denselben Abruf. Jetzt liefert der Server UTC-ISO
    (data-ts-utc) und die JS rechnet ALLE Zeitstempel der Seite in lokale
    Zeit um — einheitlich, ohne Kopfrechnen."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    assert tpl.count("data-ts-utc") >= 3  # Quoten-Bewegung (zuletzt + je Spiel) + Modellgüte
    assert "localizeTimestamps" in js and "Gespeichert (lokale Zeit)" in js
    # Server-Helfer: UTC -> ISO mit Z (ohne Z parst JS die Zeit als lokal!)
    from admin_tip_optimizer_routes import _iso_z
    naive = datetime(2026, 9, 19, 12, 4, 5)
    assert _iso_z(naive) == "2026-09-19T12:04:05Z"
    aware = datetime(2026, 9, 19, 14, 4, 5, tzinfo=timezone(timedelta(hours=2)))
    assert _iso_z(aware) == "2026-09-19T12:04:05Z"
    assert _iso_z(None) == ""
