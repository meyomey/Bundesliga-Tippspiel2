"""Cron-Aufruf per HTTP - fuer Plesk-Cron im chroot ohne Python.

Netcup fuehrt geplante Aufgaben in einer chroot-Umgebung aus, in der kein
Python verfuegbar ist (nur sh/bash/php/wget/curl). Stattdessen ruft die
Plesk-Aufgabe diese URL auf - die App selbst fuehrt die Arbeit aus
(sync/reminder/bots/backup) und schreibt die Heartbeats wie sonst auch.

Beispiel-Aufgabe (Plesk > Geplante Aufgaben):
    wget -q -O /dev/null "https://tipp.wulmstorf.net/cron/run?task=all&key=SECRET"

Schutz: Secret-Vergleich per hmac. Secret kommt aus Setting `cron_secret`
oder ENV `CRON_SECRET` (.env). Ohne Secret ist die Route deaktiviert (404).
"""
import hmac

from flask import current_app, jsonify, request

from routes_main import main_bp

_ALLOWED = ("sync", "reminder", "bots", "backup", "all")


def _cron_secret():
    from scoring import get_setting
    return (get_setting("cron_secret", current_app.config.get("CRON_SECRET", ""))
            or "")


@main_bp.route("/cron/run", methods=["GET"], endpoint="cron_http_run")
def cron_http_run():
    """Fuehrt eine Cron-Task im App-Kontext aus (Aufruf nur mit gueltigem Key)."""
    secret = _cron_secret()
    if not secret:
        return jsonify({"ok": False,
                        "msg": "Cron-HTTP deaktiviert: kein Secret gesetzt"}), 404

    key = request.args.get("key", "") or ""
    if not hmac.compare_digest(str(key), str(secret)):
        return jsonify({"ok": False, "msg": "Ungueltiger Cron-Key"}), 403

    task = request.args.get("task", "all")
    if task not in _ALLOWED:
        return jsonify({"ok": False, "msg": f"Unbekannte Task: {task}"}), 400

    import cron_jobs
    handlers = {
        "sync": cron_jobs.run_sync,
        "reminder": cron_jobs.run_reminders,
        "bots": cron_jobs.run_bot_tips,
        "backup": cron_jobs.run_backup,
    }
    tasks = ("sync", "bots", "reminder") if task == "all" else (task,)
    results = {}
    for t in tasks:
        ok = cron_jobs._run_task_safe(t, handlers[t])
        results[t] = bool(ok)

    return jsonify({"ok": all(results.values()), "tasks": results,
                    "msg": "Cron-HTTP ausgefuehrt"})
