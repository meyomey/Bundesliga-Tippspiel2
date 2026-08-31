# Migrations-Strategie: Warum (aktuell) kein Alembic

**Stand:** 2026-08-31 · **Status:** bewusste Architektur-Entscheidung

## Entscheidung

Alembic wird in diesem Projekt **nicht** eingeführt. Das Schema wird stattdessen
über zwei app-interne, getestete Mechanismen gepflegt:

1. **`sync.py: auto_migrate_schema()`** — fügt beim App-Start fehlende Spalten
   idempotent zur SQLite-DB hinzu (nur SQLite; andere Treiber werden übersprungen).
2. **`schema_migrations.py` + Tabelle `schema_migrations` (Modell `SchemaMigration`)** —
   versionierte Wartungsschritte mit Erfolg-Tracking, Pending-Erkennung und
   Admin-Oberfläche (`/admin/schema`), inkl. Abdeckung in `tests/test_schema_migrations.py`.

## Begründung

- **Hosting ohne SSH (Netcup/Plesk, Passenger/WSGI):** Alembics Standard-Workflow
  (`alembic upgrade head` auf der Konsole) ist auf dem Produktiv-Host nicht ausführbar.
  Migrationen müssen beim App-Start oder über eine Admin-Oberfläche laufen —
  genau das leisten die internen Mechanismen bereits.
- **Vendor-Packaging:** Neue Pakete müssen doppelt gepflegt werden
  (`requirements.txt` **und** `requirements_py39.txt`) und über `build_vendor.bat`
  in `vendor/` paketiert + per FTP nachgezogen. Alembic + SQLAlchemy-Abhängigkeiten
  wären dauerhafter Deploy-Ballast für einen Nutzen, der produktiv nicht abrufbar ist.
- **Single Source of Truth:** Ein zweites Migrationssystem neben `SchemaMigration`
  riskiert Drift (Doppel-Ausführung, widersprüchliche Versionstände).
- **SQLite-Tauglichkeit:** Alembic-ALTERs auf SQLite erfordern Batch-Mode
  (`render_as_batch`); der interne Pfad nutzt bewusst einfache, gut testbare
  `ALTER TABLE … ADD COLUMN` patterns plus Daten-Wartungsschritte.

## Werden intern abgedeckt (Alembic-Kernnutzen)

| Alembic-Nutzen | Interne Abdeckung |
|---|---|
| Versionierung | `SchemaMigration`-Tabelle (version, description, success, applied_at) |
| Pending-Erkennung | `schema_status()` / `pending_migrations()` |
| Ausführung | Admin-UI `/admin/schema` + `run_pending_migrations()` |
| Schema-Drift-Prüfung | `EXPECTED_SCHEMA` in `schema_migrations.py` + Integritäts-Checks |
| Tests | `tests/test_schema_migrations.py` |

## Wann neu bewerten?

- Wechsel zu einem Hosting **mit Shell-Zugang** (z. B. VPS) oder
- Umstieg auf **PostgreSQL/MySQL** mit komplexeren Migrationen (Index-Umbauten,
  Foreign-Key-Änderungen, Daten-Migrationen über mehrere Releases) oder
- mehrere aktive Entwickler mit parallelen Schema-Branches.

Dann: Alembic als **alleinigen** Mechanismus einführen, `auto_migrate_schema()`
und die `SchemaMigration`-Liste auf die Alembic-History migrieren und den
Admin-Endpunkt auf `upgrade head` umbauen.
