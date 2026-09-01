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

## 2026-08-30 - Admin-Kleinigkeiten: Offene Tipps, Spieler-Vorschau, Smoke-Tests

- Neue Admin-Seite `/admin/open-tips`: Übersicht offener Tipps je Spieltag und User auf einen Blick.
- Reminder-Versand an offene Tipper direkt aus der Übersicht (benutzt die Benachrichtigungszentrale).
- Spieler-Vorschau-Modus für Admins: App temporär aus Spielerperspektive ansehen (reine Admin-Bereiche dabei ausgeblendet) und per Aktion wieder beenden.
- Neues pragmatisches Admin-Smoke-Test-Paket (Package 3): Spielerfilter, Einladungen, Sonderfragen, Bots, Saisonwechsel-Seite, Preise, Wartungscenter und Spieler-Vorschau gegen 500er/Regressionen abgesichert.
- Weitere Kleinkorrekturen und Polishing im Adminbereich.
- Teststand: 163/163 bestanden, Coverage ca. 72%, 1 harmlose reportlab-Warnung.

## 2026-08-30 - Fix: Punkteanzeige verschwand zwischenzeitlich (Status-Monotonie)

- Produktionsfehler behoben: Beendete Spiele konnten durch API-Syncs zeitweise wieder auf "scheduled" zurückgesetzt werden – Ergebnis und Punkte verschwanden dann in Tippübersicht und Rangliste, bis ein späterer Sync den Status erneut setzte (Spiele vom Samstag waren z. B. am Sonntag punktlos, das Freitagsspiel und das gerade laufende Spiel nicht).
- `apply_match_update()` mit Status-Monotonie: "finished" und "live" können durch automatische Quellen nicht mehr zurückgedreht werden. Erlaubte Übergänge bleiben: scheduled → live → finished sowie Score-Korrektur bei finished. Explizites Zurücksetzen nur noch mit `allow_status_reset=True` (Admin).
- FD-Cache-Fallback bei API-Fehlern (429/Netzfehler) auf max. 10 Minuten begrenzt, damit veraltete Statusdaten keine frischeren Zustände mehr überschreiben.
- Sicherheitsnetz aktiviert: `_fill_missing_from_openligadb()` zieht nach jedem erfolgreichen FD-Sync fällige Spiele ohne Ergebnis aus OpenLigaDB nach (war bisher ungenutzter Code ohne Aufrufer).
- Neue Regressionstests in `tests/test_sync_status_monotonic.py` (9 Fälle: Downgrade-Blocker für FD und OLB, Score-Korrektur, normale Übergänge, Admin-Reset, Cache-Begrenzung).
- Teststand: 172/172 bestanden, Coverage ca. 72 %, 1 harmlose reportlab-Warnung.

## 2026-08-30 - CI-Workflow wiederhergestellt

- `.github/workflows/tests.yml` nachgebaut (war beim Upload der Projektdateien nie mit auf GitHub gelandet, Verlauf geprueft).
- Jobs wie urspruenglich: flake8-Lintgate (haertes Gate nur bei Syntaxfehlern/undefinierten Namen, Rest als Statistik) plus pytest-Matrix auf Python 3.9 bis 3.13 mit Coverage aus pytest.ini.
- `psycopg2-binary` wird in CI explizit nicht installiert (Tests laufen mit SQLite; fuer den gepinnten Stand gibt es keine cp313-Wheels).
- Lokal verifiziert: flake8-Gate 0 Fehler, Teststand unveraendert 172/172.

## 2026-08-30 - Schnelltipp: nach dem Speichern im Schnelltipp bleiben

- Nach „Alle Tipps speichern" im Schnelltipp bleibt man jetzt auf der Schnelltipp-Seite (gleicher Spieltag), statt auf „Spiele & Tipps" (Spielplan) weitergeleitet zu werden.
- Gespeicherte Tipps und Fortschritt sind damit direkt sichtbar.
- Regressionstest ergänzt (Redirect-Ziel und gespeicherte Werte).
- Teststand: 173/173 bestanden, Coverage ca. 72 %, 1 harmlose reportlab-Warnung.

## 2026-08-30 - Statistik-Dashboard aufgeräumt & neu gestaltet

- Dashboard komplett neu strukturiert: klare Reihenfolge nach Nutzwert – Kennzahlen (Punkte/Rang/Tipps/Ø/Joker), Fun-Facts-Leiste, dann die zwei Hauptdiagramme (Punkte-Verlauf, Ranglistenverlauf aller Spieler), danach kompakte Detailkarten.
- Desktop bekommt ein echtes Layout: Zwei-Spalten-Grid für die Detailkarten statt endloser Scrollstrecke; Diagrammhöhen begrenzt (keine riesigen Vollbreiten-Grafiken mehr).
- Doppelungen entfernt: Tipp-Verteilung (Donut) + separate Tipp-Stil-Tabelle + Neigungszeile zu einer Karte „Tipp-Stil & -Verteilung" mit Prozentbalken und Häufigste-Tipps-Chips zusammengeführt; Joker-Donut durch kompakte Trefferquoten-Anzeige ersetzt; Bot-Vergleich nur noch einmal als Tabelle statt zusätzlich als Balkendiagramm.
- Anzahl der Chart.js-Diagramme von 7 auf 3 reduziert (Punkte-Verlauf, Ranglistenverlauf, Tipp-Qualität) – Seite lädt spürbar schneller und bleibt mobil wie vorher einspaltig.
- Anzeige der Joker-Trefferquote ohne Nachkommastellen.
- Bestehender Dashboard-Test an die neue Kartenstruktur angepasst.
- Teststand: 173/173 bestanden, Coverage ca. 72 %, 1 harmlose reportlab-Warnung.

## 2026-08-31 - Spieltags-Preview & -Recap neu gestaltet + globales Statistik-CSS

- Beide Spieltagsseiten komplett neu strukturiert, passend zum gestrigen Dashboard-Redesign: gestylte Kennzahlen-Leiste oben (statt ungestylter KPI-Klassen), dann inhaltlich nach Nutzwert sortiert.
- Recap: neue „Highlights des Spieltags“-Liste (🥇 Sieger, 🎯 bester Einzeltipp inkl. getipptem Ergebnis, ⚡ bester Joker) – eigene Einträge werden wie in der Tabelle hervorgehoben; Spieltagswertung mit 🥇 für Rang 1 und DU-Badge.
- Preview: Top-Spiel als Highlight-Karte (häufigster Tipp + Anzahl Tipps), Spiele als kompakte Karten im Zweispalten-Grid mit Status-Badge und bestehender Tipptendenz-Anzeige, offene Tipper als Chip-Übersicht.
- CSS dafür liegt **einmalig global** in `static/css/style.css` (Block „Statistik-Karten & Redesign-Toolkit“: Statistik-Karten/KPIs, Section-/Chart-Boxen, Tipp-Stil-Farben, Chips, Split-Balken, Highlight-Liste) statt dreifach seitenlokal – der seitenlokale <style>-Block aus dem Dashboard ist entfernt; Dashboard-Klassen dafür kollisionsfrei umbenannt (tip-chip → tchip, joker-split → split-bar, joker-quote → legend-right).
- Folge: das neue Styling wirkt automatisch auch auf künftige Seiten, und `recap.html` nutzt jetzt den globalen `.highlight-row`-Stil (wirkungsneutral, identische Farbe).
- Preview/Recap-Tests gehärtet: aktiver Wettbewerb (TEST-Fixture) wird explizit in der Session gesetzt – isoliert wie im Vollauf stabil grün (vorher reihenfolgeabhängig durch den Demo-BL1-Saisonstart).
- Teststand: 173/173 bestanden, zweimal hintereinander.

## 2026-08-31 - Mini-Charts in Vorschau/Rückblick + komplette Deutsche Übersetzung

- **Neu: zwei kleine Chart.js-Diagramme.** Spieltags-Vorschau: horizontales Balkendiagramm „Tippquote der Spiele“ (0–100 %, wie viele Mitspieler je Spiel getippt haben). Spieltags-Rückblick: horizontales Balkendiagramm „Punkte des Spieltags“ (Top 15; 🥇 Gold = Spieltagsieger, Blau = eigener Balken, sonst Teal). Kompakt in den vorhandenen Chart-Boxen, kein Aufblähen der Seiten.
- **Übersetzung ins Deutsche:** Die beiden Seiten heißen jetzt durchgängig **„Spieltags-Vorschau“** und **„Spieltags-Rückblick“** (Titel, H1, Wechsel-Buttons). Ebenso angepasst: Bottom-Nav-Eintrag „Preview & Recap“ → „Vorschau & Rückblick“, Mehr-Seite („Spieltags-Vorschau“/-„Rückblick“), Spielplan-Button („Vorschau“). Das Status-Badge in der Vorschau zeigt deutscher Ursprungszustand: „geplant“ / „LIVE“ / „beendet“ statt Roh-Status „scheduled“.
- Tests angepasst & erweitert: Assertions auf die neuen deutschen Titel, Chart-Canvas-IDs (`previewQuoteChart`, `recapPunkteChart`) und deutschen Status „geplant“.
- Technik-Hinweis: Jinja-Variablen für Chart-Daten werden auf Template-Ebene (außerhalb der Blöcke) aufgebaut – innerhalb von `{% block %}` gesetzte Variablen sind in anderen Blöcken nicht sichtbar (Undefined-Fehler).
- Teststand: 173/173 bestanden, zweimal hintereinander.

## 2026-08-31 - Spieltagsieger-Chronik: volle Namen auf dem Smartphone

- Auf kleinen Bildschirmen (≤ 640 px) wurden die Gewinnernamen in der Chronik mit „…" abgeschnitten (fester Ellipsis-Stil) — z. B. nur „Tante …" statt „Tante Käthe".
- Fix in `static/css/style.css` (rein CSS, keine Logik): Auf dem Smartphone darf der Name jetzt auf bis zu zwei Zeilen umbrechen, dazu etwas schmaleres Layout (Tag-Box 70 → 56 px, Avatar 32 → 28 px, kleinere Abstände) — ausgesprochen lange Namen bleiben per Zeilenumbruch vollständig lesbar, Desktop unverändert.
- Teststand: 173/173 bestanden.

## 2026-08-31 - Menü „Mehr" konsistent zwischen Desktop und Smartphone

- **Ungleiche Inhalte aufgeräumt:** Das Desktop-„Mehr"-Dropdown enthielt nicht alles, was die Smartphone-„Mehr"-Seite zeigt (u. a. fehlten Saisonbericht und Mitspieler einladen komplett; am Desktop war die Einladung sonst nirgends erreichbar). Umgekehrt gab es „Vorschau & Rückblick" am Handy nur als kleinen Schnellzugriffs-Chip statt als Karte.
- **Desktop-Dropdown** spiegelt jetzt die komplette Auswahl der Mehr-Seite: Mehr Übersicht, Sonderfragen, Statistiken, Vorschau & Rückblick, Gewinne & Pott, Ewige Tabelle, **Saisonbericht (neu im Menü)**, **Mitspieler einladen (neu im Menü)**, Hilfe & Regeln. Profil/Benachrichtigungen bleiben bewusst draußen – dafür gibt es am Desktop schon den User-Chip oben rechts.
- **Mehr-Seite (Smartphone):** neue Karte „🔮 Vorschau & Rückblick" im Hauptbereich (statt nur Schnellzugriff-Chip), Namensgleichheit hergestellt: „Preise & Pott" → **„Gewinne & Pott"** (so heißt die Seite selbst). Schnellzugriff verschlankt: Tippübersicht, Spieltags-Rückblick, Liga-Tabelle.
- Menüpunkt „Einladen" wird jetzt überall als aktiv markiert (Desktop-Dropdown, obere Navigation, Bottom-Tabbar).
- Bei sehr flachen Fenstern bekommt das Desktop-Dropdown eine Maximalhöhe mit Scrollen.
- Teststand: 173/173 bestanden.

## 2026-08-31 - Mehr-Seite entdoppelt & Schnellzugriff nach oben

- Auf der Smartphone-„Mehr"-Seite erschien „Hilfe & Regeln" doppelt: einmal als großer grüner Button im Hero ganz oben und nochmals als Akzent-Karte im Kartenraster. Der Hero-Button ist entfernt — die Karte bleibt der einzige Hilfe-Einstieg.
- Der **Schnellzugriff** (Tippübersicht, Spieltags-Rückblick, Liga-Tabelle) stand ganz unten unter allen Karten — bei einer Seite, die als Navigationshilfe dient, unlogisch. Er sitzt jetzt **direkt unter dem Hero**, danach folgt das Kartenraster.
- Hero-Text leicht angepasst („Gewinne" statt „Preise", passend zur einheitlichen Benennung); ungenutzte CSS-Regel `.more-hero-btn` entfernt.
- Teststand: 173/173 bestanden.

## 2026-08-31 - Schnellzugriff: vierter Chip „⚡ Schnelltipp"

- Der Schnellzugriff auf der Mehr-Seite hat einen vierten Chip bekommen: **⚡ Schnelltipp** an erster Stelle (direkt zum aktuellen Spieltag), danach Tippübersicht, Spieltags-Rückblick, Liga-Tabelle.
- Teststand: 173/173 bestanden.

## 2026-08-31 - Schnellzugriff: fünfter Chip „🔮 Vorschau"

- Der Schnellzugriff enthält jetzt auch **🔮 Vorschau** (direkt zum aktuellen Spieltag) an zweiter Stelle, zwischen Schnelltipp und Tippübersicht. Damit: Schnelltipp · Vorschau · Tippübersicht · Spieltags-Rückblick · Liga-Tabelle.
- Teststand: 173/173 bestanden.

## 2026-08-31 - Schnellzugriff: Sortierung + garantiert zwei Zeilen mobil

- Neue Reihenfolge im Schnellzugriff: **Schnelltipp · Tippübersicht · Vorschau · Rückblick · Liga-Tabelle**; „Spieltags-Rückblick" zu **„Rückblick"** verkürzt.
- Mobil (≤ 640 px) umbrachen die Pill-Chips bisher je nach Gerätebreite zufällig auf drei Zeilen. Jetzt fest per CSS-Grid gesteuert: **3 Chips oben + 2 Chips unten**, gleichmäßig verteilte Breiten, kompaktere Schrift (12 px).
- Icons in eigene Spans gelegt; auf sehr schmalen Geräten (≤ 380 px) werden sie ausgeblendet, damit „Tippübersicht" sicher ohne Abschneiden passt. Desktop-Ansicht unverändert (Pill-Reihe mit natürlichem Umbruch).
- Teststand: 173/173 bestanden.

## 2026-08-31 - Schnelltipp: Buttons bei abgeschlossenem Spieltag ausgrauen

- Auf Vergangenheits-Spieltagen (zurückgeblättert auf einen abgeschlossenen Spieltag) waren im Schnelltipp die Footer-Buttons **„🎲 Zufällig füllen"** und **„💾 Alle Tipps speichern"** weiter aktiv, obwohl sie dort nichts mehr bewirken können — die einzelnen Eingabefelder waren zwar gesperrt, die Buttons aber nicht.
- Wenn an einem Spieltag kein Spiel mehr tippbar ist (`is_open()` false bei allen), werden beide Buttons jetzt **deaktiviert und ausgegraut** (`disabled`, Opazität 45 %, kein Hover-Effekt), dazu ein Hinweis unter den Buttons: „🔒 Dieser Spieltag ist abgeschlossen — Tipps können nicht mehr geändert werden."
- Gemischte Spieltage (z. B. Freitagsspiel beendet, Rest offen) bleiben unverändert bedienbar: Buttons aktiv, nur gesperrte Spiele ausgegraut — der Zufallsgenerator füllt ohnehin nur offene Felder (prüfte bereits `!inp.disabled`).
- Serverseitig war das Überschreiben gesperrter Spiele schon geblockt (POST überspringt `not m.is_open()`) — die Änderung ist reine UI-Verbesserung, keine Sicherheitslücke.
- Zwei neue Tests: Buttons deaktiviert bei abgeschlossenem Spieltag; Buttons aktiv + korrekt gesperrte/freie Eingabefelder bei gemischtem Spieltag.
- Teststand: 175/175 bestanden.

## 2026-08-31 - Schnelltipp: offizielles Ergebnis bei beendeten Spielen

- Bei beendeten Spielen standen im Schnelltipp nur die eigenen (gesperrten) Tipps — das tatsächliche Ergebnis fehlte.
- Neu erscheint unter den Tippfeldern ein Ergebnis-Chip: **„Ergebnis 3:1"**, bei vorhandenem Tipp zusätzlich die **erzielten Punkte** („· +4 Pkt", auch „· 0 Pkt" bei Nieten; noch nicht ausgewertete Tipps ohne Punkteanzeige).
- Nur bei Status `finished` — bei Live-Spielen gibt es bewusst kein solches Label, damit ein Zwischenstand nicht wie ein Endergebnis aussieht.
- Zwei neue Tests: Ergebnis + Punkte werden bei beendeten Spielen angezeigt; offene Spiele zeigen keine Ergebnisbox.
- Teststand: 177/177 bestanden.

## 2026-08-31 - Schnelltipp: Ausgrauung abgeschlossener Spiele abgemildert

- Die Deckkraft der Ausgrauung war insgesamt zu stark: abgeschlossene Spielkarten lagen bei 50 %, deaktivierte Stepper-Buttons bei 30 %, die Footer-Buttons („Zufällig füllen"/„Alle Tipps speichern") bei 45 %.
- Neue, dezentere Stufen: Karten 78 %, Stepper 50 %, Footer-Buttons 65 % — der Sperr-Status bleibt klar erkennbar, Inhalte (Namen, Logos, neue Ergebnisanzeige) sind aber gut lesbar.
- Teststand: 177/177 bestanden.

## 2026-08-31 - Formkurve mit deutschen Buchstaben (S/U/N)

- Die kleinen Form-Kästchen neben den Teams zeigten **englische** Kürzel (W/D/L = Win/Draw/Loss), die Legende im Schnelltipp-Footer erklärte sie aber schon deutsch (S/U/N) uneinheitlich.
- Anzeige jetzt überall deutsch: **S = Sieg, U = Unentschieden, N = Niederlage** — in allen drei Templates, die die Formkurve rendern (Schnelltipp, Spiele & Tipps, Spiel-Details). Die CSS-Klassen (form-W/D/L) bleiben bewusst englisch/technisch, nur der sichtbare Buchstabe ändert sich.
- Reihenfolge unverändert: ältestes Spiel links, jüngstes rechts (die Kästchen zeigen die letzten 5 Spiele).
- Neuer Test: im Schnelltipp erscheinen form-W→„S", form-D→„U", form-L→„N", keine englischen Buchstaben mehr.
- Teststand: 178/178 bestanden.

## 2026-08-31 - Schnelltipp: Ergebnis-Chip auf schmalen Screens lesbar

- Die gestern eingeführte Ergebnisanzeige saß innerhalb der schmalen mittleren Spalte (Score-Block, fix 120 px). Auf dem Smartphone blieb davon nur „Erg" übrig — und auch am Desktop passte „Ergebnis 2:1 · +4 Pkt" dort nie vollständig hinein.
- Der Chip liegt jetzt auf eigener Zeile unter der Team-Zeile und nimmt die **volle Kartenbreite** (zentriert) ein — auf jeder Fenstergröße vollständig lesbar, kein horizontales Abschneiden mehr.
- Teststand: 178/178 bestanden.

## 2026-08-31 - Doppel-Saisonlabel entdoppelt („Bundesliga 2026 2026")

- **Ursache:** Der Admin-Saisonwechsel schrieb die Saison sowohl in `name` als auch `season` der Competition (name='Bundesliga 2026', season='2026') — überall, wo die App beides zusammen rendert, entstand „Bundesliga 2026 2026".
- **Dreifach gelöst:** 1) Neue Helper-Funktion `competition_label(name, season)` dedupliziert robust („Bundesliga 2026"+„2026"→„Bundesliga 2026"; „Bundesliga 2026"+„2026/27"→„Bundesliga 2026/27"; „Bundesliga"+„2025/26"→„Bundesliga · 2025/26") und liegt als `comp_label` im Template-Kontext. 2) Alle Anzeige-Stellen umgestellt (Header/Comp-Selector, Mobile-User-Card, Spieltags-Vorschau/-Rückblick, Tippübersicht). 3) **Ursache behoben:** Der Saisonwechsel schreibt die Saison nicht mehr in den Namen und bereinigt beim nächsten Wechsel automatisch Altbestand.
- Tests: reine Fälle (7 Varianten), Saisonwechsel hinterlässt sauberen Namen, gerenderte Seite ohne Doppelung.

## 2026-08-31 - Sync mit API-Mocks abgesichert (Testdatei test_sync_mocked.py)

- Neue Testsuite deckt den kompletten Sync **ohne echte APIs** ab (requests komplett gemockt):
  - **Mapping football-data.org:** Spiele+Teams werden angelegt, Status-Mapping (FINISHED→finished), Kickoff-Parsing, `external_id` fd:…
  - **Deduplizierung:** Zweiter Lauf erzeugt keine Dubletten, aktualisiert stattdessen.
  - **Ergebnis-Update:** scheduled→finished aktualisiert Score+Status und **berechnet Tipppunkte neu** (exakter Tipp → volle Punkte).
  - **Rate-Limit/Timeout/Cache:** Timeout → saubere Fehlermeldung statt Crash; HTTP 429 → Rate-Limit-Meldung; frischer Cache (≤10 min) schlägt Netzfehler; kaputtes JSON → klare Meldung.
  - **Purge-Bremse:** Bei offensichtlich unvollständiger API-Antwort (lokal 55 Spiele, API 1 Spiel) wird NICHT gelöscht — kein Datenverlust. Normale Purgierung entfernt veraltete Spiele inkl. Tipps+Kommentare.
  - **OpenLigaDB-Fallback:** camelCase UND PascalCase akzeptiert, Endergebnis-Typ (resultTypeID 2) richtig ausgewertet.
  - `store_sync_result` setzt Zeitstempel.
- Teststand: 186 → 194 bestanden.

## 2026-08-31 - Export/PDF testabgesichert (Testdatei test_export_pdf.py)

- **PDF-Saison-Report:** generiert valides PDF (%PDF-Magic, >1 KB) — mit Tipps UND komplett ohne Daten (leere Tabellen bauen nicht ab).
- **Route /export/pdf:** liefert Attachment mit deutschem Dateinamen; ohne reportlab (None-Fall) sauberer Redirect zum Saisonbericht mit Hinweis statt 500.
- **Route /export/csv:** deutscher Header (Spieltag/Datum/Heim/…), Tipp und Ergebnis getrennt, Joker-Spalte; getestet, dass nur der **aktive Wettbewerb** exportiert wird.
- Teststand: 195/195 bestanden.

## 2026-08-31 - Notification Center bulk-optimiert (N+1 beseitigt)

- **Problem:** `send_match_reminders` feuerte pro Spiel und pro Benutzer eigene Queries: 1× Prediction-Check, 4× „schon gesendet?"-Einzelabfragen (E-Mail/Push/Telegram/WhatsApp), 1× `get_setting('public_base_url')`, dazu pro Versand ein eigener Session-Flush. `upcoming_reminder_matches` lud zudem alle Benutzer **einmal pro Spiel** neu, `_next_open_match_for_user` fragte pro Spiel einzeln nach dem eigenen Tipp.
- **Lösung:** Prefetch-Pattern — einmal je Lauf: alle Benutzer (1 Query), Tipp-Set des Spiels (1 Query), kompletter NotificationLog-Prefetch (1 Query), Setting gehoistet (1 Query). In-Memory-Caches: `tipped_user_ids` (Set), `sent_cache` (Tupel-Set), Fenster-`timedelta`-Liste. Am Ende genau **ein** `db.session.flush()`. Öffentliche Funktionen bekamen nur optionale keyword-only Prefetch-Parameter — API bleibt rückwärtskompatibel.
- **Latenter Bug gefixt:** SQLite liefert naive Datetimes zurück; der Fenster-Vergleich in `upcoming_reminder_matches` mit aware-`datetime.now(timezone.utc)` hätte dort einen TypeError geworfen — Kickoffs werden jetzt als UTC normalisiert.
- Neue Testsuite test_notification_bulk.py zählt SQL-Statements per SQLAlchemy-Event: kein N+1 bei ≥11 Benutzern, Zweitlauf sendet nichts mehr, Filterregeln (getippt ⇒ raus, notify_enabled=False ⇒ raus), Stundenfenster, Prefetch-Pfade.
- Teststand: 195 → 200 bestanden.

## 2026-08-31 - Inline-JS/CSS in statische Dateien ausgelagert

- **Ausgelagert (ca. 56 KB):** live.html (10,3 KB → static/js/live.js), match_detail.html (9,7 KB → match_detail.js), quick_tip.html (7,1 KB → quick_tip.js), stats_dashboard.html (4,6 KB → stats_dashboard.js), tip_overview.html (19,5 KB CSS → tip_overview.css; JS → tip_overview.js + konditional geladenes tip_overview_live.js), admin/bots.html (4,4 KB CSS → admin_bots.css).
- **Vorteile:** Browser-Caching mit `?v=asset_version`, kleinere HTML-Antworten, JS syntaktisch mit `node --check` prüfbar.
- **Jinja-Interpolations sauber entkoppelt:** match_detail übergibt die Quick-Tip-Fallback-URL per verstecktem `<span id="md-config" data-quick-tip-url>`; tip_overview übergibt Live-Endpunkt + Sortiermodus per `data-live-url`/`data-sort` am tbody; stats_dashboard bekommt seine 10 Chart-Datensätze als JSON-Insel (`<script type="application/json" id="stats-chart-data">…|tojson</script>`, vom JS geparst). Ausführreihenfolge (z. B. has_live-Gate, DOMContentLoaded-vs.-defer-Timing mit Chart.js) unverändert.
- Verbleibende kleine Inline-Blöcke (<3 KB, gesamt ca. 19 KB) bewusst belassen — geringer Hebel, hohes Jinja-Verknüpfungsrisiko.
- Test test_live_center_uses_polling_not_sse prüft jetzt Script-Einbindung + Polling-Logik in static/js/live.js (war: Inline-String).
- Teststand: 200/200 bestanden.

## 2026-08-31 - Lokale Vereinslogos finalisiert (Testabdeckung Logo-Pflege)

- 4 neue Tests in test_maintenance.py sichern die kritischen Pfade von `ensure_local_team_logos`:
  - **Download-Fehler ⇒ markiertes Fallback-SVG** (`data-generated="wulmstoerper-fallback"`), Zähler `fallback`, DB-Pfad gesetzt.
  - **Gültiges lokales Logo ⇒ Skip**, kein Netzaufruf (AssertionError-Guard), Datei unberührt.
  - **Generiertes Fallback ⇒ ersetzt** bei erfolgreichem Download über bekannte Quell-URL (`_logo_source_map`, Team HSV), Zähler `replaced_fallback` + `downloaded`.
  - **`update_known_team_logos` dreht lokale Logos nicht zurück** auf externe URLs; Gegenprobe: externe URL wird korrekt auf Fix-URL gesetzt.
- Testhygiene: Tests löschen die Team-Tabelle vorher und räumen angelegte Dateien wieder weg (`_LogoCase`-Helfer, `_cleanup`), damit keine Seed-Daten oder eingecheckte Logos angefasst werden.
- Teststand: 204/204 bestanden.

## 2026-08-31 - Smoke-Tests Spieler-Zentralseiten (Testdatei test_player_smoke.py)

- 19 neue Tests: Zentralseiten rendern mit HTTP 200 (Spielplan, Tabelle, Vorschau, Spieltag-Recap, Ewige Tabelle, Spieltagsieger, Meine offenen Tipps, Mehr, Preise — vorher teils ganz ungetestet).
- Asset-Absicherung der Inline-Auslagerung: /schnelltipp, /live, /tipps, /stats referenzieren ihre ausgelagerten JS/CSS-Dateien; match_detail.md liefert den `#md-config`-Konfig-Span; stats_dashboard liefert die JSON-Insel `#stats-chart-data`; admin/bots verlinkt admin_bots.css.
- Teststand: 204 → 223 bestanden (kumuliert mit Audit-Tests unten: 233).

## 2026-08-31 - Activity Log mit before/after-Diffs

- **Neue Helfer:** `audit_log.snapshot_model(obj, attrs)` (modell-agnostisch, Datum → ISO) und `audit_log.diff_snapshots(before, after)` → `{feld: {"from": alt, "to": neu}}`, nur tatsächlich geänderte Felder.
- **`log_admin_action(...)` erweitert:** optionale keyword-only Parameter `before`/`after`; berechneter Diff wird als `diff`-Schlüssel in die Metadaten gelegt (bestehende Metadaten bleiben erhalten; Nicht-Dict-Metadaten werden als `payload` verpackt). Kein Diff = Metadaten unverändert.
- **Verdrahtet:** `user_update` (loggte bisher gar keine Metadaten — jetzt komplette Feld-Diffs inkl. `password_changed`-Flag) und `special_question_edit` (bekam `diff` zusätzlich zum vorhandenen old/new-Payload).
- **UI:** `/admin/activity` zeigt pro Eintrag aufklappbar „Änderungen (n)“ mit alt (rot/durchgestrichen) → neu (grün); Modell-Property `AdminActivityLog.diff` (+ `meta`, geparste Metadaten). Achtung Fallstrick: Property darf nicht `metadata` heißen (überschreibt SQLAlchemy-Base-Attribut → Boot-Crash).
- 10 neue Tests (tests/test_audit_diffs.py): Helper-Units, Diff-Merge-Semantik, beide Routen, UI-Rendering. Teststand: 233/233 bestanden.

## 2026-08-31 - Alembic: bewusst NICHT eingeführt (Architektur-Entscheidung)

- **Begründung:** Auf Netcup/Plesk gibt es keinen Shell-Zugang — Alembics `upgrade head`-Workflow wäre produktiv nicht ausführbar. Gleichzeitig existiert mit `auto_migrate_schema()` (idempotente Spalten beim Boot) + `schema_migrations.py`/`SchemaMigration` (versionierte, admin-auslösbare Schritte mit Erfolg-Tracking, Pending-Erkennung und `/admin/schema`-UI) bereits ein getesteter, zum Hosting passender Mechanismus. Ein zweites System wäre Drift-Risiko und Deploy-Ballast (Vendor-Packaging für Python 3.9).
- Dokumentiert in `docs/MIGRATIONS.md` inklusive Kriterien, ab wann neu bewertet werden sollte (Hosting mit Shell / PostgreSQL / komplexere Migrationen, parallele Entwickler).
- Der interne Mechanismus bleibt **die** Migrations-Source-of-Truth.

## 2026-08-31 - routes_main-Delegation aufgelöst (Lazy-Wrapper komplett abgebaut)

- **Vorher:** `routes_main.py` (484 Zeilen) enthielt neben 7 echten Routen **27 dünne Lazy-Wrapper**, die ihre Logik per Import-in-Function aus Partner-Modulen (`main_tips/stats/pwa/profile/export/telegram_routes`) holten.
- **Nachher:** Die 6 Partner-Module registrieren ihre Routen **direkt auf `main_bp`** (`@main_bp.route(..., endpoint="<alter Name>")` hält alle öffentlichen Endpunktnamen `main.*` exakt), `app.py` importiert die Module direkt nach dem Blueprint-Import. `routes_main.py` schrumpft auf ~310 Zeilen mit nur noch den 7 echten Routen (index, dashboard, invite_users, more, help_rules, tip_entry, test_user_notification) — plus aufgeräumtem Import-Header (56 tote Imports entfernt) und gelöschten, ungenutzten Helfer-Duplikaten `_compute_profile_stats`/`_compute_form_curve` (leben weiterhin in main_profile_routes.py).
- **Spezialfälle gelöst:** two-endpoints-ein-View (`/favicon.ico` via `defaults={"size": 192}` auf `_pwa_icon`), Routing-Parameter-Signaturen bleiben gleich, Methoden unverändert (GET/POST exakt wie vorher), `/telegram/webhook` öffentlich ohne login_required.
- **Bugfix nebenbei:** `/tabelle/<int:matchday>` wurde vom alten Wrapper still ignoriert (`_leaderboard()` ohne Argument) — nach direkter Registrierung greift der Parameter wieder (regressions-abgesichert in test_player_smoke.py).
- Verifikation: kompletter URL-Map-Vergleich (137 Routen, 22 verschobene Endpunktgruppen mit identischen Rules/Methods/Names), kein doppelregistrierter Endpunkt, Undefined-Name-AST-Check sauber. Fallstrick beim Header-Purge erwischt und gefixt: AST-basierte Unused-Namen-Prüfung hat Lambda-Parameter und teils genutzte Namen unterschätzt → danach immer komplette Suite laufen lassen (234/234 bestanden).
- Teststand: 233 → 234 bestanden.

## 2026-08-31 - Fix: Team-Logos nach FTP-Upload kaputt (Test-Fakes im ZIP)

- **Symptom:** Nach jedem Upload der Runtime-ZIP fehlten die Logos von Bayern (fcb.svg), Dortmund (bvb.png), Leverkusen (b04.png) und Leipzig (rbl.png); erst „Logos lokalisieren" im Wartungscenter stellte sie wieder her.
- **Ursachenkette (verifiziert):** Der alte Test `test_ensure_local_team_logos_updates_remote_urls` lief mit `force=True` gegen echte Team-Fixtures und überschrieb dabei die eingecheckten Dateien in `static/team_logos/` mit einem 46-Byte-Platzhalter `<svg…></svg>`. Betroffen genau die vier Teams aus KNOWN_TEAM_LOGO_FIXES, weil dort für FCB die Endung .svg und für BVB/B04/RBL .png zuständig ist. Die kaputten Dateien wurden committed und gingen über das 01-Runtime-ZIP per FTP auf den Server, wo die DB bereits lokale Pfade speicherte → kaputte Logos bis zum manuellen Neu-Download.
- **Fixes:** 1) Neue Fixture `logo_static` in tests/test_maintenance.py leitet `app.static_folder` für alle Logo-Tests nach `tmp_path` um — Tests können das Repo-Verzeichnis gar nicht mehr beschreiben (Beweis: Dateien byte-identisch vor/nach voller Suite). 2) Die vier Originaldateien von den offiziellen Quell-URLs neu geladen (gleiche Quellen wie `_logo_source_map`, damit exakt die Dateien entstehen, die das Wartungscenter erzeugt hätte). 3) Repo-Hygiene-Test: eingecheckte Logos müssen >200 Bytes und valide SVG-/PNG-Signatur haben — Stub-Commits schlagen künftig in der Suite fehl.
- Teststand: 234 → 235 bestanden.

## 2026-08-31 - Workspace neu aufgesetzt & Gesamtstand re-verifiziert

- Frischer Klon von GitHub (Commit `2982653`, 31.08.2026, 18:58 Uhr) in der Sandbox; Venv neu aufgebaut mit psycopg2-gefiltertem requirements (Python 3.13) — wie gehabt ohne psycopg2-binary (PostgreSQL-only, für SQLite-Tests nicht nötig).
- Setup-Skript `setup_sandbox.sh` im Workspace-Root angelegt (außerhalb des Repos): stellt Klon + Venv nach einem Sandbox-Reset mit einem Befehl wieder her.
- Komplette Suite: **235/235 bestanden** (53 s), 4 Warnings (reportlab-Deprecation bekannt, Rest Umgebungsrauschen).
- Coverage neu gemessen: **78 %** (10.618 Statements) — vorher dokumentiert 72 %; Anstieg durch die neuen Suiten (Sync-Mocks, PDF-Export, Notification-Bulk, Player-Smoke, Audit-Diffs).
- Hinweis: `_lieferungen/` (01 Runtime, 02 Doku+Tests) ist nicht auf GitHub eingecheckt und muss nach jedem Klon lokal neu gebaut werden.

## 2026-08-31 - Lieferpakete neu gebaut (01 Runtime, 02 Doku+Tests)

- Neues Dev-Tool `build_lieferungen.py` baut beide ZIPs automatisch aus `git ls-files`: `01_Runtime_<Datum>.zip` (136 Dateien: passenger_wsgi.py, alle Runtime-Module, requirements.txt + requirements_py39.txt, templates/, static/) und `02_Doku_Tests_<Datum>.zip` (52 Dateien: Doku inkl. docs/, tests/, pytest.ini, Dev-Tools inkl. build_lieferungen.py, Docker-Dateien). Jedes ZIP enthält ein MANIFEST.txt mit Build-Datum, Commit und Teststand.
- **Verifikation:** Beide ZIPs in ein leeres Verzeichnis entpackt → komplette Suite läuft dort **235/235 grün**.
- **Bewusst NICHT in 01 enthalten:** `vendor/` (separat via build_vendor.bat), `.env`, `tippspiel.db` (Server-Daten nicht überschreiben), `.htaccess` (nicht im Repo, liegt auf dem Server) sowie **zwei kaputte Avatar-Stubs** (`static/uploads/avatar_1_*.png`, 85 Byte, keine validen PNGs — gleiche Bug-Klasse wie der Logo-Vorfall). Offen: Repo-Cleanup + Avatar-Test-Fixture auf tmp_path umstellen (wie `logo_static`).
- Weiterhin offen: `.github/workflows/tests.yml` ist nicht im Repo (wurde im alten Chat nachgebaut, aber nie auf GitHub hochgeladen).

## 2026-08-31 - Rangliste: Spalte "Quote" eindeutig in "Exaktquote" umbenannt

- Nutzer-Rückfrage: "Quote" war missverständlich (11 % vs. 0 % bei zwei Spielern). Klarstellung per Label statt nur Tooltip:
  - Desktop-Tabellenkopf: `Quote` → `Exaktquote`, Tooltip erweitert ("Exaktquote: Anteil exakter Ergebnistipps an allen beendeten Spielen, zu denen getippt wurde").
  - Mobile Karte: Label `Quote` → `Exaktquote`.
  - Legende: fehlender Eintrag ergänzt — "Exaktquote: exakte Treffer / beendete, getippte Spiele".
- Berechnung unverändert (`scoring.get_leaderboard`): `round(exakt / beendete_getippte * 100)`, sonst 0 — es zählt nur der exakte Ergebnistipp, live/laufende Spiele zählen nicht.
- Test `test_leaderboard_page` (test_routes.py) um 6 Assertions erweitert (positiv: Header/Tooltip/Legende/Mobil-Karte; negativ: alte Labels weg). Teststand bleibt **235/235**.

## 2026-08-31 - Repo-Hygiene & CI: .gitignore, CI-Workflow, Avatar-Stubs entfernt

- **.gitignore angelegt** (fehlte komplett): schuetzt vor Commits von `tippspiel.db` (echte Nutzerdaten: Mails, Passwort-Hashes), `.env`, `instance/`, `.venv/`, `__pycache__/`, `.coverage`/`htmlcov`/`.pytest_cache`, `_lieferungen/`, `vendor/` sowie lokal erzeugten Avataren (`static/uploads/avatar_*.png`). Die eingecheckten PWA-Icons bleiben erlaubt.
- **CI-Workflow `.github/workflows/tests.yml` erstellt** (war im alten Chat nachgebaut, aber nie hochgeladen): Job 1 Flake8 — harter Gate nur auf Syntaxfehler/undefinierte Namen (`E9,F63,F7,F82`, aktuell **0 Befunde**), Rest als reine Statistik (2366 Style-Befunde, kein Fail). Job 2 pytest-Matrix auf Python **3.9–3.13** (3.9 = Netcup-Ziel) mit Coverage aus pytest.ini. Damit faengt CI kuenftig genau die Fehlerklasse ab, die zum Logo-Vorfall fuehrte: lokal gruen, aber Repo kaputt (Stub-Commits).
- **Kaputte Avatar-Stubs entfernt:** `static/uploads/avatar_1_1778599755.png` + `avatar_1_1778599851.png` (85/89 Byte, keine validen PNGs — Test-Fakes einer alten Testversion) per `git rm`. Der aktuelle Avatar-Test schreibt schon laengst nach `tmp_path` (`app.config['UPLOAD_FOLDER']`), es war also reiner Altbestand.
- **Hygiene-Test** `test_eingecheckte_uploads_keine_defekten_platzhalter` (test_avatars_live_push.py): alle eingecheckten Dateien in `static/uploads` muessen echte Bilder sein (>200 B + SVG/PNG-Magic), `avatar_*`-Dateien duerfen gar nicht eingecheckt sein — analog zum Logo-Hygiene-Test.
- `build_lieferungen.py` angepasst: Avatar-Ausschluss entfernt (obsolet), `.github/workflows/` + `.gitignore` wandern in Paket 02, Manifeste aktualisiert.
- Teststand: 235 → **236 bestanden**.

## 2026-08-31 - Fix: Doppel-Saisonlabel auf Rangliste & weiteren Seiten (comp_label nachgerüstet)

- **Symptom (Nutzer-Report nach Deploy):** Rangliste zeigte weiterhin "Bundesliga 2026 · Saison 2026" — obwohl der Saisonlabel-Fix vom selben Tag deployed war.
- **Ursache:** Der Fix hatte nur `base.html` (teilweise), `matchday_preview/recap` und `tip_overview` umgestellt. Sechs Templates konkatenierten Name + Saison weiterhin roh: `leaderboard.html` (Unterzeile der Rangliste — genau die Stelle aus dem Report), `standings.html` (3 Stellen), `stats_dashboard.html`, `special_tips.html`, `admin/dashboard.html` und der season-pill-Tooltip in `base.html`.
- **Zusatzfund:** `standings.html` hatte im `{% block scripts %}` eine verirrte Textzeile (Copy-Paste-Rest aus der Legende) — "Bundesliga 2026 · Saison 2026 · " wurde als nackter Text am Seitenende der Tabelle ausgegeben. Entfernt; der `{% if source == 'football-data.org (live)' %}`-Wächter um das Polling-Script bleibt.
- **Fix:** Alle Stellen nutzen jetzt `comp_label(active_competition_name, active_competition_season)`. Mit Produktiv-Daten (name='Bundesliga 2026', season='2026') zeigt die Rangliste nun "Bundesliga 2026 · Bei Gleichstand: …" (Jahr bleibt im Namen, Saison dedupliziert); die vollständige Namens-Bereinigung passiert beim nächsten Saisonwechsel.
- 2 neue Regressionstests in `test_season_wizard.py`: `test_zentralseiten_kein_doppeltes_saisonlabel` (/tabelle, /bundesliga-tabelle, /stats, /sondertipps — kein Doppel-Label + dedupliziertes Label auf der Rangliste) und `test_admin_dashboard_kein_doppeltes_saisonlabel` (/admin).
- Teststand: 236 → **238 bestanden**.
- Deploy: nur 6 Templates geaendert (leaderboard, standings, stats_dashboard, special_tips, base, admin/dashboard) — im neuen 03-Deploy-Paket enthalten.

## 2026-08-31 - Ewige Tabelle: Legende + Spaltentooltips ergaenzt

- Nutzer-Hinweis: Die Ewige Tabelle nutzte abgekuerzte Spaltenkoepfe (EX, DIF, TEN, ✗, 🏆, "Beste"), erklaerte sie aber nirgends — die Rangliste hat dagegen eine Legende.
- **Legende** unter der Tabelle im Stil der Rangliste (`legend leaderboard-legend`): Saisons = mitgespielte Saisons, 🏆 = Saisonsiege (Rang 1), Beste = beste Platzierung, Exakt/Diff/Tendenz/Falsch wie in der Rangliste, Gesamt = Punkte ueber alle Saisons.
- **Tooltips** auf allen abgekuerzten Desktop-Spaltenkoepfen ergaenzt (gleiche Titel wie die Legende), damit die Erklaerung auch ohne Scrollen verfuegbar ist.
- Regressionstest `test_eternal_table_has_legend` in test_player_smoke.py (Legenden-Eintraege + Tooltip-Attribute).
- Nur `templates/eternal.html` + Test geaendert. Teststand: 238 → **239 bestanden**.

## 2026-08-31 - Fix: YAML-Syntaxfehler im CI-Workflow (erster GitHub-Lauf)

- **Symptom:** GitHub meldete nach dem ersten Push "Invalid workflow file: .github/workflows/tests.yml, error in your yaml syntax on line 18".
- **Ursache:** Step-Name `Harter Gate: Syntaxfehler & undefinierte Namen` war unquotiert — der Doppelpunkt mit Leerzeichen (`: `) beendet in YAML einen Plain-Scalar, der Parser erwartete danach ein neues Schluessel-Wert-Paar.
- **Fix:** Name gequotet (`"Harter Gate: …"`); lokal mit pyyaml verifiziert (Struktur: Jobs lint/test, alle Steps, Matrix 3.9-3.13). Lehre: Workflow-Dateien vor dem Upload immer lokal parsen (pyyaml).
- Teststand unveraendert **239/239** (CI-Datei ist nicht Teil der Suite).

## 2026-08-31 - CI-Fix: Python-3.13-Job (psycopg2-Wheel) + Node.js-20-Warnungen

- **Symptom (GitHub-Actions-Lauf 2):** Python-3.13-Job scheiterte mit exit code 1; dazu 6 Node.js-20-Deprecation-Warnungen (checkout@v4, setup-python@v5) in allen Jobs.
- **Ursache 1 (Error):** `requirements.txt` pinnte `psycopg2-binary==2.9.9` — diese Version hat **keine cp313-Wheels** (PyPI-geprueft); auf dem Python-3.13-Job fiel `pip install -r requirements.txt` auf Source-Build zurueck, der ohne libpq auf dem Runner scheitert. 3.9–3.12 waren nicht betroffen (cp39-cp312-Wheels vorhanden).
- **Fix 1:** `psycopg2-binary==2.9.12` (letzte 2.9.x) — hat cp313-Wheels **und** cp39-manylinux-Wheels (Netcup-Kompatibilitaet bleibt). In der Sandbox auf Python 3.13 installiert + importiert verifiziert (genau der in CI fehlgeschlagene Schritt). `requirements_py39.txt` war nicht betroffen (kein psycopg-Eintrag).
- **Ursache 2 (Warnings):** `actions/checkout@v4` und `actions/setup-python@v5` laufen auf dem seit 2025 deprecated Node.js 20.
- **Fix 2:** `actions/checkout@v5` + `actions/setup-python@v6` (Node.js 24); Workflow lokal mit pyyaml geparst, Job-/Step-Struktur unveraendert.
- Gepruefte Zusatzfakten: Pillow 10.4.0 hat cp313-Wheels; reportlab 4.2.2 ist ein reines Python-Wheel (`py3-none-any`) — beides kein 3.13-Risiko.
- `build_lieferungen.py` baut jetzt auch `04_GitHub_Upload_*.zip` (fest integriert, inkl. Anleitung); `requirements.txt` ist dort enthalten. Manifest-Teststaende auf 239/239 aktualisiert.
- Teststand unveraendert **239/239**.

## 2026-08-31 - CI live: erster kompletter Lauf gruen auf GitHub

- Push via GitHub Desktop in 3 Commits: `2f4d1f8` (Stand 31.08.: Exaktquote, comp_label-Fix, Legende Ewige Tabelle, CI + gitignore), `b77b5d6` (Fix YAML-Syntax im CI-Workflow), `445dcf2` (CI-Fix: psycopg2 2.9.12 fuer Python 3.13 + Actions-Update, 19:47 Uhr).
- **Erster vollstaendiger CI-Lauf gruen:** Flake8-Lint + pytest-Matrix auf Python 3.9/3.10/3.11/3.12/3.13 (6 Jobs) ohne Fehler.
- Damit ist GitHub wieder aktuell: Avatar-Stubs geloescht, `.gitignore` + `.github/workflows/tests.yml` eingecheckt. Die CI wacht ab jetzt bei jedem Push ueber das Repo — sie faengt kuenftig automatisch die Fehlerklassen ab, die zum Logo-Vorfall fuehrten (Stub-Commits, lokal gruen aber Repo kaputt) und prueft die Netcup-Zielversion 3.9 sowie 3.10-3.13.
- `build_lieferungen.py`: Liste `GITHUB_UPLOAD_FILES` geleert — Paket `04_GitHub_Upload` entfaellt automatisch, solange keine offenen GitHub-Aenderungen existieren; beim naechsten lokalen Aenderungsblock einfach wieder befuellen.

## 2026-08-31 - Coverage-Runde: export.py & whatsapp.py auf 100 %

- Neue Suite `tests/test_export_whatsapp_coverage.py` (12 Tests) schliesst die dokumentierten Luecken der beiden zuvor am schlechtesten abgedeckten Module:
  - **export.py (88 % → 100 %):** reportlab-ImportError-Pfad (Rueckgabe None via `builtins.__import__`-Monkeypatch), Rang-Berechnungs-Exception (Report baut trotzdem), MatchdayWinner-Tabelle ("Gewonnene Spieltage" mit Geteilt/Solo), Badge-Sektion ("Erspielte Auszeichnungen"), Vollstaendiger-Name-Zweig.
  - **whatsapp.py (42 % → 100 %):** Eingabe-Guards (leere Nummer/Key/Nachricht → False ohne Request), Ziffern-Normalisierung + URL-Encoding, HTTP-Fehler (200 ohne "Message queued" → False + Warning-Log), RequestException (→ False + Error-Log), Massen-Reminder (nur offene User mit WhatsApp-Konfig, Bots per @bot.local raus, Tipp-Skip, sleep gepatcht), Fehler-Zaehlung, Scheduler-Job (1h-Fenster + stdout-Ausgabe via capsys), Test-Nachricht ohne Konfiguration.
  - Fallstrick dokumentiert: `User` hat kein `is_bot`-Feld — Bot-Erkennung laeuft ausschliesslich ueber die E-Mail-Endung `@bot.local`.
- Gesamtprojekt-Coverage: **78 % → 79 %** (10.917 Statements, 2.345 offen).
- Teststand: 239 → **251 bestanden**.
## 2026-08-31 - Refactoring Prio 7: stats.py & sync.py in Fachmodule aufgeteilt

- **stats.py (630 Zeilen → Kern ~100 + Fassade):** Ausgelagert in `stats_personal.py` (persoenliche Statistiken, 246 Z.), `stats_live.py` (Live-Statistiken, 251 Z.) und `stats_season.py` (Saison-Tabellen/Ewige Tabelle, 143 Z.). `stats.py` bleibt Kernmodul (Misc-Helper, Spieltags-Preview/Recap) und re-exportiert alle Namen der Fachmodule (Fassade), damit saemtliche `from stats import ...`-Aufrufer unveraendert weiterlaufen.
- **sync.py (1348 Zeilen → Kern ~330 + Fassade):** Ausgelagert in `sync_shared.py` (Konstanten, Saisoncode, Team-Aufloesung, Match-Abgleich, store_sync_result, 359 Z.), `sync_football_data.py` (football-data.org-Client inkl. Live-Standings, 267 Z.) und `sync_openligadb.py` (OpenLigaDB-Client inkl. `sync_results`, 365 Z.). `sync.py` behaelt Logos, Seeding, `get_sync_diagnostics` und die Schema-Migration und re-exportiert alle ausgelagerten Namen inkl. `requests`, damit auch Test-Monkeypatches (`monkeypatch.setattr(sync.requests, "get", ...)`, `'sync.requests.get'`) unveraendert greifen.
- Import-Graph azyklisch: `sync_football_data`/`sync_openligadb` → `sync_shared`; `sync_openligadb` → `sync_football_data`. Zirkularitaetsfalle geloest: `_olb_get`/`_olb_team_name` (generische Dict-Helfer) liegen in `sync_shared`, weil die Team-Aufloesung dort sie ebenfalls nutzt.
- Nebenbei: toten `from badges import check_and_award_badges`-Import in `seed_demo_data` entfernt; alle 8 Dateien flake8-clean (F401/F811/F821/E9/F63/F7/F82).
- **Kein einziger bestehender Test musste angepasst werden** — die Fassaden halten alle Importpfade und Monkeypatch-Ziele am Leben. Neu dazu: `tests/test_split_facades.py` (5 Vertragstests) sichert die Re-Exports dauerhaft ab (Namenslisten + Identitaet Fassade→Fachmodul + `sync.requests`-Monkeypatch-Ziel + Azyklik).
- Teststand: 251 → **256 bestanden**. Gesamt-Coverage: **79 %** (unveraendert; die Importkoepfe der neuen Module werden vom Vertragstest abgedeckt).
## 2026-08-31 - Push & Deploy: Stand komplett live

- **GitHub:** 2 Commits per Desktop gepusht — `89486e7` (Coverage-Runde: export.py & whatsapp.py auf 100 %) und `5b2a925` („sync.py/stats.py Aufteilung"). CI-Lauf Nr. 5 zum Push **gruen (6/6 Jobs)** — via GitHub-API verifiziert.
- **Netcup:** `03_Deploy_2026-08-31.zip` hochgeladen + Plesk-Restart durchgefuehrt — Status-Monotonie-Fix (30.08.), Coverage-Runde und Prio-7-Split sind damit produktiv.
- `build_lieferungen.py`: `GITHUB_UPLOAD_FILES` wieder geleert (04 entfaellt, bis der naechste lokale Aenderungsblock ansteht).
## 2026-09-01 - Hilfe: Punktevergabe verstaendlicher erklaert (Unentschieden-Fokus)

- **Problem (Nutzer-Feedback):** Mehrere Tipper verstanden die Punktevergabe bei Unentschieden falsch — der Punktwert fuer „Richtige Tordifferenz" wird bei Remis nie vergeben, was aus dem alten Hilfetext nicht hervorging.
- **`templates/help_rules.html` (Sektion „Punkte"):** Einleitung ergaenzt („genau eine Stufe pro Spiel, nichts wird kombiniert, Joker verdoppelt; Ausgang daneben = 0 Punkte"); alle drei Stufen mit klaren Beispielen; Unentschieden kompakt in den Stufen-Texten erklaert (Remis zaehlt nur als Exakt bei exakter Torzahl — Tipp 1:1 = Ergebnis 1:1 —, sonst als Tendenz — Tipp 1:1, Ergebnis 2:2; die Differenz-Stufe gibt es nur bei Siegen). Joker-Sektion mit Rechenbeispiel. (Auf Nutzerwunsch ohne zusaetzliche Akzent-Box — Erklaerung nur in den bestehenden Stufen-Karten.)
- **Tests:** `test_help_rules_points_section_explains_draw_cases` in `tests/test_routes.py` pinnt die neuen Erklaerungen (7 Marker).
- Teststand: 256 → **257 bestanden**, Coverage **79 %**.
## 2026-09-01 - Netcup: Python 3.9 als feste Rahmenbedingung dokumentiert

- **Rahmenbedingung:** Das Netcup-Webhosting bietet in Plesk aktuell **nur Python 3.9** als waehlbare Version. Die App bleibt deshalb dauerhaft 3.9-kompatibel — ein Hoster-Wechsel der Python-Version ist nicht moeglich.
- **Doku korrigiert** (`DEPLOY_NETCUP.md`, `NETCUP_OHNE_SSH.md`): Beide empfahlen fälschlich Python 3.10/3.11 — jetzt 3.9 als einzige Option, inkl. Hinweis auf EOL-Status (seit Okt. 2025) und die Abfederung durch app-seitige Haertung (Security-Gate, Rate-Limiting, CSRF) sowie vorbereitete Upgrade-Pfade (build_vendor.bat Option [2]/[3], CI-Matrix 3.10-3.13).
- **`requirements.txt`:** Kopfkommentar ergaenzt — alle Pins muessen Python 3.9 unterstuetzen (Netcup-Zielversion, CI testet 3.9).
- **`.github/workflows/tests.yml`:** Matrix-Kommentar praezisiert (3.9 = einzige auf Netcup waehlbare Version).
- Kein Code-Funktionsaenderung — Teststand unveraendert **257/257**, Coverage 79 %.
## 2026-09-01 - Produktions-Absicherung: DB-Backup + Cron-Heartbeat

- **Neues Modul `backup.py`:** erstellt konsistente SQLite-Backups per sqlite3-Backup-API (sicher auch waehrend die App laeuft, kein blosses Datei-Kopieren), schreibt nach `backups/` (Konfig: `BACKUP_DIR`, `BACKUP_KEEP`=14), rotiert alte Dateien automatisch und meldet Fehlerfaelle klar (kein SQLite / Datei fehlt).
- **Neues Modul `cron_heartbeat.py`:** jeder Cron-Lauf (sync/reminder/bots/backup) schreibt Zeitstempel + Status als Setting (`cron_last_run:<task>`). `get_cron_status()` bewertet das Alter je Aufgabe (ok/warn/error/never) — funktioniert mit und ohne App-Kontext.
- **`cron_jobs.py`:** neue Tasks `backup` (taegliches DB-Backup) und `status` (Heartbeat-Ausgabe fuer die Konsole); alle Laeufe laufen durch `_run_task_safe` (Heartbeat ok/fehler, Fehler werden ausgegeben statt still verschluckt); **Cron-Bootstrap** bindet `vendor/` + Plesk-venv selbst ein (gleiche Logik wie `passenger_wsgi.py`) — der Cron laeuft damit unabhaengig davon, ob die Pakete per venv oder vendor/ bereitgestellt werden; Docstring mit den zwei Plesk-Cron-Aufgaben (alle 15 min `all`, taeglich 03:15 `backup`).
- **Admin-Wartungscenter:** neue Karte „Cron & Backup" — Status aller Aufgaben (✅/⚠️/❌/noch nie), Plesk-Einrichtungs-Hinweis solange noch nichts gelaufen ist, Button „Jetzt Backup erstellen" (Route `/admin/maintenance/backup-now`, mit Activity-Log) und Liste der letzten Backups. `run_health_check()` liefert die Daten und warnt bei ueberfaelligem/fehlgeschlagenem Cron. Zusaetzlich zeigt die Karte den **exakten Python-Interpreter-Pfad** (`sys.executable`) samt fertig ausformulierter Cron-Befehle — die App laeuft ja bereits unter genau diesem Interpreter, damit entfaellt die Suche nach dem „Python Interpreter"-Feld in Plesk.
- **`.gitignore`:** `backups/` ergaenzt (Backups nie ins Repo).
- **Doku:** `DEPLOY_NETCUP.md` Schritt 8 komplett neu (zwei Aufgaben mit exakten Feldern, Sofort-Test ueber den ▶-Button + Wartungscenter, Offsite-Hinweis: Backups regelmaessig per FTP herunterladen); `NETCUP_OHNE_SSH.md` um Cron-Abschnitt ergaenzt. **Am 01.09. live ermittelt:** Die App laeuft auf Netcup unter dem System-Python **`/usr/bin/python3`** mit Paketen aus `vendor/` (kein „Python Interpreter"-Feld in Plesk) — die Cron-Befehle nutzen deshalb exakt diesen Interpreter; der Cron-Bootstrap in `cron_jobs.py` bindet `vendor/` selbst ein (lokal end-to-end verifiziert: System-Python ohne Flask + Bootstrap → lauffaehig).
- **Tests:** neue Suite `tests/test_cron_backup.py` (18 Tests: Backup-Konsistenz/Rotation/Fehlerfaelle, Heartbeat-Roundtrip + Alters-Bewertung, Wartungscenter-Anzeige, backup-now-Route, cron_jobs-Dispatch, Cron-Bootstrap) — `backup.py` auf 82 %, `cron_heartbeat.py` auf 91 %, `cron_jobs.py` auf 43 % Coverage (vorher 0 %).
- Teststand: 257 → **275 bestanden**, Coverage **79 %**.

## 2026-09-01 - Cron-Härtung 2: HTTP-Cron für Plesk-chroot (kein Python im Cron)

- **Problem (live auf Netcup ermittelt):** `cron_jobs.py` direkt als Plesk-Aufgabe schlug fehl (`/usr/bin/python3: No such file or directory`) — Netcup führt geplante Aufgaben in einer **chroot-Umgebung ohne Python** aus (im Netcup-Forum dokumentiert). Die App selbst läuft dagegen unter Passenger mit `/usr/bin/python3` + Paketen aus `vendor/`.
- **Lösung:** neue Route **`/cron/run`** (`main_cron_routes.py`, registriert auf `main_bp`): führt sync/reminder/bots/backup/all im App-Kontext aus, schreibt die Heartbeats über `cron_jobs._run_task_safe`, gibt JSON zurück. Schutz per `?key=`-Secret (`hmac.compare_digest`) aus Setting `cron_secret` oder ENV **`CRON_SECRET`** (`.env`) — ohne Secret ist die Route deaktiviert (404), falscher Key → 403, unbekannte Task → 400.
- **Plesk-Aufgaben jetzt per wget:** `*/15 * * * *` → `wget -q -O /dev/null "https://tipp.wulmstorf.net/cron/run?task=all&key=…"`, `15 3 * * *` → `…task=backup&key=…` (PHP-Fallback in der Doku). `cron_jobs.py` bleibt für Umgebungen MIT Python erhalten (Status-Task, Backup, lokale Nutzung).
- **`maintenance.py`/Wartungscenter:** zeigt jetzt den Cron-HTTP-Status (aktiv/deaktiviert), die fertigen wget-Befehle und warnt, wenn `CRON_SECRET` fehlt.
- **Tests:** +6 in `tests/test_cron_backup.py` (Secret-Schutz 404/403/400, backup/all-Ausführung mit Heartbeat, Fehlerfall). Teststand: 275 → **281 bestanden**, Coverage **79 %**.

## 2026-09-01 - README: Badges und Teststand aktualisiert

- **README:** Badges (Tests 134/134 → **281/281**, Coverage 65 % → **79 %**) und Teststand-Textabsatz aktualisiert (Warnings sind jetzt 3 harmlose LegacyAPIWarnings statt der alten reportlab-Warnung).

## 2026-09-01 - Sicherheits-Automatik: Dependabot + pip-audit (Pins auf 3.9-Sicherheitsstand)

- **Ausgangslage:** `pip-audit` meldete 36 Advisories in `requirements.txt` und 47 in `requirements_py39.txt` (Flask, Werkzeug, Jinja2, requests, urllib3, python-dotenv, Pillow, click, idna, pytest, bleach).
- **Pins gehoben — jeweils neueste Python-3.9-taugliche Version** (3.9 = feste Netcup-Vorgabe): Flask 3.0.3→**3.1.3**, Werkzeug 3.0.4→**3.1.7**, Jinja2 3.1.4→**3.1.6** (py39), click→**8.1.8**, blinker→**1.9.0** (für Flask 3.1 nötig), requests→**2.32.5**, urllib3 1.26.20→**2.6.3**, idna→**3.15**, python-dotenv→**1.2.1**, Pillow 10.4.0→**11.3.0**, pytest→**8.4.2**, bleach→**6.2.0**. Alle `requires_python`-Werte per PyPI-Metadaten gegen 3.9 verifiziert; komplette Suite auf neuem Stack grün (281/281, Coverage 79 %).
- **Bewusst ignorierte Rest-Advisories (26 IDs, im CI-Audit dokumentiert):** deren Fix-Versionen verlangen Python ≥ 3.10 (Pillow-Fixes erst ab 12.x, pytest ab 9.0.3, bleach ab 6.4.0, requests ab 2.33.0, urllib3 ab 2.7.0, click ab 8.3.3, python-dotenv ab 1.2.2). Solange Netcup nur 3.9 anbietet, ist das der maximale Stand; bei 3.10+ Liste abbauen und Pins anheben.
- **CI neu:** eigener Job **„Security Audit (pip-audit)"** im Workflow (auditiert `requirements.txt` + `requirements_py39.txt`, Exit ≠ 0 = rot; lokal end-to-end simuliert: „No known vulnerabilities found").
- **Dependabot neu:** `.github/dependabot.yml` — wöchentliche Update-PRs für pip + github-actions, Label `dependencies`. Die CI-Matrix (3.9–3.13) prüft jeden PR automatisch: Updates ohne 3.9-Support werden rot.
- **`requirements_py39.txt`:** Header korrigiert — die Datei IST die gepflegte Netcup-Datei (Option [1] in `build_vendor.bat`), alle Pins aktualisiert.
- **Folgeaktion Netcup:** `vendor/` mit `build_vendor.bat` (Option 1) neu bauen + hochladen + Plesk-Restart — erst dadurch wirken die Sicherheitsfixes in Produktion.

## 2026-09-01 - CI-Härtung: 3.9-Gate für requirements_py39.txt (nach Live-Beobachtung)

- **Live-Beobachtung nach dem Push (`e7f60f6`):** Dependabot sprang sofort an (10 PRs) und die 3.9-Matrix funktionierte wie geplant — `pillow 12.3.0` (#9), `wtforms 3.2.2` (#6), `flask-caching 2.5.0` (#11) fielen exakt am Python-3.9-Job durch. Lücke dabei entdeckt: PRs, die **nur `requirements_py39.txt`** ändern, liefen „blind grün" (die Test-Matrix installiert nur `requirements.txt`).
- **Fix:** neuer Step „Python-3.9-Gate" im 3.9-Job — `pip download -r requirements_py39.txt --no-deps` prüft `requires_python` jedes Pins gegen den echten 3.9-Interpreter und bricht bei unpassendem Pin ab. Lokal in beide Richtungen verifiziert: aktueller Stand grün, injiziertes `click==8.5.0` (braucht ≥3.10) rot („No matching distribution found").
- **GitHub-Stand verifiziert:** main = `e7f60f6` mit dependabot.yml, neuen Pins und Audit-Job; CI-Lauf komplett grün (7/7 inkl. „Security Audit (pip-audit)").

## 2026-09-01 - Dependabot-Runde 1 abgearbeitet (12 PRs verarbeitet, finaler Stack)

- **6 PRs gemergt** (alle via CI verifiziert, inkl. Python-3.9-Matrix und 3.9-Gate): `#1 actions/checkout 5→7`, `#2 actions/setup-python 6→7`, `#4 reportlab 4.2.2→5.0.1` (requires_python `<4,>=3.9` ✓), `#7 MarkupSafe 2.1.5→3.0.3` (nur py39-Datei, ≥3.9 ✓), `#8 email-validator 2.2.0→2.3.0` (≥3.8 ✓), `#10 Werkzeug 3.1.7→3.1.8` (≥3.9 ✓).
- **6 PRs geschlossen** (Updates brauchen Python ≥ 3.10 — korrekt abgelehnt): `#3 zipp 4.1.0`, `#5 click 8.5.0`, `#6 WTForms 3.2.2`, `#9 Pillow 12.3.0`, `#11 flask-caching 2.5.0`, `#12 dnspython 2.8.0`.
- **Live verifiziert:** main = `9bf0825`, CI-Lauf auf main komplett grün (Tests 3.9–3.13, Flake8, Audit, 3.9-Gate); lokaler Workspace auf den finalen Stand synchronisiert — Suite **281/281 grün**, pip-audit auf beiden requirements-Dateien sauber (Exit 0).
- **Netcup:** `vendor/` wurde mit `build_vendor.bat` neu gebaut und per FTP hochgeladen (Nutzer, 01.09.) — die Sicherheitsfixes (Flask 3.1.3, Werkzeug ≥ 3.1.7, Pillow 11.3.0, …) sind damit in Produktion wirksam. Optional: Vendor mit dem finalen Merge-Stand (Werkzeug 3.1.8, email-validator 2.3.0, reportlab 5.0.1) bei Gelegenheit neu bauen — rein inkrementell, nichts Dringendes.
- **Hinweis:** Dependabot legt die 6 abgelehnten Updates wöchentlich neu auf — optional Ignore-Regeln in `.github/dependabot.yml` eintragen (z. B. click ≥ 8.2, Pillow ≥ 12, zipp ≥ 4, dnspython ≥ 2.8, WTForms ≥ 3.2, flask-caching ≥ 2.4 ignorieren, solange Python 3.9 gilt).

## 2026-09-01 - Dependabot-Ignore-Regeln (3.9-Schutz dauerhaft)

- **`.github/dependabot.yml`:** sechs `ignore`-Regeln unter pip, damit die abgelehnten Updates nicht wöchentlich neu aufgelegt werden: `click >= 8.2`, `wtforms >= 3.2`, `pillow >= 12`, `flask-caching >= 2.4` (2.4.0 verlangt ≥3.10, 2.5.0 sogar ≥3.11), `zipp >= 4`, `dnspython >= 2.8`. Kommentar im File dokumentiert die letzten 3.9-tauglichen Versionen und die Bedingung, die Regeln bei einem künftigen Netcup-Python-3.10+ zu entfernen.
- **Nebeneffekt gewollt:** für `dnspython` (2.7.0 geht noch auf 3.9) und `zipp` (3.21.0 geht noch auf 3.9) darf Dependabot die 3.9-kompatiblen Zwischenversionen weiter anbieten — solche PRs sind grün und können bedenkenlos gemergt werden (Grenzen per PyPI-`requires_python` verifiziert).
