"""Ausgelagerte Main-Route-Logik: Statistiken, Recap, Live."""
from datetime import datetime, timedelta, timezone

from flask import render_template
from flask_login import current_user, login_required

from routes_main import main_bp  # Blueprint-Registrierung statt Lazy-Wrapper in routes_main.py
from sqlalchemy import func

from extensions import db
from models import Match, MatchdayWinner, Prediction, Prize, User, UserBadge
from scoring import compute_pot_summary, filter_active_users, get_leaderboard, get_setting
from stats import (
    compute_live_standings,
    get_eternal_table,
    get_matchday_preview,
    get_matchday_recap,
    get_user_insights,
    get_user_trend,
    get_current_matchday,
)
from sync import fetch_live_standings
from competition_helpers import (
    active_matchdays,
    filter_competition_scoped,
    filter_matches_for_active_competition,
    get_active_competition,
)

@main_bp.route("/preview", endpoint="matchday_preview")
@main_bp.route("/preview/<int:matchday>", endpoint="matchday_preview")
@login_required
def _matchday_preview(matchday=None):
    if matchday is None:
        matchday = get_current_matchday()
    data = get_matchday_preview(matchday)
    return render_template(
        "matchday_preview.html",
        preview=data,
        matchday=matchday,
        matchdays=active_matchdays(),
    )

@main_bp.route("/spieltag-recap", endpoint="matchday_recap")
@main_bp.route("/spieltag-recap/<int:matchday>", endpoint="matchday_recap")
@login_required
def _matchday_recap(matchday=None):
    data = get_matchday_recap(matchday)
    return render_template(
        "matchday_recap.html",
        recap=data,
        matchday=data["matchday"],
        matchdays=active_matchdays(),
    )


# ================================================ Sondertipps -

@main_bp.route("/ewige-tabelle", endpoint="eternal_table")
@login_required
def _eternal_table():
    rows = get_eternal_table()
    return render_template("eternal.html", rows=rows)


# ================================================ Saison-Recap -
# ------------------------------------------------------------------
# 📊 Erweitertes Statistik-Dashboard
# ------------------------------------------------------------------

def _build_rank_progression_data(current_user_id):
    """Rangverlauf aller aktiven Spieler nach beendeten Spieltagen.

    Basis sind Match-Punkte im aktiven Wettbewerb. Sonderfragen werden bewusst
    nicht einberechnet, weil sie keine eindeutige Spieltags-Zeitachse haben.
    Deaktivierte Bots und reine Admin-Konten werden herausgefiltert.
    """
    from scoring import classify_prediction

    comp = get_active_competition()
    users = filter_active_users(User.query.order_by(User.username.asc()).all())
    if not users:
        return [], [], 0

    user_ids = [u.id for u in users]
    users_by_id = {u.id: u for u in users}

    md_q = db.session.query(Match.matchday).filter(Match.status == "finished")
    if comp:
        md_q = md_q.filter(Match.competition_id == comp.id)
    matchdays = [row[0] for row in md_q.distinct().order_by(Match.matchday.asc()).all()]
    if not matchdays:
        return [], [], len(users)

    pred_q = Prediction.query.join(Match).filter(
        Prediction.user_id.in_(user_ids),
        Match.status == "finished",
        Match.matchday.in_(matchdays),
    )
    if comp:
        pred_q = pred_q.filter(Match.competition_id == comp.id)
    preds = pred_q.options(db.joinedload(Prediction.match)).all()

    preds_by_md = {}
    for pred in preds:
        preds_by_md.setdefault(pred.match.matchday, []).append(pred)

    aggregates = {
        uid: {"points": 0, "exact": 0, "diff": 0, "tendency": 0, "tips": 0}
        for uid in user_ids
    }
    rank_series = {uid: [] for uid in user_ids}

    for md in matchdays:
        for pred in preds_by_md.get(md, []):
            a = aggregates[pred.user_id]
            a["points"] += pred.points or 0
            a["tips"] += 1
            kind = classify_prediction(pred, pred.match)
            if kind in ("exact", "diff", "tendency"):
                a[kind] += 1

        sorted_users = sorted(
            users,
            key=lambda u: (
                -aggregates[u.id]["points"],
                -aggregates[u.id]["exact"],
                -aggregates[u.id]["diff"],
                -aggregates[u.id]["tendency"],
                -aggregates[u.id]["tips"],
                u.username.lower(),
            ),
        )
        for rank, u in enumerate(sorted_users, 1):
            rank_series[u.id].append(rank)

    leaderboard_order = [r["user"] for r in get_leaderboard() if r["user"].id in users_by_id]
    ordered_ids = [u.id for u in leaderboard_order]
    ordered_ids.extend(uid for uid in user_ids if uid not in ordered_ids)

    palette = [
        "#14b8a6", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#10b981",
        "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1", "#64748b",
    ]
    initially_visible = set(ordered_ids[:5])
    initially_visible.add(current_user_id)

    datasets = []
    for i, uid in enumerate(ordered_ids):
        u = users_by_id[uid]
        is_me = uid == current_user_id
        color = "#14b8a6" if is_me else palette[i % len(palette)]
        datasets.append({
            "label": u.username,
            "data": rank_series[uid],
            "borderColor": color,
            "backgroundColor": color,
            "tension": 0.22,
            "pointRadius": 3 if is_me else 2,
            "borderWidth": 3 if is_me else 2,
            "hidden": uid not in initially_visible,
            "isMe": is_me,
        })

    labels = [f"ST {md}" for md in matchdays]
    return labels, datasets, len(users)

@main_bp.route("/stats", endpoint="stats_dashboard")
@login_required
def _stats_dashboard():
    """Umfassendes Statistik-Dashboard mit Diagrammen.

    Die Auswertungen sind bewusst auf den aktiven Wettbewerb begrenzt und
    verwenden bei Bot-Vergleichen nur aktivierte Bots. So tauchen deaktivierte
    Test-/KI-Gegner nicht mehr in der Statistik auf.
    """
    user = current_user
    comp = get_active_competition()

    # 1. Punkte-Verlauf (letzte 8 Spieltage)
    trend = get_user_trend(user.id, last_n_matchdays=8)
    sparkline_mds = trend.get("recent_matchdays", [])
    sparkline_pts = trend.get("sparkline", [])

    # 2. Tipp-Verteilung (Heim/X/Auswärts)
    from scoring import classify_prediction
    from stats import get_user_insights, get_user_stats_20
    insights = get_user_insights(user)
    stats20 = get_user_stats_20(user)

    # 3. Spieltagspunkte (aktive Saison / aktiver Wettbewerb)
    preds_q = Prediction.query.filter_by(user_id=user.id).join(Match)
    if comp:
        preds_q = preds_q.filter(Match.competition_id == comp.id)
    preds = preds_q.options(
        db.joinedload(Prediction.match).joinedload(Match.home_team),
        db.joinedload(Prediction.match).joinedload(Match.away_team),
    ).all()
    finished_preds = [p for p in preds if p.match and p.match.status == "finished"]

    md_points_all = {}
    for p in finished_preds:
        md = p.match.matchday
        md_points_all[md] = md_points_all.get(md, 0) + (p.points or 0)
    md_labels_all = [str(md) for md in sorted(md_points_all.keys())]
    md_data_all = [md_points_all[md] for md in sorted(md_points_all.keys())]

    # 4. Genauigkeit pro Spieltag
    md_accuracy = {}
    for p in finished_preds:
        md = p.match.matchday
        if md not in md_accuracy:
            md_accuracy[md] = {"exact": 0, "diff": 0, "tendency": 0, "wrong": 0}
        cls = classify_prediction(p, p.match)
        if cls in md_accuracy[md]:
            md_accuracy[md][cls] += 1

    acc_labels = []
    acc_exact = []
    acc_diff = []
    acc_tendency = []
    acc_wrong = []
    for md in sorted(md_accuracy.keys()):
        acc_labels.append(str(md))
        d = md_accuracy[md]
        total = d["exact"] + d["diff"] + d["tendency"] + d["wrong"]
        acc_exact.append(round(d["exact"] / total * 100, 1) if total else 0)
        acc_diff.append(round(d["diff"] / total * 100, 1) if total else 0)
        acc_tendency.append(round(d["tendency"] / total * 100, 1) if total else 0)
        acc_wrong.append(round(d["wrong"] / total * 100, 1) if total else 0)

    # 5. Beliebteste Tipps
    tip_counts = {}
    for p in finished_preds:
        key = f"{p.home_tip}:{p.away_tip}"
        tip_counts[key] = tip_counts.get(key, 0) + 1
    top_tips = sorted(tip_counts.items(), key=lambda x: (-x[1], x[0]))[:8]
    top_tip_labels = [t[0] for t in top_tips]
    top_tip_data = [t[1] for t in top_tips]

    # 6. Joker-Statistik
    joker_preds = [p for p in finished_preds if p.joker]
    joker_success = sum(1 for p in joker_preds if p.points and p.points > 0)
    joker_fail = len(joker_preds) - joker_success
    joker_avg = round(sum(p.points or 0 for p in joker_preds) / max(len(joker_preds), 1), 1)

    # 7. Vergleich mit aktivierten KI-Bots
    bot_comparison = [{"name": user.username, "points": sum(p.points or 0 for p in finished_preds), "is_me": True}]
    bots = filter_active_users(User.query.filter(User.email.like("%@bot.local")).order_by(User.username.asc()).all())
    if bots:
        bot_ids = [b.id for b in bots]
        bot_q = db.session.query(
            Prediction.user_id,
            func.coalesce(func.sum(Prediction.points), 0).label("points"),
        ).join(Match).filter(
            Prediction.user_id.in_(bot_ids),
            Match.status == "finished",
        )
        if comp:
            bot_q = bot_q.filter(Match.competition_id == comp.id)
        bot_points = {uid: int(points or 0) for uid, points in bot_q.group_by(Prediction.user_id).all()}
        for b in bots:
            bot_comparison.append({"name": b.username, "points": bot_points.get(b.id, 0), "is_me": False})
    bot_comparison.sort(key=lambda x: (-x["points"], 0 if x["is_me"] else 1, x["name"].lower()))
    bot_chart_labels = [b["name"] for b in bot_comparison]
    bot_chart_data = [b["points"] for b in bot_comparison]
    bot_chart_colors = ["#14b8a6" if b["is_me"] else "#3b82f6" for b in bot_comparison]

    # 8. Ranglistenverlauf aller aktiven Spieler
    rank_chart_labels, rank_chart_datasets, rank_chart_max = _build_rank_progression_data(user.id)

    # 9. H2H-Auswahl: nur aktive Mitspieler / aktivierte Bots
    all_users = filter_active_users(User.query.order_by(User.username).all())
    h2h_users = [u for u in all_users if u.id != user.id]

    pot = compute_pot_summary()

    # 9. Saison-Übersicht
    current_md = get_current_matchday()

    return render_template("stats_dashboard.html",
        user=user,
        trend=trend,
        insights=insights,
        stats20=stats20,
        sparkline_mds=sparkline_mds,
        sparkline_pts=sparkline_pts,
        md_labels_all=md_labels_all,
        md_data_all=md_data_all,
        acc_labels=acc_labels,
        acc_exact=acc_exact,
        acc_diff=acc_diff,
        acc_tendency=acc_tendency,
        acc_wrong=acc_wrong,
        top_tip_labels=top_tip_labels,
        top_tip_data=top_tip_data,
        joker_count=len(joker_preds),
        joker_success=joker_success,
        joker_fail=joker_fail,
        joker_avg=joker_avg,
        bot_comparison=bot_comparison,
        bot_chart_labels=bot_chart_labels,
        bot_chart_data=bot_chart_data,
        bot_chart_colors=bot_chart_colors,
        rank_chart_labels=rank_chart_labels,
        rank_chart_datasets=rank_chart_datasets,
        rank_chart_max=rank_chart_max,
        h2h_users=h2h_users,
        pot=pot,
        current_md=current_md,
        total_tips=len(finished_preds),
        total_points=sum(p.points or 0 for p in finished_preds),
    )

@main_bp.route("/recap", endpoint="season_recap")
@login_required
def _season_recap():
    # Profil-Helper lazy importieren, um zyklische Imports zwischen
    # ausgelagerten Main-Route-Modulen zu vermeiden.
    from main_profile_routes import _compute_profile_stats

    insights = get_user_insights(current_user)
    stats = _compute_profile_stats(current_user)
    trend = get_user_trend(current_user.id, last_n_matchdays=34)
    md_wins = filter_competition_scoped(
        MatchdayWinner.query.filter_by(user_id=current_user.id), MatchdayWinner
    ).all()
    badges = UserBadge.query.filter_by(user_id=current_user.id).all()

    comp = get_active_competition()
    best_md_base = db.session.query(
        Match.matchday,
        func.coalesce(func.sum(Prediction.points), 0).label("pts"),
    ).join(Prediction, Prediction.match_id == Match.id) \
     .filter(Prediction.user_id == current_user.id, Match.status == "finished")
    if comp:
        best_md_base = best_md_base.filter(Match.competition_id == comp.id)
    best_md_q = best_md_base.group_by(Match.matchday).order_by(func.sum(Prediction.points).desc()).first()
    best_md_pts = best_md_q.pts if best_md_q else 0
    best_md_num = best_md_q.matchday if best_md_q else None

    joker_q = Prediction.query.filter_by(user_id=current_user.id, joker=True).join(Match)
    if comp:
        joker_q = joker_q.filter(Match.competition_id == comp.id)
    joker_preds = joker_q.all()
    joker_total_pts = sum(p.points or 0 for p in joker_preds)
    joker_avg = round(joker_total_pts / len(joker_preds), 1) if joker_preds else 0

    leaderboard_rows = get_leaderboard()
    my_row = next((r for r in leaderboard_rows if r["user"].id == current_user.id), None)
    final_rank = my_row["rank"] if my_row else trend.get("current_rank")
    best_rank = final_rank
    if trend.get("previous_rank") and final_rank:
        best_rank = min(trend["previous_rank"], final_rank)

    comp = get_active_competition()
    matches_q = Match.query.filter(Match.status == "finished")
    if comp:
        matches_q = matches_q.filter(Match.competition_id == comp.id)
    finished_matches_count = matches_q.count()
    possible_tips = finished_matches_count
    completion_pct = round((stats["total_tips"] / possible_tips) * 100) if possible_tips else 0
    avg_points = round((stats["total_points"] / max(stats["total_tips"], 1)), 2)
    exact_quote = my_row["exact_quote"] if my_row else 0

    md_point_rows = db.session.query(
        Match.matchday,
        func.coalesce(func.sum(Prediction.points), 0).label("pts"),
    ).join(Prediction, Prediction.match_id == Match.id)      .filter(Prediction.user_id == current_user.id, Match.status == "finished")
    if comp:
        md_point_rows = md_point_rows.filter(Match.competition_id == comp.id)
    md_point_rows = md_point_rows.group_by(Match.matchday).order_by(Match.matchday.asc()).all()
    matchday_points = [{"matchday": r.matchday, "points": int(r.pts or 0)} for r in md_point_rows]
    max_md_points = max([r["points"] for r in matchday_points], default=0)

    report_badges = [ub.badge for ub in badges]
    report_awards = []
    if final_rank == 1:
        report_awards.append(("👑", "Saison-Champion"))
    if md_wins:
        report_awards.append(("🏆", f"{len(md_wins)} Spieltagsieg(e)"))
    if joker_total_pts:
        report_awards.append(("⚡", f"{joker_total_pts} Joker-Punkte"))
    if exact_quote >= 25:
        report_awards.append(("🎯", f"{exact_quote}% exakte Quote"))

    return render_template(
        "recap.html",
        insights=insights, stats=stats, trend=trend,
        md_wins_count=len(md_wins), badges_count=len(badges),
        best_md_pts=best_md_pts, best_md_num=best_md_num,
        joker_total_pts=joker_total_pts, joker_avg=joker_avg,
        joker_count=len(joker_preds),
        final_rank=final_rank, best_rank=best_rank,
        season_label=comp.season if comp else get_setting("current_season", ""),
        competition_name=comp.name if comp else "Bundesliga",
        leaderboard_top=leaderboard_rows[:5], total_players=len(leaderboard_rows),
        avg_points=avg_points, exact_quote=exact_quote,
        completion_pct=completion_pct, possible_tips=possible_tips,
        matchday_points=matchday_points, max_md_points=max_md_points,
        report_badges=report_badges, report_awards=report_awards,
    )


# ================================================ Preise & Pott -

@main_bp.route("/preise", endpoint="prizes")
@login_required
def _prizes():
    prize_q = filter_competition_scoped(Prize.query.filter_by(active=True), Prize)
    all_prizes = prize_q.order_by(
        Prize.sort_order.asc(), Prize.rank.asc()
    ).all()
    pot = compute_pot_summary()
    leaderboard = get_leaderboard()[:10]
    return render_template(
        "prizes.html", prizes=all_prizes, pot=pot,
        leaderboard=leaderboard,
    )


# =================================================== Live Match Center -

@main_bp.route("/live", endpoint="live_center")
@login_required
def _live_center():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    live_q = Match.query.filter(
        Match.kickoff >= today_start,
        Match.kickoff < today_end,
    )
    live_matches = filter_matches_for_active_competition(live_q).order_by(Match.kickoff.asc()).all()

    if not live_matches:
        next_q = Match.query.filter(Match.kickoff >= now)
        next_match = filter_matches_for_active_competition(next_q).order_by(Match.kickoff.asc()).first()
        if next_match:
            day = next_match.kickoff.replace(hour=0, minute=0, second=0, microsecond=0)
            live_day_q = Match.query.filter(
                Match.kickoff >= day,
                Match.kickoff < day + timedelta(days=1),
            )
            live_matches = filter_matches_for_active_competition(live_day_q).order_by(Match.kickoff.asc()).all()

    leaderboard = get_leaderboard()
    user_preds = {
        p.match_id: p
        for p in Prediction.query.filter_by(user_id=current_user.id).all()
        if p.match_id in [m.id for m in live_matches]
    }

    is_today = bool(live_matches and live_matches[0].kickoff.date() == now.date())
    has_live = any(m.status == "live" for m in live_matches)
    shown_date = live_matches[0].kickoff if live_matches else None
    return render_template(
        "live.html",
        matches=live_matches,
        leaderboard=leaderboard,
        user_preds=user_preds,
        is_today=is_today,
        has_live=has_live,
        shown_date=shown_date,
    )


# ================================================ Live Bundesliga-Tabelle -

@main_bp.route("/bundesliga-tabelle", endpoint="bl_standings")
@login_required
def _bl_standings():
    source = "lokal"
    error_msg = None
    standings, err = fetch_live_standings()
    if standings:
        source = "football-data.org (live)"
        if len(standings) < 18:
            error_msg = f"Hinweis: API-Tabelle enthält nur {len(standings)} erkannte Teams. Bitte Sync/Team-Mapping prüfen."
    else:
        error_msg = err
        standings = compute_live_standings()
    return render_template(
        "standings.html",
        standings=standings,
        source=source,
        error_msg=error_msg,
    )

@main_bp.route("/tabelle", endpoint="leaderboard")
@main_bp.route("/tabelle/<int:matchday>", endpoint="leaderboard")
@login_required
def _leaderboard(matchday=None):
    rows = get_leaderboard(matchday=matchday)
    matchdays = active_matchdays()

    md_wins_q = filter_competition_scoped(
        db.session.query(MatchdayWinner.user_id, func.count(MatchdayWinner.id)),
        MatchdayWinner,
    )
    md_wins = dict(md_wins_q.group_by(MatchdayWinner.user_id).all())
    trends = {}
    if not matchday:
        for r in rows:
            try:
                trends[r["user"].id] = get_user_trend(r["user"].id, last_n_matchdays=6)
            except Exception:
                pass
    return render_template(
        "leaderboard.html",
        rows=rows, current_md=matchday, matchdays=matchdays,
        md_wins=md_wins, trends=trends,
    )

@main_bp.route("/spieltagsieger", endpoint="matchday_winners")
@login_required
def _matchday_winners():
    winners = (
        filter_competition_scoped(MatchdayWinner.query, MatchdayWinner)
        .order_by(MatchdayWinner.matchday.desc())
        .all()
    )
    from collections import OrderedDict
    grouped = OrderedDict()
    for w in winners:
        grouped.setdefault(w.matchday, []).append(w)

    top_base_q = db.session.query(
        MatchdayWinner.user_id,
        func.count(MatchdayWinner.id).label("wins"),
        func.sum(MatchdayWinner.points).label("total_pts"),
    )
    top_base_q = filter_competition_scoped(top_base_q, MatchdayWinner)
    top_winners_q = (
        top_base_q
        .group_by(MatchdayWinner.user_id)
        .order_by(func.count(MatchdayWinner.id).desc())
        .all()
    )
    top_winners = []
    for row in top_winners_q:
        u = db.session.get(User, row.user_id)
        if u:
            top_winners.append({"user": u, "wins": row.wins, "total_pts": row.total_pts or 0})

    return render_template(
        "matchday_winners.html",
        grouped=grouped, top_winners=top_winners,
    )

@main_bp.route("/h2h/<int:user_id>", endpoint="head_to_head")
@login_required
def _head_to_head(user_id):
    other = db.get_or_404(User, user_id)
    my_preds = {p.match_id: p for p in current_user.predictions.all()}
    other_preds = {p.match_id: p for p in other.predictions.all()}
    common_matches = Match.query.filter(Match.id.in_(set(my_preds) & set(other_preds))).all()

    me_pts = sum(my_preds[m.id].points or 0 for m in common_matches)
    other_pts = sum(other_preds[m.id].points or 0 for m in common_matches)

    return render_template(
        "h2h.html", other=other, common=common_matches,
        my=my_preds, their=other_preds, me_pts=me_pts, other_pts=other_pts,
    )

