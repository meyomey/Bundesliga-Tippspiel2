# ⚽ Wulmstörper Tipprunde (Flask)

[![Tests](https://github.com/meyomey/Bundesliga-Tippspiel2/actions/workflows/tests.yml/badge.svg)](https://github.com/meyomey/Bundesliga-Tippspiel2/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue)
![Tests](https://img.shields.io/badge/Tests-285%2F285-green)
![Coverage](https://img.shields.io/badge/Coverage-79%25-yellowgreen)

Ein umfangreiches, produktionsnahes Bundesliga-Tippspiel mit Flask, Admin-Bereich, Live-Features, KI-Bots, PWA, Benachrichtigungen, Saisonarchiv und Netcup-/Shared-Hosting-Unterstützung.

---

## ✨ Aktueller Funktionsumfang

### Kernfunktionen
- ✅ Registrierung, Login, Logout
- ✅ Passwort-Reset per E-Mail
- ✅ Profil mit Avatar-Upload
- ✅ Lieblingsverein
- ✅ Spielplan und Matchdetails
- ✅ Tippabgabe bis exakt zum Anpfiff
- ✅ Joker-System pro Spieltag
- ✅ Schnelltipps pro Spieltag
- ✅ Konfigurierbare Punkteberechnung
- ✅ Gesamt- und Spieltagsrangliste
- ✅ Tippübersicht/Tippmatrix mit Sichtbarkeit ab Spielstart
- ✅ Live-Gesamtpunkte und Live-Spieltagespunkte in der Tippübersicht
- ✅ Sonderfragen
- ✅ Kommentare pro Spiel
- ✅ Badges/Gamification
- ✅ Preise & Pott-System
- ✅ Spieltagsieger
- ✅ Ewige Tabelle / Saisonarchiv
- ✅ PDF- und CSV-Export
- ✅ Zentrale Mehr-Seite (`/mehr`)
- ✅ Hilfe-/Regelseite (`/hilfe`, Alias `/regeln`)
- ✅ Vereinfachte mobile User-Navigation

### Live, Statistik & Gamification
- ⚡ Live-Scoring und Live-Leaderboard
- 📊 Statistik-Dashboard inkl. Stats 2.0 Fun-Facts
- 🔮 Spieltags-Preview mit Community-Trends
- 📊 Spieltags-Recap 2.0
- 👀 Tippmatrix mit Sortierung nach Gesamt live, Spieltag live oder Name
- 🤖 KI-Tippgegner/Bots
- 📈 Head-to-Head Vergleich
- ⚽ Lokale und externe Liga-Tabelle

### Benachrichtigungen & Integrationen
- 🔔 Benachrichtigungszentrale pro User
- 📧 E-Mail-Reminder
- 🔔 Web Push vorbereitet
- 🤖 Telegram Bot mit Tippabgabe, Joker, offenen Tipps und Statistik
- 💬 WhatsApp via CallMeBot
- 📱 PWA/Offline-Grundlagen

### Admin & Betrieb
- ⚙ Admin-Dashboard
- 🔄 API-Sync mit football-data.org + OpenLigaDB-Fallback
- 🧪 Sync-Diagnose mit letztem Sync-Ergebnis
- 🧰 Wartungscenter für Netcup/Shared Hosting
- 🧬 DB-/Schema-Wartung mit interner Migration-Versionierung
- 📜 Admin Activity Log
- 💾 SQLite Backup/Restore
- 📦 Komplett-Backup als ZIP inkl. Uploads/Logos
- 🏁 Saisonwechsel-Assistent 2.0
- 🖼 Lokale Vereinslogos über Wartungscenter
- 💨 Redis-Cache optional mit Fallback
- 🐳 Docker-Dateien vorhanden

---

## 🚀 Schnellstart lokal

```bash
python -m venv venv
source venv/bin/activate         # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

App läuft unter:

```txt
http://localhost:5000
```

Beim ersten Start werden automatisch angelegt:

- Teams
- Demo-Spielplan
- Default-Badges
- Default-Preise
- Admin-User

> Standard-Admin nur für Entwicklung: `admin@tippspiel.de` / `admin123` – in Produktion unbedingt ändern.

---

## 🔐 Sicherheit / Production

Für produktive Nutzung setzen:

```bash
SECRET_KEY=<langer-zufallswert>
ADMIN_PASSWORD=<sicheres-admin-passwort>
PUBLIC_BASE_URL=https://deine-domain.de
TELEGRAM_WEBHOOK_SECRET=<zufallswert>
```

Optionales Sicherheitsgate:

```bash
REQUIRE_SECURE_CONFIG=1
```

Dann startet die App nicht mehr mit Default-`SECRET_KEY` oder `admin123`.

---

## 🌐 Netcup / Plesk ohne SSH

Für Netcup mit Python 3.9.2:

```bat
build_vendor.bat
```

Dann Auswahl:

```txt
1 = Python 3.9.x
```

Das Skript baut `vendor/` mit Linux/manylinux-Wheels und schreibt zusätzlich:

```txt
vendor/vendor_manifest.txt
```

Hochladen per FTP:

```txt
*.py
templates/
static/
vendor/
requirements.txt
requirements_py39.txt
```

Danach in Plesk:

```txt
Python-App neu starten
```

Nicht versehentlich hochladen, wenn Serverdaten erhalten bleiben sollen:

```txt
tippspiel.db
```

---

## ⚙️ Wichtige Konfiguration

### football-data.org API-Key

1. Kostenlos registrieren: https://www.football-data.org/client/register
2. Token in **Admin → Einstellungen** oder als ENV setzen:

```bash
FOOTBALL_DATA_TOKEN=...
```

### Mail

```bash
MAIL_SERVER=smtp.example.de
MAIL_PORT=587
MAIL_USERNAME=...
MAIL_PASSWORD=...
MAIL_DEFAULT_SENDER=...
```

### Telegram

Admin → Einstellungen:

- Telegram Bot Token
- Telegram Bot Username
- Telegram Webhook Secret

Webhook-Beispiel:

```txt
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://DEINE-DOMAIN/telegram/webhook/<SECRET>
```

---

## 📁 Projektstruktur

```txt
app.py                    App-Factory, Bootstrap, CLI
config.py                 ENV/default-basierte Konfiguration
extensions.py             DB, Login, Mail, Cache, CSRF, Limiter
models.py                 SQLAlchemy-Modelle (18 Modelle)
forms.py                  WTForms (15 Form-/Validator-Klassen)

routes_main.py            Hauptseiten, Profil, Tipps, Stats, Telegram-Webhook
routes_auth.py            Login, Register, Passwort-Reset
routes_admin.py           Adminbereich, Saisonwechsel, Wartung, Schema, Backup
routes_api.py             JSON-APIs
main_*_routes.py          ausgelagerte User-Routen (Tipps, Profil, Stats, Export, PWA, Telegram)
admin_*_routes.py         ausgelagerte Admin-Routen (User, Preise, Schema, Wartung, Export, Bots usw.)

scoring.py                Punkte, Ranglisten, Live-Ranglisten, Pott
stats.py                  Statistiken, Tabelle, H2H, Preview/Recap
sync.py                   API-Sync, OpenLigaDB, Seeding, Auto-Migration
cache.py                  Redis-Cache-Wrapper + Key-/Invalidierungslogik
ai_opponent.py            KI-Bots
notification_center.py    E-Mail/Push/Telegram/WhatsApp Reminder-Zentrale
schema_migrations.py      interne Migration-Versionierung
maintenance.py            Wartungscenter-Funktionen, lokale Logos
cache_monitor_routes.py   Cache-Monitoring
admin_bots_routes.py      Bot-Adminlogik
audit_log.py              Admin Activity Log Helper
export.py                 PDF-Export
avatars.py                Avatar-Verarbeitung
mail_helpers.py           Mail, Tokens, VAPID-Settings
live_scoring.py           Live-Scoring/SSE
push_routes.py            Web Push
pwa_routes.py             PWA/Offline
telegram_bot.py           Telegram Bot
whatsapp.py               CallMeBot WhatsApp
```

---

## 🧪 Tests

```bash
pytest
pytest -q
pytest --cov=. --cov-report=html
```

Aktueller Stand lokal:

```txt
285/285 Tests bestanden
Coverage: 79 %
3 Warnings (LegacyAPIWarning für Query.get() in zwei Tests, harmlos)
```

Testbereiche:

- Models
- Routes
- Cache
- KI-Bots
- Tippübersicht
- Telegram Bot
- Notifications
- Security
- Saisonwechsel-Assistent
- Admin Activity Log
- Wartungscenter
- Schema-Migrationen
- Sync/Backup/Export
- Stats/Scoring
- Avatar/Live/Push
- Mail/WhatsApp/PWA

---

## 🐳 Docker

```bash
docker-compose up -d
```

Startet Flask-App, PostgreSQL, Redis und optional Scheduler.

---

## 📄 Lizenz

MIT
