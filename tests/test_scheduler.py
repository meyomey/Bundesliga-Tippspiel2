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


# ============================================================
# (80) Quoten-Erinnerung: 48-h-Fenster, Dedupe, stille Ausnahmen
# ============================================================

def _naechsten_anstoss_anlegen(db, competition, teams, stunden, md=5):
    """Ein geplantes Spiel des Spieltags `md` in `stunden` Stunden."""
    kickoff = datetime.now(timezone.utc) + timedelta(hours=stunden)
    m = Match(competition_id=competition.id, matchday=md,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=kickoff, status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def test_odds_reminder_sendet_einmal_je_spieltag(app, db, competition, teams, admin_user, monkeypatch):
    """Fenster (+24 h), Key gesetzt, keine Stände → 1 Telegram-Info an den
    Admin; der zweite Lauf im selben Spieltag schweigt (Dedupe)."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    from scoring import set_setting
    set_setting("the_odds_api_key", "TESTKEY")
    _naechsten_anstoss_anlegen(db, competition, teams, 24)
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_reminder_job()
    assert len(tgram) == 1
    assert "ST 5" in tgram[0] and "Quoten online laden" in tgram[0]
    scheduler.odds_reminder_job()
    assert len(tgram) == 1                     # Dedupe: einmal je Spieltag


def test_odds_reminder_stumm_bei_vorhandenen_staenden(app, db, competition, teams, admin_user, monkeypatch):
    """Schon ein Snapshot für den Spieltag → keine Erinnerung."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    from scoring import set_setting
    from models import OddsSnapshot
    set_setting("the_odds_api_key", "TESTKEY")
    m = _naechsten_anstoss_anlegen(db, competition, teams, 24)
    db.session.add(OddsSnapshot(competition_id=competition.id, match_id=m.id,
                                matchday=5, o1=2.0, ox=3.4, o2=3.8))
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_reminder_job()
    assert tgram == []


def test_odds_reminder_stumm_ohne_key_oder_deaktiviert(app, db, competition, teams, admin_user, monkeypatch):
    """Ohne The-Odds-API-Key und bei odds_reminder_enabled=false: still
    (fehlender optionaler Key ist ℹ️, nie ⚠️ — Dauerregel 2)."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _naechsten_anstoss_anlegen(db, competition, teams, 24)
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_reminder_job()              # kein Key gesetzt
    assert tgram == []
    from scoring import set_setting
    set_setting("the_odds_api_key", "TESTKEY")
    set_setting("odds_reminder_enabled", False)
    scheduler.odds_reminder_job()              # explizit deaktiviert
    assert tgram == []


def test_odds_reminder_stumm_ausserhalb_des_fensters(app, db, competition, teams, admin_user, monkeypatch):
    """Erster Anstoß erst in 72 h (außerhalb 48-h-Fenster) → keine Erinnerung."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    from scoring import set_setting
    set_setting("the_odds_api_key", "TESTKEY")
    _naechsten_anstoss_anlegen(db, competition, teams, 72)
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_reminder_job()
    assert tgram == []


def test_odds_cron_task_ruft_scheduler_job(app, monkeypatch):
    """Der wget-Cron-Task 'odds' (cron_jobs.run_odds_reminder) ruft den
    Scheduler-Job im App-Kontext auf."""
    monkeypatch.setattr(scheduler, "app", app)
    calls = []
    monkeypatch.setattr(scheduler, "odds_reminder_job",
                        lambda: calls.append(1))
    from cron_jobs import run_odds_reminder
    assert run_odds_reminder() is True
    assert calls == [1]


# ============================================================
# (81) „Quoten sind da“ — positive Gegmeldung zur Erinnerung
# ============================================================

def test_odds_arrival_sendet_einmal_je_spieltag(app, db, competition, teams, admin_user, monkeypatch):
    """Stände vorhanden → genau eine positive Telegram-Info („Quoten sind
    da“); der zweite Lauf schweigt (Dedupe je Spieltag)."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    from models import OddsSnapshot
    m = _naechsten_anstoss_anlegen(db, competition, teams, 72)
    db.session.add(OddsSnapshot(competition_id=competition.id, match_id=m.id,
                                matchday=5, o1=2.0, ox=3.4, o2=3.8))
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_arrival_job()
    assert len(tgram) == 1
    assert "Quoten sind da" in tgram[0] and "ST 5" in tgram[0]
    scheduler.odds_arrival_job()
    assert len(tgram) == 1                    # Dedupe: einmal je Spieltag


def test_odds_arrival_stumm_ohne_staenden(app, db, competition, teams, admin_user, monkeypatch):
    """Kein Snapshot für den nächsten Spieltag → keine Meldung (dafür
    zuständig ist die 48-h-Erinnerung)."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _naechsten_anstoss_anlegen(db, competition, teams, 72)
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_arrival_job()
    assert tgram == []


def test_odds_arrival_deaktiviert_bleibt_still(app, db, competition, teams, admin_user, monkeypatch):
    """odds_reminder_enabled=false schaltet beide Richtungen still (ein
    gemeinsamer Schalter für Erinnerung und „sind da“)."""
    monkeypatch.setattr(scheduler, "app", app)
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    from scoring import set_setting
    from models import OddsSnapshot
    m = _naechsten_anstoss_anlegen(db, competition, teams, 72)
    db.session.add(OddsSnapshot(competition_id=competition.id, match_id=m.id,
                                matchday=5, o1=2.0, ox=3.4, o2=3.8))
    set_setting("odds_reminder_enabled", False)
    admin_user.phone = "tg:TESTCHAT"
    db.session.commit()
    tgram = []
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda user, msg: tgram.append(msg))
    scheduler.odds_arrival_job()
    assert tgram == []
