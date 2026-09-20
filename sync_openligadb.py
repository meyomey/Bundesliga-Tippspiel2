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
    store_sync_result, _olb_get, _olb_team_name, purge_summary_suffix,
)
from sync_football_data import sync_with_football_data

# ---------------------------------------------------------- OpenLigaDB Helper -
def _olb_match_id(md):
    return _olb_get(md, "matchID", "MatchID")


def _olb_group_order_id(md, default=1):
    grp = _olb_get(md, "group", "Group", default=None)
    if isinstance(grp, dict) and grp:
        wert = _olb_get(grp, "groupOrderID", "GroupOrderID", default=None)
        if wert is not None:
            return wert
    # (83) defensiv: manche OLB-Endpunkte liefern das Feld auch flach
    flach = _olb_get(md, "groupOrderID", "GroupOrderID", default=None)
    return flach if flach is not None else default


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


# ------------------------------------------------------- OLB Match-Events -
# OpenLigaDB fuehrt pro Spiel `matchEvents` (Tore, Gelb/Rot). Stand 13.09.2026
# ist der BL1-Feed dort leer (alle Spieltage 0 Ereignisse, live geprueft) -
# dieser Pfad ist bewusst ein kostenloser "wenn Daten da sind, werden sie
# genutzt"-Abnehmer ohne Key und ohne eigenes HTTP (haengt am getmatchdata-
# Payload der Syncs). Solange nichts kommt, bleibt er lautlos.

_OLB_CARD_KINDS = (
    ("yellow red", "yellow_red"),
    ("yellow", "gelb"),
    ("red", "rot"),
)


def _olb_event_side(md, ev):
    t1 = _olb_get(_olb_get(md, "team1", "Team1", default={}) or {}, "teamId", "TeamID")
    t2 = _olb_get(_olb_get(md, "team2", "Team2", default={}) or {}, "teamId", "TeamID")
    tid = _olb_get(ev, "teamId", "TeamID")
    if tid is not None and t1 is not None and str(tid) == str(t1):
        return "home"
    if tid is not None and t2 is not None and str(tid) == str(t2):
        return "away"
    return None


def _olb_event_rows(md):
    """matchEvents -> normale Zeilen im Seitenformat (Tore wie Goal-Boost)."""
    rows = []
    for ev in (_olb_get(md, "matchEvents", "MatchEvents", default=[]) or []):
        if not isinstance(ev, dict):
            continue
        etype_raw = _olb_get(ev, "matchEventType", "EventType", default="") or ""
        if isinstance(etype_raw, dict):  # manche Builds liefern {"name": ...}
            etype_raw = etype_raw.get("name") or ""
        etype = str(etype_raw).strip().lower()
        try:
            minute = int(_olb_get(ev, "minute", "Minute", default=0) or 0)
        except (TypeError, ValueError):
            minute = 0
        if minute < 1:
            continue
        player = str(_olb_get(ev, "playerName", "PlayerName", default="") or "").strip() or None
        side = _olb_event_side(md, ev) or "home"
        if "penalty miss" in etype or etype in ("5", "penalty missed"):
            continue  # verschossener Elfer: kein Tor, keine Karte - bewusst raus
        if "own goal" in etype or etype == "6":
            rows.append({"kind": "gf", "min": minute, "team": side, "player": player,
                         "assist": None, "penalty": False, "own_goal": True, "src": "olb"})
        elif "goal" in etype or etype in ("1",):
            rows.append({"kind": "gf", "min": minute, "team": side, "player": player,
                         "assist": None, "penalty": "penalty" in etype or bool(
                             _olb_get(ev, "isPenalty", "IsPenalty", default=False)),
                         "own_goal": False, "src": "olb"})
        elif "card" in etype or etype in ("2", "3", "4"):
            label = {"2": "gelb", "3": "yellow_red", "4": "rot"}.get(etype)
            if label is None:
                for needle, k in _OLB_CARD_KINDS:
                    if needle in etype:
                        label = k
                        break
            if label:
                rows.append({"kind": "olb", "type": "card", "card": label,
                             "min": minute, "team": side, "player": player, "src": "olb"})
        # unbekannte Ereignistypen (Auswechslungen, Taktik ...) bleiben draussen
    rows.sort(key=lambda r: (r["min"], 0 if r["kind"] == "gf" else 1))
    return rows


def _apply_olb_events(md, match):
    """Ergaenzt OLB-Ereignisse ins events-JSON - ueberschreibt und verdoppelt nie.

    Tore deckt der Goal-Boost (API-Football, mit Vorlagen) besser ab: hat der
    fuer Minute+Seite schon eine gf-Zeile, laesst OLB den Platz. Karten kommen
    nur dazu, wenn dieselbe Kombination noch nicht steht. Gibt Anzahl neu
    geschriebener Zeilen zurueck (0 = alles unveraendert).
    """
    if not _olb_is_finished(md):
        return 0
    rows = _olb_event_rows(md)
    if not rows:
        return 0
    import json
    try:
        existing = json.loads(match.events or "[]")
    except (TypeError, ValueError):
        existing = []
    if not isinstance(existing, list):
        existing = []
    gf_marks = {(int(r.get("min") or 0), r.get("team"))
                for r in existing if isinstance(r, dict) and r.get("kind") == "gf"}
    card_marks = {(int(r.get("min") or 0), r.get("team"), str(r.get("card") or ""))
                  for r in existing if isinstance(r, dict) and r.get("type") == "card"}
    added = 0
    for r in rows:
        if r["kind"] == "gf":
            if (r["min"], r["team"]) in gf_marks:
                continue
            gf_marks.add((r["min"], r["team"]))
        else:
            key = (r["min"], r["team"], r["card"])
            if key in card_marks:
                continue
            card_marks.add(key)
        existing.append(r)
        added += 1
    if added:
        existing.sort(key=lambda x: (int(x.get("min") or 0), 0 if isinstance(x, dict) and x.get("kind") == "gf" else 1))
        match.events = json.dumps(existing, ensure_ascii=False)
    return added


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
    events_applied = 0
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

        if _apply_olb_events(md, existing):
            events_applied += 1

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
    if events_applied:
        msg += f" \u00b7 \U0001f947 {events_applied} Spiele mit neuen Ereignissen (Tore/Karten)"
    if new_teams:
        msg += f", {new_teams} Team(s) angelegt"
    if purged_stale:
        msg += f", {purged_stale} veraltete Spiele entfernt"
    msg += purge_summary_suffix()
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
        "events": events_applied,
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
    # (83) faelschlich zu frueh beendet (z. B. football-data "FINISHED"
    # waehrend des Spiels): fertige 0:0 der letzten 5 Tage gegen den echten
    # OLB-Endstand pruefen und korrigieren (finished->finished ist erlaubt).
    falsch_fertig = Match.query.filter(
        Match.status == "finished",
        Match.home_score == 0,
        Match.away_score == 0,
        Match.kickoff >= datetime.now(timezone.utc) - timedelta(days=5),
        Match.external_id.isnot(None),
    ).all()
    falsch_ids = {m.id for m in falsch_fertig}

    if not missing and not falsch_ids:
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
    korrigiert = 0
    events_applied = 0
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

        if match and _apply_olb_events(md, match):
            events_applied += 1
        # Ergebnis einmalig lesen (flat fuer beide Zweige: Nachzug + Korrektur)
        results = _olb_results(md)
        h_score = a_score = None
        for res in results:
            if _olb_result_type_id(res) == 2:
                h_score, a_score = _olb_score(res)
                break
        if h_score is None and results:
            h_score, a_score = _olb_score(results[-1])

        if match and match.status == "scheduled":
            if h_score is not None and a_score is not None:
                apply_match_update(match, home_score=h_score, away_score=a_score, status="finished", is_live=False)
                affected_match_ids.add(match.id)
                filled += 1
        elif (match and match.id in falsch_ids
              and h_score is not None and a_score is not None
              and (h_score, a_score) != (0, 0)
              and (match.home_score, match.away_score) != (h_score, a_score)):
            # (83) echter OLB-Endstand heilt das vorzeitige 0:0
            apply_match_update(match, home_score=h_score, away_score=a_score,
                               status="finished", is_live=False)
            affected_match_ids.add(match.id)
            korrigiert += 1
            current_app.logger.info(
                f"(83) Korrektur: {match.home_team.short_name}-"
                f"{match.away_team.short_name} von vorzeitigem 0:0 "
                f"auf {h_score}:{a_score} korrigiert")

    if filled or korrigiert:
        from scoring import recalculate_matches_points
        from badges import check_and_award_badges
        from models import User
        affected_users = recalculate_matches_points(affected_match_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)
    elif events_applied:
        db.session.commit()
    return filled + korrigiert


# ---------------------------------------------------------- OLB Live-Boost -
_OLB_BOOST_CACHE_KEY = "olb_live_boost:last_fetch"
_OLB_BOOST_TTL_SECONDS = 20
# In-Prozess-Fallback, wenn der Redis-Cache nicht laeuft (CacheManager ist
# dann bewusst ein No-Op - ohne dieses Netz wuerde jeder Client pollend die
# OpenLigaDB direkt treffen).
_olb_boost_last_fetch = {"ts": 0.0}


def boost_live_from_openligadb(matchday=None):
    """Frische Tore fuer laufende/begonnene Spiele von OpenLigaDB holen.

    Hintergrund: football-data.org liefert Scores im Free-Tier zeitlich
    versetzt (Tore teils erst nach Minuten). OpenLigaDB meldet Bundesliga-
    Treffer quasi in Echtzeit - als schneller Live-Booster ideal.

    Regeln:
    - Kein Upstream-Call, wenn gar kein Spiel im (angehenden) Zeitfenster liegt.
    - Prozessweites Throttling: fruehestens alle _OLB_BOOST_TTL_SECONDS ein
      Request, egal wie viele Clients das Live-Center pollen.
    - schreibt nur ueber apply_match_update (Status-Monotonie bleibt gewahrt)
      und loest Punkte-Recalc fuer betroffene Spiele aus.
    - Bei OLB-Ausfall/Timeout: stiller Rueckzug, der fd-Pfad bleibt allein aktiv.
    """
    now = datetime.now(timezone.utc)
    from competition_helpers import filter_matches_for_active_competition

    window_open = now - timedelta(hours=3, minutes=15)   # Nachspielzeit + Puffer
    window_close = now + timedelta(minutes=20)            # Anpfiff-Naeherung
    cand_q = Match.query.filter(
        Match.kickoff >= window_open,
        Match.kickoff <= window_close,
        Match.status.in_(("scheduled", "live")),
    )
    cand_q = filter_matches_for_active_competition(cand_q)
    if matchday:
        cand_q = cand_q.filter(Match.matchday == matchday)
    candidates = cand_q.all()
    if not candidates:
        return {"ok": True, "updated": 0}

    import time as _time
    try:
        from cache import cache as _cache
        if _cache.enabled:
            if _cache.get(_OLB_BOOST_CACHE_KEY):
                return {"ok": True, "updated": 0, "throttled": True}
            _cache.set(_OLB_BOOST_CACHE_KEY, 1, ttl=_OLB_BOOST_TTL_SECONDS)
        else:
            raise RuntimeError("cache inaktiv")
    except Exception:
        if _time.monotonic() - _olb_boost_last_fetch["ts"] < _OLB_BOOST_TTL_SECONDS:
            return {"ok": True, "updated": 0, "throttled": True}
        _olb_boost_last_fetch["ts"] = _time.monotonic()

    season = current_sync_season_code()
    matchdays = sorted({m.matchday for m in candidates if m.matchday})
    urls = [f"https://api.openligadb.de/getmatchdata/bl1/{season}/{md}" for md in matchdays] or \
           [f"https://api.openligadb.de/getmatchdata/bl1/{season}"]

    def _parse_dt(value):
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    updated = 0
    affected_ids = set()
    for url in urls:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code != 200:
                continue
            payload = r.json()
        except Exception:
            continue
        for md in payload if isinstance(payload, list) else []:
            kickoff = _parse_dt(_olb_kickoff(md))
            if kickoff is None or not (window_open <= kickoff <= window_close):
                continue
            home_short = _OLB_TEAM_MAP.get(_olb_team_name(_olb_get(md, "team1", "Team1")) or "")
            away_short = _OLB_TEAM_MAP.get(_olb_team_name(_olb_get(md, "team2", "Team2")) or "")
            if not home_short or not away_short:
                continue
            match = None
            for cand in candidates:
                if cand.home_team.short_name == home_short and cand.away_team.short_name == away_short:
                    match = cand
                    break
            if match is None:
                continue
            h_score = a_score = None
            for res in _olb_results(md):
                if _olb_result_type_id(res) == 2:
                    h_score, a_score = _olb_score(res)
                    break
            if h_score is None and _olb_results(md):
                h_score, a_score = _olb_score(_olb_results(md)[-1])
            if h_score is None or a_score is None:
                continue
            if _olb_is_finished(md):
                target_status, target_live = "finished", False
            elif kickoff <= now:
                target_status, target_live = "live", True
            else:
                continue  # noch nicht angepfiffen
            if (match.home_score, match.away_score, match.status) == (h_score, a_score, target_status):
                continue
            apply_match_update(match, home_score=h_score, away_score=a_score,
                               status=target_status, is_live=target_live)
            if target_status == "finished":
                match.live_phase = None
                match.minute = None
            affected_ids.add(match.id)
            updated += 1
    if updated:
        db.session.commit()
        from scoring import recalculate_matches_points
        from badges import check_and_award_badges
        from models import User
        affected_users = recalculate_matches_points(affected_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)
        current_app.logger.info(f"OLB-Live-Boost: {updated} Spiele aktualisiert ({', '.join(str(i) for i in sorted(affected_ids))})")
    return {"ok": True, "updated": updated}


def _refresh_top_scorers_hook():
    """Torjaeger-Aktualisierung aus OpenLigaDB (keyfrei, 30-min-Takt im Modul).

    Bewusst VOR den Netzwerkaufrufen des Syncs, damit sie auch bei FD-/OLB-
    Stoerungen laeuft; Fehler bleiben lautlos (Debug-Log), nie fatal.
    """
    try:
        from top_scorers import refresh_top_scorers
        refresh_top_scorers()
    except Exception as e:
        current_app.logger.debug(f"top-scorers Hook uebersprungen: {e}")


def sync_results():
    """Haupt-Entry-Point für den Ergebnis-Sync.

    Strategie:
      1. **PRIMÄR:** football-data.org (Live-Daten, exakte Status)
      2. **FALLBACK:** OpenLigaDB (kein Token nötig, aber nur Endergebnisse)

    Wenn FD einen Token hat und funktioniert, wird OLB gar nicht erst
    aufgerufen. Andernfalls (kein Token, Rate-Limit, Netzwerkfehler …)
    übernimmt OLB.
    """
    _refresh_top_scorers_hook()

    # --- 1. football-data.org versuchen ---
    res_fd = sync_with_football_data()
    try:
        from datasource_activity import record as _rec
        _rec("football-data", bool(res_fd.get("ok")), res_fd.get("msg", ""))
    except Exception:
        pass
    if res_fd.get("ok"):
        # Sicherheitsnetz: faellige Spiele ohne Ergebnis aus OpenLigaDB nachziehen,
        # damit sie nicht dauerhaft auf "scheduled" stehen bleiben.
        try:
            filled = _fill_missing_from_openligadb()
            if filled:
                res_fd["msg"] += f" · {filled} Ergebnis(se) via OpenLigaDB nachgezogen/korrigiert"
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
    try:
        from datasource_activity import record as _rec
        _rec("openligadb", bool(res_olb.get("ok")), res_olb.get("msg", ""))
    except Exception:
        pass
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


