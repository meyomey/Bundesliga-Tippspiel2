"""Tests fuer die Spieltags-Trenner im Dashboard ((84)).

Die lange Liste der kommenden Spiele bekommt je Spieltag eine Trennzeile
mit ST-Kuerzel, „aktuell"-Markierung des laufenden Spieltags, Trennlinie
und Spielzahl. Muster aus Runde 79: den App-Fallback `COMPETITION` auf die
Test-Competition pinnen — dann zeigt das Dashboard ausschliesslich die
eigenen Test-Spiele, egal was create_app geseedet hat.
"""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Match


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def _spiel(db, competition, teams, spieltag, stunden_bis):
    m = Match(competition_id=competition.id, matchday=spieltag,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=stunden_bis),
              status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def test_dashboard_trennt_spieltage_mit_kuerzel(client, app, db, user,
                                                competition, teams, monkeypatch):
    """ST 5 (2 Spiele) und ST 6 (1 Spiel) -> zwei Trennzeilen in richtiger
    Reihenfolge. (86): KEINE Spielzahl mehr im Trenner — in der BL1 sind es
    immer 9, die Zahl war redundant."""

    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _spiel(db, competition, teams, 5, 48)
    _spiel(db, competition, teams, 6, 24 * 8)
    _login(client, user.email, "testpass123")
    resp = client.get("/dashboard")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'md-sep' in body
    assert 'ST 5' in body and 'ST 6' in body
    assert body.index('ST 5') < body.index('ST 6')
    assert 'md-sep-count' not in body   # (86) Spielzahl bewusst entfernt


def test_dashboard_markiert_aktuellen_spieltag(client, app, db, user,
                                               competition, teams, monkeypatch):
    """Der frueheste offene Spieltag (hier ST 5) traegt das „aktuell"-Chip,
    der spaetere nicht (Chip-Index liegt vor dem ST-6-Trenner)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _spiel(db, competition, teams, 6, 24 * 8)
    _login(client, user.email, "testpass123")
    resp = client.get("/dashboard")
    body = resp.get_data(as_text=True)
    assert 'md-sep-now' in body
    assert body.index('ST 5') < body.index('md-sep-now') < body.index('ST 6')


def test_dashboard_ohne_kommende_spiele_keine_trenner(client, app, db, user,
                                                      competition, monkeypatch):
    """Ohne jedes Spiel -> Empty-State, keine Trenner-Elemente."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    Match.query.delete(synchronize_session=False)
    db.session.commit()
    _login(client, user.email, "testpass123")
    resp = client.get("/dashboard")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'md-sep-label' not in body   # kein gerenderter Trenner (Skript-Text enthaelt 'md-sep-when' legitim)


def test_trenner_stil_vorhanden_quelltext_guard():
    """Selbstbeweis: Trenner sind ein neues, eigenes Element (CSS + Template)."""
    tpl = open('templates/dashboard.html', encoding='utf-8').read()
    css = open('static/css/style.css', encoding='utf-8').read()
    assert 'md-sep-label' in tpl and "ST {{ m.matchday }}" in tpl
    assert '.md-sep-line' in css and '.md-sep-now' in css


def test_trenner_enthaelt_tages_hook_mit_kickoff(client, app, db, user,
                                                 competition, teams, monkeypatch):
    """(85) Der Trenner traegt den data-utc-Hook (.md-sep-when) mit dem
    Kickoff des ersten Spiels der Gruppe — das JS fuellt 'heute'/'morgen'
    viewer-lokal; ohne JS bleibt der Chip leer (graceful)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'md-sep-when' in body and 'data-utc="' in body
    assert 'js/dash_days.js' in body


def test_dash_days_modul_und_kette_vorhanden():
    """(85) Quelltext-Guard: reines Logikmodul (Node-exportiert), Verdrahtung
    im Dashboard-Template, CSS-Klassen und CI-Schritt vorhanden."""
    modul = open('static/js/dash_days.js', encoding='utf-8').read()
    tpl = open('templates/dashboard.html', encoding='utf-8').read()
    css = open('static/css/style.css', encoding='utf-8').read()
    wf = open('.github/workflows/tests.yml', encoding='utf-8').read()
    assert 'module.exports' in modul and 'tagesLabel' in modul
    assert 'md-sep-when' in tpl and 'js/dash_days.js' in tpl
    # (88): Inline-Wiring gehoert jetzt ins Modul (Selbst-Init)
    assert 'querySelectorAll' not in tpl
    assert '.md-sep-when.ist-heute' in css and '.match-date.ist-heute' in css
    assert 'dash_days_test.js' in wf
    assert __import__('os').path.exists('tests/js/dash_days_test.js')


def test_st_kuerzel_ist_link_zum_schnelltipp(client, app, db, user,
                                             competition, teams, monkeypatch):
    """(87) Das ST-Kürzel verlinkt auf /tippen/<Spieltag> (Schnelltipp-Einstieg)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert '/tippen/5' in body


def test_tippschluss_chip_bei_ungetippt_und_kurzfristig(client, app, db, user,
                                                        competition, teams, monkeypatch):
    """(87) Ungetippt + Anstoss in < 24 h -> Warn-Chip „Tippschluss“;
    bei 72 h bleibt es der neutrale „Tippen“-Chip."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 5)     # kurzfristig
    _spiel(db, competition, teams, 6, 72)    # entspannt
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'chip-urgent' in body and 'Tippschluss' in body
    # der entspannte ST-6-Match hat den normalen Chip
    assert body.count('chip-urgent') == 1


def test_offene_tipps_zahl_nur_im_aktuellen_trenner(client, app, db, user,
                                                    competition, teams, monkeypatch):
    """(87) Der aktuelle Trenner zeigt „1 Tipp offen“; nach dem Tippen
    erscheint die Zahl nicht mehr."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    from models import Prediction
    _spiel(db, competition, teams, 5, 5)     # aktueller ST, ungetippt
    _spiel(db, competition, teams, 6, 72)
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'md-sep-open' in body and '1 Tipp offen' in body
    m = Match.query.filter_by(matchday=5).first()
    db.session.add(Prediction(user_id=user.id, match_id=m.id,
                              home_tip=2, away_tip=1, joker=False))
    db.session.commit()
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'md-sep-open' not in body         # alles getippt -> keine Zahl


def test_trennlinie_aria_hidden(client, app, db, user, competition, teams, monkeypatch):
    """(87) A11y: die Zieline ist aria-hidden (Screenreader lesen nur Text)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert '<span class="md-sep-line" aria-hidden="true"></span>' in body


def test_spielplan_und_schnelltipp_binden_dash_days_ein(client, app, db, user,
                                                        competition, teams, monkeypatch):
    """(88) Spielplan + Schnelltipp laden das Selbst-Init-Modul; die
    Zeitstrukturen tragen data-utc, das CSS kennt die Akzent-Klassen."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _login(client, user.email, "testpass123")
    plan = client.get("/spielplan/5").get_data(as_text=True)
    schnell = client.get("/schnelltipp/5").get_data(as_text=True)
    assert 'js/dash_days.js' in plan and 'data-utc=' in plan
    assert 'js/dash_days.js' in schnell and 'data-utc=' in schnell
    css = open('static/css/style.css', encoding='utf-8').read()
    assert '.match-time.ist-heute' in css and '.qt-time.ist-heute' in css


def test_dashboard_nutzt_selbstinit_ohne_doppelte_verdrahtung():
    """(88) Quelltext-Guard: das Modul initialisiert sich selbst (kein
    DOM) — das Dashboard hat keinen Inline-Wiring-Block mehr."""
    modul = open('static/js/dash_days.js', encoding='utf-8').read()
    tpl = open('templates/dashboard.html', encoding='utf-8').read()
    assert 'anwenden' in modul and 'DOMContentLoaded' in modul
    assert 'tagesLabel(el.dataset.utc)' not in tpl


def test_offene_tipps_tippschluss_chip(client, app, db, user,
                                       competition, teams, monkeypatch):
    """(88) Offene-Tipps-Seite: ungetippt & < 24 h -> Warn-Chip
    „Tippschluss"; 72 h -> neutraler „Noch tippen“-Chip."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 5)     # kurzfristig
    _spiel(db, competition, teams, 5, 72)    # entspannt
    _login(client, user.email, "testpass123")
    body = client.get("/meine-offenen-tipps/5").get_data(as_text=True)
    assert 'Tippschluss' in body and 'tippschluss' in body
    assert 'Noch tippen' in body
    assert body.count('tippschluss') == 1    # nur der kurzfristige


def test_spielplan_route_laeuft_mit_marker_daten(client, app, db, user,
                                                 competition, teams, monkeypatch):
    """(88) Regression: Spielplan mit Daten rendert 200 und behaelt die
    Anstosszeiten-Struktur (data-utc) inklusive renderbarem Zeitfeld."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _spiel(db, competition, teams, 5, 24)
    _login(client, user.email, "testpass123")
    resp = client.get("/spielplan/5")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'match-date' in body and 'match-hour' in body
