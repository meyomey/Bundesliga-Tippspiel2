"""Statistiken: Trend-Tracking, Insights, Form, H2H, Tipp-Verteilung, Wetter, Tabelle."""
import json
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import func

from extensions import db
from models import (
    User, Team, Match, Prediction, SpecialPrediction, SeasonArchive, MatchdayWinner,
)
from scoring import get_setting, get_leaderboard, classify_prediction, is_bot_user
from competition_helpers import (
    get_active_competition, filter_matches_for_active_competition,
    filter_competition_scoped,
)


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


# ============================================================ Wetter-API -
# Stadion-Koordinaten (Top-Genauigkeit, alle 18 Vereine)
STADIUM_COORDS = {
    "FCB": (48.2188, 11.6247),     # Allianz Arena
    "BVB": (51.4926, 7.4516),      # Signal Iduna Park
    "B04": (51.0383, 7.0020),      # BayArena
    "RBL": (51.3454, 12.3487),     # Red Bull Arena
    "VFB": (48.7924, 9.2320),      # MHPArena
    "SGE": (50.0686, 8.6455),      # Deutsche Bank Park
    "WOB": (52.4310, 10.6640),     # Volkswagen Arena
    "BMG": (51.1747, 6.3915),      # Borussia-Park
    "SCF": (47.9891, 7.8930),      # Europa-Park Stadion
    "FCU": (52.4574, 13.5698),     # Stadion An der Alten Försterei
    "TSG": (49.2433, 8.8603),      # PreZero Arena
    "M05": (50.0011, 8.2561),      # Mewa Arena
    "FCA": (48.3260, 10.8830),     # WWK Arena
    "SVW": (53.0789, 8.8394),      # Weserstadion
    "FCH": (48.6782, 10.1527),     # Voith-Arena
    "STP": (53.5566, 9.9647),      # Millerntor-Stadion
    "HSV": (53.5869, 9.8957),      # Volksparkstadion
    "KOE": (50.9336, 6.8769),      # RheinEnergieStadion
}


def get_match_weather(match):
    """Holt Wetter vom Open-Meteo (kostenlos, kein Key)."""
    home_short = match.home_team.short_name
    coords = STADIUM_COORDS.get(home_short)
    if not coords:
        return None

    lat, lon = coords
    kickoff = match.kickoff
    date_str = kickoff.strftime("%Y-%m-%d")

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,precipitation_probability,weather_code,wind_speed_10m"
        f"&start_date={date_str}&end_date={date_str}"
        f"&timezone=Europe/Berlin"
    )

    try:
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        hourly = data.get("hourly", {})
        hour = kickoff.hour
        times = hourly.get("time", [])

        # Finde naechsten Stundeneintrag zum Kickoff
        idx = None
        for i, t in enumerate(times):
            if t.endswith(f"T{hour:02d}:00"):
                idx = i
                break
        if idx is None:
            idx = min(hour, len(times) - 1) if times else None
        if idx is None:
            return None

        temp = hourly.get("temperature_2m", [None])[idx]
        precip = hourly.get("precipitation_probability", [None])[idx]
        code = hourly.get("weather_code", [None])[idx]
        wind = hourly.get("wind_speed_10m", [None])[idx]

        if temp is None:
            return None

        return {
            "temp": temp,
            "precip": precip,
            "code": code,
            "label": _weather_code_to_label(code) if code is not None else "—",
            "wind": wind,
        }
    except Exception:
        return None


def _weather_code_to_label(code):
    """WMO Weather interpretation codes."""
    mapping = {
        0: "☀️ Klar", 1: "🌤 Überwiegend klar", 2: "⛅ Bewölkt", 3: "☁️ Bedeckt",
        45: "🌫 Nebel", 48: "🌫 Nebel mit Reif",
        51: "🌧 Leichter Nieselregen", 53: "🌧 Nieselregen", 55: "🌧 Starker Nieselregen",
        61: "🌧 Leichter Regen", 63: "🌧 Regen", 65: "🌧 Starker Regen",
        71: "🌨 Leichter Schneefall", 73: "🌨 Schneefall", 75: "🌨 Starker Schneefall",
        80: "🌦 Regenschauer", 81: " showers", 82: "🌦 Starke Regenschauer",
        95: "⛈ Gewitter", 96: "⛈ Gewitter mit Hagel", 99: "⛈ Starke Gewitter",
    }
    return mapping.get(code, f"🌡 Code {code}")


# ==================================================== Live-Bundesliga-Tabelle -
def compute_live_standings():
    """Berechnet die aktuelle Tabelle des aktiven Wettbewerbs.

    Wichtig: Es werden nicht mehr pauschal alle Teams aus der Team-Tabelle
    angezeigt. Alte Absteiger bleiben als historische Teams in der DB, duerfen
    aber in der aktuellen Liga-Tabelle nicht erscheinen. Basis sind Teams mit
    Matches im aktiven Wettbewerb; falls noch kein Spielplan vorhanden ist,
    faellt die Funktion auf CompetitionTeam zurueck.
    """
    from models import CompetitionTeam
    from competition_helpers import get_active_competition
    comp = get_active_competition()

    match_q = Match.query
    match_q = filter_matches_for_active_competition(match_q)
    match_team_rows = match_q.with_entities(Match.home_team_id, Match.away_team_id).all()
    team_ids = {tid for row in match_team_rows for tid in row if tid}

    if not team_ids and comp:
        team_ids = {ct.team_id for ct in CompetitionTeam.query.filter_by(competition_id=comp.id).all()}

    teams = Team.query.filter(Team.id.in_(team_ids)).all() if team_ids else []
    table = {t.id: {
        "team": t, "played": 0, "won": 0, "drawn": 0, "lost": 0,
        "goals_for": 0, "goals_against": 0, "points": 0,
    } for t in teams}

    finished_q = Match.query.filter_by(status="finished")
    finished_q = filter_matches_for_active_competition(finished_q)
    finished = finished_q.all()
    for m in finished:
        if m.home_score is None or m.away_score is None:
            continue
        h = table.get(m.home_team_id)
        a = table.get(m.away_team_id)
        if not h or not a:
            continue
        h["played"] += 1
        a["played"] += 1
        h["goals_for"] += m.home_score
        h["goals_against"] += m.away_score
        a["goals_for"] += m.away_score
        a["goals_against"] += m.home_score
        if m.home_score > m.away_score:
            h["won"] += 1; h["points"] += 3; a["lost"] += 1
        elif m.home_score == m.away_score:
            h["drawn"] += 1; a["drawn"] += 1; h["points"] += 1; a["points"] += 1
        else:
            a["won"] += 1; a["points"] += 3; h["lost"] += 1

    for t in table.values():
        t["goal_diff"] = t["goals_for"] - t["goals_against"]

    rows = sorted(table.values(), key=lambda r: (
        -r["points"], -r["goal_diff"], -r["goals_for"], r["team"].name
    ))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def get_official_standings_positions():
    """Liefert offizielle Tabellenpositionen aus der externen Tabellenquelle.

    Wichtig fuer die Tippseiten: Die bisher lokal aus beendeten Matches
    berechnete Tabelle kann unvollstaendig oder durch Test-/Importdaten
    irrefuehrend sein. Auf Tippkarten zeigen wir daher nur Positionen, wenn sie
    aus der offiziellen Tabellenquelle kommen. Ist die Quelle nicht erreichbar,
    bleibt der Platz bewusst ausgeblendet statt falsch zu wirken.
    """
    try:
        from sync import fetch_live_standings
        rows, err = fetch_live_standings()
    except Exception:
        return {}
    if not rows:
        return {}
    return {r["team"].id: r for r in rows if r.get("team") and r.get("rank")}


def get_team_position(team_id):
    """Liefert die offizielle aktuelle Tabellenposition eines Teams."""
    row = get_official_standings_positions().get(team_id)
    return row["rank"] if row else None


# ============================================================== Form / H2H -
def get_team_form(team_id, limit=5):
    """Letzte N Ergebnisse eines Teams.

    Liefert eine Liste von Dicts (neuestes zuerst), z.B.:
        [{"result": "W", "opponent": <Team>, "score": "3:1",
          "home": True, "gf": 3, "ga": 1, "match": <Match>}, ...]

    Templates (schedule.html, match_detail.html, quick_tip.html) erwarten
    die Felder ``result``, ``opponent``, ``score`` und ``home``.
    """
    q = Match.query.filter(
        Match.status == "finished",
        (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
    )
    q = filter_matches_for_active_competition(q)
    finished = q.order_by(Match.kickoff.desc()).limit(limit).all()

    form = []
    for m in finished:
        is_home = m.home_team_id == team_id
        gf = m.home_score if is_home else m.away_score
        ga = m.away_score if is_home else m.home_score
        if gf is None or ga is None:
            continue
        if gf > ga:
            result = "W"
        elif gf == ga:
            result = "D"
        else:
            result = "L"
        opponent = m.away_team if is_home else m.home_team
        form.append({
            "result": result,
            "opponent": opponent,
            "score": f"{gf}:{ga}",
            "home": is_home,
            "gf": gf,
            "ga": ga,
            "match": m,
        })
    return form


def get_h2h(home_team_id, away_team_id, limit=5):
    """Historische Duelle zwischen zwei Teams."""
    q = Match.query.filter(
        Match.status == "finished",
        ((Match.home_team_id == home_team_id) & (Match.away_team_id == away_team_id))
        | ((Match.home_team_id == away_team_id) & (Match.away_team_id == home_team_id))
    )
    q = filter_matches_for_active_competition(q)
    matches = q.order_by(Match.kickoff.desc()).limit(limit).all()

    results = []
    for m in matches:
        is_normal = m.home_team_id == home_team_id
        h_score = m.home_score if is_normal else m.away_score
        a_score = m.away_score if is_normal else m.home_score
        results.append({
            "match": m,
            "home_score": h_score,
            "away_score": a_score,
            "is_home_swap": not is_normal,
        })
    return results


# ===================================================== Sondertipps Punkte -
def _normalize(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _parse_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    s = str(value).strip()
    if s.startswith("["):
        try:
            return [_normalize(v) for v in json.loads(s)]
        except Exception:
            pass
    return [_normalize(v) for v in s.split(",") if v.strip()]


def compare_special_answer(question, user_answer):
    """Vergleicht User-Antwort mit korrekter Antwort."""
    if not question.correct_answer:
        return 0
    atype = question.answer_type or "text"

    if atype == "multi_team":
        correct = set(_parse_list(question.correct_answer))
        given = set(_parse_list(user_answer))
        if not correct or not given:
            return 0
        hits = len(correct & given)
        if hits == 0:
            return 0
        per_hit = question.points_value / max(len(correct), 1)
        return int(round(per_hit * hits))

    if atype == "number":
        try:
            return question.points_value if int(user_answer) == int(question.correct_answer) else 0
        except (ValueError, TypeError):
            return 0

    return question.points_value if _normalize(user_answer) == _normalize(question.correct_answer) else 0


def evaluate_special_predictions():
    """Berechnet Punkte fuer alle Sondertipps mit gesetzter correct_answer."""
    from models import SpecialQuestion
    q_base = SpecialQuestion.query.filter(SpecialQuestion.correct_answer.isnot(None))
    questions = filter_competition_scoped(q_base, SpecialQuestion).all()
    for q in questions:
        if not q.correct_answer:
            continue
        for sp in SpecialPrediction.query.filter_by(question_id=q.id).all():
            sp.points = compare_special_answer(q, sp.answer)
    db.session.commit()


# ============================================================ Ewige Tabelle -
def get_eternal_table():
    """Aggregiert SeasonArchive ueber alle Saisons + aktuelle Saison."""
    archives = filter_competition_scoped(SeasonArchive.query, SeasonArchive).all()
    archives = [a for a in archives if a.user is not None and not is_bot_user(a.user)]
    table = {}
    for a in archives:
        uid = a.user_id
        if uid not in table:
            table[uid] = {
                "user": a.user, "seasons": 0, "points": 0,
                "exact": 0, "diff": 0, "tendency": 0, "wrong": 0,
                "best_rank": 999, "titles": 0,
            }
        t = table[uid]
        t["seasons"] += 1
        t["points"] += a.points
        t["exact"] += a.exact_count
        t["diff"] += a.diff_count
        t["tendency"] += a.tendency_count
        t["wrong"] += a.wrong_count
        if a.rank < t["best_rank"]:
            t["best_rank"] = a.rank
        if a.rank == 1:
            t["titles"] += 1

    current_season = get_setting("current_season", "2025/26")
    for stats in get_leaderboard():
        uid = stats["user"].id
        if uid not in table:
            table[uid] = {
                "user": stats["user"], "seasons": 1, "points": stats["points"],
                "exact": stats["exact"], "diff": stats["diff"],
                "tendency": stats["tendency"], "wrong": stats["wrong"],
                "best_rank": stats["rank"], "titles": 0,
                "current_season": True,
            }
        else:
            existing_seasons = {a.season for a in archives if a.user_id == uid}
            if current_season not in existing_seasons:
                t = table[uid]
                t["seasons"] += 1
                t["points"] += stats["points"]
                t["exact"] += stats["exact"]
                t["diff"] += stats["diff"]
                t["tendency"] += stats["tendency"]
                t["wrong"] += stats["wrong"]
                if stats["rank"] < t["best_rank"]:
                    t["best_rank"] = stats["rank"]

    rows = sorted(table.values(), key=lambda r: (-r["points"], -r["titles"], r["user"].username))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def archive_season(season_label):
    """Speichert die aktuelle Tabelle als Saison-Archiv."""
    rows = get_leaderboard()
    for r in rows:
        comp = get_active_competition()
        archive_q = SeasonArchive.query.filter_by(user_id=r["user"].id, season=season_label)
        if comp:
            archive_q = archive_q.filter(SeasonArchive.competition_id == comp.id)
        existing = archive_q.first()
        if existing:
            existing.rank = r["rank"]
            existing.points = r["points"]
            existing.exact_count = r["exact"]
            existing.diff_count = r["diff"]
            existing.tendency_count = r["tendency"]
            existing.wrong_count = r["wrong"]
        else:
            db.session.add(SeasonArchive(
                competition_id=comp.id if comp else None,
                user_id=r["user"].id, season=season_label,
                rank=r["rank"], points=r["points"],
                exact_count=r["exact"], diff_count=r["diff"],
                tendency_count=r["tendency"], wrong_count=r["wrong"],
            ))
    db.session.commit()


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
