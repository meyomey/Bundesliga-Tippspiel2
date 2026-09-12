"""Zwei Reminder-Wellen + einstellbare Vorlaeufe (12.09.2026, Nutzerwuensche:
'beides, aber einstellbar').

Abgedeckt:
- Welle 1 respektiert Profil-Vorlauf bzw. globalen Force-Standard
- Welle 2 (Vorwarnung) nutzt eigenes Versand-Log -> blockiert Welle 1 nicht
- Dedup: pro Welle/Kanal/Spiel genau ein Versand
- Zyklus-Reporting (wave1/wave2-Zaehler) und Master-Schalter aus
"""
from datetime import datetime, timedelta, timezone

import pytest

from models import Match, NotificationLog, User
import notification_center
from notification_center import reminder_lead_hours, run_reminder_cycle


def _mk_user(db, i, hours=None):
    u = User(username=f"waveuser{i}", email=f"wave{i}@example.com",
             notify_enabled=True, notify_email=True)
    if hours is not None:
        u.notify_hours_before = hours
    u.set_password("x")
    db.session.add(u)
    return u


def _mk_match(db, competition, teams, hours_ahead, matchday):
    m = Match(competition_id=competition.id, matchday=matchday,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=hours_ahead),
              status='scheduled')
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture
def wave_env(app, db, monkeypatch):
    mails = []
    monkeypatch.setattr('mail_helpers.send_email',
                        lambda s, r, b, html=None: mails.append((s, r)) or True)
    from scoring import set_setting
    set_setting("reminders_force_lead_hours", False)
    set_setting("reminders_second_wave_enabled", True)
    set_setting("reminders_second_lead_hours", 36)
    return mails


def test_lead_hours_resolution(app, db, wave_env):
    from scoring import set_setting
    u = _mk_user(db, 1, hours=3)
    db.session.commit()
    with app.app_context():
        # ohne Force: Profilwert gewinnt
        set_setting("reminders_force_lead_hours", False)
        set_setting("reminders_lead_hours", 1)
        assert reminder_lead_hours(u, wave=1) == 3
        # Force an: globaler Standard gilt fuer alle
        set_setting("reminders_force_lead_hours", True)
        set_setting("reminders_lead_hours", 6)
        assert reminder_lead_hours(u, wave=1) == 6
        # Welle 2: immer global, clamp 1..168
        set_setting("reminders_second_lead_hours", 30)
        assert reminder_lead_hours(u, wave=2) == 30
        set_setting("reminders_second_lead_hours", 400)
        assert reminder_lead_hours(u, wave=2) == 168


def test_second_wave_earlier_and_first_wave_later(app, db, competition, teams, wave_env):
    """Spiel in 30h bekommt nur die Vorwarnung; Spiel in 30min beide Wellen.
    Dedup pro Welle: zweiter Zyklus sendet nichts mehr, Log getrennt (kind)."""
    mails = wave_env
    _mk_user(db, 1, hours=1)
    db.session.commit()
    m_far = _mk_match(db, competition, teams, hours_ahead=30, matchday=7)
    m_near = _mk_match(db, competition, teams, hours_ahead=0.5, matchday=8)
    now = datetime.now(timezone.utc)
    with app.app_context():
        total = run_reminder_cycle(channels=["email"], now=now)
        assert total["wave2"] >= 1 and total["wave1"] >= 1
        w1_far = NotificationLog.query.filter_by(match_id=m_far.id, kind="match_reminder").count()
        w2_far = NotificationLog.query.filter_by(match_id=m_far.id, kind="match_reminder_w2").count()
        w1_near = NotificationLog.query.filter_by(match_id=m_near.id, kind="match_reminder").count()
        w2_near = NotificationLog.query.filter_by(match_id=m_near.id, kind="match_reminder_w2").count()
        assert (w1_far, w2_far) == (0, 1)          # 30h: nur Vorwarnwelle
        assert (w1_near, w2_near) == (1, 1)        # 30min: beide Wellen
        assert any("dbg" in r[0] or "wave" in r[0] for _s, r in mails)

        n_before = len(mails)
        total2 = run_reminder_cycle(channels=["email"], now=now)
        assert total2["users"] == 0 and len(mails) == n_before  # Dedup


def test_second_wave_disabled_no_w2_log(app, db, competition, teams, wave_env):
    from scoring import set_setting
    u = _mk_user(db, 1, hours=1)
    db.session.commit()
    m = _mk_match(db, competition, teams, hours_ahead=12, matchday=8)
    now = datetime.now(timezone.utc)
    with app.app_context():
        set_setting("reminders_second_wave_enabled", False)
        total = run_reminder_cycle(channels=["email"], now=now)
        assert total["wave2"] == 0 and total["wave1"] == 0
        assert NotificationLog.query.filter_by(kind="match_reminder_w2").count() == 0
        # Manueller Admin-Versand (enforce_window=False) bleibt vom Fenster verschont
        res = notification_center.send_user_notification(u, m, channels=["email"])
        assert res["email"] is True


def test_master_switch_off_blocks_everything(app, db, competition, teams, wave_env):
    from scoring import set_setting
    _mk_user(db, 1, hours=24)
    db.session.commit()
    _mk_match(db, competition, teams, hours_ahead=2, matchday=9)
    now = datetime.now(timezone.utc)
    with app.app_context():
        set_setting("reminders_enabled", False)
        total = run_reminder_cycle(channels=["email"], now=now)
        assert total["enabled"] is False and total["users"] == 0
        set_setting("reminders_enabled", True)
