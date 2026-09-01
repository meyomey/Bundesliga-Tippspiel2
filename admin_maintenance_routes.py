"""Admin: Wartungscenter."""
from flask import current_app, flash, redirect, render_template, request, url_for

from audit_log import log_admin_action


def _admin_maintenance_view():
    from maintenance import run_health_check
    return render_template("admin/maintenance.html", health=run_health_check())


def _admin_maintenance_run():
    from maintenance import run_repair_tasks
    task = request.form.get("task", "").strip()
    try:
        result = run_repair_tasks(task)
        log_admin_action("maintenance_run", "maintenance", task, f"Wartungsaufgabe ausgefuehrt: {task}", result)
        flash(f"✅ Wartung ausgeführt: {task} – {result}", "success")
    except Exception as e:
        current_app.logger.exception("Wartungsaufgabe fehlgeschlagen")
        flash(f"❌ Wartungsaufgabe fehlgeschlagen: {e}", "danger")
    return redirect(url_for("admin.maintenance_center"))


def _admin_cron_backup_now():
    from backup import create_database_backup
    result = create_database_backup()
    if result["ok"]:
        log_admin_action("backup_now", "backup", result["name"],
                         "Manuelles DB-Backup erstellt", result)
        flash(f"✅ Backup erstellt: {result['name']} ({result['size']} Bytes)", "success")
    else:
        log_admin_action("backup_now", "backup", None, f"Backup fehlgeschlagen: {result['error']}", result)
        flash(f"❌ Backup fehlgeschlagen: {result['error']}", "danger")
    return redirect(url_for("admin.maintenance_center"))
