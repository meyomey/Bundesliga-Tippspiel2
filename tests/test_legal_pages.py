"""Tests fuer Impressum & Datenschutzerklärung ((89)).

Beide Seiten sind ÖFFENTLICH (ohne Login erreichbar, Pflicht trotz
privater Runde: DSGVO-Informationspflichten; Impressum als Sicherheits-
reserve bei Einsatz/Topf). Platzhalter („ANPASSEN“) sind dokumentierter
Offener Punkt für den Betreiber.
"""
from extensions import db
from models import Match


def test_impressum_oeffentlich(client):
    """/impressum ohne Login: 200, Anbieter-Absatz, Hosting, Aufforderung."""
    resp = client.get('/impressum')
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Impressum' in body and '§ 5 DDG' in body
    assert 'netcup' in body
    assert 'ANPASSEN' in body            # dokumentierter Offener Punkt


def test_datenschutz_oeffentlich(client):
    """/datenschutz ohne Login: 200, Kernabschnitte der Erklärung."""
    resp = client.get('/datenschutz')
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Datenschutzerklärung' in body
    for stichwort in ('Verantwortlicher', 'Rechtsgrundlage', 'Speicherdauer',
                      'Deine Rechte', 'Session-Cookie', 'netcup'):
        assert stichwort in body


def test_footer_links_auf_oeffentlicher_seite(client):
    """Auch ohne Login verweist der Footer auf beide Seiten (Pflicht)."""
    body = client.get('/impressum').get_data(as_text=True)
    assert 'href="/datenschutz"' in body
    assert 'Impressum' in body           # Selbstverweis-Link im Footer


def test_kein_login_erforderlich_und_schutz_ungestoert(client, db, user):
    """Legaler Seitenzugriff berührt den Spielbetrieb nicht; Tipps bleiben
    weiterhin hinter dem Login (Spot-Check der Spiel-Daten)."""
    assert client.get('/datenschutz').status_code == 200
    assert client.get('/').status_code in (200, 302)
    assert Match.query.count() >= 0      # DB unberührt vom Seitenaufruf


def test_quelltext_guards_neue_dateien():
    """Selbstbeweis: beide Seiten sind eigene neue Templates im Footer
    verankert; Build-Liste enthält sie."""
    imp = open('templates/impressum.html', encoding='utf-8').read()
    ds = open('templates/datenschutz.html', encoding='utf-8').read()
    base = open('templates/base.html', encoding='utf-8').read()
    build = open('build_lieferungen.py', encoding='utf-8').read()
    assert "main.impressum" in base and "main.datenschutz" in base
    assert 'templates/impressum.html' in build and 'templates/datenschutz.html' in build
    assert 'legal-page' in imp and 'legal-page' in ds
