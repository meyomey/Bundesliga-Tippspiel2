"""Regressionstests: Sync darf beendete/laufende Spiele nicht zurueckdrehen.

Hintergrund (Produktionsbug 2026-08-30): Ergebnis- und Punkteanzeige haengen
strikt am Match-Status ("finished"). Meldete eine API zwischenzeitlich einen
veralteten Status (z. B. "scheduled" fuer ein gestern beendetes Spiel),
verschwanden Ergebnis und Punkte in den Anzeigen, bis ein spaeterer Sync den
Status erneut setzte. Die Status-Monotonie in apply_match_update verhindert
genau diese automatischen Downgrades.
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db as _db
from models import Match, Prediction
from match_results import apply_match_update
from sync import _process_football_data, sync_with_openligadb


def _fd_payload(match_id, matchday, home, away, status, home_score=None, away_score=None):
    return {
        'matches': [{
            'id': match_id,
            'utcDate': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z'),
            'matchday': matchday,
            'status': status,
            'homeTeam': {'id': 1, 'name': home.name, 'shortName': home.short_name, 'tla': home.short_name, 'crest': home.logo},
            'awayTeam': {'id': 2, 'name': away.name, 'shortName': away.short_name, 'tla': away.short_name, 'crest': away.logo},
            'score': {'fullTime': {'home': home_score, 'away': away_score}, 'halfTime': {'home': None, 'away': None}},
        }]
    }


def _make_match(db, competition, teams, *, ext_id, status, kickoff_delta, home_score=None, away_score=None, is_live=False):
    m = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + kickoff_delta,
        status=status, home_score=home_score, away_score=away_score,
        external_id=ext_id, is_live=is_live,
    )
    db.session.add(m)
    db.session.commit()
    return m


def test_finished_match_not_downgraded_to_scheduled(db, competition, teams):
    """Gestrige, beendete Spiele verschwinden nicht, wenn die API sie
    faelschlich wieder als geplant meldet."""
    m = _make_match(db, competition, teams, ext_id='fd:501', status='finished',
                    kickoff_delta=timedelta(days=-1), home_score=3, away_score=1)
    data = _fd_payload(501, 1, teams[0], teams[1], 'TIMED')
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.status == 'finished'
    assert m.home_score == 3
    assert m.away_score == 1


def test_finished_match_not_downgraded_to_live(db, competition, teams):
    m = _make_match(db, competition, teams, ext_id='fd:502', status='finished',
                    kickoff_delta=timedelta(days=-1), home_score=2, away_score=2)
    data = _fd_payload(502, 1, teams[0], teams[1], 'IN_PLAY', home_score=None, away_score=None)
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.status == 'finished'
    assert m.is_live is False
    assert m.home_score == 2
    assert m.away_score == 2


def test_finished_match_score_correction_still_applied(db, competition, teams):
    """Korrektur-Meldungen mit echtem Endstand duerfen weiterhin aktualisieren."""
    m = _make_match(db, competition, teams, ext_id='fd:503', status='finished',
                    kickoff_delta=timedelta(days=-1), home_score=3, away_score=1)
    data = _fd_payload(503, 1, teams[0], teams[1], 'FINISHED', home_score=4, away_score=2)
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.status == 'finished'
    assert (m.home_score, m.away_score) == (4, 2)


def test_live_match_not_downgraded_to_scheduled(db, competition, teams):
    """Ein laufendes Spiel bleibt live, auch wenn die API es kurzzeitig
    als geplant meldet (Fallback-Lag, Rate-Limit-Cache)."""
    m = _make_match(db, competition, teams, ext_id='fd:504', status='live',
                    kickoff_delta=timedelta(hours=-1), home_score=1, away_score=0, is_live=True)
    data = _fd_payload(504, 1, teams[0], teams[1], 'TIMED')
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.status == 'live'
    assert m.is_live is True


def test_scheduled_match_upgrades_to_finished(db, competition, teams, user):
    """Der normale Weg scheduled -> finished muss weiter funktionieren,
    inklusive Punkte-Neuberechnung."""
    m = _make_match(db, competition, teams, ext_id='fd:505', status='scheduled',
                    kickoff_delta=timedelta(hours=-2))
    pred = Prediction(user_id=user.id, match_id=m.id, home_tip=2, away_tip=0)
    db.session.add(pred)
    db.session.commit()
    data = _fd_payload(505, 1, teams[0], teams[1], 'FINISHED', home_score=2, away_score=0)
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    db.session.refresh(pred)
    assert m.status == 'finished'
    assert pred.points is not None
    assert pred.points > 0


def test_apply_match_update_allow_status_reset(db, competition, teams):
    """Nur explizites Zuruecksetzen (Admin) darf den Status zurueckdrehen."""
    m = _make_match(db, competition, teams, ext_id='fd:506', status='finished',
                    kickoff_delta=timedelta(days=-1), home_score=1, away_score=0)
    apply_match_update(m, status='scheduled')
    assert m.status == 'finished'
    apply_match_update(m, status='scheduled', allow_status_reset=True)
    assert m.status == 'scheduled'


def _olb_match(match_id, home, away, home_id=1001, away_id=1002, finished=False):
    return {
        'matchID': match_id,
        'matchDateTimeUTC': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace('+00:00', 'Z'),
        'matchIsFinished': finished,
        'group': {'groupOrderID': 1},
        'team1': {'teamId': home_id, 'teamName': home, 'shortName': home[:3].upper(), 'teamIconUrl': f'https://example.test/{home_id}.svg'},
        'team2': {'teamId': away_id, 'teamName': away, 'shortName': away[:3].upper(), 'teamIconUrl': f'https://example.test/{away_id}.svg'},
        'matchResults': [],
    }


def test_openligadb_fallback_not_downgrading_finished(monkeypatch, db, competition, teams):
    """Auch der OLB-Fallback (keine Live-Daten, ggf. verzoegerte Ergebnisse)
    darf beendete Spiele nicht mehr auf scheduled drehen."""
    competition.code = 'BL1'
    m = _make_match(db, competition, teams, ext_id='oldb:777', status='finished',
                    kickoff_delta=timedelta(days=-1), home_score=2, away_score=0)

    class Resp:
        status_code = 200

        def json(self):
            return [_olb_match(777, teams[0].name, teams[1].name, finished=False)]

    monkeypatch.setattr('sync.requests.get', lambda *a, **kw: Resp())
    result = sync_with_openligadb()

    assert result['ok'] is True
    db.session.refresh(m)
    assert m.status == 'finished'
    assert m.home_score == 2
    assert m.away_score == 0


def test_fd_request_stale_cache_not_reused_beyond_10_minutes(monkeypatch, db):
    """Bei API-Fehlern darf der FD-Cache nur max. 10 Minuten alt sein."""
    from scoring import set_setting
    from sync import _fd_request
    import requests as real_requests

    set_setting('football_data_token', 'test-token')
    cache_key = 'fd_cache:/competitions/BL1/matches?season=2026'
    old_ts = datetime.now(timezone.utc).timestamp() - 900  # 15 Minuten alt
    set_setting(cache_key, {'ts': old_ts, 'data': {'matches': [{'id': 1}]}})

    def _raise(*a, **kw):
        raise real_requests.exceptions.RequestException('down')

    monkeypatch.setattr('sync.requests.get', _raise)
    data, err = _fd_request('/competitions/BL1/matches?season=2026', ttl_seconds=30)
    assert data is None
    assert err is not None


def test_fd_request_fresh_cache_used_on_error(monkeypatch, db):
    """Frischer Cache (<= 10 Minuten) darf bei API-Fehlern weiter greifen."""
    from scoring import set_setting
    from sync import _fd_request
    import requests as real_requests

    set_setting('football_data_token', 'test-token')
    cache_key = 'fd_cache:/competitions/BL1/matches?season=2026&matchday=1'
    fresh_ts = datetime.now(timezone.utc).timestamp() - 120  # 2 Minuten alt
    set_setting(cache_key, {'ts': fresh_ts, 'data': {'matches': [{'id': 42}]}})

    def _raise(*a, **kw):
        raise real_requests.exceptions.RequestException('down')

    monkeypatch.setattr('sync.requests.get', _raise)
    data, err = _fd_request('/competitions/BL1/matches?season=2026&matchday=1', ttl_seconds=1)
    assert err is None
    assert data == {'matches': [{'id': 42}]}
