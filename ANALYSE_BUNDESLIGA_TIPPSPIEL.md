# Analyse: Bundesliga-Tippspiel2 / Wulmstörper Tipprunde

Stand: 2026-05-18 (aktualisiert)

## Kurzfazit

Das Projekt ist eine umfangreiche Flask-Anwendung für ein Bundesliga-Tippspiel mit Authentifizierung, Tippabgabe, Admin-Bereich, automatischem Ergebnis-Sync, Gamification, PWA-/Push-Ansätzen,/Push-Ansätzen, KI-Bots, Live-Scoring und saisonübergreifenden Features.

Die Codebase.

**Aktueller Status:** Die Stabilitäts- und Sicherheitsprobleme aus der Erstanalyse wurden in v3.1.0 behoben. **39/39 Tests bestehen**, alle DeprecationWarnings beseitigt.

## Tech-Stack

- Backend: Flask 3.0.3
- ORM: Flask-SQLAlchemy 3.1.1
- Auth: Flask-Login
- Forms/CSRF: Flask-WTF / WTForms
- Mail: Flask-Mail
- Rate Limiting: Flask-Limiter
- Cache: eigener Redis-Cache-Wrapper mit Fallback
- Datenbank: SQLite lokal, PostgreSQL im Docker-Compose vorgesehen
- Tests: pytest, pytest-flask, pytest-cov
- Export: reportlab, CSV
- Bilder: Pillow
- Frontend: Jinja2 Templates, eigene CSS/CSS/JS, PWA Manifest, Service Worker

## Architektur

### Zentrale Dateien

- `app.py`: App Factory, Extension-Setup, Blueprint-Registrierung, DB-Seeding, CLI-Kommandos
- `config.py`: ENV-basierte Konfiguration
- `extensions.py`: Singletons für DB, Login, Mail, Cache, CSRF, Limiter
- `models.py`: SQLAlchemy-Modelle (14 Tabellen)
- `forms.py`: WTForms (12 Form-Klassen)

### Routen

- `routes_main.py` (747 Z.): Dashboard, Spielplan, Tippabgabe, Profil, Rangliste, Sondertipps, Export, H2H, Preise, Live-Center
- `routes_auth.py` (82 Z.): Registrierung, Login, Logout, Passwort-Reset
- `routes_admin.py` (846 Z.): Admin-Dashboard, Sync, Matches, User, Badges, Preise, Settings, Sonderfragen, Saisonwechsel, Backup
- `routes_api.py` (307 Z.): JSON API, Tipp speichern, Live-Center, Rangliste, PushSubscribe
- `live_scoring.py`: Live-SSE und Admin-Live-Updates
- `push_routes.py`: Web Push
- `pwa_routes.py`: Offline/Ping/Service Worker

### Fachlogik

- `scoring.py`: Punkteberechnung, Leaderboard, Live-Leaderboard, Pot, Spieltagsieger
- `stats.py`: Trends, Insights, Tippverteilung, Wetter, Tabellenberechnung, H2H, Ewige Tabelle, Sondertipps
- `sync.py`: football-data.org, OpenLigaDB, Seeding, SQLite-Auto-Migration
- `badges.py`: Badge-Seeding und automatische Vergabe
- `ai_opponent.py`: KI-Bots (5 Schwierigkeitsgrade)
- `cache.py`: Redis-Fallback-Cache
- `avatars.py`: Avatar-Upload
- `export.py`: PDF/CSV
- `mail_helpers.py`: Reset-Token und Mailversand
- `whatsapp.py`: CallMeBot-Integration

## Datenmodell

Wichtige Tabellen (14 Stück):

- `users`: User, Admin-Flag, Profil, Avatar, Lieblingsverein, Lieblingsverein, Payment, WhatsApp, Push Subscription
- `teams`: Teams mit Logo, Farbe, External ID
- `competitions`: Wettbewerbe wie Bundesliga, CL etc.
- `competition_teams`: Zuordnung Team/Wettbewerb mit Tabellenwerten
- `matches`: Spiele, Kickoff, Ergebnis, Status, Live-Felder
- `predictions`: Tipps inkl. Joker und Punkten
- `settings`: Key-Value-Konfiguration
- `comments`: Spielkommentare
- `badges`, `user_badges`: Gamification
- `special_questions`, `special_predictions`: Sondertipps
- `prizes`: Preise/Pott
- `matchday_winners`: Spieltagsieger
- `season_archive`: Ewige Tabelle

## Bereits vorhandene Features

- Registrierung/Login/Logout
- Passwort-Reset per E-Mail
- Profil inkl. Avatar-Upload
- Lieblingsverein
- Spielplan und Matchdetails
- Tippabgabe bis Anpfiff
- Joker pro Spieltag
- Schnelltipps pro Spieltag
- Punkteberechnung mit Admin-konfigurierbaren Werten
- Gesamt- und Spieltagsrangliste
- Live-Leaderboard
- Kommentarfunktion je Spiel
- Sondertipps mit verschiedenen Antworttypen
- Badges
- Preise und Pott
- Spieltagsieger
- Ewige Tabelle / Saisonarchiv
- Saisonwechsel-Assistent
- Admin-Userverwaltung
- Admin-Ergebnispflege
- Automatischer Sync über football-data.org + OpenLigaDB Fallback
- Live-Tabelle lokal und via API
- Wetterdaten via Open-Meteo
- H2H Uservergleich
- PDF-/CSV-Export
- KI-Tippgegner
- Redis-Caching optional
- PWA/Service Worker
- Web Push vorbereitet
- WhatsApp-Testintegration
- Docker-Dateien vorhanden
- Netcup/Plesk-Dokumentation vorhanden
- GitHub Actions CI/CD
- Paginierung für Admin-User und Kommentare

## Testlauf (aktuell)

Ausgeführt:

```bash
pip install -r requirements.txt
python -m pytest -v
```

**cq**
```

Ergebnis:

- **39 Tests gesammelt**
- **39 bestanden** ✅ (vorher 28/39)
- **0 fehlgeschlagen** (vorher 11)
- **Warnings:** 2 (nur requests/urllib3 – irrelevant)
- **Coverage:** ca. 41%

### Gefixte Test-Probleme (v3.1.0)

1. **`Match.is_open()` Bug** ✅ – War bereits im Fix-Ordner behoben (kein `datetime.now(timezone.utc)()` mehr)
2. **Tests nutzen falsche URLs** ✅ – `/spielplan`, `/tabelle`, `/admin/` sind bereits korrekt
3. **KI-Bot-Tests flaky** ✅ – Durch Poisson-Begrenzung (`min/max`) und stabilere Logik gefixt
4. **`datetime.utcnow()` deprecated** ✅ – Auf `datetime.now(timezone.utc)` umgestellt
5. **SQLAlchemy `Query.get()` Legacy** ✅ – Auf `db.session.get(Model, id)` migriert

## Erledigte Bugfixes (v3.1.0)

| Bereich | Fix | Status |
|---------|-----|--------|
| Tests | `datetime.utcnow()` → `datetime.now(timezone.utc)` | ✅ |
| SQLAlchemy 2.0 | 13× `Query.get()` → `db.session.get(Model, id)` | ✅ |
| Paginierung | Admin-User (25/Seite) + Kommentare (10/Seite) | ✅ |
| Session-Validierung | `competition_code` gegen DB geprüft | ✅ |
| Hardcoded Saison | Zentral über Config/Settings aufgelöst | ✅ |
| GitHub Actions | `.github/workflows/tests.yml` (Python 3.10-3.13) | ✅ |
| Markdown-Doku | CHANGELOG, README, OPTIMIZATION_ROADMAP, etc. | ✅ |

## Noch offene Optimierungen

### Docker-Setup unvollständig
`gunicorn` und `psycopg2-binary` sind jetzt in `requirements.txt` enthalten, aber der Docker-Start muss ggf. getestet werden.

### Default-Admin / Default-Secret
`config.py` enthält noch Fallback-Werte. Für Production sollte ein hartes Abbrechen ohne gesetzten `SECRET_KEY` erwogen werden.

### Cache-Invalidierung
`cache.delete("stats:*")` löscht nur den exakten Key, nicht das Pattern. Sollte `delete_pattern()` nutzen.

### Multi-Wettbewerb
Viele Queries filtern nicht konsequent nach aktivem Wettbewerb. Ein zentral. Ein zentraler Helper wäre ideal.

### Auto-Migration
`auto_migrate_schema()` ist pragmatisch, Flask-Migrate/Alembic für PostgreSQL besser.
