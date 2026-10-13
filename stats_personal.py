"""Persoenliche Spieler-Statistiken: Trend, Tipp-Stil, Tipp-Verteilung, Stats 2.0.

 Ausgelagert aus stats.py (Refactoring 31.08.2026); stats.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from sqlalchemy import func

from extensions import db
from models import User, Match, Prediction
from scoring import get_leaderboard
from competition_helpers import get_active_competition, filter_matches_for_active_competition

# ============================================================ Trend-Tracking -
def rank_map_through(max_matchday):
    """(94) Rang ALLER User bis inklusive Spieltag `max_matchday` — EINE
    Aggregat-Query statt vormals N Punktsummen-Queries pro User.

    Rueckgabe: {user_id: rank}. User ohne gewertete Tipps zaehlen mit 0
    Punkten mit (wie vorher); Tie-Break user_id aufsteigend (= alte
    User.query.all()-Reihenfolge).
    """
    comp = get_active_competition()
    q = (
        db.session.query(
            Prediction.user_id,
            func.coalesce(func.sum(Prediction.points), 0).label("pts"),
        )
        .join(Match, Prediction.match_id == Match.id)
        .filter(Match.matchday <= max_matchday, Match.status == "finished")
    )
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    punkte = {uid: int(pts or 0) for uid, pts in q.group_by(Prediction.user_id).all()}
    for (uid,) in db.session.query(User.id):
        punkte.setdefault(uid, 0)
    rangfolge = sorted(punkte.items(), key=lambda kv: (-kv[1], kv[0]))
    return {uid: rank for rank, (uid, _) in enumerate(rangfolge, 1)}


def vor_spieltag_rangkarte():
    """Referenz-Rangkarte der Vorplatzierungs-Pfeile + Spieltags-Nummer.

    (119) Rangkarte aus ``get_leaderboard(bis_matchday=...)`` — EXAKT die
    Sortierkette der aktuellen Tabelle (inkl. Sonderpunkte/Tie-Break-Kette),
    damit Pfeil und Platz nie auseinanderlaufen.

    (120) Referenz-Zeitpunkt, Nutzerkorrektur zu (119):
    - Läuft ein neuerer Spieltag (irgendein fertiges Spiel hinter dem letzten
      VOLLSTÄNDIGEN Spieltag N): Referenz = Stand nach N → die Pfeile zeigen
      die Bewegung des laufenden Spieltags.
    - Liegt der letzte vollständige Spieltag N noch ohne Nachfolger-Ergebnis
      (Lücke zwischen den Spieltagen): Referenz = Stand nach N−1 → die
      Bewegung von Spieltag N bleibt sichtbar (wie die TV-Tabelle), statt
      überall „unverändert" anzuzeigen.
    - Erst wenn NUR Spieltag 1 fertig ist, gibt es noch keine Referenz
      (vorher gibt es nichts Vergleichbares) → (None, None).
    Quelle für N ist ``abgeschlossene_spieltage`` — dieselbe wie die
    Sieger-Ansage (115).
    """
    comp = get_active_competition()
    if not comp:
        return None, None
    from matchday_announce import abgeschlossene_spieltage
    fertige = abgeschlossene_spieltage(comp.id)
    if not fertige:
        return None, None
    letzter = fertige[-1]
    f_q = db.session.query(func.max(Match.matchday)).filter(
        Match.status == "finished")
    f_q = filter_matches_for_active_competition(f_q)
    frischester = f_q.scalar()
    if frischester is not None and frischester > letzter:
        ref_md = letzter            # laufender ST: seine Bewegung zeigen
    elif letzter > 1:
        ref_md = letzter - 1        # Lücke: Bewegung des fertigen ST halten
    else:
        return None, None           # nur ST 1 fertig → noch keine Pfeile
    ref_rows = get_leaderboard(bis_matchday=ref_md)
    return {r["user"].id: r["rank"] for r in ref_rows}, ref_md


def rang_deltas_berechnen(rows):
    """(119) Pfeil-Deltas fuer Ranglisten-Zeilen (EINMAL je Aufruf).

    Liefert ({user_id: {"delta": int|None, "prev_rank": int|None}}, ref_md):
    delta > 0 = Plaetze gut, delta < 0 = Plaetze schlechter, delta None =
    keine Referenz (neu in der Rangliste). ({}, None), wenn kein Spieltag
    vollstaendig abgeschlossen ist.
    """
    prev_map, ref_md = vor_spieltag_rangkarte()
    if prev_map is None:
        return {}, None
    deltas = {}
    for r in rows:
        prev = prev_map.get(r["user"].id)
        if prev is None:
            deltas[r["user"].id] = {"delta": None, "prev_rank": None}
        else:
            deltas[r["user"].id] = {"delta": prev - r["rank"], "prev_rank": prev}
    return deltas, ref_md


def get_user_trend(user_id, last_n_matchdays=8, rows=None,
                   prev_rank_map=None, prev_map_md=None):
    """Punkte-Verlauf ueber die letzten N Spieltage + Rang-Entwicklung."""
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=user_id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    # (94) joinedload: ohne ihn liefert p.match pro Tipp 1 Query — bei 108
    # Tipps je Spieler waren das 1500+ Match-Queries pro Ranglisten-Aufruf!
    preds = q.options(db.joinedload(Prediction.match)).all()
    finished_preds = [p for p in preds if p.match.status == "finished"]

    md_points = {}
    for p in finished_preds:
        md_points.setdefault(p.match.matchday, 0)
        md_points[p.match.matchday] += p.points or 0

    sorted_mds = sorted(md_points.keys())
    recent_mds = sorted_mds[-last_n_matchdays:] if len(sorted_mds) > last_n_matchdays else sorted_mds
    sparkline = [md_points.get(md, 0) for md in recent_mds]

    # Rang aktuell — (94) fertige Zeilen nutzen, wenn die Route sie hat
    # (vorher: erneute get_leaderboard()-Vollberechnung PRO Zeile!)
    if rows is not None:
        current_rank = next(
            (r.get("rank") for r in rows if r["user"].id == user_id), None)
    else:
        current_rank = None
        for r in get_leaderboard():
            if r["user"].id == user_id:
                current_rank = r["rank"]
                break

    # (119) Referenz EINHEITLICH ueber vor_spieltag_rangkarte (letzter
    # vollstaendiger Spieltag, get_leaderboard-Sortierkette) — davor:
    # zweitletzter Tipp-Spieltag via _compute_rank_through, was zwischen
    # den Spieltagen einen Spieltag zu weit hinten lag. prev_map_md ist
    # nur noch Informationsparameter (Kompatibilitaet der Signatur).
    previous_rank = None
    if prev_rank_map is not None:
        previous_rank = prev_rank_map.get(user_id)
    else:
        ref_map, _ref_md = vor_spieltag_rangkarte()
        previous_rank = ref_map.get(user_id) if ref_map else None

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
    """Rang eines Users bis zu einem Spieltag.

    (94) Duenner Wrapper um rank_map_through — die alte Schleife führte PRO
    User eine eigene SUM-Query aus (N Queries pro Aufruf); jetzt eine
    Aggregat-Query fuer alle User gleichzeitig.
    """
    return rank_map_through(max_matchday).get(user_id)


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

