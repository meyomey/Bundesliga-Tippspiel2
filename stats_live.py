"""Live-/Tabellen-Statistiken: Wetter, Bundesliga-Tabelle, Form, H2H.

 Ausgelagert aus stats.py (Refactoring 31.08.2026); stats.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

import requests

from models import Team, Match
from competition_helpers import filter_matches_for_active_competition

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
    "SVE": (49.2983, 7.0549),      # Ursapharm-Arena an der Kaiserlinde (Aufsteiger 2026/27)
    "SCP": (51.7203, 8.7677),      # Home Deluxe Arena, Paderborn
    "S04": (51.5774, 7.1320),      # VELTINS-Arena, Gelsenkirchen
}

# Keyword-Fallback (12.09.2026): neue Aufsteiger/-innen oder andere
# TLA-Schreibweisen des Feeds sollen das Wetter nicht sofort aussteigen
# lassen - wenn das Kuerzel fehlt, zaehlt der Vereinsname.
_COORD_KEYWORDS = [
    (("bayern",), "FCB"),
    (("dortmund",), "BVB"),
    (("leverkusen",), "B04"),
    (("leipzig",), "RBL"),
    (("stuttgart",), "VFB"),
    (("eintracht", "frankfurt"), "SGE"),
    (("wolfsburg",), "WOB"),
    (("monchengladbach", "gladbach"), "BMG"),
    (("freiburg",), "SCF"),
    (("union", "berlin"), "FCU"),
    (("hoffenheim",), "TSG"),
    (("mainz",), "M05"),
    (("augsburg",), "FCA"),
    (("werder",), "SVW"),
    (("heidenheim",), "FCH"),
    (("pauli",), "STP"),
    (("hamburger",), "HSV"),
    (("koeln",), "KOE"),
    (("elversberg",), "SVE"),
    (("paderborn",), "SCP"),
    (("schalke",), "S04"),
]


def _coords_for_team(team):
    """Stadion-Koordinaten: erst Kuerzel-Lookup, dann Namens-Fallback."""
    if team is None:
        return None
    code = (team.short_name or "").upper()
    if code in STADIUM_COORDS:
        return STADIUM_COORDS[code]
    name = (team.name or "").lower().replace("ä", "ae").replace("ö", "oe") \
        .replace("ü", "ue").replace("ß", "ss")
    if not name:
        return None
    for keywords, coord_code in _COORD_KEYWORDS:
        if all(k in name for k in keywords) and coord_code in STADIUM_COORDS:
            return STADIUM_COORDS[coord_code]
    return None


def get_match_weather(match):
    """Holt Wetter vom Open-Meteo (kostenlos, kein Key)."""
    coords = _coords_for_team(match.home_team)
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
def compute_live_standings(include_live=True):
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
        "in_play": False,  # (144) Team steht gerade auf dem Platz
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

    # (144) Laufende Spiele einrechnen: der OLB-Live-Boost haelt die
    # aktuellen Stände in der DB - die Tabelle kann damit waehrend des
    # Spieltags sekundenscharf sein. Gezählt wird das laufende Spiel
    # (wie in TV-Tabellen), betroffene Team-Zeilen werden markiert.
    # (146) include_live=False = reine Gesamttabelle (nur fertige Spiele).
    live_q = Match.query.filter_by(status="live") if include_live else Match.query.filter_by(status="__none__")
    live_q = filter_matches_for_active_competition(live_q)
    for m in live_q.all():
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
        h["in_play"] = True
        a["in_play"] = True

    for t in table.values():
        t["goal_diff"] = t["goals_for"] - t["goals_against"]

    rows = sorted(table.values(), key=lambda r: (
        -r["points"], -r["goal_diff"], -r["goals_for"], r["team"].name
    ))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def prev_rank_map():
    """(148) Referenz fuer Platz-Verschiebe-Pfeile in der Livetabelle.

    Konvention wie bei der Tipprunden-Rangliste ((119)/(120)): laeuft ein
    Spieltag, ist die Referenz der STAND NACH DEM LETZTEN VOLLSTAENDIGEN
    SPIELTAG - Ergebnisse desselben (laufenden) Spieltags veraendern die
    Referenz nicht, auch wenn sie schon abgeschlossen sind. Laeuft kein
    Spiel, bleibt die Map leer -> keine Pfeile.
    Rueckgabe: {team_id: platz_vor_dem_spieltag}.
    """
    first_live = (Match.query.filter_by(status="live")
                  .with_entities(Match.matchday)
                  .order_by(Match.matchday.asc()).first())
    if not first_live or not first_live[0]:
        return {}
    ref_md = first_live[0]  # alles DAVOR ist Referenz
    q = Match.query.filter(Match.status == "finished", Match.matchday < ref_md)
    q = filter_matches_for_active_competition(q)
    matches = q.all()
    if not matches:
        return {}
    from models import Team
    from extensions import db as _db
    table = {}
    for m in matches:
        if m.home_score is None or m.away_score is None:
            continue
        for tid in (m.home_team_id, m.away_team_id):
            if tid not in table:
                table[tid] = {"played": 0, "won": 0, "drawn": 0, "lost": 0,
                              "gf": 0, "ga": 0, "pts": 0, "name": ""}
        h, a = table[m.home_team_id], table[m.away_team_id]
        h["played"] += 1; a["played"] += 1
        h["gf"] += m.home_score; h["ga"] += m.away_score
        a["gf"] += m.away_score; a["ga"] += m.home_score
        if m.home_score > m.away_score:
            h["won"] += 1; h["pts"] += 3; a["lost"] += 1
        elif m.home_score == m.away_score:
            h["drawn"] += 1; a["drawn"] += 1; h["pts"] += 1; a["pts"] += 1
        else:
            a["won"] += 1; a["pts"] += 3; h["lost"] += 1
    for tid, r in table.items():
        team = _db.session.get(Team, tid)
        r["name"] = team.name if team else ""
    ordered = sorted(table.items(),
                     key=lambda kv: (-kv[1]["pts"],
                                     -(kv[1]["gf"] - kv[1]["ga"]),
                                     -kv[1]["gf"], kv[1]["name"]))
    return {tid: i for i, (tid, _r) in enumerate(ordered, 1)}


def count_live_matches():
    """(144) Anzahl laufender Spiele im aktiven Wettbewerb."""
    from competition_helpers import filter_matches_for_active_competition
    q = Match.query.filter_by(status="live")
    return filter_matches_for_active_competition(q).count()


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


