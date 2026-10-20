"""(130) Tipp-Optimizer: Einsteiger-Überarbeitung der Darstellung.

Ziel: Einstieg in 3 Schritten (Quoten → Empfehlung → optional speichern),
Ergebnistabelle auf das Wesentliche verschlankt (Spiel · Tipp · EP ·
Sicherheit — Fachdaten λ/1X2/wahrsch. Ergebnis stecken im Spiel-Akkordeon),
die fünf Experten-Karten (Modellgüte, Kalibrierung, Mitspieler, Quoten-
Bewegung, Backtest) standardmäßig EINGEK LAPPT mit Klartext-Summary.

Der JS-DOM-Vertrag bleibt unangetastet: alle to-*-Ids/Klassen, die
tip_optimizer.js ansieht, müssen weiter im Markup existieren.
"""
from datetime import datetime, timedelta, timezone

from models import Match
from stats import get_current_matchday


def _login(client, user):
    client.post("/auth/login", data={"email": user.email, "password": "admin123"},
                follow_redirects=True)


def _use_test_comp(client):
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"


def _mk_match(db, competition, teams):
    m = Match(competition_id=competition.id, matchday=get_current_matchday(),
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=24),
              status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def _seite(client, db, admin_user, competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    _mk_match(db, competition, teams)
    r = client.get("/admin/tip-optimizer")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_intro_und_einstiegsreihenfolge(client, db, admin_user, competition,
                                        teams):
    """(130) 3-Schritte-Intro oben; Eingabe VOR Ergebnis; Ergebnis-Karte
    heißt klar 'Deine Empfehlungen' und hat den Leere-Hinweis."""
    html = _seite(client, db, admin_user, competition, teams)
    assert 'class="to-intro"' in html
    assert "1 · Quoten eintragen" in html
    assert "2 · Empfehlung lesen" in html
    assert "3 · Optional speichern" in html
    # Eingabe-Step kommt vor dem Ergebnis (Workflow-Reihenfolge):
    assert html.index('id="to-input-fold"') < html.index('id="to-summary-card"')
    assert "Schritt 2: Deine Empfehlungen" in html
    assert 'id="to-results-hint"' in html
    assert "erscheinen hier automatisch die Empfehlungen" in html


def test_experten_karten_eingeklappt_mit_klartext(client, db, admin_user,
                                                  competition, teams):
    """(130) Die 5 Experten-Karten sind <details> ohne 'open' und tragen
    Klartext-Summaries + 'noch keine Daten'-Marker bei leerer DB."""
    html = _seite(client, db, admin_user, competition, teams)
    assert html.count('<details class="card to-expert">') == 5
    assert 'to-expert" open' not in html
    assert "Wie gut ist das Modell bisher?" in html
    assert "Hält das Modell, was es verspricht?" in html
    assert "Wo hätte der Optimizer in der Rangfolge gestanden?" in html
    assert "Wie haben sich die Quoten bewegt?" in html
    assert "Backtest: Modell nur mit alten Daten testen" in html
    # DB ist leer → die 4 datengetriebenen Karten tragen den Marker
    # (Backtest ist immer verfuegbar und braucht keinen):
    assert html.count("noch keine Daten") == 4
    # Die klassischen Fach-Titel bleiben als h2 im aufgeklappten Zustand:
    assert "Modellgüte – gespeicherte Vorhersagen" in html
    assert "Kalibrierung &amp; Trend" in html


def test_js_ergebnistabelle_verschlankt_details_voll(client):
    """(130) Die JS-Tabelle zeigt 4 Spalten (Spiel/Tipp/EP/Sicherheit);
    λ, Modell-1X2 und wahrscheinlichstes Ergebnis stehen im Spiel-
    Akkordeon; Legende in Einsteiger-Sprache."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    thead = js[js.index('$("#to-results")'):]
    assert "<th>Spiel</th>" in thead and "Optimaler Tipp</th>" in thead
    assert ">EP</th>" in thead and ">Sicherheit</th>" in thead
    assert "λ H</th>" not in thead and "Wahrsch. Ergebnis</th>" not in thead
    assert 'colspan=\\"3\\"' in js and 'colspan=\\"9\\"' not in js
    assert "Modell-1X2" in js and "wahrscheinlichstes Ergebnis <b>" in js
    assert "Technik-Details (λ, faire Quoten, Top-3) stecken im Akkordeon je Spiel" in js
    # Einsteiger-Hinweis wird bei Ergebnissen ausgeblendet:
    assert '$("#to-results-hint")' in js

def test_adjuster_klemmt_lambda_rechenlogik_131(client):
    """(131) Der ±%-Adjuster klemmt lambda auf das Fit-Intervall (max 6,0) —
    sonst wuerde die Tor-Matrix ab ~98 % Abdeckung ranten (bis 8.4 moeglich)."""
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    assert js.count("Math.min(6, Math.max(0.05,") >= 4  # lh/la x Haupt-/Alt-Lauf
    eng = open("static/js/to_engine.js", encoding="utf-8").read()
    assert "var NMAX = 12" in eng
    assert 'typeof prior.w === "number"' in eng  # w=0 = Anker aus


def test_js_dom_vertrag_unveraendert(client, db, admin_user, competition,
                                     teams):
    """(130) Alle Hooks, die tip_optimizer.js ansieht, existieren weiter."""
    html = _seite(client, db, admin_user, competition, teams)
    for hook in ['id="to-config"', 'id="to-summary-card"', 'id="to-chips"',
                 'id="to-results"', 'id="to-details"', 'id="to-total"',
                 'id="to-joker"', 'id="to-btn-snapshot"', 'id="to-snap-msg"',
                 'id="to-input-fold"', 'id="to-fold-state"',
                 'id="to-btn-online"', 'id="to-btn-clear"',
                 'id="to-load-chip"', 'id="to-online-status"',
                 'id="to-margin"', 'id="to-rho0"', 'id="to-rhoD"',
                 'id="to-rho1"', 'id="to-backtest"', 'id="to-btn-backtest"',
                 'class="card to-card"', 'to-apply-paste', 'to-toggle-extras',
                 'to-o1', 'to-ox', 'to-o2', 'to-ou25', 'to-ou35', 'to-btts',
                 'to-adjh', 'to-adja', 'to-paste', "to-fair"]:
        assert hook in html, "JS-Hook fehlt: " + hook


def test_apply_als_meine_tipps_143():
    """(143) Nutzerwunsch: Empfehlungen per Knopfdruck in die echten Tipps
    (meyomey) uebernehmen — Button + JS-Vertrag (API, Joker-Max, Offen-Filter)."""
    tpl = open("templates/admin/tip_optimizer.html", encoding="utf-8").read()
    assert 'id="to-btn-apply"' in tpl
    assert 'id="to-apply-msg"' in tpl
    assert "Empfehlungen als meine Tipps übernehmen" in tpl
    # Reihenfolge: Uebernehmen ist die Primaer-Aktion und steht vor Modellguete
    assert tpl.index('id="to-btn-apply"') < tpl.index('id="to-btn-snapshot"')
    js = open("static/js/tip_optimizer.js", encoding="utf-8").read()
    assert 't.id === "to-btn-apply"' in js
    assert '"/api/tip/" + it.match_id' in js
    assert 'meta[name="csrf-token"]' in js          # wie quick_tip.js
    assert "kicks[it.match_id] > Date.now()" in js  # Offen-Filter vor Anstoss
    assert "open[ji].ep > jokerIt.ep" in js          # Joker = laufendes EP-Max
    assert "🃏 Joker: " in js
    assert "lastFull.filter(Boolean)" in js
    assert "abtn.disabled = true" in js              # Doppelklick-Schutz
