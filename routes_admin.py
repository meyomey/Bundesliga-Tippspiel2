"""Admin-Routes: Dashboard, Sync, Users, Badges, Prizes, Settings, etc."""
import os
import sqlite3
import tempfile
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    abort, send_file, current_app, session,
)
from flask_login import login_required, current_user
from sqlalchemy import func
from io import BytesIO

from extensions import db
from models import (
    User, Team, Match, Prediction, Setting, Comment, Badge, UserBadge,
    SpecialQuestion, SpecialPrediction, SeasonArchive, Prize, MatchdayWinner,
    Competition, CompetitionTeam, AdminActivityLog,
)
from forms import (
    MatchResultForm, SettingsForm, SpecialQuestionForm,
    BadgeForm, AdminUserForm, PrizeForm,
)
from scoring import (
    get_setting, set_setting, recalculate_all_points, compute_pot_summary,
    is_bot_user, is_pot_participant, is_admin_only_user,
)
from stats import evaluate_special_predictions, get_current_matchday
from badges import check_and_award_badges, award_badge, revoke_badge
from sync import sync_results, get_sync_diagnostics, season_code_from_label, _purge_demo_matches, auto_migrate_schema, force_seed_demo_matches
from mail_helpers import apply_mail_settings, send_email
from stats import archive_season
from competition_helpers import (
    active_match_query, active_matchdays, get_active_competition,
    filter_competition_scoped,
)

import json as _json
from audit_log import log_admin_action


admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        if session.get("player_preview_mode") and request.endpoint != "admin.player_preview_end":
            flash("Spieleransicht ist aktiv. Beende sie, um den Admin-Bereich zu nutzen.", "info")
            return redirect(url_for("main.dashboard"))
        return f(*a, **kw)
    return wrapper


@admin_bp.route("/player-preview/start")
@login_required
@admin_required
def player_preview_start():
    session["player_preview_mode"] = True
    flash("👤 Spieleransicht aktiv: Admin-Menüs sind ausgeblendet.", "info")
    return redirect(url_for("main.dashboard"))


@admin_bp.route("/player-preview/end")
@login_required
@admin_required
def player_preview_end():
    session.pop("player_preview_mode", None)
    flash("Admin-Ansicht wieder aktiv.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    comp = get_active_competition()
    pred_q = Prediction.query.join(Match)
    if comp:
        pred_q = pred_q.filter(Match.competition_id == comp.id)
    pot = compute_pot_summary()
    all_users = User.query.all()
    user_summary = {
        "accounts": len(all_users),
        "players": sum(1 for u in all_users if is_pot_participant(u)),
        "bots": sum(1 for u in all_users if is_bot_user(u)),
        "admin_only": sum(1 for u in all_users if is_admin_only_user(u)),
    }
    stats = {
        "users": user_summary["players"],
        "accounts": user_summary["accounts"],
        "bots": user_summary["bots"],
        "admin_only": user_summary["admin_only"],
        "matches": active_match_query().count(),
        "predictions": pred_q.count(),
        "finished": active_match_query().filter_by(status="finished").count(),
    }
    return render_template("admin/dashboard.html", stats=stats, pot=pot)


@admin_bp.route("/activity")
@login_required
@admin_required
def activity_log():
    page = request.args.get("page", 1, type=int)
    action = (request.args.get("action", "") or "").strip()
    qtext = (request.args.get("q", "") or "").strip()
    query = AdminActivityLog.query
    if action:
        query = query.filter(AdminActivityLog.action == action)
    if qtext:
        like = f"%{qtext}%"
        query = query.filter(
            (AdminActivityLog.message.ilike(like)) |
            (AdminActivityLog.entity_type.ilike(like)) |
            (AdminActivityLog.entity_id.ilike(like))
        )
    pagination = query.order_by(AdminActivityLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    actions = [a for (a,) in db.session.query(AdminActivityLog.action).distinct().order_by(AdminActivityLog.action.asc()).all()]
    return render_template("admin/activity.html", pagination=pagination, logs=pagination.items, actions=actions, current_action=action, q=qtext)


@admin_bp.route("/sync")
@login_required
@admin_required
def sync():
    if request.args.get("run") == "1":
        res = sync_results()
        log_admin_action("sync", "competition", get_active_competition().code if get_active_competition() else None, res.get("msg"), {"ok": res.get("ok"), "source": res.get("source"), "created": res.get("created"), "updated": res.get("updated")})
        flash(res["msg"], "success" if res["ok"] else "danger")
        return redirect(url_for("admin.sync"), code=303)
    return render_template("admin/sync.html", diag=get_sync_diagnostics())


@admin_bp.route("/purge-demo", methods=["POST"])
@login_required
@admin_required
def purge_demo():
    count = _purge_demo_matches()
    log_admin_action("purge_demo", "match", None, f"{count} Demo-Spiele entfernt", {"count": count})
    flash(f"{count} Demo-Spiele entfernt.", "success" if count else "info")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/seed-demo", methods=["POST"])
@login_required
@admin_required
def seed_demo():
    count = force_seed_demo_matches()
    log_admin_action("seed_demo", "match", None, f"{count} Demo-Spiele neu erstellt", {"count": count})
    flash(f"✅ {count} Demo-Spiele neu erstellt (vorhandene geloescht).", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/purge-all-matches", methods=["POST"])
@login_required
@admin_required
def purge_all_matches():
    Prediction.query.delete()
    Comment.query.delete()
    Match.query.delete()
    db.session.commit()
    log_admin_action("purge_all_matches", "match", None, "Alle Matches und Tipps gelöscht")
    flash("⚠️ Alle Matches und Tipps gelöscht.", "warning")
    return redirect(url_for("admin.dashboard"))


# ============================================================ Backup / Restore -
def _sqlite_db_path():
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("sqlite:///"):
        return None
    raw = uri.replace("sqlite:///", "", 1)
    if os.path.isabs(raw):
        return raw
    return os.path.join(current_app.root_path, raw)


@admin_bp.route("/backup", methods=["GET"])
@login_required
@admin_required
def backup_page():
    db_path = _sqlite_db_path()
    exists = bool(db_path and os.path.exists(db_path))
    size = os.path.getsize(db_path) if exists else 0
    return render_template("admin/backup.html", db_path=db_path, exists=exists, size=size)


@admin_bp.route("/backup/download")
@login_required
@admin_required
def backup_download():
    db_path = _sqlite_db_path()
    if not db_path or not os.path.exists(db_path):
        flash("Backup nicht möglich: SQLite-Datenbank nicht gefunden.", "danger")
        return redirect(url_for("admin.backup_page"))
    filename = f"wulmstoerper_tipprunde_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(db_path, as_attachment=True, download_name=filename,
                     mimetype="application/octet-stream")


@admin_bp.route("/backup/zip")
@login_required
@admin_required
def backup_zip_download():
    """Laedt DB + wichtige Uploads/Logos als ZIP herunter."""
    db_path = _sqlite_db_path()
    if not db_path or not os.path.exists(db_path):
        flash("ZIP-Backup nicht möglich: SQLite-Datenbank nicht gefunden.", "danger")
        return redirect(url_for("admin.backup_page"))
    mem = BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, arcname="tippspiel.db")
        for folder, arc_prefix in [
            (current_app.config.get("UPLOAD_FOLDER"), "static/uploads"),
            (os.path.join(current_app.static_folder, "team_logos"), "static/team_logos"),
        ]:
            if folder and os.path.isdir(folder):
                for root, _dirs, files in os.walk(folder):
                    for fn in files:
                        path = os.path.join(root, fn)
                        rel = os.path.relpath(path, folder)
                        zf.write(path, arcname=os.path.join(arc_prefix, rel))
        zf.writestr("README_BACKUP.txt", "Backup enthaelt SQLite-Datenbank und lokale Uploads/Logos. Sensible Daten sicher aufbewahren.\n")
    mem.seek(0)
    filename = f"wulmstoerper_full_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    log_admin_action("backup_zip_download", "database", None, "ZIP-Backup heruntergeladen")
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="application/zip")


@admin_bp.route("/backup/restore", methods=["POST"])
@login_required
@admin_required
def backup_restore():
    db_path = _sqlite_db_path()
    if not db_path:
        flash("Restore ist nur bei SQLite-Datenbanken verfügbar.", "danger")
        return redirect(url_for("admin.backup_page"))

    uploaded = request.files.get("backup_file")
    if not uploaded or not uploaded.filename:
        flash("Bitte eine .db-Datei auswählen.", "danger")
        return redirect(url_for("admin.backup_page"))

    if not uploaded.filename.lower().endswith((".db", ".sqlite", ".sqlite3")):
        flash("Ungültiger Dateityp.", "danger")
        return redirect(url_for("admin.backup_page"))

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        uploaded.save(tmp_path)
        try:
            con = sqlite3.connect(tmp_path)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            valid = cur.fetchone() is not None
            con.close()
        except sqlite3.DatabaseError:
            valid = False
        if not valid:
            flash("Ungültige Tipprunden-Datenbank.", "danger")
            return redirect(url_for("admin.backup_page"))

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if os.path.exists(db_path):
            backup_before = db_path + ".before_restore_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            shutil.copy2(db_path, backup_before)

        db.session.remove()
        db.engine.dispose()
        shutil.copy2(tmp_path, db_path)
        log_admin_action("backup_restore", "database", None, "Backup wiederhergestellt", {"filename": uploaded.filename})
        flash("✅ Backup wiederhergestellt. App neu starten.", "success")
        return redirect(url_for("admin.dashboard"))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@admin_bp.route("/matches")
@login_required
@admin_required
def matches():
    md = request.args.get("matchday", 1, type=int)
    matches = active_match_query().filter_by(matchday=md).order_by(Match.kickoff).all()
    matchdays = active_matchdays()
    return render_template("admin/matches.html", matches=matches, current_md=md, matchdays=matchdays)


@admin_bp.route("/match/<int:match_id>/result", methods=["GET", "POST"])
@login_required
@admin_required
def edit_result(match_id):
    match = db.get_or_404(Match, match_id)
    form = MatchResultForm(obj=match)
    if form.validate_on_submit():
        from match_results import set_match_result
        set_match_result(match, form.home_score.data, form.away_score.data, status="finished", source="admin")
        log_admin_action("result_update", "match", match.id, f"Ergebnis {match.home_team.short_name}-{match.away_team.short_name}: {match.home_score}:{match.away_score}")
        flash(f"Ergebnis gespeichert.", "success")
        return redirect(url_for("admin.matches", matchday=match.matchday))
    return render_template("admin/edit_result.html", match=match, form=form)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    from admin_users_routes import _admin_users
    return _admin_users()


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def user_edit(user_id):
    from admin_users_routes import _admin_user_edit
    return _admin_user_edit(user_id)


@admin_bp.route("/user/<int:user_id>/toggle_paid", methods=["POST"])
@login_required
@admin_required
def toggle_paid(user_id):
    from admin_users_routes import _admin_toggle_paid
    return _admin_toggle_paid(user_id)


@admin_bp.route("/user/<int:user_id>/toggle_admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id):
    from admin_users_routes import _admin_toggle_admin
    return _admin_toggle_admin(user_id)


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    from admin_users_routes import _admin_delete_user
    return _admin_delete_user(user_id)


@admin_bp.route("/open-tips", methods=["GET", "POST"])
@login_required
@admin_required
def admin_open_tips():
    from admin_open_tips_routes import _admin_open_tips_view
    return _admin_open_tips_view()


# ============================================================ Prizes -
@admin_bp.route("/prizes")
@login_required
@admin_required
def admin_prizes():
    from admin_prizes_routes import _admin_prizes
    return _admin_prizes()


@admin_bp.route("/prizes/new", methods=["GET", "POST"])
@admin_bp.route("/prizes/<int:prize_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def prize_form(prize_id=None):
    from admin_prizes_routes import _admin_prize_form
    return _admin_prize_form(prize_id)


@admin_bp.route("/prizes/<int:prize_id>/delete", methods=["POST"])
@login_required
@admin_required
def prize_delete(prize_id):
    from admin_prizes_routes import _admin_prize_delete
    return _admin_prize_delete(prize_id)


# ============================================================ Badges -
@admin_bp.route("/badges")
@login_required
@admin_required
def badges():
    from admin_badges_routes import _admin_badges
    return _admin_badges()


@admin_bp.route("/badges/new", methods=["GET", "POST"])
@admin_bp.route("/badges/<int:badge_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def badge_form(badge_id=None):
    from admin_badges_routes import _admin_badge_form
    return _admin_badge_form(badge_id)


@admin_bp.route("/badges/<int:badge_id>/delete", methods=["POST"])
@login_required
@admin_required
def badge_delete(badge_id):
    from admin_badges_routes import _admin_badge_delete
    return _admin_badge_delete(badge_id)


@admin_bp.route("/badges/<int:badge_id>/award", methods=["GET", "POST"])
@login_required
@admin_required
def badge_award(badge_id):
    from admin_badges_routes import _admin_badge_award
    return _admin_badge_award(badge_id)


@admin_bp.route("/badges/recheck", methods=["POST"])
@login_required
@admin_required
def badge_recheck():
    from admin_badges_routes import _admin_badge_recheck
    return _admin_badge_recheck()


# ============================================================ Special Questions -
@admin_bp.route("/special-questions", methods=["GET", "POST"])
@login_required
@admin_required
def special_questions():
    from admin_special_questions_routes import _admin_special_questions
    return _admin_special_questions()


@admin_bp.route("/special-question/<int:qid>/answer", methods=["POST"])
@login_required
@admin_required
def set_special_answer(qid):
    from admin_special_questions_routes import _admin_set_special_answer
    return _admin_set_special_answer(qid)


@admin_bp.route("/special-question/<int:qid>/edit", methods=["POST"])
@login_required
@admin_required
def edit_special_question(qid):
    from admin_special_questions_routes import _admin_edit_special_question
    return _admin_edit_special_question(qid)


@admin_bp.route("/special-question/<int:qid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_special_question(qid):
    from admin_special_questions_routes import _admin_delete_special_question
    return _admin_delete_special_question(qid)


@admin_bp.route("/archive-season", methods=["POST"])
@login_required
@admin_required
def archive_current_season():
    label = request.form.get("season_label", "").strip()
    if not label:
        flash("Saison-Label fehlt.", "danger")
        return redirect(url_for("admin.dashboard"))
    archive_season(label)
    flash(f"Saison '{label}' archiviert.", "success")
    return redirect(url_for("admin.dashboard"))


# ============================================================ Settings -


@admin_bp.route("/integrity", methods=["GET", "POST"])
@login_required
@admin_required
def integrity():
    from admin_integrity_routes import _admin_integrity_view
    return _admin_integrity_view()


@admin_bp.route("/invitations")
@login_required
@admin_required
def invitations():
    from admin_invitations_routes import _admin_invitations_view
    return _admin_invitations_view()


@admin_bp.route("/invitations/create", methods=["POST"])
@login_required
@admin_required
def invitation_create():
    from admin_invitations_routes import _admin_invitation_create
    return _admin_invitation_create()


@admin_bp.route("/invitations/<int:invite_id>/deactivate", methods=["POST"])
@login_required
@admin_required
def invitation_deactivate(invite_id):
    from admin_invitations_routes import _admin_invitation_deactivate
    return _admin_invitation_deactivate(invite_id)


@admin_bp.route("/invitations/<int:invite_id>/delete", methods=["POST"])
@login_required
@admin_required
def invitation_delete(invite_id):
    from admin_invitations_routes import _admin_invitation_delete
    return _admin_invitation_delete(invite_id)


@admin_bp.route("/settings/test-mail", methods=["POST"])
@login_required
@admin_required
def test_mail():
    recipient = (request.form.get("mail_test_recipient") or current_user.email or "").strip()
    if not recipient:
        flash("Bitte einen Test-Empfänger eintragen.", "danger")
        return redirect(url_for("admin.settings"))

    for key in ["mail_server", "mail_username", "mail_password", "mail_default_sender"]:
        if key in request.form:
            val = request.form.get(key, "").strip()
            if key == "mail_password" and not val:
                continue
            set_setting(key, val)
    if "mail_port" in request.form:
        try:
            set_setting("mail_port", int(request.form.get("mail_port") or 587))
        except ValueError:
            set_setting("mail_port", 587)
    set_setting("mail_use_tls", bool(request.form.get("mail_use_tls")))
    set_setting("mail_use_ssl", bool(request.form.get("mail_use_ssl")))
    apply_mail_settings()

    ok = send_email(
        "Testmail – Wulmstörper Tipprunde",
        [recipient],
        "Diese Testmail wurde über die SMTP-Einstellungen gesendet.",
    )
    if ok:
        flash(f"✅ Testmail gesendet an {recipient}.", "success")
    else:
        flash("❌ Testmail konnte nicht gesendet werden.", "danger")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/settings/test-reminder", methods=["POST"])
@login_required
@admin_required
def test_reminder():
    """Sendet eine Test-Erinnerung fuer fehlende Tipps an den aktuellen Admin."""
    # Relevante Einstellungen aus dem Formular uebernehmen, damit der Test direkt
    # nach dem Eintragen von SMTP/PUBLIC_BASE_URL funktioniert.
    for key in ["mail_server", "mail_username", "mail_password", "mail_default_sender"]:
        if key in request.form:
            val = request.form.get(key, "").strip()
            if key == "mail_password" and not val:
                continue
            set_setting(key, val)
    if "mail_port" in request.form:
        try:
            set_setting("mail_port", int(request.form.get("mail_port") or 587))
        except ValueError:
            set_setting("mail_port", 587)
    if "public_base_url" in request.form:
        set_setting("public_base_url", (request.form.get("public_base_url") or "").strip().rstrip("/"))
    set_setting("mail_use_tls", bool(request.form.get("mail_use_tls")))
    set_setting("mail_use_ssl", bool(request.form.get("mail_use_ssl")))
    set_setting("reminders_enabled", bool(request.form.get("reminders_enabled")))
    apply_mail_settings()
    try:
        from mail_helpers import apply_vapid_settings
        apply_vapid_settings()
    except Exception:
        pass

    from notification_center import send_test_missing_tip_notification
    result = send_test_missing_tip_notification(current_user)
    sent = [k for k, ok in result.items() if ok]
    log_admin_action(
        "test_missing_tip_reminder",
        "user", current_user.id,
        "Test-Reminder fuer fehlende Tipps gesendet",
        {"channels": result},
    )
    if sent:
        flash(f"✅ Test-Erinnerung gesendet über: {', '.join(sent)}.", "success")
    else:
        flash("ℹ️ Keine Test-Erinnerung gesendet. Prüfe deine Benachrichtigungskanäle im Profil und SMTP/Push/Telegram/WhatsApp-Konfiguration.", "info")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    form = SettingsForm()

    if request.method == "GET":
        form.points_exact.data = get_setting("points_exact", 4)
        form.points_diff.data = get_setting("points_diff", 3)
        form.points_tendency.data = get_setting("points_tendency", 2)
        form.pot_amount.data = get_setting("pot_amount", 5)
        form.pot_currency.data = get_setting("pot_currency", "€")
        form.pot_intro.data = get_setting("pot_intro", "")
        form.payment_info_title.data = get_setting("payment_info_title", "Zahlung an den Spielleiter")
        form.payment_info_text.data = get_setting("payment_info_text", "")
        form.prize_notes.data = get_setting("prize_notes", "")
        form.football_data_token.data = ""
        form.public_base_url.data = get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", ""))
        form.mail_server.data = get_setting("mail_server", current_app.config.get("MAIL_SERVER", ""))
        form.mail_port.data = get_setting("mail_port", current_app.config.get("MAIL_PORT", 587))
        form.mail_username.data = get_setting("mail_username", current_app.config.get("MAIL_USERNAME", ""))
        form.mail_password.data = ""
        form.mail_default_sender.data = get_setting("mail_default_sender", current_app.config.get("MAIL_DEFAULT_SENDER", ""))
        form.mail_use_tls.data = bool(get_setting("mail_use_tls", True))
        form.mail_use_ssl.data = bool(get_setting("mail_use_ssl", False))
        form.mail_test_recipient.data = current_user.email
        form.vapid_public.data = ""
        form.vapid_private.data = ""
        form.telegram_bot_token.data = ""
        form.telegram_bot_username.data = get_setting("telegram_bot_username", "")
        form.telegram_webhook_secret.data = ""
        form.reminders_enabled.data = get_setting("reminders_enabled", True)
        form.registration_mode.data = get_setting("registration_mode", "invite")

    if form.validate_on_submit():
        old_exact = get_setting("points_exact", 4)
        old_diff = get_setting("points_diff", 3)
        old_tendency = get_setting("points_tendency", 2)

        set_setting("points_exact", int(form.points_exact.data or 4))
        set_setting("points_diff", int(form.points_diff.data or 3))
        set_setting("points_tendency", int(form.points_tendency.data or 2))
        set_setting("pot_amount", int(form.pot_amount.data or 5))
        set_setting("pot_currency", (form.pot_currency.data or "€").strip())
        set_setting("pot_intro", (form.pot_intro.data or "").strip())
        set_setting("payment_info_title", (form.payment_info_title.data or "").strip())
        set_setting("payment_info_text", (form.payment_info_text.data or "").strip())
        set_setting("prize_notes", (form.prize_notes.data or "").strip())

        api_token = (form.football_data_token.data or "").strip()
        if api_token:
            set_setting("football_data_token", api_token)
        set_setting("public_base_url", (form.public_base_url.data or "").strip().rstrip("/"))

        set_setting("mail_server", (form.mail_server.data or "").strip())
        set_setting("mail_port", int(form.mail_port.data or 587))
        set_setting("mail_username", (form.mail_username.data or "").strip())
        mail_pwd = (form.mail_password.data or "").strip()
        if mail_pwd:
            set_setting("mail_password", mail_pwd)
        set_setting("mail_default_sender", (form.mail_default_sender.data or "").strip())
        set_setting("mail_use_tls", bool(form.mail_use_tls.data))
        set_setting("mail_use_ssl", bool(form.mail_use_ssl.data))

        vapid_pub = (form.vapid_public.data or "").strip()
        if vapid_pub:
            set_setting("vapid_public", vapid_pub)
        vapid_priv = (form.vapid_private.data or "").strip()
        if vapid_priv:
            set_setting("vapid_private", vapid_priv)

        tg_token = (form.telegram_bot_token.data or "").strip()
        if tg_token:
            set_setting("telegram_bot_token", tg_token)
        tg_username = (form.telegram_bot_username.data or "").strip()
        if tg_username:
            set_setting("telegram_bot_username", tg_username)
        tg_webhook_secret = (form.telegram_webhook_secret.data or "").strip()
        if tg_webhook_secret:
            set_setting("telegram_webhook_secret", tg_webhook_secret)
        set_setting("reminders_enabled", bool(form.reminders_enabled.data))
        set_setting("registration_mode", form.registration_mode.data or "invite")

        apply_mail_settings()
        from mail_helpers import apply_vapid_settings
        apply_vapid_settings()

        new_exact = int(form.points_exact.data or 4)
        new_diff = int(form.points_diff.data or 3)
        new_tendency = int(form.points_tendency.data or 2)

        if old_exact != new_exact or old_diff != new_diff or old_tendency != new_tendency:
            recalculate_all_points()
            log_admin_action("settings_update", "settings", None, "Einstellungen gespeichert und Punkte neu berechnet")
            flash("✅ Einstellungen gespeichert und Punkte neu berechnet.", "success")
        else:
            log_admin_action("settings_update", "settings", None, "Einstellungen gespeichert")
            flash("✅ Einstellungen gespeichert.", "success")
        return redirect(url_for("admin.settings"), code=303)

    elif request.method == "POST":
        for field_name, errors in form.errors.items():
            field_label = getattr(getattr(form, field_name, None), "label", None)
            label_text = field_label.text if field_label else field_name
            for err in errors:
                flash(f"❌ {label_text}: {err}", "danger")
        flash("⚠️ Einstellungen konnten nicht gespeichert werden.", "warning")

    mail_missing = not (form.mail_server.data) or not (form.mail_username.data)
    api_missing = not (get_setting("football_data_token", current_app.config.get("FOOTBALL_DATA_TOKEN", "")))
    vapid_missing = not (get_setting("vapid_public", current_app.config.get("VAPID_PUBLIC_KEY", ""))) or not (get_setting("vapid_private", current_app.config.get("VAPID_PRIVATE_KEY", "")))
    pts_missing = not (form.points_exact.data) or not (form.points_diff.data) or not (form.points_tendency.data)
    pot_missing = not (form.pot_amount.data) or form.pot_amount.data == 0

    return render_template("admin/settings.html", form=form,
                           mail_missing=mail_missing, api_missing=api_missing,
                           vapid_missing=vapid_missing, pts_missing=pts_missing,
                           pot_missing=pot_missing,
                           api_configured=not api_missing,
                           mail_password_configured=bool(get_setting("mail_password", current_app.config.get("MAIL_PASSWORD", ""))),
                           vapid_private_configured=bool(get_setting("vapid_private", current_app.config.get("VAPID_PRIVATE_KEY", ""))),
                           telegram_token_configured=bool(get_setting("telegram_bot_token", current_app.config.get("TELEGRAM_BOT_TOKEN", ""))),
                           telegram_secret_configured=bool(get_setting("telegram_webhook_secret", current_app.config.get("TELEGRAM_WEBHOOK_SECRET", ""))))


@admin_bp.route("/export/tip-matrix/<int:matchday>")
@login_required
@admin_required
def export_tip_matrix(matchday):
    from admin_export_routes import _admin_export_tip_matrix
    return _admin_export_tip_matrix(matchday)


# ============================================================ Bot/Cache/New-Season Routes -
@admin_bp.route("/bots")
@login_required
@admin_required
def admin_bots():
    from admin_bots_routes import _admin_bots_view
    return _admin_bots_view()


@admin_bp.route("/bots/tip-all", methods=["POST"])
@login_required
@admin_required
def admin_bots_tip_all():
    from admin_bots_routes import _admin_bots_tip_all
    return _admin_bots_tip_all()


@admin_bp.route("/bots/tip-single", methods=["POST"])
@login_required
@admin_required
def admin_bots_tip_single():
    from admin_bots_routes import _admin_bots_tip_single
    return _admin_bots_tip_single()


@admin_bp.route("/bots/reset", methods=["POST"])
@login_required
@admin_required
def admin_bots_reset():
    from admin_bots_routes import _admin_bots_reset
    return _admin_bots_reset()


@admin_bp.route("/bots/toggle", methods=["POST"])
@login_required
@admin_required
def admin_bots_toggle():
    from admin_bots_routes import _admin_bots_toggle
    return _admin_bots_toggle()


@admin_bp.route("/bots/toggle-auto", methods=["POST"])
@login_required
@admin_required
def admin_bots_toggle_auto():
    from admin_bots_routes import _admin_bots_toggle_auto
    return _admin_bots_toggle_auto()


@admin_bp.route("/bots/seed", methods=["POST"])
@login_required
@admin_required
def admin_bots_seed():
    from admin_bots_routes import _admin_bots_seed
    return _admin_bots_seed()


@admin_bp.route("/bots/create", methods=["POST"])
@login_required
@admin_required
def admin_bots_create():
    from admin_bots_routes import _admin_bots_create_one
    return _admin_bots_create_one()


@admin_bp.route("/schema")
@login_required
@admin_required
def schema_center():
    from admin_schema_routes import _admin_schema_view
    return _admin_schema_view()


@admin_bp.route("/schema/run", methods=["POST"])
@login_required
@admin_required
def schema_run():
    from admin_schema_routes import _admin_schema_run
    return _admin_schema_run()


@admin_bp.route("/season-awards")
@login_required
@admin_required
def season_awards():
    from admin_awards_routes import _admin_season_awards_view
    return _admin_season_awards_view()


@admin_bp.route("/season-awards/pdf")
@login_required
@admin_required
def season_awards_pdf():
    from admin_awards_routes import _admin_season_awards_pdf
    return _admin_season_awards_pdf()


@admin_bp.route("/maintenance")
@login_required
@admin_required
def maintenance_center():
    from admin_maintenance_routes import _admin_maintenance_view
    return _admin_maintenance_view()


@admin_bp.route("/maintenance/run", methods=["POST"])
@login_required
@admin_required
def maintenance_run():
    from admin_maintenance_routes import _admin_maintenance_run
    return _admin_maintenance_run()


@admin_bp.route("/maintenance/backup-now", methods=["POST"])
@login_required
@admin_required
def maintenance_backup_now():
    from admin_maintenance_routes import _admin_cron_backup_now
    return _admin_cron_backup_now()


@admin_bp.route("/cache")
@login_required
@admin_required
def admin_cache():
    from cache_monitor_routes import _admin_cache_view
    return _admin_cache_view()


@admin_bp.route("/cache/flush-all", methods=["POST"])
@login_required
@admin_required
def admin_cache_flush_all():
    from cache_monitor_routes import _admin_cache_flush_all
    return _admin_cache_flush_all()


@admin_bp.route("/cache/flush-pattern", methods=["POST"])
@login_required
@admin_required
def admin_cache_flush_pattern():
    from cache_monitor_routes import _admin_cache_flush_pattern
    return _admin_cache_flush_pattern()


@admin_bp.route("/cache/delete-key", methods=["POST"])
@login_required
@admin_required
def admin_cache_delete_key():
    from cache_monitor_routes import _admin_cache_delete_key
    return _admin_cache_delete_key()


@admin_bp.route("/new-season", methods=["GET", "POST"])
@login_required
@admin_required
def new_season():
    """Saisonwechsel-Assistent 2.0.

    Fokus: erst prüfen/archivieren, dann gezielt wettbewerbsbezogene Daten
    löschen und die aktive Competition auf die neue Saison setzen.
    """
    comp = get_active_competition()
    current_season = get_setting("current_season", comp.season if comp else "2025/26")

    def _suggest_next(label):
        try:
            first = int(str(label).split("/")[0])
            return f"{first + 1}/{str(first + 2)[-2:]}"
        except Exception:
            year = datetime.now(timezone.utc).year
            return f"{year}/{str(year + 1)[-2:]}"

    if request.method == "POST":
        confirm_text = (request.form.get("confirm_text", "") or "").strip().upper()
        if confirm_text != "SAISON STARTEN":
            flash("Bitte bestätige den Saisonwechsel mit 'SAISON STARTEN'.", "warning")
            return redirect(url_for("admin.new_season"), code=303)

        do_archive = request.form.get("do_archive") == "1"
        do_delete_schedule = request.form.get("do_delete_schedule") == "1"
        do_delete_specials = request.form.get("do_delete_specials") == "1"
        do_reset_bots = request.form.get("do_reset_bots") == "1"
        do_reset_badges = request.form.get("do_reset_badges") == "1"
        do_reset_paid = request.form.get("do_reset_paid") == "1"
        new_season_label = (request.form.get("new_season_label", "") or _suggest_next(current_season)).strip()
        old_season_label = (request.form.get("old_season_label", "") or current_season).strip()

        if not new_season_label or new_season_label == old_season_label:
            flash("Bitte eine neue Saison eintragen (z.B. 2026/27).", "danger")
            return redirect(url_for("admin.new_season"), code=303)

        if request.form.get("backup_ack") != "1":
            flash("Bitte bestätige zuerst, dass ein aktuelles Backup vorhanden ist.", "warning")
            return redirect(url_for("admin.new_season"), code=303)

        risky_open_matches = active_match_query().filter(Match.status.in_(["scheduled", "live"])).count()
        risky_missing_results = active_match_query().filter(
            Match.status == "finished",
            (Match.home_score.is_(None)) | (Match.away_score.is_(None)),
        ).count()
        risky_special_open = filter_competition_scoped(
            SpecialQuestion.query.filter(SpecialQuestion.correct_answer.is_(None)), SpecialQuestion
        ).count()
        if (risky_open_matches or risky_missing_results or risky_special_open) and request.form.get("risk_ack") != "1":
            flash(
                "Es gibt noch offene/live Spiele, fehlende Ergebnisse oder offene Sonderfragen. Bitte prüfen und Risiko bestätigen.",
                "warning",
            )
            return redirect(url_for("admin.new_season"), code=303)

        try:
            if do_archive:
                archive_season(old_season_label)
                flash(f"✅ Saison {old_season_label} wurde in der Ewigen Tabelle archiviert.", "success")

            if do_delete_schedule:
                mdw_q = MatchdayWinner.query.filter_by(season=old_season_label)
                if comp:
                    mdw_q = mdw_q.filter(MatchdayWinner.competition_id == comp.id)
                mdw_q.delete(synchronize_session=False)

                match_ids = [m.id for m in active_match_query().all()]
                if match_ids:
                    Comment.query.filter(Comment.match_id.in_(match_ids)).delete(synchronize_session=False)
                    Prediction.query.filter(Prediction.match_id.in_(match_ids)).delete(synchronize_session=False)
                    Match.query.filter(Match.id.in_(match_ids)).delete(synchronize_session=False)
                db.session.commit()
                flash("🗑️ Spielplan, Tipps, Kommentare und Spieltagsieger gelöscht.", "success")

            if do_delete_specials:
                sp_q = filter_competition_scoped(SpecialPrediction.query, SpecialPrediction, include_global=False)
                sq_q = filter_competition_scoped(SpecialQuestion.query, SpecialQuestion, include_global=False)
                sp_q.delete(synchronize_session=False)
                sq_q.delete(synchronize_session=False)
                db.session.commit()
                flash("🗑️ Sonderfragen und Sondertipps gelöscht.", "success")

            if do_reset_bots:
                bot_ids = [u.id for u in User.query.filter(User.email.like("%@bot.local")).all()]
                if bot_ids:
                    match_ids = [m.id for m in active_match_query().all()]
                    if match_ids:
                        Prediction.query.filter(
                            Prediction.user_id.in_(bot_ids),
                            Prediction.match_id.in_(match_ids),
                        ).delete(synchronize_session=False)
                    db.session.commit()
                flash("🤖 Bot-Tipps zurückgesetzt.", "success")

            if do_reset_badges:
                from models import UserBadge
                UserBadge.query.delete(synchronize_session=False)
                db.session.commit()
                flash("🏅 Spieler-Badges zurückgesetzt.", "success")

            if do_reset_paid:
                User.query.filter(~User.email.like("%@bot.local")).update({
                    "has_paid": False, "paid_at": None, "paid_note": None
                }, synchronize_session=False)
                db.session.commit()
                flash("💰 Bezahlstatus zurückgesetzt.", "success")

            # Aktive Competition aktualisieren (nicht blind alle anderen deaktivieren)
            target = comp or Competition.query.filter_by(code=current_app.config.get("COMPETITION", "BL1")).first()
            import re as _re
            def _base_competition_name(existing, code):
                # Name soll die Saison NICHT mehr enthalten (erzeugte zuvor
                # Doppel-Labels wie 'Bundesliga 2026 2026'); Altbestand bereinigen.
                base = _re.sub(r"\s+20\d{2}(/\d{2})?$", "", (existing or "").strip())
                return base or ("Bundesliga" if code == "BL1" else code)
            if target:
                target.name = _base_competition_name(target.name, target.code)
                target.season = new_season_label
                target.is_active = True
                target.external_id = None
            else:
                target = Competition(
                    code="BL1", name="Bundesliga",
                    season=new_season_label, matchdays=34, teams_count=18,
                    is_active=True, external_id=None,
                )
                db.session.add(target)
            db.session.commit()

            set_setting("season", season_code_from_label(new_season_label))
            set_setting("current_season", new_season_label)

            try:
                from cache import invalidate_leaderboard
                invalidate_leaderboard()
            except Exception:
                pass

            log_admin_action("season_change", "competition", target.code if target else None,
                             f"Saisonwechsel {old_season_label} → {new_season_label}",
                             {"old_season": old_season_label, "new_season": new_season_label,
                              "archive": do_archive, "delete_schedule": do_delete_schedule,
                              "delete_specials": do_delete_specials, "reset_bots": do_reset_bots,
                              "reset_badges": do_reset_badges, "reset_paid": do_reset_paid})
            flash(f"🏁 Neue Saison '{new_season_label}' gestartet. Lade jetzt den neuen Spielplan per Sync.", "success")
            return redirect(url_for("admin.new_season"), code=303)

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Saison-Wechsel fehlgeschlagen")
            flash(f"❌ Saisonwechsel fehlgeschlagen: {e}", "danger")
            return redirect(url_for("admin.new_season"), code=303)

    # Diagnose/Checkliste fuer GET
    match_q = active_match_query()
    total_matches = match_q.count()
    finished_matches = active_match_query().filter_by(status="finished").count()
    scheduled_matches = active_match_query().filter(Match.status.in_(["scheduled", "live"])).count()
    missing_results = active_match_query().filter(
        Match.status == "finished",
        (Match.home_score.is_(None)) | (Match.away_score.is_(None)),
    ).count()
    match_ids = [m.id for m in active_match_query().all()]
    predictions_count = Prediction.query.filter(Prediction.match_id.in_(match_ids)).count() if match_ids else 0
    comments_count = Comment.query.filter(Comment.match_id.in_(match_ids)).count() if match_ids else 0
    pot_summary = compute_pot_summary()
    users_count = pot_summary.get("total_count", 0)
    paid_count = pot_summary.get("paid_count", 0)
    special_questions_count = filter_competition_scoped(SpecialQuestion.query, SpecialQuestion).count()
    special_open_count = filter_competition_scoped(
        SpecialQuestion.query.filter(SpecialQuestion.correct_answer.is_(None)), SpecialQuestion
    ).count()
    archived = filter_competition_scoped(
        SeasonArchive.query.filter_by(season=current_season), SeasonArchive
    ).count()

    checklist = {
        "backup_recommended": True,
        "all_matches_finished": total_matches > 0 and scheduled_matches == 0,
        "missing_results": missing_results,
        "special_open_count": special_open_count,
        "archived_count": archived,
        "can_archive": total_matches > 0,
    }
    counts = {
        "total_matches": total_matches,
        "finished_matches": finished_matches,
        "scheduled_matches": scheduled_matches,
        "predictions_count": predictions_count,
        "comments_count": comments_count,
        "users_count": users_count,
        "paid_count": paid_count,
        "special_questions_count": special_questions_count,
    }
    return render_template(
        "admin/new_season.html",
        comp=comp,
        current_season=current_season,
        suggested_next_season=_suggest_next(current_season),
        checklist=checklist,
        counts=counts,
    )

