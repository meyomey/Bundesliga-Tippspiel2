"""Cron-Jobs fuer Shared Hosting (Netcup) - Ersatz fuer APScheduler.

Auf Shared-Hosting darfst du keine dauerhaft laufenden Prozesse starten.
Stattdessen ruft Plesk-Cron dieses Script periodisch auf.

  Plesk-Panel -> Websites & Domains -> <Domain> -> Geplante Aufgaben
  ----------------------------------------------------------------
  Aufgabe 1 (alle 15 Minuten):
    Befehl:   /var/www/vhosts/<domain>/.python-venvs/<app>/bin/python
              /var/www/vhosts/<domain>/<app-pfad>/cron_jobs.py all
    Wann:     */15 * * * *

  Aufgabe 2 (einmal taeglich, z. B. 03:15 Uhr - DB-Backup):
    Befehl:   ... (gleicher Python-Pfad) ... cron_jobs.py backup
    Wann:     15 3 * * *
  ----------------------------------------------------------------

Verfuegbare Tasks:
  python cron_jobs.py sync       -> Ergebnisse von API holen
  python cron_jobs.py reminder   -> Tipp-Erinnerungen ueber aktivierte Kanaele senden
  python cron_jobs.py bots       -> aktive KI-Bots fuer aktuellen Spieltag tippen lassen
  python cron_jobs.py all        -> Sync, Bot-Tipps und Reminder nacheinander
  python cron_jobs.py backup     -> SQLite-Backup nach backups/ (Rotation, 14 Stueck)
  python cron_jobs.py status     -> Heartbeat-Status aller Aufgaben ausgeben

Jeder Lauf schreibt einen Heartbeat (cron_last_run:<task> in der Settings-
Tabelle). Das Admin-Wartungscenter zeigt Alter und Status der letzten Laeufe.
"""
import sys
import os
from datetime import datetime, timezone

# Pfad zum App-Verzeichnis hinzufuegen (falls von cron aufgerufen)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# .env laden
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _bootstrap_dependencies():
    """Bindet vendor/ und die Plesk-venv ein (wie passenger_wsgi.py).

    Der Plesk-Cron ruft dieses Skript OHNE Passenger auf - je nach Setup
    liegen die Pakete im vendor/-Ordner oder in der Plesk-venv. Ohne
    Bootstrap wuerde `import flask` fehlschlagen.
    """
    import importlib.util

    app_dir = os.path.dirname(os.path.abspath(__file__))

    def _flask_ok():
        try:
            return importlib.util.find_spec("flask") is not None
        except Exception:
            return False

    if _flask_ok():
        return

    # 1. vendor/ (falls vorhanden)
    vendor_dir = os.path.join(app_dir, "vendor")
    if os.path.isdir(vendor_dir) and vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)
    if _flask_ok():
        return

    # 2. Plesk-venv site-packages suchen (.python-venvs/ bis 6 Ebenen hoch)
    parent = app_dir
    candidates = []
    for _ in range(6):
        parent = os.path.dirname(parent)
        if not parent or parent == "/":
            break
        venvs_dir = os.path.join(parent, ".python-venvs")
        if os.path.isdir(venvs_dir):
            for name in sorted(os.listdir(venvs_dir)):
                v = os.path.join(venvs_dir, name)
                if os.path.isdir(v):
                    candidates.append(v)
    # Lokale venvs (Entwicklung)
    candidates.append(os.path.join(app_dir, "venv"))
    candidates.append(os.path.join(app_dir, ".venv"))
    for venv_path in candidates:
        added = False
        for lib_dir in ("lib", "lib64"):
            for py_ver in ("python3.9", "python3.10", "python3.11",
                           "python3.12", "python3.13"):
                site = os.path.join(venv_path, lib_dir, py_ver, "site-packages")
                if os.path.isdir(site) and site not in sys.path:
                    sys.path.insert(0, site)
                    added = True
        if added and _flask_ok():
            return

    # 3. Re-exec mit venv-Python, falls wir mit dem System-Python laufen
    for venv_path in candidates:
        py_bin = os.path.join(venv_path, "bin", "python")
        if (os.path.isfile(py_bin)
                and os.path.realpath(sys.executable) != os.path.realpath(py_bin)):
            try:
                os.execl(py_bin, py_bin, *sys.argv)
            except OSError:
                continue


_bootstrap_dependencies()


def _run_task_safe(task, fn):
    """Fuehrt eine Aufgabe aus und schreibt den Heartbeat (ok/fehler)."""
    from cron_heartbeat import record_cron_run
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        result = fn()
        record_cron_run(task, ok=result if isinstance(result, bool) else True)
        return result
    except Exception as e:
        record_cron_run(task, ok=False, detail=f"{type(e).__name__}: {e}")
        print(f"[{ts}] {task.upper()}: FEHLER - {type(e).__name__}: {e}")
        return False


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


def run_backup():
    """Erstellt das taegliche SQLite-Backup (Heartbeat schreibt backup.py selbst)."""
    from app import app
    from backup import create_database_backup
    with app.app_context():
        result = create_database_backup()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if result["ok"]:
            print(f"[{ts}] BACKUP: {result['name']} ({result['size']} Bytes), "
                  f"{len(result['removed'])} alte entfernt")
        else:
            print(f"[{ts}] BACKUP: FEHLER - {result['error']}")
        return result["ok"]


def run_status():
    """Gibt den Heartbeat-Status aller Aufgaben als Textzeilen aus."""
    from app import app
    from cron_heartbeat import get_cron_status
    with app.app_context():
        for row in get_cron_status():
            age = f"{row['age_minutes']} min" if row["age_minutes"] is not None else "-"
            mark = {"ok": "OK  ", "warn": "WARN", "error": "FEHL",
                    "never": "NIE "}[row["state"]]
            detail = f" - {row['detail']}" if row.get("detail") else ""
            print(f"[{mark}] {row['label']:<28} letzter Lauf: {age:>10}{detail}")
        return True


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "all"

    if task == "sync":
        _run_task_safe("sync", run_sync)
    elif task == "reminder":
        _run_task_safe("reminder", run_reminders)
    elif task == "bots":
        _run_task_safe("bots", run_bot_tips)
    elif task == "backup":
        _run_task_safe("backup", run_backup)
    elif task == "status":
        run_status()
    elif task == "all":
        _run_task_safe("sync", run_sync)
        _run_task_safe("bots", run_bot_tips)
        _run_task_safe("reminder", run_reminders)
    else:
        print(f"Unbekannte Task: {task}")
        print("Verwendung: python cron_jobs.py [sync|reminder|bots|backup|status|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
