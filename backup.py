"""Datenbank-Backup fuer Shared Hosting (Netcup/Plesk).

Erstellt konsistente SQLite-Kopien der Produktions-DB - auch waehrend die App
laeuft (sqlite3-Backup-API statt blossem Datei-Kopieren), rotiert alte
Backups automatisch und schreibt einen Cron-Heartbeat, damit das
Admin-Wartungscenter den letzten Lauf anzeigen kann.

Aufgabe im Plesk-Cron (einmal taeglich, z. B. 03:15 Uhr):
  /var/www/vhosts/<domain>/.python-venvs/<app>/bin/python
      /var/www/vhosts/<domain>/<app-pfad>/cron_jobs.py backup

Wichtig: Die Backups liegen auf demselben Server wie die App. Für echten
Schutz mindestens wöchentlich den Ordner `backups/` per FTP herunterladen
(Offsite-Kopie).
"""
import glob
import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app


def _db_file_path():
    """Pfad zur SQLite-Datei aus der SQLAlchemy-URI (nur sqlite)."""
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("sqlite:///"):
        return None
    raw = uri.replace("sqlite:///", "", 1)
    if os.path.isabs(raw):
        return raw
    return os.path.join(current_app.root_path, raw)


def _backup_dir():
    return current_app.config.get(
        "BACKUP_DIR", os.path.join(current_app.root_path, "backups")
    )


def list_backups():
    """Liste vorhandener Backup-Dateien (Pfad, Groesse, mtime), neueste zuerst."""
    d = _backup_dir()
    if not os.path.isdir(d):
        return []
    out = []
    for p in glob.glob(os.path.join(d, "tippspiel_*.db")):
        try:
            st = os.stat(p)
        except OSError:
            continue
        out.append({"path": p, "name": os.path.basename(p),
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                             .strftime("%Y-%m-%d %H:%M:%S")})
    out.sort(key=lambda x: x["name"], reverse=True)
    return out


def _rotate(backup_dir, keep):
    """Loescht aeltere Backups, bis maximal `keep` Stueck uebrig sind."""
    files = sorted(glob.glob(os.path.join(backup_dir, "tippspiel_*.db")))
    removed = []
    while len(files) > max(1, keep):
        oldest = files.pop(0)
        try:
            os.remove(oldest)
            removed.append(os.path.basename(oldest))
        except OSError:
            pass
    return removed


def create_database_backup(keep=None):
    """Erstellt ein Backup und rotiert alte Dateien.

    Returns dict mit ok/file/size/error/removed; schreibt den Heartbeat
    (`cron_last_run:backup`), damit Erfolg UND Fehlschlag im Admin sichtbar sind.
    """
    from cron_heartbeat import record_cron_run
    keep = int(keep if keep is not None else current_app.config.get("BACKUP_KEEP", 14))

    src = _db_file_path()
    if not src:
        msg = "Backup nur für SQLite unterstützt."
        record_cron_run("backup", ok=False, detail=msg)
        return {"ok": False, "error": msg, "file": None, "size": 0, "removed": []}
    if not os.path.exists(src):
        msg = f"Datenbankdatei fehlt: {src}"
        record_cron_run("backup", ok=False, detail=msg)
        return {"ok": False, "error": msg, "file": None, "size": 0, "removed": []}

    backup_dir = _backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    final = os.path.join(backup_dir, f"tippspiel_{stamp}.db")
    tmp = os.path.join(backup_dir, f".tmp_{stamp}.db")

    try:
        # Backup-API: konsistente Kopie auch bei laufender App (WAL etc.)
        source = sqlite3.connect(src, timeout=30)
        target = sqlite3.connect(tmp, timeout=30)
        with target:
            source.backup(target)
        target.close()
        source.close()
        os.replace(tmp, final)
        size = os.path.getsize(final)
        removed = _rotate(backup_dir, keep)
        record_cron_run("backup", ok=True, detail=f"{os.path.basename(final)} ({size} Bytes)")
        return {"ok": True, "file": final, "name": os.path.basename(final),
                "size": size, "error": None, "removed": removed}
    except Exception as e:  # pragma: no cover - Defensivpfad
        for p in (tmp,):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        record_cron_run("backup", ok=False, detail=str(e)[:200])
        return {"ok": False, "error": str(e), "file": None, "size": 0, "removed": []}
