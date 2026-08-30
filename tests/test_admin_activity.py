"""Tests fuer Admin Activity Log."""
from datetime import datetime, timedelta, timezone

from models import AdminActivityLog, Match


def _login_admin(client, admin_user):
    return client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)


def test_activity_log_page_accessible(client, admin_user):
    _login_admin(client, admin_user)
    resp = client.get('/admin/activity')
    assert resp.status_code == 200
    assert b'Activity Log' in resp.data


def test_result_update_creates_activity_log(client, db, admin_user, competition, teams):
    _login_admin(client, admin_user)
    match = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='scheduled'
    )
    db.session.add(match)
    db.session.commit()

    resp = client.post(f'/admin/match/{match.id}/result', data={
        'home_score': 2,
        'away_score': 1,
        'status': 'finished',
    }, follow_redirects=True)
    assert resp.status_code == 200
    log = AdminActivityLog.query.filter_by(action='result_update', entity_type='match', entity_id=str(match.id)).first()
    assert log is not None
    assert '2:1' in (log.message or '')


def test_activity_search_filter(client, db, admin_user):
    _login_admin(client, admin_user)
    db.session.add(AdminActivityLog(
        admin_user_id=admin_user.id,
        action='test_action',
        entity_type='unit',
        entity_id='42',
        message='Needle message',
    ))
    db.session.commit()
    resp = client.get('/admin/activity?q=Needle')
    assert resp.status_code == 200
    assert b'Needle message' in resp.data
