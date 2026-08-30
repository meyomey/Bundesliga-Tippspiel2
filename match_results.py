"""Zentrale Ergebnis-/Status-Aktualisierung fuer Matches.

Alle Pfade, die Ergebnisse setzen, sollen ueber diese Helfer laufen, damit
Punkte, Badges und Caches konsistent aktualisiert werden.
"""
from extensions import db
from badges import check_and_award_badges
from scoring import recalculate_all_points, recalculate_match_points, recalculate_matches_points


def apply_match_update(match, *, home_score=None, away_score=None, status=None, kickoff=None, is_live=None):
    """Aendert Match-Felder ohne Commit/Recalc.

    Gedacht fuer Bulk-Syncs. Danach `finalize_match_updates()` aufrufen.
    """
    changed = False
    if kickoff is not None and match.kickoff != kickoff:
        match.kickoff = kickoff
        changed = True
    if status is not None and match.status != status:
        match.status = status
        changed = True
    if is_live is not None and match.is_live != is_live:
        match.is_live = is_live
        changed = True
    if home_score is not None and match.home_score != home_score:
        match.home_score = home_score
        changed = True
    if away_score is not None and match.away_score != away_score:
        match.away_score = away_score
        changed = True
    return changed


def finalize_match_updates(*, recalc=True, badges=True, invalidate=True, match_ids=None, users=None):
    """Commit + optionale Folgerechnungen nach Ergebnis-/Status-Aenderungen.

    Wenn `match_ids` uebergeben wird, werden nur diese Spiele neu bepunktet.
    Ohne `match_ids` bleibt aus Rueckwaertskompatibilitaet die globale
    Neuberechnung erhalten.
    """
    affected_user_ids = set()
    if recalc and match_ids:
        affected_user_ids = recalculate_matches_points(match_ids, commit=False)
        db.session.commit()
        try:
            from scoring import recompute_matchday_winners
            recompute_matchday_winners()
        except Exception:
            pass
    else:
        db.session.commit()
        if recalc:
            recalculate_all_points()
    if badges:
        if users is None and affected_user_ids:
            from models import User
            users = User.query.filter(User.id.in_(affected_user_ids)).all()
        check_and_award_badges(users=users)
    if invalidate:
        try:
            from cache import invalidate_leaderboard
            invalidate_leaderboard()
        except Exception:
            pass


def set_match_result(match, home_score, away_score, *, status="finished", source="manual"):
    """Setzt ein Endergebnis zentral und aktualisiert alle abhaengigen Daten."""
    apply_match_update(
        match,
        home_score=home_score,
        away_score=away_score,
        status=status,
        is_live=(status == "live"),
    )
    finalize_match_updates(recalc=True, badges=True, invalidate=True, match_ids=[match.id])
    return match
