"""Admin: Badges."""
from datetime import datetime, timezone
import json as _json

from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user
from sqlalchemy import func

from extensions import db
from models import (
    User, Team, Match, Prediction, Comment, Badge, UserBadge,
    SpecialQuestion, SpecialPrediction, Prize, MatchdayWinner,
)
from forms import AdminUserForm, PrizeForm, BadgeForm, SpecialQuestionForm
from scoring import compute_pot_summary
from stats import evaluate_special_predictions
from badges import check_and_award_badges, award_badge, revoke_badge
from competition_helpers import get_active_competition, filter_competition_scoped
from audit_log import log_admin_action

# ============================================================ Badges -
def _admin_badges():
    all_badges = Badge.query.order_by(Badge.created_at.desc()).all()
    award_counts = dict(
        db.session.query(UserBadge.badge_id, func.count(UserBadge.id))
        .group_by(UserBadge.badge_id).all()
    )
    return render_template("admin/badges.html", badges=all_badges, award_counts=award_counts)


def _admin_badge_form(badge_id=None):
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


def _admin_badge_delete(badge_id):
    badge = db.get_or_404(Badge, badge_id)
    name = badge.name
    UserBadge.query.filter_by(badge_id=badge.id).delete()
    db.session.delete(badge)
    db.session.commit()
    flash(f"Badge '{name}' gelöscht.", "info")
    return redirect(url_for("admin.badges"))


def _admin_badge_award(badge_id):
    badge = db.get_or_404(Badge, badge_id)
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


def _admin_badge_recheck():
    check_and_award_badges()
    flash("Alle Badge-Regeln neu geprüft.", "success")
    return redirect(url_for("admin.badges"))
