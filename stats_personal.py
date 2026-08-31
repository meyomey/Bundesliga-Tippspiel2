"""Persoenliche Spieler-Statistiken: Trend, Tipp-Stil, Tipp-Verteilung, Stats 2.0.

 Ausgelagert aus stats.py (Refactoring 31.08.2026); stats.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from sqlalchemy import func

from extensions import db
from models import User, Match, Prediction
from scoring import get_leaderboard
from competition_helpers import get_active_competition

# ============================================================ Trend-Tracking -
def get_user_trend(user_id, last_n_matchdays=8):
    """Punkte-Verlauf ueber die letzten N Spieltage + Rang-Entwicklung."""
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=user_id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    preds = q.all()
    finished_preds = [p for p in preds if p.match.status == "finished"]

    md_points = {}
    for p in finished_preds:
        md_points.setdefault(p.match.matchday, 0)
        md_points[p.match.matchday] += p.points or 0

    sorted_mds = sorted(md_points.keys())
    recent_mds = sorted_mds[-last_n_matchdays:] if len(sorted_mds) > last_n_matchdays else sorted_mds
    sparkline = [md_points.get(md, 0) for md in recent_mds]

    # Rang aktuell
    current_rank = None
    for r in get_leaderboard():
        if r["user"].id == user_id:
            current_rank = r["rank"]
            break

    previous_rank = None
    if len(recent_mds) >= 2:
        previous_rank = _compute_rank_through(user_id, recent_mds[-2])

    delta = None
    if current_rank and previous_rank:
        delta = previous_rank - current_rank  # positiv = aufgestiegen

    return {
        "sparkline": sparkline,
        "recent_matchdays": recent_mds,
        "current_rank": current_rank,
        "previous_rank": previous_rank,
        "delta": delta,
    }


def _compute_rank_through(user_id, max_matchday):
    """Berechnet den Rang eines Users bis zu einem bestimmten Spieltag."""
    all_users = User.query.all()
    user_points = {}
    for u in all_users:
        comp = get_active_competition()
        pts_q = db.session.query(func.coalesce(func.sum(Prediction.points), 0)) \
            .join(Match, Prediction.match_id == Match.id) \
            .filter(Prediction.user_id == u.id, Match.matchday <= max_matchday,
                    Match.status == "finished")
        if comp:
            pts_q = pts_q.filter(Match.competition_id == comp.id)
        pts = pts_q.scalar() or 0
        user_points[u.id] = pts

    sorted_users = sorted(user_points.items(), key=lambda x: -x[1])
    for rank, (uid, _) in enumerate(sorted_users, 1):
        if uid == user_id:
            return rank
    return None


# ============================================================ Tipp-Stil-Insights -
def get_user_insights(user):
    """Analysiert den Tipp-Stil eines Users."""
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=user.id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    preds = q.all()
    finished = [p for p in preds if p.match.status == "finished"]
    if not finished:
        return None

    # Häufigster Tipp
    tip_counts = {}
    for p in finished:
        key = f"{p.home_tip}:{p.away_tip}"
        tip_counts[key] = tip_counts.get(key, 0) + 1

    most_common = max(tip_counts, key=tip_counts.get)
    most_common_count = tip_counts[most_common]
    most_common_pct = round(most_common_count / len(finished) * 100)

    # Tendenz-Verteilung
    home_wins = sum(1 for p in finished if p.home_tip > p.away_tip)
    draws = sum(1 for p in finished if p.home_tip == p.away_tip)
    away_wins = sum(1 for p in finished if p.home_tip < p.away_tip)
    total = len(finished)

    # Durchschnitt Punkte
    total_pts = sum(p.points or 0 for p in finished)
    avg_pts = round(total_pts / total, 1) if total else 0

    # Bester / schlechtester Tipp
    scored = [(p, p.points or 0) for p in finished if p.points is not None]
    best = max(scored, key=lambda x: x[1])[0] if scored else None
    worst = min(scored, key=lambda x: x[1])[0] if scored else None

    return {
        "most_common_tip": most_common,
        "most_common_count": most_common_count,
        "most_common_pct": most_common_pct,
        "tendency_pct": {
            "home": round(home_wins / total * 100),
            "draw": round(draws / total * 100),
            "away": round(away_wins / total * 100),
        },
        "avg_points_per_match": avg_pts,
        "best": best,
        "worst": worst,
    }


# ============================================================ Match-Insights -
def get_match_tip_distribution(match_id, exclude_user_id=None, active_only=True):
    """Tipp-Verteilung fuer ein Spiel.

    Standardmaessig werden nur aktive Mitspieler gezaehlt; reine Admin-Konten
    und deaktivierte Bots fallen damit heraus. Fuer die Matchdetail-Seite kann
    ``exclude_user_id`` gesetzt werden, damit der Block "Wie tippen die
    anderen?" wirklich nur die anderen Spieler auswertet.
    """
    q = Prediction.query.filter_by(match_id=match_id)
    if exclude_user_id is not None:
        q = q.filter(Prediction.user_id != exclude_user_id)
    preds = q.all()

    if active_only and preds:
        from scoring import filter_active_users
        active_ids = {u.id for u in filter_active_users([p.user for p in preds if p.user])}
        preds = [p for p in preds if p.user_id in active_ids]

    empty = {
        "home": 0, "draw": 0, "away": 0,
        "total": 0, "n_total": 0,
        "tendency_pct": {"home": 0, "draw": 0, "away": 0},
        "avg_home": 0, "avg_away": 0,
        "scores": {}, "all_combos": [],
        "most_common_tip": None, "most_common_count": 0, "most_common_pct": 0,
    }
    if not preds:
        return empty

    home = sum(1 for p in preds if p.home_tip > p.away_tip)
    draw = sum(1 for p in preds if p.home_tip == p.away_tip)
    away = sum(1 for p in preds if p.home_tip < p.away_tip)
    total = len(preds)

    avg_h = round(sum(p.home_tip for p in preds) / total, 1)
    avg_a = round(sum(p.away_tip for p in preds) / total, 1)

    scores = {}
    for p in preds:
        key = f"{p.home_tip}:{p.away_tip}"
        scores[key] = scores.get(key, 0) + 1

    all_combos = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    most_common_tip, most_common_count = all_combos[0]

    # Berechne Prozentwerte für die UI
    total_for_pct = max(total, 1)
    tendency_pct = {
        "home": round(home / total_for_pct * 100),
        "draw": round(draw / total_for_pct * 100),
        "away": round(away / total_for_pct * 100),
    }
    return {
        "home": home, "draw": draw, "away": away,
        "total": total, "n_total": total,
        "tendency_pct": tendency_pct,
        "avg_home": avg_h, "avg_away": avg_a,
        "scores": scores, "all_combos": all_combos,
        "most_common_tip": most_common_tip,
        "most_common_count": most_common_count,
        "most_common_pct": round(most_common_count / total_for_pct * 100),
    }


# ============================================================ Stats 2.0 -
def get_user_stats_20(user):
    """Spassige Zusatz-Statistiken fuer das Dashboard."""
    from scoring import classify_prediction
    from competition_helpers import get_active_competition
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=user.id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    preds = q.all()
    finished = [p for p in preds if p.match and p.match.status == "finished"]

    # Serien ueber Kickoff sortiert
    streak_best = 0
    streak_current = 0
    dry_best = 0
    dry_current = 0
    upset_hits = 0
    home_bias = draw_bias = away_bias = 0
    team_points = {}

    for p in sorted(finished, key=lambda x: x.match.kickoff):
        kind = classify_prediction(p, p.match)
        pts = p.points or 0
        if p.home_tip > p.away_tip:
            home_bias += 1
        elif p.home_tip == p.away_tip:
            draw_bias += 1
        else:
            away_bias += 1
        team_points[p.match.home_team.short_name] = team_points.get(p.match.home_team.short_name, 0) + pts
        team_points[p.match.away_team.short_name] = team_points.get(p.match.away_team.short_name, 0) + pts

        if pts > 0:
            streak_current += 1
            dry_current = 0
            streak_best = max(streak_best, streak_current)
        else:
            dry_current += 1
            streak_current = 0
            dry_best = max(dry_best, dry_current)

        # Upset-Hit: auf klaren Außensieg oder überraschendes Remis getippt und Punkte geholt
        if pts > 0 and ((p.home_tip < p.away_tip and p.match.home_score > p.match.away_score) is False):
            if abs((p.home_tip - p.away_tip)) >= 2 or (p.home_tip == p.away_tip and p.match.home_score == p.match.away_score):
                upset_hits += 1

    total = len(finished)
    favorite_score_team = None
    if team_points:
        favorite_score_team = max(team_points.items(), key=lambda x: x[1])

    return {
        "best_point_streak": streak_best,
        "current_point_streak": streak_current,
        "longest_dry_run": dry_best,
        "upset_hits": upset_hits,
        "home_bias": round(home_bias / total * 100) if total else 0,
        "draw_bias": round(draw_bias / total * 100) if total else 0,
        "away_bias": round(away_bias / total * 100) if total else 0,
        "favorite_score_team": favorite_score_team,
        "finished_count": total,
    }

