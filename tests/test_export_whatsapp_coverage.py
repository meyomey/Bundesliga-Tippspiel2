"""Coverage-Runde export.py & whatsapp.py.

Schliesst die dokumentierten Luecken:
- export.py:  reportlab-ImportError-Pfad, Rank-Ausnahme-Pfad, MatchdayWinner-
              Tabelle, Badge-Sektion (Ziel: ~100 %)
- whatsapp.py: Eingabe-Guards, Fehlerpfade (HTTP-Status, RequestException),
              Massen-Reminder mit Bot-Filter/Tipp-Skip, Scheduler-Job,
              Test-Nachricht ohne Konfiguration (Ziel: ~100 %)
"""
from datetime import datetime, timedelta, timezone

import requests

from models import Match, MatchdayWinner, Prediction, User, UserBadge


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


# ============================================================ export.py ==


def test_generate_season_pdf_without_reportlab_returns_none(db, user, competition, monkeypatch):
    """Fehlt reportlab (ImportError), liefert der Builder None statt zu crashen."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith('reportlab'):
            raise ImportError('reportlab fehlt (Test)')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', fake_import)
    from export import generate_season_pdf
    assert generate_season_pdf(user) is None


def test_generate_season_pdf_rank_error_is_graceful(client, db, user, competition, teams, app, monkeypatch):
    """Wirft die Rang-Berechnung eine Exception, baut der Report trotzdem."""
    import stats
    from export import generate_season_pdf

    _mk_finished(db, competition, teams, user)
    monkeypatch.setattr(stats, '_compute_rank_through', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('kaputt')))
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    with app.test_request_context():
        buf = generate_season_pdf(user)
    assert buf is not None
    assert buf.read()[:4] == b'%PDF'


def test_generate_season_pdf_includes_matchday_wins_and_badges(client, db, user, competition, teams, app, badge):
    """MatchdayWinner-Tabelle und Badge-Sektion werden gerendert (Report baut)."""
    from export import generate_season_pdf

    _mk_finished(db, competition, teams, user)
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=1, user_id=user.id,
                                  points=12, exact_count=2, is_shared=False))
    db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
    db.session.commit()
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    with app.test_request_context():
        buf = generate_season_pdf(user)
    assert buf is not None
    data = buf.read()
    assert data[:4] == b'%PDF'
    assert len(data) > 1000


def test_generate_season_pdf_with_full_name(client, db, user, competition, app):
    """Vollstaendiger Name landet im Report (Zweig if user.full_name)."""
    from export import generate_season_pdf

    user.full_name = 'Tante Kathe'
    db.session.commit()
    _login(client, user)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code
    with app.test_request_context():
        buf = generate_season_pdf(user)
    assert buf is not None and buf.read()[:4] == b'%PDF'


# =========================================================== whatsapp.py ==


def test_whatsapp_empty_inputs_guard(monkeypatch, app):
    """Leere Telefonnummer/API-Key/Nachricht -> False ohne Request."""
    from whatsapp import send_whatsapp_message

    def boom(*a, **k):
        raise AssertionError('requests.get darf nicht aufgerufen werden')

    monkeypatch.setattr('whatsapp.requests.get', boom)
    with app.app_context():
        assert send_whatsapp_message('', '123', 'Hallo') is False
        assert send_whatsapp_message('+491701234', '', 'Hallo') is False
        assert send_whatsapp_message('+491701234', '123', '') is False


def test_whatsapp_phone_digits_only_and_url_encoded(monkeypatch, app):
    """Telefonnummer wird auf Ziffern reduziert, Nachricht URL-encodiert."""
    from whatsapp import send_whatsapp_message

    calls = []

    class Resp:
        status_code = 200
        text = 'Message queued'

    def fake_get(url, timeout=10):
        calls.append(url)
        return Resp()

    monkeypatch.setattr('whatsapp.requests.get', fake_get)
    with app.app_context():
        assert send_whatsapp_message('+49 (170) 12 34-567', 'abc123', 'Hallo Welt!') is True
    assert len(calls) == 1
    assert 'phone=491701234567' in calls[0]
    assert 'Hallo+Welt%21' in calls[0] or 'Hallo%20Welt%21' in calls[0]
    assert 'apikey=abc123' in calls[0]


def test_whatsapp_http_error_logs_and_returns_false(monkeypatch, app, caplog):
    """HTTP 200 ohne 'Message queued' (z. B. Fehlertext) -> False + Warning."""
    from whatsapp import send_whatsapp_message

    class Resp:
        status_code = 200
        text = 'Error: bad key'

    monkeypatch.setattr('whatsapp.requests.get', lambda url, timeout=10: Resp())
    with app.app_context():
        assert send_whatsapp_message('+491701234', '123', 'Hallo') is False
    assert 'CallMeBot Fehler' in caplog.text


def test_whatsapp_request_exception_returns_false(monkeypatch, app, caplog):
    """RequestException (Netzfehler) -> False + Error-Log, kein Crash."""
    from whatsapp import send_whatsapp_message

    def raise_req(url, timeout=10):
        raise requests.RequestException('Netz weg (Test)')

    monkeypatch.setattr('whatsapp.requests.get', raise_req)
    with app.app_context():
        assert send_whatsapp_message('+491701234', '123', 'Hallo') is False
    assert 'CallMeBot Request-Fehler' in caplog.text


def test_whatsapp_reminder_sends_only_to_open_users(monkeypatch, app, db, user, competition, teams):
    """Reminder: nur User ohne Tipp + mit WhatsApp-Konfig, Bots raus, sleep gepatcht."""
    from whatsapp import send_whatsapp_reminder_for_match

    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=1),
              status='scheduled')
    db.session.add(m)
    db.session.commit()

    # User mit Tipp -> wird uebersprungen
    user.whatsapp_phone = '+491701111111'
    user.whatsapp_apikey = 'k1'
    db.session.add(Prediction(user_id=user.id, match_id=m.id, home_tip=1, away_tip=0))
    # Offener User -> bekommt Nachricht
    open_user = User(username='offen', email='offen@example.com')
    open_user.set_password('testpass123')
    open_user.whatsapp_phone = '+491702222222'
    open_user.whatsapp_apikey = 'k2'
    db.session.add(open_user)
    # Bot -> rausgefiltert (~@bot.local)
    bot = User(username='bot1', email='bot1@bot.local')
    bot.set_password('testpass123')
    bot.whatsapp_phone = '+491703333333'
    bot.whatsapp_apikey = 'k3'
    db.session.add(bot)
    # User ohne WhatsApp-Konfig -> nicht adressiert
    no_wa = User(username='ohnewa', email='ohnewa@example.com')
    no_wa.set_password('testpass123')
    db.session.add(no_wa)
    db.session.commit()

    class Resp:
        status_code = 200
        text = 'Message queued'

    sent_to = []

    def fake_get(url, timeout=10):
        sent_to.append(url)
        return Resp()

    monkeypatch.setattr('whatsapp.requests.get', fake_get)
    monkeypatch.setattr('whatsapp.time.sleep', lambda s: None)

    with app.app_context():
        sent, failed = send_whatsapp_reminder_for_match(m)
    assert sent == 1
    assert failed == 0
    assert len(sent_to) == 1
    assert 'phone=491702222222' in sent_to[0]


def test_whatsapp_reminder_counts_failures(monkeypatch, app, db, user, competition, teams):
    """Senden schlaegt fehl -> failed hochgezaehlt, kein Tipp gesetzt."""
    from whatsapp import send_whatsapp_reminder_for_match

    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=1),
              status='scheduled')
    db.session.add(m)
    db.session.commit()
    user.whatsapp_phone = '+491701111111'
    user.whatsapp_apikey = 'k1'
    db.session.commit()

    def raise_req(url, timeout=10):
        raise requests.RequestException('Netz weg (Test)')

    monkeypatch.setattr('whatsapp.requests.get', raise_req)
    monkeypatch.setattr('whatsapp.time.sleep', lambda s: None)

    with app.app_context():
        sent, failed = send_whatsapp_reminder_for_match(m)
    assert sent == 0
    assert failed == 1


def test_whatsapp_reminder_job_window_and_output(monkeypatch, app, db, competition, teams, capsys):
    """Scheduler-Job nimmt nur Spiele im 1h-Fenster und loggt das Ergebnis."""
    from whatsapp import whatsapp_reminder_job

    in_win = Match(competition_id=competition.id, matchday=1,
                   home_team_id=teams[0].id, away_team_id=teams[1].id,
                   kickoff=datetime.now(timezone.utc) + timedelta(minutes=30),
                   status='scheduled')
    out_win = Match(competition_id=competition.id, matchday=2,
                    home_team_id=teams[2].id, away_team_id=teams[3].id,
                    kickoff=datetime.now(timezone.utc) + timedelta(hours=5),
                    status='scheduled')
    db.session.add_all([in_win, out_win])
    db.session.commit()

    called_with = []

    def fake_reminder(match, app=None):
        called_with.append(match.id)
        return 2, 1

    monkeypatch.setattr('whatsapp.send_whatsapp_reminder_for_match', fake_reminder)
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    with app.app_context():
        whatsapp_reminder_job(app)
    assert called_with == [in_win.id]
    out = capsys.readouterr().out
    assert '2 gesendet, 1 fehlgeschlagen' in out


def test_whatsapp_test_message_without_config_returns_false(db, user):
    """Test-Nachricht ohne hinterlegte Nummer/Key -> False."""
    from whatsapp import send_whatsapp_test
    assert user.whatsapp_phone is None
    assert send_whatsapp_test(user) is False
