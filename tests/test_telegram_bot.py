"""Tests fuer Telegram Bot Kommandos."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction, User
from telegram_bot import generate_telegram_token, process_message


def test_telegram_start_links_user(app, db, user):
    with app.app_context():
        token = generate_telegram_token(user.id)
        reply = process_message('12345', f'/start {token}')
        linked = db.session.get(User, user.id)
        assert 'verknuepft' in reply or 'verknüpft' in reply
        assert linked.phone == 'tg:12345'


def test_telegram_tip_with_joker(app, db, user, competition, teams):
    with app.app_context():
        user.phone = 'tg:12345'
        match = Match(
            competition_id=competition.id, matchday=1,
            home_team_id=teams[0].id, away_team_id=teams[1].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
        )
        db.session.add(match)
        db.session.commit()

        reply = process_message('12345', '/tipp FCB-BVB 2:1 joker')
        pred = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
        assert 'gespeichert' in reply
        assert pred is not None
        assert pred.home_tip == 2 and pred.away_tip == 1
        assert pred.joker is True


def test_telegram_open_requires_link(app, db):
    with app.app_context():
        reply = process_message('999', '/offen')
        assert 'nicht verknuepft' in reply or 'nicht verknüpft' in reply


def test_telegram_stats_for_linked_user(app, db, user):
    with app.app_context():
        linked = db.session.get(User, user.id)
        linked.phone = 'tg:12345'
        db.session.commit()
        reply = process_message('12345', '/stats')
        assert 'Statistik' in reply
        assert 'Punkte' in reply
