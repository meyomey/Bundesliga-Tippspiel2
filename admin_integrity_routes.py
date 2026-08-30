"""Admin: Datenintegritaets-Checks und sichere Reparaturen."""
from collections import defaultdict

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func

from audit_log import log_admin_action
from competition_helpers import active_matchdays, active_competition_teams, get_active_competition
from extensions import db
from models import User, Match, Prediction, SpecialPrediction, SpecialQuestion
from scoring import is_admin_only_user


def _duplicate_joker_groups():
    rows = (
        db.session.query(
            Prediction.user_id,
            Match.competition_id,
            Match.matchday,
            func.count(Prediction.id).label("cnt"),
        )
        .join(Match, Prediction.match_id == Match.id)
        .filter(Prediction.joker.is_(True))
        .group_by(Prediction.user_id, Match.competition_id, Match.matchday)
        .having(func.count(Prediction.id) > 1)
        .all()
    )
    return rows


def _invalid_predictions():
    return Prediction.query.filter(
        (Prediction.home_tip < 0) | (Prediction.home_tip > 30) |
        (Prediction.away_tip < 0) | (Prediction.away_tip > 30)
    ).all()


def build_integrity_report():
    """Erzeugt aktuelle Integritaetschecks ohne Daten zu veraendern."""
    comp = get_active_competition()
    checks = []

    dup_jokers = _duplicate_joker_groups()
    checks.append({
        "id": "duplicate_jokers",
        "level": "error" if dup_jokers else "ok",
        "title": "Mehrfach-Joker",
        "message": f"{len(dup_jokers)} User/Spieltag-Gruppen mit mehr als einem Joker." if dup_jokers else "Keine Mehrfach-Joker gefunden.",
        "count": len(dup_jokers),
        "repairable": bool(dup_jokers),
    })

    invalid_preds = _invalid_predictions()
    checks.append({
        "id": "invalid_predictions",
        "level": "error" if invalid_preds else "ok",
        "title": "Ungueltige Tipps",
        "message": f"{len(invalid_preds)} Tipps ausserhalb 0–30 gefunden." if invalid_preds else "Alle Tipps liegen im Bereich 0–30.",
        "count": len(invalid_preds),
        "repairable": bool(invalid_preds),
    })

    admin_paid = [u for u in User.query.filter_by(is_admin=True, has_paid=True).all() if is_admin_only_user(u)]
    checks.append({
        "id": "admin_paid",
        "level": "warn" if admin_paid else "ok",
        "title": "Reine Admins im Pott",
        "message": f"{len(admin_paid)} reine Admin-Konten sind als bezahlt markiert." if admin_paid else "Keine reinen Admin-Konten im Pott.",
        "count": len(admin_paid),
        "repairable": bool(admin_paid),
    })

    null_specials = SpecialQuestion.query.filter(SpecialQuestion.competition_id.is_(None)).count()
    checks.append({
        "id": "special_competition",
        "level": "warn" if null_specials else "ok",
        "title": "Sonderfragen ohne Wettbewerb",
        "message": f"{null_specials} Sonderfragen haben keine competition_id." if null_specials else "Alle Sonderfragen sind wettbewerbsbezogen.",
        "count": null_specials,
        "repairable": bool(null_specials and comp),
    })

    teams_current = active_competition_teams()
    team_count = len(teams_current)
    checks.append({
        "id": "team_count",
        "level": "warn" if team_count and team_count != 18 else "ok",
        "title": "Aktuelle Teams",
        "message": f"{team_count} Teams im aktiven Wettbewerb erkannt." if team_count else "Keine aktuellen Teams erkannt.",
        "count": team_count,
        "repairable": False,
    })

    match_q = Match.query
    if comp:
        match_q = match_q.filter(Match.competition_id == comp.id)
    total_matches = match_q.count()
    level = "ok" if total_matches in (0, 306) else "warn"
    checks.append({
        "id": "match_count",
        "level": level,
        "title": "Spielanzahl Saison",
        "message": f"{total_matches} Spiele vorhanden (Bundesliga-Soll: 306).",
        "count": total_matches,
        "repairable": False,
    })

    bad_matchdays = []
    for md in active_matchdays():
        q = Match.query.filter_by(matchday=md)
        if comp:
            q = q.filter(Match.competition_id == comp.id)
        c = q.count()
        if c != 9:
            bad_matchdays.append((md, c))
    checks.append({
        "id": "matchday_counts",
        "level": "warn" if bad_matchdays else "ok",
        "title": "Spiele je Spieltag",
        "message": ", ".join(f"ST {md}: {cnt}" for md, cnt in bad_matchdays[:8]) + (" …" if len(bad_matchdays) > 8 else "") if bad_matchdays else "Alle vorhandenen Spieltage haben 9 Spiele.",
        "count": len(bad_matchdays),
        "repairable": False,
    })

    missing_scores_q = Match.query.filter(
        Match.status == "finished",
        ((Match.home_score.is_(None)) | (Match.away_score.is_(None)))
    )
    if comp:
        missing_scores_q = missing_scores_q.filter(Match.competition_id == comp.id)
    missing_scores = missing_scores_q.count()
    checks.append({
        "id": "finished_missing_scores",
        "level": "error" if missing_scores else "ok",
        "title": "Beendete Spiele ohne Ergebnis",
        "message": f"{missing_scores} beendete Spiele haben kein vollstaendiges Ergebnis." if missing_scores else "Keine beendeten Spiele ohne Ergebnis.",
        "count": missing_scores,
        "repairable": False,
    })

    return checks


def run_safe_repairs():
    """Fuehrt nur risikoarme Reparaturen aus."""
    repaired = defaultdict(int)

    # Mehrfachjoker: pro Gruppe den fruehesten Datensatz behalten.
    for row in _duplicate_joker_groups():
        preds = (
            Prediction.query.join(Match)
            .filter(
                Prediction.user_id == row.user_id,
                Prediction.joker.is_(True),
                Match.competition_id == row.competition_id,
                Match.matchday == row.matchday,
            )
            .order_by(Prediction.created_at.asc(), Prediction.id.asc())
            .all()
        )
        for pred in preds[1:]:
            pred.joker = False
            repaired["duplicate_jokers"] += 1

    # Ungueltige Tipps clampen statt loeschen.
    for p in _invalid_predictions():
        p.home_tip = max(0, min(30, int(p.home_tip or 0)))
        p.away_tip = max(0, min(30, int(p.away_tip or 0)))
        repaired["invalid_predictions"] += 1

    # Reine Admins aus Pott nehmen.
    for u in User.query.filter_by(is_admin=True, has_paid=True).all():
        if is_admin_only_user(u):
            u.has_paid = False
            u.paid_at = None
            u.paid_note = None
            repaired["admin_paid"] += 1

    comp = get_active_competition()
    if comp:
        for q in SpecialQuestion.query.filter(SpecialQuestion.competition_id.is_(None)).all():
            q.competition_id = comp.id
            repaired["special_competition"] += 1
        for sp in SpecialPrediction.query.filter(SpecialPrediction.competition_id.is_(None)).all():
            if sp.question and sp.question.competition_id:
                sp.competition_id = sp.question.competition_id
                repaired["special_prediction_competition"] += 1

    db.session.commit()
    try:
        from cache import invalidate_leaderboard
        invalidate_leaderboard()
    except Exception:
        pass
    return dict(repaired)


def _admin_integrity_view():
    if request.method == "POST":
        result = run_safe_repairs()
        log_admin_action("integrity_repair", "system", None, "Datenintegritaet repariert", result)
        if result:
            flash("✅ Reparaturen ausgeführt: " + ", ".join(f"{k}: {v}" for k, v in result.items()), "success")
        else:
            flash("ℹ️ Keine reparierbaren Probleme gefunden.", "info")
        return redirect(url_for("admin.integrity"), code=303)

    checks = build_integrity_report()
    summary = {
        "errors": sum(1 for c in checks if c["level"] == "error"),
        "warnings": sum(1 for c in checks if c["level"] == "warn"),
        "ok": sum(1 for c in checks if c["level"] == "ok"),
        "repairable": sum(1 for c in checks if c.get("repairable")),
    }
    return render_template("admin/integrity.html", checks=checks, summary=summary)
