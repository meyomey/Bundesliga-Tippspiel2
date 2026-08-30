"""Tests fuer Sync mit neuen/Aufsteiger-Teams."""
from datetime import datetime, timezone

from models import Match, Team, CompetitionTeam
from sync import _process_football_data


def test_football_data_sync_creates_unknown_promoted_teams(db, competition):
    data = {
        'matches': [{
            'id': 999001,
            'utcDate': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'matchday': 1,
            'status': 'TIMED',
            'homeTeam': {'id': 9101, 'name': 'Aufsteiger FC', 'shortName': 'Aufsteiger', 'tla': 'AFC', 'crest': 'https://example.test/afc.png'},
            'awayTeam': {'id': 9102, 'name': 'Neuling 09', 'shortName': 'Neuling', 'tla': 'N09', 'crest': 'https://example.test/n09.png'},
            'score': {'fullTime': {'home': None, 'away': None}, 'halfTime': {'home': None, 'away': None}},
        }]
    }
    result = _process_football_data(data, competition.id, source='unit')
    assert result['created'] == 1
    assert result['new_teams'] == 2
    assert Team.query.filter_by(short_name='AFC').first() is not None
    assert Team.query.filter_by(short_name='N09').first() is not None
    match = Match.query.filter_by(external_id='fd:999001').first()
    assert match is not None
    assert CompetitionTeam.query.filter_by(competition_id=competition.id, team_id=match.home_team_id).first() is not None


def test_full_football_data_sync_purges_stale_matches(db, competition, teams):
    old = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc), status='scheduled', external_id='fd:old-season'
    )
    db.session.add(old)
    db.session.commit()
    data = {
        'matches': [{
            'id': 999002,
            'utcDate': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'matchday': 1,
            'status': 'TIMED',
            'homeTeam': {'id': teams[0].external_id or 5, 'name': teams[0].name, 'shortName': teams[0].name, 'tla': teams[0].short_name, 'crest': teams[0].logo},
            'awayTeam': {'id': teams[1].external_id or 4, 'name': teams[1].name, 'shortName': teams[1].name, 'tla': teams[1].short_name, 'crest': teams[1].logo},
            'score': {'fullTime': {'home': None, 'away': None}, 'halfTime': {'home': None, 'away': None}},
        }]
    }
    result = _process_football_data(data, competition.id, source='football-data.org')
    assert result['purged_stale'] >= 1
    assert Match.query.filter_by(external_id='fd:old-season').first() is None


def _olb_match(match_id, home, away, home_id=1001, away_id=1002, finished=False):
    return {
        'matchID': match_id,
        'matchDateTimeUTC': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'matchIsFinished': finished,
        'group': {'groupOrderID': 1},
        'team1': {'teamId': home_id, 'teamName': home, 'shortName': home[:3].upper(), 'teamIconUrl': f'https://example.test/{home_id}.svg'},
        'team2': {'teamId': away_id, 'teamName': away, 'shortName': away[:3].upper(), 'teamIconUrl': f'https://example.test/{away_id}.svg'},
        'matchResults': [],
    }


def test_openligadb_sync_creates_promoted_teams_and_purges_stale(monkeypatch, db, competition, teams):
    from sync import sync_with_openligadb

    competition.code = 'BL1'
    stale = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc), status='scheduled', external_id='oldb:stale'
    )
    db.session.add(stale)
    db.session.commit()

    class Resp:
        status_code = 200
        def json(self):
            return [_olb_match(12345, 'Aufsteiger OLB', 'Neuling OLB', 9201, 9202)]

    monkeypatch.setattr('sync.requests.get', lambda *a, **kw: Resp())
    result = sync_with_openligadb()

    assert result['ok'] is True
    assert result['created'] == 1
    assert result['new_teams'] == 2
    assert result['purged_stale'] == 1
    assert Match.query.filter_by(external_id='oldb:stale').first() is None
    match = Match.query.filter_by(external_id='oldb:12345').first()
    assert match is not None
    assert Team.query.filter_by(name='Aufsteiger OLB').first() is not None
    assert CompetitionTeam.query.filter_by(competition_id=competition.id, team_id=match.home_team_id).first() is not None


def test_openligadb_fallback_preserves_existing_fd_match_predictions(monkeypatch, db, competition, teams, user):
    from models import Prediction
    from sync import sync_with_openligadb

    competition.code = 'BL1'
    existing = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc), status='scheduled', external_id='fd:existing'
    )
    db.session.add(existing)
    db.session.commit()
    pred = Prediction(user_id=user.id, match_id=existing.id, home_tip=2, away_tip=1)
    db.session.add(pred)
    db.session.commit()

    class Resp:
        status_code = 200
        def json(self):
            return [_olb_match(54321, teams[0].name, teams[1].name, teams[0].external_id or 5, teams[1].external_id or 4)]

    monkeypatch.setattr('sync.requests.get', lambda *a, **kw: Resp())
    result = sync_with_openligadb()

    assert result['ok'] is True
    assert result['created'] == 0
    assert result['updated'] == 1
    assert Match.query.count() == 1
    match = Match.query.first()
    assert match.id == existing.id
    assert match.external_id == 'oldb:54321'
    assert Prediction.query.filter_by(id=pred.id, match_id=existing.id).first() is not None


def test_known_logo_fixes_do_not_overwrite_local_logos(db, teams):
    from sync import update_known_team_logos

    teams[0].short_name = 'FCB'
    teams[0].logo = '/static/team_logos/fcb.svg'
    db.session.commit()
    changed = update_known_team_logos()
    db.session.refresh(teams[0])

    assert teams[0].logo == '/static/team_logos/fcb.svg'
    assert changed >= 0
