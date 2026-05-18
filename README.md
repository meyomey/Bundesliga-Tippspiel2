# ⚽ Wulmstörper Tipprunde (Flask)

[![Tests](https://github.com/meyomey/Bundesliga-Tippspiel2/actions/workflows/tests.yml/badge.svg)](https://github.com/meyomey/Bundesliga-Tippspiel2/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
![Tests](https://img.shields.io/badge/Tests-39%2F39-green)
![Coverage](https://img.shields.io/badge/Coverage-41%25-yellow)

Ein vollständiges, produktionsreifes Bundesliga-Tippspiel mit Flask.

## ✨ Features

### Must-Have ✅
- ✅ Benutzerregistrierung & Login (mit Passwort-Reset per E-Mail)
- ✅ Profil mit Avatar-Upload (mit PIL-Resize)
- ✅ Vollständiger Spielplan (34 Spieltage) inkl. Vereins-Logos
- ✅ Automatische Ergebnisabfrage (football-data.org + OpenLigaDB Fallback)
- ✅ Manuelle Spiel-Eingabe als Notfall-Lösung
- ✅ Tippabgabe bis exakt zum Anstoß
- ✅ Joker-System (1× pro Spieltag, verdoppelt Punkte)
- ✅ Konfigurierbare Punkteberechnung (Exakt/Diff/Tendenz)
- ✅ Tages- & Gesamtwertung mit Gleichstandsregelung
- ✅ Admin-Bereich (Sync, Ergebnisse, Benutzer, Einstellungen)
-Admin-Bereich (Sync, Ergebnisse, Benutzer, Einstellungen)
- ✅ Rate-Limiting auf Login/API (Brute-Force-Schutz via Flask-Limiter)

### Nice-to-Have 🎁
- 🔔 Push-Benachrichtigungen (WebPushAPI · Service Worker bereit)
- ⚡ Schnelltipps (alle Spiele eines Spieltags auf einer Seite)
- 💬 Chat/Kommentare pro Spiel
- ⭐ Sondertipps (Datenmodell vorbereitet)
- 🏅 Badges & Gamification (auto-vergeben)
- 📊 Head-to-Head Vergleich
- 📈 Persönliche Statistik mit Formkurve (Chart.js)
- 📄 CSV- & PDF-Export
- 🌙 Dark Mode (toggle in Navbar)
- ⏰ Tipp-Deadline Countdown
- 📧 Automatische E-Mail-Reminder (1h vor Anpfiff via APScheduler)

### v2.0.0 🚀
- 🤖 KI-Tippgegner (5 Bots, Easy → Expert)
- ⚡ Live-Scoring (Server-Sent Events)
- 🏆 Multi-Wettbewerb (BL, CL, DFB-Pokal)
- 💨 Redis Caching (optional, gracefulfallback)
- 🐳 Docker Support
- 📱 PWA + WhatsApp-Integration
- 🏆 Preise & Pott-System, Ewige Tabelle, Spieltagsieger

### v3.0.0 🏗️ Architektur-Refactoring
- 📦 **app.py aufgeteilt** in 4 Blueprint-Module (routes_main, routes_auth, routes_admin, routes_api)
- 📦 **utils.py aufgeteilt** in 7 spezialisierte Module (scoring, badages, stats, sync, mail_helpers, avatars, export)
- 🔒 **Flask-Limiter** integriert (Login, Register, API geschützt)
- ⚡ **N+1 Queries** in get_leaderboard() optimiert (Bulk-Query + Eager Loading)

### v3.1.0 🐛 Bugfixes (2026-05-18)
- 🐛 **`datetime.utcnow()` deprecated** – auf `datetime.now(timezone.utc)` umgestellt
- 🐛 **SQLAlchemy `Query.get()` Legacy** – auf `db.session.get(Model, id)` migriert (13 Stellen)
- 📄 **Paginierung** – Admin-User-Liste (25/Seite) + Kommentare (10/Seite)
- 🔒 **Session-Validierung** – `competition_code` wird gegen DB geprüft
- 🎯 **Hardcoded Saison** – zentralisiert (leichter Saisonwechsel)
- 🤖 **GitHub Actions CI** – Tests auf 4 Python-Versionen

---

## 🚀 Schnellstart

```bash
# 1. Virtuelle Umgebung
python -m venv venv
source venv/bin/activate         # Windows: venv\\Scripts\\activate

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. (Optional) .env anlegen
cp .env.example .env

# 4. Starten
python app.py
```

App läuft unter: **[http://localhost:5000](http://localhost:5000/)**

**Standard-Admin:** `admin@tippspiel.de` / `admin123` → **sofort ändern!**

Beim ersten Start werden automatisch:
- 18 Bundesliga-Teams (mit Logos) angelegt
- 34 Spieltage mit Demo-Spielen erzeugt
- Default-Badges geseedet
- Admin-User erstellt

---

## ⚙️ Konfiguration

### football-data.org API Key (empfohlen)
1. Kostenlos registrieren: [https://www.football-data.org/client/register]()
2. Token in **Admin → Einstellungen** eintragen, **oder** als ENV: `FOOTBALL_DATA_TOKEN=...`
3. 10 Calls/Minute im Free Tier

### E-Mail (für Passwort-Reset & Reminder)
In `.env` setzen:
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=deine@gmail.com
MAIL_PASSWORD=dein-app-password
MAIL_DEFAULT_SENDER=deine@gmail.com
```

### VAPID Keys für Push-Benachrichtigungen
```bash
pip install pywebpush
vapid --gen
# Keys in Admin → Einstellungen eintragen
```

### Sicherheit
```bash
export SECRET_KEY="ein-sehr-langer-zufaelliger-string-min-32-zeichen"
```

---

## 📁 Projektstruktur

```
├── app.py                  # App-Factory + CLI Commands
├── config.py               # Konfiguration aus ENV/Defaults
├── extensions.py           # Flask-Extensions (DB, Login, Mail, Cache, CSRF, Limiter)
├── models.py               # SQLAlchemy-Modelle (14 Tabellen)
├── forms.py                # WTForms (12 Form-Klassen)
│
├── routes_main.py          # Hauptroutes (Dashboard, Spielplan, Profil, Export, …)
├── routes_auth.py          # Login, Register, Passwort-Reset
├── routes_admin.py         # Kompletter Admin-Bereich
├── routes_api.py           # JSON API-Endpunkte
│
├── scoring.py              # Punkteberechnung, Ranglisten, Pot, Spieltagsieger
├── badges.py               # Badge-System (Vergabe, Prüfung, Seeding)
├── stats.py                # Statistiken, Trend, Insights, Form, H2H, Wetter, Tabelle
├── sync.py                 # API-Sync (football-data.org + OpenLigaDB), Seeding, Schema-Migration
├── ai_opponent.py          # KI-Tippgegner (5 Bots)
├── cache.py                # Redis-Cache-Wrapper mit Fallback
├── export.py               # PDF/CSV-Export
├── avatars.py              # Avatar-Upload (PIL)
├── mail_helpers.py         # E-Mail, Token
├── live_scoring.py         # Live-Scoring (SSE)
├── push_routes.py          # Web Push
├── pwa_routes.py           # PWA-Routes
├── admin_bots_routes.py    # Bot-Verwaltung
└── whatsapp.py             # WhatsApp-Integration (CallMeBot)
```

---

## 🧪 Tests

```bash
pytest                                    # Alle Tests (39)
pytest -v --tb=short                      # Ausführlich
pytest --cov=. --cov-report=html          # Mit Coverage
pytest tests/test_models.py -v            # Nur Model-Tests
```

**Aktuell:** 39/39 Tests ✅ | Coverage: 41% | 2 Warnings (nur requests-Lib)

---

## 🐳 Docker

```bash
docker-compose up -d
```

Startet Flask-App + PostgreSQL + Redis + Scheduler.

---

## 🔧 Fix-Ordner

Der Ordner `Bundesliga-Tippspiel2-fix/` enthält eine bereinigte Version mit:
- Lazy-Init für AI Manager
- Bulk-Queries für Bot-Admin (N+1 gefixt)
- Optimierte Matchday-Queries
- Weitere Stabilitäts-Fixes

Diese Fixes sind in den main-Branch eingeflossen.

---

## 📄 Lizenz

MIT – machen damit, was ihr wollt.
