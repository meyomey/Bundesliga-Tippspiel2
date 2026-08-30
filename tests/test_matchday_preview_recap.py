"""Tests fuer Spieltags-Preview und Recap 2.0."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction


def _login(client, user):
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)


def test_matchday_preview_page(client, db, user, competition, teams):
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=2, away_tip=1))
    db.session.commit()
    _login(client, user)
    resp = client.get('/preview/1')
    assert resp.status_code == 200
    assert 'Spieltags-Preview'.encode('utf-8') in resp.data
    assert b'2:1' in resp.data


def test_matchday_recap_page(client, db, user, finished_match):
    db.session.add(Prediction(user_id=user.id, match_id=finished_match.id, home_tip=3, away_tip=1, points=4))
    db.session.commit()
    _login(client, user)
    resp = client.get('/spieltag-recap/1')
    assert resp.status_code == 200
    assert 'Spieltags-Recap'.encode('utf-8') in resp.data
    assert user.username.encode() in resp.data
    assert b'4' in resp.data
