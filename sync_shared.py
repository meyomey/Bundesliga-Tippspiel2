"""Gemeinsame Sync-Bausteine: Konstanten, Saisoncode, Team-Aufloesung, Match-Abgleich, store_sync_result.

 Ausgelagert aus sync.py (Refactoring 31.08.2026); sync.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from datetime import datetime, timezone

from flask import current_app

from extensions import db
from models import Team, Match, Prediction, Comment, Competition, CompetitionTeam
from scoring import get_setting, set_setting

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



def store_sync_result(result):
    """Speichert das letzte Sync-Ergebnis fuer Admin-Diagnose."""
    payload = dict(result or {})
    payload["at"] = datetime.now(timezone.utc).isoformat()
    try:
        set_setting("last_sync_result", payload)
    except Exception:
        pass
    return payload




# ================================================== OpenLigaDB Dict-Helfer --
# Bewusst hier (statt im OLB-Modul): die Team-Aufloesung (sync_shared) und
# der OLB-Client nutzen sie gemeinsam - sonst entstuende ein Import-Zyklus.
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


def _olb_team_name(team_dict):
    if not isinstance(team_dict, dict):
        return None
    return _olb_get(team_dict, "teamName", "TeamName", "shortName", "ShortName")
