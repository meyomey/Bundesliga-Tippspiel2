"""Smoke-Tests fuer die Spieler-Zentralseiten.

Ergänzt test_routes.py dort, wo Seiten bislang gar nicht oder nur
stiefmuetterlich geprueft wurden, und sichert die Auslagerung des
Inline-JS/CSS ab: Die Seiten muessen ihre statischen Assets referenzieren,
sonst faellt der Funktionsverlust im Browser erst zur Laufzeit auf.
"""

import pytest

from models import Match


def _login(client, user):
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'},
                follow_redirects=True)


# (URL, erwarteter ASCII-Marker im gerenderten HTML oder None)
CENTRAL_PAGES = [
    ('/spielplan', None),
    ('/spielplan/1', None),
    ('/tabelle', 'Punkte'),
    ('/preview', 'Vorschau'),
    ('/preview/1', 'Vorschau'),
    ('/spieltag-recap', None),
    ('/spieltag-recap/1', None),
    ('/ewige-tabelle', None),
    ('/spieltagsieger', 'Spieltagsieger'),
    ('/meine-offenen-tipps', None),
    ('/mehr', None),
    ('/preise', None),
]


@pytest.mark.parametrize('url,marker', CENTRAL_PAGES)
def test_central_pages_render_200(client, db, user, url, marker):
    """Zentralseiten laden fuer eingeloggte Spieler ohne Serverfehler."""
    _login(client, user)
    resp = client.get(url)
    assert resp.status_code == 200, f'{url} -> HTTP {resp.status_code}'
    if marker:
        assert marker.encode('utf-8') in resp.data, f'{url}: Marker {marker!r} fehlt'


# (URL, Liste der statischen Assets, die referenziert sein muessen)
ASSET_PAGES = [
    ('/schnelltipp', ['css/quick_tip.css', 'js/quick_tip.js']),
    ('/live', ['js/live.js']),
    ('/tipps', ['css/tip_overview.css', 'js/tip_overview.js']),
    ('/stats', ['js/stats_dashboard.js']),
]


@pytest.mark.parametrize('url,assets', ASSET_PAGES)
def test_externalized_assets_are_linked(client, db, user, url, assets):
    """Ausgelagerte JS/CSS-Dateien werden von den Seiten eingebunden."""
    _login(client, user)
    resp = client.get(url, follow_redirects=True)
    assert resp.status_code == 200
    for asset in assets:
        assert asset.encode('ascii') in resp.data, f'{url}: Asset {asset} fehlt'


def test_match_detail_links_asset_and_config_span(client, db, user, competition, teams, app, monkeypatch):
    """match_detail.html bindet match_detail.js ein und stellt die
    Quick-Tip-Fallback-URL per #md-config-Span bereit (frueher inline)."""
    from datetime import datetime, timedelta, timezone
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    match = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=5),
        status='scheduled',
    )
    db.session.add(match)
    db.session.commit()
    _login(client, user)
    resp = client.get(f'/match/{match.id}')
    assert resp.status_code == 200
    assert b'js/match_detail.js' in resp.data
    assert b'id="md-config"' in resp.data
    assert b'data-quick-tip-url=' in resp.data


def test_stats_dashboard_ships_chart_data_island(client, db, user):
    """Die Chart-Daten kommen als JSON-Insel (#stats-chart-data) statt
    als Jinja-interpoliertes Inline-Skript."""
    _login(client, user)
    resp = client.get('/stats')
    assert resp.status_code == 200
    assert b'id="stats-chart-data"' in resp.data
    assert b'type="application/json"' in resp.data
    # Kein serverseitig interpoliertes tojson-Skript mehr:
    assert b'const rankDatasets = SD.rank_datasets' not in resp.data


def test_admin_bots_page_links_external_css(client, db, admin_user):
    """Admin-Bots-Seite bindet admin_bots.css ein."""
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'},
                follow_redirects=True)
    resp = client.get('/admin/bots')
    assert resp.status_code == 200
    assert b'css/admin_bots.css' in resp.data


def test_leaderboard_honours_matchday_parameter(client, db, user):
    """Regressions-Test: /tabelle/<matchday> wertet den Spieltag aus.

    Vor der routes_main-Entflechtung rief der Lazy-Wrapper _leaderboard() OHNE
    matchday auf — die URL /tabelle/<n> wurde still ignoriert. Nach der direkten
    Registrierung in main_stats_routes.py greift der Parameter wieder.
    (Damit der Test ohne abgeschlossene Spiele deterministisch prueft, wird die
    statistik-Funktion gemonkeypatcht und nur die Weitergabe verifiziert.)
    """
    import main_stats_routes
    seen = []
    real = main_stats_routes.get_leaderboard

    def spy(matchday=None):
        seen.append(matchday)
        return real(matchday=matchday)

    main_stats_routes.get_leaderboard = spy
    try:
        _login(client, user)
        resp = client.get('/tabelle/3')
        assert resp.status_code == 200
        assert seen == [3], f'matchday wurde nicht uebergeben: {seen}'
    finally:
        main_stats_routes.get_leaderboard = real
