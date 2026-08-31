"""Vertragstests fuer das Refactoring vom 31.08.2026: stats.py und sync.py sind
in Fachmodule aufgeteilt (stats_personal/stats_live/stats_season bzw.
sync_shared/sync_football_data/sync_openligadb). Die Fassaden in stats.py und
sync.py muessen alle bisherigen Import-Namen und Monkeypatch-Ziele weiter
bereitstellen - sonst brechen Aufrufer und Test-Patches unmerklich.
"""
import importlib

import requests as real_requests

import stats
import sync


# ---------------------------------------------------------------- Namenslisten

SYNC_FACADE_NAMES = [
    # sync_shared
    "BUNDESLIGA_TEAMS", "KNOWN_TEAM_LOGO_FIXES",
    "season_code_from_label", "current_sync_season_code", "store_sync_result",
    "_team_color_from_name", "_resolve_or_create_team_from_fd", "_ensure_competition_team",
    "_find_existing_match", "_purge_stale_matches_for_comp",
    "_resolve_or_create_team_from_olb", "_OLB_TEAM_MAP",
    "_normalize_team_key", "_resolve_team_by_name",
    # sync_football_data
    "_fd_request", "sync_with_football_data", "_process_football_data",
    "fetch_live_standings", "fetch_live_match_updates",
    # sync_openligadb
    "_olb_get", "_olb_match_id", "_olb_team_name", "_olb_group_order_id", "_olb_kickoff",
    "_olb_is_finished", "_olb_results", "_olb_result_type_id", "_olb_score",
    "sync_with_openligadb", "_purge_external_other_than",
    "_fill_missing_from_openligadb", "sync_results",
]

STATS_FACADE_NAMES = [
    # stats_personal
    "get_user_trend", "_compute_rank_through", "get_user_insights",
    "get_match_tip_distribution", "get_user_stats_20",
    # stats_live
    "get_match_weather", "_weather_code_to_label", "compute_live_standings",
    "get_official_standings_positions", "get_team_position", "get_team_form", "get_h2h",
    # stats_season
    "_normalize", "_parse_list", "compare_special_answer", "evaluate_special_predictions",
    "get_eternal_table", "archive_season",
]

# Identitaets-Zuordnungen: Fassadenname -> Fachmodul (Kurzname).
SYNC_HOME = {
    "BUNDESLIGA_TEAMS": "sync_shared", "current_sync_season_code": "sync_shared",
    "store_sync_result": "sync_shared", "_olb_get": "sync_shared",
    "_olb_team_name": "sync_shared",
    "_fd_request": "sync_football_data", "fetch_live_standings": "sync_football_data",
    "sync_with_openligadb": "sync_openligadb", "sync_results": "sync_openligadb",
    "_olb_match_id": "sync_openligadb",
}
STATS_HOME = {
    "get_user_insights": "stats_personal", "get_user_stats_20": "stats_personal",
    "compute_live_standings": "stats_live", "get_team_form": "stats_live",
    "get_eternal_table": "stats_season", "archive_season": "stats_season",
    "evaluate_special_predictions": "stats_season",
}


# ---------------------------------------------------------------- Tests

def test_sync_fassade_re_exportiert_alle_namen():
    for name in SYNC_FACADE_NAMES:
        assert hasattr(sync, name), f"sync.{name} fehlt in der Fassade"


def test_stats_fassade_re_exportiert_alle_namen():
    for name in STATS_FACADE_NAMES:
        assert hasattr(stats, name), f"stats.{name} fehlt in der Fassade"


def test_fassaden_namen_zeigen_auf_die_fachmodule():
    for name, module in SYNC_HOME.items():
        owner = importlib.import_module(module)
        assert getattr(sync, name) is getattr(owner, name), (
            f"sync.{name} zeigt nicht auf {module}.{name}"
        )
    for name, module in STATS_HOME.items():
        owner = importlib.import_module(module)
        assert getattr(stats, name) is getattr(owner, name), (
            f"stats.{name} zeigt nicht auf {module}.{name}"
        )


def test_sync_requests_bleibt_monkeypatch_ziel():
    # Test-Patches nutzen sync.requests (Objektform) und 'sync.requests.get'
    # (Stringform). Beide muessen das echte requests-Modul erreichen, denn die
    # Fachmodule importieren dasselbe Modulobjekt.
    assert sync.requests is real_requests
    assert sync.requests.get is real_requests.get


def test_import_graph_azyklisch_und_frisch_importierbar():
    # Zyklus-Schutz: alle Fachmodule muessen isoliert importierbar sein.
    for module in ("sync_shared", "sync_football_data", "sync_openligadb",
                   "stats_personal", "stats_live", "stats_season"):
        importlib.import_module(module)
