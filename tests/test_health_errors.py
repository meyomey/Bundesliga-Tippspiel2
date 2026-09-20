"""(81) Betrieb & Grundhärtung: /healthz, Sicherheits-Header, gehärtete
Session-Cookies und deutsche Fehlerseiten (404/500, API-Pfade mit JSON)."""
from sqlalchemy.orm import Session

from extensions import db


def _login(client, admin_user):
    return client.post('/auth/login',
                       data={'email': admin_user.email, 'password': 'admin123'},
                       follow_redirects=True)


def test_healthz_ok_oeffentlich(app, client):
    """/healthz meldet ok + DB-Verbindung — ohne Login, ohne personen-
    bezogene Daten (Monitoring/Plesk kann abfragen)."""
    resp = client.get('/healthz')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['db'] is True
    assert 'time' in data


def test_healthz_degradiert_bei_db_ausfall(app, client, monkeypatch):
    """Fällt die DB aus, antwortet /healthz mit 503 und db:false — ehrlich
    melden statt grün lügen (ℹ️-Prinzip)."""
    def kaputt(self, *a, **k):
        raise RuntimeError('DB weg (Test)')

    monkeypatch.setattr(Session, 'execute', kaputt)
    resp = client.get('/healthz')
    monkeypatch.undo()
    assert resp.status_code == 503
    assert resp.get_json()['db'] is False


def test_sicherheits_header_auf_jeder_antwort(app, client):
    """Grundhärtung: nosniff, SAMEORIGIN, Referrer-Policy überall."""
    resp = client.get('/healthz')
    assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
    assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert resp.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


def test_session_cookie_gehaertet(app, client, db, admin_user):
    """Login-Cookie: HttpOnly + SameSite=Lax immer; Secure nur bei HTTPS-
    Public-URL (Prod) — die Test-Instanz läuft bewusst über http."""
    resp = _login(client, admin_user)
    assert resp.status_code == 200
    cookies = [h for h in resp.headers.getlist('Set-Cookie')
               if h.startswith('session=')]
    assert cookies, 'Login setzt keinen Session-Cookie'
    cookie = cookies[0]
    assert 'HttpOnly' in cookie
    assert 'SameSite=Lax' in cookie
    assert 'Secure' not in cookie          # http-Testinstanz ohne Secure


def test_404_seite_deutsch(app, client):
    """Unbekannte Seite → deutsche 404-Seite statt Flasks Englisch-Default."""
    resp = client.get('/gibt-es-nicht-81')
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert '404' in body and 'existiert nicht' in body
    assert 'Zum Tippspiel' in body


def test_404_api_pfad_liefert_json(app, client):
    """API-Pfade bekommen maschinenlesbare Fehler statt HTML."""
    resp = client.get('/api/gibt-es-nicht-81')
    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json()['error'] == 'not_found'


def test_500_seite_deutsch(app, client, monkeypatch):
    """Interner Fehler → deutsche 500-Seite. Flasks App ist session-scoped
    und nach dem ersten Request gesperrt für neue Routen — deshalb wird die
    bestehende /healthz-View im Route-Mapping durch eine knallende ersetzt
    (PROPAGATE_EXCEPTIONS im Test bewusst aus, damit der Handler greift)."""
    app.config['PROPAGATE_EXCEPTIONS'] = False

    def _boom():
        raise RuntimeError('Boom-81')

    monkeypatch.setitem(app.view_functions, 'healthz', _boom)
    resp = client.get('/healthz')
    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert 'geklommen' in body or 'Interner Fehler' in body


def test_500_api_pfad_liefert_json(app, client, monkeypatch):
    """Auch der 500er bleibt unter /api/ maschinenlesbar (öffentliche
    /api/matches-View wird durch eine knallende ersetzt)."""
    app.config['PROPAGATE_EXCEPTIONS'] = False

    def _boom_api(_md):
        raise RuntimeError('Boom-API-81')

    monkeypatch.setitem(app.view_functions, 'api.api_matches', _boom_api)
    resp = client.get('/api/matches/1')
    assert resp.status_code == 500
    assert resp.is_json
    assert resp.get_json()['error'] == 'server_error'
