"""Tests fuer Tippuebersicht / Tippmatrix."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction, User


def _login(client, user):
    return client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)


def test_tip_overview_hides_other_tips_before_kickoff(client, db, user, competition, teams):
    other = User(username='other', email='other@example.com')
    other.set_password('testpass123')
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    db.session.add_all([other, match])
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=2, away_tip=1))
    db.session.add(Prediction(user_id=other.id, match_id=match.id, home_tip=3, away_tip=0))
    db.session.commit()

    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/tipps/1')
    assert resp.status_code == 200
    assert b'2:1' in resp.data          # eigener Tipp sichtbar
    assert b'<strong>3:0</strong>' not in resp.data      # fremder Tipp noch verborgen
    assert '🔒'.encode('utf-8') in resp.data


def test_tip_overview_shows_other_tips_after_kickoff(client, db, user, competition, teams):
    other = User(username='other', email='other@example.com')
    other.set_password('testpass123')
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=5), status='live',
        home_score=0, away_score=0
    )
    db.session.add_all([other, match])
    db.session.commit()
    db.session.add(Prediction(user_id=other.id, match_id=match.id, home_tip=3, away_tip=0))
    db.session.commit()

    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/tipps/1')
    assert resp.status_code == 200
    assert b'<strong>3:0</strong>' in resp.data


def test_tip_overview_live_api_returns_points(client, db, user, finished_match):
    db.session.add(Prediction(
        user_id=user.id, match_id=finished_match.id,
        home_tip=3, away_tip=1, points=4
    ))
    db.session.commit()
    _login(client, user)
    resp = client.get('/api/tip-overview/live/1?sort=total')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    row = next(r for r in data['rows'] if r['user_id'] == user.id)
    assert row['total_points'] >= 4
    assert row['matchday_points'] >= 4


# ------------------------------------------------------------- Auffindbarkeit (Navigation)

def _css_text():
    import pathlib
    return (pathlib.Path(__file__).resolve().parents[1]
            / "static" / "css" / "style.css").read_text(encoding="utf-8")


def test_primary_nav_shows_tip_overview_on_all_devices(auth_client):
    """Der Link haette frueher ein hidden-desktop trug -> auf Desktop unsichtbar.

    Jetzt fester Prim\u00e4r-Punkt "Tipps" (ohne hidden-*), plus eigener Tab in der
    mobilen Bottom-Tabbar.
    """
    html = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert '<a href="/tipps" class="nav-link' in html  # kein hidden-desktop mehr
    assert "Tippübersicht: alle Tipps" in html  # Titel-Tooltip erklaert den Kurz-Label
    assert '<span class="bt-icon">👀</span><span class="bt-label">Tipps</span>' in html


def test_bottom_tabbar_grid_has_five_columns():
    """Es gibt zwei .bottom-tabbar-Regeln (Basis: display none; Media: Grid).
    Die 5-Spalten-Regel muss zur Tabbar-Blockdefinition gehoeren."""
    css = _css_text()
    idx = css.index("grid-template-columns: repeat(5, 1fr);")
    opener = css.rindex(".bottom-tabbar {", 0, idx)
    assert 0 < idx - opener < 400


def test_tip_overview_marks_nav_active(auth_client):
    html = auth_client.get("/tipps").get_data(as_text=True)
    assert '<a href="/tipps" class="nav-link active' in html


def test_manifest_shortcut_targets_tip_overview(client):
    """PWA-Verknuepfung (Long-Press aufs App-Icon) zeigt direkt zur Tippuebersicht."""
    resp = client.get("/manifest.json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(s.get("url") == "/tipps" for s in data.get("shortcuts", []))
