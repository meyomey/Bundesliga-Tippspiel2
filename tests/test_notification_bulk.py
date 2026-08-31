"""Notification Center bulk-optmiert: kein N+1 bei Tipps, Versand-Logs,
Basis-URL und User-Ladung. Zusaetzlich Verhaltenstests fuer den Bulk-Pfad."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from extensions import db as _db
from models import Match, NotificationLog, Prediction, User
import notification_center
from notification_center import (
    _next_open_match_for_user, send_match_reminders, upcoming_reminder_matches,
)


def _mk_user(db, i):
    u = User(username=f"bulkuser{i}", email=f"bulk{i}@example.com",
             notify_enabled=True, notify_email=True)
    u.set_password("x")
    db.session.add(u)
    return u


def _mk_match(db, competition, teams, hours_ahead=2, matchday=1, past=False):
    m = Match(
        competition_id=competition.id, matchday=matchday,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + (timedelta(hours=-hours_ahead) if past else timedelta(hours=hours_ahead)),
        status='scheduled'
    )
    db.session.add(m)
    db.session.commit()
    return m


class _QueryCounter:
    """Zaehlt SELECTs pro Tabelle via SQLAlchemy-Event."""

    def __init__(self):
        self.selects = []

    def attach(self, engine):
        @event.listens_for(engine, "before_cursor_execute")
        def _before(conn, cursor, statement, parameters, context, executemany):
            stmt = statement.upper()
            if stmt.startswith("SELECT"):
                self.selects.append(stmt)


def _count_selects_from(counter, table):
    return sum(1 for s in counter.selects if f" FROM {table}" in s or f"FROM {table}" in s.replace("\n", " "))


def test_send_match_reminders_no_n_plus_1_on_lookups(app, db, user, competition, teams, monkeypatch):
    """Kern des Bulk-Refactors: Lookup-Queries (Tipps vorhanden? schon gesendet?)
    duerfen NICHT pro User feuern — unabhaengig von der User-Anzahl."""
    mails = []
    monkeypatch.setattr('mail_helpers.send_email',
                        lambda s, r, b, html=None: mails.append(r) or True)

    for i in range(10):
        _mk_user(db, i)
    db.session.commit()
    match = _mk_match(db, competition, teams)
    total_users = User.query.filter(~User.email.like("%@bot.local")).count()
    assert total_users >= 11

    counter = _QueryCounter()
    with app.app_context():
        counter.attach(_db.engine)
        res = send_match_reminders(match, channels=['email'])
        db.session.commit()

    assert res["email"] == total_users  # alle wollen den Reminder
    assert len(mails) == total_users
    # Statt einmal Tipp-Query + eine Log-Query PRO User: exakt je 1 Bulk-Prefetch
    assert _count_selects_from(counter, "predictions") <= 1, \
        f"N+1 auf predictions: {_count_selects_from(counter, 'predictions')} Selects"
    assert _count_selects_from(counter, "notification_log") <= 1, \
        f"N+1 auf notification_log: {_count_selects_from(counter, 'notification_log')} Selects"

    # Zweiter Lauf: alle schon im Log -> kein erneuter Versand, weiterhin wenig Queries
    mails.clear()
    counter.selects.clear()
    with app.app_context():
        res2 = send_match_reminders(match, channels=['email'])
    assert res2["email"] == 0 and mails == []
    assert _count_selects_from(counter, "predictions") <= 1


def test_send_match_reminders_bulk_respects_user_rules(app, db, user, competition, teams, monkeypatch):
    """Bulk-Pfad verhaelt sich wie der alte Einzelpfad: getippte stille, deaktivierte
    Kanale/Reminder stumm, Bots raus."""
    mails = []
    monkeypatch.setattr('mail_helpers.send_email',
                        lambda s, r, b, html=None: mails.append(r[0]) or True)
    match = _mk_match(db, competition, teams)

    u_tip = _mk_user(db, 1)          # hat schon getippt -> kein Reminder
    u_off = _mk_user(db, 2)          # Reminder komplett aus
    u_ok = _mk_user(db, 3)           # bekommt Reminder
    db.session.commit()
    db.session.add(Prediction(user_id=u_tip.id, match_id=match.id, home_tip=1, away_tip=1))
    u_off.notify_enabled = False
    db.session.commit()

    with app.app_context():
        res = send_match_reminders(match, channels=['email'])
        db.session.commit()

    # 2 = fixture-user + u_ok (u_tip getippt, u_off deaktiviert)
    assert res["email"] == 2
    assert u_tip.email not in mails and u_off.email not in mails
    assert user.email in mails and u_ok.email in mails
    assert NotificationLog.query.filter_by(match_id=match.id, channel='email').count() == 2


def test_upcoming_reminder_matches_loads_users_once(app, db, competition, teams):
    """Frueher wurden ALLE User einmal PRO SPIEL geladen (N+1)."""
    for i in range(8):
        _mk_user(db, i)
    db.session.commit()
    for md in range(1, 7):
        _mk_match(db, competition, teams, hours_ahead=1, matchday=md)

    counter = _QueryCounter()
    with app.app_context():
        counter.attach(_db.engine)
        hits = upcoming_reminder_matches()

    assert len(hits) == 6
    user_selects = _count_selects_from(counter, "users")
    assert user_selects <= 1, f"User-Tabelle {user_selects}x geladen statt 1x"


def test_upcoming_reminder_matches_respects_user_windows(app, db, competition, teams, monkeypatch):
    """Individuelles Stundenfenster (notify_hours_before) bleibt erhalten."""
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)  # Scope auf Test-Liga
    u_far = _mk_user(db, 1)
    u_far.notify_hours_before = 24
    u_near = _mk_user(db, 2)
    u_near.notify_hours_before = 1
    db.session.commit()
    m_in_far_window = _mk_match(db, competition, teams, hours_ahead=12, matchday=1)
    with app.app_context():
        hits = upcoming_reminder_matches()
    assert any(h.id == m_in_far_window.id for h in hits)  # Fenster von u_far (24h) deckt das Spiel ab

    # Nur 1h-Fenster zwischen Spiel und jetzt -> nicht enthalten
    db.session.delete(m_in_far_window)
    u_far.notify_hours_before = 0  # deaktiviert weites Fenster
    db.session.commit()
    m_close = _mk_match(db, competition, teams, hours_ahead=12, matchday=2)
    with app.app_context():
        hits2 = upcoming_reminder_matches()
    assert all(h.id != m_close.id for h in hits2)


def test_next_open_match_for_user_prefetches_tips(app, db, user, competition, teams):
    m1 = _mk_match(db, competition, teams, hours_ahead=2, matchday=1)
    m2 = _mk_match(db, competition, teams, hours_ahead=26, matchday=2)
    db.session.add(Prediction(user_id=user.id, match_id=m1.id, home_tip=1, away_tip=0))
    db.session.commit()

    counter = _QueryCounter()
    with app.app_context():
        counter.attach(_db.engine)
        nxt = _next_open_match_for_user(user)
    assert nxt.id == m2.id
    assert _count_selects_from(counter, "predictions") <= 1
