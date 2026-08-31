"""Ausgelagerte Main-Route-Logik: Profil."""
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from routes_main import main_bp  # Blueprint-Registrierung statt Lazy-Wrapper in routes_main.py

from extensions import db
from models import Match, MatchdayWinner, Prediction, Team, User, UserBadge
from forms import ProfileForm
from scoring import compute_pot_summary, get_setting
from stats import get_user_insights, get_user_trend
from avatars import save_avatar
from competition_helpers import filter_competition_scoped, get_active_competition

def _compute_profile_stats(user):
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=user.id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    user_preds = q.all()
    md_wins = filter_competition_scoped(
        MatchdayWinner.query.filter_by(user_id=user.id), MatchdayWinner
    ).count()
    return {
        "total_tips": len(user_preds),
        "total_points": sum(p.points or 0 for p in user_preds),
        "exact": sum(1 for p in user_preds if p.points and p.points >= get_setting("points_exact", 4)),
        "joker_used": sum(1 for p in user_preds if p.joker),
        "md_wins": md_wins,
    }

def _compute_form_curve(user):
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=user.id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    md_points = {}
    for p in q.all():
        if p.match and p.match.status == "finished":
            md_points.setdefault(p.match.matchday, 0)
            md_points[p.match.matchday] += p.points or 0
    return sorted(md_points.items())

@main_bp.route("/profil", methods=["GET", "POST"], endpoint="profile")
@login_required
def _profile():
    form = ProfileForm(obj=current_user)
    teams = Team.query.order_by(Team.name).all()
    form.favorite_team_id.choices = [(0, "— kein Lieblingsverein —")] + [
        (t.id, t.name) for t in teams
    ]
    if request.method == "GET":
        form.favorite_team_id.data = current_user.favorite_team_id or 0
        form.default_tip_view.data = current_user.default_tip_view or "normal"

    # Telegram-Verknüpfung trennen
    if request.method == "POST" and request.form.get("telegram_unlink") == "1":
        current_user.phone = None
        db.session.commit()
        flash("✅ Telegram-Verknüpfung aufgehoben.", "info")
        return redirect(url_for("main.profile"))

    if form.validate_on_submit():
        new_username = (form.username.data or "").strip()
        if new_username and new_username != current_user.username:
            existing = User.query.filter(
                User.username == new_username,
                User.id != current_user.id,
            ).first()
            if existing:
                flash(f"Spielername '{new_username}' ist bereits vergeben.", "danger")
            else:
                current_user.username = new_username

        current_user.full_name = (form.full_name.data or "").strip() or None
        # Private Tipprunde: eingetragene volle Namen sind innerhalb der Runde sichtbar.
        current_user.show_full_name = True
        current_user.phone = (form.phone.data or "").strip() or None
        current_user.whatsapp_phone = (form.whatsapp_phone.data or "").strip() or None
        current_user.whatsapp_apikey = (form.whatsapp_apikey.data or "").strip() or None
        default_tip_view = form.default_tip_view.data if form.default_tip_view.data in ("normal", "quick") else "normal"
        current_user.default_tip_view = default_tip_view
        if request.form.get("notification_form") == "1":
            current_user.notify_enabled = bool(form.notify_enabled.data)
            current_user.notify_email = bool(form.notify_email.data)
            current_user.notify_push = bool(form.notify_push.data)
            current_user.notify_telegram = bool(form.notify_telegram.data)
            current_user.notify_whatsapp = bool(form.notify_whatsapp.data)
            current_user.notify_hours_before = form.notify_hours_before.data or 1
            current_user.notify_only_favorite = bool(form.notify_only_favorite.data)
        current_user.favorite_team_id = form.favorite_team_id.data or None

        try:
            avatar_filename, avatar_error = save_avatar(form.avatar.data, current_user.id)
            if avatar_error:
                flash(f"Avatar nicht übernommen: {avatar_error}", "warning")
            elif avatar_filename:
                current_user.avatar = avatar_filename
        except Exception as e:
            current_app.logger.exception("Unerwarteter Fehler beim Avatar-Upload")
            flash(f"Avatar-Upload fehlgeschlagen: {e}", "danger")

        try:
            db.session.commit()
            flash("Profil gespeichert.", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("DB-Fehler beim Profil speichern")
            flash(f"Fehler beim Speichern: {e}", "danger")
        return redirect(url_for("main.profile"))

    if request.method == "POST":
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{field}: {err}", "danger")

    stats = _compute_profile_stats(current_user)
    form_curve = _compute_form_curve(current_user)
    badges = UserBadge.query.filter_by(user_id=current_user.id).all()
    pot = compute_pot_summary()
    # Telegram-Token für Verknüpfung
    telegram_token = None
    if not current_user.phone or not current_user.phone.startswith("tg:"):
        try:
            from telegram_bot import generate_telegram_token
            telegram_token = generate_telegram_token(current_user.id)
        except Exception:
            pass

    insights = get_user_insights(current_user)
    trend = get_user_trend(current_user.id)
    return render_template(
        "profile.html", form=form, stats=stats, badges=badges,
        form_curve=form_curve, pot=pot,
        insights=insights, trend=trend,
        telegram_token=telegram_token,
        telegram_bot_username=get_setting("telegram_bot_username", ""),
    )

