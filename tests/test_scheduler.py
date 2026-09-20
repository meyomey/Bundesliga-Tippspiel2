"""Tests für die Scheduler-Jobs (Reminder, Sync, Saison-Archiv).

Die Jobs laufen in Produktion im Takt (10/15/60 min) und hatten bislang
0 % Coverage — ein stiller Fehler wäre sonst unbemerkt geblieben.
"""
from datetime import datetime, timedelta, timezone

import pytest

import scheduler
from models import Match, SeasonArchive, User


def test_reminder_job_huht_wenn_deaktiviert(app, monkeypatch):
    """reminders_enabled=false → der Reminder-Zyklus wird nicht angestoßen."""
    monkeypatch.setattr(scheduler, "app", app)
    calls = []
    monkeypatch.setattr("scoring.get_setting", lambda key, default=None: "false")
    monkeypatch.setattr("notification_center.run_reminder_cycle", lambda: calls.append(1))
    scheduler.reminder_job()
    assert calls == []


def test_reminder_job_lauft_wenn_aktiv(app, monkeypatch):
    """Aktiv → run_reminder_cycle wird ausgeführt und meldet die Nutzer."""
    monkeypatch.setattr(scheduler, "app", app)
    calls = []

    def cycle():
        calls.append(1)
        return {"users": ["a@b.c"], "sent": 1}

    monkeypatch.setattr("scoring.get_setting", lambda key, default=None: True)
    monkeypatch.setattr("notification_center.run_reminder_cycle", cycle)
    scheduler.reminder_job()
    assert calls == [1]


def test_reminder_job_ignoriert_settingsfehler(app, monkeypatch):
    """Ein kaputtes Setting darf den Reminder-Lauf nicht sprengen."""
    monkeypatch.setattr(scheduler, "app", app)
    calls = []

    def broken(key, default=None):
        raise RuntimeError("Settings kaputt")

    monkeypatch.setattr("scoring.get_setting", broken)
    monkeypatch.setattr("notification_center.run_reminder_cycle",
                        lambda: (calls.append(1), {"users": []})[1])
    scheduler.reminder_job()
    assert calls == [1]


def test_sync_job_ruft_sync_results_an(app, monkeypatch):
    """Der 15-Minuten-Sync ruft sync_results auf und liest dessen Meldung."""
    monkeypatch.setattr(scheduler, "app", app)
    calls = []
    monkeypatch.setattr(scheduler, "sync_results",
                        lambda: calls.append(1) or {"msg": "keine neuen Ergebnisse"})
    scheduler.sync_job()
    assert calls == [1]


def _finished_match(teams, competition, matchday):
    m = Match(
        competition_id=competition.id, matchday=matchday,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status="finished", home_score=1, away_score=0)
    return m


def test_season_archive_job_huht_wenn_deaktiviert(app, db, competition, teams, monkeypatch):
    """auto_archive_season=false → nichts passiert, auch nach letztem Spieltag."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    db.session.add(_finished_match(teams, competition, 34))
    db.session.commit()
    calls = []
    monkeypatch.setattr("scoring.get_setting",
                        lambda key, default=None: {"auto_archive_season": False}.get(key, default))
    monkeypatch.setattr("stats.archive_season", lambda season: calls.append(season))
    scheduler.season_archive_job()
    assert calls == []


def test_season_archive_job_ignoriert_unbeendete_saison(app, db, competition, teams, monkeypatch):
    """Noch kein letzter Spieltag finished → kein Archiv."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    db.session.add(_finished_match(teams, competition, 12))
    db.session.commit()
    calls = []
    monkeypatch.setattr("scoring.get_setting",
                        lambda key, default=None: {"auto_archive_season": True}.get(key, default))
    monkeypatch.setattr("stats.archive_season", lambda season: calls.append(season))
    scheduler.season_archive_job()
    assert calls == []


def test_season_archive_job_ignoriert_bereits_archivierte_saison(app, db, competition, teams, admin_user, monkeypatch):
    """Vorhandene SeasonArchive-Zeile → kein doppeltes Archivieren."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    db.session.add(_finished_match(teams, competition, 34))
    admin = admin_user
    db.session.add(SeasonArchive(competition_id=competition.id, user_id=admin.id,
                                 season="2025/26", rank=1, points=99))
    db.session.commit()
    calls = []
    monkeypatch.setattr("scoring.get_setting",
                        lambda key, default=None: {"auto_archive_season": True}.get(key, default))
    monkeypatch.setattr("stats.archive_season", lambda season: calls.append(season))
    scheduler.season_archive_job()
    assert calls == []


def test_season_archive_job_archiviert_nach_letztem_spieltag(app, db, competition, teams, admin_user, monkeypatch):
    """34. Spieltag finished + alle Bedingungen → archivieren, Flag setzen,
    Admins mit Telegram-Id informieren (Fehler bleiben still)."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    db.session.add(_finished_match(teams, competition, 34))
    admin_user.phone = "tg:12345"
    db.session.commit()
    calls = []
    tgram = []
    monkeypatch.setattr("scoring.get_setting",
                        lambda key, default=None: {"auto_archive_season": True}.get(key, default))
    monkeypatch.setattr("stats.archive_season", lambda season: calls.append(season))
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append((user.id, msg)))
    scheduler.season_archive_job()
    assert calls == ["2025/26"]
    assert len(tgram) == 1 and "2025/26" in tgram[0][1]
    # Flag in der DB (get_setting ist hier gemonkt – direkt prüfen):
    from models import Setting
    s = Setting.query.get("season_archived")
    assert s is not None and s.value == "true"
