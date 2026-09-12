"""Feste Heimstadium-Karte (12.09.2026): Zuordnung + Sync-Fallback.

Hintergrund: Free-Plan von football-data liefert kein `venue` (Diagnose-
Zaehler 12.09.: 0/306), OLB ebenso nicht - die Karte fuellt Luecken mit
stabilen oeffentlichen Fakten. Feed-Werte haben stets Vorrang, Unbekanntes
bleibt leer (kein Schaetzen).
"""
import pytest

import stadiums
import sync
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
        # 2. Lauf ohne Feed-venue am gespeicherten Spiel: Ueberschreiben verboten
        data2 = {"matches": [_fd_match(9203, "Werder Bremen", "TSG Hoffenheim")]}
        res2 = sync._process_football_data(data2, bl1.id, source="test")
        assert by_ext["fd:9203"].venue == "Speicher XI"
        assert res2["venues_map"] == 0  # vorhandener Wert bleibt unangetastet


def test_maps_url_builds_keyless_search_link():
    url = stadiums.maps_url("Allianz Arena", "FC Bayern München")
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Allianz%20Arena" in url and "Bayern" in url
    assert "%2C" in url  # Komma zwischen Arena und Verein ist escaped
    # Ohne Stadion gibt es keinen Link; ohne Verein bleibt der Query beim Namen
    assert stadiums.maps_url(None) is None
    assert stadiums.maps_url("Voith-Arena").endswith("query=Voith-Arena")
