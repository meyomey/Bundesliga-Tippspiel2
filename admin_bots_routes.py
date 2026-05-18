"""Admin-Routes für KI-Bot-Verwaltung."""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import User, Match, Prediction

BOT_NAMES = ["RookieBot", "AmateurBot", "ProBot", "ExpertBot", "MasterBot"]
BOT_LEVELS = {"RookieBot": 1, "AmateurBot": 2, "ProBot": 3, "ExpertBot": 4, "MasterBot": 5}


def _get_bots():
    return User.query.filter(User.email.like("%@bot.local")).all()


def _current_matchday():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    next_match = Match.query.filter(Match.status == "scheduled").order_by(Match.kickoff).first()
    if next_match:
        return next_match.matchday
    last = Match.query.filter(Match.status == "finished").order_by(Match.matchday.desc()).first()
    return last.matchday if last else 1


def _get_bot_active_status(bot_name):
    """True, wenn Bot aktiv ist (tolerant gegen str/bool)."""
    from scoring import get_setting, _truthy_setting
    return _truthy_setting(get_setting(f"bot_active_{bot_name}", True), default=True)


def _admin_bots_view():
    # 🤖 Lazy-Init triggern: legt alle vordefinierten Bot-User an, falls sie fehlen
    try:
        from ai_opponent import get_ai_manager
        get_ai_manager()
    except Exception as e:
        from flask import current_app
        current_app.logger.warning(f"AIManager-Init fehlgeschlagen: {e}")

    bots = _get_bots()
    matchday = _current_matchday()
    bot_ids = [b.id for b in bots]
    bot_map = {b.id: b for b in bots}

    # Welche der vordefinierten Bots fehlen noch in der DB?
    existing_names = {b.username for b in bots}
    missing_bots = [name for name in BOT_NAMES if name not in existing_names]

    # 🔥 PERFORMANCE: Bulk-Query statt N+1 (1 Query statt 15+)
    from sqlalchemy import func, case
    from scoring import get_setting
    points_exact = get_setting("points_exact", 4)

    stats_rows = db.session.query(
        Prediction.user_id,
        func.count(Prediction.id).label("tips"),
        func.sum(case((Prediction.points >= points_exact, 1), else_=0)).label("exact"),
        func.coalesce(func.sum(Prediction.points), 0).label("pts"),
    ).filter(Prediction.user_id.in_(bot_ids)).group_by(Prediction.user_id).all()
    stats_map = {s.user_id: s for s in stats_rows}

    bot_list = []
    for b in bots:
        s = stats_map.get(b.id)
        from scoring import _truthy_setting
        active = _truthy_setting(get_setting(f"bot_active_{b.username}", True), default=True)
        bot_list.append({
            "user": b,
            "name": b.username,
            "level": BOT_LEVELS.get(b.username, 1),
            "tips": s.tips if s else 0,
            "exact": int(s.exact or 0) if s else 0,
            "points": int(s.pts or 0) if s else 0,
            "active": active,
        })
    bot_list.sort(key=lambda x: x["points"], reverse=True)
    total_tips = sum(b["tips"] for b in bot_list)
    open_matches = Match.query.filter_by(status="scheduled").count()
    active_count = sum(1 for b in bot_list if b["active"])
    return render_template(
        "admin/bots.html", bots=bot_list, current_matchday=matchday,
        total_tips=total_tips, open_matches=open_matches, active_count=active_count,
        bot_names=BOT_NAMES, missing_bots=missing_bots,
    )


def _admin_bots_tip_all():
    from ai_opponent import ai_manager
    matchday = int(request.form.get("matchday", _current_matchday()))
    overwrite = request.form.get("overwrite") == "1"
    try:
        results = ai_manager.tip_all_matches(matchday=matchday, overwrite=overwrite)
        tipped = sum(r.get("tipped", 0) for r in results.values())
        skipped = sum(r.get("skipped", 0) for r in results.values())
        if tipped > 0:
            flash(f"✅ {tipped} Bot-Tipps für Spieltag {matchday} abgegeben", "success")
        else:
            flash(f"ℹ️ Keine neuen Tipps für Spieltag {matchday}.", "info")
    except Exception as e:
        flash(f"❌ Fehler beim Tippen: {e}", "error")
    return redirect(url_for("admin.admin_bots"))


def _admin_bots_tip_single():
    from ai_opponent import ai_manager
    bot_id = int(request.form.get("bot_id"))
    matchday = int(request.form.get("matchday", _current_matchday()))
    bot_user = db.session.get(User, bot_id)
    if not bot_user or "@bot.local" not in bot_user.email:
        flash("❌ Bot nicht gefunden.", "error")
        return redirect(url_for("admin.admin_bots"))
    bot_name = bot_user.username
    try:
        opponent = ai_manager.get_opponent(bot_name)
        if opponent is None:
            flash(f"❌ KI-Opponent '{bot_name}' nicht gefunden.", "error")
            return redirect(url_for("admin.admin_bots"))
        matches = Match.query.filter_by(matchday=matchday, status="scheduled").all()
        tipped = 0
        for match in matches:
            existing = Prediction.query.filter_by(user_id=bot_id, match_id=match.id).first()
            if not existing:
                home_tip, away_tip = opponent.get_tip(match)
                db.session.add(Prediction(
                    user_id=bot_id, match_id=match.id,
                    home_tip=home_tip, away_tip=away_tip,
                    joker=False, points=0,
                ))
                tipped += 1
        db.session.commit()
        flash(f"✅ {bot_name}: {tipped} Tipps für Spieltag {matchday} abgegeben.", "success")
    except Exception as e:
        flash(f"❌ Fehler: {e}", "error")
    return redirect(url_for("admin.admin_bots"))


def _admin_bots_reset():
    bot_id = int(request.form.get("bot_id"))
    matchday = int(request.form.get("matchday", _current_matchday()))
    bot_user = db.session.get(User, bot_id)
    if not bot_user or "@bot.local" not in bot_user.email:
        flash("❌ Bot nicht gefunden.", "error")
        return redirect(url_for("admin.admin_bots"))
    match_ids = [m.id for m in Match.query.filter_by(matchday=matchday).all()]
    deleted = Prediction.query.filter(
        Prediction.user_id == bot_id,
        Prediction.match_id.in_(match_ids),
    ).delete(synchronize_session=False)
    db.session.commit()
    flash(f"🗑️ {deleted} Tipps von {bot_user.username} für Spieltag {matchday} gelöscht.", "warning")
    return redirect(url_for("admin.admin_bots"))


def _admin_bots_toggle():
    from utils import get_setting, set_setting
    bot_name = request.form.get("bot_name", "").strip()
    if bot_name not in BOT_NAMES:
        flash("❌ Unbekannter Bot.", "error")
        return redirect(url_for("admin.admin_bots"))
    from scoring import _truthy_setting
    key = f"bot_active_{bot_name}"
    is_currently_active = _truthy_setting(get_setting(key, True), default=True)
    new_val = "0" if is_currently_active else "1"
    set_setting(key, new_val)
    status = "aktiviert" if new_val == "1" else "deaktiviert"

    # Cache leeren, damit der Bot SOFORT aus der Rangliste verschwindet
    # (bzw. wieder erscheint).
    try:
        from cache import invalidate_leaderboard
        invalidate_leaderboard()
    except Exception:
        pass

    flash(f"🤖 {bot_name} {status}.", "success")
    return redirect(url_for("admin.admin_bots"))


# ------------------------------------------------------------------ Seed Bots -
def _admin_bots_seed():
    """Erzeugt fehlende Standard-Bots in der DB (idempotent).

    Nützlich, wenn ein Bot manuell gelöscht wurde oder wenn der erste
    Aufruf von /admin/bots noch keine Bots gezeigt hat.
    """
    try:
        from ai_opponent import get_ai_manager
        # Reset des Caches, damit alle Bots neu geladen werden
        import ai_opponent
        ai_opponent._ai_manager = None
        get_ai_manager()  # legt fehlende Bots an
        bots = _get_bots()
        flash(
            f"✅ {len(bots)} Bots verfügbar: {', '.join(b.username for b in bots)}",
            "success",
        )
    except Exception as e:
        flash(f"❌ Bot-Seeding fehlgeschlagen: {e}", "error")
    return redirect(url_for("admin.admin_bots"))


def _admin_bots_create_one():
    """Legt einen einzelnen vordefinierten Bot an (per bot_name)."""
    import random
    bot_name = (request.form.get("bot_name") or "").strip()
    if bot_name not in BOT_NAMES:
        flash(f"❌ Unbekannter Bot: '{bot_name}'. Erlaubt: {', '.join(BOT_NAMES)}", "error")
        return redirect(url_for("admin.admin_bots"))

    existing = User.query.filter_by(username=bot_name).first()
    if existing:
        flash(f"ℹ️ Bot '{bot_name}' existiert bereits (ID {existing.id}).", "info")
        return redirect(url_for("admin.admin_bots"))

    bot = User(
        username=bot_name,
        email=f"{bot_name.lower()}@bot.local",
        is_admin=False,
    )
    bot.set_password("".join(random.choices("0123456789abcdef", k=32)))
    try:
        db.session.add(bot)
        db.session.commit()
        # Cache invalidieren
        import ai_opponent
        ai_opponent._ai_manager = None
        flash(f"✅ Bot '{bot_name}' angelegt (ID {bot.id}).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Konnte Bot nicht anlegen: {e}", "error")
    return redirect(url_for("admin.admin_bots"))
