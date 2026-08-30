# Analyse: Bundesliga-Tippspiel2 / Wulmstörper Tipprunde

Stand: 2026-07-05

## Kurzfazit

Das Projekt ist inzwischen eine umfangreiche Flask-Anwendung fuer ein Bundesliga-Tippspiel mit Authentifizierung, Tipps, Adminbereich, API-Sync, Bots, Live-Funktionen, Tippmatrix, Benachrichtigungen, Saisonarchiv, Activity Log, Wartungscenter, Schema-Migrationen, User-Orientierung mit Mehr-/Hilfe-Seite und Netcup-/Shared-Hosting-Unterstuetzung.

Aktueller lokaler Teststand:

```txt
134/134 Tests bestanden
Coverage ca. 65%
1 Warning (reportlab DeprecationWarning, harmlos)
```

---

## Tech-Stack

- Backend: Flask 3.0.3
- ORM: Flask-SQLAlchemy / SQLAlchemy 2
- Auth: Flask-Login
- Forms/CSRF: Flask-WTF / WTForms
- Mail: Flask-Mail
- Rate Limiting: Flask-Limiter
- Cache: eigener Redis-Wrapper mit Fallback
- Datenbank: SQLite lokal/Netcup, PostgreSQL optional via Docker
- Tests: pytest, pytest-flask, pytest-cov
- Export: reportlab, CSV
- Bilder: Pillow
- Frontend: Jinja2, eigene CSS/JS, PWA Manifest, Service Worker

---

## Architektur

### Einstieg

- `app.py`: App-Factory, Extension-Setup, Blueprint-Registrierung, Bootstrap, CLI
- `config.py`: ENV/default-basierte Konfiguration mit Production-Sicherheitsgate
- `extensions.py`: DB, Login, Mail, Cache, CSRF, Limiter
- `models.py`: SQLAlchemy-Modelle, aktuell 18 Modelle
- `forms.py`: WTForms, aktuell 15 Form-/Validator-Klassen

### Routen

- `routes_main.py`: Dashboard, Spielplan, Tipps, Tippübersicht, Profil, Stats, Preview/Recap, Telegram Webhook, Export
- `routes_auth.py`: Login, Register, Logout, Passwort-Reset
- `routes_admin.py`: Admin-Dashboard, Sync, Ergebnisse, User, Badges, Preise, Wartung, Schema, Saisonwechsel, Backup
- `routes_api.py`: JSON-APIs fuer Tipps, Live, Tippübersicht, Leaderboard
- `live_scoring.py`: Live-Scoring/SSE
- `push_routes.py`: Web Push
- `pwa_routes.py`: PWA/Offline

### Fachlogik

- `scoring.py`: Punkte, Leaderboard, Live-Leaderboard, Pott, Spieltagsieger
- `stats.py`: Trends, Insights, Liga-Tabelle, H2H, Preview, Recap, Stats 2.0
- `sync.py`: football-data.org, OpenLigaDB, Seeding, Auto-Migration, Sync-Diagnose
- `cache.py`: Redis-Fallback, versionierte Keys, SCAN-Invalidierung
- `notification_center.py`: E-Mail/Push/Telegram/WhatsApp Reminder
- `schema_migrations.py`: interne Migration-Versionierung fuer Hosting ohne SSH
- `maintenance.py`: Wartungscenter, lokale Logos, Health Checks
- `audit_log.py`: Admin Activity Log
- `ai_opponent.py`: KI-Bots
- `badges.py`: Badge-System
- `export.py`: PDF-Export
- `avatars.py`: Avatar-Upload
- `mail_helpers.py`: Mail, Token, VAPID
- `telegram_bot.py`: Telegram Bot
- `whatsapp.py`: CallMeBot WhatsApp

---

## Datenmodell

Wichtige Modelle:

- User, Team, Competition, CompetitionTeam
- Match, Prediction
- Setting
- Comment
- Badge, UserBadge
- SpecialQuestion, SpecialPrediction
- Prize
- MatchdayWinner
- SeasonArchive
- NotificationLog
- AdminActivityLog
- SchemaMigration

---

## Implementierte Kernfeatures

- Registrierung/Login/Logout
- Passwort-Reset
- Profil, Avatar, Lieblingsverein
- Spielplan, Matchdetails, Kommentare
- Tippabgabe bis Anpfiff
- Joker pro Spieltag
- Schnelltipp
- Gesamt-/Spieltagsrangliste
- Tippmatrix mit Sichtbarkeit ab Spielstart
- Live-Punkte in der Tippmatrix
- Sonderfragen
- Badges
- Preise/Pott
- Spieltagsieger
- Ewige Tabelle
- CSV/PDF-Export
- KI-Bots
- Live-Scoring
- Liga-Tabelle
- Statistik-Dashboard/Stats 2.0
- Spieltags-Preview und Recap 2.0
- Benachrichtigungszentrale
- Telegram Bot
- WhatsApp/Push-Grundlagen
- PWA

---

## Admin- und Betriebsfeatures

- Sync-Diagnose und letzter Sync-Status
- football-data.org + OpenLigaDB-Fallback
- Admin Activity Log
- Wartungscenter
- lokale Vereinslogos
- DB-/Schema-Wartung mit internen Migrationen
- Backup/Restore
- Komplett-Backup als ZIP
- Saisonwechsel-Assistent 2.0
- Cache-Monitoring
- Bot-Verwaltung
- Netcup/vendor-Unterstuetzung

---

## Sicherheit

Erledigt:

- CSRF global aktiv
- Login/API Rate-Limiting
- Kommentar-Sanitizing mit Bleach
- Query.get Legacy entfernt
- Production-Sicherheitsgate fuer SECRET_KEY/Admin-Passwort
- Telegram Webhook Secret
- sensible Admin-Settings werden nicht vorausgefüllt
- Pott-Berechnung ohne Bots

Noch sinnvoll:

- Langfristig sensible Settings verschlüsseln oder konsequent in ENV halten
- Noch mehr JS-HTML-Injection-Stellen auf `textContent`/Escaping umbauen

---

## Performance

Erledigt:

- `get_leaderboard()` Bulk-Query
- `get_live_leaderboard()` Bulk-Query
- Tippübersicht-Livepunkte per JSON statt Full Reload
- Redis `SCAN` statt `KEYS`
- versionierte Cache-Keys

Noch sinnvoll:

- Notification Center weiter bulk-optimieren
- Sync-Mapping/API mit gezielten Mocks weiter absichern
- Sehr große Adminlisten ggf. weiter paginieren

---

## Tests

Aktuell:

```txt
134 Tests
134 bestanden
1 Warning (reportlab DeprecationWarning, harmlos)
Coverage ca. 65%
```

Neuere Testbereiche:

- Tippübersicht
- Telegram Bot
- Notifications
- Security
- Saisonwechsel
- Admin Activity Log
- Wartungscenter
- Schema-Migrationen
- Sync/Backup/Export
- Preview/Recap
- Stats/Scoring
- Avatar/Live/Push
- Mail/WhatsApp/PWA

---

## Wichtigste verbleibende technische Schulden

1. `routes_main.py` und `routes_admin.py` sind sehr groß und sollten langfristig weiter aufgeteilt werden.
2. `sync.py` ist komplex und sollte noch mehr API-Mock-Tests bekommen.
3. `export.py` hat weiterhin niedrige Coverage.
4. Auto-Migration + interne SchemaMigration ist Netcup-tauglich, ersetzt Alembic aber nicht vollstaendig.
5. Inline-JS/CSS in Templates koennte schrittweise ausgelagert werden.

---

## Empfehlung

Die App ist jetzt feature-reich und betriebsnah. Weitere Arbeit sollte sich vor allem auf Stabilitaet, Sync-Robustheit, Export-Qualitaet und Code-Aufteilung konzentrieren statt auf immer neue Features.
