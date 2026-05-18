# 🚀 Features – Wulmstörper Tipprunde

Übersicht aller implementierten Features und der aktuellen Architektur.

---

## Architektur (v3.1.0)

```
app.py (App-Factory, ~300 Zeilen)
  ├── routes_main.py    → Hauptroutes (Dashboard, Spielplan, Profil, …)
  ├── routes_auth.py    → Login, Register, Passwort-Reset
  ├── routes_admin.py   → Admin-Bereich
  ├── routes_api.py     → JSON API
  ├── live_scoring.py   → Live-Scoring (SSE)
  ├── push_routes.py    → Web Push
  └── pwa_routes.py     → PWA

Utility-Module:
  ├── scoring.py        → Punkte, Ranglisten, Pot, Spieltagsieger
  ├── badges.py         → Badge-System
  ├── stats.py          → Statistiken, Trend, Insights, Form, H2H, Wetter
  ├── sync.py           → API-Sync, Seeding, Schema-Migration
  ├── mail_helpers.py   → E-Mail, Token
  ├── avatars.py        → Avatar-Upload
  └── export.py         → PDF/CSV-Export

KI & Extra:
  ├── ai_opponent.py    → 5 KI-Bots (Rookie→Master)
  ├── cache.py          → Redis-Cache-Wrapper
  ├── admin_bots_routes.py → Bot-Verwaltung
  └── whatsapp.py       → WhatsApp-Integration
```

---

## 1. 🤖 KI-Tippgegner

Fünf computergesteuerte Gegner mit unterschiedlichen Schwierigkeitsgraden.

| Bot | Stärke | Strategie |
|-----|--------|-----------|
| **RookieBot** | ⭐ | Viel Zufall |
| **AmateurBot** | ⭐⭐ | Heimvorteil |
| **ProBot** | ⭐⭐⭐ | Statistik + Zufall |
| **ExpertBot** | ⭐⭐⭐⭐ | Form + Tabelle |
| **MasterBot** | ⭐⭐⭐⭐⭐ | Form + Tabelle + H2H |

**Verwendung:**
```python
from ai_opponent import get_ai_manager
results = get_ai_manager().tip_all_matches(matchday=5)
```

**Admin-UI:** ✅ Vorhanden (`/admin/bots`)

---

## 2. ⚡ Live-Scoring

Echtzeit-Updates via Server-Sent Events (SSE).

**API Endpunkte:**
```
GET  /live/matches              # Alle Live-Spiele
GET  /live/match/<id>           # Details + Statistik
GET  /live/match/<id>/stream    # SSE Stream
GET  /live/user/predictions     # Eigene Live-Tipps
POST /live/admin/update/<id>    # Admin: Update
POST /live/admin/finish/<id>    # Admin: Beenden
```

**Frontend:** Live-Center unter `/live` mit Polling + SSE.

---

## 3. 🏆 Mehrere Wettbewerbe

Unterstützung für verschiedene Wettbewerbe (Bundesliga, CL, DFB-Pokal).

**Modelle:** `Competition`, `CompetitionTeam`

**Wettbewerb-Wechsler:** ✅ Vorhanden (Session-basiert, Dropdown in Navigation)

---

## 4. 💨 Redis Caching

| Daten | TTL | Invalidierung |
|-------|-----|---------------|
| Ranglisten | 2 Min | Bei Tipp/Ergebnis |
| Live-Matches | 30 Sek | Bei Update |
| API-Responses | 30-60 Sek | Automatisch |

**Ohne Redis** läuft die App normal weiter (Cache deaktiviert).

**Cache-Monitoring:** ✅ Vorhanden (`/admin/cache`)

---

## 5. 🔒 Rate Limiting

| Endpunkt | Limit |
|----------|-------|
| `/auth/login` | 10/min |
| `/auth/register` | 5/min |
| `/auth/passwort-vergessen` | 3/min |
| `/api/tip/<id>` | 30/min |
| `/api/leaderboard` | 60/min |

---

## 6. ⚡ Performance-Optimierung

- **N+1 Query-Problem gelöst:** `get_leaderboard()` lädt alle Predictions in einer Bulk-Query
- **Bot-Admin:** Group By/CASE statt 15+ Einzel-Queries
- **Matchdays-Liste:** `distinct().all()` statt 306 Entitäten laden
- **DB-Indizes:** Alle relevanten Spalten indiziert
- **Paginierung:** Admin-User (25/Seite), Kommentare (10/Seite)

---

## 7. 🧪 Pytest Suite

```
tests/
├── conftest.py          # Fixtures
├── test_models.py       # Model-Tests
├── test_routes.py       # Route-Tests
├── test_ai_opponent.py  # KI-Tests
└── test_cache.py        # Cache-Tests
```

```bash
pytest                                    # Alle Tests (39 ✅)
pytest --cov=. --cov-report=html          # Mit Coverage (41%)
pytest -v --tb=short                      # Ausführlich
pytest tests/test_models.py -v            # Spezifische Datei
```

---

## 8. 🔧 Bugfixes (v3.1.0)

| Fix | Details |
|-----|---------|
| `datetime.utcnow()` deprecated | Alle Stellen auf `datetime.now(timezone.utc)` |
| SQLAlchemy 2.0 Legacy | 13× `Query.get()` → `db.session.get(Model, id)` |
| Session-Validierung | `competition_code` gegen DB geprüft |
| Hardcoded Saison | Zentral über Config/Settings |
| GitHub Actions CI | Workflow für Python 3.10-3.13 |

---

## 📦 Dependencies

```txt
# Core
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1
Flask-Mail==0.10.0
Flask-Limiter==3.5.1
WTForms==3.1.2
Werkzeug==3.0.4

# Daten & APIs
requests==2.32.3
redis==5.0.8
flask-caching==2.3.0

# Bilder & Export
Pillow==10.4.0
reportlab==4.2.2

# Sicherheit
bleach==6.1.0
email-validator==2.2.0

# Testing
pytest==8.3.3
pytest-flask==1.3.0
pytest-cov==5.0.0
factory-boy==3.3.1
faker==28.4.1

# Deployment
gunicorn==23.0.0
psycopg2-binary==2.9.9
python-dotenv==1.0.1
```

> **Hinweis:** `numpy` und `scikit-learn` werden **nicht** mehr benötigt.
> Die KI-Bots nutzen reine Python-Algorithmen Python-Algorithmen (Poisson-Verteilung etc.).

---

## 🎯 Nächste Schritte

Noch nicht implementierte Feature-Ideen:

1. **OAuth Login** (Google/GitHub als Alternative)
2. **Mini-Leagues / Gruppen** (private Tippgruppen mit Einladungs-Links)
3. **Telegram Bot** (Tipps per Telegram, Benachrichtigungen)
4. **Mobile App** (Capacitor Wrapper für iOS/Android)
5. **Erweiterte Statistik-Dashboard** (Heatmaps, Poisson-Analyse)
6. **Admin Activity Log** (Audit-Trail)
7. **Multi-Language (i18n)** (Deutsch/Englisch)
8. **Alembic/Flask-Migrate** für saubere Schema-Migrationen
9. **htmx** für dynamische UI-Updates ohne Vanilla JS
