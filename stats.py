"""Statistiken: Kernmodul (Misc-Helfer, Spieltags-Preview & Recap) + Fassade.

Die Fachbereiche wurden am 31.08.2026 ausgelagert (stats_personal,
stats_live, stats_season); dieses Modul re-exportiert alle Namen. Ausgelagert aus stats.py (Refactoring 31.08.2026); stats.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from datetime import datetime, timedelta, timezone

from extensions import db
from models import User, Match, Prediction
from competition_helpers import filter_matches_for_active_competition

# ============================================================ Misc Helpers -
def get_open_matches_for_user(user, max_hours=72):
    """Findet offene Spiele ohne Tipp in den naechsten Stunden."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=max_hours)
    q = Match.query.filter(
        Match.status == "scheduled",
        Match.kickoff > now,
        Match.kickoff <= horizon,
    )
    q = filter_matches_for_active_competition(q)
    matches = q.order_by(Match.kickoff.asc()).all()
    if not matches:
        return []
    tipped_ids = {p.match_id for p in user.predictions.all()}
    return [m for m in matches if m.id not in tipped_ids]


def get_current_matchday():
    """Liefert den aktuell relevanten Spieltag."""
    open_q = db.session.query(Match.matchday).filter(
        Match.status.in_(["scheduled", "live"])
    )
    open_q = filter_matches_for_active_competition(open_q)
    open_md = open_q.order_by(Match.matchday.asc()).first()
    if open_md:
        return open_md[0]
    last_q = db.session.query(Match.matchday)
    last_q = filter_matches_for_active_competition(last_q)
    last_md = last_q.order_by(Match.matchday.desc()).first()
    return last_md[0] if last_md else 1

# ============================================================ Spieltags-Preview & Recap 2.0 -
def get_matchday_preview(matchday=None):
    """Aggregierte Vorschau fuer einen Spieltag.

    Zeigt bewusst nur Community-Trends und Abgabequoten, keine individuellen
    Tipps vor Anpfiff.
    """
    from scoring import filter_active_users
    from competition_helpers import active_match_query, get_active_competition
    if matchday is None:
        matchday = get_current_matchday()
    comp = get_active_competition()
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff, Match.id).all()
    users = filter_active_users(User.query.all())
    user_ids = [u.id for u in users]
    match_ids = [m.id for m in matches]
    preds = []
    if user_ids and match_ids:
        preds = Prediction.query.filter(Prediction.user_id.in_(user_ids), Prediction.match_id.in_(match_ids)).all()

    by_match = {}
    by_user = {}
    for p in preds:
        by_match.setdefault(p.match_id, []).append(p)
        by_user.setdefault(p.user_id, []).append(p)

    rows = []
    top_match = None
    max_tips = -1
    for m in matches:
        mp = by_match.get(m.id, [])
        home = draw = away = 0
        score_counts = {}
        joker_count = 0
        for p in mp:
            if p.home_tip > p.away_tip:
                home += 1
            elif p.home_tip == p.away_tip:
                draw += 1
            else:
                away += 1
            score = f"{p.home_tip}:{p.away_tip}"
            score_counts[score] = score_counts.get(score, 0) + 1
            if p.joker:
                joker_count += 1
        total = len(mp)
        top_score = max(score_counts.items(), key=lambda x: x[1]) if score_counts else None
        row = {
            "match": m,
            "tips": total,
            "missing": max(len(users) - total, 0),
            "completion_pct": round(total / len(users) * 100) if users else 0,
            "home_pct": round(home / total * 100) if total else 0,
            "draw_pct": round(draw / total * 100) if total else 0,
            "away_pct": round(away / total * 100) if total else 0,
            "top_score": top_score[0] if top_score else "—",
            "top_score_count": top_score[1] if top_score else 0,
            "joker_count": joker_count,
            "is_open": m.is_open(),
        }
        rows.append(row)
        if total > max_tips:
            max_tips = total
            top_match = row

    missing_users = [u for u in users if len(by_user.get(u.id, [])) < len(matches)]
    return {
        "competition": comp,
        "matchday": matchday,
        "matches": rows,
        "users_count": len(users),
        "total_predictions": len(preds),
        "possible_predictions": len(users) * len(matches),
        "overall_completion_pct": round(len(preds) / (len(users) * len(matches)) * 100) if users and matches else 0,
        "missing_users": missing_users,
        "top_match": top_match,
    }


def get_matchday_recap(matchday=None):
    """Spieltag-Rueckblick fuer alle User mit Fun-Facts."""
    from scoring import filter_active_users, classify_prediction
    from competition_helpers import active_match_query, get_active_competition
    if matchday is None:
        # letzter Spieltag mit mindestens einem beendeten Spiel
        last = active_match_query().filter_by(status="finished").order_by(Match.matchday.desc()).first()
        matchday = last.matchday if last else get_current_matchday()
    comp = get_active_competition()
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff, Match.id).all()
    match_ids = [m.id for m in matches]
    users = filter_active_users(User.query.all())
    user_ids = [u.id for u in users]
    preds = []
    if match_ids and user_ids:
        preds = Prediction.query.filter(Prediction.match_id.in_(match_ids), Prediction.user_id.in_(user_ids)).options(
            db.joinedload(Prediction.match).joinedload(Match.home_team),
            db.joinedload(Prediction.match).joinedload(Match.away_team),
        ).all()

    by_user = {}
    for p in preds:
        by_user.setdefault(p.user_id, []).append(p)

    rows = []
    best_single = None
    best_joker = None
    for u in users:
        ups = by_user.get(u.id, [])
        exact = diff = tendency = wrong = pending = 0
        points = 0
        joker_points = 0
        for p in ups:
            kind = classify_prediction(p, p.match)
            if kind == "exact": exact += 1
            elif kind == "diff": diff += 1
            elif kind == "tendency": tendency += 1
            elif kind == "wrong": wrong += 1
            else: pending += 1
            pts = p.points or 0
            points += pts
            if p.joker:
                joker_points += pts
                if pts > 0 and (best_joker is None or pts > best_joker["points"]):
                    best_joker = {"user": u, "prediction": p, "points": pts}
            if pts > 0 and (best_single is None or pts > best_single["points"]):
                best_single = {"user": u, "prediction": p, "points": pts}
        rows.append({
            "user": u,
            "points": points,
            "tips": len(ups),
            "exact": exact,
            "diff": diff,
            "tendency": tendency,
            "wrong": wrong,
            "pending": pending,
            "joker_points": joker_points,
        })
    rows.sort(key=lambda r: (-r["points"], -r["exact"], -r["diff"], r["user"].username.lower()))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    finished_count = sum(1 for m in matches if m.status == "finished")
    return {
        "competition": comp,
        "matchday": matchday,
        "matches": matches,
        "finished_count": finished_count,
        "total_matches": len(matches),
        "rows": rows,
        "winner": rows[0] if rows else None,
        "best_single": best_single,
        "best_joker": best_joker,
    }

# ============================================================ Fassade -------
# Re-Exports: bestehende Importeure (from stats import ...) funktionieren
# unveraendert weiter. Neue Code-Stellen koennen direkt aus den Fachmodulen
# importieren.
from stats_personal import (  # noqa: F401
    get_user_trend, _compute_rank_through, get_user_insights,
    get_match_tip_distribution, get_user_stats_20,
)
from stats_live import (  # noqa: F401
    get_match_weather, _weather_code_to_label, compute_live_standings,
    get_official_standings_positions, get_team_position, get_team_form, get_h2h,
)
from stats_season import (  # noqa: F401
    _normalize, _parse_list, compare_special_answer, evaluate_special_predictions,
    get_eternal_table, archive_season,
)
