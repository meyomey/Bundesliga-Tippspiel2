"""Tests fuer Wartungscenter-Funktionen."""

from models import Team
from maintenance import ensure_local_team_logos, run_health_check


class FakeResponse:
    ok = True
    content = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    headers = {'content-type': 'image/svg+xml'}


def test_health_check_counts_teams(db, teams):
    health = run_health_check()
    assert health['teams_total'] >= len(teams)
    assert health['db_ok'] is True


def test_ensure_local_team_logos_updates_remote_urls(app, db, teams, monkeypatch):
    for t in teams:
        t.logo = 'https://example.test/logo.svg'
    db.session.commit()

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr('requests.sessions.Session.get', fake_get)
    with app.app_context():
        res = ensure_local_team_logos(force=True)
    assert res['updated'] == len(teams)
    assert all(t.logo.startswith('/static/team_logos/') for t in Team.query.all())


def test_health_check_admin_password_uses_real_hash(db, admin_user):
    from maintenance import run_health_check
    # admin_user fixture uses admin123 initially -> warning/check should fail
    health = run_health_check()
    assert health['checks']['admin_password_secure'] is False
    admin_user.set_password('changed-secure-password')
    db.session.commit()
    health = run_health_check()
    assert health['checks']['admin_password_secure'] is True
    assert not any('admin123' in w for w in health['warnings'])
