"""Tests fuer Saisonwechsel-Assistent."""
from datetime import datetime, timedelta, timezone

from models import Match, User
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
