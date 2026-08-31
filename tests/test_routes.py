"""Tests fuer Flask Routes."""
import pytest


class TestAuthRoutes:
    """Test cases fuer Auth Blueprint."""
    
    def test_login_page_loads(self, client):
        """Test: Login-Seite ist erreichbar."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Anmelden' in response.data or b'Login' in response.data
    
    def test_register_page_requires_invite(self, client):
        """Test: Registrierung ist ohne Einladungscode gesperrt."""
        response = client.get('/auth/register')
        assert response.status_code == 403
        assert 'Einladungslink'.encode('utf-8') in response.data or 'Einladung'.encode('utf-8') in response.data
    
    def test_valid_login(self, client, user):
        """Test: Gueltiger Login funktioniert."""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Sollte weiterleiten zu Dashboard oder zeigt angemeldeten Status
    
    def test_invalid_login(self, client, user):
        """Test: Ungueltiger Login wird abgelehnt."""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'falsch' in response.data.lower() or b'invalid' in response.data.lower()
    
    def test_logout(self, auth_client):
        """Test: Logout funktioniert."""
        response = auth_client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200

    def test_register_with_invite_code(self, client, db, user):
        """Test: Registrierung mit gueltigem Einladungscode funktioniert."""
        from datetime import datetime, timedelta, timezone
        from models import InvitationCode, User

        inv = InvitationCode(
            code='invite-test-123', invited_by_user_id=user.id,
            email='neu@example.com', max_uses=1, uses=0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.session.add(inv)
        db.session.commit()
        response = client.post('/auth/register?invite=invite-test-123', data={
            'invite': 'invite-test-123',
            'username': 'newuser',
            'email': 'neu@example.com',
            'password': 'testpass123',
            'confirm': 'testpass123',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert User.query.filter_by(email='neu@example.com').first() is not None
        db.session.refresh(inv)
        assert inv.uses == 1


class TestMainRoutes:
    """Test cases fuer Main Blueprint."""
    
    def test_landing_page(self, client):
        """Test: Startseite ist erreichbar."""
        response = client.get('/')
        assert response.status_code in [200, 302]  # OK oder Redirect
    
    def test_dashboard_requires_login(self, client):
        """Test: Dashboard erfordert Login."""
        response = client.get('/dashboard', follow_redirects=True)
        assert response.status_code == 200
        # Sollte Login-Seite zeigen
        assert b'Anmelden' in response.data or b'Bitte melde dich an' in response.data
    
    def test_dashboard_accessible_when_logged_in(self, auth_client):
        """Test: Dashboard erreichbar wenn eingeloggt."""
        response = auth_client.get('/dashboard')
        assert response.status_code == 200
        assert 'Tippen →'.encode('utf-8') in response.data
    
    def test_schedule_page(self, auth_client):
        """Test: Spiele-&-Tipps-Seite ist erreichbar und nicht mehr als Spielplan beschriftet."""
        response = auth_client.get('/spielplan', follow_redirects=True)
        assert response.status_code == 200
        assert 'Spiele &amp; Tipps'.encode('utf-8') in response.data
    
    def test_leaderboard_page(self, auth_client):
        """Test: Rangliste ist oeffentlich."""
        response = auth_client.get('/tabelle', follow_redirects=True)
        assert response.status_code == 200
        assert 'Spieler-Info'.encode('utf-8') in response.data
        assert 'vollen Namen &amp; Lieblingsverein'.encode('utf-8') in response.data
        assert 'Smartphone: Spieler kurz antippen'.encode('utf-8') in response.data
        assert b'>Tipps</th>' in response.data
        assert b'>Exakt</th>' in response.data
        assert b'>Tendenz</th>' in response.data
        assert b'ST-Siege' in response.data

    def test_more_page_requires_login(self, client):
        """Test: Mehr-Seite erfordert Login."""
        response = client.get('/mehr')
        assert response.status_code in [302, 401, 403]

    def test_more_page_accessible_when_logged_in(self, auth_client):
        """Test: Mehr-Seite ist fuer eingeloggte Nutzer erreichbar."""
        response = auth_client.get('/mehr')
        assert response.status_code == 200
        assert 'Hilfe &amp; Regeln'.encode() in response.data
        assert 'Sonderfragen'.encode() in response.data

    def test_help_rules_page_accessible_when_logged_in(self, auth_client):
        """Test: Hilfe-/Regelseite ist erreichbar."""
        response = auth_client.get('/hilfe')
        assert response.status_code == 200
        assert 'Punkte'.encode() in response.data
        assert 'Joker'.encode() in response.data
        assert 'vollem Namen und Lieblingsverein'.encode('utf-8') in response.data
        assert 'Smartphone kannst du den Spieler kurz antippen'.encode('utf-8') in response.data

    def test_rules_alias_redirectless(self, auth_client):
        """Test: /regeln ist als stabiler Alias erreichbar."""
        response = auth_client.get('/regeln')
        assert response.status_code == 200
        assert 'Tippabgabe bis Anpfiff'.encode() in response.data

    def test_season_recap_accessible_when_logged_in(self, auth_client):
        """Test: Saisonbericht ist fuer eingeloggte Nutzer erreichbar."""
        response = auth_client.get('/recap')
        assert response.status_code == 200
        assert 'das war deine Saison'.encode() in response.data


class TestAdminRoutes:
    """Test cases fuer Admin Blueprint."""
    
    def test_admin_requires_login(self, client):
        """Test: Admin erfordert Login."""
        response = client.get('/admin/', follow_redirects=True)
        assert response.status_code == 200
    
    def test_admin_requires_admin_rights(self, auth_client):
        """Test: Admin erfordert Admin-Rechte."""
        response = auth_client.get('/admin/', follow_redirects=True)
        # Sollte 403 oder Redirect sein
        assert response.status_code in [200, 403]
    
    def test_admin_accessible_for_admin(self, client, admin_user):
        """Test: Admin-Panel fuer Admin erreichbar."""
        client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)
        
        response = client.get('/admin/')
        assert response.status_code == 200

    def test_admin_test_reminder_route(self, client, admin_user, monkeypatch):
        """Test: Admin-Testfunktion fuer Tipp-Erinnerungen ist erreichbar."""
        client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)

        monkeypatch.setattr('notification_center.send_test_missing_tip_notification', lambda user: {
            'email': True, 'push': False, 'telegram': False, 'whatsapp': False
        })
        response = client.post('/admin/settings/test-reminder', data={
            'csrf_token': '',
            'reminders_enabled': 'y',
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'Test-Erinnerung'.encode('utf-8') in response.data

    def test_admin_special_questions_page_accessible(self, client, admin_user):
        """Test: Sonderfragen-Adminseite laedt ohne 500er."""
        client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)
        response = client.get('/admin/special-questions')
        assert response.status_code == 200
        assert 'Sonderfragen'.encode('utf-8') in response.data

    def test_admin_badges_page_accessible(self, client, admin_user):
        """Test: Badges-Adminseite laedt ohne 500er."""
        client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)
        response = client.get('/admin/badges')
        assert response.status_code == 200
        assert b'Badge' in response.data or 'Badges'.encode('utf-8') in response.data

    def test_admin_set_special_answer(self, client, db, admin_user):
        """Test: Antwort auf Sonderfrage speichern laedt ohne 500er."""
        from datetime import datetime, timedelta, timezone
        from models import SpecialQuestion

        client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)
        q = SpecialQuestion(
            text='Wer wird Meister?', answer_type='text',
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            points_value=5,
        )
        db.session.add(q)
        db.session.commit()

        response = client.post(f'/admin/special-question/{q.id}/answer', data={
            'correct_answer': 'FC Bayern München',
        }, follow_redirects=True)
        assert response.status_code == 200
        db.session.refresh(q)
        assert q.correct_answer == 'FC Bayern München'

    def test_admin_set_special_answer_evaluation_error_does_not_500(self, client, db, admin_user, monkeypatch):
        """Test: Auswertungsfehler wird abgefangen, Antwort bleibt gespeichert."""
        from datetime import datetime, timedelta, timezone
        from models import SpecialQuestion

        client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin123'
        }, follow_redirects=True)
        q = SpecialQuestion(
            text='Testfrage', answer_type='text',
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            points_value=5,
        )
        db.session.add(q)
        db.session.commit()
        monkeypatch.setattr('admin_special_questions_routes.evaluate_special_predictions', lambda: (_ for _ in ()).throw(RuntimeError('boom')))

        response = client.post(f'/admin/special-question/{q.id}/answer', data={
            'correct_answer': 'Antwort',
        }, follow_redirects=True)
        assert response.status_code == 200
        db.session.refresh(q)
        assert q.correct_answer == 'Antwort'
        assert b'Auswertung fehlgeschlagen' in response.data


class TestAPIRoutes:
    """Test cases fuer API Blueprint."""
    
    def test_api_tip_requires_login(self, client, match):
        """Test: Tipp-API erfordert Login."""
        response = client.post(f'/api/tip/{match.id}', json={
            'home_tip': 2,
            'away_tip': 1
        })
        # Sollte 401 oder 302 (Redirect zu Login)
        assert response.status_code in [401, 302, 403]
    
    def test_api_tip_valid(self, auth_client, match):
        """Test: Gueltiger Tipp wird gespeichert."""
        response = auth_client.post(f'/api/tip/{match.id}', 
            json={'home_tip': 2, 'away_tip': 1},
            follow_redirects=True
        )
        assert response.status_code == 200


def test_invite_page_accessible_for_user(auth_client):
    resp = auth_client.get('/einladen')
    assert resp.status_code == 200
    assert 'Mitspieler einladen'.encode('utf-8') in resp.data
    assert b'/auth/register' in resp.data


def test_invite_sends_email(monkeypatch, auth_client):
    sent = []

    def fake_send_email(subject, recipients, body, html=None):
        sent.append((subject, recipients, body))
        return True

    monkeypatch.setattr('mail_helpers.send_email', fake_send_email)
    resp = auth_client.post('/einladen', data={
        'emails': 'neu@example.de, neu@example.de; invalid',
        'message': 'Mach mit!',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert len(sent) == 1
    assert sent[0][1] == ['neu@example.de']
    assert 'Mach mit!' in sent[0][2]


def test_user_can_send_test_notification(auth_client, monkeypatch):
    calls = []

    def fake_test(user):
        calls.append(user.id)
        return {'email': True, 'push': False, 'telegram': False, 'whatsapp': False}

    monkeypatch.setattr('notification_center.send_test_missing_tip_notification', fake_test)
    resp = auth_client.post('/profil/test-benachrichtigung', follow_redirects=True)
    assert resp.status_code == 200
    assert calls
    assert 'Test-Benachrichtigung'.encode('utf-8') in resp.data


def test_user_can_answer_special_questions(client, db, user):
    """Test: User kann Sonderfragen beantworten ohne 500er."""
    from datetime import datetime, timedelta, timezone
    from models import SpecialQuestion, SpecialPrediction

    q = SpecialQuestion(
        text='Wer wird Meister?', answer_type='text',
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        points_value=5,
    )
    db.session.add(q)
    db.session.commit()
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)

    response = client.post('/sondertipps', data={f'q_{q.id}': 'FC Bayern München'}, follow_redirects=True)
    assert response.status_code == 200
    sp = SpecialPrediction.query.filter_by(user_id=user.id, question_id=q.id).first()
    assert sp is not None
    assert sp.answer == 'FC Bayern München'


def test_user_can_answer_multi_team_special_question(client, db, user, teams):
    """Test: Multi-Team-Sonderfrage nutzt lokalen JSON-Import und speichert Liste."""
    from datetime import datetime, timedelta, timezone
    import json
    from models import SpecialQuestion, SpecialPrediction

    q = SpecialQuestion(
        text='Welche Teams steigen auf?', answer_type='multi_team', multi_count=2,
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        points_value=5,
    )
    db.session.add(q)
    db.session.commit()
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)

    response = client.post('/sondertipps', data={f'q_{q.id}': [teams[0].name, teams[1].name]}, follow_redirects=True)
    assert response.status_code == 200
    sp = SpecialPrediction.query.filter_by(user_id=user.id, question_id=q.id).first()
    assert sp is not None
    assert json.loads(sp.answer) == [teams[0].name, teams[1].name]


def test_special_question_team_choices_use_current_match_teams(client, db, user, competition, teams):
    """Sonderfragen zeigen bei Teamantworten nur aktuelle Teams aus dem Spielplan."""
    from datetime import datetime, timedelta, timezone
    from models import Match, SpecialQuestion, Team

    stale = Team(name='Alter Absteiger FC', short_name='AAF', logo='x')
    db.session.add(stale)
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    q = SpecialQuestion(
        competition_id=competition.id,
        text='Welche 2 Teams steigen ab?', answer_type='multi_team', multi_count=2,
        deadline=datetime.now(timezone.utc) + timedelta(days=2), points_value=10,
    )
    db.session.add_all([match, q])
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/sondertipps')
    assert resp.status_code == 200
    assert teams[0].name.encode('utf-8') in resp.data
    assert teams[1].name.encode('utf-8') in resp.data
    assert 'Alter Absteiger FC'.encode('utf-8') not in resp.data
    assert b'2 Mannschaft' in resp.data or '2 Mannschaft'.encode('utf-8') in resp.data


def test_admin_special_question_team_choices_use_current_match_teams(client, db, admin_user, competition, teams):
    """Admin-Aufloesung von Team-Sonderfragen zeigt nur aktuelle Teams."""
    from datetime import datetime, timedelta, timezone
    from models import Match, SpecialQuestion, Team

    stale = Team(name='Ehemaliger Erstligist', short_name='ALT', logo='x')
    db.session.add(stale)
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    q = SpecialQuestion(
        competition_id=competition.id,
        text='Bester Aufsteiger?', answer_type='team',
        deadline=datetime.now(timezone.utc) + timedelta(days=2), points_value=6,
    )
    db.session.add_all([match, q])
    db.session.commit()

    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/admin/special-questions')
    assert resp.status_code == 200
    assert teams[0].name.encode('utf-8') in resp.data
    assert teams[1].name.encode('utf-8') in resp.data
    assert 'Ehemaliger Erstligist'.encode('utf-8') not in resp.data


def test_special_question_restricted_team_options(client, db, user, competition, teams):
    """Team-Sonderfrage kann auf bestimmte Teams eingeschraenkt werden."""
    from datetime import datetime, timedelta, timezone
    import json
    from models import Match, SpecialQuestion, SpecialPrediction

    # Alle vier Teams sind im aktuellen Spielplan, aber nur zwei sind als Antwort erlaubt.
    db.session.add(Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    ))
    db.session.add(Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[2].id, away_team_id=teams[3].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    ))
    q = SpecialQuestion(
        competition_id=competition.id,
        text='Wer wird bester Aufsteiger?', answer_type='team',
        options=json.dumps([teams[0].name, teams[1].name]),
        deadline=datetime.now(timezone.utc) + timedelta(days=2), points_value=6,
    )
    db.session.add(q)
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/sondertipps')
    assert resp.status_code == 200
    assert teams[0].name.encode('utf-8') in resp.data
    assert teams[1].name.encode('utf-8') in resp.data
    assert teams[2].name.encode('utf-8') not in resp.data

    # Nicht erlaubte Antwort wird serverseitig ignoriert.
    resp = client.post('/sondertipps', data={f'q_{q.id}': teams[2].name}, follow_redirects=True)
    assert resp.status_code == 200
    assert SpecialPrediction.query.filter_by(user_id=user.id, question_id=q.id).first() is None


def test_admin_create_special_question_restricted_teams(client, db, admin_user, competition, teams):
    """Admin kann erlaubte Teams fuer Mannschaftsfragen als Optionen speichern."""
    from datetime import datetime, timedelta, timezone
    import json
    from models import Match, SpecialQuestion

    for i in range(0, 4, 2):
        db.session.add(Match(
            competition_id=competition.id, matchday=1,
            home_team_id=teams[i].id, away_team_id=teams[i+1].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
        ))
    db.session.commit()
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code

    resp = client.post('/admin/special-questions', data={
        'text': 'Wer wird bester Aufsteiger?',
        'description': '',
        'answer_type': 'team',
        'options': f'{teams[0].name}\n{teams[1].name}',
        'multi_count': '1',
        'deadline': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
        'points_value': '6',
        'correct_answer': '',
    }, follow_redirects=True)
    assert resp.status_code == 200
    q = SpecialQuestion.query.filter_by(text='Wer wird bester Aufsteiger?').first()
    assert q is not None
    assert json.loads(q.options) == [teams[0].name, teams[1].name]
    assert teams[2].name.encode('utf-8') not in resp.data


def test_registration_mode_open_allows_registration(client, db):
    from models import User
    from scoring import set_setting

    set_setting('registration_mode', 'open')
    resp = client.post('/auth/register', data={
        'username': 'openuser',
        'email': 'open@example.com',
        'password': 'testpass123',
        'confirm': 'testpass123',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert User.query.filter_by(email='open@example.com').first() is not None


def test_registration_mode_closed_blocks_even_invite(client, db, user):
    from datetime import datetime, timedelta, timezone
    from models import InvitationCode, User
    from scoring import set_setting

    set_setting('registration_mode', 'closed')
    inv = InvitationCode(
        code='closed-invite', invited_by_user_id=user.id,
        email='closed@example.com', max_uses=1, uses=0,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.session.add(inv)
    db.session.commit()
    resp = client.post('/auth/register?invite=closed-invite', data={
        'invite': 'closed-invite',
        'username': 'closeduser',
        'email': 'closed@example.com',
        'password': 'testpass123',
        'confirm': 'testpass123',
    }, follow_redirects=True)
    assert resp.status_code == 403
    assert User.query.filter_by(email='closed@example.com').first() is None
    assert 'geschlossen'.encode('utf-8') in resp.data


def test_admin_integrity_page_and_repair(client, db, admin_user, user, competition, teams):
    from datetime import datetime, timedelta, timezone
    from models import Match, Prediction

    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    match1 = Match(competition_id=competition.id, matchday=1, home_team_id=teams[0].id, away_team_id=teams[1].id, kickoff=datetime.now(timezone.utc)+timedelta(days=1), status='scheduled')
    match2 = Match(competition_id=competition.id, matchday=1, home_team_id=teams[2].id, away_team_id=teams[3].id, kickoff=datetime.now(timezone.utc)+timedelta(days=1), status='scheduled')
    db.session.add_all([match1, match2]); db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=match1.id, home_tip=1, away_tip=0, joker=True))
    db.session.add(Prediction(user_id=user.id, match_id=match2.id, home_tip=2, away_tip=1, joker=True))
    db.session.commit()

    resp = client.get('/admin/integrity')
    assert resp.status_code == 200
    assert 'Mehrfach-Joker'.encode('utf-8') in resp.data
    resp = client.post('/admin/integrity', follow_redirects=True)
    assert resp.status_code == 200
    assert Prediction.query.filter_by(user_id=user.id, joker=True).count() == 1


def test_admin_invitations_page_create_deactivate(client, admin_user):
    from models import InvitationCode

    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    resp = client.get('/admin/invitations')
    assert resp.status_code == 200
    assert 'Einladungen'.encode('utf-8') in resp.data
    resp = client.post('/admin/invitations/create', data={'email': 'x@example.com', 'max_uses': '1', 'days': '7'}, follow_redirects=True)
    assert resp.status_code == 200
    inv = InvitationCode.query.filter_by(email='x@example.com').first()
    assert inv is not None
    resp = client.post(f'/admin/invitations/{inv.id}/deactivate', follow_redirects=True)
    assert resp.status_code == 200
    assert inv.uses >= inv.max_uses


def test_prizes_page_accessible_when_logged_in(auth_client):
    """Regression: /preise darf nach expliziten Imports keinen 500er werfen."""
    response = auth_client.get('/preise')
    assert response.status_code == 200
    assert 'Pott'.encode('utf-8') in response.data or 'Preise'.encode('utf-8') in response.data


def test_favicon_route(client):
    """Browser-Favicon-Request soll keinen 404 erzeugen."""
    response = client.get('/favicon.ico')
    assert response.status_code == 200
    assert response.mimetype == 'image/png'


def test_linkify_payment_info_filter(app):
    """Zahlungsinfos: paypal.me-Links werden anklickbar, HTML bleibt escaped."""
    with app.app_context():
        html = app.jinja_env.filters['linkify']('PayPal: paypal.me/meyerheiko <script>')
    rendered = str(html)
    assert 'href="https://paypal.me/meyerheiko"' in rendered
    assert 'target="_blank"' in rendered
    assert '<script>' not in rendered
    assert '&lt;script&gt;' in rendered


def test_tip_entry_always_uses_quick_tip(client, db, user):
    """Klick auf /tippen fuehrt bewusst immer zum Schnelltipp."""
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)

    user.default_tip_view = 'normal'
    db.session.commit()
    resp = client.get('/tippen/1')
    assert resp.status_code in (301, 302)
    assert '/schnelltipp/1' in resp.headers['Location']


def test_profile_saves_default_tip_view(client, db, user):
    """Profil speichert die bevorzugte Standard-Tippansicht."""
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.post('/profil', data={
        'username': user.username,
        'full_name': user.full_name or '',
        'show_full_name': 'y',
        'phone': '',
        'whatsapp_phone': '',
        'whatsapp_apikey': '',
        'favorite_team_id': '0',
        'default_tip_view': 'quick',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(user)
    assert user.default_tip_view == 'quick'


def test_tip_entry_without_matchday_uses_next_open_missing_tip(client, db, user, competition, teams):
    """/tippen springt zum ersten Spieltag mit offenem, ungetipptem Spiel."""
    from datetime import datetime, timedelta, timezone
    from models import Match, Prediction

    m1 = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1),
        status='scheduled',
    )
    m2 = Match(
        competition_id=competition.id,
        matchday=2,
        home_team_id=teams[2].id,
        away_team_id=teams[3].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=8),
        status='scheduled',
    )
    db.session.add_all([m1, m2])
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=m1.id, home_tip=1, away_tip=0))
    user.default_tip_view = 'normal'
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/tippen')
    assert resp.status_code in (301, 302)
    assert '/schnelltipp/2' in resp.headers['Location']


def test_tip_entry_requires_full_name_before_tipping(client, db, user):
    """Ohne vollen Namen wird der User vor dem Tippen ins Profil geschickt."""
    user.full_name = None
    db.session.commit()
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.get('/tippen/1', follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert '/profil' in resp.headers['Location']


def test_stats_dashboard_filters_inactive_bots_and_uses_json_chart_data(client, db, user, competition, teams, monkeypatch, app):
    """Statistikbereich zeigt nur aktivierte Bots und liefert gueltige Chart-Daten."""
    from datetime import datetime, timedelta, timezone
    from models import Match, Prediction, User
    from scoring import set_setting

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)

    match = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished',
        home_score=2,
        away_score=0,
    )
    active_bot = User(username='ProBot', email='probot@bot.local')
    inactive_bot = User(username='MasterBot', email='masterbot@bot.local')
    active_bot.set_password('x')
    inactive_bot.set_password('x')
    db.session.add_all([match, active_bot, inactive_bot])
    db.session.commit()

    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=2, away_tip=0, points=4))
    db.session.add(Prediction(user_id=active_bot.id, match_id=match.id, home_tip=2, away_tip=1, points=2))
    db.session.add(Prediction(user_id=inactive_bot.id, match_id=match.id, home_tip=0, away_tip=2, points=0))
    db.session.commit()
    set_setting('bot_active_ProBot', True)
    set_setting('bot_active_MasterBot', False)

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/stats')
    assert resp.status_code == 200
    assert 'vs aktive KI-Bots'.encode('utf-8') in resp.data
    assert b'ProBot' in resp.data
    assert b'MasterBot' not in resp.data
    assert 'Ranglistenverlauf aller Spieler'.encode('utf-8') in resp.data
    assert b'rankProgressChart' in resp.data
    assert b'data-rank-player="0"' in resp.data
    assert 'Tipp-Stil'.encode('utf-8') in resp.data
    assert b'2:0' in resp.data


def test_quick_tip_displays_official_table_positions(client, db, user, competition, teams, monkeypatch, app):
    """Schnelltipp zeigt offizielle Tabellenplaetze als Tab.-Badge."""
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    match = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1),
        status='scheduled',
    )
    db.session.add(match)
    db.session.commit()

    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([
        {'team': teams[0], 'rank': 7, 'points': 10},
        {'team': teams[1], 'rank': 3, 'points': 14},
    ], None))

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/1')
    assert resp.status_code == 200
    assert b'Tab. 7' in resp.data
    assert b'Tab. 3' in resp.data
    assert 'offizieller Tabellenplatz'.encode('utf-8') in resp.data


def test_admin_edit_special_question_full_before_answers(client, db, admin_user):
    """Ohne Spielerantworten darf Admin Sonderfrage vollstaendig bearbeiten."""
    from datetime import datetime, timedelta, timezone
    from models import SpecialQuestion

    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    q = SpecialQuestion(
        text='Alter Text?', answer_type='text',
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        points_value=5,
    )
    db.session.add(q)
    db.session.commit()

    new_deadline = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M')
    resp = client.post(f'/admin/special-question/{q.id}/edit', data={
        'text': 'Neue Frage?',
        'description': 'Neue Beschreibung',
        'answer_type': 'choice',
        'options': 'A\nB\nC',
        'multi_count': '1',
        'number_min': '',
        'number_max': '',
        'correct_answer': 'B',
        'deadline': new_deadline,
        'points_value': '12',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(q)
    assert q.text == 'Neue Frage?'
    assert q.description == 'Neue Beschreibung'
    assert q.answer_type == 'choice'
    assert q.options is not None and 'B' in q.options
    assert q.correct_answer == 'B'
    assert q.points_value == 12


def test_admin_edit_special_question_limited_after_answers(client, db, admin_user, user):
    """Mit vorhandenen Spielerantworten darf Admin nur Deadline und Punkte aendern."""
    from datetime import datetime, timedelta, timezone
    from models import SpecialQuestion, SpecialPrediction

    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)
    q = SpecialQuestion(
        text='Original?', answer_type='text',
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        points_value=5,
        correct_answer='Alt',
    )
    db.session.add(q)
    db.session.commit()
    db.session.add(SpecialPrediction(user_id=user.id, question_id=q.id, answer='Antwort'))
    db.session.commit()

    new_deadline = (datetime.now() + timedelta(days=20)).strftime('%Y-%m-%dT%H:%M')
    resp = client.post(f'/admin/special-question/{q.id}/edit', data={
        'text': 'Soll ignoriert werden?',
        'description': 'Auch ignorieren',
        'answer_type': 'number',
        'options': '1\n2',
        'multi_count': '3',
        'number_min': '1',
        'number_max': '9',
        'correct_answer': 'Neu',
        'deadline': new_deadline,
        'points_value': '15',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(q)
    assert q.text == 'Original?'
    assert q.answer_type == 'text'
    assert q.correct_answer == 'Alt'
    assert q.points_value == 15
    assert 'nur'.encode('utf-8') in resp.data and 'Punkte'.encode('utf-8') in resp.data


def test_quick_tip_has_prev_next_matchday_buttons(client, db, user, competition, teams, monkeypatch, app):
    """Schnelltipp bietet direkte Buttons fuer vorherigen/naechsten Spieltag."""
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    db.session.add_all([
        Match(competition_id=competition.id, matchday=1, home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'),
        Match(competition_id=competition.id, matchday=2, home_team_id=teams[1].id, away_team_id=teams[2].id,
              kickoff=datetime.now(timezone.utc) + timedelta(days=8), status='scheduled'),
        Match(competition_id=competition.id, matchday=3, home_team_id=teams[2].id, away_team_id=teams[3].id,
              kickoff=datetime.now(timezone.utc) + timedelta(days=15), status='scheduled'),
    ])
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/2')
    assert resp.status_code == 200
    assert 'Spieltag wechseln'.encode('utf-8') in resp.data
    assert b'ST 1' in resp.data
    assert b'ST 3' in resp.data
    assert b'aria-label="Vorheriger Spieltag"' in resp.data
    assert 'aria-label="Nächster Spieltag"'.encode('utf-8') in resp.data
    assert 'Tippübersicht'.encode('utf-8') in resp.data
    assert b'/tipps/2' in resp.data


def test_quick_tip_save_stays_on_quick_tip_page(client, db, user, competition, teams, monkeypatch, app):
    """UX-Fix 2026-08-30: Nach 'Alle Tipps speichern' im Schnelltipp bleibt man
    im Schnelltipp (selber Spieltag) statt auf 'Spiele & Tipps'/Spielplan zu landen."""
    from datetime import datetime, timedelta, timezone
    from models import Match, Prediction

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    match = Match(competition_id=competition.id, matchday=1,
                  home_team_id=teams[0].id, away_team_id=teams[1].id,
                  kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled')
    db.session.add(match)
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.post('/schnelltipp/1', data={
        f'home_{match.id}': '2',
        f'away_{match.id}': '1',
    })

    assert resp.status_code in (301, 302)
    assert '/schnelltipp/1' in resp.headers['Location']
    pred = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
    assert pred is not None
    assert (pred.home_tip, pred.away_tip) == (2, 1)


def test_live_center_uses_polling_not_sse(client, user):
    """Plesk/Passenger-Stabilitaet: Live-Center nutzt kein dauerhaftes SSE."""
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.get('/live')
    assert resp.status_code == 200
    assert b'EventSource' not in resp.data
    # Polling-Logik liegt ausgelagert in static/js/live.js
    assert b'js/live.js' in resp.data
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent / 'static' / 'js' / 'live.js').read_text(encoding='utf-8')
    assert 'startPolling' in js
    assert 'EventSource' not in js


def test_live_center_stream_does_not_block_worker(client, user):
    """Der alte SSE-Endpunkt antwortet sofort, damit keine Worker blockieren."""
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.get('/api/live/center/stream')
    assert resp.status_code == 204


def test_live_center_shows_match_minute(client, db, user, competition, teams, monkeypatch, app):
    """Live-Center zeigt bei Live-Spielen die Spielminute."""
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('routes_api.fetch_live_match_updates', lambda matchday=None: {'ok': True, 'updated': 0, 'live': 1})
    live_match = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=23),
        status='live',
        home_score=1,
        away_score=0,
        minute=23,
    )
    db.session.add(live_match)
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code

    page = client.get('/live')
    assert page.status_code == 200
    assert b'LIVE' in page.data
    assert b'23. Min' in page.data

    api = client.get('/api/live/center')
    assert api.status_code == 200
    payload = api.get_json()
    assert payload['matches'][0]['minute'] == 23


def test_live_leaderboard_uses_clear_stat_labels(client, db, user, competition, teams, monkeypatch, app):
    """Live-Rangliste nutzt klare Labels statt unklarer E/D/T-Abkuerzungen."""
    from datetime import datetime, timedelta, timezone
    from models import Match, Prediction

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('routes_api.fetch_live_match_updates', lambda matchday=None: {'ok': True, 'updated': 0, 'live': 1})
    live_match = Match(
        competition_id=competition.id,
        matchday=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=10),
        status='live',
        home_score=1,
        away_score=0,
    )
    db.session.add(live_match)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=live_match.id, home_tip=1, away_tip=0))
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/live')
    assert resp.status_code == 200
    assert 'exakt'.encode('utf-8') in resp.data
    assert b'Diff' in resp.data
    assert b'Tendenz' in resp.data
    assert b'0E' not in resp.data


def test_closed_special_questions_show_round_answers(client, db, user):
    """Nach Deadline sehen Spieler die Antworten der Runde."""
    from datetime import datetime, timedelta, timezone
    from models import SpecialQuestion, SpecialPrediction, User

    other = User(username='mitspieler', email='mitspieler@example.com', full_name='Mit Spieler')
    other.set_password('x')
    q = SpecialQuestion(
        text='Wer wird Meister?',
        answer_type='text',
        deadline=datetime.now(timezone.utc) - timedelta(hours=1),
        points_value=10,
    )
    db.session.add_all([other, q])
    db.session.commit()
    db.session.add_all([
        SpecialPrediction(user_id=user.id, question_id=q.id, answer='FC Bayern München'),
        SpecialPrediction(user_id=other.id, question_id=q.id, answer='Borussia Dortmund'),
    ])
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.get('/sondertipps')
    assert resp.status_code == 200
    assert 'Antworten der Runde'.encode('utf-8') in resp.data
    assert b'mitspieler' in resp.data
    assert 'Borussia Dortmund'.encode('utf-8') in resp.data


def test_open_special_questions_do_not_show_round_answers(client, db, user):
    """Vor Deadline bleiben Antworten anderer Spieler verborgen."""
    from datetime import datetime, timedelta, timezone
    from models import SpecialQuestion, SpecialPrediction, User

    other = User(username='nochgeheim', email='nochgeheim@example.com')
    other.set_password('x')
    q = SpecialQuestion(
        text='Geheime Frage?',
        answer_type='text',
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        points_value=10,
    )
    db.session.add_all([other, q])
    db.session.commit()
    db.session.add(SpecialPrediction(user_id=other.id, question_id=q.id, answer='Geheime Antwort'))
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    resp = client.get('/sondertipps')
    assert resp.status_code == 200
    assert 'Antworten der Runde'.encode('utf-8') not in resp.data
    assert b'nochgeheim' not in resp.data
    assert 'Geheime Antwort'.encode('utf-8') not in resp.data


def test_quick_tip_finished_matchday_disables_action_buttons(client, db, user, competition, teams, monkeypatch, app):
    """Abgeschlossener Spieltag: 'Zufällig füllen' + 'Alle Tipps speichern' ausgrauen."""
    import re
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    db.session.add_all([
        Match(competition_id=competition.id, matchday=1, home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=7), status='finished', home_score=2, away_score=1),
        Match(competition_id=competition.id, matchday=1, home_team_id=teams[2].id, away_team_id=teams[3].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=8), status='finished', home_score=0, away_score=0),
    ])
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/1')
    assert resp.status_code == 200
    assert re.search(rb'<button[^>]*id="qtRandomBtn"[^>]*disabled', resp.data), "Zufällig-Button muss deaktiviert sein"
    assert re.search(rb'<button[^>]*qt-btn-save[^>]*disabled', resp.data), "Speichern-Button muss deaktiviert sein"
    assert 'abgeschlossen'.encode('utf-8') in resp.data  # Hinweistext


def test_quick_tip_open_matchday_keeps_action_buttons(client, db, user, competition, teams, monkeypatch, app):
    """Spieltag mit offenen Spielen: Buttons bleiben aktiv; geschlossene Eingaben sind disabled."""
    import re
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    done = Match(competition_id=competition.id, matchday=1, home_team_id=teams[0].id, away_team_id=teams[1].id,
                 kickoff=datetime.now(timezone.utc) - timedelta(days=7), status='finished', home_score=2, away_score=1)
    open_ = Match(competition_id=competition.id, matchday=1, home_team_id=teams[2].id, away_team_id=teams[3].id,
                  kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled')
    db.session.add_all([done, open_])
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/1')
    assert resp.status_code == 200
    assert not re.search(rb'<button[^>]*id="qtRandomBtn"[^>]*disabled', resp.data), "Buttons sollen aktiv bleiben"
    assert not re.search(rb'<button[^>]*qt-btn-save[^>]*disabled', resp.data)
    m = re.search(rb'name="home_%d"[^>]*disabled' % done.id, resp.data)
    assert m, "Eingaben des abgeschlossenen Spiels bleiben gesperrt"
    n = re.search(rb'name="home_%d"[^>]*disabled' % open_.id, resp.data)
    assert not n, "Eingaben des offenen Spiels bleiben bedienbar"


def test_quick_tip_finished_match_shows_final_result_and_points(client, db, user, competition, teams, monkeypatch, app):
    """Beendet: offizielles Ergebnis + erzielte Punkte unter den gesperrten Tippfeldern."""
    import re
    from datetime import datetime, timedelta, timezone
    from models import Match, Prediction

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    match = Match(competition_id=competition.id, matchday=1,
                  home_team_id=teams[0].id, away_team_id=teams[1].id,
                  kickoff=datetime.now(timezone.utc) - timedelta(days=7),
                  status='finished', home_score=3, away_score=1)
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=2, away_tip=1, points=3))
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/1')
    assert resp.status_code == 200
    m = re.search(rb'qt-final-result[^>]*>(.*?)</div>', resp.data, re.S)
    assert m, "Ergebniszeile fehlt"
    assert b'Ergebnis' in m.group(1) and b'<strong>3:1</strong>' in m.group(1), "Endergebnis wird nicht angezeigt"
    assert b'+3 Pkt' in m.group(1), "Erzielte Punkte fehlen"


def test_quick_tip_unfinished_match_shows_no_result_box(client, db, user, competition, teams, monkeypatch, app):
    """Offene Spiele bekommen keine Ergebnisanzeige."""
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    db.session.add(Match(competition_id=competition.id, matchday=1,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'))
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/1')
    assert resp.status_code == 200
    assert b'qt-final-result' not in resp.data, "Ergebnisbox bei offenem Spiel unerwuenscht"


def test_quick_tip_form_dots_show_german_letters(client, db, user, competition, teams, monkeypatch, app):
    """Formkurve zeigt deutsche Buchstaben S/U/N (statt englisch W/D/L), passend zur Legende."""
    from datetime import datetime, timedelta, timezone
    from models import Match

    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('sync.fetch_live_standings', lambda: ([], 'keine daten'))
    db.session.add_all([
        # beendete Vorspiele: Winstreak/D/L fuer teams[0]/[2]/[1]
        Match(competition_id=competition.id, matchday=1, home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=7), status='finished', home_score=2, away_score=1),
        Match(competition_id=competition.id, matchday=1, home_team_id=teams[2].id, away_team_id=teams[3].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=5), status='finished', home_score=1, away_score=1),
        Match(competition_id=competition.id, matchday=1, home_team_id=teams[3].id, away_team_id=teams[0].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=2), status='finished', home_score=1, away_score=0),
        # anstehendes Spiel, damit die Formkurve von teams[0] gerendert wird
        Match(competition_id=competition.id, matchday=2, home_team_id=teams[0].id, away_team_id=teams[2].id,
              kickoff=datetime.now(timezone.utc) + timedelta(days=3), status='scheduled'),
    ])
    db.session.commit()

    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    resp = client.get('/schnelltipp/2')
    assert resp.status_code == 200
    # Klassen bleiben englisch (CSS), angezeigte Buchstaben deutsch:
    assert b'form-W">S<' in resp.data, "Sieg muss als 'S' erscheinen"
    assert b'form-D">U<' in resp.data, "Unentschieden muss als 'U' erscheinen"
    assert b'form-L">N<' in resp.data, "Niederlage muss als 'N' erscheinen"
    assert b'form-W">W<' not in resp.data and b'form-D">D<' not in resp.data and b'form-L">L<' not in resp.data
