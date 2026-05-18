"""Haupt-Routes: Dashboard, Spielplan, Tipp, Profil, Export, etc."""
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    abort, jsonify, send_file, current_app, send_from_directory,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import (
    User, Team, Match, Prediction, Setting, Comment, Badge, UserBadge,
    SpecialQuestion, SpecialPrediction, SeasonArchive, Prize, MatchdayWinner,
    Competition, CompetitionTeam,
)
from forms import (
    ProfileForm, TipForm, CommentForm, SpecialAnswerForm,
)
from scoring import (
    get_setting, set_setting, get_leaderboard, get_user_stats,
    get_live_leaderboard, recalculate_all_points, compute_pot_summary,
    calculate_points,
)
from stats import (
    get_user_trend, get_user_insights, get_match_tip_distribution,
    get_match_weather, get_open_matches_for_user, get_current_matchday,
    compute_live_standings, get_team_position, get_team_form, get_h2h,
    get_eternal_table, archive_season, evaluate_special_predictions,
)
from sync import fetch_live_standings, fetch_live_match_updates
import bleach
from badges import check_and_award_badges
from avatars import save_avatar
from export import generate_season_pdf

import json as _json


main_bp = Blueprint("main", __name__)


# ============================================================ PWA Routes -
@main_bp.route("/sw.js")
def service_worker():
    response = send_from_directory(
        os.path.join(current_app.root_path, "static", "js"),
        "sw.js",
        mimetype="application/javascript",
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@main_bp.route("/manifest.json")
def manifest():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "manifest.json",
        mimetype="application/manifest+json",
    )


@main_bp.route("/icon-<int:size>.png")
def pwa_icon(size):
    if size not in (192, 512):
        size = 192
    try:
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO

        img = Image.new("RGB", (size, size), color=(20, 184, 166))
        draw = ImageDraw.Draw(img)
        text = "⚽"
        font = None
        for font_path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "C:/Windows/Fonts/seguiemj.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]:
            try:
                font = ImageFont.truetype(font_path, size=int(size * 0.6))
                break
            except (OSError, IOError):
                continue
        if font is None:
            font = ImageFont.load_default()

        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (size - tw) // 2 - bbox[0]
            y = (size - th) // 2 - bbox[1]
        except Exception:
            x = y = size // 4
        draw.text((x, y), text, fill="white", font=font)

        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        from flask import Response
        resp = Response(buf.getvalue(), mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        from flask import Response
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#14b8a6" rx="20%"/>'
            f'<text x="50%" y="50%" dominant-baseline="central" text-anchor="middle" '
            f'font-size="{size//2}" fill="white">⚽</text></svg>'
        )
        return Response(svg, mimetype="image/svg+xml")


# ============================================================ Main Pages -
@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    top3 = get_leaderboard()[:3]
    return render_template(
        "landing.html",
        top3=top3,
        current_md=get_current_matchday(),
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    upcoming = Match.query.filter(
        Match.kickoff > datetime.now(timezone.utc),
        Match.status == "scheduled"
    ).order_by(Match.kickoff.asc()).all()

    user_points = current_user.total_points()
    leaderboard = get_leaderboard()[:5]
    user_rank = next((r["rank"] for r in get_leaderboard() if r["user"].id == current_user.id), None)
    current_matchday = get_current_matchday()
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()

    live_count = Match.query.filter_by(status="live").count()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_matches_count = Match.query.filter(
        Match.kickoff >= today,
        Match.kickoff < today + timedelta(days=1),
    ).count()

    return render_template(
        "dashboard.html",
        upcoming=upcoming,
        user_points=user_points,
        leaderboard=leaderboard,
        user_rank=user_rank,
        current_matchday=current_matchday,
        badges=user_badges,
        live_count=live_count,
        today_matches_count=today_matches_count,
        get_user_prediction=lambda mid: Prediction.query.filter_by(user_id=current_user.id, match_id=mid).first(),
    )


@main_bp.route("/spielplan")
@main_bp.route("/spielplan/<int:matchday>")
@login_required
def schedule(matchday=None):
    if matchday is None:
        matchday = get_current_matchday()

    matches = Match.query.filter_by(matchday=matchday).order_by(Match.kickoff).all()
    matchdays = sorted([r[0] for r in db.session.query(Match.matchday).distinct().all()])

    pred_map = {}
    for p in Prediction.query.filter_by(user_id=current_user.id).all():
        pred_map[p.match_id] = p

    joker_used = current_user.joker_used_for_matchday(matchday)

    standings = compute_live_standings()
    pos_map = {r["team"].id: r for r in standings}
    form_map = {}
    for m in matches:
        if m.home_team_id not in form_map:
            form_map[m.home_team_id] = get_team_form(m.home_team_id, 5)
        if m.away_team_id not in form_map:
            form_map[m.away_team_id] = get_team_form(m.away_team_id, 5)

    return render_template(
        "schedule.html",
        matches=matches,
        current_md=matchday,
        matchdays=matchdays,
        pred_map=pred_map,
        joker_used=joker_used,
        pos_map=pos_map,
        form_map=form_map,
    )


@main_bp.route("/match/<int:match_id>", methods=["GET", "POST"])
@login_required
def match_detail(match_id):
    match = Match.query.get_or_404(match_id)
    pred = Prediction.query.filter_by(user_id=current_user.id, match_id=match_id).first()

    tip_form = TipForm(obj=pred)
    comment_form = CommentForm()

    siblings = Match.query.filter_by(matchday=match.matchday).order_by(Match.kickoff, Match.id).all()
    sibling_ids = [m.id for m in siblings]
    try:
        idx = sibling_ids.index(match_id)
    except ValueError:
        idx = 0
    prev_id = sibling_ids[idx - 1] if idx > 0 else None
    next_id = sibling_ids[idx + 1] if idx < len(sibling_ids) - 1 else None
    nav_position = idx + 1
    nav_total = len(siblings)

    if tip_form.validate_on_submit() and request.form.get("form") == "tip":
        if not match.is_open():
            flash("Tipps sind nicht mehr möglich – Anpfiff erfolgt.", "danger")
            return redirect(url_for("main.match_detail", match_id=match_id))

        if tip_form.joker.data and not (pred and pred.joker):
            existing = Prediction.query.join(Match).filter(
                Prediction.user_id == current_user.id,
                Prediction.joker.is_(True),
                Match.matchday == match.matchday,
                Prediction.match_id != match_id,
            ).all()
            for ep in existing:
                old_label = f"{ep.match.home_team.short_name}-{ep.match.away_team.short_name}"
                ep.joker = False
                flash(f"⚡ Joker von {old_label} hierher verschoben.", "info")

        if pred:
            pred.home_tip = tip_form.home_tip.data
            pred.away_tip = tip_form.away_tip.data
            pred.joker = tip_form.joker.data
        else:
            pred = Prediction(
                user_id=current_user.id, match_id=match_id,
                home_tip=tip_form.home_tip.data, away_tip=tip_form.away_tip.data,
                joker=tip_form.joker.data,
            )
            db.session.add(pred)
        db.session.commit()
        check_and_award_badges()
        flash("Tipp gespeichert!", "success")
        return redirect(url_for("main.match_detail", match_id=match_id))

    if comment_form.validate_on_submit() and request.form.get("form") == "comment":
        c = Comment(match_id=match_id, user_id=current_user.id, text=bleach.clean(comment_form.text.data, tags=["b", "i", "em", "strong", "code", "span"], attributes={"span": ["class"]}, strip=True))
        db.session.add(c)
        db.session.commit()
        flash("Kommentar gepostet.", "success")
        return redirect(url_for("main.match_detail", match_id=match_id))

    # Kommentare mit Paginierung
    comments_page = request.args.get("comments_page", 1, type=int)
    comments_per_page = 10
    comments_pagination = Comment.query.filter_by(match_id=match_id).order_by(Comment.created_at.desc()).paginate(page=comments_page, per_page=comments_per_page, error_out=False)
    comments = comments_pagination.items
    all_preds = match.predictions.all() if match.status == "finished" else []

    home_form = get_team_form(match.home_team_id, limit=5)
    away_form = get_team_form(match.away_team_id, limit=5)
    h2h = get_h2h(match.home_team_id, match.away_team_id, limit=5)
    home_pos = get_team_position(match.home_team_id)
    away_pos = get_team_position(match.away_team_id)
    tip_dist = get_match_tip_distribution(match_id)
    weather = None
    if match.is_open() or match.status == "live":
        try:
            weather = get_match_weather(match)
        except Exception as e:
            current_app.logger.warning(f"Wetter-API Fehler: {e}")

    return render_template(
        "match_detail.html",
        match=match, pred=pred,
        tip_form=tip_form, comment_form=comment_form,
        comments=comments, comments_pagination=comments_pagination, all_preds=all_preds,
        home_form=home_form, away_form=away_form, h2h=h2h,
        home_pos=home_pos, away_pos=away_pos,
        sibling_ids=sibling_ids, prev_id=prev_id, next_id=next_id,
        nav_position=nav_position, nav_total=nav_total,
        siblings=siblings,
        tip_dist=tip_dist, weather=weather,
    )


@main_bp.route("/schnelltipp/<int:matchday>", methods=["GET", "POST"])
@login_required
def quick_tip(matchday):
    matches = Match.query.filter_by(matchday=matchday).order_by(Match.kickoff).all()

    if request.method == "POST":
        joker_match_id = request.form.get("joker_match", type=int)

        # Alte Joker für diesen Spieltag entfernen (wenn neuer Joker gesetzt wurde)
        if joker_match_id:
            old_jokers = Prediction.query.join(Match).filter(
                Prediction.user_id == current_user.id,
                Prediction.joker.is_(True),
                Match.matchday == matchday,
            ).all()
            for oj in old_jokers:
                oj.joker = False

        used_joker = False
        for m in matches:
            if not m.is_open():
                continue
            h = request.form.get(f"home_{m.id}", type=int)
            a = request.form.get(f"away_{m.id}", type=int)
            if h is None or a is None:
                continue

            is_joker = (m.id == joker_match_id and not used_joker)
            if is_joker:
                used_joker = True

            pred = Prediction.query.filter_by(user_id=current_user.id, match_id=m.id).first()
            if pred:
                pred.home_tip = h
                pred.away_tip = a
                pred.joker = is_joker
            else:
                db.session.add(Prediction(
                    user_id=current_user.id, match_id=m.id,
                    home_tip=h, away_tip=a, joker=is_joker,
                ))
        db.session.commit()
        check_and_award_badges()

        try:
            from cache import invalidate_leaderboard
            invalidate_leaderboard()
        except Exception:
            pass

        flash(f"Schnelltipps für Spieltag {matchday} gespeichert.", "success")
        return redirect(url_for("main.schedule", matchday=matchday))

    pred_map = {p.match_id: p for p in Prediction.query.filter_by(user_id=current_user.id).all()}

    standings = compute_live_standings()
    pos_map = {r["team"].id: r for r in standings}
    form_map = {}
    for m in matches:
        if m.home_team_id not in form_map:
            form_map[m.home_team_id] = get_team_form(m.home_team_id, 5)
        if m.away_team_id not in form_map:
            form_map[m.away_team_id] = get_team_form(m.away_team_id, 5)

    return render_template(
        "quick_tip.html",
        matches=matches, matchday=matchday, pred_map=pred_map,
        pos_map=pos_map, form_map=form_map,
    )


# ================================================ Sondertipps -
@main_bp.route("/sondertipps", methods=["GET", "POST"])
@login_required
def special_tips():
    questions = SpecialQuestion.query.order_by(SpecialQuestion.deadline.asc()).all()

    if request.method == "POST":
        for q in questions:
            if datetime.now(timezone.utc) > q.deadline:
                continue
            if q.answer_type == "multi_team":
                values = request.form.getlist(f"q_{q.id}")
                values = [v.strip() for v in values if v.strip()]
                if not values:
                    continue
                if q.multi_count and len(values) > q.multi_count:
                    flash(f"Bei '{q.text[:40]}': max. {q.multi_count} Antworten erlaubt.", "warning")
                    values = values[:q.multi_count]
                answer = _json.dumps(values)
            else:
                answer = request.form.get(f"q_{q.id}", "").strip()
                if not answer:
                    continue

            sp = SpecialPrediction.query.filter_by(user_id=current_user.id, question_id=q.id).first()
            if sp:
                sp.answer = answer
            else:
                db.session.add(SpecialPrediction(
                    user_id=current_user.id, question_id=q.id, answer=answer,
                ))
        db.session.commit()
        evaluate_special_predictions()
        flash("Sondertipps gespeichert.", "success")
        return redirect(url_for("main.special_tips"))

    user_answers = {sp.question_id: sp for sp in SpecialPrediction.query.filter_by(user_id=current_user.id).all()}
    user_answer_lists = {}
    for qid, sp in user_answers.items():
        try:
            parsed = _json.loads(sp.answer)
            if isinstance(parsed, list):
                user_answer_lists[qid] = parsed
        except (ValueError, TypeError):
            pass

    parsed_options = {}
    for q in questions:
        if q.answer_type == "choice" and q.options:
            try:
                parsed_options[q.id] = _json.loads(q.options)
            except (ValueError, TypeError):
                parsed_options[q.id] = [o.strip() for o in q.options.split("\n") if o.strip()]
        else:
            parsed_options[q.id] = None

    all_teams = Team.query.order_by(Team.name).all()

    return render_template(
        "special_tips.html",
        questions=questions, user_answers=user_answers,
        user_answer_lists=user_answer_lists,
        options=parsed_options, all_teams=all_teams,
        current_time=datetime.now(timezone.utc),
    )


# ================================================ Ewige Tabelle -
@main_bp.route("/ewige-tabelle")
@login_required
def eternal_table():
    rows = get_eternal_table()
    return render_template("eternal.html", rows=rows)


# ================================================ Saison-Recap -
# ------------------------------------------------------------------
# 📊 Erweitertes Statistik-Dashboard
# ------------------------------------------------------------------

@main_bp.route("/stats")
@login_required
def stats_dashboard():
    """Umfassendes Statistik-Dashboard mit Diagrammen."""
    user = current_user

    # 1. Punkte-Verlauf (letzte 8 Spieltage)
    trend = get_user_trend(user.id, last_n_matchdays=8)
    sparkline_mds = trend.get("recent_matchdays", [])
    sparkline_pts = trend.get("sparkline", [])

    # 2. Tipp-Verteilung (Heim/X/Auswärts)
    from stats import get_user_insights
    insights = get_user_insights(user)

    # 3. Spieltagspunkte (alle)
    preds = user.predictions.all()
    finished_preds = [p for p in preds if p.match.status == "finished"]
    md_points_all = {}
    md_labels_all = []
    md_data_all = []
    for p in finished_preds:
        md = p.match.matchday
        md_points_all[md] = md_points_all.get(md, 0) + (p.points or 0)
    for md in sorted(md_points_all.keys()):
        md_labels_all.append(str(md))
        md_data_all.append(md_points_all[md])

    # 4. Genauigkeit pro Spieltag
    md_accuracy = {}
    for p in finished_preds:
        md = p.match.matchday
        if md not in md_accuracy:
            md_accuracy[md] = {"exact": 0, "diff": 0, "tendency": 0, "wrong": 0}
        from scoring import classify_prediction
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
        acc_exact.append(round(d["exact"]/total*100, 1) if total else 0)
        acc_diff.append(round(d["diff"]/total*100, 1) if total else 0)
        acc_tendency.append(round(d["tendency"]/total*100, 1) if total else 0)
        acc_wrong.append(round(d["wrong"]/total*100, 1) if total else 0)

    # 5. Beliebteste Tipps
    tip_counts = {}
    for p in finished_preds:
        key = f"{p.home_tip}:{p.away_tip}"
        tip_counts[key] = tip_counts.get(key, 0) + 1
    top_tips = sorted(tip_counts.items(), key=lambda x: -x[1])[:8]
    top_tip_labels = [t[0] for t in top_tips]
    top_tip_data = [t[1] for t in top_tips]

    # 6. Joker-Statistik
    joker_preds = [p for p in finished_preds if p.joker]
    joker_success = sum(1 for p in joker_preds if p.points and p.points > 0)
    joker_fail = len(joker_preds) - joker_success
    joker_avg = round(sum(p.points or 0 for p in joker_preds) / max(len(joker_preds), 1), 1)

    # 7. Vergleich mit KI-Bots
    bot_comparison = []
    from models import User as Usr
    bots = Usr.query.filter(Usr.email.like("%@bot.local")).all()
    bot_comparison.append({"name": user.username, "points": sum(p.points or 0 for p in finished_preds), "is_me": True})
    for b in bots:
        b_preds = Prediction.query.filter_by(user_id=b.id).all()
        b_finished = [p for p in b_preds if p.match.status == "finished"]
        bot_comparison.append({"name": b.username, "points": sum(p.points or 0 for p in b_finished), "is_me": False})
    bot_comparison.sort(key=lambda x: -x["points"])

    # 8. H2H-Auswahl (alle User für Dropdown)
    all_users = User.query.order_by(User.username).all()
    h2h_users = [u for u in all_users if u.id != user.id]

    from scoring import compute_pot_summary
    pot = compute_pot_summary()

    # 9. Saison-Übersicht
    from stats import get_current_matchday
    current_md = get_current_matchday()

    return render_template("stats_dashboard.html",
        user=user,
        trend=trend,
        insights=insights,
        sparkline_mds=sparkline_mds,
        sparkline_pts=sparkline_pts,
        md_labels_all=",".join(md_labels_all),
        md_data_all=",".join(str(d) for d in md_data_all),
        acc_labels=",".join(acc_labels),
        acc_exact=",".join(str(d) for d in acc_exact),
        acc_diff=",".join(str(d) for d in acc_diff),
        acc_tendency=",".join(str(d) for d in acc_tendency),
        acc_wrong=",".join(str(d) for d in acc_wrong),
        top_tip_labels=",".join(top_tip_labels),
        top_tip_data=",".join(str(d) for d in top_tip_data),
        joker_count=len(joker_preds),
        joker_success=joker_success,
        joker_fail=joker_fail,
        joker_avg=joker_avg,
        bot_comparison=bot_comparison,
        h2h_users=h2h_users,
        pot=pot,
        current_md=current_md,
        total_tips=len(finished_preds),
        total_points=sum(p.points or 0 for p in finished_preds),
    )


@main_bp.route("/recap")
@login_required
def season_recap():
    insights = get_user_insights(current_user)
    stats = _compute_profile_stats(current_user)
    trend = get_user_trend(current_user.id, last_n_matchdays=34)
    md_wins = MatchdayWinner.query.filter_by(user_id=current_user.id).all()
    badges = UserBadge.query.filter_by(user_id=current_user.id).all()

    best_md_q = db.session.query(
        Match.matchday,
        func.coalesce(func.sum(Prediction.points), 0).label("pts"),
    ).join(Prediction, Prediction.match_id == Match.id) \
     .filter(Prediction.user_id == current_user.id, Match.status == "finished") \
     .group_by(Match.matchday).order_by(func.sum(Prediction.points).desc()).first()
    best_md_pts = best_md_q.pts if best_md_q else 0
    best_md_num = best_md_q.matchday if best_md_q else None

    joker_preds = [p for p in current_user.predictions.all() if p.joker]
    joker_total_pts = sum(p.points or 0 for p in joker_preds)
    joker_avg = round(joker_total_pts / len(joker_preds), 1) if joker_preds else 0

    final_rank = trend.get("current_rank")
    best_rank = final_rank
    if trend.get("previous_rank") and trend.get("current_rank"):
        best_rank = min(trend["previous_rank"], trend["current_rank"])

    return render_template(
        "recap.html",
        insights=insights, stats=stats, trend=trend,
        md_wins_count=len(md_wins), badges_count=len(badges),
        best_md_pts=best_md_pts, best_md_num=best_md_num,
        joker_total_pts=joker_total_pts, joker_avg=joker_avg,
        joker_count=len(joker_preds),
        final_rank=final_rank, best_rank=best_rank,
    )


# ================================================ Preise & Pott -
@main_bp.route("/preise")
@login_required
def prizes():
    all_prizes = Prize.query.filter_by(active=True).order_by(
        Prize.sort_order.asc(), Prize.rank.asc()
    ).all()
    pot = compute_pot_summary()
    leaderboard = get_leaderboard()[:10]
    return render_template(
        "prizes.html", prizes=all_prizes, pot=pot,
        leaderboard=leaderboard,
    )


# =================================================== Live Match Center -
@main_bp.route("/live")
@login_required
def live_center():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    live_matches = Match.query.filter(
        Match.kickoff >= today_start,
        Match.kickoff < today_end,
    ).order_by(Match.kickoff.asc()).all()

    if not live_matches:
        next_match = Match.query.filter(Match.kickoff >= now).order_by(Match.kickoff.asc()).first()
        if next_match:
            day = next_match.kickoff.replace(hour=0, minute=0, second=0, microsecond=0)
            live_matches = Match.query.filter(
                Match.kickoff >= day,
                Match.kickoff < day + timedelta(days=1),
            ).order_by(Match.kickoff.asc()).all()

    leaderboard = get_leaderboard()
    user_preds = {
        p.match_id: p
        for p in Prediction.query.filter_by(user_id=current_user.id).all()
        if p.match_id in [m.id for m in live_matches]
    }

    return render_template(
        "live.html",
        matches=live_matches,
        leaderboard=leaderboard,
        user_preds=user_preds,
        is_today=bool(live_matches and live_matches[0].kickoff.date() == now.date()),
    )


# ================================================ Live Bundesliga-Tabelle -
@main_bp.route("/bundesliga-tabelle")
@login_required
def bl_standings():
    source = "lokal"
    error_msg = None
    standings, err = fetch_live_standings()
    if standings:
        source = "football-data.org (live)"
    else:
        error_msg = err
        standings = compute_live_standings()
    return render_template(
        "standings.html",
        standings=standings,
        source=source,
        error_msg=error_msg,
    )


@main_bp.route("/tabelle")
@main_bp.route("/tabelle/<int:matchday>")
@login_required
def leaderboard(matchday=None):
    rows = get_leaderboard(matchday=matchday)
    matchdays = sorted([r[0] for r in db.session.query(Match.matchday).distinct().all()])

    md_wins = dict(
        db.session.query(MatchdayWinner.user_id, func.count(MatchdayWinner.id))
        .group_by(MatchdayWinner.user_id).all()
    )
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


@main_bp.route("/spieltagsieger")
@login_required
def matchday_winners():
    winners = MatchdayWinner.query.order_by(MatchdayWinner.matchday.desc()).all()
    from collections import OrderedDict
    grouped = OrderedDict()
    for w in winners:
        grouped.setdefault(w.matchday, []).append(w)

    top_winners_q = (
        db.session.query(
            MatchdayWinner.user_id,
            func.count(MatchdayWinner.id).label("wins"),
            func.sum(MatchdayWinner.points).label("total_pts"),
        )
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


def _compute_profile_stats(user):
    user_preds = user.predictions.all()
    md_wins = MatchdayWinner.query.filter_by(user_id=user.id).count()
    return {
        "total_tips": len(user_preds),
        "total_points": sum(p.points or 0 for p in user_preds),
        "exact": sum(1 for p in user_preds if p.points and p.points >= get_setting("points_exact", 4)),
        "joker_used": sum(1 for p in user_preds if p.joker),
        "md_wins": md_wins,
    }


def _compute_form_curve(user):
    md_points = {}
    for p in user.predictions.all():
        if p.match and p.match.status == "finished":
            md_points.setdefault(p.match.matchday, 0)
            md_points[p.match.matchday] += p.points or 0
    return sorted(md_points.items())


@main_bp.route("/profil", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    teams = Team.query.order_by(Team.name).all()
    form.favorite_team_id.choices = [(0, "— kein Lieblingsverein —")] + [
        (t.id, t.name) for t in teams
    ]
    if request.method == "GET":
        form.favorite_team_id.data = current_user.favorite_team_id or 0

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
        current_user.show_full_name = bool(form.show_full_name.data)
        current_user.phone = (form.phone.data or "").strip() or None
        current_user.whatsapp_phone = (form.whatsapp_phone.data or "").strip() or None
        current_user.whatsapp_apikey = (form.whatsapp_apikey.data or "").strip() or None
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


@main_bp.route("/h2h/<int:user_id>")
@login_required
def head_to_head(user_id):
    other = User.query.get_or_404(user_id)
    my_preds = {p.match_id: p for p in current_user.predictions.all()}
    other_preds = {p.match_id: p for p in other.predictions.all()}
    common_matches = Match.query.filter(Match.id.in_(set(my_preds) & set(other_preds))).all()

    me_pts = sum(my_preds[m.id].points or 0 for m in common_matches)
    other_pts = sum(other_preds[m.id].points or 0 for m in common_matches)

    return render_template(
        "h2h.html", other=other, common=common_matches,
        my=my_preds, their=other_preds, me_pts=me_pts, other_pts=other_pts,
    )


@main_bp.route("/export/pdf")
@login_required
def export_pdf():
    pdf_buf = generate_season_pdf(current_user)
    if pdf_buf is None:
        flash("PDF-Export benötigt das Paket 'reportlab' (pip install reportlab).", "danger")
        return redirect(url_for("main.season_recap"))
    filename = f"Saison-Report_{current_user.username}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return send_file(pdf_buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


@main_bp.route("/export/csv")
@login_required
def export_csv():
    output = BytesIO()
    writer_data = [["Spieltag", "Datum", "Heim", "Auswärts", "Tipp", "Ergebnis", "Punkte", "Joker"]]
    for p in current_user.predictions.all():
        m = p.match
        writer_data.append([
            m.matchday, m.kickoff.strftime("%d.%m.%Y %H:%M"),
            m.home_team.name, m.away_team.name,
            f"{p.home_tip}:{p.away_tip}",
            f"{m.home_score}:{m.away_score}" if m.home_score is not None else "—",
            p.points or 0, "Ja" if p.joker else "Nein",
        ])
    csv_data = "\n".join(";".join(str(c) for c in row) for row in writer_data)
    output.write(csv_data.encode("utf-8-sig"))
    output.seek(0)
    return send_file(
        output, mimetype="text/csv",
        as_attachment=True, download_name=f"tipps_{current_user.username}.csv"
    )


# ------------------------------------------------------------------
# Telegram Bot Webhook
# ------------------------------------------------------------------

@main_bp.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """Webhook für eingehende Telegram-Nachrichten."""
    from telegram_bot import process_message, send_telegram_message
    import json

    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if chat_id and text:
            reply = process_message(str(chat_id), text)
            if reply:
                send_telegram_message(chat_id, reply)
    except Exception as e:
        current_app.logger.error(f"Telegram Webhook Error: {e}")

    return "", 200


@main_bp.route("/profile/telegram-token")
@login_required
def profile_telegram_token():
    """Generiert einen Telegram-Verknüpfungs-Token für das Profil."""
    from telegram_bot import generate_telegram_token
    token = generate_telegram_token(current_user.id)
    bot_username = None
    from scoring import get_setting
    bot_username = get_setting("telegram_bot_username", "")
    return jsonify({
        "ok": True,
        "token": token,
        "bot_username": bot_username,
    })


@main_bp.route("/set-competition/<string:code>")
@login_required
def set_competition(code):
    from flask import session
    comp = Competition.query.filter_by(code=code, is_active=True).first()
    if comp:
        session["competition_code"] = code
        flash(f"Wettbewerb auf '{comp.name}' gewechselt.", "success")
    else:
        flash("Ungültiger Wettbewerb.", "danger")
    return redirect(request.referrer or url_for("main.dashboard"))
