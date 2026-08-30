"""Tests fuer die Benachrichtigungszentrale."""
from datetime import datetime, timedelta, timezone

from models import Match, NotificationLog, Prediction
from notification_center import send_user_notification, user_wants_match_reminder


def test_user_with_existing_tip_gets_no_reminder(db, user, match):
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=1, away_tip=1))
    db.session.commit()
    assert user_wants_match_reminder(user, match) is False


def test_notify_only_favorite_filters_matches(db, user, competition, teams):
    user.notify_only_favorite = True
    user.favorite_team_id = teams[2].id
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=1), status='scheduled'
    )
    db.session.add(match)
    db.session.commit()
    assert user_wants_match_reminder(user, match) is False


def test_notification_log_prevents_duplicate_email(app, db, user, match, monkeypatch):
    sent = []

    def fake_send_email(subject, recipients, body, html=None):
        sent.append((subject, recipients, body))
        return True

    monkeypatch.setattr('mail_helpers.send_email', fake_send_email)
    with app.app_context():
        res1 = send_user_notification(user, match, channels=['email'])
        res2 = send_user_notification(user, match, channels=['email'])
        assert res1['email'] is True
        assert res2['email'] is False
        assert len(sent) == 1
        assert NotificationLog.query.filter_by(user_id=user.id, match_id=match.id, channel='email').count() == 1


def test_disabled_channel_is_not_sent(app, db, user, match, monkeypatch):
    user.notify_email = False
    db.session.commit()
    called = []

    def fake_send_email(*args, **kwargs):
        called.append(True)
        return True

    monkeypatch.setattr('mail_helpers.send_email', fake_send_email)
    with app.app_context():
        res = send_user_notification(user, match, channels=['email'])
        assert res['email'] is False
        assert called == []


def test_run_reminder_cycle_respects_global_setting(app, db, user, match, monkeypatch):
    from scoring import set_setting
    from notification_center import run_reminder_cycle

    called = []
    monkeypatch.setattr('notification_center.send_match_reminders', lambda *a, **kw: called.append(True) or {})
    with app.app_context():
        set_setting('reminders_enabled', False)
        res = run_reminder_cycle(channels=['email'])
        assert res['enabled'] is False
        assert called == []


def test_test_missing_tip_notification_sends_without_log(app, db, user, match, monkeypatch):
    from notification_center import send_test_missing_tip_notification

    sent = []
    def fake_send_email(subject, recipients, body, html=None):
        sent.append((subject, recipients, body))
        return True

    monkeypatch.setattr('mail_helpers.send_email', fake_send_email)
    with app.app_context():
        user.notify_email = True
        user.notify_push = False
        user.notify_telegram = False
        user.notify_whatsapp = False
        db.session.commit()
        res = send_test_missing_tip_notification(user, channels=['email'])
        assert res['email'] is True
        assert len(sent) == 1
        assert 'Test' in sent[0][0]
        assert NotificationLog.query.filter_by(user_id=user.id, match_id=match.id, channel='email').count() == 0
