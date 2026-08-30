"""Regressionstests fuer Fairness-/Integritaetsfixes aus Audit."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction
from scoring import classify_prediction


def test_joker_cannot_move_after_old_joker_match_started(client, db, user, competition, teams):
    old_match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=5),
        status='scheduled',
    )
    new_match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[2].id, away_team_id=teams[3].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=2),
        status='scheduled',
    )
    db.session.add_all([old_match, new_match])
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=old_match.id, home_tip=1, away_tip=0, joker=True))
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.post(f'/api/tip/{new_match.id}', json={'home_tip': 2, 'away_tip': 1, 'joker': True})

    assert resp.status_code == 400
    old_pred = Prediction.query.filter_by(user_id=user.id, match_id=old_match.id).first()
    assert old_pred.joker is True
    assert Prediction.query.filter_by(user_id=user.id, match_id=new_match.id).first() is None


def test_quicktip_rejects_manipulated_scores(client, db, user, competition, teams):
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=2),
        status='scheduled',
    )
    db.session.add(match)
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.post(f'/schnelltipp/1', data={
        f'home_{match.id}': '-1',
        f'away_{match.id}': '999',
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert Prediction.query.filter_by(user_id=user.id, match_id=match.id).first() is None


def test_draw_to_different_draw_is_tendency_not_diff(db, competition, teams, user):
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished', home_score=2, away_score=2,
    )
    db.session.add(match)
    db.session.commit()
    pred = Prediction(user_id=user.id, match_id=match.id, home_tip=1, away_tip=1)

    assert classify_prediction(pred, match) == 'tendency'


def test_sync_partial_response_does_not_purge_large_local_schedule(db, competition, teams):
    from sync import _process_football_data

    old_matches = []
    for i in range(60):
        m = Match(
            competition_id=competition.id, matchday=(i // 9) + 1,
            home_team_id=teams[i % len(teams)].id,
            away_team_id=teams[(i + 1) % len(teams)].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=i),
            status='scheduled', external_id=f'fd:old-{i}',
        )
        old_matches.append(m)
    db.session.add_all(old_matches)
    db.session.commit()

    data = {'matches': [{
        'id': 999123,
        'utcDate': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'matchday': 1,
        'status': 'TIMED',
        'homeTeam': {'id': teams[0].external_id or 5, 'name': teams[0].name, 'shortName': teams[0].name, 'tla': teams[0].short_name, 'crest': teams[0].logo},
        'awayTeam': {'id': teams[1].external_id or 4, 'name': teams[1].name, 'shortName': teams[1].name, 'tla': teams[1].short_name, 'crest': teams[1].logo},
        'score': {'fullTime': {'home': None, 'away': None}, 'halfTime': {'home': None, 'away': None}},
    }]}

    result = _process_football_data(data, competition.id, source='football-data.org')

    assert result['purged_stale'] == 0
    assert Match.query.filter_by(external_id='fd:old-0').first() is not None
