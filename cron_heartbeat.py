"""Cron-Heartbeat: zeichnet Laeufe der geplanten Aufgaben auf und bewertet sie.

Netcup/Plesk-Cron laeuft ohne Aufsicht - wenn eine Aufgabe still ausfaellt
(Sync, Reminder, Bots, Backup), merkt das sonst niemand. Jede Aufgabe
schreibt deshalb bei jedem Lauf einen Zeitstempel in die Settings-Tabelle;
das Admin-Wartungscenter zeigt Alter und Status der letzten Laeufe an.
"""
from datetime import datetime, timezone

# task -> (Anzeigename, maximales Alter in Minuten fuer "ok", fuer "warn")
CRON_TASKS = {
    "sync":     ("Ergebnis-Sync (API)", 90, 360),
    "reminder": ("Tipp-Erinnerungen",    90, 360),
    "bots":     ("KI-Bot-Tipps",         120, 480),
    "backup":   ("Datenbank-Backup",     27 * 60, 75 * 60),  # taeglich ~03:15 Uhr
}


def record_cron_run(task, ok=True, detail=None):
    """Schreibt Zeitstempel + Status des letzten Laufs einer Aufgabe.

    Funktioniert innerhalb UND ausserhalb eines Flask-App-Kontexts
    (Plesk-Cron ruft cron_jobs.py ohne Request auf).
    """
    from flask import has_app_context
    from scoring import set_setting
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": bool(ok),
        "detail": str(detail)[:200] if detail else "",
    }
    if has_app_context():
        set_setting(f"cron_last_run:{task}", payload)
    else:
        from app import app
        with app.app_context():
            set_setting(f"cron_last_run:{task}", payload)


def get_cron_status(tasks=None):
    """Liefert Statuszeilen fuer die bekannten (oder angegebenen) Aufgaben.

    Jede Zeile: {task, label, ok, detail, ts (str|None), age_minutes (float|None),
    state}. state in {"never", "ok", "warn", "error"}.
    """
    from scoring import get_setting
    rows = []
    for task, (label, ok_min, warn_min) in (tasks or CRON_TASKS).items():
        raw = get_setting(f"cron_last_run:{task}", None)
        if not raw or not isinstance(raw, dict) or not raw.get("ts"):
            rows.append({"task": task, "label": label, "ok": None,
                         "detail": "", "ts": None, "age_minutes": None,
                         "state": "never"})
            continue
        ts = None
        try:
            ts = datetime.fromisoformat(raw["ts"])
        except (ValueError, TypeError):
            ts = None
        if ts is None:
            rows.append({"task": task, "label": label, "ok": raw.get("ok"),
                         "detail": raw.get("detail", ""), "ts": raw.get("ts"),
                         "age_minutes": None, "state": "error"})
            continue
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = max(0.0, (now - ts).total_seconds() / 60.0)
        if not raw.get("ok"):
            state = "error"          # letzter Lauf fehlgeschlagen
        elif age <= ok_min:
            state = "ok"
        elif age <= warn_min:
            state = "warn"
        else:
            state = "error"
        rows.append({"task": task, "label": label, "ok": bool(raw.get("ok")),
                     "detail": raw.get("detail", ""), "ts": raw["ts"],
                     "age_minutes": round(age, 1), "state": state})
    return rows


def cron_any_never_or_error(status_rows=None):
    """True, wenn mindestens eine Aufgabe nie lief oder im Fehlerzustand ist."""
    rows = status_rows if status_rows is not None else get_cron_status()
    return any(r["state"] in ("never", "error") for r in rows)
