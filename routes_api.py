"""API-Routes: JSON-Endpunkte für Rangliste, Tipps, Live-Updates."""
from datetime import datetime, timedelta, timezone
import time
import json as _json_lib

from flask import (
    Blueprint, jsonify, request, Response, stream_with_context,
)
from flask_login import login_required, current_user

from extensions import db, limiter
from models import Match, Prediction, User, Competition
from scoring import (
    get_setting, get_live_leaderboard, calculate_points,
    recalculate_all_points,
)
from sync import fetch_live_standings, fetch_live_match_updates
from stats import get_current_matchday
from badges import check_and_award_badges


api_bp = Blueprint("api", __name__)


@api_bp.route("/leaderboard")
@limiter.limit("60/minute")
def api_leaderboard():
    rows = get_live_leaderboard()
    return jsonify([
        {"rank": r["rank"], "username": r["user"].username,
         "points": r["points"], "exact": r["exact"], "tips": r["tips"]}
        for r in rows
    ])


@api_bp.route("/live/standings")
@login_required
def api_live_standings():
    rows, err = fetch_live_standings()
    if not rows:
        return jsonify({"ok": False, "error": err}), 503
    return jsonify({
        "ok": True,
        "source": "football-data.org",
        "fetched_at": datetime.now(timezone.utc).isoformat() + "Z",
        "table": [
            {
                "rank": r["rank"],
                "team_name": r["team"].name,
                "team_short": r["team"].short_name,
                "team_logo": r["team"].logo,
                "played": r["played"], "won": r["won"], "drawn": r["drawn"], "lost": r["lost"],
                "goals_for": r["goals_for"], "goals_against": r["goals_against"],
                "goal_diff": r["goal_diff"], "points": r["points"],
                "form": r.get("form", ""),
            }
            for r in rows
        ],
    })


@api_bp.route("/tip/<int:match_id>", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def api_save_tip(match_id):
    from models import Match, Prediction
    match = Match.query.get_or_404(match_id)
    if not match.is_open():
        return jsonify({"ok": False, "error": "Anstoß bereits erfolgt"}), 400

    data = request.get_json(silent=True) or {}
    try:
        home_tip = int(data.get("home_tip"))
        away_tip = int(data.get("away_tip"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Ungültiger Tipp"}), 400

    if not (0 <= home_tip <= 30 and 0 <= away_tip <= 30):
        return jsonify({"ok": False, "error": "Score 0–30 erlaubt"}), 400

    use_joker = bool(data.get("joker", False))
    moved_from = None

    if use_joker:
        existing = Prediction.query.join(Match).filter(
            Prediction.user_id == current_user.id,
            Prediction.joker.is_(True),
            Match.matchday == match.matchday,
            Prediction.match_id != match_id,
        ).all()
        for ep in existing:
            moved_from = f"{ep.match.home_team.short_name}-{ep.match.away_team.short_name}"
            ep.joker = False

    pred = Prediction.query.filter_by(user_id=current_user.id, match_id=match_id).first()
    if pred:
        pred.home_tip = home_tip
        pred.away_tip = away_tip
        pred.joker = use_joker
    else:
        pred = Prediction(
            user_id=current_user.id, match_id=match_id,
            home_tip=home_tip, away_tip=away_tip, joker=use_joker,
        )
        db.session.add(pred)
    db.session.commit()
    check_and_award_badges()

    try:
        from cache import invalidate_leaderboard, invalidate_match
        invalidate_leaderboard()
        invalidate_match(match_id)
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "home_tip": pred.home_tip,
        "away_tip": pred.away_tip,
        "joker": pred.joker,
        "joker_moved_from": moved_from,
    })


@api_bp.route("/live/center")
@login_required
def api_live_center():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    today_matches = Match.query.filter(
        Match.kickoff >= today_start,
        Match.kickoff < today_end,
    ).all()
    matchdays = sorted(set(m.matchday for m in today_matches))

    sync_info = []
    for md in matchdays:
        res = fetch_live_match_updates(matchday=md)
        if res.get("ok"):
            sync_info.append(f"ST{md}: {res.get('updated', 0)} updates, {res.get('live', 0)} live")

    matches = Match.query.filter(
        Match.kickoff >= today_start,
        Match.kickoff < today_end,
    ).order_by(Match.kickoff.asc()).all()

    rows = get_live_leaderboard()

    user_preds = {
        p.match_id: {"home_tip": p.home_tip, "away_tip": p.away_tip,
                      "joker": p.joker, "points": p.points}
        for p in Prediction.query.filter_by(user_id=current_user.id).all()
        if p.match_id in [m.id for m in matches]
    }

    return jsonify({
        "ok": True,
        "fetched_at": now.isoformat() + "Z",
        "sync_info": " | ".join(sync_info),
        "matches": [
            {
                "id": m.id, "matchday": m.matchday,
                "home_id": m.home_team_id, "home_name": m.home_team.name,
                "home_short": m.home_team.short_name, "home_logo": m.home_team.logo,
                "away_id": m.away_team_id, "away_name": m.away_team.name,
                "away_short": m.away_team.short_name, "away_logo": m.away_team.logo,
                "kickoff": m.kickoff.isoformat() + "Z",
                "home_score": m.home_score, "away_score": m.away_score,
                "status": m.status,
                "user_pred": user_preds.get(m.id),
            }
            for m in matches
        ],
        "leaderboard": [
            {
                "rank": r["rank"], "user_id": r["user"].id,
                "username": r["user"].username, "avatar": r["user"].avatar,
                "points": r["points"], "exact": r["exact"],
                "diff": r["diff"], "tendency": r["tendency"],
                "wrong": r["wrong"],
                "is_me": r["user"].id == current_user.id,
            }
            for r in rows
        ],
    })


@api_bp.route("/live/center/stream")
@login_required
def api_live_center_stream():
    def event_stream():
        last_state = None
        while True:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            matches = Match.query.filter(
                Match.kickoff >= today_start,
                Match.kickoff < today_end,
            ).order_by(Match.kickoff.asc()).all()

            rows = get_live_leaderboard()

            user_preds = {
                p.match_id: {"home_tip": p.home_tip, "away_tip": p.away_tip,
                              "joker": p.joker, "points": p.points}
                for p in Prediction.query.filter_by(user_id=current_user.id).all()
                if p.match_id in [m.id for m in matches]
            }

            current_state = {
                "matches": [{"id": m.id, "home_score": m.home_score, "away_score": m.away_score, "status": m.status} for m in matches],
                "leaderboard": [{"rank": r["rank"], "user_id": r["user"].id, "username": r["user"].username, "points": r["points"]} for r in rows]
            }

            if current_state != last_state:
                payload = {
                    "ok": True,
                    "fetched_at": now.isoformat() + "Z",
                    "matches": [
                        {
                            "id": m.id, "matchday": m.matchday,
                            "home_id": m.home_team_id, "home_name": m.home_team.name,
                            "home_short": m.home_team.short_name, "home_logo": m.home_team.logo,
                            "away_id": m.away_team_id, "away_name": m.away_team.name,
                            "away_short": m.away_team.short_name, "away_logo": m.away_team.logo,
                            "kickoff": m.kickoff.isoformat() + "Z",
                            "home_score": m.home_score, "away_score": m.away_score,
                            "status": m.status,
                            "user_pred": user_preds.get(m.id),
                        }
                        for m in matches
                    ],
                    "leaderboard": [
                        {
                            "rank": r["rank"], "user_id": r["user"].id,
                            "username": r["user"].username, "avatar": r["user"].avatar,
                            "points": r["points"], "exact": r["exact"],
                            "diff": r["diff"], "tendency": r["tendency"],
                            "wrong": r["wrong"],
                            "is_me": r["user"].id == current_user.id,
                        }
                        for r in rows
                    ],
                }
                yield f"data: {_json_lib.dumps(payload)}\n\n"
                last_state = current_state

            time.sleep(5)

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@api_bp.route("/live/matchday/<int:matchday>")
@login_required
def api_live_matchday(matchday):
    res = fetch_live_match_updates(matchday=matchday)
    matches = Match.query.filter_by(matchday=matchday).order_by(Match.kickoff).all()
    return jsonify({
        "ok": True,
        "fetched_at": datetime.now(timezone.utc).isoformat() + "Z",
        "updated": res.get("updated", 0),
        "live_count": res.get("live", 0),
        "matches": [
            {
                "id": m.id, "home": m.home_team.short_name,
                "away": m.away_team.short_name,
                "home_logo": m.home_team.logo, "away_logo": m.away_team.logo,
                "kickoff": m.kickoff.isoformat(),
                "home_score": m.home_score, "away_score": m.away_score,
                "status": m.status,
            }
            for m in matches
        ],
    })


@api_bp.route("/matches/<int:matchday>")
def api_matches(matchday):
    matches = Match.query.filter_by(matchday=matchday).all()
    return jsonify([
        {
            "id": m.id, "matchday": m.matchday,
            "home": m.home_team.name, "away": m.away_team.name,
            "home_logo": m.home_team.logo, "away_logo": m.away_team.logo,
            "kickoff": m.kickoff.isoformat(),
            "home_score": m.home_score, "away_score": m.away_score,
            "status": m.status,
        } for m in matches
    ])


@api_bp.route("/push/subscribe", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def push_subscribe():
    sub = request.get_json()
    current_user.push_subscription = str(sub) if sub else None
    db.session.commit()
    return jsonify({"ok": True})
