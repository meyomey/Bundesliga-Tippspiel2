"""Admin: Userverwaltung."""
from datetime import datetime, timezone
import json as _json

from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from extensions import db
from models import (
    User, Team, Match, Prediction, Comment, Badge, UserBadge,
    SpecialQuestion, SpecialPrediction, Prize, MatchdayWinner,
)
from forms import AdminUserForm, PrizeForm, BadgeForm, SpecialQuestionForm
from scoring import compute_pot_summary, is_pot_participant, is_bot_user, is_admin_only_user
from stats import evaluate_special_predictions
from badges import check_and_award_badges, award_badge, revoke_badge
from competition_helpers import get_active_competition, filter_competition_scoped
from audit_log import log_admin_action, snapshot_model
from cache import invalidate_leaderboard

def _admin_users():
    """Spielerverwaltung: alle Konten anzeigen.

    Vorher wurden nur 25 Einträge pro Seite geladen, aber die Vorlage hatte keine
    sichtbare Pagination. Dadurch konnten User in Ranglisten auftauchen, in der
    Spielerverwaltung aber scheinbar fehlen.
    """
    all_users = User.query.order_by(User.username.asc()).all()
    user_summary = {
        "accounts": len(all_users),
        "players": sum(1 for u in all_users if is_pot_participant(u)),
        "bots": sum(1 for u in all_users if is_bot_user(u)),
        "admin_only": sum(1 for u in all_users if is_admin_only_user(u)),
    }
    user_filter = (request.args.get("filter") or "all").strip().lower()
    valid_filters = {"all", "players", "bots", "admin"}
    if user_filter not in valid_filters:
        user_filter = "all"

    if user_filter == "players":
        visible_users = [u for u in all_users if is_pot_participant(u)]
    elif user_filter == "bots":
        visible_users = [u for u in all_users if is_bot_user(u)]
    elif user_filter == "admin":
        visible_users = [u for u in all_users if is_admin_only_user(u)]
    else:
        visible_users = all_users

    pot = compute_pot_summary()
    return render_template(
        "admin/users.html",
        users=visible_users,
        user_summary=user_summary,
        user_filter=user_filter,
        filtered_count=len(visible_users),
        total_users=len(all_users),
        pot=pot,
        pagination=None,
        is_pot_participant=is_pot_participant,
    )


def _admin_user_edit(user_id):
    u = db.get_or_404(User, user_id)
    audited_attrs = [
        "username", "full_name", "show_full_name", "email", "phone",
        "favorite_team_id", "is_admin", "has_paid", "paid_note", "paid_at",
    ]
    before_snapshot = snapshot_model(u, audited_attrs)
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
                return render_template("admin/user_edit.html", user=u, form=form, is_pot_participant=is_pot_participant)
        new_email = (form.email.data or "").strip().lower()
        if new_email != u.email:
            other = User.query.filter(User.email == new_email, User.id != u.id).first()
            if other:
                flash(f"E-Mail '{new_email}' ist bereits vergeben.", "danger")
                return render_template("admin/user_edit.html", user=u, form=form, is_pot_participant=is_pot_participant)

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
        if is_pot_participant(u):
            u.has_paid = form.has_paid.data
            u.paid_note = (form.paid_note.data or "").strip() or None
        else:
            u.has_paid = False
            u.paid_note = None
        if u.has_paid and not was_paid:
            u.paid_at = datetime.now(timezone.utc)
        elif not u.has_paid:
            u.paid_at = None

        if form.new_password.data:
            u.set_password(form.new_password.data)

        after_snapshot = snapshot_model(u, audited_attrs)
        extra_meta = {"password_changed": True} if form.new_password.data else None
        db.session.commit()
        invalidate_leaderboard()
        log_admin_action("user_update", "user", u.id, f"Spieler '{u.username}' aktualisiert",
                         metadata=extra_meta, before=before_snapshot, after=after_snapshot)
        flash(f"Spieler '{u.username}' aktualisiert.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_edit.html", user=u, form=form, is_pot_participant=is_pot_participant)


def _admin_toggle_paid(user_id):
    u = db.get_or_404(User, user_id)
    if not is_pot_participant(u):
        u.has_paid = False
        u.paid_at = None
        u.paid_note = None
        db.session.commit()
        invalidate_leaderboard()
        flash(f"{u.username} ist ein reines Admin-Konto und zählt nicht als zahlender Mitspieler.", "info")
        return redirect(url_for("admin.users"))
    u.has_paid = not u.has_paid
    if u.has_paid:
        u.paid_at = datetime.now(timezone.utc)
    else:
        u.paid_at = None
    db.session.commit()
    invalidate_leaderboard()
    log_admin_action("user_toggle_paid", "user", u.id, f"{u.username}: paid={u.has_paid}")
    flash(f"{u.username}: {'✅ Bezahlt' if u.has_paid else '❌ Removed'}.", "success")
    return redirect(url_for("admin.users"))


def _admin_toggle_admin(user_id):
    u = db.get_or_404(User, user_id)
    if u.id == current_user.id:
        flash("Du kannst dich nicht selbst entfernen.", "warning")
    else:
        u.is_admin = not u.is_admin
        db.session.commit()
        invalidate_leaderboard()
        log_admin_action("user_toggle_admin", "user", u.id, f"{u.username}: admin={u.is_admin}")
        flash(f"{u.username} ist jetzt {'Admin' if u.is_admin else 'normaler User'}.", "success")
    return redirect(url_for("admin.users"))


def _admin_delete_user(user_id):
    u = db.get_or_404(User, user_id)
    if u.id == current_user.id:
        flash("Du kannst dich nicht selbst löschen.", "warning")
    else:
        username = u.username
        uid = u.id
        db.session.delete(u)
        db.session.commit()
        invalidate_leaderboard()
        log_admin_action("user_delete", "user", uid, f"User {username} gelöscht")
        flash(f"User {username} gelöscht.", "info")
    return redirect(url_for("admin.users"))
