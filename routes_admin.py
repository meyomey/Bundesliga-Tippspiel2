"""Admin-Routes: Dashboard, Sync, Users, Badges, Prizes, Settings, etc."""
import os
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    abort, send_file, current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import func
from io import BytesIO

from extensions import db
from models import (
    User, Team, Match, Prediction, Setting, Comment, Badge, UserBadge,
    SpecialQuestion, SpecialPrediction, SeasonArchive, Prize, MatchdayWinner,
    Competition, CompetitionTeam,
)
from forms import (
    MatchResultForm, SettingsForm, SpecialQuestionForm,
    BadgeForm, AdminUserForm, PrizeForm,
)
from scoring import (
    get_setting, set_setting, recalculate_all_points, compute_pot_summary,
)
from stats import evaluate_special_predictions, get_current_matchday
from badges import check_and_award_badges, award_badge, revoke_badge
from sync import sync_results, _purge_demo_matches, auto_migrate_schema, force_seed_demo_matches
from mail_helpers import apply_mail_settings, send_email
from stats import archive_season

import json as _json


admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*a, **kw)
    return wrapper


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "matches": Match.query.count(),
        "predictions": Prediction.query.count(),
        "finished": Match.query.filter_by(status="finished").count(),
    }
    pot = compute_pot_summary()
    return render_template("admin/dashboard.html", stats=stats, pot=pot)


@admin_bp.route("/sync")
@login_required
@admin_required
def sync():
    res = sync_results()
    flash(res["msg"], "success" if res["ok"] else "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/purge-demo", methods=["POST"])
@login_required
@admin_required
def purge_demo():
    count = _purge_demo_matches()
    flash(f"{count} Demo-Spiele entfernt.", "success" if count else "info")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/seed-demo", methods=["POST"])
@login_required
@admin_required
def seed_demo():
    count = force_seed_demo_matches()
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
    matches = Match.query.filter_by(matchday=md).order_by(Match.kickoff).all()
    matchdays = sorted([r[0] for r in db.session.query(Match.matchday).distinct().all()])
    return render_template("admin/matches.html", matches=matches, current_md=md, matchdays=matchdays)


@admin_bp.route("/match/<int:match_id>/result", methods=["GET", "POST"])
@login_required
@admin_required
def edit_result(match_id):
    match = Match.query.get_or_404(match_id)
    form = MatchResultForm(obj=match)
    if form.validate_on_submit():
        match.home_score = form.home_score.data
        match.away_score = form.away_score.data
        match.status = "finished"
        db.session.commit()
        recalculate_all_points()
        check_and_award_badges()
        flash(f"Ergebnis gespeichert.", "success")
        return redirect(url_for("admin.matches", matchday=match.matchday))
    return render_template("admin/edit_result.html", match=match, form=form)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    page = request.args.get("page", 1, type=int)
    per_page = 25
    pagination = User.query.order_by(User.username).paginate(page=page, per_page=per_page, error_out=False)
    all_users = pagination.items
    pot = compute_pot_summary()
    return render_template("admin/users.html", users=all_users, pot=pot, pagination=pagination)


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def user_edit(user_id):
    u = User.query.get_or_404(user_id)
    form = AdminUserForm(obj=u)
    teams = Team.query.order_by(Team.name).all()
    form.favorite_team_id.choices = [(0, "— kein Lieblingsverein —")] + [
        (t.id, t.name) for t in teams
    ]
    if request.method == "GET":
        form.favorite_team_id.data = u.favorite_team_id or 0

    if form.validate_on_submit():
        new_uname = (form.username.data or "").strip()
        if new_uname != u.username:
            other = User.query.filter(User.username == new_uname, User.id != u.id).first()
            if other:
                flash(f"Spielername '{new_uname}' ist bereits vergeben.", "danger")
                return render_template("admin/user_edit.html", user=u, form=form)
        new_email = (form.email.data or "").strip().lower()
        if new_email != u.email:
            other = User.query.filter(User.email == new_email, User.id != u.id).first()
            if other:
                flash(f"E-Mail '{new_email}' ist bereits vergeben.", "danger")
                return render_template("admin/user_edit.html", user=u, form=form)

        u.username = new_uname
        u.full_name = (form.full_name.data or "").strip() or None
        u.show_full_name = bool(form.show_full_name.data)
        u.email = new_email
        u.phone = (form.phone.data or "").strip() or None
        u.favorite_team_id = form.favorite_team_id.data or None
        if u.id == current_user.id and not form.is_admin.data:
            flash("Du kannst dir die Admin-Rechte nicht selbst entziehen.", "warning")
        else:
            u.is_admin = form.is_admin.data

        was_paid = u.has_paid
        u.has_paid = form.has_paid.data
        u.paid_note = (form.paid_note.data or "").strip() or None
        if u.has_paid and not was_paid:
            u.paid_at = datetime.now(timezone.utc)
        elif not u.has_paid:
            u.paid_at = None

        if form.new_password.data:
            u.set_password(form.new_password.data)

        db.session.commit()
        flash(f"Spieler '{u.username}' aktualisiert.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_edit.html", user=u, form=form)


@admin_bp.route("/user/<int:user_id>/toggle_paid", methods=["POST"])
@login_required
@admin_required
def toggle_paid(user_id):
    u = User.query.get_or_404(user_id)
    u.has_paid = not u.has_paid
    if u.has_paid:
        u.paid_at = datetime.now(timezone.utc)
    else:
        u.paid_at = None
    db.session.commit()
    flash(f"{u.username}: {'✅ Bezahlt' if u.has_paid else '❌ Removed'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/user/<int:user_id>/toggle_admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("Du kannst dich nicht selbst entfernen.", "warning")
    else:
        u.is_admin = not u.is_admin
        db.session.commit()
        flash(f"{u.username} ist jetzt {'Admin' if u.is_admin else 'normaler User'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("Du kannst dich nicht selbst löschen.", "warning")
    else:
        db.session.delete(u)
        db.session.commit()
        flash(f"User {u.username} gelöscht.", "info")
    return redirect(url_for("admin.users"))


# ============================================================ Prizes -
@admin_bp.route("/prizes")
@login_required
@admin_required
def admin_prizes():
    all_prizes = Prize.query.order_by(Prize.sort_order.asc(), Prize.rank.asc()).all()
    pot = compute_pot_summary()
    return render_template("admin/prizes.html", prizes=all_prizes, pot=pot)


@admin_bp.route("/prizes/new", methods=["GET", "POST"])
@admin_bp.route("/prizes/<int:prize_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def prize_form(prize_id=None):
    prize = db.session.get(Prize, prize_id) if prize_id else None
    form = PrizeForm(obj=prize)
    if form.validate_on_submit():
        if not prize:
            prize = Prize()
            db.session.add(prize)
        prize.rank = form.rank.data
        prize.title = form.title.data.strip()
        prize.description = (form.description.data or "").strip() or None
        prize.icon = form.icon.data.strip() or "🏆"
        prize.color = form.color.data.strip() or "#fbbf24"
        prize.amount = (form.amount.data or "").strip() or None
        prize.detail = (form.detail.data or "").strip() or None
        prize.active = form.active.data
        prize.sort_order = form.sort_order.data or 0
        db.session.commit()
        flash(f"Preis '{prize.title}' gespeichert.", "success")
        return redirect(url_for("admin.admin_prizes"))
    return render_template("admin/prize_form.html", form=form, prize=prize)


@admin_bp.route("/prizes/<int:prize_id>/delete", methods=["POST"])
@login_required
@admin_required
def prize_delete(prize_id):
    prize = Prize.query.get_or_404(prize_id)
    title = prize.title
    db.session.delete(prize)
    db.session.commit()
    flash(f"Preis '{title}' gelöscht.", "info")
    return redirect(url_for("admin.admin_prizes"))


# ============================================================ Badges -
@admin_bp.route("/badges")
@login_required
@admin_required
def badges():
    all_badges = Badge.query.order_by(Badge.created_at.desc()).all()
    award_counts = dict(
        db.session.query(UserBadge.badge_id, func.count(UserBadge.id))
        .group_by(UserBadge.badge_id).all()
    )
    return render_template("admin/badges.html", badges=all_badges, award_counts=award_counts)


@admin_bp.route("/badges/new", methods=["GET", "POST"])
@admin_bp.route("/badges/<int:badge_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def badge_form(badge_id=None):
    badge = db.session.get(Badge, badge_id) if badge_id else None
    form = BadgeForm(obj=badge)
    if form.validate_on_submit():
        existing = Badge.query.filter(
            Badge.code == form.code.data,
            Badge.id != (badge.id if badge else 0),
        ).first()
        if existing:
            flash(f"Badge-Code '{form.code.data}' ist bereits vergeben.", "danger")
            return render_template("admin/badge_form.html", form=form, badge=badge)

        if not badge:
            badge = Badge(code=form.code.data)
            db.session.add(badge)
        badge.code = form.code.data.strip()
        badge.name = form.name.data.strip()
        badge.description = form.description.data.strip()
        badge.icon = form.icon.data.strip() or "🏅"
        badge.color = form.color.data.strip() or "#fbbf24"
        badge.trigger_type = form.trigger_type.data
        badge.threshold = form.threshold.data or 0
        badge.active = form.active.data
        db.session.commit()

        if badge.trigger_type != "manual" and badge.active:
            check_and_award_badges()

        flash(f"Badge '{badge.name}' gespeichert.", "success")
        return redirect(url_for("admin.badges"))

    return render_template("admin/badge_form.html", form=form, badge=badge)


@admin_bp.route("/badges/<int:badge_id>/delete", methods=["POST"])
@login_required
@admin_required
def badge_delete(badge_id):
    badge = Badge.query.get_or_404(badge_id)
    name = badge.name
    UserBadge.query.filter_by(badge_id=badge.id).delete()
    db.session.delete(badge)
    db.session.commit()
    flash(f"Badge '{name}' gelöscht.", "info")
    return redirect(url_for("admin.badges"))


@admin_bp.route("/badges/<int:badge_id>/award", methods=["GET", "POST"])
@login_required
@admin_required
def badge_award(badge_id):
    badge = Badge.query.get_or_404(badge_id)
    if request.method == "POST":
        action = request.form.get("action", "award")
        user_ids = request.form.getlist("user_ids", type=int)
        count = 0
        for uid in user_ids:
            user = db.session.get(User, uid)
            if not user:
                continue
            if action == "award":
                if award_badge(user, badge):
                    count += 1
            elif action == "revoke":
                if revoke_badge(user, badge):
                    count += 1
        verb = "vergeben" if action == "award" else "entzogen"
        flash(f"Badge '{badge.name}' bei {count} User(n) {verb}.", "success")
        return redirect(url_for("admin.badge_award", badge_id=badge_id))

    awarded_user_ids = {ub.user_id for ub in UserBadge.query.filter_by(badge_id=badge.id).all()}
    all_users = User.query.order_by(User.username).all()
    return render_template(
        "admin/badge_award.html",
        badge=badge, all_users=all_users,
        awarded_user_ids=awarded_user_ids,
    )


@admin_bp.route("/badges/recheck", methods=["POST"])
@login_required
@admin_required
def badge_recheck():
    check_and_award_badges()
    flash("Alle Badge-Regeln neu geprüft.", "success")
    return redirect(url_for("admin.badges"))


# ============================================================ Special Questions -
@admin_bp.route("/special-questions", methods=["GET", "POST"])
@login_required
@admin_required
def special_questions():
    form = SpecialQuestionForm()
    if form.validate_on_submit():
        atype = form.answer_type.data or "text"
        opts_text = form.options.data or ""
        opt_list = [o.strip() for o in opts_text.split("\n") if o.strip()]

        if atype == "choice":
            options_json = _json.dumps(opt_list) if opt_list else None
        elif atype == "yes_no":
            options_json = _json.dumps(["Ja", "Nein"])
        else:
            options_json = None

        correct = (form.correct_answer.data or "").strip() or None

        q = SpecialQuestion(
            text=form.text.data,
            description=form.description.data or None,
            answer_type=atype,
            options=options_json,
            multi_count=form.multi_count.data or 1,
            number_min=form.number_min.data,
            number_max=form.number_max.data,
            deadline=form.deadline.data,
            points_value=form.points_value.data,
            correct_answer=correct,
        )
        db.session.add(q)
        db.session.commit()
        evaluate_special_predictions()
        flash(f"Sonderfrage angelegt.", "success")
        return redirect(url_for("admin.special_questions"))

    questions = SpecialQuestion.query.order_by(SpecialQuestion.deadline.desc()).all()
    min_dt = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
    all_teams = Team.query.order_by(Team.name).all()
    return render_template(
        "admin/special_questions.html",
        form=form, questions=questions, min_dt=min_dt,
        all_teams=all_teams,
    )


@admin_bp.route("/special-question/<int:qid>/answer", methods=["POST"])
@login_required
@admin_required
def set_special_answer(qid):
    q = SpecialQuestion.query.get_or_404(qid)
    if q.answer_type == "multi_team":
        values = [v.strip() for v in request.form.getlist("correct_answer") if v.strip()]
        q.correct_answer = _json.dumps(values) if values else None
    else:
        ans = request.form.get("correct_answer", "").strip()
        q.correct_answer = ans or None
    db.session.commit()
    evaluate_special_predictions()
    flash("Antwort gesetzt. Punkte wurden vergeben.", "success")
    return redirect(url_for("admin.special_questions"))


@admin_bp.route("/special-question/<int:qid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_special_question(qid):
    q = SpecialQuestion.query.get_or_404(qid)
    SpecialPrediction.query.filter_by(question_id=qid).delete()
    db.session.delete(q)
    db.session.commit()
    flash("Sonderfrage gelöscht.", "info")
    return redirect(url_for("admin.special_questions"))


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
        form.football_data_token.data = get_setting("football_data_token", "")
        form.mail_server.data = get_setting("mail_server", current_app.config.get("MAIL_SERVER", ""))
        form.mail_port.data = get_setting("mail_port", current_app.config.get("MAIL_PORT", 587))
        form.mail_username.data = get_setting("mail_username", current_app.config.get("MAIL_USERNAME", ""))
        form.mail_password.data = get_setting("mail_password", current_app.config.get("MAIL_PASSWORD", ""))
        form.mail_default_sender.data = get_setting("mail_default_sender", current_app.config.get("MAIL_DEFAULT_SENDER", ""))
        form.mail_use_tls.data = bool(get_setting("mail_use_tls", True))
        form.mail_use_ssl.data = bool(get_setting("mail_use_ssl", False))
        form.mail_test_recipient.data = current_user.email
        form.vapid_public.data = get_setting("vapid_public", "")
        form.vapid_private.data = get_setting("vapid_private", "")
        form.telegram_bot_token.data = get_setting("telegram_bot_token", "")
        form.telegram_bot_username.data = get_setting("telegram_bot_username", "")
        form.reminders_enabled.data = get_setting("reminders_enabled", True)

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

        api_token = (form.football_data_token.data or "").strip()
        if api_token:
            set_setting("football_data_token", api_token)

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
        set_setting("reminders_enabled", bool(form.reminders_enabled.data))

        apply_mail_settings()
        from mail_helpers import apply_vapid_settings
        apply_vapid_settings()

        new_exact = int(form.points_exact.data or 4)
        new_diff = int(form.points_diff.data or 3)
        new_tendency = int(form.points_tendency.data or 2)

        if old_exact != new_exact or old_diff != new_diff or old_tendency != new_tendency:
            recalculate_all_points()
            flash("✅ Einstellungen gespeichert und Punkte neu berechnet.", "success")
        else:
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
    api_missing = not (form.football_data_token.data)
    vapid_missing = not (form.vapid_public.data) or not (form.vapid_private.data)
    pts_missing = not (form.points_exact.data) or not (form.points_diff.data) or not (form.points_tendency.data)
    pot_missing = not (form.pot_amount.data) or form.pot_amount.data == 0

    return render_template("admin/settings.html", form=form,
                           mail_missing=mail_missing, api_missing=api_missing,
                           vapid_missing=vapid_missing, pts_missing=pts_missing,
                           pot_missing=pot_missing)


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
    if request.method == "POST":
        do_archive = request.form.get("do_archive") == "1"
        do_delete_schedule = request.form.get("do_delete_schedule") == "1"
        do_delete_specials = request.form.get("do_delete_specials") == "1"
        do_reset_bots = request.form.get("do_reset_bots") == "1"
        do_reset_badges = request.form.get("do_reset_badges") == "1"
        do_reset_paid = request.form.get("do_reset_paid") == "1"
        new_season_label = (request.form.get("new_season_label", "") or "2025/26").strip()

        season_code = get_setting("season", "2025")

        if do_archive:
            rows = db.session.query(
                User.id.label("user_id"),
                func.coalesce(func.sum(Prediction.points), 0).label("points"),
                func.coalesce(func.sum(func.case((Prediction.points == 4, 1), else_=0)), 0).label("exact_count"),
            ).outerjoin(Prediction, Prediction.user_id == User.id).group_by(User.id).all()

            for r in rows:
                existing = SeasonArchive.query.filter_by(user_id=r.user_id, season=season_code).first()
                if existing:
                    existing.points = int(r.points or 0)
                    existing.exact_count = int(r.exact_count or 0)
                else:
                    db.session.add(SeasonArchive(
                        user_id=r.user_id, season=season_code,
                        points=int(r.points or 0), exact_count=int(r.exact_count or 0),
                        rank=0, diff_count=0,
                    ))
            db.session.commit()
            flash("✅ Ewige Tabelle aktualisiert.", "success")

        if do_delete_schedule:
            MatchdayWinner.query.filter_by(season=season_code).delete(synchronize_session=False)
            Comment.query.delete(synchronize_session=False)
            Prediction.query.delete(synchronize_session=False)
            Match.query.delete(synchronize_session=False)
            db.session.commit()
            flash("🗑️ Spielplan gelöscht.", "success")

        if do_delete_specials:
            SpecialPrediction.query.delete(synchronize_session=False)
            SpecialQuestion.query.delete(synchronize_session=False)
            db.session.commit()
            flash("🗑️ Sonderfragen gelöscht.", "success")

        if do_reset_bots:
            bot_ids = [u.id for u in User.query.filter(User.email.like("%@bot.local")).all()]
            if bot_ids:
                Prediction.query.filter(Prediction.user_id.in_(bot_ids)).delete(synchronize_session=False)
                db.session.commit()
            flash("🤖 Bot-Tipps zurückgesetzt.", "success")

        if do_reset_badges:
            from models import UserBadge
            UserBadge.query.delete(synchronize_session=False)
            db.session.commit()
            flash("🏅 Badges zurückgesetzt.", "success")

        if do_reset_paid:
            User.query.filter(~User.email.like("%@bot.local")).update({
                "has_paid": False, "paid_at": None, "paid_note": None
            }, synchronize_session=False)
            db.session.commit()
            flash("💰 Bezahlstatus zurückgesetzt.", "success")

        # ----- Competition aktualisieren -----
        # Wichtig: "competitions.code" ist UNIQUE. Wir können also nicht
        # einfach einen zweiten BL1 anlegen, sondern updaten den bestehenden
        # Eintrag mit dem neuen Saison-Label.
        try:
            existing = Competition.query.filter_by(code="BL1").first()
            if existing:
                existing.name = f"Bundesliga {new_season_label}"
                existing.season = new_season_label
                existing.is_active = True
                existing.external_id = None
            else:
                db.session.add(Competition(
                    code="BL1", name=f"Bundesliga {new_season_label}",
                    season=new_season_label, matchdays=34, teams_count=18,
                    is_active=True, external_id=None,
                ))
            # Andere Competitions deaktivieren (falls vorhanden)
            Competition.query.filter(Competition.code != "BL1").update(
                {"is_active": False}, synchronize_session=False
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Saison-Wechsel fehlgeschlagen")
            flash(f"❌ Saison konnte nicht angelegt werden: {e}", "danger")
            return redirect(url_for("admin.new_season"), code=303)

        set_setting("season", new_season_label)
        set_setting("current_season", new_season_label)

        # Caches invalidieren (Rangliste etc.)
        try:
            from cache import invalidate_leaderboard
            invalidate_leaderboard()
        except Exception:
            pass

        flash(f"🏁 Neue Saison '{new_season_label}' gestartet.", "success")
        return redirect(url_for("admin.new_season"), code=303)

    return render_template("admin/new_season.html")
