"""Admin: DB-/Schema-Wartung."""
from flask import flash, redirect, render_template, url_for

from audit_log import log_admin_action


def _admin_schema_view():
    from schema_migrations import schema_status
    return render_template("admin/schema.html", status=schema_status())


def _admin_schema_run():
    from schema_migrations import run_pending_migrations
    results = run_pending_migrations()
    ok = all(r.get("ok") for r in results) if results else True
    log_admin_action("schema_migrations_run", "schema", None, f"{len(results)} Migration(en) ausgefuehrt", {"results": results})
    if not results:
        flash("ℹ️ Keine offenen Migrationen.", "info")
    elif ok:
        flash(f"✅ {len(results)} Migration(en) erfolgreich ausgeführt.", "success")
    else:
        flash("❌ Migrationen mit Fehler abgebrochen. Details siehe Activity Log.", "danger")
    return redirect(url_for("admin.schema_center"))
