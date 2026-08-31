"""Tests fuer Saisonwechsel-Assistent."""
from datetime import datetime, timedelta, timezone

from models import Match, User, Competition
from scoring import get_setting


def _login_admin(client, admin_user):
    return client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)


def test_new_season_page_accessible_for_admin(client, admin_user):
    _login_admin(client, admin_user)
    resp = client.get('/admin/new-season')
    assert resp.status_code == 200
    assert 'Saisonwechsel-Assistent'.encode('utf-8') in resp.data


def test_new_season_requires_confirmation(client, admin_user):
    _login_admin(client, admin_user)
    resp = client.post('/admin/new-season', data={
        'new_season_label': '2026/27',
        'confirm_text': 'WRONG',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'SAISON STARTEN'.encode('utf-8') in resp.data


def test_new_season_updates_setting_and_keeps_users(client, db, admin_user, competition, teams):
    _login_admin(client, admin_user)
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished', home_score=2, away_score=1
    )
    db.session.add(match)
    db.session.commit()

    resp = client.post('/admin/new-season', data={
        'new_season_label': '2026/27',
        'old_season_label': '2025/26',
        'confirm_text': 'SAISON STARTEN',
        'backup_ack': '1',
        'risk_ack': '1',
        'do_archive': '1',
        'do_delete_schedule': '1',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert get_setting('current_season') == '2026/27'
    assert User.query.filter_by(email=admin_user.email).first() is not None


def test_new_season_requires_backup_ack(client, db, admin_user, competition, teams):
    _login_admin(client, admin_user)
    resp = client.post('/admin/new-season', data={
        'new_season_label': '2026/27',
        'old_season_label': '2025/26',
        'confirm_text': 'SAISON STARTEN',
        'risk_ack': '1',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'Backup'.encode('utf-8') in resp.data


def test_new_season_keeps_competition_name_season_free(client, db, admin_user, competition, teams):
    """Saisonwechsel schreibt die Saison nicht (mehr) in den Wettbewerbs-Namen
    und bereinigt Altbestand ('Bundesliga 2026' -> 'Bundesliga')."""
    _login_admin(client, admin_user)
    competition.name = "Bundesliga 2026"  # Altbestand simulieren
    db.session.commit()

    resp = client.post('/admin/new-season', data={
        'new_season_label': '2026/27',
        'old_season_label': '2025/26',
        'confirm_text': 'SAISON STARTEN',
        'backup_ack': '1',
        'risk_ack': '1',
        'do_archive': '1',
        'do_delete_schedule': '1',
    }, follow_redirects=True)
    assert resp.status_code == 200
    fresh = Competition.query.get(competition.id)
    assert fresh.name == 'Bundesliga'
    assert fresh.season == '2026/27'


def test_competition_label_dedupes_year(client, db, user, competition, teams, monkeypatch, app):
    """Anzeige entdoppelt 'Bundesliga 2026 2026', egal woher der Name kommt."""
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    competition.name = "Bundesliga 2026"
    competition.season = "2026"
    db.session.add(Match(competition_id=competition.id, matchday=1,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'))
    db.session.commit()
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/preview/1')
    assert resp.status_code == 200
    assert resp.data.count(b'Bundesliga 2026 2026') == 0
    assert 'Bundesliga 2026'.encode('utf-8') in resp.data


def test_competition_label_pure_cases():
    """competition_label deckt alle Doppel-Jahr-Varianten ab."""
    from competition_helpers import competition_label
    assert competition_label('Bundesliga', '2025/26') == 'Bundesliga · 2025/26'
    assert competition_label('Bundesliga 2026', '2026') == 'Bundesliga 2026'
    assert competition_label('Bundesliga 2026', '2026/27') == 'Bundesliga 2026/27'
    assert competition_label('Bundesliga 2025/26', '2025/26') == 'Bundesliga 2025/26'
    assert competition_label('2. Bundesliga', '2026') == '2. Bundesliga · 2026'
    assert competition_label('', '2026') == '2026'
    assert competition_label('Bundesliga', '') == 'Bundesliga'


def test_zentralseiten_kein_doppeltes_saisonlabel(client, db, user, competition, teams, monkeypatch, app):
    """Alle Zentralseiten nutzen comp_label: kein 'Bundesliga 2026 · Saison 2026'.

    Regressions-Schutz: Die Rangliste (und weitere Seiten) konkatenierten
    Name + Saison roh, obwohl competition_label() als comp_label global
    verfuegbar ist. Produktiv war dort 'Bundesliga 2026 · Saison 2026'
    sichtbar (Name trug das Jahr noch aus dem alten Saisonwechsel).
    """
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    competition.name = "Bundesliga 2026"
    competition.season = "2026"
    db.session.add(Match(competition_id=competition.id, matchday=1,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'))
    db.session.commit()
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code

    double = 'Bundesliga 2026 · Saison 2026'.encode('utf-8')
    for url in ['/tabelle', '/bundesliga-tabelle', '/stats', '/sondertipps']:
        resp = client.get(url, follow_redirects=True)
        assert resp.status_code == 200, url
        assert double not in resp.data, f'{url}: Doppel-Saisonlabel noch sichtbar'
    # Rangliste zeigt das deduplizierte Label (Name behaelt das Jahr, Saison faellt weg)
    resp = client.get('/tabelle')
    assert 'Bundesliga 2026 · Bei Gleichstand'.encode('utf-8') in resp.data


def test_admin_dashboard_kein_doppeltes_saisonlabel(client, db, admin_user, competition, monkeypatch, app):
    """Admin-Dashboard nutzt comp_label statt roher Name+Saison-Konkatenation."""
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    competition.name = "Bundesliga 2026"
    competition.season = "2026"
    db.session.commit()
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    resp = client.get('/admin', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Bundesliga 2026 · Saison 2026'.encode('utf-8') not in resp.data
    assert 'Bundesliga 2026'.encode('utf-8') in resp.data
