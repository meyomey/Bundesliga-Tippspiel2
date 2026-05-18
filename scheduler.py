"""APScheduler: Automatische E-Mail-Reminder + API-Sync.

Starte zusammen mit: `python scheduler.py` (parallel zur App)
oder via Worker-Service in Production.
"""
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler

from app import app
from extensions import db
from models import Match, User, Prediction
from utils import send_kickoff_reminder, sync_results


def reminder_job():
    """Erinnert User 1h vor Anpfiff, wenn sie noch nicht getippt haben."""
    with app.app_context():
        now = datetime.now(timezone.utc)
        upcoming = Match.query.filter(
            Match.kickoff > now,
            Match.kickoff <= now + timedelta(hours=1, minutes=5),
            Match.status == "scheduled",
        ).all()

        if not upcoming:
            return

        reminders_enabled = False
        try:
            from scoring import get_setting
            reminders_on = get_setting("reminders_enabled", True)
            if isinstance(reminders_on, bool):
                reminders_enabled = reminders_on
            else:
                reminders_enabled = str(reminders_on).lower() not in ("0", "false", "no")
        except Exception:
            reminders_enabled = True

        if not reminders_enabled:
            return

        for match in upcoming:
            for user in User.query.all():
                pred = Prediction.query.filter_by(
                    user_id=user.id, match_id=match.id
                ).first()
                if not pred:
                    # E-Mail-Reminder
                    send_kickoff_reminder(user, match)
                    print(f"Reminder per E-Mail an {user.email} fuer {match.id}")

                    # Telegram-Reminder (falls verknuepft)
                    if user.phone and user.phone.startswith("tg:"):
                        try:
                            from telegram_bot import notify_user_telegram
                            match_info = f"{match.home_team.short_name} vs {match.away_team.short_name}"
                            ko = match.kickoff.strftime("%d.%m. %H:%M") if match.kickoff else "?"
                            msg = f"Anpfiff in 1h: {match_info} um {ko}"
                            notify_user_telegram(user, msg)
                            print(f"Reminder per Telegram an {user.username}")
                        except Exception:
                            pass


def sync_job():
    """Synct Ergebnisse alle 15 Minuten."""
    with app.app_context():
        res = sync_results()
        print(f"[{datetime.now(timezone.utc)}] Sync: {res['msg']}")


def season_archive_job():
    """Prueft ob die aktuelle Saison beendet ist und archiviert sie automatisch."""
    with app.app_context():
        try:
            from scoring import get_setting, set_setting
            from stats import archive_season

            # Nur ausfuehren, wenn Auto-Archiv aktiviert ist
            auto_archive = get_setting("auto_archive_season", True)
            if not auto_archive:
                return

            # Pruefen ob bereits archiviert
            from models import SeasonArchive
            current_season = get_setting("current_season", "2025/26")
            already_archived = SeasonArchive.query.filter_by(season=current_season).first()
            if already_archived:
                return

            # Alle Spieltage durch? (34. Spieltag finished)
            from models import Match
            max_md = Match.query.filter_by(status="finished").order_by(Match.matchday.desc()).first()
            if not max_md:
                return

            # Wenn der letzte Spieltag (34) erreicht ist und alle Spiele finished -> archivieren
            total_matchdays = get_setting("total_matchdays", 34)
            if max_md.matchday >= total_matchdays:
                archive_season(current_season)
                set_setting("season_archived", True)
                print(f"[{datetime.now(timezone.utc)}] Saison {current_season} automatisch archiviert!")

                # Admin benachrichtigen
                from models import User
                admins = User.query.filter_by(is_admin=True).all()
                for admin in admins:
                    if admin.phone and admin.phone.startswith("tg:"):
                        try:
                            from telegram_bot import notify_user_telegram
                            notify_user_telegram(admin, f"Saison {current_season} wurde automatisch archiviert!")
                        except Exception:
                            pass
        except Exception as e:
            print(f"[{datetime.now(timezone.utc)}] Archive-Job Fehler: {e}")


if __name__ == "__main__":
    sched = BlockingScheduler()
    sched.add_job(reminder_job, "interval", minutes=10, id="reminders")
    sched.add_job(sync_job, "interval", minutes=15, id="sync")
    sched.add_job(season_archive_job, "interval", hours=6, id="season_archive")
    print("⏰ Scheduler gestartet (Reminder: alle 10min, Sync: alle 15min, Archive: alle 6h)")
    sched.start()
