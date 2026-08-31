"""Export-Abdeckung: PDF-Saison-Report (reportlab) + CSV-Export + Graceful-Paths."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction


def _login(client, user):
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)


def _mk_finished(db, competition, teams, user, home=2, away=1, tip_h=2, tip_a=1):
    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=3),
              status='finished', home_score=home, away_score=away)
    db.session.add(m)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=m.id, home_tip=tip_h, away_tip=tip_a, points=4))
    db.session.commit()
    return m


def test_generate_season_pdf_returns_pdf_bytes(client, db, user, competition, teams, app):
    """PDF-Builder liefert mit echten Daten ein valides reportlab-Dokument."""
    from export import generate_season_pdf
    _mk_finished(db, competition, teams, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    _login(client, user)
    with app.test_request_context():
        buf = generate_season_pdf(user)
    assert buf is not None
    data = buf.read()
    assert data[:4] == b'%PDF'
    assert len(data) > 1000


def test_generate_season_pdf_without_tips_still_builds(client, db, user, competition, app):
    """Auch komplett ohne Tipps muss der Report bauen (leere Tabellen)."""
    from export import generate_season_pdf
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    with app.test_request_context():
        buf = generate_season_pdf(user)
    assert buf is not None and buf.read()[:4] == b'%PDF'


def test_export_pdf_route_sends_attachment(client, db, user, competition, teams):
    _mk_finished(db, competition, teams, user)
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/export/pdf')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'
    assert b'%PDF' in resp.data[:8]
    assert 'attachment' in resp.headers.get('Content-Disposition', '')
    assert 'Saison-Report_' in resp.headers.get('Content-Disposition', '')


def test_export_pdf_route_without_reportlab_redirects(client, db, user, competition, monkeypatch):
    """Fehlt reportlab (Rueckgabe None), wird sauber auf den Saisonbericht umgeleitet."""
    import main_export_routes
    monkeypatch.setattr(main_export_routes, "generate_season_pdf", lambda u: None)
    _login(client, user)
    resp = client.get('/export/pdf')
    assert resp.status_code == 302
    assert '/recap' in resp.headers['Location']


def test_export_csv_contains_german_header_and_tip_data(client, db, user, competition, teams):
    _mk_finished(db, competition, teams, user, home=3, away=0, tip_h=2, tip_a=1)
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/export/csv')
    assert resp.status_code == 200
    text = resp.data.decode('utf-8-sig')
    head = text.splitlines()[0]
    assert 'Spieltag' in head and 'Punkte' in head and 'Joker' in head and 'Ergebnis' in head
    row = text.splitlines()[1]
    assert 'FC Bayern München' in row
    assert '2:1' in row and '3:0' in row  # Tipp und Ergebnis getrennt ausgegeben


def test_export_csv_scoped_to_active_competition(client, db, user, competition, teams, app, monkeypatch):
    """CSV zeigt nur Tipps des aktiven Wettbewerbs, nicht die anderer Ligen."""
    from models import Competition, Match, Prediction as P
    other = Competition(code='FAKE2', name='Andere Liga', season='2026', matchdays=34, teams_count=18)
    db.session.add(other)
    db.session.commit()
    m_other = Match(competition_id=other.id, matchday=1,
                    home_team_id=teams[2].id, away_team_id=teams[3].id,
                    kickoff=datetime.now(timezone.utc) - timedelta(days=2),
                    status='finished', home_score=1, away_score=0)
    db.session.add(m_other)
    db.session.add(P(user_id=user.id, match_id=m_other.id, home_tip=1, away_tip=0, points=4))
    _mk_finished(db, competition, teams, user)
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/export/csv')
    text = resp.data.decode('utf-8-sig')
    assert 'FC Bayern München' in text          # aktiver Wettbewerb drin
    assert 'Bayer Leverkusen' not in text       # Fremd-Liga-Tipp nicht drin
