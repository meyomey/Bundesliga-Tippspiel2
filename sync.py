"""API-Sync: football-data.org, OpenLigaDB, Live-Updates, Schema-Migration, Seeding."""
import json
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app
from sqlalchemy import inspect, text

from extensions import db
from models import (
    User, Team, Match, Prediction, Comment, Setting,
    Competition, CompetitionTeam, InvitationCode,
)
from scoring import get_setting, set_setting
from match_results import apply_match_update


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
    # football-data.org liefert fuer diese Teams teils falsche/fehlende Crest-URLs.
    # Deshalb nutzen wir nur hier die von OpenLigaDB verlinkten Wikimedia-SVGs.
    ("FC St. Pauli",            "STP", 24,  "https://upload.wikimedia.org/wikipedia/commons/b/b3/Fc_st_pauli_logo.svg", "#62351D"),
    ("Hamburger SV",            "HSV", 269, "https://upload.wikimedia.org/wikipedia/commons/f/f7/Hamburger_SV_logo.svg", "#0F4D92"),
    ("1. FC Köln",              "KOE", 1,   "https://crests.football-data.org/1.png",   "#ED1C24"),
]


# Nur gezielte Logo-Fixes. Andere Teams werden bewusst nicht angefasst.
KNOWN_TEAM_LOGO_FIXES = {
    # Problematische/fehlende football-data-Crests gezielt mit OpenLigaDB/Wikimedia-Quellen ersetzen.
    "STP": "https://upload.wikimedia.org/wikipedia/commons/b/b3/Fc_st_pauli_logo.svg",
    "HSV": "https://upload.wikimedia.org/wikipedia/commons/f/f7/Hamburger_SV_logo.svg",
    "FCB": "https://upload.wikimedia.org/wikipedia/commons/1/1f/Logo_FC_Bayern_M%C3%BCnchen_%282002%E2%80%932017%29.svg",
    "BVB": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Borussia_Dortmund_logo.svg/960px-Borussia_Dortmund_logo.svg.png",
    "B04": "https://www.bundesliga-reisefuehrer.de/sites/default/files/B04_Standard_Logo_RGB.png",
    "RBL": "https://i.imgur.com/Rpwsjz1.png",
    "S04": "https://upload.wikimedia.org/wikipedia/commons/9/97/FC_Schalke_04_Logo.png",
    "SCP": "https://upload.wikimedia.org/wikipedia/commons/e/e3/SC_Paderborn_07_Logo.svg",
    "PAD": "https://upload.wikimedia.org/wikipedia/commons/e/e3/SC_Paderborn_07_Logo.svg",
    "ELV": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/SV_Elversberg_Logo.svg/500px-SV_Elversberg_Logo.svg.png",
    "N09": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/SV_Elversberg_Logo.svg/500px-SV_Elversberg_Logo.svg.png",
}


def update_known_team_logos():
    """Korrigiert bekannte falsche/fehlende Logo-URLs in Bestandsdaten.

    Hintergrund: football-data.org zeigt bei St. Pauli/HSV je nach Saison/ID
    falsche bzw. fehlende Crest-URLs. Wir aktualisieren deshalb nur diese zwei
    Teams auf die von OpenLigaDB referenzierten Wikimedia-SVGs.
    """
    changed = 0
    for short_name, logo_url in KNOWN_TEAM_LOGO_FIXES.items():
        team = Team.query.filter_by(short_name=short_name).first()
        # Lokale Logos nicht wieder auf externe URLs zurueckdrehen.
        if team and team.logo and str(team.logo).startswith("/static/team_logos/"):
            continue
        if team and team.logo != logo_url:
            team.logo = logo_url
            changed += 1
    if changed:
        db.session.commit()
        try:
            current_app.logger.info(f"✅ Team-Logo-Fixes aktualisiert: {changed}")
        except Exception:
            pass
    return changed


def season_code_from_label(value, default=None):
    """Extrahiert den football-data/OpenLigaDB Saison-Code aus Labels.

    Beispiele:
    - "2026/27" -> "2026"
    - "2026" -> "2026"
    - None -> default
    """
    if value is None:
        return str(default or current_app.config.get("SEASON", "2025"))
    raw = str(value).strip()
    if not raw:
        return str(default or current_app.config.get("SEASON", "2025"))
    # Erstes vierstelliges Jahr gewinnt.
    import re
    m = re.search(r"(20\d{2})", raw)
    if m:
        return m.group(1)
    return raw


def current_sync_season_code():
    """Saison-Code fuer externe APIs. Admin-Settings haben Vorrang vor Config.

    Wichtig: football-data.org erwartet fuer 2026/27 den Parameter `season=2026`,
    nicht das Label `2026/27`.
    """
    configured = current_app.config.get("SEASON", "2025")
    setting_value = get_setting("season", None)
    if setting_value is None:
        current_label = get_setting("current_season", None)
        if current_label is not None:
            return season_code_from_label(current_label, configured)
        comp = Competition.query.filter_by(is_active=True).order_by(Competition.id.asc()).first()
        if comp and comp.season:
            return season_code_from_label(comp.season, configured)
    return season_code_from_label(setting_value, configured)


# ============================================================ Seeding -
def seed_teams_if_empty():
    if Team.query.count() == 0:
        for name, short, ext_id, logo, color in BUNDESLIGA_TEAMS:
            db.session.add(Team(
                name=name, short_name=short, external_id=ext_id, logo=logo, color=color
            ))
        db.session.commit()
    update_known_team_logos()


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


def _team_color_from_name(name):
    """Deterministische Fallback-Farbe fuer neu erkannte Teams."""
    palette = ["#0ea5e9", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#14b8a6", "#64748b"]
    return palette[sum(ord(c) for c in (name or "")) % len(palette)]


def _resolve_or_create_team_from_fd(team_data):
    """Findet oder erstellt Team anhand football-data.org Teamobjekt.

    Wichtig fuer neue Saisons: Aufsteiger sind oft nicht in den initialen
    Seed-Daten. Frueher wurden solche Spiele uebersprungen. Jetzt wird das Team
    automatisch angelegt und dem Sync nicht mehr blockiert.
    """
    if not isinstance(team_data, dict):
        return None, False
    name = team_data.get("name") or team_data.get("shortName") or team_data.get("tla")
    if not name:
        return None, False
    ext_id = team_data.get("id")
    short = (team_data.get("tla") or team_data.get("shortName") or name[:3]).upper()[:10]
    logo = team_data.get("crest") or team_data.get("crestUrl") or ""

    team = None
    if ext_id is not None:
        team = Team.query.filter_by(external_id=ext_id).first()
    if not team:
        team = _resolve_team_by_name(name)
    if not team:
        # Kuerzel-Kollision vermeiden
        base_short = short
        i = 2
        while Team.query.filter_by(short_name=short).first():
            short = (base_short[:7] + str(i))[:10]
            i += 1
        team = Team(
            name=name,
            short_name=short,
            external_id=ext_id,
            logo=logo or f"/static/team_logos/{_normalize_team_key(short) or 'team'}.svg",
            color=_team_color_from_name(name),
        )
        db.session.add(team)
        db.session.flush()
        return team, True

    changed = False
    if ext_id is not None and team.external_id != ext_id:
        team.external_id = ext_id
        changed = True
    if logo and (not team.logo or str(team.logo).startswith("https://crests.football-data.org/")):
        team.logo = logo
        changed = True
    if changed:
        db.session.flush()
    return team, False


def _ensure_competition_team(comp_id, team):
    if not comp_id or not team:
        return
    exists = CompetitionTeam.query.filter_by(competition_id=comp_id, team_id=team.id).first()
    if not exists:
        db.session.add(CompetitionTeam(competition_id=comp_id, team_id=team.id))


def _find_existing_match(comp_id, ext_id, matchday, home_team, away_team, source_prefix=None):
    """Findet vorhandenes Spiel stabil ueber externe ID oder Paarung.

    Wichtig beim Wechsel der Datenquelle (football-data.org -> OpenLigaDB):
    Bereits vorhandene Tipps duerfen nicht geloescht werden, nur weil die
    externe ID einen anderen Prefix hat. Deshalb suchen wir nach der externen
    ID zunaechst comp-scoped und danach nach Spieltag + Team-Paarung.
    """
    existing = Match.query.filter_by(competition_id=comp_id, external_id=ext_id).first()
    if existing:
        return existing
    if home_team and away_team:
        candidate = Match.query.filter_by(
            competition_id=comp_id,
            matchday=matchday,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
        ).first()
        # Innerhalb derselben Quelle keine alte externe ID versehentlich auf
        # ein neues Spiel mappen (typischer Fall: alter Saisonspielplan mit
        # gleicher Paarung/gleichem Spieltag). Beim Quellenwechsel, z.B.
        # fd:* -> oldb:*, ist Matching dagegen gewuenscht, um Tipps zu erhalten.
        if candidate and source_prefix and candidate.external_id:
            same_source = str(candidate.external_id).startswith(f"{source_prefix}:")
            if same_source and candidate.external_id != ext_id:
                return None
        return candidate
    return None


def _purge_stale_matches_for_comp(comp_id, current_ext_ids):
    """Loescht Spiele des aktiven Wettbewerbs, die nicht in einem Vollsync vorkommen.

    Sicherheitsbremse: Wenn lokal bereits viele Spiele existieren, die API aber
    nur eine offensichtlich unvollstaendige Teilmenge liefert, wird NICHT
    geloescht. Sonst koennte ein temporaerer API-/Saisonfehler echte Tipps
    entfernen.
    """
    if not comp_id or not current_ext_ids:
        return 0

    local_count = Match.query.filter(Match.competition_id == comp_id).count()
    incoming_count = len(current_ext_ids)
    comp = db.session.get(Competition, comp_id)
    expected = (comp.matchdays or 34) * ((comp.teams_count or 18) // 2) if comp else 306
    min_plausible = max(50, int(min(expected, max(local_count, expected)) * 0.75))
    if local_count >= 50 and incoming_count < min_plausible:
        try:
            current_app.logger.warning(
                f"Sync-Purge uebersprungen: API liefert nur {incoming_count} Spiele, "
                f"lokal existieren {local_count}, Mindestwert {min_plausible}."
            )
        except Exception:
            pass
        return 0

    stale = Match.query.filter(
        Match.competition_id == comp_id,
        (
            (Match.external_id.is_(None)) |
            (~Match.external_id.in_(current_ext_ids))
        )
    ).all()
    if not stale:
        return 0
    stale_ids = [m.id for m in stale]
    Prediction.query.filter(Prediction.match_id.in_(stale_ids)).delete(synchronize_session=False)
    Comment.query.filter(Comment.match_id.in_(stale_ids)).delete(synchronize_session=False)
    Match.query.filter(Match.id.in_(stale_ids)).delete(synchronize_session=False)
    return len(stale_ids)


def _resolve_or_create_team_from_olb(team_dict):
    """Findet/erstellt Team anhand OpenLigaDB-Teamobjekt.

    OpenLigaDB ist unser Fallback. Auch dort duerfen Aufsteiger nicht mehr zum
    Ueberspringen kompletter Spiele fuehren.
    """
    if not isinstance(team_dict, dict):
        return None, False
    name = _olb_team_name(team_dict)
    if not name:
        return None, False
    ext_id = _olb_get(team_dict, "teamId", "TeamId", "teamID", "TeamID")
    short = (_OLB_TEAM_MAP.get(name) or _olb_get(team_dict, "shortName", "ShortName") or name[:3]).upper()[:10]
    logo = _olb_get(team_dict, "teamIconUrl", "TeamIconUrl", "iconUrl", "IconUrl") or ""

    team = None
    if ext_id is not None:
        team = Team.query.filter_by(external_id=ext_id).first()
    if not team:
        team = _resolve_team_by_name(name)
    if not team:
        base_short = short
        i = 2
        while Team.query.filter_by(short_name=short).first():
            short = (base_short[:7] + str(i))[:10]
            i += 1
        team = Team(
            name=name,
            short_name=short,
            external_id=ext_id,
            logo=logo or f"/static/team_logos/{_normalize_team_key(short) or 'team'}.svg",
            color=_team_color_from_name(name),
        )
        db.session.add(team)
        db.session.flush()
        return team, True

    changed = False
    if ext_id is not None and team.external_id != ext_id:
        team.external_id = ext_id
        changed = True
    if logo and (not team.logo or str(team.logo).startswith("https://crests.football-data.org/")):
        team.logo = logo
        changed = True
    if changed:
        db.session.flush()
    return team, False


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
    "FC St. Pauli": "STP", "FC St Pauli": "STP", "FC St. Pauli 1910": "STP", "FC St Pauli 1910": "STP", "St. Pauli": "STP", "St Pauli": "STP", "Sankt Pauli": "STP",
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


def _normalize_team_key(value):
    if value is None:
        return ""
    import re
    value = str(value).lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]", "", value)


def _resolve_team_by_name(api_name):
    """Findet Team in DB per Name, short_name, Mapping oder robuster Normalisierung."""
    short = _OLB_TEAM_MAP.get(api_name)
    if short:
        t = Team.query.filter_by(short_name=short).first()
        if t:
            return t

    norm = _normalize_team_key(api_name)
    # Spezielle haeufige API-Varianten, z.B. "FC St. Pauli 1910".
    if "stpauli" in norm or "sanktpauli" in norm:
        t = Team.query.filter_by(short_name="STP").first()
        if t:
            return t
    if "hamburgersv" in norm or norm == "hsv":
        t = Team.query.filter_by(short_name="HSV").first()
        if t:
            return t

    t = Team.query.filter_by(name=api_name).first()
    if t:
        return t

    # Normalisierter Vergleich gegen lokale Teamnamen/Kuerzel.
    for team in Team.query.all():
        if norm and (norm == _normalize_team_key(team.name) or norm == _normalize_team_key(team.short_name)):
            return team
        if norm and (norm in _normalize_team_key(team.name) or _normalize_team_key(team.name) in norm):
            return team

    # Letzter Fallback: SQL ilike (nur fuer sehr aehnliche Namen).
    return Team.query.filter(Team.name.ilike(f"%{api_name}%")).first()



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


# ============================================================ Sync Diagnostics -
def get_sync_diagnostics():
    """Prueft API-/Sync-Konfiguration ohne Daten zu veraendern.

    `teams_total` meint bewusst Teams im aktiven Wettbewerb/aktuellen Spielplan,
    nicht alle historischen Teams in der globalen Team-Tabelle. Alte Absteiger
    duerfen in der DB bleiben, sollen hier aber nicht als aktuelle Teams zählen.
    """
    token = get_setting("football_data_token", current_app.config["FOOTBALL_DATA_TOKEN"])
    comp_code = current_app.config.get("COMPETITION", "BL1")
    season = current_sync_season_code()
    comp_obj = Competition.query.filter_by(code=comp_code, is_active=True).first()
    comp_id = comp_obj.id if comp_obj else None

    matches_q = Match.query
    if comp_id:
        matches_q = matches_q.filter(Match.competition_id == comp_id)
    matches_total = matches_q.count()
    team_pairs = matches_q.with_entities(Match.home_team_id, Match.away_team_id).all()
    current_team_ids = {tid for row in team_pairs for tid in row if tid}
    if not current_team_ids and comp_id:
        current_team_ids = {ct.team_id for ct in CompetitionTeam.query.filter_by(competition_id=comp_id).all()}

    all_teams_total = Team.query.count()
    # Test-/Legacy-Fallback: sehr alte oder bewusst minimale Testdaten haben
    # manchmal weder Matches noch CompetitionTeam-Zuordnungen. In echten
    # Saison-Daten bleiben Match-/CompetitionTeam-IDs massgeblich, damit alte
    # historische Teams nicht wieder als aktuelle Teams gezaehlt werden.
    if not current_team_ids and current_app.config.get("TESTING"):
        current_team_ids = {tid for (tid,) in Team.query.with_entities(Team.id).all()}

    teams_total = len(current_team_ids)
    remote_logos = Team.query.filter(Team.id.in_(current_team_ids), Team.logo.like("http%"), Team.logo.isnot(None)).count() if current_team_ids else 0
    checks = {
        "football_data_token": bool(token),
        "openligadb_available": True,
        "active_competition": bool(comp_obj),
        "teams_seeded": teams_total >= 18,
        "has_matches": matches_total > 0,
    }
    # OpenLigaDB Ping leichtgewichtig
    try:
        r = requests.get(f"{current_app.config['OPENLIGADB_BASE']}/getavailableleagues", timeout=5)
        checks["openligadb_available"] = r.ok
    except Exception:
        checks["openligadb_available"] = False
    warnings = []
    if not checks["football_data_token"]:
        warnings.append("football-data.org Token fehlt – Live-Daten nur via Fallback/OLB.")
    if not checks["active_competition"]:
        warnings.append(f"Aktive Competition {comp_code} nicht gefunden.")
    if not checks["teams_seeded"]:
        warnings.append(f"Aktiver Wettbewerb hat nur {teams_total} erkannte Teams (erwartet: 18).")
    if teams_total > 18:
        warnings.append(f"Aktiver Wettbewerb hat {teams_total} Teams. Alte Matches/Teams prüfen und ggf. Spielplan bereinigen.")
    if remote_logos:
        warnings.append(f"{remote_logos} Teamlogos sind noch extern verlinkt.")
    last_sync = get_setting("last_sync_result", None)
    return {
        "competition": comp_obj,
        "competition_code": comp_code,
        "season": season,
        "teams_total": teams_total,
        "all_teams_total": all_teams_total,
        "matches_total": matches_total,
        "remote_logos": remote_logos,
        "checks": checks,
        "warnings": warnings,
        "last_sync": last_sync,
    }


def store_sync_result(result):
    """Speichert das letzte Sync-Ergebnis fuer Admin-Diagnose."""
    payload = dict(result or {})
    payload["at"] = datetime.now(timezone.utc).isoformat()
    try:
        set_setting("last_sync_result", payload)
    except Exception:
        pass
    return payload


# ============================================================ Schema-Migration -
def auto_migrate_schema():
    """Fügt fehlende Spalten/Tabellen zur SQLite-DB hinzu."""
    engine = db.engine
    if not engine.url.drivername.startswith("sqlite"):
        return

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    if "invitation_codes" not in existing_tables:
        try:
            InvitationCode.__table__.create(bind=engine, checkfirst=True)
            existing_tables.add("invitation_codes")
            current_app.logger.info("✅ Auto-Migration: Tabelle invitation_codes erstellt")
        except Exception as e:
            current_app.logger.warning(f"Auto-Migration: Tabelle invitation_codes konnte nicht erstellt werden: {e}")

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
            ("notify_enabled",  "BOOLEAN",            "1"),
            ("notify_email",    "BOOLEAN",            "1"),
            ("notify_push",     "BOOLEAN",            "1"),
            ("notify_telegram", "BOOLEAN",            "1"),
            ("notify_whatsapp", "BOOLEAN",            "1"),
            ("notify_hours_before", "INTEGER",        "1"),
            ("notify_only_favorite", "BOOLEAN",       "0"),
            ("default_tip_view", "VARCHAR(20)",       "'normal'"),
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
            ("competition_id",  "INTEGER",            "NULL"),
            ("description",     "VARCHAR(500)",       "NULL"),
            ("answer_type",     "VARCHAR(20)",        "'text'"),
            ("number_min",      "INTEGER",            "NULL"),
            ("number_max",      "INTEGER",            "NULL"),
            ("multi_count",     "INTEGER",            "1"),
            ("season",          "VARCHAR(20)",        "'2025/26'"),
            ("created_at",      "DATETIME",           "NULL"),
        ],
        "special_predictions": [
            ("competition_id",  "INTEGER",            "NULL"),
            ("created_at",      "DATETIME",           "NULL"),
            ("updated_at",      "DATETIME",           "NULL"),
        ],
        "prizes": [
            ("competition_id",  "INTEGER",            "NULL"),
        ],
        "matchday_winners": [
            ("competition_id",  "INTEGER",            "NULL"),
        ],
        "season_archive": [
            ("competition_id",  "INTEGER",            "NULL"),
        ],
        "admin_activity_log": [
            ("admin_user_id",   "INTEGER",            "NULL"),
            ("action",          "VARCHAR(80)",        "'unknown'"),
            ("entity_type",     "VARCHAR(80)",        "NULL"),
            ("entity_id",       "VARCHAR(80)",        "NULL"),
            ("message",         "VARCHAR(500)",       "NULL"),
            ("metadata_json",   "TEXT",               "NULL"),
            ("ip_address",      "VARCHAR(64)",        "NULL"),
            ("user_agent",      "VARCHAR(300)",       "NULL"),
            ("created_at",      "DATETIME",           "NULL"),
        ],
        "invitation_codes": [
            ("code",               "VARCHAR(80)",    "NULL"),
            ("invited_by_user_id", "INTEGER",         "NULL"),
            ("email",              "VARCHAR(120)",    "NULL"),
            ("max_uses",           "INTEGER",         "1"),
            ("uses",               "INTEGER",         "0"),
            ("used_by_user_id",    "INTEGER",         "NULL"),
            ("created_at",         "DATETIME",        "NULL"),
            ("expires_at",         "DATETIME",        "NULL"),
            ("used_at",            "DATETIME",        "NULL"),
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

    # Backfill: neue Competition-Spalten in Bestandsdaten auf den ersten aktiven Wettbewerb setzen.
    # So bleiben bestehende BL1-Daten nach der Migration sichtbar und werden nicht als "global" behandelt.
    try:
        default_comp = (
            Competition.query.filter_by(is_active=True).order_by(Competition.id.asc()).first()
            or Competition.query.order_by(Competition.id.asc()).first()
        )
        if default_comp:
            scoped_tables = ["special_questions", "special_predictions", "prizes", "matchday_winners", "season_archive"]
            with engine.begin() as conn:
                for tbl in scoped_tables:
                    if tbl in existing_tables:
                        try:
                            conn.execute(text(
                                f'UPDATE "{tbl}" SET "competition_id" = :cid WHERE "competition_id" IS NULL'
                            ), {"cid": default_comp.id})
                        except Exception:
                            # Tabelle existiert, aber Spalte ggf. in sehr alten/abweichenden Schemas nicht.
                            pass
    except Exception as e:
        current_app.logger.warning(f"Auto-Migration: Competition-Backfill fehlgeschlagen: {e}")

    null_fixes = [
        ("users", "show_full_name", 1),
        ("users", "has_paid", 0),
        ("users", "notify_enabled", 1),
        ("users", "notify_email", 1),
        ("users", "notify_push", 1),
        ("users", "notify_telegram", 1),
        ("users", "notify_whatsapp", 1),
        ("users", "notify_hours_before", 1),
        ("users", "notify_only_favorite", 0),
        ("users", "default_tip_view", "normal"),
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
