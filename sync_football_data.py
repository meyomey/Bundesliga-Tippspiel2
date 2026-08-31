"""football-data.org-Client: _fd_request, Spielplan-Sync, Live-Standings, Live-Updates.

 Ausgelagert aus sync.py (Refactoring 31.08.2026); sync.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from extensions import db
from models import Match, Competition
from scoring import get_setting, set_setting
from match_results import apply_match_update

from sync_shared import (
    current_sync_season_code, _resolve_or_create_team_from_fd, _ensure_competition_team,
    _find_existing_match, _purge_stale_matches_for_comp,
)

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

    def _stale_cache_data():
        """Liefert gecachte Daten bei API-Fehlern - aber nur, wenn der Cache
        max. 10 Minuten alt ist. Aeltere Daten duerfen nicht mehr geschrieben
        werden, sonst koennen veraltete Stati frischere Zustaende ueberschreiben."""
        if isinstance(cached, dict) and (now_ts - cached.get("ts", 0)) <= 600:
            return cached.get("data")
        return None

    url = f"{current_app.config['FOOTBALL_DATA_BASE']}{path}"
    headers = {"X-Auth-Token": token}
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        stale = _stale_cache_data()
        if stale is not None:
            return stale, None
        return None, f"Netzwerkfehler: {e}"

    if r.status_code == 429:
        stale = _stale_cache_data()
        if stale is not None:
            return stale, None
        return None, "API-Rate-Limit erreicht (10 Calls/Min)."

    if r.status_code != 200:
        stale = _stale_cache_data()
        if stale is not None:
            return stale, None
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
    season = current_sync_season_code()
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
    from scoring import recalculate_all_points, recalculate_matches_points
    from badges import check_and_award_badges
    from models import User

    matches_data = data.get("matches", [])
    updated = 0
    created = 0
    live_count = 0
    new_teams = 0
    current_ext_ids = set()
    affected_match_ids = set()

    for md in matches_data:
        ext_id = f"fd:{md['id']}"
        current_ext_ids.add(ext_id)

        home_team_data = md.get("homeTeam", {})
        away_team_data = md.get("awayTeam", {})
        home_team_name = home_team_data.get("name", "")
        away_team_name = away_team_data.get("name", "")
        home_team, home_created = _resolve_or_create_team_from_fd(home_team_data)
        away_team, away_created = _resolve_or_create_team_from_fd(away_team_data)
        if home_created or away_created:
            new_teams += int(bool(home_created)) + int(bool(away_created))
            current_app.logger.info(
                f"Neue Teams aus football-data.org angelegt: "
                f"{home_team.name if home_created else ''} {away_team.name if away_created else ''}".strip()
            )
        if not home_team or not away_team:
            current_app.logger.warning(f"Sync: Team nicht erkannt: {home_team_name} / {away_team_name}")
            continue
        _ensure_competition_team(comp_id, home_team)
        _ensure_competition_team(comp_id, away_team)

        kickoff_str = md["utcDate"]
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except Exception:
            continue

        matchday_num = md.get("matchday") or 1
        existing = _find_existing_match(comp_id, ext_id, matchday_num, home_team, away_team, source_prefix="fd")
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
                is_live=(our_status == "live"),
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
                is_live=(our_status == "live"),
            )
            db.session.add(existing)
            db.session.flush()
            if our_status == "finished":
                affected_match_ids.add(existing.id)
            created += 1

        if our_status == "live":
            live_count += 1

    purged_stale = 0
    if source == "football-data.org" and current_ext_ids:
        purged_stale = _purge_stale_matches_for_comp(comp_id, current_ext_ids)

    db.session.commit()

    if purged_stale > 0:
        recalculate_all_points()
        check_and_award_badges()
    elif affected_match_ids:
        affected_users = recalculate_matches_points(affected_match_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)

    return {
        "ok": True,
        "msg": f"✅ {source}: {created} neu, {updated} aktualisiert, {live_count} live",
        "created": created,
        "updated": updated,
        "live": live_count,
        "new_teams": new_teams,
        "purged_stale": purged_stale,
    }


def fetch_live_standings():
    """Holt die Live-Tabelle von football-data.org."""
    season = current_sync_season_code()
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
        team_data = entry.get("team", {})
        team_name = team_data.get("name", "")
        team_obj, created_team = _resolve_or_create_team_from_fd(team_data)
        if created_team:
            db.session.commit()
        if not team_obj:
            current_app.logger.warning(f"Tabelle: Team nicht erkannt: {team_name}")
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
    season = current_sync_season_code()
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


