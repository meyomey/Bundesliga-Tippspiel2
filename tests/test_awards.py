"""Tests fuer Admin-Saisonabschluss / Siegerehrung."""
from datetime import datetime, timedelta, timezone

from awards import compute_season_awards, generate_awards_pdf
from models import Match, Prediction, Prize


def _login_admin(client, admin_user):
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)


def test_compute_season_awards_and_pdf(db, admin_user, competition, teams):
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished', home_score=2, away_score=1
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=admin_user.id, match_id=match.id, home_tip=2, away_tip=1, points=4, joker=True))
    db.session.add(Prize(competition_id=competition.id, rank=1, title='1. Platz', icon='🏆', amount='Pokal', active=True))
    db.session.commit()

    data = compute_season_awards()
    assert data['leaderboard']
    assert data['podium'][0]['user'].id == admin_user.id
    assert any(a['code'] == 'champion' for a in data['awards'])
    pdf = generate_awards_pdf(data)
    assert pdf is None or pdf.getbuffer().nbytes > 100


def test_season_awards_admin_pages(client, db, admin_user, competition, teams):
    _login_admin(client, admin_user)
    resp = client.get('/admin/season-awards')
    assert resp.status_code == 200
    assert 'Siegerehrung'.encode('utf-8') in resp.data
    resp = client.get('/admin/season-awards/pdf')
    assert resp.status_code in (200, 302)
