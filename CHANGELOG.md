# Changelog – Wulmstörper Tipprunde

## [3.1.0] - 2026-05-18

### 🐛 Bugfixes & Optimierungen

**🔴 `datetime.utcnow()` deprecated (Python 3.12+)**
- `test_ai_opponent.py`: Alle 8 Stellen von `datetime.utcnow()` auf `datetime.now(timezone.utc)` umgestellt
- Beseitigt DeprecationWarnings, die ab Python 3.14 zu Fehlern führen

**🔴 SQLAlchemy 2.0: `Query.get()` → `db.session.get(Model, id)`**
- 13 Stellen in 5 Dateien migriert: `scoring.py`, `ai_opponent.py`, `live_scoring.py`, `admin_bots_routes.py`, `routes.py`, `mail_helpers.py`
- Beseitigt ~40 `LegacyAPIWarning`-Meldungen im Testlauf

**🟠 Paginierung eingeführt**
- Admin-User-Liste (`/admin/users`): 25 User pro Seite
- Kommentare pro Spiel: 10 Kommentare pro Seite
- Verhindert Performance-Probleme bei 50+ Usern / hunderter Kommentaren

**🟠 Session-Validierung für `competition_code`**
- `app.py`: Helper prüft den Session-Wert gegen existierende Competitions in der DB
- `scoring.py`: Fallback auf ersten aktiven Wettbewerb bei ungültigem Code
- Verhindert unerwartetes Verhalten bei manipulierten Session-Werten

**🟡 Hardcoded "2025/26" zentralisiert**
- `app.py`: Saison wird dynamisch aus `app.config["SEASON"]` generiert
- `export.py`: Saison wird über `get_setting("current_season")` aufgelöst
- Erleichtert Saisonwechsel – nur noch Config ändern statt 20+ Dateien

**🟡 GitHub Actions CI/CD**
- Neuer Workflow: `.github/workflows/tests.yml`
- Testet auf Python 3.10, 3.11, 3.12, 3.13
- flake8-Linting + pytest mit Coverage

**🟢 Markdown-Dokumentation aktualisiert**
- `CHANGELOG.md`: Dieser Eintrag
- `OPTIMIZATION_ROADMAP.md`: Gefixte Items als ✅ markiert
- `ANALYSE_BUNDESLIGA_TIPPSPIEL.md`: Test-Ergebnisse aktualisiert (39/39 ✅)
- `FEATURES.md`: Test-Info aktualisiert
- `README.md`: Badges + Test-Status aktualisiert

### ✅ Ergebnis
- **39/39 Tests bestanden** (vorher 28/39)
- **Warnings reduziert** von ~98 auf 2 (nur requests/urllib3)
- **Coverage**: 41% (unverändert, da Bugfixes hauptsächlich Infrastruktur)

---

## [3.0.0] - 2026-05-17

### 🏗️ Architektur-Refactoring

**app.py aufgeteilt** (2.494 → 294 Zeilen, -88%):
- `routes_main.py` (747 Zeilen) – Dashboard, Spielplan, Profil, Export, etc.
- `routes_auth.py` (82 Zeilen) – Login, Register, Passwort-Reset
- `routes_admin.py` (846 Zeilen) – Kompletter Admin-Bereich
- `routes_api.py` (307 Zeilen) – JSON API-Endpunkte

**utils.py aufgeteilt** (2.211 → 64 Zeilen Backward-Compat-Wrapper):
- `scoring.py` (446 Zeilen) – Punkteberechnung, Ranglisten, Pot, Spieltagsieger
- `badges.py` (148 Zeilen) – Badge-System, Vergabe, Prüfung, Seeding
- `stats.py` (497 Zeilen) – Statistiken, Trend, Insights, Form, H2H, Wetter, Tabelle
- `sync.py` (602 Zeilen) – API-Sync (football-data.org + OpenLigaDB), Seeding, Schema-Migration
- `mail_helpers.py` (108 Zeilen) – E-Mail, Token, Mail-Einstellungen
- `avatars.py` (49 Zeilen) – Avatar-Upload (PIL)
- `export.py` (181 Zeilen) – PDF-Export (reportlab)

`utils.py` existiert weiterhin als Re-Export-Wrapper für Abwärtskompatibilität
(sodass `scheduler.py`, `whatsapp.py` etc. ohne Änderung funktionieren).

### 🔒 Rate Limiting (Flask-Limiter)
- Login: 10 req/min
- Register: 5 req/min
- Passwort-Reset: 3 req/min
- API Tipp: 30 req/min
- API Leaderboard: 60 req/min
- Push Subscribe: 10 req/min

### ⚡ Performance-Optimierung (N+1 Queries)
- `get_leaderboard()` – Bulk-Query statt N Queries pro User
- Eager Loading mit `joinedload(Match.home_team, Match.away_team)`
- Sonderpunkte per GROUP BY in einer einzigen Query

### 📦 Neue Dependency
- `Flask-Limiter==3.0.3`
- `Flask-SQLAlchemy==3.1.1`
- `Flask-Login==0.6.3`
- `Flask-WTF==1.2.1`
- `Flask-Mail==0.10.0`
- `Flask-Limiter==3.5.1`
- `WTForms==3.1.2`
- `email-validator==2.2.0`
- `Werkzeug==3.0.4`
- `bleach==6.1.0`
- `python-dotenv==1.0.1`
- `python-dotenv==1.0.1`
- `psycopg2-binary==2.9.9`
- `gunicorn==23.0.0`

---

## [2.0.0] - 2025-05-15

### 🤖 KI-Tippgegner
- **5 Bots** mit unterschiedlichen Schwierigkeitsgraden (Easy bis Expert)
- Statistik-basierte Tipps (Form, Tabelle, H2H)
- Automatische Tippabgabe für alle offenen Spiele
- Integration in Rangliste (wie reguläre Spieler)
- Neue Datei: `ai_opponent.py`

### ⚡ Live-Scoring
- Echtzeit-Updates via Server-Sent Events (SSE)
- Live-Spielstände mit Minuten-Anzeige
- Ereignis-Tracking (Tore, Karten)
- REST API für Live-Daten
- Automatische Status-Änderung
- Neue Datei: `live_scoring.py`

### 🏆 Mehrere Wettbewerbe
- Unterstützung für Bundesliga, CL, DFB-Pokal, etc.
- Neues `Competition` Model
- `CompetitionTeam` für Wettbewerbs-spezifische Tabellen

### 💨 Redis Caching
- Transparentes Caching via `@cached` Decorator
- Cache-Invalidation bei Änderungen
- Funktioniert auch ohne Redis (degraded mode)
- Neue Datei: `cache.py`

### 🧪 Pytest Test-Suite
- Vollständige Testabdeckung
- Fixtures für User, Matches, Tipps
- Tests für Models, Routes, KI, Cache
- Coverage-Reporting

### 🐳 Docker Support
- Dockerfile für Container-Deployment
- docker-compose.yml mit PostgreSQL & Redis
- Separate Scheduler-Service

### 📦 Dependencies
```
redis==5.0.8
flask-caching==2.3.0
pytest==8.3.3
pytest-flask==1.3.0
pytest-cov==5.0.0
factory-boy==3.3.1
faker==28.4.1
```

> **Hinweis:** `numpy` und `scikit-learn` waren ursprünglich geplant,
> wurden aber zugunsten reiner Python-Algorithmen entfernt
> (bessere Kompatibilität mit Shared Hosting).

---

## Statistik

| Metrik | v1.0 | v2.0 | v3.0 | v3.1.0 |
|--------|------|------|------|--------|
| Python-Dateien | 9 | 17 | 29 | 30 (+ CI) |
| Code-Zeilen | ~4.800 | ~6.400 | ~8.500 | ~8.650 |
| Tests | 0 | 25+ | 25+ | 39 |
| Tests bestanden | - | - | 28/39 | **39/39** |
| Module (utils + routes) | 2 Monolithen | 2 Monolithen | 11 spezialisierte Module | 11 spezialisierte Module |

---

**Viel Spaß mit dem Tippspiel!** 🚀⚽
