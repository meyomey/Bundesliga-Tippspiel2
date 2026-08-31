"""OpenLigaDB-Client: OLB-Helfer, OLB-Sync, Purge, Nachzug, sync_results-Orchestrierung.

 Ausgelagert aus sync.py (Refactoring 31.08.2026); sync.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from extensions import db
from models import Match, Prediction, Comment, Competition
from match_results import apply_match_update

from sync_shared import (
    current_sync_season_code, _resolve_or_create_team_from_olb, _ensure_competition_team,
    _find_existing_match, _purge_stale_matches_for_comp, _OLB_TEAM_MAP,
    store_sync_result, _olb_get, _olb_team_name,
)
from sync_football_data import sync_with_football_data

# ---------------------------------------------------------- OpenLigaDB Helper -
def _olb_match_id(md):
    return _olb_get(md, "matchID", "MatchID")


def _olb_group_order_id(md, default=1):
    grp = _olb_get(md, "group", "Group", default={}) or {}
    return _olb_get(grp, "groupOrderID", "GroupOrderID", default=default)


def _olb_kickoff(md):
    return _olb_get(md, "matchDateTimeUTC", "MatchDateTimeUTC",
                    "matchDateTime", "MatchDateTime")


def _olb_is_finished(md):
    return bool(_olb_get(md, "matchIsFinished", "MatchIsFinished", default=False))


def _olb_results(md):
    return _olb_get(md, "matchResults", "MatchResults", default=[]) or []


def _olb_result_type_id(res):
    return _olb_get(res, "resultTypeID", "ResultTypeID")


def _olb_score(res):
    return (
        _olb_get(res, "pointsTeam1", "PointsTeam1"),
        _olb_get(res, "pointsTeam2", "PointsTeam2"),
    )


def sync_with_openligadb():
    """Fallback-Sync gegen OpenLigaDB.

    Wird verwendet, wenn football-data.org keinen Token hat, das
    Rate-Limit erreicht ist oder ein Fehler auftritt. OpenLigaDB
    braucht keine Authentifizierung, liefert aber keine Live-Daten
    (nur Endergebnisse).
    """
    season = current_sync_season_code()

    try:
        url = f"https://api.openligadb.de/getmatchdata/bl1/{season}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return {"ok": False, "msg": f"OpenLigaDB: HTTP {r.status_code}"}
        data = r.json()
    except Exception as e:
        return {"ok": False, "msg": f"OpenLigaDB Fehler: {e}"}

    comp_obj = Competition.query.filter_by(code="BL1", is_active=True).first()
    comp_id = comp_obj.id if comp_obj else 1

    updated = 0
    created = 0
    skipped = 0
    new_teams = 0
    current_ext_ids = set()
    affected_match_ids = set()

    for md in data:
        match_id_raw = _olb_match_id(md)
        if match_id_raw is None:
            skipped += 1
            continue
        ext_id = f"oldb:{match_id_raw}"
        current_ext_ids.add(ext_id)

        home_obj = _olb_get(md, "team1", "Team1")
        away_obj = _olb_get(md, "team2", "Team2")
        home_name = _olb_team_name(home_obj)
        away_name = _olb_team_name(away_obj)
        if not home_name or not away_name:
            skipped += 1
            continue

        home_team, home_created = _resolve_or_create_team_from_olb(home_obj)
        away_team, away_created = _resolve_or_create_team_from_olb(away_obj)
        if home_created or away_created:
            new_teams += int(bool(home_created)) + int(bool(away_created))
        if not home_team or not away_team:
            skipped += 1
            current_app.logger.warning(f"OpenLigaDB Sync: Team nicht erkannt: {home_name} / {away_name}")
            continue
        _ensure_competition_team(comp_id, home_team)
        _ensure_competition_team(comp_id, away_team)

        kickoff_str = _olb_kickoff(md)
        if not kickoff_str:
            skipped += 1
            continue
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except Exception:
            skipped += 1
            continue

        matchday_num = _olb_group_order_id(md, default=1)
        existing = _find_existing_match(comp_id, ext_id, matchday_num, home_team, away_team, source_prefix="oldb")
        is_finished = _olb_is_finished(md)
        our_status = "finished" if is_finished else "scheduled"

        home_score = None
        away_score = None
        if is_finished:
            results = _olb_results(md)
            for res in results:
                if _olb_result_type_id(res) == 2:
                    home_score, away_score = _olb_score(res)
                    break
            if home_score is None and results:
                home_score, away_score = _olb_score(results[-1])

        if existing:
            old_status, old_h, old_a = existing.status, existing.home_score, existing.away_score
            existing.external_id = ext_id
            existing.matchday = matchday_num
            existing.home_team_id = home_team.id
            existing.away_team_id = away_team.id
            apply_match_update(
                existing,
                home_score=home_score if home_score is not None else None,
                away_score=away_score if home_score is not None else None,
                status=our_status,
                kickoff=kickoff,
                is_live=False,
            )
            if old_status != our_status or old_h != existing.home_score or old_a != existing.away_score:
                affected_match_ids.add(existing.id)
            updated += 1
        else:
            existing = Match(
                competition_id=comp_id,
                matchday=matchday_num,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                kickoff=kickoff,
                home_score=home_score,
                away_score=away_score,
                status=our_status,
                external_id=ext_id,
                is_live=False,
            )
            db.session.add(existing)
            db.session.flush()
            if our_status == "finished":
                affected_match_ids.add(existing.id)
            created += 1

    purged_stale = _purge_stale_matches_for_comp(comp_id, current_ext_ids) if current_ext_ids else 0

    db.session.commit()

    if purged_stale > 0:
        from scoring import recalculate_all_points
        from badges import check_and_award_badges
        recalculate_all_points()
        check_and_award_badges()
    elif affected_match_ids:
        from scoring import recalculate_matches_points
        from badges import check_and_award_badges
        from models import User
        affected_users = recalculate_matches_points(affected_match_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)

    msg = f"OpenLigaDB: {created} neu, {updated} aktualisiert"
    if new_teams:
        msg += f", {new_teams} Team(s) angelegt"
    if purged_stale:
        msg += f", {purged_stale} veraltete Spiele entfernt"
    if skipped:
        msg += f", {skipped} übersprungen"
    return {
        "ok": True,
        "source": "openligadb",
        "created": created,
        "updated": updated,
        "new_teams": new_teams,
        "purged_stale": purged_stale,
        "skipped": skipped,
        "msg": msg,
    }


def _purge_external_other_than(source):
    """Loescht Matches von anderen Quellen als der angegebenen."""
    all_matches = Match.query.filter(Match.external_id.isnot(None)).all()
    prefix = f"{source}:"
    to_delete = [m for m in all_matches if not m.external_id.startswith(prefix)]
    if not to_delete:
        return 0
    ids = [m.id for m in to_delete]
    Prediction.query.filter(Prediction.match_id.in_(ids)).delete(synchronize_session=False)
    Comment.query.filter(Comment.match_id.in_(ids)).delete(synchronize_session=False)
    Match.query.filter(Match.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return len(to_delete)


def _fill_missing_from_openligadb():
    """Versucht, fehlende Ergebnisse von OpenLigaDB zu holen."""
    season = current_sync_season_code()
    missing = Match.query.filter(
        Match.status == "scheduled",
        Match.kickoff < datetime.now(timezone.utc) - timedelta(hours=3),
        Match.external_id.isnot(None),
    ).all()

    if not missing:
        return 0

    try:
        url = f"https://api.openligadb.de/getmatchdata/bl1/{season}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return 0
        data = r.json()
    except Exception:
        return 0

    filled = 0
    affected_match_ids = set()
    for md in data:
        if not _olb_is_finished(md):
            continue
        match_id_raw = _olb_match_id(md)
        if match_id_raw is None:
            continue
        ext_id = f"oldb:{match_id_raw}"
        home_name = _olb_team_name(_olb_get(md, "team1", "Team1"))
        away_name = _olb_team_name(_olb_get(md, "team2", "Team2"))
        if not home_name or not away_name:
            continue
        match = Match.query.filter(
            (Match.external_id == ext_id) |
            ((Match.home_team.has(short_name=_OLB_TEAM_MAP.get(home_name, ""))) &
             (Match.away_team.has(short_name=_OLB_TEAM_MAP.get(away_name, ""))) &
             (Match.matchday == _olb_group_order_id(md, default=0)))
        ).first()

        if match and match.status == "scheduled":
            results = _olb_results(md)
            h_score = a_score = None
            for res in results:
                if _olb_result_type_id(res) == 2:
                    h_score, a_score = _olb_score(res)
                    break
            if h_score is None and results:
                h_score, a_score = _olb_score(results[-1])
            if h_score is not None and a_score is not None:
                apply_match_update(match, home_score=h_score, away_score=a_score, status="finished", is_live=False)
                affected_match_ids.add(match.id)
                filled += 1

    if filled:
        from scoring import recalculate_matches_points
        from badges import check_and_award_badges
        from models import User
        affected_users = recalculate_matches_points(affected_match_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)
    return filled


def sync_results():
    """Haupt-Entry-Point für den Ergebnis-Sync.

    Strategie:
      1. **PRIMÄR:** football-data.org (Live-Daten, exakte Status)
      2. **FALLBACK:** OpenLigaDB (kein Token nötig, aber nur Endergebnisse)

    Wenn FD einen Token hat und funktioniert, wird OLB gar nicht erst
    aufgerufen. Andernfalls (kein Token, Rate-Limit, Netzwerkfehler …)
    übernimmt OLB.
    """
    # --- 1. football-data.org versuchen ---
    res_fd = sync_with_football_data()
    if res_fd.get("ok"):
        # Sicherheitsnetz: faellige Spiele ohne Ergebnis aus OpenLigaDB nachziehen,
        # damit sie nicht dauerhaft auf "scheduled" stehen bleiben.
        try:
            filled = _fill_missing_from_openligadb()
            if filled:
                res_fd["msg"] += f" · {filled} Ergebnis(se) via OpenLigaDB nachgezogen"
        except Exception as e:
            current_app.logger.warning(f"OpenLigaDB-Nachzug fehlgeschlagen: {e}")
        current_app.logger.info(f"✅ Sync via football-data.org: {res_fd.get('msg')}")
        store_sync_result(res_fd)
        return res_fd

    fd_reason = res_fd.get("msg", "unbekannter Fehler")
    current_app.logger.warning(
        f"⚠️ football-data.org nicht verfügbar ({fd_reason}) – "
        f"fallback auf OpenLigaDB …"
    )

    # --- 2. OpenLigaDB als Fallback ---
    res_olb = sync_with_openligadb()
    if res_olb.get("ok"):
        current_app.logger.info(f"✅ Sync via OpenLigaDB (Fallback): {res_olb.get('msg')}")
        # Hinweis im UI, falls FD nicht konfiguriert ist
        hint = ""
        if "Token" in fd_reason or "token" in fd_reason:
            hint = " · Tipp: Setze einen football-data.org-Token in Admin → Einstellungen für Live-Daten."
        result = {
            "ok": True,
            "source": "openligadb",
            "created": res_olb.get("created", 0),
            "updated": res_olb.get("updated", 0),
            "new_teams": res_olb.get("new_teams", 0),
            "purged_stale": res_olb.get("purged_stale", 0),
            "skipped": res_olb.get("skipped", 0),
            "msg": f"{res_olb['msg']} (Fallback – football-data.org: {fd_reason}){hint}",
        }
        store_sync_result(result)
        return result

    # --- 3. Beide fehlgeschlagen ---
    result = {
        "ok": False,
        "source": "none",
        "msg": (
            f"❌ Beide Datenquellen fehlgeschlagen.  "
            f"football-data.org: {res_fd.get('msg')}  |  "
            f"OpenLigaDB: {res_olb.get('msg')}"
        ),
    }
    store_sync_result(result)
    return result


