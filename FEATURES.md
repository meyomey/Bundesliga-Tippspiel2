# 🚀 Features – Wulmstörper Tipprunde

Stand: 2026-07-05

Diese Datei beschreibt den aktuellen Stand der Codebase nach den letzten Stabilitäts-, Netcup-, Performance-, Security- und UI-Paketen.

---

## Architektur

```txt
app.py
  ├── routes_main.py       Hauptseiten, Tipps, Profil, Stats, Telegram Webhook
  ├── routes_auth.py       Auth/Login/Reset
  ├── routes_admin.py      Admin, Sync, Saisonwechsel, Wartung, Schema, Backup
  ├── routes_api.py        JSON-APIs
  ├── main_*_routes.py     ausgelagerte User-Routen
  ├── admin_*_routes.py    ausgelagerte Admin-Routen
  ├── live_scoring.py      Live-Scoring/SSE
  ├── push_routes.py       Web Push
  └── pwa_routes.py        PWA/Offline

Fachlogik
  ├── scoring.py           Punkte, Ranglisten, Live-Ranglisten, Pott
  ├── stats.py             Statistiken, Tabelle, H2H, Preview, Recap
  ├── sync.py              football-data/OpenLigaDB, Seeding, Auto-Migration
  ├── cache.py             Redis-Fallback, SCAN-Invalidierung, Cache-Keys
  ├── badges.py            Badge-System
  ├── ai_opponent.py       KI-Bots
  ├── notification_center.py E-Mail/Push/Telegram/WhatsApp Reminder
  ├── schema_migrations.py interne Migration-Versionierung
  ├── maintenance.py       Wartungscenter, lokale Logos, Health Checks
  ├── audit_log.py         Admin Activity Log
  └── export.py            PDF-Export
```

---

## Datenmodell

Aktuell wichtige Modelle:

- `Competition`
- `User`
- `CompetitionTeam`
- `Team`
- `Match`
- `Prediction`
- `Setting`
- `Comment`
- `Badge`
- `UserBadge`
- `SpecialQuestion`
- `SpecialPrediction`
- `Prize`
- `MatchdayWinner`
- `SeasonArchive`
- `NotificationLog`
- `AdminActivityLog`
- `SchemaMigration`

---

## Kernfeatures

- Registrierung/Login/Logout
- Passwort-Reset per E-Mail
- Profil, Avatar, Lieblingsverein
- Spielplan, Matchdetails, Kommentare
- Tippabgabe bis Anpfiff
- Joker pro Spieltag
- Schnelltipp
- Gesamt-/Spieltagsrangliste
- Tippübersicht/Tippmatrix mit Sichtbarkeit ab Spielstart
- Live-Punkte in Tippübersicht
- Sonderfragen
- Badges
- Preise und Pott
- Ewige Tabelle/Saisonarchiv
- CSV/PDF-Export
- Mehr-Seite als zentrale User-Übersicht
- Hilfe-/Regelseite mit Punkte-, Joker- und Sichtbarkeitsregeln
- Vereinfachte mobile Navigation und klarere User-Texte

---

## Live & Statistik

- Live-Scoring
- Live-Leaderboard mit Bulk-Query-Optimierung
- Liga-Tabelle lokal oder per API
- Statistik-Dashboard
- Stats 2.0 Fun-Facts
- H2H-Vergleich
- Spieltags-Preview mit Community-Trends
- Spieltags-Recap 2.0
- Spieltagsieger-Chronik

---

## Bots & Gamification

- 5 KI-Bots
- Bot-Verwaltung im Adminbereich
- Bots aktivieren/deaktivieren
- Bots pro Spieltag tippen lassen
- Bot-Tipps überschreiben
- Badges automatisch/manuell

---

## Benachrichtigungen

- Benachrichtigungszentrale pro User
- E-Mail
- Web Push vorbereitet
- Telegram Bot
- WhatsApp via CallMeBot
- NotificationLog gegen doppelte Reminder

Telegram-Kommandos u. a.:

```txt
/start TOKEN
/tipp FCB-BVB 2:1
/tipp FCB-BVB 2:1 joker
/joker FCB-BVB
/offen
/stats
/rangliste
/meine_tipps
/spielplan
```

---

## Admin & Betrieb

- Sync-Diagnose
- football-data.org + OpenLigaDB-Fallback
- Backup/Restore
- Komplett-Backup als ZIP
- Wartungscenter
- lokale Vereinslogos
- DB-/Schema-Wartung
- interne Migration-Versionierung
- Admin Activity Log
- Saisonwechsel-Assistent 2.0
- Cache-Monitoring
- Netcup/vendor-Unterstützung

---

## Caching

- Optionaler Redis-Cache
- Graceful Fallback ohne Redis
- SCAN statt KEYS für Pattern-Invalidierung
- Versionierte Cache-Keys (`v2:*`)
- Invalidierung für Leaderboard/Stats/Matches/Competition

---

## Sicherheit

- CSRF global aktiv
- Login/Register/API rate-limited
- Kommentare mit Bleach bereinigt
- Production-Sicherheitsgate über `REQUIRE_SECURE_CONFIG=1` oder `APP_ENV=production`
- Telegram Webhook Secret unterstützt
- sensible Settings werden nicht mehr im Adminformular vorausgefüllt

---

## Tests

Aktueller Stand lokal:

```txt
134/134 Tests bestanden
Coverage ca. 65%
1 Warning (reportlab DeprecationWarning, harmlos)
```

Testbereiche:

- Models
- Routes
- Cache/Cache-Monitor
- KI-Bots
- Tippübersicht
- Telegram Bot
- Notifications
- Security
- Saisonwechsel
- Admin Activity
- Wartungscenter
- Schema-Migrationen
- Sync/Backup/Export
- Stats/Scoring
- Avatar/Live/Push
- Mail/WhatsApp/PWA

---

## Sinnvolle naechste Schritte

- Sync/API noch tiefer mit API-Mocks testen
- Export/PDF weiter verbessern
- `routes_main.py` und `routes_admin.py` langfristig weiter aufteilen
- Optional: mehr Admin-Routen testen
- Optional: lokale Logos direkt als feste Assets ins Repo legen
