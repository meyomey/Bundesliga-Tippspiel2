"""Cron-Jobs fuer Shared Hosting (Netcup) - Ersatz fuer APScheduler.

Auf Shared-Hosting darfst du keine dauerhaft laufenden Prozesse starten.
Stattdessen ruft Plesk-Cron dieses Script periodisch auf:

  Plesk-Panel -> Geplante Aufgaben (Cron) -> Aufgabe hinzufuegen:
  ----------------------------------------------------------------
  Befehl:   /var/www/vhosts/<domain>/.python-venvs/<app>/bin/python
            /var/www/vhosts/<domain>/<app-pfad>/cron_jobs.py <task>
  Pfad:     <app-pfad>
  Wann:     */15 * * * *   (alle 15 Minuten)
  ----------------------------------------------------------------

Verfuegbare Tasks:
  python cron_jobs.py sync       -> Ergebnisse von API holen
  python cron_jobs.py reminder   -> Tipp-Erinnerungen ueber aktivierte Kanaele senden
  python cron_jobs.py bots       -> aktive KI-Bots fuer aktuellen Spieltag tippen lassen
  python cron_jobs.py all        -> Sync, Bot-Tipps und Reminder nacheinander
"""
import sys
import os
from datetime import datetime, timedelta, timezone

# Pfad zum App-Verzeichnis hinzufuegen (falls von cron aufgerufen)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# .env laden
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def run_sync():
    """Synchronisiert Ergebnisse von football-data.org / OpenLigaDB."""
    from app import app
    from utils import sync_results
    with app.app_context():
        result = sync_results()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] SYNC: {result['msg']}")
        return result["ok"]


def run_reminders():
    """Sendet Tipp-Erinnerungen fuer fehlende Tipps ueber die Benachrichtigungszentrale."""
    from app import app
    from notification_center import run_reminder_cycle

    with app.app_context():
        res = run_reminder_cycle()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] REMINDER: {res}")
        return True


def run_bot_tips():
    """Laesst aktive KI-Bots fuer den aktuellen Spieltag tippen, falls aktiviert."""
    from app import app
    from scoring import get_setting, _truthy_setting
    from stats import get_current_matchday
    from ai_opponent import get_ai_manager

    with app.app_context():
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if not _truthy_setting(get_setting("bot_auto_tip_active", False), default=False):
            print(f"[{ts}] BOTS: Auto-Tipp deaktiviert")
            return True
        matchday = get_current_matchday()
        manager = get_ai_manager()
        results = manager.tip_all_matches(matchday=matchday, overwrite=False)
        summary = getattr(results, "summary_by_bot", {})
        tipped = sum(v.get("tipped", 0) for v in summary.values())
        skipped = sum(v.get("skipped", 0) for v in summary.values())
        print(f"[{ts}] BOTS: Spieltag {matchday}, {tipped} Tipps, {skipped} uebersprungen")
        return True


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "all"

    if task == "sync":
        run_sync()
    elif task == "reminder":
        run_reminders()
    elif task == "bots":
        run_bot_tips()
    elif task == "all":
        run_sync()
        run_bot_tips()
        run_reminders()
    else:
        print(f"Unbekannte Task: {task}")
        print("Verwendung: python cron_jobs.py [sync|reminder|bots|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
