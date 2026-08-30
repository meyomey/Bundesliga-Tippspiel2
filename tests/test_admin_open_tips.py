"""Tests fuer Admin-Offene-Tipps-Uebersicht."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction


def _login_admin(client, admin_user):
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)


def test_admin_open_tips_page(client, db, admin_user, user, competition, teams):
    _login_admin(client, admin_user)
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=admin_user.id, match_id=match.id, home_tip=2, away_tip=1))
    db.session.commit()
    resp = client.get('/admin/open-tips?matchday=1')
    assert resp.status_code == 200
    assert 'Offene Tipps'.encode('utf-8') in resp.data
    assert user.username.encode() in resp.data


def test_admin_open_tips_reminder(monkeypatch, client, db, admin_user, user, competition, teams):
    _login_admin(client, admin_user)
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    db.session.add(match)
    db.session.commit()
    calls = []
    def fake_send(user_obj, match_obj):
        calls.append((user_obj.id, match_obj.id))
        return {'email': True, 'push': False, 'telegram': False, 'whatsapp': False}
    monkeypatch.setattr('notification_center.send_user_notification', fake_send)
    resp = client.post('/admin/open-tips', data={'matchday': 1}, follow_redirects=True)
    assert resp.status_code == 200
    assert calls
