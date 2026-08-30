"""App-interne Schema-Wartung und Migration-Versionierung.

Warum nicht nur Alembic? Auf Netcup/Shared Hosting ohne SSH ist ein kleiner,
admin-ausloesbarer Migrationsmechanismus praktikabler. Dieser ersetzt Alembic
nicht vollstaendig, gibt aber versionierte, nachvollziehbare Wartungsschritte.
"""
from datetime import datetime, timezone
from sqlalchemy import inspect, text

from extensions import db
from models import (
    SchemaMigration, Competition, Match, Prediction, Comment, User,
    SpecialQuestion, SpecialPrediction, Prize, MatchdayWinner, SeasonArchive,
    InvitationCode,
)


EXPECTED_SCHEMA = {
    "users": [
        "id", "username", "email", "password_hash", "notify_enabled", "notify_email",
        "notify_push", "notify_telegram", "notify_whatsapp", "notify_hours_before",
        "notify_only_favorite", "default_tip_view",
    ],
    "competitions": ["id", "code", "name", "season", "is_active"],
    "matches": ["id", "competition_id", "matchday", "home_team_id", "away_team_id", "kickoff", "status"],
    "predictions": ["id", "user_id", "match_id", "home_tip", "away_tip", "joker", "points"],
    "notification_log": ["id", "user_id", "match_id", "channel", "kind", "sent_at"],
    "admin_activity_log": ["id", "admin_user_id", "action", "message", "created_at"],
    "schema_migrations": ["id", "version", "description", "success", "applied_at"],
    "special_questions": ["id", "competition_id", "text", "answer_type", "deadline"],
    "special_predictions": ["id", "competition_id", "user_id", "question_id", "answer", "points"],
    "prizes": ["id", "competition_id", "rank", "title", "active"],
    "matchday_winners": ["id", "competition_id", "matchday", "user_id", "season"],
    "season_archive": ["id", "competition_id", "user_id", "season", "rank", "points"],
    "invitation_codes": [
        "id", "code", "invited_by_user_id", "email", "max_uses", "uses",
        "used_by_user_id", "created_at", "expires_at", "used_at",
    ],
}


def _table_columns(table_name):
    insp = inspect(db.engine)
    if table_name not in insp.get_table_names():
        return None
    return {c["name"] for c in insp.get_columns(table_name)}


def _add_column_if_missing(table, column, ddl_type, default_sql=None):
    cols = _table_columns(table)
    if cols is None or column in cols:
        return False
    default_clause = f" DEFAULT {default_sql}" if default_sql is not None else ""
    with db.engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl_type}{default_clause}'))
    return True


def _migration_baseline_auto_schema():
    """Stellt Tabellen/Spalten soweit moeglich her."""
    db.create_all()
    from sync import auto_migrate_schema
    auto_migrate_schema()
    return "db.create_all + auto_migrate_schema ausgefuehrt"


def _migration_user_notification_defaults():
    defaults = {
        "notify_enabled": 1,
        "notify_email": 1,
        "notify_push": 1,
        "notify_telegram": 1,
        "notify_whatsapp": 1,
        "notify_hours_before": 1,
        "notify_only_favorite": 0,
    }
    for col, default in defaults.items():
        # Falls alte DB die Spalte noch nicht hat, pragmatisch ergaenzen.
        typ = "INTEGER" if col == "notify_hours_before" else "BOOLEAN"
        _add_column_if_missing("users", col, typ, str(default))
        with db.engine.begin() as conn:
            conn.execute(text(f'UPDATE "users" SET "{col}" = :d WHERE "{col}" IS NULL'), {"d": default})
    return "User-Notification-Defaults gesetzt"


def _migration_backfill_competition_ids():
    comp = Competition.query.filter_by(is_active=True).order_by(Competition.id.asc()).first() \
        or Competition.query.order_by(Competition.id.asc()).first()
    if not comp:
        return "Keine Competition vorhanden; Backfill uebersprungen"
    scoped = [
        (SpecialQuestion, "special_questions"),
        (SpecialPrediction, "special_predictions"),
        (Prize, "prizes"),
        (MatchdayWinner, "matchday_winners"),
        (SeasonArchive, "season_archive"),
    ]
    changed = 0
    for _model, table in scoped:
        if "competition_id" in (_table_columns(table) or set()):
            with db.engine.begin() as conn:
                res = conn.execute(text(f'UPDATE "{table}" SET "competition_id" = :cid WHERE "competition_id" IS NULL'), {"cid": comp.id})
                changed += res.rowcount or 0
    return f"competition_id Backfill: {changed} Zeilen"




def _migration_user_default_tip_view():
    _add_column_if_missing("users", "default_tip_view", "VARCHAR(20)", "'normal'")
    with db.engine.begin() as conn:
        conn.execute(text('UPDATE "users" SET "default_tip_view" = :d WHERE "default_tip_view" IS NULL OR "default_tip_view" = :empty'), {"d": "normal", "empty": ""})
    return "users.default_tip_view gesetzt"

def _migration_invitation_codes_schema():
    """Stellt die Einladungscode-Tabelle explizit sicher.

    db.create_all() legt neue Tabellen normalerweise an. Diese Migration macht
    den Schritt im Schema-Center sichtbar und reparierbar, falls eine Netcup/Plesk
    Installation die Tabelle noch nicht besitzt.
    """
    InvitationCode.__table__.create(bind=db.engine, checkfirst=True)
    cols = {
        "code": ("VARCHAR(80)", None),
        "invited_by_user_id": ("INTEGER", None),
        "email": ("VARCHAR(120)", None),
        "max_uses": ("INTEGER", "1"),
        "uses": ("INTEGER", "0"),
        "used_by_user_id": ("INTEGER", None),
        "created_at": ("DATETIME", None),
        "expires_at": ("DATETIME", None),
        "used_at": ("DATETIME", None),
    }
    changed = 0
    for col, (ddl_type, default_sql) in cols.items():
        if _add_column_if_missing("invitation_codes", col, ddl_type, default_sql):
            changed += 1
    return f"invitation_codes sichergestellt; {changed} Spalte(n) ergaenzt"

def _migration_repair_orphan_logs_only():
    """Bewusst kein Delete: nur zaehlen und melden."""
    orphan_predictions = db.session.query(Prediction).outerjoin(Match, Prediction.match_id == Match.id).filter(Match.id.is_(None)).count()
    orphan_comments = db.session.query(Comment).outerjoin(Match, Comment.match_id == Match.id).filter(Match.id.is_(None)).count()
    return f"Orphan-Check: predictions={orphan_predictions}, comments={orphan_comments}"


MIGRATIONS = [
    ("2026_05_19_001_baseline_auto_schema", "Baseline: create_all und Auto-Migration", _migration_baseline_auto_schema),
    ("2026_05_19_002_user_notification_defaults", "User Notification Defaults auffuellen", _migration_user_notification_defaults),
    ("2026_05_19_003_backfill_competition_ids", "competition_id fuer saisonbezogene Daten auffuellen", _migration_backfill_competition_ids),
    ("2026_05_19_004_orphan_report", "Orphan-Daten pruefen und berichten", _migration_repair_orphan_logs_only),
    ("2026_08_11_001_invitation_codes_schema", "Einladungscode-Tabelle sicherstellen", _migration_invitation_codes_schema),
    ("2026_08_12_001_user_default_tip_view", "Standard-Tippansicht je User sicherstellen", _migration_user_default_tip_view),
]


def applied_versions():
    return {m.version for m in SchemaMigration.query.filter_by(success=True).all()}


def pending_migrations():
    done = applied_versions()
    return [(v, d, f) for v, d, f in MIGRATIONS if v not in done]


def run_pending_migrations():
    """Fuehrt alle offenen Migrationen aus und protokolliert sie."""
    results = []
    for version, description, func in pending_migrations():
        try:
            message = func()
            entry = SchemaMigration(
                version=version, description=description, success=True,
                message=str(message), applied_at=datetime.now(timezone.utc),
            )
            db.session.add(entry)
            db.session.commit()
            results.append({"version": version, "ok": True, "message": str(message)})
        except Exception as e:
            db.session.rollback()
            entry = SchemaMigration(
                version=version, description=description, success=False,
                message=str(e), applied_at=datetime.now(timezone.utc),
            )
            db.session.add(entry)
            db.session.commit()
            results.append({"version": version, "ok": False, "message": str(e)})
            break
    return results


def schema_status():
    """Liefert Status zu Tabellen/Spalten, Migrationen und einfachen Datenproblemen."""
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    missing_tables = sorted(set(EXPECTED_SCHEMA) - tables)
    missing_columns = {}
    for table, expected_cols in EXPECTED_SCHEMA.items():
        cols = _table_columns(table)
        if cols is None:
            continue
        missing = sorted(set(expected_cols) - cols)
        if missing:
            missing_columns[table] = missing

    orphan_predictions = 0
    orphan_comments = 0
    matches_without_competition = 0
    try:
        orphan_predictions = db.session.query(Prediction).outerjoin(Match, Prediction.match_id == Match.id).filter(Match.id.is_(None)).count()
        orphan_comments = db.session.query(Comment).outerjoin(Match, Comment.match_id == Match.id).filter(Match.id.is_(None)).count()
        matches_without_competition = Match.query.filter(Match.competition_id.is_(None)).count()
    except Exception:
        pass

    applied = SchemaMigration.query.order_by(SchemaMigration.applied_at.desc()).all()
    pending = pending_migrations()
    return {
        "tables_total": len(tables),
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "applied": applied,
        "pending": pending,
        "pending_count": len(pending),
        "orphan_predictions": orphan_predictions,
        "orphan_comments": orphan_comments,
        "matches_without_competition": matches_without_competition,
        "ok": not missing_tables and not missing_columns and not pending,
    }
