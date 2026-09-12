"""Wetter-Koordinaten: Kuerzel-Lookup + Namens-Fallback (12.09.2026).

Anlass: fuer Aufsteiger Elversberg (und Paderborn/Schalke) gab es weder
Stadion-Pille noch Wetter-Pill, weil beide Karten nur den alten 18er-Kader
kannten. Der Fallback stellt sicher, dass ein unbekanntes TLA nicht mehr
das ganze Wetter-Feld aussteigen laesst.
"""
from types import SimpleNamespace

import pytest

from stats_live import STADIUM_COORDS, _coords_for_team


def test_code_lookup_hits_direct():
    team = SimpleNamespace(short_name="FCB", name="FC Bayern München")
    assert _coords_for_team(team) == STADIUM_COORDS["FCB"]


def test_name_fallback_for_unknown_code():
    # Elversberg mit fremdem TLA (z.B. "EVE") -> ueber den Namen trotzdem drin
    team = SimpleNamespace(short_name="EVE", name="SV 07 Elversberg")
    assert _coords_for_team(team) == STADIUM_COORDS["SVE"]
    assert _coords_for_team(SimpleNamespace(short_name="S04", name="FC Schalke 04")) == STADIUM_COORDS["S04"]
    assert _coords_for_team(SimpleNamespace(short_name="", name="SC Paderborn 07")) == STADIUM_COORDS["SCP"]


def test_unknown_team_has_no_weather():
    assert _coords_for_team(SimpleNamespace(short_name="HRO", name="Hansa Rostock")) is None
    assert _coords_for_team(None) is None


def test_all_three_promoted_have_stadium_and_weather_hooks():
    # Einfallstor-Test: jeder Aufsteiger-Code existiert in Wetter- UND Stadionkarte
    import stadiums
    for code, name in (("SVE", "SV 07 Elversberg"), ("SCP", "SC Paderborn 07"), ("S04", "FC Schalke 04")):
        assert code in STADIUM_COORDS, code
        assert stadiums.home_stadium_for(name), name
