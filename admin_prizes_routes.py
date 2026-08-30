"""Admin: Preise/Pott."""
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
from scoring import compute_pot_summary
from stats import evaluate_special_predictions
from badges import check_and_award_badges, award_badge, revoke_badge
from competition_helpers import get_active_competition, filter_competition_scoped
from audit_log import log_admin_action

# ============================================================ Prizes -
def _admin_prizes():
    prize_q = filter_competition_scoped(Prize.query, Prize)
    all_prizes = prize_q.order_by(Prize.sort_order.asc(), Prize.rank.asc()).all()
    pot = compute_pot_summary()
    return render_template("admin/prizes.html", prizes=all_prizes, pot=pot)


def _admin_prize_form(prize_id=None):
    prize = db.session.get(Prize, prize_id) if prize_id else None
    form = PrizeForm(obj=prize)
    if form.validate_on_submit():
        if not prize:
            prize = Prize()
            comp = get_active_competition()
            prize.competition_id = comp.id if comp else None
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


def _admin_prize_delete(prize_id):
    prize = db.get_or_404(Prize, prize_id)
    title = prize.title
    db.session.delete(prize)
    db.session.commit()
    flash(f"Preis '{title}' gelöscht.", "info")
    return redirect(url_for("admin.admin_prizes"))
