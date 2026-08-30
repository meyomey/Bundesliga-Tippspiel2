"""Admin: offene Tipps und Reminder."""
from flask import flash, redirect, render_template, request, url_for

from audit_log import log_admin_action
from competition_helpers import active_match_query, active_matchdays
from extensions import db
from models import Match, Prediction, User
from stats import get_current_matchday


def _admin_open_tips_view():
    from scoring import filter_active_users
    from notification_center import send_user_notification

    matchday = request.values.get("matchday", get_current_matchday(), type=int)
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff.asc(), Match.id.asc()).all()
    matchdays = active_matchdays()
    open_matches = [m for m in matches if m.is_open()]
    match_ids = [m.id for m in matches]

    users = filter_active_users(User.query.filter(~User.email.like("%@bot.local")).order_by(User.username.asc()).all())
    user_ids = [u.id for u in users]
    preds = []
    if match_ids and user_ids:
        preds = Prediction.query.filter(
            Prediction.user_id.in_(user_ids),
            Prediction.match_id.in_(match_ids),
        ).all()
    pred_map = {(p.user_id, p.match_id): p for p in preds}

    rows = []
    total_missing = 0
    for u in users:
        missing = [m for m in open_matches if (u.id, m.id) not in pred_map]
        tipped = len([m for m in matches if (u.id, m.id) in pred_map])
        total_missing += len(missing)
        rows.append({
            "user": u,
            "missing": missing,
            "missing_count": len(missing),
            "tipped": tipped,
            "total": len(matches),
            "completion_pct": round((tipped / len(matches)) * 100) if matches else 0,
        })
    rows.sort(key=lambda r: (-r["missing_count"], r["user"].username.lower()))

    if request.method == "POST":
        sent_users = 0
        channel_totals = {"email": 0, "push": 0, "telegram": 0, "whatsapp": 0}
        for row in rows:
            if not row["missing"]:
                continue
            match = row["missing"][0]
            result = send_user_notification(row["user"], match)
            if any(result.values()):
                sent_users += 1
            for channel, ok in result.items():
                if ok:
                    channel_totals[channel] += 1
        log_admin_action(
            "open_tips_reminder",
            "matchday", matchday,
            f"Reminder an offene Tipper fuer Spieltag {matchday}",
            {"users": sent_users, "channels": channel_totals, "total_missing": total_missing},
        )
        flash(f"🔔 Reminder gesendet an {sent_users} Spieler. Kanaele: {channel_totals}", "success" if sent_users else "info")
        return redirect(url_for("admin.admin_open_tips", matchday=matchday), code=303)

    return render_template(
        "admin/open_tips.html",
        rows=rows,
        matches=matches,
        open_matches=open_matches,
        matchdays=matchdays,
        current_md=matchday,
        total_missing=total_missing,
    )
