# Changelog – Wulmstörper Tipprunde

























## [3.1.24] - 2026-05-18

### 🧪 Coverage-Ausbau Richtung 55%

- Neue Tests fuer Statistik-/Scoring-Helfer: Live-Leaderboard, Live-User-Stats, Tabellenberechnung, Teamform, H2H, Tippverteilung, Preview/Recap-Helfer.
- Neue Tests fuer Avatar-Upload, LiveMatchManager und Push-Reminder.
- Neue Tests fuer Cache-Monitor-Routes.
- Neue Tests fuer Mail-Helper, WhatsApp-Helper und PWA-Routes.
- Coverage lokal auf ca. **55%** erhoeht.

### ✅ Verifikation

- `python -m pytest -q`: **80/80 Tests bestanden**, keine Warnings.

---

## [3.1.23] - 2026-05-18

### 🔮 Spieltags-Preview + Recap 2.0

- Neue Seite `/preview` bzw. `/preview/<spieltag>` fuer Spieltagsvorschau.
- Neue Seite `/spieltag-recap` bzw. `/spieltag-recap/<spieltag>` fuer Spieltagsrueckblick.
- Preview zeigt Tippquote, abgegebene Tipps, Top-Spiel, Community-Tendenzen, haeufigsten Tipp, Joker-Anzahl und offene Tipper.
- Recap zeigt Spieltagsieger, Siegerpunkte, besten Einzeltipp, besten Joker, Ergebnisse und Spieltagswertung.
- Navigation in Hauptmenue und Spielplan ergaenzt.
- Tests fuer Preview und Recap ergaenzt.

### ✅ Verifikation

- `python -m pytest -q`: **65/65 Tests bestanden**, keine Warnings.
- Coverage lokal: ca. **48%**.

---

## [3.1.22] - 2026-05-18

### 🚀 Deployment-/Netcup-Paket

- Wartungscenter um Netcup/Deployment-Check erweitert: Python-Version, vendor-Ordner, Schreibrechte, SQLite-Pfad, wichtige Pakete.
- Sicherheits-/Konfigurationsstatus im Wartungscenter: SECRET_KEY, Admin-Passwort, PUBLIC_BASE_URL, Telegram Secret.
- `build_vendor.bat` schreibt nun ein `vendor/vendor_manifest.txt` mit Ziel-Python, ABI, Requirements-Datei und Zeitstempel.
- Wartungscenter zeigt Paketstatus fuer Flask, SQLAlchemy, Pillow, ReportLab, Requests, Redis und Flask-Limiter.
- Deployment-Health-Check in `maintenance.py` erweitert.

### ✅ Verifikation

- `python -m pytest -q`: **63/63 Tests bestanden**, keine Warnings.
- Coverage lokal: ca. **48%**.

---

## [3.1.21] - 2026-05-18

### 📱 UI-/Mobile-Polishing

- Mobile Abstaende, Schriftgroessen, Cards und Header-Actions verdichtet.
- Mobile Formulare, Buttons, Selects und Checkbox-Zeilen vereinheitlicht.
- Admin-Dashboard und Admin-Kacheln auf Smartphones kompakter dargestellt.
- Reminder-Banner und Toasts fuer Bottom-Tabbar/Safe-Area angepasst.
- Mobile Tabellen/Scrollbereiche leicht optimiert.
- Light/Dark-Kompatibilitaet der bestehenden Komponenten bleibt erhalten.

### ✅ Verifikation

- `python -m pytest -q`: **63/63 Tests bestanden**, keine Warnings.

---

## [3.1.20] - 2026-05-18

### 🧰 Lokale Vereinslogos & Wartungscenter

- Neues `maintenance.py` mit Wartungsfunktionen fuer Netcup/Shared-Hosting-Betrieb.
- Admin-Wartungscenter `/admin/maintenance` ergaenzt.
- Teamlogos koennen lokal nach `static/team_logos/` gespiegelt werden; DB wird auf lokale `/static/team_logos/...` Pfade gesetzt.
- Fallback-SVG wird erzeugt, wenn ein Logo-Download fehlschlaegt.
- Wartungsaktionen: Logos lokalisieren/neu laden, Punkte neu berechnen, Spieltagsieger neu berechnen, Badges neu pruefen, Sondertipps auswerten.
- Wartungscenter im Admin-Dashboard verlinkt und Activity-Log integriert.
- Tests fuer Wartungsfunktionen ergaenzt.

### ✅ Verifikation

- `python -m pytest -q`: **63/63 Tests bestanden**, keine Warnings.
- Coverage lokal: ca. **47%**.

---

## [3.1.19] - 2026-05-18

### 📜 Admin Activity Log

- Neues Modell `AdminActivityLog` fuer Audit-Trail wichtiger Admin-Aktionen.
- Neuer Helper `audit_log.py` mit `log_admin_action(...)`.
- Neue Admin-Seite `/admin/activity` mit Filter nach Aktion und Freitextsuche.
- Admin-Dashboard um Kachel `Activity Log` erweitert.
- Erste wichtige Aktionen werden geloggt: Sync, Demo-Daten, alle Spiele loeschen, Backup-Restore, Ergebnis-Update, User-Update/Delete/Admin/Paid, Bot-Aktionen, Cache-Flush, Saisonwechsel, Settings.
- Tests fuer Activity Log ergaenzt.

### ✅ Verifikation

- `python -m pytest -q`: **60/60 Tests bestanden**, keine Warnings.
- Coverage lokal: ca. **47%**.

---

## [3.1.18] - 2026-05-18

### 🧹 Cache-Refactor

- Redis Pattern-Invalidierung von blockierendem `KEYS` auf `SCAN`/`scan_iter` umgestellt.
- Cache-Loeschungen laufen jetzt in Batches (`delete_many`).
- Cache-Monitoring nutzt ebenfalls `scan_iter` und loescht Pattern in Batches.
- Versionierte Cache-Key-Helfer eingefuehrt (`v2:*`) fuer Leaderboards, User-Stats, Matchdetails und Live-Matches.
- Leaderboard-Cache nutzt jetzt zentralen Key-Helper mit Saison und Wettbewerb.
- Breitere Domain-Invalidierung fuer Leaderboard/Stats/Live-Matches/Competition ergaenzt.
- Cache-Fehler werden debug-geloggt statt still komplett verschluckt.

### ✅ Verifikation

- `python -m pytest -q`: **57/57 Tests bestanden**, keine Warnings.

---

## [3.1.17] - 2026-05-18

### 🧪 Test- & Stabilitaetspaket

- Neue Tests fuer Tippuebersicht inkl. Sichtbarkeit vor/nach Anpfiff und Live-API.
- Neue Tests fuer Telegram Bot: Account-Link, Tipp mit Joker, offene Tipps, Statistik.
- Neue Tests fuer Benachrichtigungszentrale: Tipp vorhanden, Lieblingsverein-Filter, Kanal deaktiviert, NotificationLog-Dedupe.
- Neue Security-Tests: Production-Sicherheitsgate und Telegram-Webhook-Secret.
- Neue Tests fuer Saisonwechsel-Assistent: Zugriff, Bestaetigungszwang, Saison-Update.
- Telegram-Webhook-Fehlerbehandlung korrigiert, damit `abort(403)` nicht versehentlich als 200 geschluckt wird.

### ✅ Verifikation

- `python -m pytest -q`: **57/57 Tests bestanden**, keine Warnings.
- Coverage lokal: ca. **46%**.

---

## [3.1.16] - 2026-05-18

### ⚡ Performance-Paket: Live-Leaderboard & Tippübersicht

- `get_live_leaderboard()` von N+1-Queries auf Bulk-Query umgestellt.
- Live-Punkte werden jetzt fuer alle User in einem Durchlauf berechnet.
- Sonderpunkte werden gesammelt per GROUP BY geladen.
- Tippübersicht bekommt einen schlanken JSON-Endpunkt fuer Live-Punkte: `/api/tip-overview/live/<matchday>`.
- Tippübersicht aktualisiert waehrend Live-Spielen nur noch Punkte/Sortierung per Fetch statt komplettem Page-Reload.
- Sonderpunkte im normalen Leaderboard werden jetzt ebenfalls competition-spezifisch gefiltert.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.15] - 2026-05-18

### 🔐 Kritisches Sicherheitspaket

- Production-Sicherheitsgate ergaenzt: mit `REQUIRE_SECURE_CONFIG=1` oder `APP_ENV=production` startet die App nicht mehr mit Default-`SECRET_KEY` oder `admin123`.
- Telegram Webhook kann jetzt per Secret abgesichert werden: `/telegram/webhook/<secret>` oder Header `X-Telegram-Bot-Api-Secret-Token`.
- Admin-Einstellungen fuellen sensible Felder nicht mehr mit gespeicherten Klartextwerten vor (API-Token, SMTP-Passwort, VAPID Private Key, Telegram Token, Webhook Secret).
- `PUBLIC_BASE_URL` als Setting/ENV ergaenzt und fuer Reminder-Links verwendet.
- Pott-Berechnung schliesst Bot-User aus.
- Alter `tippspiel.example.com`-Reminder-Link entfernt.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.14] - 2026-05-18

### 🧭 Saisonwechsel-Assistent 2.0

- Admin-Seite `/admin/new-season` komplett als gefuehrter Saisonwechsel-Assistent ueberarbeitet.
- Checkliste fuer Backup, abgeschlossene Spiele, offene Sondertipps und vorhandenes Archiv ergaenzt.
- Kennzahlen vor dem Wechsel: Spiele, Tipps, Kommentare, Bezahlstatus.
- Sicherere Bestaetigung per Text `SAISON STARTEN`.
- Archivierung nutzt jetzt `archive_season()` statt manueller Teilarchivierung.
- Saisonwechsel arbeitet wettbewerbsbezogen und gibt klare Folge-Schritte aus.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.13] - 2026-05-18

### 🖼️ HSV/St. Pauli Logo-Fix

- Nur die Logo-URLs fuer `HSV` und `FC St. Pauli` korrigiert.
- Quelle: OpenLigaDB-referenzierte Wikimedia-SVGs.
- Andere Vereinslogos bleiben unveraendert.
- Bestehende Datenbanken werden beim App-Start automatisch fuer diese zwei Teams aktualisiert.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.12] - 2026-05-18

### ↕️ Sortierung Tippübersicht

- Tippübersicht kann jetzt direkt nach `Gesamt live`, `Spieltag live` oder `Name` sortiert werden.
- Sortierung ist ueber Dropdown und ueber klickbare Punkte-Spalten auswählbar.
- Aktive Sortierung wird in der Kopfzeile markiert.
- Spieltagswechsel behält die gewählte Sortierung bei.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.11] - 2026-05-18

### 🎨 Rang-Darstellung

- Raute (`#`) vor Rangzahlen in Rangliste, Dashboard, Tippübersicht, Ewiger Tabelle, Recap und Preisübersicht entfernt.
- In der Tippübersicht wird der Rang jetzt als `Rang 2` statt `#2` angezeigt.
- Tabellenpositionen bei Teams werden ohne Raute bzw. mit Punkt dargestellt.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.10] - 2026-05-18

### 📱 Mobile Navigation Fix

- Bottom-Tabbar wird ausgeblendet, sobald das Hamburger-Menü geöffnet ist.
- Mobiler Drawer liegt jetzt über der Sockelleiste und hat zusätzliches Bottom-Padding.
- Verhindert, dass die unteren Menüpunkte im Hamburger-Menü abgeschnitten werden.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.9] - 2026-05-18

### 🤖 KI-Bot Admin-Fix

- `AIManager.tip_all_matches()` akzeptiert jetzt `overwrite`.
- Admin-Button "Alle Bots tippen lassen" funktioniert wieder mit und ohne Überschreiben.
- Admin-Auswertung nutzt jetzt eine Summary pro Bot: neue Tipps, überschriebene Tipps, übersprungene Tipps.
- Leaderboard-Cache wird nach Bot-Tipps invalidiert.
- Fallback fuer Tests/Alt-Setups: Wenn der aktive Wettbewerb keine offenen Spiele liefert, werden geplante Spiele des Spieltags ohne Competition-Filter gesucht.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.8] - 2026-05-18

### 📌 Mobile Sockelleiste

- Mobile Bottom-Tabbar fuer die wichtigsten App-Bereiche ergaenzt: Dashboard, Rangliste, Live und Tippübersicht.
- Safe-Area-Unterstuetzung fuer iPhone/Android-Gestensteuerung.
- Aktive Seite wird hervorgehoben; Live-Tab mit rotem Live-Indikator.
- Desktop bleibt unverändert; die Sockelleiste erscheint nur auf Smartphones.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.7] - 2026-05-18

### 📱 Tippübersicht Smartphone-Optimierung

- Spieler-Spalte und Spielspalten auf Smartphones verkleinert, damit mehr Paarungen sichtbar sind.
- Schriftgroessen, Paddings, Avatare und Punkte-Spalten in der Tippmatrix mobil kompakter.
- Sticky-Spieler-Spalte jetzt deckend statt transparent, damit beim horizontalen Scrollen keine Spielpaarungen im Hintergrund durchscheinen.
- Eigene Zeile bleibt markiert, aber mit deckendem Hintergrund und Akzentbalken.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.6] - 2026-05-18

### ☀️ Light-Mode-Kontrastfix

- Globale CSS-Aliase fuer alte Inline-Styles ergaenzt: `--card`, `--muted`, `--bg-subtle`, `--bg-app`.
- Tippübersicht im hellen Modus korrigiert: Tabellenzellen, Sticky-Spalte, Punkte-Spalten, Locks und Avatar-Fallbacks sind jetzt lesbar.
- Admin-Einstellungen im hellen Modus korrigiert: Accordion-Hintergruende und Summary-Texte nutzen helle Theme-Farben.
- Formularfelder, Checkbox-Zeilen und Flash-Meldungen im hellen Modus mit besserem Kontrast.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.5] - 2026-05-18

### 👀 Tippübersicht / Tippmatrix

- Neue Seite `/tipps` bzw. `/tipps/<spieltag>`: Matrix mit allen Spielern und allen Spielen eines Spieltags.
- Tipps anderer Spieler sind erst ab Spielstart sichtbar; vorher sind sie gesperrt.
- Eigene Tipps bleiben auch vor Anpfiff sichtbar und sind als `nur du` markiert.
- Fertige Spiele zeigen Ergebnis und Punkte pro Tipp.
- Gesamtpunkte, Gesamtrang und Spieltagspunkte je Spieler werden als Live-Werte angezeigt.
- Bei laufenden Spielen aktualisiert sich die Tippübersicht automatisch alle 30 Sekunden.
- Navigation in Spielplan und Hauptmenü ergänzt.
- KI-Expert-Bot leicht stabilisiert, damit H2H-starke Heimteams nicht zufällig mit 0 Heimtoren getestet werden.

### ✅ Verifikation

- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.4] - 2026-05-18

### 🔔 Benachrichtigungszentrale, Telegram Bot, Stats 2.0

- Neue `notification_center.py`: zentrale Reminder-Logik fuer E-Mail, Push, Telegram und WhatsApp.
- User-Praeferenzen fuer Benachrichtigungen ergaenzt: aktiv/inaktiv, Kanaele, Stunden vor Anpfiff, nur Lieblingsverein.
- Profil-Seite um eine Benachrichtigungszentrale erweitert.
- Scheduler und Cron nutzen jetzt die zentrale Reminder-Logik statt separater E-Mail-Schleifen.
- Telegram Bot erweitert: `/offen`, `/joker`, `/stats`; `/tipp ... joker` setzt direkt den Joker.
- Stats 2.0 im Statistik-Dashboard: Punkte-Serien, Durststrecke, mutige Treffer, Tipp-Neigung und Punkte-Liebling.
- Auto-Migration erweitert um Notification-Spalten in `users`.
- `NotificationLog` verhindert doppelte Reminder je User/Spiel/Kanal bei wiederholten Scheduler-/Cron-Läufen.

### ✅ Verifikation

- `python -m compileall -q .` erfolgreich.
- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.3] - 2026-05-18

### 🧱 Multi-Wettbewerb Schema-Finish

- `competition_id` fuer `SpecialQuestion`, `SpecialPrediction`, `Prize`, `MatchdayWinner` und `SeasonArchive` im Datenmodell ergaenzt.
- Auto-Migration erweitert: neue `competition_id`-Spalten werden fuer Bestandsdaten angelegt und auf den ersten aktiven Wettbewerb zurueckgefuellt.
- Sonderfragen, Sondertipps, Preise, Spieltagsieger und Saisonarchiv werden jetzt wettbewerbsbezogen angelegt und abgefragt.
- Saisonwechsel-/Reset-Logik loescht nun Spielplan-, Bot- und Sonderdaten wettbewerbsbezogen statt global.
- PDF-Export, Ewige Tabelle, Auto-Archivierung und Spieltagsieger-Zaehler beruecksichtigen den aktiven Wettbewerb.
- `build_vendor.bat` robuster fuer Netcup ohne SSH: laedt jetzt Linux/manylinux-Wheels passend zur Ziel-Python-Version und bietet explizit Python 3.9/3.12/3.13 an.

### ⚠️ Hinweis fuer bestehende SQLite-Datenbanken

Die Auto-Migration kann Spalten ergaenzen, aber bestehende Unique-Constraints nicht sauber umbauen. Fuer komplett getrennte Archive pro Wettbewerb und gleicher Saison ist mittelfristig Flask-Migrate/Alembic empfohlen. Neue Installationen haben die aktualisierten Constraints direkt.

### ✅ Verifikation

- `python -m compileall -q .` erfolgreich.
- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.2] - 2026-05-18

### 🏆 Multi-Wettbewerb-Fundament

- Neuer zentraler Helper `competition_helpers.py` fuer validierte aktive Wettbewerbe.
- Session-Wert `competition_code` wird zentral gegen aktive Competitions validiert.
- Match-/Spieltag-Queries in Hauptseiten, API, Admin-Matches, Bots, Live-Scoring, Scheduler/Cron, Telegram und Statistiken auf aktiven Wettbewerb eingegrenzt.
- Leaderboard-Cache-Key enthaelt jetzt Saison und Competition-Code (`leaderboard:<season>:<competition>:<matchday>`).
- Joker-Pruefung und Joker-Verschiebung sind jetzt wettbewerbsbezogen.
- Team-Form, H2H, Live-Tabelle, offene Spiele und aktueller Spieltag beruecksichtigen den aktiven Wettbewerb.

### ✅ Verifikation

- `python -m compileall -q .` erfolgreich.
- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

## [3.1.1] - 2026-05-18

### 🔧 Fix-Paket

- **DateTime-Defaults korrigiert:** SQLAlchemy-Defaults nutzen jetzt Callables (`lambda: datetime.now(timezone.utc)`) statt beim Import ausgewerteter Zeitstempel.
- **CSRF für API-Autosave ergänzt:** Tipp-Autosave in Matchdetail und Schnelltipps sendet jetzt `X-CSRFToken`; `sendBeacon` wurde durch `fetch(..., keepalive: true)` ersetzt.
- **Python 3.13 / PostgreSQL-Dependency:** `psycopg2-binary` auf `2.9.11` aktualisiert. Bleibt kompatibel mit Python 3.9.x.
- **Requests-Warnings beseitigt:** `urllib3`, `charset-normalizer` und `chardet` in `requirements.txt` kompatibel gepinnt.
- **SQLAlchemy 2.0 Cleanup:** `query.get_or_404()` durch `db.get_or_404(Model, id)` ersetzt.
- **Cache-Invalidierung:** Live-Match-Wildcards nutzen jetzt `delete_pattern()` statt `delete()`.
- **CI ergänzt:** GitHub Actions Workflow für Python 3.9 bis 3.13 hinzugefügt.

### ✅ Verifikation

- `python -m pip install -r requirements.txt` läuft lokal unter Python 3.13 durch.
- `python -m pytest -q`: **39/39 Tests bestanden**, keine Warnings.

---

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

## 2026-07-05 - Mehr-Seite & Hilfe/Regeln
- Neue Nutzerseite `/mehr` als zentrale Übersicht für Profil, Benachrichtigungen, Sonderfragen, Statistiken, Preise & Pott, Ewige Tabelle, Saisonbericht und Hilfe.
- Neue Hilfe-/Regelseite `/hilfe` plus Alias `/regeln` mit kurzen Erklärungen zu Punkten, Joker, Tippabgabe, Tippübersicht, Sonderfragen, Benachrichtigungen und Saison/Spieltag.
- Mobile Bottom-Navigation: „Mehr“ öffnet nun die neue Übersichtsseite statt das Hamburger-Menü.

## 2026-07-05 - User-Usability-Feinschliff ohne neue Features
- Smartphone-Menü vereinfacht: Hauptpunkte bleiben direkt sichtbar, Detailbereiche liegen gebündelt unter „Mehr“.
- Dashboard, Tippen, Spielplan, Tippübersicht, Live-Center und Tippdetails mit klareren Texten, leeren Zuständen und kontextbezogenen Hilfe-Hinweisen versehen.
- Begriffe für User vereinheitlicht: „Tippen“, „Spielplan“, „Tippübersicht“, „Sonderfragen“.
- Tippdetail zeigt jetzt deutlicher, ob ein Tipp fehlt, gespeichert ist oder nach Anpfiff nicht mehr abgegeben werden kann.

## 2026-07-05 - Fix Saisonbericht 500
- `/recap` repariert: Profil-Statistik-Helper wird in der ausgelagerten Stats-Route jetzt explizit importiert.
- Regressionstest fuer den Saisonbericht ergaenzt.
- Teststand: 101/101 bestanden, 1 harmlose reportlab-Warnung.

## 2026-07-06 - Komplettes Audit & Deployment-Hardening
- Komplettes Audit als `AUDIT_2026-07-06.md` erstellt.
- `build_vendor.bat` korrigiert: `vendor_manifest.txt` wird wieder mit normalem Pfad `vendor\vendor_manifest.txt` geschrieben.
- Login-Hinweis auf Standard-Admin wird in Production/Secure-Konfiguration nicht mehr angezeigt.
- Audit-Prüfung: compileall erfolgreich, 101/101 Tests bestanden, pip check ohne defekte Abhängigkeiten.

## 2026-07-06 - Tippen-Seite: volle Teamnamen
- Offene und bereits getippte Spiele auf der Tippen-Seite zeigen jetzt soweit möglich vollständige Mannschaftsnamen statt nur Kürzel.
- Desktop-Navigation vereinheitlicht: „Spielplan“ statt „Spiele/Tipps“.

## 2026-07-06 - Schnelltipp-Usability-Feinschliff
- Schnelltipp-Karten kompakter und auf Desktop breiter dargestellt.
- Datum/Uhrzeit klarer formatiert: Wochentag, Datum und „Uhr“.
- Fortschritt zeigt jetzt „x von y getippt · z fehlen“.
- Auto-Save-Hinweis verkleinert und Joker-Erklärung integriert.
- Team-Meta bereinigt: Tabellenplatz als „x. Platz“, keine leeren Form-Striche mehr.
- Plus/Minus-Stepper auch auf Desktop sichtbar und mobil klarer gruppiert.
- Kartenstatus ergänzt: offen, gespeichert, nicht mehr änderbar; Joker-Status zeigt „Joker aktiv – doppelte Punkte“.

## 2026-07-06 - Tippen-Seite: Trenner neutralisiert
- In offenen Tippkarten wird zwischen den Mannschaften nicht mehr das Wort „gegen“ angezeigt, sondern ein neutraler Gedankenstrich.

## 2026-07-06 - Tipp-Zahlenfelder einfacher bearbeiten
- Zahlenfelder im Schnelltipp und in der Tippdetail-Seite markieren beim Fokussieren den vorhandenen Wert.
- Der erste eingegebene Ziffernwert ersetzt den alten Tipp, statt ihn versehentlich anzuhängen. Dadurch entstehen nicht mehr ungewollt Werte wie `03` oder `30`.

## 2026-07-06 - Sync-Stabilität: Aufsteiger, Absteiger, Saisonwechsel, Logos
- OpenLigaDB-Fallback repariert: Vollsync lief bisher in einen undefinierten `source/current_ext_ids`-Pfad und konnte dadurch bei erfolgreicher OLB-Antwort crashen.
- OpenLigaDB legt unbekannte/Aufsteiger-Teams jetzt analog zu football-data.org automatisch an und verknüpft sie mit dem aktiven Wettbewerb.
- Quellenwechsel football-data.org → OpenLigaDB erhält vorhandene Spiele und Tipps über Paarungs-/Spieltag-Matching, statt Duplikate zu erzeugen oder Tipps zu löschen.
- Stale-Match-Bereinigung für Vollsyncs in einen gemeinsamen, wettbewerbsspezifischen Helper ausgelagert.
- football-data.org-Matching abgesichert, damit alte `fd:*`-Saisonspiele mit gleicher Paarung nicht versehentlich auf neue Spiele umgebogen werden.
- Logo-Fix zusätzlich getestet: lokale `/static/team_logos/...` werden nicht wieder auf externe URLs zurückgesetzt.
- Zusätzliche Regressionstests für OpenLigaDB-Aufsteiger, stale Matches, Quellenwechsel mit bestehenden Tipps und lokale Logos ergänzt.
- Teststand: 104/104 bestanden, Coverage ca. 60%, 1 harmlose reportlab-Warnung.

## 2026-07-06 - Automatische Tipp-Erinnerungen mit Testfunktion
- Benachrichtigungszentrale erweitert: Reminder bei fehlenden Tipps nutzen jetzt zentral die globale Einstellung `reminders_enabled` auch im Cron-Lauf.
- Admin-Einstellungen ergänzt um Abschnitt „Tipp-Erinnerungen“ mit Testbutton „Test-Erinnerung an mich senden“.
- Test-Erinnerungen nutzen die aktivierten Profil-Kanäle des Admins, schreiben aber keinen `NotificationLog`-Eintrag und blockieren daher keine echten Erinnerungen.
- Reminder-Texte zeigen vollständige Mannschaftsnamen.
- Tests für globale Reminder-Deaktivierung, Test-Reminder ohne NotificationLog und Admin-Testfunktion ergänzt.
- Teststand: 107/107 bestanden, Coverage ca. 60%, 1 harmlose reportlab-Warnung.

## 2026-07-06 - Spielplan: Uhrzeit und Tabellenplatz eindeutiger
- Im Spielplan steht hinter der Anstoßzeit jetzt „Uhr“.
- Tabellenplatz-Badges zeigen jetzt „x. Platz“ statt nur der Zahl.

## 2026-07-06 - Spielplan: Joker-Hinweis und Status klarer
- Joker-Hinweis im Spielplan zeigt jetzt, auf welches Spiel der Joker gesetzt wurde.
- Status „geplant“ wird bei offenen Spielen als „Tipp noch änderbar“ angezeigt.

## 2026-07-06 - Admin-Dashboard aufgeräumt
- Admin-Startseite neu strukturiert: kompakter Header, klickbare Kennzahlen und Fokusbereich „Wichtigste Aufgaben“.
- Seltenere Funktionen in einklappbare Gruppen verschoben: Spieler/Pott/Spiel, Einstellungen/Wartung, Saisonabschluss.
- Daten-Tools bleiben weiterhin separat eingeklappt als Sicherheitsbereich.

## 2026-07-06 - User-Einladungen
- Neue User-Seite `/einladen`: Jeder eingeloggte User kann Mitspieler per E-Mail einladen.
- Einladungslink kann kopiert oder direkt per WhatsApp/Mail-App geteilt werden.
- `/mehr` um „Mitspieler einladen“ ergänzt.
- Registrierung zeigt optional an, von wem die Einladung stammt (`?invited_by=...`).
- Tests für Einladungsseite und E-Mail-Versand ergänzt.
- Teststand: 109/109 bestanden, Coverage ca. 61%, 1 harmlose reportlab-Warnung.

## 2026-07-06 - Profilseite aufgeräumt
- Linke Profilseite übersichtlicher gestaltet: kompakterer Kopfbereich, kleinerer Avatar und klarer Abschnitt „Basisdaten“.
- Benachrichtigungen, WhatsApp und Telegram sind jetzt als kompakte einklappbare Karten dargestellt statt dauerhaft lange Blöcke zu zeigen.
- Benachrichtigungs-Kanäle werden kompakter als Raster angezeigt; Status-Badges zeigen aktiv/verknüpft/nicht eingerichtet.
- Datei-Upload und Hilfeboxen im Profil optisch geglättet.

## 2026-07-06 - User-Test fuer Benachrichtigungen
- Jeder User kann im Profil unter „Benachrichtigungen“ eine eigene Test-Benachrichtigung auslösen.
- Test nutzt die aktivierten und eingerichteten Kanäle des Users: E-Mail, Push, Telegram, WhatsApp.
- Test schreibt keinen `NotificationLog`-Eintrag und blockiert daher keine echten Erinnerungen.
- Regressionstest für die User-Testfunktion ergänzt.
- Teststand: 110/110 bestanden, Coverage ca. 61%, 1 harmlose reportlab-Warnung.

## 2026-07-06 - Landing-/Anmeldeseite: Saison dynamisch
- Die öffentliche Start-/Anmeldeseite zeigt die Saison jetzt aus der aktiven Competition bzw. den Saison-Einstellungen statt fest `2025/26`.

## 2026-07-06 - Login-Seite ohne Standard-Admin-Hinweis
- Hinweis auf Standard-Admin-Zugang von der Anmeldeseite entfernt.

## 2026-07-06 - Tippübersicht auf großen Bildschirmen optimiert
- Tippmatrix passt sich auf breiten Bildschirmen besser an und vermeidet dort den horizontalen Scrollbalken.
- Spaltenbreiten, Schriftgrößen und Abstände der Tippübersicht für Desktop kompakter abgestimmt.

## 2026-07-06 - Tippübersicht dezenter
- Fairness-Hinweis oberhalb der Tippmatrix optisch dezenter gestaltet.
- Lock-Symbole in gesperrten Tippzellen abgeschwächt, damit die Matrix ruhiger wirkt.

## 2026-07-06 - Tippübersicht Scrollen auf kleineren Fenstern repariert
- Horizontales Scrollen der Tippmatrix wieder auf kleinen Fenstern und Smartphones aktiviert.
- Auf mobilen Geräten wird ein dezenter Hinweis angezeigt, dass Querformat mehr Spiele gleichzeitig zeigt.
- Querformat-Darstellung auf Smartphones kompakter abgestimmt.

## 2026-07-06 - Tippübersicht: Querformat in PWA ermöglichen
- PWA-Manifest von `portrait-primary` auf `any` gestellt, damit Querformat grundsätzlich möglich ist.
- Manifest-Route liefert jetzt `Cache-Control: no-cache`, damit Orientation-Änderungen schneller greifen.
- Tippübersicht erhält auf Smartphones einen Querformat-Hinweis und einen Button zum Anstoßen des Landscape-Modus, falls vom Browser/PWA unterstützt.

## 2026-07-06 - Tippübersicht Mobile-Kopf kompakter
- Mobile Tippübersicht optimiert: Spieltag, Sortierung und Spielplan liegen jetzt in einer kompakten Werkzeugleiste.
- Fairness- und Querformat-Hinweise sind auf Smartphones deutlich flacher und nehmen weniger Höhe ein.

## 2026-07-06 - Tippübersicht Querformat: leeren Bereich entfernt
- Tippübersicht bekommt im Smartphone-Querformat einen eigenen Kompaktmodus.
- Header, Hinweise, Footer und Bottom-Navigation werden im Querformat reduziert/ausgeblendet, damit die Matrix direkt sichtbar ist.
- Matrix wird im Querformat flacher und kompakter dargestellt.

## 2026-07-07 - Sonderfragen-Antwort speichern ohne 500
- Speichern/Auswerten einer Antwort auf Sonderfragen abgesichert: Fehler beim Speichern oder Auswerten führen nicht mehr zu einem Internal Server Error.
- Antwort bleibt gespeichert, auch wenn die Auswertung ausnahmsweise fehlschlägt; Admin sieht dann eine Warnung.
- Regressionstests für erfolgreiches Speichern und abgefangene Auswertungsfehler ergänzt.
- Teststand: 114/114 bestanden, Coverage ca. 62%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - User-Sonderfragen ohne 500
- User-Seite `/sondertipps` repariert: lokaler JSON-Import statt fehlendem `_json` aus Lazy-Import.
- Speichern von normalen und Multi-Team-Sonderfragen abgesichert und mit Regressionstests versehen.
- Teststand: 116/116 bestanden, Coverage ca. 63%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - Bots standardmäßig inaktiv
- KI-Bots sind jetzt standardmäßig inaktiv und erscheinen erst in Ranglisten/Spielerlisten, wenn sie im Adminbereich explizit aktiviert wurden.
- Bot-Tippgenerierung respektiert ebenfalls den inaktiven Standard.
- Neu angelegte einzelne Bots werden explizit als inaktiv gespeichert.
- Cache-Version auf `v3` erhöht, damit alte Leaderboard-Caches mit Bots nicht weiterverwendet werden.
- Regressionstest ergänzt: Bot-User werden ohne Aktivierung aus aktiven Userlisten gefiltert.
- Teststand: 117/117 bestanden, Coverage ca. 63%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - Admin-Konto taucht nicht mehr als Spieler auf
- Bootstrap erstellt keinen zusaetzlichen Default-Admin mehr, wenn bereits ein anderes Admin-Konto existiert.
- Reine Admin-Konten ohne Spielaktivitaet werden aus Spieler-/Ranglisten gefiltert. Admins, die selbst tippen, bleiben sichtbar.
- Regressionstest ergänzt: Admin ohne Tipp wird ausgeblendet, spielender Admin bleibt sichtbar.
- Teststand: 118/118 bestanden, Coverage ca. 63%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - Reine Admin-Konten zählen nicht zum Pott
- Reine Admin-Konten ohne Spielaktivität zählen jetzt nicht als zahlende Mitspieler im Pott.
- Spielende Admins bleiben weiterhin Pott-/Mitspieler, sobald sie Tipps oder Sonderfragen abgegeben haben.
- Spielerverwaltung zeigt für reine Admin-Konten „Verwaltung“ statt Bezahlt-Toggle.
- Bezahlstatus reiner Admin-Konten kann nicht mehr versehentlich aktiviert werden.
- Dashboard- und Saisonwechsel-Zählungen nutzen nun den bereinigten Pott-/Mitspielerstand.
- Regressionstest ergänzt: Admin-only wird im Pott nicht gezählt.
- Teststand: 119/119 bestanden, Coverage ca. 63%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - Liga-Tabelle mobile mit Vereinsnamen
- Smartphone-Ansicht der Bundesliga-Tabelle zeigt jetzt volle Vereinsnamen mit Kürzel darunter.
- Lange Namen werden auf maximal zwei Zeilen begrenzt, damit die Tabelle kompakt bleibt.
- Die Tore-Spalte wird auf Smartphone ausgeblendet, damit Teamnamen und Punkte lesbar bleiben.

## 2026-07-07 - Tippübersicht besser lesbar
- Vereinskürzel, Datum/Uhrzeit, Ergebnisse und Tippzahlen in der Tippübersicht kontrastreicher dargestellt.
- Gesperrte Spielspalten werden nicht mehr komplett abgedimmt; nur Lock-Symbole bleiben dezent.

## 2026-07-07 - Sonderfragen: aktuelle Teams und Multi-Auswahl
- Sonderfragen mit Teamantworten zeigen jetzt nur Teams des aktiven Wettbewerbs/aktuellen Spielplans, nicht mehr alte Absteiger aus der globalen Teamliste.
- Fallback bei noch leerem Spielplan: CompetitionTeam-Zuordnungen, danach alle Teams.
- Admin- und User-Seite nutzen denselben aktuellen Teamfilter.
- Multi-Team-Fragen begrenzen die Auswahl weiterhin auf `multi_count`; Admin-Auflösungen werden serverseitig ebenfalls auf diese Anzahl begrenzt.
- Regressionstests ergänzt: alte Absteiger erscheinen nicht mehr in User-/Admin-Teamantworten.
- Teststand: 121/121 bestanden, Coverage ca. 63%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - Sonderfragen: eingeschränkte Team-Auswahl
- Team- und Multi-Team-Sonderfragen können jetzt über „Antwortoptionen / eingeschränkte Teams“ auf bestimmte Mannschaften begrenzt werden.
- Beispiel „Wer wird bester Aufsteiger?“: Bei Antworttyp „Mannschaft“ nur die drei Aufsteiger zeilenweise als Optionen eintragen; User sehen dann nur diese drei Teams.
- User- und Admin-Auflösung filtern serverseitig ungültige Teamantworten heraus.
- Formular-Hilfe im Adminbereich erweitert.
- Regressionstests für eingeschränkte Teamoptionen in User- und Adminansicht ergänzt.
- Teststand: 123/123 bestanden, Coverage ca. 63%, 1 harmlose reportlab-Warnung.

## 2026-07-07 - KI-Bot-Stärke im Adminbereich transparenter
- Adminseite „KI-Tippgegner“ um erklärenden Abschnitt „Wie wird die Bot-Stärke definiert?“ ergänzt.
- Pro Bot werden Zufallsanteil, Datengewichtung und kurze Beschreibung des Tippverhaltens angezeigt.
- Bot-Tabelle zeigt zusätzlich die Spalte „Tippverhalten“.

## 2026-07-07 - KI-Bots mobil konfigurierbar
- KI-Bot-Verwaltung auf Smartphones als Kartenlayout ergänzt.
- Aktivieren/Deaktivieren, einzelnes Tippen und Reset sind nun mobil direkt bedienbar.
- Desktop-Tabelle bleibt erhalten, wird auf kleinen Screens ausgeblendet.

## 2026-07-07 - KI-Bots Mobile-Karten sichtbar
- Fehler in der mobilen KI-Bot-Verwaltung behoben: Kartenlayout wurde zwar gestylt, aber nicht ins Template gerendert.
- Bots erscheinen auf Smartphone jetzt wirklich als konfigurierbare Karten unterhalb der Aktionsleiste.

## 2026-07-07 - KI-Bot-Beschreibungen entdoppelt
- Lange Bot-Erklärungen bleiben nur noch im oberen Infobereich.
- In Tabelle und Mobile-Karten steht unter „Kurzprofil“ nur noch Kurztext plus Zufalls-/Datengewichtung.

## 2026-07-07 - KI-Bots mobil weiter verdichtet
- Ausführlicher Bot-Erklärbereich ist jetzt standardmäßig eingeklappt.
- Mobile Bot-Karten zeigen nur noch Kurzprofil, Zufallsanteil und Datengewichtung – keine langen Beschreibungstexte mehr.

## 2026-07-07 - Bot-Aktion umbenannt und Auto-Tipp vorbereitet
- „Alle Bots tippen lassen“ in „Aktive Bots tippen lassen“ umbenannt, weil nur aktivierte Bots tippen und inaktive übersprungen werden.
- Admin-Botseite um Auto-Tipp-Schalter ergänzt.
- Neuer Cron-Task `python cron_jobs.py bots`; `python cron_jobs.py all` führt jetzt Sync → aktive Bot-Tipps → Reminder aus.
- Auto-Tipps überschreiben keine vorhandenen Bot-Tipps.

## 2026-07-07 - Fairness- und Datenintegritäts-Fix aus Audit
- Joker kann nicht mehr von einem bereits angepfiffenen bisherigen Joker-Spiel auf ein anderes Spiel verschoben werden.
- Nach Joker-Speicherung wird pro User/Spieltag/Wettbewerb auf genau einen Joker bereinigt.
- Schnelltipp validiert manipulierte Scores jetzt serverseitig auf 0 bis 30 Tore.
- Klassifikation nicht-exakter Unentschieden korrigiert: z.B. 1:1 bei Ergebnis 2:2 zählt als Tendenz, nicht als Tordifferenz.
- Sync-Purge bekommt Sicherheitsbremse: Bei offensichtlich unvollständiger API-Antwort werden lokale Spiele/Tipps nicht gelöscht.
- Regressionstests für Joker-Sperre, Schnelltipp-Validierung, Remis-Klassifikation und Sync-Purge-Schutz ergänzt.
- Teststand: 127/127 bestanden, Coverage ca. 64%, 1 harmlose reportlab-Warnung.

## 2026-08-10 - Einladungscode-Registrierung & mobile Tippübersicht pro Spiel
- Registrierung ist jetzt ohne gültigen Einladungscode gesperrt.
- Einladungsseite erzeugt teilbare Einladungscodes und persönliche E-Mail-Einladungen mit eigenem Code.
- Einladungscodes werden in neuer Tabelle `invitation_codes` gespeichert und beim Registrieren verbraucht bzw. gezählt.
- Registrierungsseite zeigt bei fehlendem/ungültigem Code einen klaren Hinweis.
- Tippübersicht hat auf Smartphones zusätzlich eine Spiel-für-Spiel-Ansicht mit Spielauswahl; Desktop-Matrix bleibt erhalten.
- Regressionstests für Einladungscode-Registrierung, Invite-Mail und mobile/klassische Tippübersicht ergänzt.
- Teststand: 128/128 bestanden, Coverage ca. 64%, 1 harmlose reportlab-Warnung.

## 2026-08-10 - Registrierungsmodus einstellbar
- Admin-Einstellungen um Registrierungsmodus ergänzt: offen, nur Einladungscode oder geschlossen.
- Standard bleibt „nur Einladungscode“.
- Modus „offen“ erlaubt Registrierung ohne Code; Modus „geschlossen“ blockiert auch gültige Einladungscodes.
- Tests für offene und geschlossene Registrierung ergänzt.
- Teststand: 130/130 bestanden, Coverage ca. 64%, 1 harmlose reportlab-Warnung.

## 2026-08-10 - Login zeigt Registrierungsmodus
- Anmeldeseite zeigt jetzt transparent, ob Registrierung offen, nur per Einladungscode oder geschlossen ist.

## 2026-08-10 - Saisonwechsel-Schutz und zentrales Ergebnis-Update
- Ergebnis-Updates zentralisiert in `match_results.py` mit Commit, Punkte-Neuberechnung, Badge-Pruefung und Cache-Invalidierung.
- Manuelle Admin-Ergebniseingabe nutzt jetzt `set_match_result()`.
- Sync-Pfade nutzen fuer bestehende Matches den zentralen `apply_match_update()`-Helper.
- Saisonwechsel-Assistent verlangt jetzt explizite Backup-Bestaetigung.
- Bei offenen/live Spielen, fehlenden Ergebnissen oder offenen Sonderfragen ist eine zusaetzliche Risiko-Bestaetigung erforderlich.
- Saisonwechsel-Template zeigt die neuen Sicherheitsbestaetigungen direkt vor dem Start.
- Regressionstests fuer zentrales Ergebnis-Update und Backup-Pflicht beim Saisonwechsel ergaenzt.
- Teststand: 132/132 bestanden, Coverage ca. 64%, 1 harmlose reportlab-Warnung.

## 2026-08-10 - Datenintegritaets-Check und Einladungsverwaltung
- Neue Admin-Seite `/admin/integrity` mit Checks fuer Mehrfach-Joker, ungueltige Tipps, reine Admins im Pott, Sonderfragen ohne Wettbewerb, Team-/Spielanzahl und beendete Spiele ohne Ergebnis.
- Sichere Reparaturen ergaenzt: Mehrfach-Joker bereinigen, ungueltige Tipps auf 0–30 clampen, reine Admins aus Pott entfernen, fehlende Competition-IDs bei Sonderfragen/-tipps setzen.
- Neue Admin-Seite `/admin/invitations` zum Anzeigen, Erstellen, Deaktivieren und Loeschen von Einladungscodes.
- Admin-Dashboard um Links zu Datenintegritaet und Einladungen ergaenzt.
- Tests fuer Integritaetsseite/Reparatur und Einladungsverwaltung ergaenzt.
- Teststand: 134/134 bestanden, Coverage ca. 65%, 1 harmlose reportlab-Warnung.

## 2026-08-10 - Schnelltipp Smartphone kompakter
- Auto-Save-Hinweis in die Fortschrittskarte integriert; separate Hinweisbox entfernt.
- Spielkarten, Teamkarten, Status-Badges, Tippfelder und Joker-Bereich auf Smartphone kompakter gestaltet.
- Globaler unterer Tippstatus wird auf der Schnelltipp-Seite ausgeblendet, weil der Fortschritt dort bereits oben steht.

## 2026-08-10 - Performance Hotpaths optimiert
- Punkte-Neuberechnung fuer Ergebnisupdates zentral auf betroffene Matches reduziert (`recalculate_match_points`, `recalculate_matches_points`).
- `match_results.py` nutzt jetzt match-spezifische Neuberechnung inklusive Badge-Pruefung nur fuer betroffene User.
- Sync aktualisiert bestehende Matches ueber `apply_match_update()` und berechnet Punkte nur fuer Matches mit Ergebnis-/Statusaenderung neu; globale Neuberechnung bleibt fuer destructive Purges.
- Badge-Pruefung kann jetzt auf einzelne/betroffene User begrenzt werden.
- Tipp-Speicherpfade pruefen Badges nur noch fuer den aktuellen User statt fuer alle User.
- Flaky Bot-Test mit festem Random-Seed stabilisiert.
- Teststand: 134/134 bestanden, Coverage ca. 65%, 1 harmlose reportlab-Warnung.
