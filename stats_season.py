"""Saison-Statistiken: Sondertipp-Auswertung, Ewige Tabelle, Saisonarchiv.

 Ausgelagert aus stats.py (Refactoring 31.08.2026); stats.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

import json

from extensions import db
from models import SpecialPrediction, SeasonArchive
from scoring import get_setting, get_leaderboard, is_bot_user
from competition_helpers import (
    get_active_competition, filter_competition_scoped,
)

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


