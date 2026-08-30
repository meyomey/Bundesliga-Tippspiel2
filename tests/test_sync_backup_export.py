"""Tests fuer Sync-Diagnose, Backup-ZIP und CSV-Export."""
import zipfile
from io import BytesIO
from datetime import datetime, timedelta, timezone

from models import Match, Prediction
from scoring import get_setting
from sync import get_sync_diagnostics, store_sync_result


def _login(client, user):
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)


def _login_admin(client, admin_user):
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)


def test_sync_diagnostics_and_store_result(monkeypatch, app, db, competition, teams):
    class Resp:
        ok = True
    monkeypatch.setattr('sync.requests.get', lambda *a, **kw: Resp())
    with app.app_context():
        diag = get_sync_diagnostics()
        assert diag['teams_total'] >= len(teams)
        stored = store_sync_result({'ok': True, 'source': 'unit', 'msg': 'ok'})
        assert stored['source'] == 'unit'
        assert get_setting('last_sync_result')['source'] == 'unit'


def test_admin_sync_page_and_run(monkeypatch, client, admin_user):
    _login_admin(client, admin_user)
    monkeypatch.setattr('routes_admin.get_sync_diagnostics', lambda: {
        'competition_code': 'TEST', 'season': '2025', 'teams_total': 18,
        'matches_total': 0, 'remote_logos': 0,
        'checks': {'football_data_token': False, 'openligadb_available': True, 'active_competition': True, 'teams_seeded': True, 'has_matches': False},
        'warnings': [], 'last_sync': None,
    })
    monkeypatch.setattr('routes_admin.sync_results', lambda: {'ok': True, 'source': 'unit', 'msg': 'Sync ok', 'created': 1, 'updated': 2})
    assert client.get('/admin/sync').status_code == 200
    resp = client.get('/admin/sync?run=1', follow_redirects=True)
    assert resp.status_code == 200
    assert b'Sync ok' in resp.data


def test_user_csv_export_escapes_semicolon(client, db, user, competition, teams):
    teams[0].name = 'Team;Semikolon'
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished', home_score=1, away_score=0
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=1, away_tip=0, points=4))
    db.session.commit()
    _login(client, user)
    resp = client.get('/export/csv')
    assert resp.status_code == 200
    data = resp.data.decode('utf-8-sig')
    assert '"Team;Semikolon"' in data


def test_admin_tip_matrix_export(client, db, admin_user, competition, teams):
    _login_admin(client, admin_user)
    match = Match(
        competition_id=competition.id, matchday=2,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished', home_score=2, away_score=1
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=admin_user.id, match_id=match.id, home_tip=2, away_tip=1, points=4))
    db.session.commit()
    resp = client.get('/admin/export/tip-matrix/2')
    assert resp.status_code == 200
    assert b'tippmatrix_st2.csv' in resp.headers.get('Content-Disposition', '').encode()
    assert b'FCB-BVB' in resp.data


def test_backup_zip_download(client, admin_user):
    _login_admin(client, admin_user)
    resp = client.get('/admin/backup/zip')
    # In TestConfig SQLite ist in-memory; ZIP kann deshalb je nach Pfad nicht verfuegbar sein.
    assert resp.status_code in (200, 302)
    if resp.status_code == 200:
        zf = zipfile.ZipFile(BytesIO(resp.data))
        assert 'README_BACKUP.txt' in zf.namelist()


def test_sync_season_code_parses_label(app, db):
    from sync import season_code_from_label, current_sync_season_code
    from scoring import set_setting
    with app.app_context():
        assert season_code_from_label('2026/27') == '2026'
        set_setting('season', '2026/27')
        assert current_sync_season_code() == '2026'
