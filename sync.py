"""API-Sync: football-data.org, OpenLigaDB, Live-Updates, Schema-Migration, Seeding."""
import json
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app
from sqlalchemy import inspect, text

from extensions import db
from models import (
    User, Team, Match, Prediction, Comment, Setting,
    Competition, CompetitionTeam,
)
from scoring import get_setting, set_setting


# Bundesliga-Teams für automatische Befüllung
BUNDESLIGA_TEAMS = [
    ("FC Bayern München",       "FCB", 5,   "https://crests.football-data.org/5.png",   "#DC052D"),
    ("Borussia Dortmund",       "BVB", 4,   "https://crests.football-data.org/4.png",   "#FDE100"),
    ("Bayer 04 Leverkusen",     "B04", 3,   "https://crests.football-data.org/3.png",   "#E32219"),
    ("RB Leipzig",              "RBL", 721, "https://crests.football-data.org/721.png", "#DD0741"),
    ("VfB Stuttgart",           "VFB", 10,  "https://crests.football-data.org/10.png",  "#E32219"),
    ("Eintracht Frankfurt",     "SGE", 19,  "https://crests.football-data.org/19.png",  "#E1000F"),
    ("VfL Wolfsburg",           "WOB", 11,  "https://crests.football-data.org/11.png",  "#65B32E"),
    ("Borussia Mönchengladbach","BMG", 18,  "https://crests.football-data.org/18.png",  "#000000"),
    ("SC Freiburg",             "SCF", 17,  "https://crests.football-data.org/17.png",  "#5B5B5B"),
    ("1. FC Union Berlin",      "FCU", 28,  "https://crests.football-data.org/28.png",  "#EB1923"),
    ("TSG Hoffenheim",          "TSG", 2,   "https://crests.football-data.org/2.png",   "#1961B5"),
    ("1. FSV Mainz 05",         "M05", 15,  "https://crests.football-data.org/15.png",  "#C8102E"),
    ("FC Augsburg",             "FCA", 16,  "https://crests.football-data.org/16.png",  "#BA3733"),
    ("SV Werder Bremen",        "SVW", 12,  "https://crests.football-data.org/12.png",  "#1D9053"),
    ("1. FC Heidenheim",        "FCH", 44,  "https://crests.football-data.org/44.png",  "#E2001A"),
    ("FC St. Pauli",            "STP", 24,  "https://crests.football-data.org/24.png",  "#62351D"),
    ("Hamburger SV",            "HSV", 269, "https://crests.football-data.org/269.png", "#0F4D92"),
    ("1. FC Köln",              "KOE", 1,   "https://crests.football-data.org/1.png",   "#ED1C24"),
]


# ============================================================ Seeding -
def seed_teams_if_empty():
    if Team.query.count() == 0:
        for name, short, ext_id, logo, color in BUNDESLIGA_TEAMS:
            db.session.add(Team(
                name=name, short_name=short, external_id=ext_id, logo=logo, color=color
            ))
        db.session.commit()


def _purge_demo_matches():
    from models import Prediction, Comment
    demo = Match.query.filter(Match.external_id.is_(None)).all()
    count = len(demo)
    if count == 0:
        return 0
    demo_ids = [m.id for m in demo]
    Prediction.query.filter(Prediction.match_id.in_(demo_ids)).delete(synchronize_session=False)
    Comment.query.filter(Comment.match_id.in_(demo_ids)).delete(synchronize_session=False)
    Match.query.filter(Match.id.in_(demo_ids)).delete(synchronize_session=False)
    db.session.commit()
    return count


def seed_demo_matches(force=False):
    """Erstellt 34 Spieltage mit jeweils 9 Spielen, falls leer.

    Args:
        force: Wenn True, werden bestehende Spiele geloescht und neu erstellt.
    """
    if not force and Match.query.count() > 0:
        return
    teams = Team.query.all()
    if len(teams) < 18:
        return

    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition.query.first()
    comp_id = comp.id if comp else 1

    import random
    base_date = datetime.now(timezone.utc) - timedelta(days=14)
    for md in range(1, 35):
        random.shuffle(teams)
        for i in range(0, 18, 2):
            home, away = teams[i], teams[i + 1]
            kickoff = base_date + timedelta(days=(md - 1) * 7, hours=15 + (i % 4))
            status = "finished" if md <= 2 else "scheduled"
            home_s = random.randint(0, 4) if status == "finished" else None
            away_s = random.randint(0, 4) if status == "finished" else None
            db.session.add(Match(
                competition_id=comp_id,
                matchday=md, home_team_id=home.id, away_team_id=away.id,
                kickoff=kickoff, status=status,
                home_score=home_s, away_score=away_s,
            ))
    db.session.commit()


def force_seed_demo_matches():
    """Loescht alle Daten und erstellt frische Demo-Spiele."""
    from models import Prediction, Comment
    Prediction.query.delete()
    Comment.query.delete()
    Match.query.delete()
    db.session.commit()
    seed_demo_matches(force=True)
    from badges import check_and_award_badges
    from scoring import recalculate_all_points
    recalculate_all_points()
    return Match.query.count()


# ============================================================ football-data.org -
def _fd_request(path, ttl_seconds=30):
    """Wrapper für football-data.org-Requests mit Token + Caching."""
    token = get_setting("football_data_token", current_app.config["FOOTBALL_DATA_TOKEN"])
    if not token:
        return None, "Kein football-data.org-Token gesetzt (Admin → Einstellungen)."

    cache_key = f"fd_cache:{path}"
    cached = get_setting(cache_key)
    now_ts = datetime.now(timezone.utc).timestamp()
    if cached and isinstance(cached, dict):
        ts = cached.get("ts", 0)
        if now_ts - ts < ttl_seconds:
            return cached.get("data"), None

    url = f"{current_app.config['FOOTBALL_DATA_BASE']}{path}"
    headers = {"X-Auth-Token": token}
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        if cached and isinstance(cached, dict):
            return cached.get("data"), None
        return None, f"Netzwerkfehler: {e}"

    if r.status_code == 429:
        if cached and isinstance(cached, dict):
            return cached.get("data"), None
        return None, "API-Rate-Limit erreicht (10 Calls/Min)."

    if r.status_code != 200:
        if cached and isinstance(cached, dict):
            return cached.get("data"), None
        return None, f"API-Fehler {r.status_code} (Token/Quota prüfen)"

    try:
        data = r.json()
    except ValueError:
        return None, "API lieferte ungültiges JSON"

    set_setting(cache_key, {"ts": now_ts, "data": data})
    return data, None


def sync_with_football_data():
    """Hauptsync gegen football-data.org (Spielplan + Ergebnisse).

    Primäre Datenquelle – liefert Live-Spielstände, exakte Kickoff-Zeiten
    und Status (IN_PLAY, PAUSED, FINISHED). Benötigt einen kostenlosen
    Token von https://www.football-data.org/client/register
    (10 Calls/min im Free Tier).
    """
    season = current_app.config["SEASON"]
    comp = current_app.config["COMPETITION"]

    comp_obj = Competition.query.filter_by(code=comp, is_active=True).first()
    comp_id = comp_obj.id if comp_obj else 1

    data, err = _fd_request(f"/competitions/{comp}/matches?season={season}", ttl_seconds=60)
    if err:
        return {"ok": False, "source": "football-data.org", "msg": err}

    result = _process_football_data(data, comp_id, source="football-data.org")
    result["source"] = "football-data.org"
    return result


def _process_football_data(data, comp_id, source="football-data.org"):
    """Verarbeitet die Match-Daten und speichert sie in der DB."""
    from scoring import recalculate_all_points, calculate_points
    from badges import check_and_award_badges

    matches_data = data.get("matches", [])
    updated = 0
    created = 0
    live_count = 0

    for md in matches_data:
        ext_id = f"fd:{md['id']}"
        existing = Match.query.filter_by(external_id=ext_id).first()

        home_team_name = md["homeTeam"]["name"]
        away_team_name = md["awayTeam"]["name"]
        home_team = _resolve_team_by_name(home_team_name)
        away_team = _resolve_team_by_name(away_team_name)
        if not home_team or not away_team:
            continue

        kickoff_str = md["utcDate"]
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except Exception:
            continue

        matchday_num = md.get("matchday") or 1
        status = md.get("status", "SCHEDULED")
        status_map = {
            "SCHEDULED": "scheduled", "TIMED": "scheduled",
            "IN_PLAY": "live", "PAUSED": "live",
            "FINISHED": "finished", "POSTPONED": "scheduled",
            "SUSPENDED": "scheduled", "CANCELLED": "scheduled",
        }
        our_status = status_map.get(status, "scheduled")

        score = md.get("score", {})
        full_time = score.get("fullTime", {})
        home_score = full_time.get("home")
        away_score = full_time.get("away")
        half_time = score.get("halfTime", {})
        ht_home = half_time.get("home")
        ht_away = half_time.get("away")

        if existing:
            existing.status = our_status
            existing.kickoff = kickoff
            if home_score is not None:
                existing.home_score = home_score
                existing.away_score = away_score
            if our_status == "live":
                existing.is_live = True
            else:
                existing.is_live = False
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
                is_live=(our_status == "live"),
            )
            db.session.add(existing)
            created += 1

        if our_status == "live":
            live_count += 1

    db.session.commit()

    if updated > 0 or created > 0:
        recalculate_all_points()
        check_and_award_badges()

    return {
        "ok": True,
        "msg": f"✅ {source}: {created} neu, {updated} aktualisiert, {live_count} live",
        "created": created,
        "updated": updated,
        "live": live_count,
    }


def fetch_live_standings():
    """Holt die Live-Tabelle von football-data.org."""
    season = current_app.config["SEASON"]
    comp = current_app.config["COMPETITION"]

    data, err = _fd_request(f"/competitions/{comp}/standings?season={season}", ttl_seconds=60)
    if err or not data:
        return None, err or "Keine Daten"

    standings = data.get("standings", [])
    if not standings:
        return None, "Keine Tabellendaten"

    table_data = standings[0].get("table", [])
    rows = []
    for entry in table_data:
        team_name = entry.get("team", {}).get("name", "")
        team_obj = _resolve_team_by_name(team_name)
        if not team_obj:
            continue
        rows.append({
            "rank": entry.get("position", 0),
            "team": team_obj,
            "played": entry.get("playedGames", 0),
            "won": entry.get("won", 0),
            "drawn": entry.get("draw", 0),
            "lost": entry.get("lost", 0),
            "goals_for": entry.get("goalsFor", 0),
            "goals_against": entry.get("goalsAgainst", 0),
            "goal_diff": entry.get("goalDifference", 0),
            "points": entry.get("points", 0),
            "form": entry.get("form", ""),
        })
    return rows, None


def fetch_live_match_updates(matchday=None):
    """Holt aktuelle Spielstände von football-data.org für heute."""
    season = current_app.config["SEASON"]
    comp = current_app.config["COMPETITION"]

    if matchday:
        data, err = _fd_request(f"/competitions/{comp}/matches?season={season}&matchday={matchday}", ttl_seconds=30)
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        next_week = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
        data, err = _fd_request(
            f"/competitions/{comp}/matches?season={season}&dateFrom={today}&dateTo={next_week}",
            ttl_seconds=30
        )

    if err or not data:
        return {"ok": False, "msg": err}

    comp_obj = Competition.query.filter_by(code=comp, is_active=True).first()
    comp_id = comp_obj.id if comp_obj else 1

    return _process_football_data(data, comp_id, source="live-sync")


# ============================================================ OpenLigaDB -
# Teamname-Mapping
_OLB_TEAM_MAP = {
    "FC Bayern München": "FCB", "Bayern München": "FCB", "FC Bayern": "FCB",
    "Borussia Dortmund": "BVB", "BVB 09": "BVB",
    "Bayer 04 Leverkusen": "B04", "Bayer Leverkusen": "B04",
    "RB Leipzig": "RBL",
    "VfB Stuttgart": "VFB",
    "Eintracht Frankfurt": "SGE",
    "VfL Wolfsburg": "WOB",
    "Borussia Mönchengladbach": "BMG", "B. Mönchengladbach": "BMG",
    "SC Freiburg": "SCF",
    "1. FC Union Berlin": "FCU", "Union Berlin": "FCU",
    "TSG Hoffenheim": "TSG", "TSG 1899 Hoffenheim": "TSG",
    "1. FSV Mainz 05": "M05", "Mainz 05": "M05",
    "FC Augsburg": "FCA",
    "SV Werder Bremen": "SVW", "Werder Bremen": "SVW",
    "1. FC Heidenheim": "FCH", "FC Heidenheim": "FCH", "1. FC Heidenheim 1846": "FCH",
    "FC St. Pauli": "STP", "St. Pauli": "STP",
    "Hamburger SV": "HSV",
    "1. FC Köln": "KOE", "FC Köln": "KOE", "1. FC Koeln": "KOE",
    "Darmstadt 98": "D98", "SV Darmstadt 98": "D98",
    "1. FC Nürnberg": "FCN",
    "FC Schalke 04": "S04", "Schalke 04": "S04",
    "Hannover 96": "H96",
    "Hertha BSC": "BSC",
    "VfL Bochum": "BOC",
    "Fortuna Düsseldorf": "F95",
    "Karlsruher SC": "KSC",
    "SC Paderborn 07": "SCP",
    "Holstein Kiel": "KSV",
    "FC Ingolstadt": "FCI",
    "Arminia Bielefeld": "BIE",
    "Greuther Fürth": "SGF", "SpVgg Greuther Fürth": "SGF",
}


def _resolve_team_by_name(api_name):
    """Findet Team in DB per Name, short_name oder Mapping."""
    short = _OLB_TEAM_MAP.get(api_name)
    if short:
        t = Team.query.filter_by(short_name=short).first()
        if t:
            return t
    t = Team.query.filter_by(name=api_name).first()
    if t:
        return t
    t = Team.query.filter(Team.name.ilike(f"%{api_name}%")).first()
    return t



# ---------------------------------------------------------- OpenLigaDB Helper -
def _olb_get(d, *keys, default=None):
    """OpenLigaDB hat 2024+ von PascalCase auf camelCase umgestellt.
    Dieser Helper akzeptiert beide Schreibweisen.

    Beispiel: _olb_get(md, "MatchID", "matchID")
    """
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    # Auto-Versuch: erstes Key in beiden Cases
    if keys:
        for k in keys:
            lower = k[0].lower() + k[1:]
            upper = k[0].upper() + k[1:]
            for variant in (lower, upper):
                if variant in d and d[variant] is not None:
                    return d[variant]
    return default


def _olb_match_id(md):
    return _olb_get(md, "matchID", "MatchID")


def _olb_team_name(team_dict):
    if not isinstance(team_dict, dict):
        return None
    return _olb_get(team_dict, "teamName", "TeamName", "shortName", "ShortName")


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
    season = current_app.config.get("SEASON", "2025")

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
    for md in data:
        match_id_raw = _olb_match_id(md)
        if match_id_raw is None:
            skipped += 1
            continue
        ext_id = f"oldb:{match_id_raw}"
        existing = Match.query.filter_by(external_id=ext_id).first()

        home_name = _olb_team_name(_olb_get(md, "team1", "Team1"))
        away_name = _olb_team_name(_olb_get(md, "team2", "Team2"))
        if not home_name or not away_name:
            skipped += 1
            continue

        home_team = _resolve_team_by_name(home_name)
        away_team = _resolve_team_by_name(away_name)
        if not home_team or not away_team:
            continue

        kickoff_str = _olb_kickoff(md)
        if not kickoff_str:
            continue
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except Exception:
            continue

        matchday_num = _olb_group_order_id(md, default=1)
        is_finished = _olb_is_finished(md)
        our_status = "finished" if is_finished else "scheduled"

        home_score = None
        away_score = None
        if is_finished:
            # ResultTypeID 2 = Endergebnis (manchmal nur 1 = Halbzeit vorhanden)
            results = _olb_results(md)
            for res in results:
                if _olb_result_type_id(res) == 2:
                    home_score, away_score = _olb_score(res)
                    break
            # Fallback: falls kein ResultTypeID==2, nimm den letzten Eintrag
            if home_score is None and results:
                home_score, away_score = _olb_score(results[-1])

        if existing:
            existing.status = our_status
            if home_score is not None:
                existing.home_score = home_score
                existing.away_score = away_score
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
            )
            db.session.add(existing)
            created += 1

    db.session.commit()

    if updated > 0 or created > 0:
        from scoring import recalculate_all_points
        from badges import check_and_award_badges
        recalculate_all_points()
        check_and_award_badges()

    return {"ok": True, "source": "openligadb", "created": created, "updated": updated, "msg": f"OpenLigaDB: {created} neu, {updated} aktualisiert" + (f", {skipped} übersprungen" if skipped else "")}


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
    season = current_app.config.get("SEASON", "2025")
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
                match.home_score = h_score
                match.away_score = a_score
                match.status = "finished"
                filled += 1

    if filled:
        db.session.commit()
        from scoring import recalculate_all_points
        from badges import check_and_award_badges
        recalculate_all_points()
        check_and_award_badges()
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
        current_app.logger.info(f"✅ Sync via football-data.org: {res_fd.get('msg')}")
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
        return {
            "ok": True,
            "source": "openligadb",
            "created": res_olb.get("created", 0),
            "updated": res_olb.get("updated", 0),
            "msg": f"{res_olb['msg']} (Fallback – football-data.org: {fd_reason}){hint}",
        }

    # --- 3. Beide fehlgeschlagen ---
    return {
        "ok": False,
        "source": "none",
        "msg": (
            f"❌ Beide Datenquellen fehlgeschlagen.  "
            f"football-data.org: {res_fd.get('msg')}  |  "
            f"OpenLigaDB: {res_olb.get('msg')}"
        ),
    }


# ============================================================ Schema-Migration -
def auto_migrate_schema():
    """Fügt fehlende Spalten/Tabellen zur SQLite-DB hinzu."""
    engine = db.engine
    if not engine.url.drivername.startswith("sqlite"):
        return

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    schema_updates = {
        "users": [
            ("full_name",       "VARCHAR(120)",       "NULL"),
            ("favorite_team_id","INTEGER",            "NULL"),
            ("phone",           "VARCHAR(40)",        "NULL"),
            ("show_full_name",  "BOOLEAN",            "1"),
            ("has_paid",        "BOOLEAN",            "0"),
            ("paid_at",         "DATETIME",           "NULL"),
            ("paid_note",       "VARCHAR(200)",       "NULL"),
            ("push_subscription","TEXT",              "NULL"),
            ("whatsapp_phone",  "VARCHAR(30)",        "NULL"),
            ("whatsapp_apikey", "VARCHAR(20)",        "NULL"),
        ],
        "matches": [
            ("competition_id",  "INTEGER",            "1"),
            ("is_live",         "BOOLEAN",            "0"),
            ("minute",          "INTEGER",            "NULL"),
            ("events",          "TEXT",               "NULL"),
        ],
        "predictions": [
            ("created_at",      "DATETIME",           "NULL"),
            ("updated_at",      "DATETIME",           "NULL"),
        ],
        "badges": [
            ("color",           "VARCHAR(20)",        "'#fbbf24'"),
            ("trigger_type",    "VARCHAR(30)",        "'manual'"),
            ("threshold",       "INTEGER",            "0"),
            ("active",          "BOOLEAN",            "1"),
            ("created_at",      "DATETIME",           "NULL"),
        ],
        "special_questions": [
            ("description",     "VARCHAR(500)",       "NULL"),
            ("answer_type",     "VARCHAR(20)",        "'text'"),
            ("number_min",      "INTEGER",            "NULL"),
            ("number_max",      "INTEGER",            "NULL"),
            ("multi_count",     "INTEGER",            "1"),
            ("season",          "VARCHAR(20)",        "'2025/26'"),
            ("created_at",      "DATETIME",           "NULL"),
        ],
        "special_predictions": [
            ("created_at",      "DATETIME",           "NULL"),
            ("updated_at",      "DATETIME",           "NULL"),
        ],
    }

    added = []
    with engine.begin() as conn:
        for table_name, columns in schema_updates.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in insp.get_columns(table_name)}
            for col_name, col_type, col_default in columns:
                if col_name in existing_cols:
                    continue
                default_clause = f" DEFAULT {col_default}" if col_default != "NULL" else ""
                ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type}{default_clause}'
                try:
                    conn.execute(text(ddl))
                    added.append(f"{table_name}.{col_name}")
                except Exception as e:
                    current_app.logger.warning(f"Auto-Migration: konnte '{ddl}' nicht ausführen: {e}")

    if added:
        current_app.logger.info(f"✅ Auto-Migration: {len(added)} Spalten ergänzt: {', '.join(added)}")

    null_fixes = [
        ("users", "show_full_name", 1),
        ("users", "has_paid", 0),
        ("badges", "active", 1),
        ("predictions", "joker", 0),
    ]
    with engine.begin() as conn:
        for tbl, col, default in null_fixes:
            try:
                conn.execute(text(
                    f'UPDATE "{tbl}" SET "{col}" = :d WHERE "{col}" IS NULL'
                ), {"d": default})
            except Exception:
                pass
