"""Feste Heimstadium-Karte (12.09.2026): Zuordnung + Sync-Fallback.

Hintergrund: Free-Plan von football-data liefert kein `venue` (Diagnose-
Zaehler 12.09.: 0/306), OLB ebenso nicht - die Karte fuellt Luecken mit
stabilen oeffentlichen Fakten. Feed-Werte haben stets Vorrang, Unbekanntes
bleibt leer (kein Schaetzen).
"""
import pytest

import stadiums
import sync
from sync import get_sync_diagnostics
from models import Competition


def test_lookup_matches_known_clubs():
    assert stadiums.home_stadium_for("FC Bayern München") == "Allianz Arena"
    assert stadiums.home_stadium_for("Borussia Dortmund") == "Signal Iduna Park"
    assert stadiums.home_stadium_for("1. FC Köln") == "RheinEnergieStadion"
    assert stadiums.home_stadium_for("RB Leipzig") == "Red Bull Arena Leipzig"
    assert stadiums.home_stadium_for("Borussia Mönchengladbach") == "Borussia-Park"
    assert stadiums.home_stadium_for("1. FSV Mainz 05") == "MEWA Arena"
    assert stadiums.home_stadium_for("Fortuna Düsseldorf") == "Merkur Spiel-Arena"
    assert stadiums.home_stadium_for("1. FC Nürnberg") == "Max-Morlock-Stadion"
    assert stadiums.home_stadium_for("FC St. Pauli") == "Millerntor-Stadion"
    assert stadiums.home_stadium_for("Hamburger SV") == "Volksparkstadion"


def test_lookup_covers_promoted_clubs_2026():
    # Luecke vom 12.09.: Aufsteiger fehlten komplett (weder Pille noch Wetter)
    assert stadiums.home_stadium_for("SV 07 Elversberg") == "Ursapharm-Arena an der Kaiserlinde"
    assert stadiums.home_stadium_for("SC Paderborn 07") == "Home Deluxe Arena"
    assert stadiums.home_stadium_for("FC Schalke 04") == "VELTINS-Arena"


def test_lookup_stays_silent_for_unknown():
    assert stadiums.home_stadium_for("SV Testwald") is None
    assert stadiums.home_stadium_for(None) is None
    assert stadiums.home_stadium_for("") is None
    # "Union" allein ist nicht eindeutig -> nur mit Berlin-Kontext
    assert stadiums.home_stadium_for("Union Salt Lake City") is None


def _fd_match(mid, home, away, venue=None):
    m = {"id": mid, "utcDate": "2026-09-05T13:30:00Z", "matchday": 3,
         "status": "SCHEDULED",
         "homeTeam": {"id": 10000 + mid, "name": home, "shortName": home[:3].upper(), "tla": home[:3].upper()},
         "awayTeam": {"id": 20000 + mid, "name": away, "shortName": away[:3].upper(), "tla": away[:3].upper()},
         "score": {"fullTime": {"home": None, "away": None}}}
    if venue:
        m["venue"] = venue
    return m


@pytest.fixture
def bl1(db):
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    return comp


def test_sync_backfills_from_map_but_feed_wins(db, app, bl1):
    data = {"matches": [
        _fd_match(9201, "FC Bayern München", "Borussia Dortmund"),          # Karte greift
        _fd_match(9202, "SV Testwald", "SV Prüfing"),                        # unbekannt -> leer
        _fd_match(9203, "Werder Bremen", "TSG Hoffenheim", venue="Speicher XI"),  # Feed gewinnt
    ]}
    with app.app_context():
        res = sync._process_football_data(data, bl1.id, source="test")
        # 1x Feed (9203), 1x Karte (Heim Bayern); Hoffenheim ist nur AUSWAERTS
        assert res["venues"] == 1 and res["venues_map"] == 1
        from models import Match
        by_ext = {m.external_id: m for m in Match.query.all()}
        assert by_ext["fd:9201"].venue == "Allianz Arena"
        assert by_ext["fd:9202"].venue is None
        assert by_ext["fd:9203"].venue == "Speicher XI"
        assert "Stadion: 1 aus Feed, 1 aus Festdaten" in res["msg"]
        # Fruehwarnung: Testwald ist unbekannt -> gemeldet und persistiert
        assert res["venues_missing"] == ["SV Testwald"]
        assert "ohne Stadion-Karte: SV Testwald" in res["msg"]
        from scoring import get_setting
        assert get_setting("stadium_gap_teams") == '["SV Testwald"]'
        assert get_sync_diagnostics()["stadium_gaps"] == ["SV Testwald"]
        # 2. Lauf ohne Feed-venue am gespeicherten Spiel: Ueberschreiben verboten
        data2 = {"matches": [_fd_match(9203, "Werder Bremen", "TSG Hoffenheim")]}
        res2 = sync._process_football_data(data2, bl1.id, source="test")
        assert by_ext["fd:9203"].venue == "Speicher XI"
        assert res2["venues_map"] == 0  # vorhandener Wert bleibt unangetastet
        # ...und die Fehlliste heilt: 2. Lauf kennt nur Werder (Karte ok)
        assert res2["venues_missing"] == []
        assert get_setting("stadium_gap_teams") == "[]"
        assert "ohne Stadion-Karte" not in res2["msg"]
        assert get_sync_diagnostics()["stadium_gaps"] == []


def test_status_sits_at_kickoff_not_in_badges():
    """Nutzerfeedback 12.09.: GEPLANT/Pille/Wetter zusammen = Ellipsen-Not.
    Status steht jetzt in der Anpfiff-Zeile (.tu-kickoff-row), die
    Badges-Zeile gehoert allein Stadion + Wetter (und entfaellt leer ganz)."""
    import pathlib
    html = pathlib.Path("templates/match_detail.html").read_text(encoding="utf-8")
    assert html.count("tu-kickoff-row") == 1
    assert html.index('class="tu-kickoff-row"') < html.index('class="tu-top-badges"')
    assert html.index("status-scheduled") < html.index('class="tu-top-badges"')
    assert "{% if match.venue or weather %}" in html


def test_combo_pill_keeps_one_line_layout():
    """Mobile-Fix 12.09.: Suche + Routing stecken in EINER Pille (Combo),
    die CSS-Seite garantiert einzeilig (nowrap + Ellipse)."""
    import pathlib
    html = pathlib.Path("templates/match_detail.html").read_text(encoding="utf-8")
    assert 'class="tu-venue-combo"' in html
    assert html.count('tu-venue-combo') == 1
    css = pathlib.Path("static/css/style.css").read_text(encoding="utf-8")
    # Zeile 1 fixiert: Container bricht nicht mehr um, Wetter/Status schrumpfen nicht
    badges = css[css.rindex(".tu-top-badges {"):][:130]
    assert "flex-wrap: nowrap" in badges
    assert "flex: none" in css[css.rindex(".tu-weather-pill {"):][:90]
    # Status wohnt nicht mehr in den Badges (wanderte 12.09. zur Anpfiff-Zeile)
    assert ".tu-top-badges .status" not in css
    at = css.rindex(".tu-venue-combo {")
    block = css[at:at + 260]
    assert "white-space: nowrap" in block and "overflow: hidden" in block
    assert "text-overflow: ellipsis" in css[css.rindex(".tu-venue-combo .tvp-text"):]


def test_maps_url_builds_keyless_search_link():
    url = stadiums.maps_url("Allianz Arena", "FC Bayern München")
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Allianz%20Arena" in url and "Bayern" in url
    assert "%2C" in url  # Komma zwischen Arena und Verein ist escaped
    # Ohne Stadion gibt es keinen Link; ohne Verein bleibt der Query beim Namen
    assert stadiums.maps_url(None) is None
    assert stadiums.maps_url("Voith-Arena").endswith("query=Voith-Arena")


def test_maps_route_url_is_directions_deeplink():
    url = stadiums.maps_route_url("Allianz Arena", "FC Bayern München")
    assert url.startswith("https://www.google.com/maps/dir/?api=1&destination=")
    assert "Allianz%20Arena" in url and "Bayern" in url
    assert stadiums.maps_route_url(None) is None
    assert stadiums.maps_route_url("Voith-Arena").endswith("destination=Voith-Arena")
