"""Tests fuer Wartungscenter-Funktionen."""

import pytest

from models import Team
from maintenance import ensure_local_team_logos, run_health_check


@pytest.fixture
def logo_static(app, monkeypatch, tmp_path):
    """Leitet static_folder fuer Logo-Tests in ein tmp-Verzeichnis um.

    WICHTIG: Logo-Tests duerfen niemals in die eingecheckten Dateien unter
    static/team_logos/ schreiben -- 46-Byte-Test-Fakes (<svg...></svg>) landeten
    sonst mit dem naechsten FTP-Upload auf dem Server und liessen dort die
    Logos von Bayern/Dortmund/Leverkusen/Leipzig verschwinden.
    """
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    return tmp_path


class FakeResponse:
    ok = True
    content = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    headers = {'content-type': 'image/svg+xml'}


def test_health_check_counts_teams(db, teams):
    health = run_health_check()
    assert health['teams_total'] >= len(teams)
    assert health['db_ok'] is True


def test_ensure_local_team_logos_updates_remote_urls(app, db, teams, monkeypatch, logo_static):
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


class _LogoCase:
    """Hilfs-Setup: nur eigene Test-Teams, damit keine Seed-Daten angefasst werden."""

    REAL_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
                b'<rect width="128" height="128" fill="#123456"/></svg>')

    @classmethod
    def reset_teams(cls, db):
        db.session.query(Team).delete()
        db.session.commit()

    @classmethod
    def logo_path(cls, app, slug):
        import pathlib
        return pathlib.Path(app.static_folder) / 'team_logos' / f'{slug}.svg'


def _cleanup(*paths):
    for p in paths:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def test_ensure_local_team_logos_fallback_bei_downloadfehler(app, db, monkeypatch, logo_static):
    """Schlaegt der Download fehl, wird ein markiertes Fallback-SVG abgelegt."""
    _LogoCase.reset_teams(db)
    db.session.add(Team(name='Fallback Verein', short_name='ZZF', logo='https://example.test/x.svg', color='#ff0000'))
    db.session.commit()
    path = _LogoCase.logo_path(app, 'zzf')

    def boom(*args, **kwargs):
        raise ConnectionError('offline')

    monkeypatch.setattr('requests.sessions.Session.get', boom)
    try:
        with app.app_context():
            res = ensure_local_team_logos()
            team = Team.query.filter_by(short_name='ZZF').one()
            assert res['fallback'] == 1
            assert res['downloaded'] == 0
            assert team.logo == '/static/team_logos/zzf.svg'
        assert b'data-generated="wulmstoerper-fallback"' in path.read_bytes()
    finally:
        _cleanup(path)


def test_ensure_local_team_logos_skips_valid_local(app, db, monkeypatch, logo_static):
    """Gueltige lokale Logos werden uebersprungen; kein Downloadversuch."""
    _LogoCase.reset_teams(db)
    db.session.add(Team(name='Lokal Verein', short_name='ZZL', logo='/static/team_logos/zzl.svg', color='#123456'))
    db.session.commit()
    path = _LogoCase.logo_path(app, 'zzl')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_LogoCase.REAL_SVG)

    def boom(*args, **kwargs):
        raise AssertionError('kein Download erwartet')

    monkeypatch.setattr('requests.sessions.Session.get', boom)
    try:
        with app.app_context():
            res = ensure_local_team_logos()
            team = Team.query.filter_by(short_name='ZZL').one()
            assert res['skipped'] == 1
            assert team.logo == '/static/team_logos/zzl.svg'
        assert path.read_bytes() == _LogoCase.REAL_SVG
    finally:
        _cleanup(path)


def test_ensure_local_team_logos_replaces_generated_fallback(app, db, monkeypatch, logo_static):
    """Ein generiertes Fallback wird bei erfolgreichem Download ersetzt."""
    from maintenance import _fallback_svg
    _LogoCase.reset_teams(db)
    db.session.add(Team(name='Hamburger SV', short_name='HSV', logo='/static/team_logos/hsv.svg', color='#123456'))
    db.session.commit()
    path = _LogoCase.logo_path(app, 'hsv')
    path.parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        team = Team.query.filter_by(short_name='HSV').one()
        path.write_bytes(_fallback_svg(team))

    class SvgResponse:
        ok = True
        content = _LogoCase.REAL_SVG
        headers = {'content-type': 'image/svg+xml'}

    monkeypatch.setattr('requests.sessions.Session.get', lambda *a, **k: SvgResponse())
    try:
        with app.app_context():
            res = ensure_local_team_logos()
            assert res['replaced_fallback'] == 1
            assert res['downloaded'] == 1
        assert path.read_bytes() == _LogoCase.REAL_SVG
    finally:
        _cleanup(path)


def test_update_known_team_logos_dreht_lokale_logos_nicht_zurueck(app, db):
    """KNOWN_TEAM_LOGO_FIXES duerfen lokale Pfade nicht auf externe URLs zuruecksetzen."""
    from sync import update_known_team_logos, KNOWN_TEAM_LOGO_FIXES
    _LogoCase.reset_teams(db)
    db.session.add(Team(name='Lokal St. Pauli', short_name='STP', logo='/static/team_logos/stp.svg', color='#000000'))
    db.session.commit()
    with app.app_context():
        update_known_team_logos()
        team = Team.query.filter_by(short_name='STP').one()
        assert team.logo == '/static/team_logos/stp.svg'

    # Gegenprobe: externes Logo wird auf die bekannte Fix-URL gesetzt
    with app.app_context():
        team = Team.query.filter_by(short_name='STP').one()
        team.logo = 'https://example.test/alt.svg'
        db.session.commit()
        update_known_team_logos()
        team = Team.query.filter_by(short_name='STP').one()
        assert team.logo == KNOWN_TEAM_LOGO_FIXES['STP']


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



def test_eingecheckte_logos_keine_defekten_platzhalter():
    """Repo-Hygiene: eingecheckte Team-Logos duerfen keine Test-Fakes sein.

    Regressions-Schutz: 46-Byte-<svg></svg>-Stubs aus Tests waren einmal
    committed worden und gingen per FTP-Upload auf den Server; dort brachen
    die lokal referenzierten Logos, bis das Wartungscenter sie neu lud.
    """
    import pathlib
    logo_dir = pathlib.Path(__file__).resolve().parent.parent / 'static' / 'team_logos'
    if not logo_dir.is_dir() or not any(logo_dir.iterdir()):
        pytest.skip('keine eingecheckten Logos vorhanden')
    for p in sorted(logo_dir.iterdir()):
        data = p.read_bytes()
        assert len(data) > 200, f'{p.name} wirkt wie ein Test-Fake/Stub ({len(data)} Bytes)'
        head = data[:200].lstrip()
        ok = (head.startswith(b'<svg') or head.startswith(b'<?xml')
              or data[:8] == b'\x89PNG\r\n\x1a\n')
        assert ok, f'{p.name}: weder SVG noch PNG — womoglich Caption kaputt'
