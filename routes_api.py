"""API-Routes: JSON-Endpunkte für Rangliste, Tipps, Live-Updates."""
from datetime import datetime, timedelta, timezone
import time
import json as _json_lib

from flask import (
    Blueprint, jsonify, request, Response,
)
from flask_login import login_required, current_user

from extensions import db, limiter
from models import Match, Prediction, User, Competition
from scoring import (
    get_setting, get_live_leaderboard, calculate_points,
    recalculate_all_points, locked_joker_conflict, keep_single_joker,
)
from sync import fetch_live_standings, fetch_live_match_updates
from stats import get_current_matchday
from badges import check_and_award_badges
from competition_helpers import get_active_competition, active_match_query, filter_matches_for_active_competition


api_bp = Blueprint("api", __name__)


def _live_minute_for_match(match, now=None):
    """Liefert eine anzeigbare Spielminute fuer Live-Spiele.

    Wenn die Datenquelle eine Minute liefert, nutzen wir diese. Falls nicht,
    schaetzen wir aus der Anstosszeit. Das ist fuer die Anzeige besser als gar
    keine Minute und wird beim naechsten API-Update wieder aktualisiert.
    """
    if not match or match.status != "live":
        return None
    if match.minute is not None:
        try:
            return max(1, int(match.minute))
        except (TypeError, ValueError):
            pass
    kickoff = match.kickoff
    if not kickoff:
        return None
    now = now or datetime.now(timezone.utc)
    if kickoff.tzinfo is None:
        now_cmp = now.replace(tzinfo=None)
    else:
        now_cmp = now
    minutes = int((now_cmp - kickoff).total_seconds() // 60) + 1
    if minutes < 1:
        return None
    # Ohne echte Nachspiel-/Pauseninformationen nur eine robuste Anzeige.
    return min(minutes, 90)


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
    match = db.get_or_404(Match, match_id)
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
        conflict = locked_joker_conflict(current_user.id, match.matchday, match.competition_id, match_id)
        if conflict:
            return jsonify({
                "ok": False,
                "error": "Joker kann nicht mehr verschoben werden – das bisherige Joker-Spiel hat bereits begonnen.",
            }), 400
        existing = Prediction.query.join(Match).filter(
            Prediction.user_id == current_user.id,
            Prediction.joker.is_(True),
            Match.matchday == match.matchday,
            Match.competition_id == match.competition_id,
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
    if use_joker:
        keep_single_joker(current_user.id, match.matchday, match.competition_id, match_id)
    db.session.commit()
    check_and_award_badges(users=[current_user])

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

    today_q = Match.query.filter(
        Match.kickoff >= today_start,
        Match.kickoff < today_end,
    )
    today_matches = filter_matches_for_active_competition(today_q).all()
    matchdays = sorted(set(m.matchday for m in today_matches))

    sync_info = []
    for md in matchdays:
        res = fetch_live_match_updates(matchday=md)
        if res.get("ok"):
            sync_info.append(f"ST{md}: {res.get('updated', 0)} updates, {res.get('live', 0)} live")

    matches_q = Match.query.filter(
        Match.kickoff >= today_start,
        Match.kickoff < today_end,
    )
    matches = filter_matches_for_active_competition(matches_q).order_by(Match.kickoff.asc()).all()

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
                "status": m.status, "minute": _live_minute_for_match(m, now),
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
    """SSE ist auf Passenger/Plesk bewusst deaktiviert.

    Hintergrund: Ein unendlicher Server-Sent-Events-Stream belegt bei
    klassischen WSGI-/Passenger-Setups dauerhaft einen Worker. Mehrere offene
    Live-Center-Seiten koennen dadurch die App blockieren bzw. wie einen
    Absturz wirken lassen. Das Live-Center nutzt deshalb stabiles HTTP-Polling.
    Alte gecachte Clients erhalten hier sofort 204 und fallen per JS-Fallback
    auf Polling zurueck.
    """
    return Response(status=204, headers={"Cache-Control": "no-cache"})


@api_bp.route("/live/matchday/<int:matchday>")
@login_required
def api_live_matchday(matchday):
    res = fetch_live_match_updates(matchday=matchday)
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff).all()
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
                "status": m.status, "minute": _live_minute_for_match(m),
            }
            for m in matches
        ],
    })


@api_bp.route("/tip-overview/live/<int:matchday>")
@login_required
def api_tip_overview_live(matchday):
    """Live-Punkte fuer die Tippuebersicht ohne kompletten Page-Reload."""
    sort = request.args.get("sort", "total")
    if sort not in ("total", "matchday", "name"):
        sort = "total"
    total_rows = get_live_leaderboard()
    md_rows = get_live_leaderboard(matchday=matchday)
    total_map = {r["user"].id: r for r in total_rows}
    md_map = {r["user"].id: r for r in md_rows}
    user_ids = set(total_map) | set(md_map)
    rows = []
    for uid in user_ids:
        tr = total_map.get(uid)
        mr = md_map.get(uid)
        user = (tr or mr)["user"]
        rows.append({
            "user_id": uid,
            "username": user.username,
            "total_points": tr["points"] if tr else 0,
            "matchday_points": mr["points"] if mr else 0,
            "rank": tr["rank"] if tr else None,
        })
    if sort == "matchday":
        rows.sort(key=lambda r: (-r["matchday_points"], -r["total_points"], r["username"].lower()))
    elif sort == "name":
        rows.sort(key=lambda r: r["username"].lower())
    else:
        rows.sort(key=lambda r: (-r["total_points"], -r["matchday_points"], r["username"].lower()))
    for i, r in enumerate(rows):
        r["order"] = i
    return jsonify({"ok": True, "rows": rows})


@api_bp.route("/matches/<int:matchday>")
def api_matches(matchday):
    matches = active_match_query().filter_by(matchday=matchday).all()
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
