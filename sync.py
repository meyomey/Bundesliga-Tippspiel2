"""API-Sync: Kernmodul (Logos, Seeding, Diagnose, Schema-Migration) + Fassade.

Die Fachbereiche wurden am 31.08.2026 ausgelagert (sync_shared,
sync_football_data, sync_openligadb); dieses Modul re-exportiert alle Namen. Ausgelagert aus sync.py (Refactoring 31.08.2026); sync.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from datetime import datetime, timedelta, timezone

import requests
from flask import current_app
from sqlalchemy import inspect, text

from extensions import db
from models import Team, Match, Competition, CompetitionTeam, InvitationCode
from scoring import get_setting

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
    from scoring import recalculate_all_points
    recalculate_all_points()
    return Match.query.count()


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

# ============================================================ Fassade -------
# Re-Exports: bestehende Importeure (from sync import ...) funktionieren
# unveraendert weiter; ebenso Test-Monkeypatches auf sync.<name>.
from sync_shared import (  # noqa: F401
    BUNDESLIGA_TEAMS, KNOWN_TEAM_LOGO_FIXES,
    season_code_from_label, current_sync_season_code, store_sync_result,
    _team_color_from_name, _resolve_or_create_team_from_fd, _ensure_competition_team,
    _find_existing_match, _purge_stale_matches_for_comp, _resolve_or_create_team_from_olb,
    _OLB_TEAM_MAP, _normalize_team_key, _resolve_team_by_name,
)
from sync_football_data import (  # noqa: F401
    _fd_request, sync_with_football_data, _process_football_data,
    fetch_live_standings, fetch_live_match_updates,
)
from sync_openligadb import (  # noqa: F401
    _olb_get, _olb_match_id, _olb_team_name, _olb_group_order_id, _olb_kickoff,
    _olb_is_finished, _olb_results, _olb_result_type_id, _olb_score,
    sync_with_openligadb, _purge_external_other_than, _fill_missing_from_openligadb,
    sync_results,
)
