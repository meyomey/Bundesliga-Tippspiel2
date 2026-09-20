"""APScheduler: Automatische E-Mail-Reminder + API-Sync.

Starte zusammen mit: `python scheduler.py` (parallel zur App)
oder via Worker-Service in Production.
"""
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler

from app import app
from extensions import db
from models import Match, User, Prediction
from competition_helpers import filter_matches_for_active_competition
from utils import send_kickoff_reminder, sync_results


def reminder_job():
    """Zentraler Reminder-Lauf fuer E-Mail/Push/Telegram/WhatsApp."""
    with app.app_context():
        try:
            from scoring import get_setting
            reminders_on = get_setting("reminders_enabled", True)
            if str(reminders_on).lower() in ("0", "false", "no", "nein", "off"):
                return
        except Exception:
            pass
        from notification_center import run_reminder_cycle
        res = run_reminder_cycle()
        if res.get("users"):
            print(f"[{datetime.now(timezone.utc)}] Reminder: {res}")


def sync_job():
    """Synct Ergebnisse alle 15 Minuten."""
    with app.app_context():
        res = sync_results()
        print(f"[{datetime.now(timezone.utc)}] Sync: {res['msg']}")


ODDS_REMINDER_WINDOW_H = 48  # Erinnerungs-Fenster vor dem ersten Anstoß


def odds_reminder_job():
    """Quoten-Erinnerung an die Admins ((80)): liegt der erste Anstoß des
    nächsten Spieltags im 48-h-Fenster UND gibt es für diesen Spieltag noch
    KEINE Quoten-Stände (odds_snapshots), bekommt jeder Admin mit Telegram-
    Verknüpfung eine Info — einmal je Spieltag (Dedupe über Setting). Ohne
    The-Odds-API-Key bewusst still (fehlender optionaler Key = ℹ️, nie ⚠️,
    Dauerregel 2). Die Odds-API listet nur zukünftige Spiele — zu spät laden
    heißt leer ausgehen ((77)), genau das verhindert dieser Lauf."""
    with app.app_context():
        try:
            from datetime import timezone as _tz
            from scoring import get_setting, set_setting
            from models import OddsSnapshot
            from admin_tip_optimizer_routes import SETTINGS_KEY
            from competition_helpers import get_active_competition

            enabled = get_setting("odds_reminder_enabled", True)
            if str(enabled).lower() in ("0", "false", "no", "nein", "off"):
                return
            if not (get_setting(SETTINGS_KEY, "") or "").strip():
                return  # ohne Key kann ohnehin nicht geladen werden — still

            comp = get_active_competition()
            now = datetime.now(timezone.utc)
            next_q = Match.query.filter(Match.status == "scheduled",
                                        Match.kickoff.isnot(None))
            next_q = filter_matches_for_active_competition(next_q)
            nxt = next_q.order_by(Match.kickoff.asc()).first()
            if nxt is None:
                return
            kickoff = nxt.kickoff
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=_tz.utc)
            delta_h = (kickoff - now).total_seconds() / 3600.0
            if delta_h <= 0 or delta_h > ODDS_REMINDER_WINDOW_H:
                return

            snap_q = OddsSnapshot.query.filter_by(competition_id=comp.id,
                                                  matchday=nxt.matchday)
            if db.session.query(snap_q.exists()).scalar():
                return

            sent = get_setting("odds_reminder_sent", None)
            if isinstance(sent, dict) and sent.get("md") == nxt.matchday \
                    and sent.get("comp") == comp.id:
                return
            set_setting("odds_reminder_sent",
                        {"md": nxt.matchday, "comp": comp.id,
                         "at": now.isoformat()})

            msg = (f"⏰ Quoten-Erinnerung: ST {nxt.matchday} startet "
                   f"{kickoff.strftime('%a, %d.%m. %H:%M')} UTC (in ~{int(delta_h)} h) — "
                   f"noch keine Quoten-Stände gespeichert. "
                   f"Admin → Tipp-Optimizer → „⬇ Quoten online laden“.")
            admins = User.query.filter_by(is_admin=True).all()
            n_sent = 0
            for admin in admins:
                if admin.phone and admin.phone.startswith("tg:"):
                    try:
                        from telegram_bot import notify_user_telegram
                        notify_user_telegram(admin, msg)
                        n_sent += 1
                    except Exception:
                        pass
            print(f"[{now}] ODDS-REMINDER: ST {nxt.matchday}, "
                  f"{n_sent} Admin-Info(s) gesendet")
        except Exception as e:
            print(f"[{datetime.now(timezone.utc)}] Odds-Reminder-Job Fehler: {e}")


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
            from competition_helpers import get_active_competition
            current_season = get_setting("current_season", "2025/26")
            comp = get_active_competition()
            archived_q = SeasonArchive.query.filter_by(season=current_season)
            if comp:
                archived_q = archived_q.filter(SeasonArchive.competition_id == comp.id)
            already_archived = archived_q.first()
            if already_archived:
                return

            # Alle Spieltage durch? (34. Spieltag finished)
            from models import Match
            max_md_q = Match.query.filter_by(status="finished")
            max_md_q = filter_matches_for_active_competition(max_md_q)
            max_md = max_md_q.order_by(Match.matchday.desc()).first()
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
    sched.add_job(odds_reminder_job, "interval", hours=1, id="odds_reminder")
    sched.add_job(season_archive_job, "interval", hours=6, id="season_archive")
    print("⏰ Scheduler gestartet (Reminder: alle 10min, Sync: alle 15min, "
          "Quoten-Erinnerung: alle 60min, Archive: alle 6h)")
    sched.start()
