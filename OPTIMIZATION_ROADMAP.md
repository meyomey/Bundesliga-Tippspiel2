# 🔧 Optimierungs- & Feature-Roadmap

> Stand: Mai 2026 – Analyse der gesamten Codebase

---

## 🔴 Kritisch (Sicherheit & Stabilität)

### 1. XSS-Lücke in Kommentaren
✅ **GEFIXT** – `bleach` in `routes_main.py` wird bereits genutzt. Zusätzlich escaped Jinja2 standardmäßig.

### 2. AI Opponent: Module-Level DB-Query
✅ **GEFIXT** – Lazy-Init Pattern via `_ai_manager = None` + `get_ai_manager()` implementiert.
`ai_manager` ist ein Proxy-Objekt (`_AIManagerProxy`), das erst bei erstem Zugriff die DB-Query macht.

### 3. Flask-Limiter nutzt `memory://` statt Redis
✅ **BEREITS GEFIXT** – In `extensions.py` wird bereits `os.environ.get("REDIS_URL", "memory://")` verwendet.
In Produktion mit Redis einfach `REDIS_URL` setzen.

### 4. `datetime.utcnow()` deprecated (Python 3.12+)
✅ **GEFIXT** (v3.1.0) – Alle Stellen in Tests auf `datetime.now(timezone.utc)` umgestellt.
Keine DeprecationWarnings mehr.

---

## 🟠 Wichtig (Performance)

### 5. Fehlende DB-Indizes
✅ **BEREITS VORHANDEN** – Alle relevanten Spalten haben bereits `index=True`:
- `Match.status`, `Match.kickoff`, `Match.matchday`, `Match.competition_id`
- `Prediction.user_id`, `Prediction.match_id`
- `Comment.match_id`, `Comment.user_id`
- `UserBadge.user_id`, `UserBadge.badge_id`

### 6. admin_bots_routes: N+1 Queries (5 Bots = 15+ Queries)
✅ **GEFIXT** (Fix-Ordner übernommen) – Bulk-Query mit GROUP BY + CASE.
1 Query statt 15+ für Bot-Statistiken.

### 7. `Match.query.all()` lädt ALLE Spiele für matchdays-Liste
✅ **GEFIXT** (Fix-Ordner übernommen) – Nutzt `db.session.query(Match.matchday).distinct().all()`
statt 306 Entitäten zu laden.

### 8. Keine Paginierung
✅ **GEFIXT** (v3.1.0) – Paginierung für:
- Admin-User-Liste: 25 User/Seite
- Kommentare pro Spiel: 10 Kommentare/Seite
- Nächstes Ziel: Rangliste paginieren

---

## 🟡 Mittel (Code-Qualität)

### 9. Hardcoded "2025/26" / "BL1" überall
✅ **GEFIXT** (v3.1.0) – Saison wird zentral aus Config/Settings aufgelöst:
- `app.py`: Dynamisch aus `app.config["SEASON"]`
- `export.py`: Über `get_setting("current_season")`
- `BL1`-Hardcoding bleibt als Fallback erhalten, ist aber über Config steuerbar

### 10. `session["competition_code"]` ohne Validierung
✅ **GEFIXT** (v3.1.0) – Helper validiert Session-Wert gegen DB.
Fallback auf ersten aktiven Wettbewerb bei ungültigem Code.
`scoring.py` hat ebenfalls Fallback.

### 11. Tests haben falsche URLs
✅ **BEREITS KORREKT** – Tests nutzen bereits die deutschen URLs:
`/spielplan`, `/tabelle`, `/admin/`, `/api/tip/<id>`.

### 12. Kein `.github/workflows/tests.yml`
✅ **GEFIXT** (v3.1.0) – Workflow angelegt mit:
- Python 3.10, 3.11, 3.12, 3.13
- flake8-Linting
- pytest + Coverage

---

## 🟢 Nice-to-Have (Features)

### 13. htmx statt Vanilla JS für dynamische Updates
**Status:** 🔄 Offen
**Problem:** 10 Templates mit inline JavaScript (~150 Zeilen), manuelle DOM-Manipulation
**Idee:** htmx einbinden (nur ein `<script>` Tag) + serverseitige Partial-Templates

### 14. Alembic/Flask-Migrate für Schema-Migrationen
**Status:** 🔄 Offen
**Problem:** `auto_migrate_schema()` ist pragmatisch, aber riskant für PostgreSQL
**Idee:** Flask-Migrate für saubere Migrationen

### 15. Rangliste-Paginierung
**Status:** 🔄 Offen
**Problem:** Bei 50+ Usern wird die Rangliste unübersichtlich
