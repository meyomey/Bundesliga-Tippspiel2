# Changelog – Wulmstörper Tipprunde










## [3.1.58] - 2026-09-22

### 🎨 App-weite Konsistenz: „heute/morgen" + Tippschluss-Chip überall (Nutzer-Auswahl „beide")

- **„heute/morgen" jetzt auch auf Spielplan + Schnelltipp:** dieselbe Teal-Sprache wie das Dashboard — Spielplan-Datenzeilen und Schnelltipp-Tagesköpfe leuchten an den betreffenden Tagen. Basis bleibt bewusst die **Betrachter-Uhr** (identisch zur Anstoßzeit-Anzeige, Kalendertagvergleich, keine Schätzung).
- **Architektur-Vereinfachung gleich mitgeliefert:** `dash_days.js` initialisiert sich jetzt **selbst** (Browser-Zweig ruft `anwenden()` auf allen `[data-utc]`-Elementen, inklusive MD-Trenner-Chips) — das Dashboard braucht keinen Inline-Wiring-Block mehr, Spielplan/Schnelltipp nur den Include. Eine Verdrahtung statt dreier Kopien.
- **Tippschluss-Chip auf „Offene Tipps":** die fokussierte Liste (`/meine-offenen-tipps`) zeigt pro Karte statt des neutralen „Noch tippen" den Bernstein-Warn-Chip **„Tippschluss"**, wenn Anstoß in **< 24 h** — exakt dieselbe Semantik wie im Dashboard (87). Bewertung über neue `now_utc`-Übergabe (naive UTC passend zur DB).
- **+4 pytest-Tests** (594 gesamt): Include auf beiden Seiten, Selbst-Init-Guard (keine doppelte Verdrahtung im Dashboard-Template), Tippschluss-Chip kurzfristig ja / entspannt nein (Zählung 1), Spielplan-Regression mit Zeitstruktur. Suite **594/594**, Hartgate 0, Coverage **88 %**, Node-Test grün.
- **Deploy:** `main_tips_routes.py` (now_utc), `templates/dashboard.html` (vereinfacht), `templates/schedule.html`, `templates/quick_tip.html`, `templates/my_open_tips.html`, `static/css/style.css`, `static/js/dash_days.js` → FTP → `__pycache__` → Plesk-Restart. Selbstbeweis: am Spieltag leuchten die Datenzeilen auf Spielplan + Schnelltipp teal; kurzfristige offene Karte zeigt „Tippschluss".
## [3.1.57] - 2026-09-22

### ✨ Dashboard: vier kleine Details (Nutzer-Auswahl „alle 4")

- **ST-Kürzel klickbar:** „ST X" in der Trennzeile ist jetzt ein Link zum Schnelltipp des Spieltags (`/tippen/X`) — die Trennzeile navigiert statt nur zu dekorieren.
- **Tippschluss-Chip:** ungetippte Spiele mit Anstoß in **weniger als 24 h** zeigen statt des neutralen „Tippen"-Chips einen dezenten Warn-Chip **„Tippschluss"** (Bernstein im bestehenden Token-Stil). Bewertung in der Vorlage über die neue `now_utc`-Übergabe (bewusst naive UTC, passend zur DB).
- **„noch X offen" im aktuellen Trenner:** nur der aktuelle Spieltag zeigt die **aktionsfähige** Zahl seiner offenen Tipps („1 Tipp offen" / „2 Tipps offen", Bernstein-Chip) — nach dem letzten Tipp verschwindet sie. Anders als die entfernte Spielzahl (86) ist das eine Zahl, auf die man reagieren kann; Quelle ist der existierende `tip_status.open`-Zähler.
- **A11y:** die Trennlinie ist `aria-hidden` — Screenreader lesen „ST 5 aktuell 1 Tipp offen" ohne „Strich"-Rauschen.
- **+4 Tests** (590 gesamt): Klick-Link `/tippen/5`, Tippschluss-Chip nur kurzfristig (5 h ja / 72 h nein), Offen-Zahl nur solange ungetippt, aria-hidden-Zeile. Testfalle bezahlt: `open_md_matches` ist **kein** Template-Parameter — die Zahl kommt über den bestehenden `tip_status.open`. Suite **590/590**, Hartgate 0, Coverage **88 %**, Node-Test grün.
- **Deploy:** `routes_main.py` (now_utc), `templates/dashboard.html`, `static/css/style.css` → FTP → `__pycache__` → Plesk-Restart. Selbstbeweis: kurzfristige ungetippte Partie zeigt „Tippschluss", aktueller ST-Trenner zählt offene Tipps mit.
## [3.1.56] - 2026-09-22

### ✂️ Dashboard: Spielzahl aus den ST-Trennern entfernt (Nutzer-Hinweis)

- **Nutzer-Hinweis:** „9 Spiele braucht man in der Trennzeile nicht, es sind ja immer 9." Richtig — in der Bundesliga hat jeder Spieltag exakt 9 Partien; die Zahl war redundant und im Teilauszug der Liste (wenn Spiele des Tages schon laufen/finisiert sind) sogar missverständlich. **Entfernt** (Template + CSS), der Trenner zeigt jetzt nur: **ST X** · „aktuell"-Chip · „heute"/„morgen"-Chip · Linie.
- **+0 Tests, 2 angepasst:** die Zählungs-Assertions drehen auf Abwesenheit (`md-sep-count` nicht mehr gerendert). Suite **586/586**, Hartgate 0, Coverage **88 %**, Node-Test grün.
- **Deploy:** nur `templates/dashboard.html` + `static/css/style.css` → FTP → `__pycache__` → Plesk-Restart (gleiche 3-Datei-Liste wie (85), falls sowieso zeitnah deployt wird). Selbstbeweis: Trennzeilen ohne Zahl.
## [3.1.55] - 2026-09-22

### 📅 Dashboard: „heute"/„morgen"-Hervorhebung (Nutzerwunsch, Fortsetzung (84))

- **Neu:** in den Spieltags-Trennern erscheint ein **„heute"**-Chip (Teal, gefüllt) bzw. **„morgen"**-Chip (dezent umrandet), sobald die erste Partie der Gruppe auf den entsprechenden Tag fällt; dazu bekommt jedes Match-Datum derselben Tage einen **Teal-Akzent**. Tage ohne Bezug bleiben ohne Chip (kein Ziermüll).
- **Korrekte Uhrzeit-Basis:** die Bewertung passiert **viewer-lokal** — exakt dieselbe Uhr wie die bestehende `data-utc`-Konvertierung der Anstoßzeiten (Abendspiele kurz nach Mitternacht werden also konsistent „morgen" marks, wie der Spieler es sieht). Keine Schätzung, nur ein Kalendertagvergleich (Dauerregel 1). Ohne JavaScript bleibt der Chip leer (graceful).
- **Architektur:** die Logik liegt bewusst im **reinen, DOM-freien Modul `static/js/dash_days.js`** (UMD: Browser `window.DashDays` + Node `module.exports`) und ist damit **in der CI testbar**: neuer Node-Test `tests/js/dash_days_test.js` als zweiter Schritt im CI-Job „JS-Engine-Tests" (Kalendertag-Grenzen, Mitternacht kurz davor/danach, Monatsgrenze 30.09→01.10, Müll-Eingaben → null, nie werfen). Verdrahtung: kleiner Initialisierungsblock im Dashboard-`scripts`-Block (`.match-date` → Klassen `ist-heute`/`ist-morgen`, `.md-sep-when` → Chip-Text + Klasse); CSS-Erweiterungen im bestehenden Token-Stil.
- **+2 pytest-Tests** (586 gesamt) + 11 Node-Assertions: Trenner-Hook mit `data-utc` + Modul-Include gerendert, Quelltext-Kette (Modul/Verdrahtung/CSS/CI). Suite **586/586**, Hartgate 0, Coverage **88 %**, Node-Test grün.
- **Deploy:** `templates/dashboard.html`, `static/css/style.css`, **NEU** `static/js/dash_days.js` (Server-Datei!) → FTP → `__pycache__` → Plesk-Restart. Selbstbeweis: am Spieltag zeigt der ST-Trenner den „heute"-Chip, Spiel-Daten leuchten teal. **Achtung:** der Build heißt wie der (84)-Build `*_2026-09-22.zip` — frisch ziehen, nicht den alten Ordner nehmen!
## [3.1.54] - 2026-09-22

### 📋 Dashboard: Spieltags-Trenner in „Kommende Spiele" (Nutzerwunsch)

- **Bisher:** die Liste war eine lange, flache Kickoff-Reihe — kein erkennbarer Wechsel zwischen den Spieltagen.
- **Jetzt:** vor dem ersten Spiel jedes Spieltags steht eine **Trennzeile** mit dem Kürzel **„ST X"**, einer **Trennlinie** und der Spielzahl („2 Spiele" / korrektes „1 Spiel"). Der aktuell offene Spieltag trägt zusätzlich das Chip **„aktuell"** (Teal, wie die bestehende Overline-Sprache).
- **Umsetzung:** reines Template+CSS (kein Route-/Datenänderung) — Jinja-Namespace-Gruppierung in `templates/dashboard.html`, neue Klassen `.md-sep`/`.md-sep-label`/`.md-sep-now`/`.md-sep-line`/`.md-sep-count` in `static/css/style.css` (Mobile-First, bestehende Design-Tokens). Die Trennzeile ist das neue Selbstbeweis-Element dieser Lieferung (Dauerregel 4).
- **+4 Tests** (584 gesamt): Trennzeilen mit ST 5/ST 6 in richtiger Reihenfolge inkl. „2 Spiele"/„1 Spiel<"-Zählung, „aktuell"-Chip am ersten Trenner, keine Trenner bei leerer Zukunft, Quelltext-Guard. Testfalle (dokumentiert): create_app seedet eine Demo-Saison — Tests pinnen daher `app.config["COMPETITION"]` auf die Test-Competition (Muster aus Runde 79), sonst vermischen sich Seed- und Test-Spiele.
- **Deploy:** nur `templates/dashboard.html` + `static/css/style.css` (beide bereits in der 16er-Liste enthalten) → FTP → `__pycache__` löschen → Plesk-Restart. Selbstbeweis: Dashboard zeigt ab dem nächsten Start die ST-Trennzeilen.
- Suite **584/584**, flake8-Hartgate 0, Coverage **88 %**.
## [3.1.53] - 2026-09-20

### 🛡️ FINISHED-Sanity-Gate: laufende Spiele können nicht mehr fälschlich „ENDE" sein (Produktionsfall 20.09.)

- **Befund (Nutzer-Meldung mit Screenshot):** Paderborn–Hoffenheim lief noch, die App zeigte „✓ ENDE 0:0". Ursache: football-data.org (Primärquelle des 15-Minuten-Syncs) meldete das laufende Spiel als `FINISHED` mit 0:0-Platzhalter — der Sync übernahm das blind, und die Status-Monotonie (Schutz vor Downgrades) machte ein falsches `finished` unheilbar: kein Pfad korrigierte es später. OpenLigaDB hatte derweil korrekt `matchIsFinished=false`.
- **Fix 1 — Sanity-Gate (`sync_football_data.py`):** `FINISHED` wird nur übernommen, wenn die physische Mindestdauer (45+15+45 = **105 min**, `FINISH_SANITY_MIN`) um ist. Darunter: Status wird nicht übernommen — bei vorbei­gehendem Anstoß gilt der harte Fakt „live" (Anpfiff ist Fakt, keine Schätzung), nie wird ein Score/Minute erfunden. Zähler landen sichtbar in der Sync-Zeile („🛡️ n vorzeitige FINISHED abgewiesen").
- **Fix 2 — Notfall-Rücknahme:** ein bereits fälschlich `finished` geglaubtes **0:0** wird im Sync mit OLB-Gegenprobe zurückgenommen (OLB erreichbar **und** `matchIsFinished=false` → `allow_status_reset` auf live). Bei unklarer OLB-Lage wird **nie** gehandelt (nie still falsch). Legitime 0:0-Endstände (z. B. Schalke–Elversberg) bleiben unangetastet: Floor vorbei bzw. OLB bestätigt fertig.
- **Fix 3 — OLB-Endstand heilt (`sync_openligadb.py`):** der bestehende OLB-Nachzug korrigiert jetzt auch vorzeitige 0:0 der letzten 5 Tage mit dem echten Endstand (`finished→finished`-Score-Korrektur, mit Recalc + Badges). Damit heilt die App jede eventuelle Restwrongheit spätestens beim Abpfiff selbst.
- **Robustheit:** `_olb_group_order_id` akzeptiert neben dem verschachtelten Gruppenfeld (`group.groupOrderID`) auch das flache Format (OLB wechselt je Endpunkt das Schema).
- **+11 Tests** (580 gesamt, Coverage **88 %**): vorzeitiges FINISHED → live, vor Anstoß → bleibt geplant, nach Mindestdauer → wird übernommen, falsch-fertig 0:0 + OLB läuft → zurückgenommen, OLB unklar → nie handeln, OLB-Endstand korrigiert 0:0, legitimes 0:0 bleibt, OLB-Gruppenfeld flach/verschachtelt. Bestandstest `test_live_minutes` auf Floor-Anstoß angepasst (künstlich komprimierte Zeitachse). Suite **580/580**, flake8-Hartgate 0, Coverage **88 %**.
- **Build-Hygiene:** die beiden sync-Dateien standen bereits seit früheren Runden in der GitHub-Upload-Liste und waren in (83) versehentlich doppelt ergänzt worden (identischer Zip-Inhalt, doppelte Einträge im 04-Paket). Behoben + **Duplikat-Schutz** in `build_lieferungen.py` (Liste wird automatisch entdoppelt, Reihenfolge bleibt) — 04-Paket jetzt **96 Dateien**, keine Doppler mehr.
- **Nachschärfung (gleicher Tag, Produktionsverlauf):** der Live-Boost hatte das falsche 0:0 zwischenzeitlich selbst auf 2:0 geheilt — nur der Status hing noch auf `finished`. Die Rücknahme wirkt deshalb jetzt **unabhängig vom Score**: OLB erreichbar + Paarung/Anstoß eindeutig + `matchIsFinished=false` + Mindestdauer verletzt → zurück auf live (egal ob 0:0 oder 2:0), auch wenn die Quelle `IN_PLAY` meldet statt `FINISHED`. Zudem `_OLB_TEAM_MAP` um **SV 07 Elversberg → ELV** ergänzt (Paderborn war schon drin) — ohne den Eintrag bliebe die Gegenprobe für genau die Aufsteiger stumm.
- **Deploy:** geändert: `sync_football_data.py`, `sync_openligadb.py`, `tests/test_live_minutes.py` (+ neu `tests/test_sync_finish_guard.py`, nur GitHub) → FTP → `__pycache__` → Plesk-Restart. **Selbstheilung:** beim ersten Sync nach dem Deploy springt ein noch laufendes falsch-„fertiges" Spiel zurück auf LIVE; hat es bereits geendet, überschreibt der echte Endstand das 0:0 automatisch. Kein manueller DB-Eingriff nötig.
## [3.1.52] - 2026-09-20

### 🧪 Robustheitstests + 💾 Backup-Restore-Drill (Nutzer-Auswahl „5 und 6")

- **Kandidat 5 — Robustheitstests für die schwächsten Module** (+33 Tests, Coverage **86 → 87 %**): `telegram_bot.py` **44 → 89 %** (Token-Fehlerpfade, alle /tipp-Fehleingaben, Aktualisieren statt Duplizieren, Joker-Umzug im Spieltag, Rangliste/Spielplan/Meine-Tipps, Dispatch, Versand ohne Token/Netzwerkfehler/Erfolg, notify-Filter), `live_scoring.py` **53 → 87 %** (kaputtes Events-JSON, scheduled→live, Abschluss mit echter Punkteberechnung, Tipp-Verteilung/Top-Tipps, alle /live-Routen mit Rollenschutz), `admin_bots_routes.py` **32 → 77 %** (Rollenschutz, Toggle-Setting, unbekannte Bot-IDs, Reset-Loeschung, Bot-Anlage/Duplikat, tip-all ohne aktive Bots).
- **Echter Bugfix dabei:** die beiden Live-Admin-Endpoints nutzten `request.get_json()` **ohne** `silent=True` — Form-POSTs (z. B. aus dem Admin-Manuell-Update) brachen mit **415 Unsupported Media Type**, statt die Formularwerte zu lesen. Jetzt `get_json(silent=True) or request.form` (JSON und Form gehen beides).
- **Kandidat 6 — Backup-Restore-Drill als CI-Test** (`tests/test_backup_restore_drill.py`): ein Backup gilt erst dann als Backup, wenn ein Restore geuebt ist. Der Ernstfall laeuft jetzt automatisiert auf echter SQLite-**Datei** (wie Netcup): Seed → `create_database_backup()` → **kompletter Datenverlust** (alle Zeilen weg) → Backup-Datei zurueckkopieren (Praxis: FTP) → Verifikation (Spieler + Passwort-Check, Tipp mit 4 Punkten, Spielstand, `PRAGMA integrity_check` = ok) — plus **point-in-time-Drill**: zwei Backup-Zeitpunkte, gezielt der AELTERE wird restauriert. Wichtige Erkenntnis, jetzt dokumentiert: der Cron-**Heartbeat steht nicht im Backup** (er schlaegt erst nach der Kopie in die Live-DB) — direkt nach einem Restore zeigt das Wartungscenter therefore korrekt `never`, bis das naechste naechtliche Backup gelaufen ist.
- **+35 Tests** (569 gesamt): 16 Telegram + 10 Live-Scoring + 7 Bots + 2 Restore-Drill. Suite **569/569**, flake8-Hartgate 0, Coverage **87 %**.
- **Testfallen bezahlt (dokumentiert):** die session-scoped `app`-Fixture erzeugt in verschachtelten App-Contexts **getrennte Sessions** (Objekte nach Job-Context neu holen statt `expire`); der Login-View short-circuitet bei eingeloggt → Rollenwechsel in Tests nur ueber **ein** Client + `/auth/logout`; Backup-Dateinamen haben Sekunden-Stempel → zwischen zwei Backups ≥1 s Abstand.
- **Deploy:** nur geaenderte Datei `live_scoring.py` + neue Testdateien (`tests/test_telegram_robust.py`, `tests/test_live_scoring_robust.py`, `tests/test_admin_bots_robust.py`, `tests/test_backup_restore_drill.py`, nur GitHub/CI) → FTP → `__pycache__` → Plesk-Restart. Selbstbeweis: Live-Admin-Update per Formular funktioniert wieder (vorher 415); Rest des Runden-Contents ist test-only.
## [3.1.51] - 2026-09-20

### 🛡️ Betrieb & Grundhärtung: /healthz, Sicherheits-Header, deutsche Fehlerseiten, „Quoten sind da"-Push (Nutzer-Auswahl „Paket 1+2+3+4")

- **Anlass:** Nutzerfrage „kann man am Bestand noch etwas verbessern?" → Bestandsaufnahme (Limiter aktiv, Indizes ok, Deps gepinnt) → vier kleine Lücken geschlossen, alles Nutzer-freundlich ohne Feature-Risiko.
- **Session-Cookies gehärtet (`config.py`):** `SESSION_COOKIE_HTTPONLY=True` und `SESSION_COOKIE_SAMESITE="Lax"` immer; `SESSION_COOKIE_SECURE` automatisch an, sobald `PUBLIC_BASE_URL` mit `https://` gesetzt ist (Prod), alternativ per `COOKIE_SECURE=1` erzwingbar — lokal/Tests (http) bleiben ohne Secure, sonst würde die Session fehlen.
- **Sicherheits-Header (`app.py`, after_request):** `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin` auf **jeder** Antwort.
- **Neu `/healthz`:** öffentlicher Betriebs-Check ohne personenbezogene Daten — `200 {"status":"ok","db":true,"time":…}` bzw. **503 `db:false`** bei DB-Ausfall (ehrlich melden statt grün lügen). Für Plesk/uptime-Monitoring und als Schnellcheck nach dem Deploy.
- **Deutsche Fehlerseiten:** 404 („Diese Seite existiert nicht (mehr)") und 500 („Hier ist etwas geklemmt") als Mobile-First-Standalone-Seiten statt Flasks Englisch-Defaults; **API-Pfade (`/api/…`) bekommen maschinenlesbares JSON** (`error: not_found`/`server_error`), der 500-Renderer ist selbst robust (Fallback-Text, falls das Rendering klemmt). **NEUE Dateien:** `templates/errors/404.html` + `templates/errors/500.html` — beim Deploy den Ordner `templates/errors/` auf dem Server anlegen!
- **Neu „📥 Quoten sind da"-Push (`scheduler.py`):** positives Gegenstück zur 48-h-Erinnerung — sobald für den nächsten Spieltag Stände existieren, bekommt jeder Telegram-Admin **einmalig** eine Info (Anzahl Partien + Anstoß; Dedupe im Setting `odds_arrival_sent`). Gleicher Schalter `odds_reminder_enabled` für beide Richtungen; ohne Stände still, Telegram-Fehler still (Dauerregel 2). Der Plesk-Cron-Task `odds` erledigt jetzt beide Richtungen in einem Lauf.
- **+11 Tests** (534 gesamt, Coverage **86 %**): healthz ok/503, Header, Cookie-Härtung (HttpOnly/SameSite immer, Secure bewusst nur https), 404/500 deutsch + API-JSON, Arrival sendet-einmal/ohne-Stände-still/deaktiviert-still. Testfalle bezahlt: die session-scoped `app`-Fixture ist nach dem ersten Request für neue Routen gesperrt (Flask 3) — 500er-Tests patchen daher bestehende Views (`view_functions["healthz"]`, `view_functions["api.api_matches"]`) statt Routen zu registrieren.
- **Deploy:** `app.py`, `config.py`, `scheduler.py`, `cron_jobs.py` geändert + **NEU** `templates/errors/404.html`, `templates/errors/500.html` (Ordner anlegen!) + `tests/test_health_errors.py` (neu, nur GitHub) → FTP → `__pycache__` löschen → Plesk-Restart. Selbstbeweise: `/healthz` zeigt grün; unbekannte URL zeigt die deutsche 404; Antwort-Header via Browser-DevTools sichtbar; erste geladene Quoten lösen genau eine 📥-Nachricht aus.
## [3.1.50] - 2026-09-20

### 📲 Quoten-Erinnerung per Telegram (48-h-Fenster, Admin-only)

- **Neu:** der Scheduler prüft stündlich, ob das **nächste geplante Spiel des laufenden Wettbewerbs innerhalb von 48 Stunden** anstößt (`ODDS_REMINDER_WINDOW_H = 48`). Trifft das zu **und** es liegen für diesen Spieltag noch keine Quoten-Stände vor, bekommen alle **Telegram-Admins** (`phone` beginnt mit `tg:`) eine kurze Info mit Spieltag, Paarung und Anstoßzeit plus direktem Link zur Optimizer-Quoten-Seite („Quoten online laden").
- **Einmal je Spieltag:** der Versand wird im Setting `odds_reminder_sent` (Spieltag + Wettbewerb + Zeitstempel) gemerkt — keine Wiederholung, auch nicht nach Scheduler-Neustart. Ein späterer Snapshot hat Vorrang vor dem Dedupe („Stände da → nichts zu tun").
- **Stille Ausnahmen (Dauerregel 2):** ohne `the_odds_api_key` (ℹ️, nie ⚠️) oder bei `odds_reminder_enabled = false` tut der Job nichts. Telegram-Fehler werden still geschluckt, ein Catch-all verhindert Scheduler-Ausfälle.
- **Bedienung:** läuft automatisch im Dauer-Scheduler (Stunden-Intervall); für Plesk-Cron gibt es den neuen Task **`odds`** (`cron_jobs.py run_odds_reminder()`, Usage `[sync|reminder|bots|odds|backup|status|all]`), z. B. stündlich per wget — parallel zum Scheduler harmlos (Snapshot-Check + Dedupe).
- **+5 Tests** (523 gesamt): Versand ins Fenster + Dedupe (zwei Läufe → eine Nachricht), Stumm bei vorhandenen Ständen, Stumm ohne Key/deaktiviert, Stumm außerhalb des Fensters, Cron-Task ruft Scheduler-Job. Suite **523/523**, flake8-Hartgate 0, Coverage **85 %**.
- **Deploy:** Dateien nur geändert (keine neuen): `scheduler.py`, `cron_jobs.py`, `tests/test_scheduler.py` → FTP → `__pycache__` löschen → Plesk-Restart. Selbstbeweis: 48 h vor dem nächsten Spieltag erscheint die Telegram-Info einmalig bei den Admins; wer Stände lädt, bekommt sie nicht mehr. Spieler sehen von allem nichts. **Build-Hinweis:** `scheduler.py` hängt seit je in der Dev-/Standalone-Klasse (`DEV_PY`) und fehlte deshalb im 04-GitHub-Paket — für die neuen CI-Tests ist er jetzt explizit in `GITHUB_UPLOAD_FILES` aufgenommen (`build_lieferungen.py`), 04-Paket damit **87 Dateien** (plus Upload-Anleitung).

## [3.1.49] - 2026-09-20

### 🤖 Optimizer als Mitspieler (Admin-Rückblick „Hätte der Optimizer gewonnen?")

- **Neu:** die Optimizer-Admin-Seite zeigt eine neue Karte **„🤖 Optimizer als Mitspieler"** (über „📊 Quoten-Bewegung"): je abgelaufenem Spieltag wird der jeweils **neueste Optimizer-Lauf** ausgewertet (`evaluate_run_tips` → erwartete Punkte pro Tipp), daraus ein virtueller Mitspieler gebaut — Summe der Erwartungswerte (`opt_pts`) und die **Joker-Simulation** (Joker = doppelter `tip_points` auf dem Tipp mit der höchsten EP, Fallback: höchste Basis-Punkte).
- **Reale Rangfolge:** der virtuelle Mitspieler wird in die echte Tipprunde einsortiert — reale Punkte pro Spieltag aus `Prediction`×`Match` (nur beendete Spiele des Wettbewerbs, gruppiert je User), Platz = 1 + Anzahl der User mit mehr Punkten; daneben die Punktedifferenz zum besten echten Spieler. Kumuliert über die Saison: Ø erwartete Punkte/Journey, Joker-Summe, kumulierter Platz (von n).
- **Fairness/Grenzen:** nur **beendete** Spiele fließen ein (läuft ein Run-Spiel noch, bleibt die Auswertung leer), je Spieltag zählt nur der neueste Lauf (spätere Neuläufe überschreiben), Anbieter-EP und echte Tipp-Punkte nutzen dieselbe Punkteregel. Wie gehabt: **Optimizer-Daten sind nie für Spieler sichtbar** — die Karte existiert nur in der Admin-Ansicht (Produktentscheidung Runde 55).
- **+4 Tests** (519 → 523): Mitspieler-Rang/Joker/Kumulus (eigene Testdaten, 0:0 exakt = 4 Punkte), nur-neuester-Lauf je Spieltag, Karte leer/mit Daten, Quelltext-Guards. Hilfs-Query auf die aktive Competition gepinnt (`app.config["COMPETITION"]`).

## [3.1.48] - 2026-09-20

### 🏅 Karriere-Badges gelten ab jetzt pro laufender Saison (Nutzer-Anforderung)

- **Frage (Nutzer):** „Karriere-Badges sollen als Standard immer nur für die laufende Saison gelten. Ist das so eingerichtet?" — **Befund: Nein.** `first_tip`, `tips_count`, `total_points`, `exact_count` und `joker_exact` zählten saisonübergreifend alle Tipps ever (nur `matchday_winner` war Saison-scoped, `perfect_day` wettbewerbs-scoped). Ein Saison-Bezug war nur indirekt über den Saisonwechsel-Assistenten denkbar („Spielplan löschen" entfernt alte Tipps, „Badges zurücksetzen" löscht alle UserBadges).
- **Jetzt als Standard:** alle Karriere-Trigger zählen nur noch Tipps, deren **Anstoß in der laufenden Saison** liegt. Saison-Anker ist das Setting `current_season` (vom Saisonwechsel-Assistenten gesetzt), Rückgriff `Competition.season`; Intervall aus dem Label („2026/27" → 1.7.2026–30.6.2027, auch „2025/2026" lesbar). **Fehlertoleranz:** ohne auswertbares Label ist der Filter inaktiv und es zählt weiter alles (nie still falsch — ℹ️-Prinzip). `matchday_winner`/`perfect_day` bleiben wie gehabt, `perfect_day`-Kandidaten sind jetzt zusätzlich saison-gefiltert.
- **Wirkung mit dem Wartungslauf:** `revalidate_badges()` (Admin → Wartung → „badges") **widerruft jetzt Karriere-Badges, die nur auf Vorsaison-Zählungen beruhen** — nach dem Deploy einmal auslösen, das ist der gewollte Saison-Schnitt. Seeding-Texte der Karriere-Badges sagen jetzt „in der Saison" (Bestand-DBs: Admin → Badges → Beschreibung manuell anpassen, wie bei „Perfekter Tag").
- **+4 Tests** (514 gesamt): Intervall-Parsing inkl. Fehlertoleranz, Karriere-Scope (10 exakte in der Vorsaison → kein Scharfschütze; ein Saison-Tipp → Tipp-Premiere; Archiv-Blick zurück zählt wieder), Revalidate-Widerruf nach Saisonwechsel, Seed-Texte. Bestehende Badge-Tests auf die laufende Saison gepinnt (autouse-Fixture `current_season = 2026/27` in den drei Badge-Testdateien; MatchdayWinner-Labels entsprechend). Suite **514/514**, flake8-Hartgate 0, Coverage **85 %**.
- **Deploy:** keine neuen Dateien — 16er-Liste bleibt (frischer Inhalt: `badges.py`, `tests/test_badge_*.py`) → FTP → `__pycache__` löschen → Plesk-Restart → **einmal Wartung → „badges"** (Saison-Schnitt). Selbstbeweis: ein Spieler, dessen Scharfschützen-Zählung überwiegend aus der Vorsaison stammt, verliert das Badge beim Wartungslauf; neue Tipps der laufenden Saison zählen wieder hoch.

## [3.1.47] - 2026-09-20

### 🕓 Quoten-Laden: angepfiffene Spiele sauber gemeldet (Nutzer-Fund ST4 „plötzlich nur noch 3/9")

- **Meldung (Nutzer, Screenshot ST4):** Statuszeile „✓ 3/9 Spiele mit Quoten befüllt … Nicht zugeordnet (Name): …" für 6 Spiele — obwohl die Namenszuordnung in Ordnung war.
- **Ursache (datenbasiert, kein Bug im Laden):** die The-Odds-API listet **nur zukünftige Spiele** — beendete/angefangene fallen aus der Antwort. Beim letzten Laden (Do, 17.09.) waren alle 9 Spiele des ST4 zukünftig (9/9 ✓); beim Laden am So, 20.09. (14:04) waren die Fr/SA-Partien (u. a. HSV–Köln, Gladbach–Mainz, Werder–Augsburg, Frankfurt–Freiburg, Stuttgart–Dortmund) bereits gespielt, nur die So-Partien (Leverkusen–Leipzig, Schalke–Elversberg, Paderborn–Hoffenheim) lagen noch vorne → genau die 3 bekamen Quoten. Die Meldung „Nicht zugeordnet (Name)" war für diesen Fall irreführend.
- **Fix (Transparenz, Dauerregel 2):** die JS klassifiziert leere Karten jetzt über `data-kick`: **„Bereits angepfiffen/beendet — die Odds-API listet nur zukünftige Spiele: …"** (Karte mit Anstoß ≤ jetzt) getrennt von **„Nicht zugeordnet (Name): …"** (zukünftige Spiele, (61)-Klasse). Zusätzlich zeigt die Meldung das **tatsächliche API-Angebot** („API-Angebot (zukünftige Spiele): …", neues Antwortfeld `event_pairs`/`event_count`) — sichtbar statt geraten.
- **Beiher fix:** `DE_NAMES` mappte Gladbach auf „Bor. Mönchengladbach", der DB-Name lautet aber „Borussia Mönchengladbach" (gleiche Falle wie Elversberg in (61); `namesMatch` fing es ab, der Exakt-Pfad nicht) → Mapping korrigiert + Kürzel-Form ergänzt.
- **+3 Tests** (510 gesamt): Gladbach-Mapping auf DB-Namen, Endpunkt liefert `event_pairs`, JS-Guard für die getrennte Meldung. Suite **510/510**, flake8-Hartgate 0, Coverage **85 %**.
- **Deploy:** keine neuen Dateien — die 16er-Liste bleibt (frischer Inhalt: `admin_tip_optimizer_routes.py`, `static/js/tip_optimizer.js`, `tests/test_tip_optimizer.py`) → FTP → `__pycache__` löschen → Plesk-Restart. Selbstbeweis: „Quoten online laden" an einem laufenden Spieltag meldet die vergangenen Partien mit obigem Wortlaut + zeigt das API-Angebot; an einem zukünftigen Spieltag bleibt es bei ✓ 9/9.

## [3.1.46] - 2026-09-20

### 📈 Tipp-Optimizer: Backtest mit Odds-Anker + Kalibrierungs-/Trend-Karte

- **Der vereinbarte Schritt (seit 16.09.):** solange 2–3 Spieltage mit „⬇ Quoten online laden“ + „💾 Vorhersage speichern“ gesammelt sind, misst der Optimizer jetzt die **echte Tipp-Qualität der Live-Pipeline** — nicht mehr nur die Blind-Untergrenze.
- **① Backtest mit Odds-Anker** (Erweiterung der Backtest-Karte, selbster Endpunkt): für jeden abgeschlossenen Spieltag **mit gespeicherten Quoten-Ständen** (`odds_snapshots`, erster/ältester Stand je Spiel) wird die Live-Pipeline nachgebaut — faire 1X2-Ziele per Power-Margen-Entfernung (`de_margin`), λ-Fit gegen die Ziele mit weichem Teamstärken-Anker W = 0,15 + vorhandenen Zusatzmärkten Ü2,5/BTTS (`fit_lambdas_odds` — 1:1-Port von `TOEngine.deMargin`/`fitLambdas`, O(N)-Schnellform der Matrix-Statistik mit Poisson-lru_cache statt O(N²) pro Grid-Punkt). Daneben laufen die **Blind-Kennzahlen derselben Spiele** (faire Paarbildung): EP/Spiel, 1X2-Treffer, Brier — als „blind → Anker“-Vergleich je Spieltag + Summenzeile. Spiele ohne Snapshot bleiben unbewertet (nichts geraten). Der Blind-Backtest selbst ist unverändert (Untergrenze).
- **② Karte „🎚 Kalibrierung & Trend“** (servergerendert, nach der Modellgüte-Karte): je abgerechnetem Spieltag der letzte gespeicherte Lauf (keine Doppelzählung) → **Σ P(1)/P(X)/P(2) prognostiziert vs. reale Ergebnishäufigkeiten** mit Stufen-Urteil (max. Abweichung ≤ 5 % „gut kalibriert“, ≤ 12 % „akzeptabel“, sonst „prüfen“), **P(1)-Zuverlässigkeits-Buckets** (Ø Prognose vs. reale Heimsiegquote je Bereich) und **EP-Trend je Spieltag** (erwartet vs. real mit Mini-Balken `.to-bar`, P(≥2 P) e/r, Brier). Kleine Stichproben (< 30 Spiele) werden als Richtwerte gekennzeichnet; ohne Daten ℹ️-Hinweis (nie ⚠).
- **Neu:** `tip_optimizer_model.py`: `_matrix_stats_fast`, `de_margin`, `fit_lambdas_odds`, `PRIOR_WEIGHT=0.15`, `calibration_summary`, `backtest_odds_anchored` (+ `_poisson_vec_cached`, lru 8192). Routes: `_kalibrierung_stats()`, Backtest-Endpunkt liefert `anchored`-Sektion (None ohne Snapshots). Template/CSS/JS: Kalibrierungs-Karte, Balken-Visual (inkl. 640-px-Kompaktform), Anker-Block im Backtest-Render.
- **+8 Tests** (508 gesamt): Schnellform exakt gegen `build_matrix` (1e-12), Power-/Prop-Margin, Solver trifft Ziele (ohne Prior eng, mit Prior messtbar weich — (57)-Verhalten), Anker-Backtest mit ergebnisgerechten Quoten (schlägt blind, Lücken-Spiel bleibt unbewertet), Endpunkt `anchored`-Feld, Kalibrierungs-Stufen/Buckets exakt, Karte leer/mit Daten, Quelltext-Guards. Suite **508/508**, flake8-Hartgate 0, Coverage **85 %**. `verify_04.py` grün, SHA-Baumcheck identisch.
- **Deploy:** keine neuen Dateien — die **16-Datei-Liste aus (62)** deckt alles ab (Inhalt frischer: `admin_tip_optimizer_routes.py`, `tip_optimizer_model.py`, `static/js/tip_optimizer.js`, `static/css/style.css`, `templates/admin/tip_optimizer.html`, `tests/test_tip_optimizer.py`) → FTP → `__pycache__` löschen → Plesk-Restart. Selbstbeweis: Backtest-Button zeigt bei vorhandenen Snapshots den „🎯 Mit Odds-Anker“-Block; die Kalibrierungs-Karte füllt sich nach dem nächsten abgerechneten Spieltag automatisch.

## [3.1.45] - 2026-09-20

### 🧪 Badge-Vollabdeckung: 22 neue Tests über alle Badge-Logiken

- **Anlass:** eigene Testrunde „alle Badge-Logiken" nach (73)/(74). Die 9 vorhandenen Badge-Tests deckten die neuen Fix-Stellen, aber längst nicht alle 13 Badge-Definitionen ab.
- **Neu in `tests/test_badge_vollabdeckung.py` (+22):**
  - *Basis:* `classify_prediction` alle 5 Fälle (exact/diff/tendency/wrong/pending bei live) und `calculate_points` 4/3/2/0 mit Joker×2 bei **joker-unabhängiger** Klassifikation.
  - *`recompute_matchday_winners`:* eindeutiger Sieger mit korrektem `points`/`exact_count`/`season`/`competition_id`; Punktgleichstand → `is_shared` mit 2 Zeilen; nur 0 Punkte → kein Sieger; Spieltag ohne Tipps → kein Sieger; **veraltete Zeilen (inkl. falscher Spieltage) werden ersetzt**.
  - *Trigger-Grenzfälle:* `first_tip`; `tips_count` (29→30); `total_points` (96→100); `exact_count` (9 exakt + diff zählt nicht → 10 mit Joker-Exakt); `joker_exact` (exakt ohne Joker → nein, Joker daneben → nein, Joker+exakt → ja); `perfect_day` (Joker-Exakt zählt, unvollständig getippt → nein, perfekt im **fremden Wettbewerb** → nein); `matchday_winner` (**Saison-Scope**: alte Saison zählt nicht; `md_winner_3`-Schwelle inkl. geteilter Siege; geteilter Sieg zählt voll).
  - *Mechanik:* `award_badge` idempotent / `revoke_badge`; **manuelle Badges** werden nie automatisch vergeben und von `revalidate_badges()` nie angetastet; Revalidierung **verleiht fehlende UND widerruft nicht mehr verdiente** (Ergebniskorrektur-Szenario); `check_and_award_badges(users=[…])` prüft nur die gegebene Liste.
- **Ergebnis:** Suite **500/500**, flake8-Hartgate 0, Coverage **85 %**. README-Testbadge nachgezogen (statisch stand noch 433/433 aus (55)). `verify_04.py` grün (Frisch-Klon + Overlay = 500/500), SHA-Baumcheck identisch.
- **Folgeaktion Nutzer:** ① 04-Paket (86 Dateien, kumulativ (53)–(75)) per GitHub Desktop pushen. ② Netcup-Deploy der **21 Dateien aus (74)** (der neue Test ist rein testseitig, kein Bestandteil des Runtime-Deploys) → Plesk-Restart → Wartung **„matchday_winners"** + **„badges"** → Badge **„Tagessieger" in „Perfekter Tag" umbenennen** (Schritt-für-Schritt: Deploy-Checkliste 20.09.).

## [3.1.44] - 2026-09-20

### 🏅 Badge-Fixes (Admin-Fund): „Tagessieger“/„Spieltagssieger“ trotz 0 Siegen

- **Meldung (Admin/Profil):** Badge „Tagessieger“ (Beschreibung „Alle Spiele eines Spieltags exakt“) und „Spieltagssieger“, obwohl das Profil 0 Spieltagssiege zeigt.
- **Was die Badges eigentlich heißen:** „Tagessieger“ = `perfect_day` (ein Spieltag, an dem **alle** Spiele exakt getippt wurden) — **nicht** ein gewonnener Spieltag. Das echte Sieg-Badge heißt „Spieltagsieger“ (`matchday_winner`). Die Namen waren verwechselbar → Seed-Umbenennung auf **„Perfekter Tag“** (neue DBs; Produktion: Admin → Badges → Name ändern).
- **Ursachen der Fehlzuteilung + Fixes:**
  1. `perfect_day` wertete **partielle Spieltage** ab: wenn erst 2 von 9 Spielen abgerechnet waren und der Tipper darauf 2 exakte Treffer hatte, galt der Spieltag als „perfekt“. Jetzt zählt nur ein **vollständig abgelaufener** Spieltag, für den der Tipper jeden Match hat.
  2. `matchday_winner`-Badges zählten MatchdayWinner-Zeilen aus **allen** Wettbewerben/Saisons — das Profil ist dagegen auf den aktiven Wettbewerb scoped. Jetzt identisch: **aktiver Wettbewerb + aktuelle Saison**.
  3. **Badges wurden nie widerrufen** (nur vergeben) → falsch zuerworbene blieben hängen. Neue **Vollrevalidierung `revalidate_badges()`**: vergibt fehlende **und widerruft** nicht mehr verdiente Auto-Badges (manuelle Badges bleiben unangetastet). Auslösung: **Admin → Wartung → Aufgabe „badges“**.
- 4 neue Tests (partieller/vollständiger Spieltag, Scope-Kontrolle, Widerruf + Manuell-Schutz, Seed-Name). Suite **478/478**, flake8-Gate 0.

## [3.1.43] - 2026-09-20

### 🎯 Bugfix (Spieler-Fund): „Exakte Treffer“ zählten Joker-Tipps (2+2=4 P) mit

- **Meldung:** Bei der Tagessieg-Auswertung wurden als exakte Treffer auch Joker-Tipps mit zusammen 4 Punkten gezählt — obwohl es 2+2 sind. Die Rangliste war korrekt.
- **Root Cause:** „Exakt“ wurde an mehreren Stellen per **Punktewert** (`points >= 4`) statt per **Endstand-Klassifikation** bestimmt. Ein Joker verdoppelt nur die Punkte — er macht aus einem Tendenz-Tipp keinen exakten Treffer.
- **Fix (alle Stellen mit dem Muster):**
  - `recompute_matchday_winners()`: Tagessieg-`exact_count` + Tiebreak zählen jetzt nur **Endstand exakt** (`home_tip == home_score` UND `away_tip == away_score` — die Definition aus `classify_prediction`, Punkte-Logik identisch).
  - Badges: `exact_count` (z. B. „Scharfschütze“), `joker_exact` (Joker + Diff mit 3+3=6 P hätte vorher gereicht!) und `perfect_day` — jetzt per `classify_prediction` == „exact“.
  - Bot-Analyse (`admin_bots_routes`) und AI-Op-Rangliste: gleiche Korrektur.
- **Produktion:** Alte Tagessieg-Zeilen nach dem Deploy über **Admin → Wartung → Aufgabe „matchday_winners“** neu berechnen (eine Klick-Aktion); alternativ passiert es beim nächsten Ergebnis-Sync automatisch.
- 5 neue Regressionstests (Spieler-Szenario, Tiebreak, alle drei Badge-Triggers). Suite **474/474**, flake8-Gate 0.

## [3.1.42] - 2026-09-19

### 🕓 Zeitanzeige einheitlich: UTC → lokale Zeit auf der ganzen Optimizer-Seite

- **Problem (Nutzer-Fund):** Oben „Quotenstand 14:04“ (Chip, lokale Zeit), unten in der Quoten-Bewegung „zuletzt 12:04“ (UTC, unbezeichnet) — derselbe Abruf, zwei unterschiedliche Angaben.
- **Fix:** Der Server liefert die Zeitstempel weiterhin ehrlich als UTC, aber zusätzlich als **UTC-ISO mit Z** (`data-ts-utc`, Helper `_iso_z()`). Neue JS-Funktion `localizeTimestamps()` rechnet beim Seitenaufruf **alle** markierten Zeitstempel in **lokale Zeit** um: Quoten-Bewegung („zuletzt … Uhr (lokale Zeit)“, pro Spiel „seit …“), Modellgüte-Tabelle (Spalte wird zu „Gespeichert (lokale Zeit)“). Chip und Statuszeile zeigen bereits lokal — jetzt passt alles zusammen (2 Stunden Differenz = CEST, weg).
- Unit-Test für `_iso_z` (naive/aware/None; ohne Z-Suffix würde JS die Zeit fälschlich als lokal parsieren). Suite **469/469**, flake8-Gate 0.

## [3.1.41] - 2026-09-19

### 🕓 Quotenstand jetzt gut findbar: Datum + Uhrzeit + Chip in der Aktionszeile

- **Problem (Nutzer):** Das Datum des letzten Quoten-Stands war schlecht findbar — nur als reine Uhrzeit („Quotenstand 14:32 Uhr“) in der sich überschreibenden Statuszeile.
- **Fix:**
  - Statuszeile zeigt jetzt **Datum + Uhrzeit**: „· Quotenstand 17.09., 14:32 Uhr (letzter Online-Abruf)“.
  - Neuer **persistenter Chip in der Aktionszeile** (oben, immer sichtbar): „🕓 Quotenstand: 17.09., 14:32 Uhr“ — gefüllt beim Seitenaufruf (aus dem Spieltag-Store) und nach jedem „⬇ Quoten online laden“; ohne Abruf bleibt er unsichtbar. Tooltip erklärt die UTC-Bezugsgröße der Quoten-Bewegungs-Karte.
- Guard-Test. Suite **468/468**, flake8-Gate 0.

## [3.1.40] - 2026-09-19

### 🧭 Tipp-Optimizer: Neuanordnung (Ergebnis zuerst, Quoten-Eingabe einklappbar) + Test-DB-Fix

- **Neue Seiten-Logik (Nutzerwunsch):** Ergebnis → Aktion → Kontrolle → Hilfe:
  1. Spieltag-Wahl + Aktionen + Status (wie bisher)
  2. **📋 Optimierte Tipps** (Chips, Tabelle, Joker, „💾 Vorhersage speichern“) — jetzt **oben**
  3. **✏️ Quoten eintragen** — die 9 Eingabe-Karten sind jetzt **einklappbar** (`<details>`): automatisch **geschlossen, wenn Quoten vorhanden** sind, **offen, wenn noch keine** (Erst-Rechenlauf-Regel, bleibt an, wenn der Nutzer selbst umschaltet); „⬇ Quoten online laden“ und „Alle Felder leeren“ klappen den Bereich auf. Live-Zähler im Summary („9/9 mit 1X2-Quoten“).
  4. 📈 Modellgüte · 📊 Quoten-Bewegung · 🔬 Backtest (Kontrollzone)
  5. ℹ️ So funktioniert’s + ⚙ Erweitert (Hilfszone, ans Ende)
- **Test-Infrastruktur-Fix (Flaky-Test-Beseitigung):** `app.py` erzeugt auf Modulsebene `create_app()` mit Default-Settings → jeder app-Import in Testläufen seedete die **Repos-Datei-DB `tippspiel.db`** (zweite, zwischen LÄUFEN persistierende Datenbank-Welt; Ursache eines Flakes: 1× Fehler in 6 Läufen). `tests/conftest.py` leitet `DATABASE_URL` jetzt vor den Imports auf `:memory:` (wie TestConfig); Artefakt-Datei gelöscht, `*.db` in .gitignore.
- Struktur-Guard-Test (Reihenfolge + Fold + JS-Regeln). Suite **467/467** (5× in Folge grün), flake8-Gate 0.

## [3.1.39] - 2026-09-16

### 📖 Brier jetzt konkret erklärt (Glossar-Beispiel + Tooltips an allen Brier-Anzeigen)

- **Glossar-Eintrag Brier** umformuliert mit konkretem Beispiel: „Schreibt das Modell 70 % für einen Heimsieg, sollten in ~70 % der Fälle auch Heimsiege eintreffen“ + Erklärung der Referenz „Brier Zufall“ (Modell sollte deutlich darunter bleiben).
- **Tooltips** an den bisher unkommentierten Brier-Stellen: Stat-Karten „Brier 1X2“ / „Brier Zufall“ (Modellgüte-Karte) und die Backtest-Vergleichszeile („Immer-Heim / Liga-Durchschnitt / Zufall“).
- Guards im Test. Suite 466/466, flake8-Gate 0.

## [3.1.38] - 2026-09-16

### 🚨 Hotfix: „Alle Buttons tot“ — verwaiste Klammer in tip_optimizer.js

- **Symptom (Produktion nach (67)):** Kein Button der Optimizer-Seite funktionierte mehr.
- **Ursache:** Bei der `toast()`-Entfernung in (67) war eine schließende Klammer übrig geblieben (Syntaxfehler). Der ganze Script-Block wurde nicht mehr geparst → keine Event-Listener → tot. Bisherige Tests waren reine String-Guards und prüfen keine JS-Syntax.
- **Fix:** Klammer entfernt; **neuer harter Test `test_js_dateien_haben_valide_syntax`** prüft beide Optimizer-Dateien mit `node --check` (wird übersprungen, wenn node fehlt). Damit ist diese Fehlerklasse „JS-Syntaxfehler geht unentdeckt live“ abgefangen.
- Suite **466/466**, flake8-Gate 0, 04-Paket 80 Dateien, verify + SHA grün.

## [3.1.37] - 2026-09-16

### 📍 Tipp-Optimizer: Save-Meldung steht jetzt beim Button (kein Bottom-Toast)

- **Nutzerwunsch:** Die Erfolgsmeldung von „💾 Vorhersage speichern“ kam als Toast ganz unten am Bildschirmrand — soll im Bereich des Buttons erscheinen.
- Neue **Inline-Meldung direkt neben dem Button** (`#to-snap-msg`): Erfolg grün („Gespeichert (9 Spiele) · 14:32 UTC ✓“), Fehler rot (mit HTTP-Status/Grund), Warnung bei fehlenden Quoten orange. Kein Bottom-Toast mehr (Element, JS-Funktion, CSS entfernt), die Meldung belegt die obere Statuszeile nicht mehr.
- Guard-Test (Template ohne `#to-toast`, JS ohne `toast(`, Inline-Meldung present). Suite **465/465**, flake8-Gate 0.

## [3.1.36] - 2026-09-16

### 🐛 Produktions-Fix: „Speichern nicht möglich (HTTP 400)“ = fehlendes CSRF-Token

- **Root Cause (remote nachgewiesen):** Produktion läuft mit `WTF_CSRF_ENABLED = True` (TestConfig hat es aus — deshalb waren alle Tests grün). Flask-WTF blockt **jeden** POST ohne Token mit 400 „The CSRF token is missing“. Die beiden `fetch()`-JSON-Endpunkte (`/admin/tip-optimizer/snapshot`, `/odds-log`) sind die einzigen POSTs der ganzen App, die per JavaScript ohne Form-Token laufen → in Produktion immer 400.
- **Fix:** Beide Endpunkte mit `@csrf.exempt` (mit dokumentierter Begründung im Code: nur Admin-Session; `Content-Type: application/json` erzwingt bei cross-site-Angriffen ein CORS-Preflight, das ohne CORS-Header abgelehnt wird — klassische CSRF-Simple-Requests treffen die Endpunkte nicht; Antwort ohne sensible Daten).
- **Schutz:** Neuer Regressionstest schaltet CSRF im Test gezielt ein (wie Produktion) und belegt: Nicht-exempter POST → 400 (Schutz aktiv), beide JSON-Endpunkte → 200. Suite **464/464**, flake8-Gate 0.

## [3.1.35] - 2026-09-16

### 🩺 Tipp-Optimizer: „Speichern nicht möglich“ wird selbst-diagnostisch (Produktions-Fehlermeldung)

- **Problem:** „💾 Vorhersage speichern“ meldete in der Produktion oben in rot nur „Speichern nicht möglich.“ ohne Grund — der JS-Fallback, wenn die Serverantwort kein JSON war (HTML-Fehlerseite, z. B. 500).
- **Server:** Die POST-Endpunkte `/admin/tip-optimizer/snapshot` und `/odds-log` fangen interne Fehler jetzt ab und antworten **JSON mit Ursache** („Serverfehler: …“, 500) statt HTML — die Statuszeile zeigt den eigentlichen Fehler (z. B. fehlende Tabelle).
- **JS:** Zeigt bei JSON-fremden Antworten jetzt den HTTP-Status („Speichern nicht möglich (HTTP 500).“); bei Historie-Fehlschlag wird die Ursache aus der Serverantwort mitgeliefert.
- Regressionstest: simulierter DB-Fehler (fehlende Tabelle) → JSON-500 mit „no such table“. Suite **463/463**, flake8-Gate 0.

## [3.1.34] - 2026-09-16

### 📖 Tipp-Optimizer: Unklare Abkürzungen erklärt (Glossar + Tooltips)

- **Glossar „Abkürzungen & Begriffe“** im einklappbaren „ℹ️ So funktioniert’s“-Block (zweite Einblendung, 2-spaltig am Desktop): 4/3/2-Regel, 1X2, EP, λ H/λ G, P(≥2 P)/Sicherheit, Brier, MAE, Ü 2,5/Ü 3,5, BTTS, ST, „knapp“, Dixon-Coles, Walk-Forward-Backtest, Odds-Anker — jeweils in einem Satz ohne Fachchinesisch.
- **Tooltips an den Spaltenköpfen** (Desktop-Hover, mobil übers Glossar): Ergebnistabelle (λ H/λ G, 1/X/2, Optimaler Tipp, EP, Sicherheit), Modellgüte-Abrechnung (ST, EP erwartet/real, P(≥2 P), Brier) und Backtest-Tabelle (gleiche Begriffe).
- Guard-Tests schützen Glossar + Tooltips. Suite 462/462, flake8-Gate 0.

## [3.1.33] - 2026-09-16

### 📱 Tipp-Optimizer: „Tippliste zum Übertragen“ entfernt (Nutzerwunsch)

- Die Karte „Tippliste zum Übertragen“ (Textfeld + „📋 Tippliste kopieren“) ist weg — die Tipps stehen sowieso in der Ergebnistabelle. Damit verschwunden: Textfeld, Copy-Handler/Clipboard-Code, `tips`-Sammlung, CSS-Regel.
- **Übersiedelt in die Ergebniskarte „Optimierte Tipps“** (bleiben erhalten): Joker-Vorschlag-Zeile, Modell-Erwartung-Zeile und der „💾 Vorhersage speichern (Modellgüte)“-Button (jetzt direkt unter den Ergebnissen, wo die Abrechnung zustandekommt).
- Quelltext-Guards schützen Entfernung + neue Position (keine Regression). Suite 462/462, flake8-Gate 0.

## [3.1.32] - 2026-09-16

### 📊 Tipp-Optimizer: Quoten-Bewegung (J) + Scheduler-Tests + utils-Fix

- **Quoten-Bewegung (V2-Kandidat J, 0 €, Admin-only):** „Quoten online laden“ merkt die befüllten Quoten je Spiel jetzt als Zeitstempel-Stand in der DB (neue Tabelle `odds_snapshots` per `db.create_all()` beim Start). Neue Karte „📊 Quoten-Bewegung“ zeigt je Spiel des angezeigten Spieltags den **ersten vs. letzten Stand** (1/X/2 mit ↓/↑-Pfeilen) + Anzahl der Stände — ab dem zweiten Abruf desselben Spieltags sichtbar, sonst ℹ️-Hinweis. Manuelle Eingaben bleiben in Ruhe; scheitert das Loggen, meldet die Statuszeile es (ℹ️, nie ⚠️). Endpunkt `POST /admin/tip-optimizer/odds-log` (Admin-Gate, Validierung wie Snapshot).
- **Bugfix (latent, von den neuen Tests gefangen):** `utils.py` exportierte `send_kickoff_reminder` nicht mehr (funktion liegt in `mail_helpers.py`) → `scheduler.py` wäre beim Start mit ImportError gestorben (Reminder/Sync/Auto-Archiv wären stillstehend). Re-Export ergänzt.
- **Scheduler-Tests (0 % → getestet):** Neues `tests/test_scheduler.py` (8 Tests) für die alle 10/15/60 min laufenden Jobs: Reminder-Deaktivierung über Setting, kaputte Settings dürfen den Lauf nicht sprengen, Sync-Job ruft `sync_results` an, Saison-Auto-Archiv (deaktiviert / Saison nicht beendet / bereits archiviert / nach 34. Spieltag → archivieren + `season_archived`-Flag + Telegram-Info an Admins).
- Tests: +12 (Odds-Log-Endpunkt inkl. Validierung/Admin-Gate, Bewegungs-Anzeige mit Einzelständen + Fallback, JS-Anbindung, 8× Scheduler). Suite **462/462**, flake8-Gate 0.

## [3.1.31] - 2026-09-16

### 🐛 Tipp-Optimizer: Schalke-Spiel beim „Quoten online laden“ stumm übergangen — gefixt + sichtbar gemacht

- **Bug (Nutzer meldete: „Warum fehlt das Schalke-Spiel?“):** Beim Online-Quotenladen blieb FC Schalke 04 – SV 07 Elversberg ohne Quoten (Zeile „—“, nicht berechnet). Ursache: `DE_NAMES` wies die API-Namen „SV Elversberg“/„Elversberg“ auf **„SV Elversberg“** statt auf den echten DB-Vereinsnamen **„SV 07 Elversberg“** — die Seiten-Zuordnung verlangt (bewusst, keine Name-Ratelei) mindestens Teilstring-Übereinstimmung, und das „07“ bricht die Teilstring-Kette. Fix: Alias zeigt auf den exakten DB-Namen (+ Eintrag „sv 07 elversberg“). Test: Parser-Test mit echtem Schalke/Elversberg-Event.
- **Transparenz (Dauerregel 2, Versuch + Grund):** „Quoten online laden“ listet im Status jetzt alle Spiele, die **danach tatsächlich ohne 1X2** geblieben sind: „✓ 8/9 Spiele mit Quoten befüllt · Nicht zugeordnet (Name): FC Schalke 04 – SV 07 Elversberg …“ (Status wird gelb statt grün). Manuell schon gefüllte Karten bleiben in Ruhe. Quelltext-Guard abgesichert. Suite 450/450, flake8-Gate 0.

## [3.1.30] - 2026-09-16

### 📱 Tipp-Optimizer: „So funktioniert’s“-Block einklappbar

- Der Infoblock unter den Aktionen ist jetzt ein `<details>`-Block (Standard: **eingeklappt**) mit der Zeile „ℹ️ So funktioniert’s“ — spart auf dem Smartphone Platz, anzeigbar per Tap. Gleiche Muster-Sprache wie der bestehende „⚙ Erweitert“-Block (Pfeil dreht sich beim Öffnen, nativer `<details>` ohne JS). Inhalt unverändert (Schnelleingabe, Engine-Logik, Ergebnis-Chips, Joker, Hinweis nur Spielleiter-Ansicht). Quelltext-Guard-Erweiterung schützt die Einbindung. Suite 449/449, flake8-Gate 0.

## [3.1.29] - 2026-09-16

### 📱 Tipp-Optimizer: Smartphone-tauglichere Anzeige (Mobile-First-Pflege)

- **Button-Reihen** (Tippliste kopieren / Vorhersage speichern, Backtest-Button) bekommen eine gemeinsame Regel (`.btnrow`): auf schmalen Screens (≤ 640 px) werden sie **vollflächig übereinander** gestapelt — große, verlässliche Tap-Ziele statt enger Seite-an-Seite-Zeile.
- **Modellgüte-Zusammenfassung** (Karte „📈 gespeicherte Vorhersagen“) ist keine dichte Zahlenzeile mehr, sondern ein **Stats-Raster** (`.to-statgrid`): EP erwartet/real, P(≥2 P) erwartet/real, Brier + Zufalls-Brier als eigene Kacheln — auf dem Handy 2-spaltig, am Desktop 3–6-spaltig (auto-fit).
- **Weite Tabellen** (Modellgüte-Abrechnung 8 Spalten, Backtest je Spieltag 6 Spalten) behalten jetzt eine Mindestbreite (`to-tblwide`/`to-tblwide-narrow`) und werden im vorhandenen `to-tblwrap`-Container **sauber gewischt** (`-webkit-overflow-scrolling: touch`), statt auf 360 px gequetscht zu werden.
- **Chips** (Backtest-Kennzahlen) und Ergebnis-Zeilen auf dem Smartphone kompakter.
- Alles reine `static/`-CSS/JS + Template-Pflege; neue Quelltext-Guard-Tests schützen die Regeln. Suite 449/449, flake8-Gate 0.

## [3.1.28] - 2026-09-16

### 📈 Tipp-Optimizer: Modellgüte – Walk-Forward-Backtest + prospektives Tracking (Admin-only)

- **Walk-Forward-Backtest (neue Karte „🔬 Modellgüte – Walk-Forward-Backtest“ auf der Admin-Optimizer-Seite):** `GET /admin/tip-optimizer/backtest` bewertet die Modell-Grundlage (Teamstärken + Dixon-Coles + Torsumme) auf der ganzen Saison aus der App-DB: jeder abgelaufene Spieltag wird aus allen *bisher* fertigen Spielen neu gefittet (mind. 8) und blind auf den Spieltag bewertet. Kennzahlen: EP/Spiel (4-3-2-0), 1X2-Trefferquote vs. Baselines (Immer-Heim, Liga-Frequenz, Zufall 33 %), Brier 1X2 (3-Wege) vs. denselben Baselines, P(≥2 P), exakt Top-1/Top-3, Torsumme-MAE – gesamt + pro Spieltag. Ohne Odds-Anker (historische Quoten gibt es von keiner Gratis-Quelle) → bewusst als **Untergrenze** der echten Tipp-Qualität gekennzeichnet. 0 €, reine DB-Auswertung, ~1–3 s.
- **Prospektives Tracking (neue Karte „📈 Modellgüte – gespeicherte Vorhersagen“):** „💾 Vorhersage speichern (Modellgüte)“ legt den aktuellen Modell-Zustand aller Spiele mit vollständigen 1X2-Quoten als `OptimizerRun`/`OptimizerRunTip` in der DB ab (Tipp, EP, p1/px/p2, P(≥2 P)/P(≥3)/P(exakt), effektive λ, verwendete Quoten). Ist der gespeicherte Spieltag beendet, rechnet die Seite automatisch ab: erwartete EP vs. realisierte Punkte, P(≥2 P)-Erwartung vs. Trefferrate, Brier 1X2 mit Odds-Anker – gesamt (gewichteter Mittelwert) + Tabelle je Spieltag. Bewertet wird erst, wenn **alle** Matches des Spieltags `finished` sind.
- **Modell-Code:** `tip_optimizer_model.py` um Python-Abbild der Engine ergänzt (`build_matrix`, `tip_points`, `ep_table` als O(N²)-Tabelle über Anti-Diagonale + Quadranten, gegen die Brutto-Summe exakt verifiziert; `backtest()`, `evaluate_run_tips()`). Neue Modelle in `models.py`: `optimizer_runs` + `optimizer_run_tips` (werden beim App-Start per `db.create_all()` angelegt → Plesk-Restart nach Deploy).
- **UI:** Optimizer-Karten tragen `data-match-id`; JS sammelt bei jedem Recalc den Voll-Zustand pro Spiel (`lastFull`), POSTet den Snapshot (`/admin/tip-optimizer/snapshot`, Validierung: Match gehört zu Competition + Spieltag, Cap 20) und rendert den Backtest (Chips + 1X2/Brier-Zeilen + per-Spieltag-Tabelle) per Fetch. Alles Admin-only, keine Spieler-Sichtbarkeit.
- **Tests:** 8 neue (EP-Tabelle == Brutto, Walk-Forward-Bewertung + Mindestanzahl-Meldung, Backtest-Endpunkt Admin-Gate, Snapshot-Validierung, Abrechnung abgelaufener Spieltag in der Seite, `evaluate_run_tips`-None bis Spieltagsende, JS-Anbindung-Guard). Suite: 448/448, flake8-Gate 0.
- **Deploy (Netcup):** 15 Dateien (14 aus 3.1.27 + `models.py`), danach `__pycache__` löschen und Plesk-Restart (neue Tabellen werden erst beim Start angelegt).

## [3.1.27] - 2026-09-15

### 🎯 Tipp-Optimizer: Modell-Fit aus den echten Saisondaten + JS-Engine in der CI

- **Saisondaten-Fit (das Modell ist jetzt datenbasiert, nicht mehr annahmebasiert):** Neues Modul `tip_optimizer_model.py` berechnet aus den fertigen Spielen der aktiven Liga in der App-DB (mindestens 8, sonst unverändert die Standalone-Defaults):
  - Ligaschnitte (Heim/Auswärts-Tore) und **Teamstärken** (Angriff/Abwehr als Multiplikatoren, Shrinkage `n/(n+6)` Richtung neutral – Ausreißer-Ergebnisse verrücken das Modell nicht)
  - **Dixon-Coles-Faktoren** (beobachtete 0:0/1:1/1:0+0:1-Frequenzen vs. unabhängiges Poisson, geklemmt auf 0,5–1,8)
  - **Torsummen-Prior** (Liga-Mittel, geklemmt auf 2,0–4,5)
  - **λ-Prior je Spiel** (`Liga-Heimschnitt × Angriff(Heim) × Abwehr(Gast)`, geklemmt auf 0,15–4,5)
- Die Engine (`static/js/to_engine.js`, `fitLambdas(target, ex, rho, prior, goalPrior)`) nimmt Prior + Torsumme-Prior als weiche Zusatz-Bestrafung auf: **die Quoten bleiben das Hauptsignal**, der Saisondaten-Anker stützt (Gewicht 0,15 – bewusst niedrig, damit eine Markt-Bewegung z. B. nach Verletzungen das Modell führt; die Details zeigen „Saisondaten-Prior λ … → Fit …“ pro Spiel).
- Transparent im UI: „Erweitert“-Feld zeigt die gefitteten Faktoren/Torsumme; Infotext nennt die Anzahl der ausgewerteten Spiele; ohne Daten (frische DB) bleibt exakt der alte Default-Verhalt (fitted=False, ℹ️-Hinweis).
- **Engine-Modul + CI:** Die Dixon-Coles-Engine steht jetzt eigenständig in `static/js/to_engine.js` (UMD-Export, DOM-frei; 1:1-Code unverändert) und wird von einer neuen CI-Job „JS-Engine-Tests (Node)“ in `tests/js/tip_optimizer_engine_test.js` abgedeckt (9 Bereiche: 4/3/2/0-Regel, Matrix-Normalisierung, DC-Faktoren, prop-vs-power-Margen, λ-Fit-Wiedergewinnung, Torsumme-Prior-Effekt, Weichheit des Teamstärken-Priors, EP-Bruttoprüfung, extreme-λ-Robustheit). Die UI bezieht die Engine über `TOEngine`.
- Tests: +5 (`fit` mit künstlicher Liga inkl. Stärken-/Prior-Assertions, Fallback ohne Spiele, Config-Insel mit Priors per JSON-Parse, Default-Hinweis ohne Daten, Engine-/UI-Anbindung als Quelltext-Guard). UI-Smoke mit Mini-DOM-Stub: Prior aktiv („Prior λ 2,60/0,50 → Fit 2,27/0,94“), Joker/Methoden-Vergleich/Ortszeit unverändert grün.

### ✅ Verifikation

- `python -m pytest -q`: **440/440 Tests bestanden**.
- `node tests/js/tip_optimizer_engine_test.js`: grün (CI-Job ergänzt).
- flake8-Gate (E9,F63,F7,F82): 0 Fehler. Coverage: **85 %** (`tip_optimizer_model.py` 97 %, `admin_tip_optimizer_routes.py` 83 %).


## [3.1.26] - 2026-09-15

### 🎯 Tipp-Optimizer: Hygiene-Runde + Joker-Optimierung (Admin)

- **Joker-Optimierung:** Neue Joker-Zeile unter der Tippliste – die Engine schlägt vor, auf welchem Spiel sich der ×2-Joker am meisten lohnt (Spiel mit dem höchsten Erwartungswert; da der Joker die erzielten Punkte linear verdoppelt, ist genau das die optimale Wahl). Beispiel: „erwartet 1,31 P, mit Joker 2,62 P“.
- **Median statt Mittelwert:** Der The-Odds-API-Konsens nimmt jetzt den Median über alle Buchmacher – eine Sonderquote eines kleinen Bookies (z. B. 4,00 statt ~1,90) verzieht den Konsens nicht mehr.
- **Quoten-Stempel:** Nach dem Online-Abruf zeigt die Statuszeile „Quotenstand HH:MM (letzter Online-Abruf)“ – bleibt nach Neuladen erhalten (im Spieltag-Store), damit das Alter der Quoten vor einem (budget-kosten) zweiten Abruf sichtbar ist.
- **Ortszeit:** Anstoss-Zeiten in den Spielkarten erscheinen jetzt in der Ortszeit des Browsers (vorher „HH:MM Uhr UTC“); die UTC-Zeit bleibt im Tooltip.
- **Plausibilitäts-Warnung:** Deutlich unplausible Quoten (implizite Marge > 35 % oder Mini-Quoten < 1,05) markiert die Karte mit „⚠ Quoten prüfen“ – Eingabefehler-Fang, nicht blockierend.
- **Margen-Methoden-Vergleich (aktuell):** In den Detail-Akkordeons steht jetzt, ob der optimale Tipp von der Margen-Methode abhängt (Power vs. proportional), plus Chip „Methode-empfindlich: N Spiele“. (Reines Vergleichs-Feature für den aktuellen Spieltag – keine Historie.)
- **Jahreswechsel-Fix:** Der localStorage-Schlüssel trägt jetzt die Saison (`to_<Saison>_md_<N>` statt `to_md_<N>`) – in der neuen Saison werden keine Quoten mehr aus der Vorsaison mitgeladen.
- Tests: +2 (`test_odds_median_ignoriert_ausreisser_buchmacher` direkt gegen den Parser, `test_js_hygiene_und_joker_logik_im_quelltext` als Quelltext-Guard), bestehende Endpunkt-Tests um Median-Semantik, `ts`-Feld und Saison-/`data-kick`-Ansprüche erweitert. UI-Smoke mit Mini-DOM-Stub in Node (Init + recalc + Joker-Rendering) grün.

### ✅ Verifikation

- `python -m pytest -q`: **435/435 Tests bestanden**.
- flake8-Gate (E9,F63,F7,F82): 0 Fehler. Coverage: **85 %** (Modul `admin_tip_optimizer_routes.py`: 84 %).


## [3.1.25] - 2026-09-15

### 🎯 Tipp-Optimizer (Admin-only) – EP-optimierte Tipps je Spieltag

- Neue Admin-Seite „Tipp-Optimizer“ (Admin → Spielleitung): Dixon-Coles-Poisson-Engine (1:1-Port des Standalone-Tools v1.4). Pro Spiel 1X2-Quoten eintragen (manuell per Schnelleingabe oder The-Odds-API-Konsens über alle Buchmacher), optional Ü2,5 / BTTS / Ü3,5 + λ-Adjuster je Team.
- EP-Optimierung nach der 4/3/2-Regel: wählt pro Spiel den Tipp mit dem höchsten erwarteten Punktwert – nicht zwingend das wahrscheinlichste Einzel-Ergebnis (⚠ wenn Abweichung). Ergebnis-Chips hoch/mittel/niedrig = P(≥2 P) ≥70/≥40/<40 %, Tippliste zum Kopieren, Ergebnisse lokal pro Spieltag gespeichert (Browser).
- The-Odds-API optional in den Einstellungen („The-Odds-API Key“): Budgetwächter 60 Abrufe/Monat (Free-Plan 500 Credits, 2/Abruf); jeder Abruf – auch Fehler wie 401/404/429 – wird im Admin-Datenquellen-Protokoll mit Grund geloggt. Ohne Key bleibt das Feld ℹ️-dezent inaktiv, Quoten laufen rein manuell.
- Port-Fixes: `requests`-Antworten lesen `status_code` (Standalone-Tool nutzte `fetch().status`); Kickoff-Sortierung sicher für naive DB-Datetimes.
- Tests: `tests/test_tip_optimizer.py` (10 Tests: Seiten-Rendering inkl. to-config-Insel, Admin-Gate 403, Spieltag-Wechsel, leerer Spieltag, Key-/Budget-Gates ohne HTTP-Versuch, Parsing mit Konsens-Quoten + Namens-Normalisierung, Fehlergrund im Datenquellen-Protokoll, Settings-Verhalten „leer = beibehalten“, Sync-Seite listet neue Quelle).
- Wichtig: Optimizer-Daten erscheinen ausschließlich im Admin-Bereich (keine Spieler-Fläche, keine /mehr-Karte, kein Dashboard-Widget für Teilnehmer).

### ✅ Verifikation

- `python -m pytest -q`: **433/433 Tests bestanden**.
- flake8-Gate (E9,F63,F7,F82): 0 Fehler. Coverage: **85 %** (neues Modul `admin_tip_optimizer_routes.py`: 83 %).
- Engine-Smoke (Node, Beispiel-Spieltag mit echten Quoten): Σ 11,69/36 EP (Ø 1,30); `tipPoints`-Regel 4/3/2/0 exakt wie in der App.

























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

## 2026-09-01 - Cron-Kosmetik: Doppel-Heartbeat beim Backup beseitigt

- **Problem (Kosmetik, aus der Cron/Backup-Runde bekannt):** Beim Task `backup` wurde der Heartbeat doppelt geschrieben — `backup.py → create_database_backup()` schrieb ihn zuerst **mit Detail** (Dateiname + Größe), direkt danach überschrieb `cron_jobs._run_task_safe()` ihn **ohne Detail**. Folge: Im Admin-Wartungscenter fehlte beim per Cron erstellten Backup das Detail (bei „Jetzt Backup erstellen" war es sichtbar — der Admin-Weg läuft nicht über `_run_task_safe`), dazu ein unnötiger zweiter Settings-Write pro Lauf. Betroffen waren beide Cron-Wege (`cron_jobs.py backup` und `/cron/run?task=backup`).
- **Fix:** Neue Konstante `SELF_HEARTBEAT_TASKS = frozenset({"backup"})` in `cron_jobs.py` — für diese Tasks schreibt `_run_task_safe` im **Erfolgsfall** keinen zweiten Heartbeat mehr (das Fachmodul deckt Erfolg UND Fehlschlag selbst ab, inkl. Detail). Der **Fehlerpfad** in `_run_task_safe` bleibt als Sicherheitsnetz für Abbrüche VOR dem Fachmodul-Aufruf (z. B. ImportError beim Bootstrap) unverändert aktiv. Keine Signatur-/Aufruferänderung — `/cron/run` profitiert automatisch.
- **Tests:** +4 in `tests/test_cron_backup.py` (genau ein Heartbeat mit erhaltenem Detail beim Backup; andere Tasks bekommen ihn weiterhin von `_run_task_safe`; Fehler-Heartbeat vor dem Fachmodul-Aufruf; End-to-End echtes Backup über den Task-Wrapper mit Detail-Erhalt); bestehender HTTP-Test `test_cron_http_backup_laeuft_mit_key` an den Vertrag angepasst (Fake schreibt Heartbeat selbst) + Detail-Assertion. Lokaler Smoke: `cron_jobs.py backup` → `status` zeigt jetzt „tippspiel_… (… Bytes)" statt leerem Detail.
- **Teststand: 285/285 Tests bestanden**, Coverage 79 %. Geänderte Dateien: `cron_jobs.py`, `tests/test_cron_backup.py`. Deploy-FTP: nur `cron_jobs.py` (kosmetisch, kein eiliger Deploy nötig — wirkt ohnehin erst mit dem nächsten Cron-Lauf).

## 2026-09-01 - Vendor-Feinschliff: vendor/ auf finalem Merge-Stand neu gebaut

- **Anlass (letzter offener Punkt aus Dependabot-Runde 1):** Der live liegende `vendor/` war vor den letzten Merges gebaut — es fehlten Werkzeug **3.1.8** (lag: 3.1.7), email-validator **2.3.0** (2.2.0) und reportlab **5.0.1** (4.2.2).
- **Build (in der Sandbox, besser als der Windows-Weg):** `pip install --target=vendor --platform=manylinux2014_x86_64 --python-version=39 --only-binary=:all: --implementation=cp -r requirements_py39.txt` — damit sind **alle** Pakete echte Linux/cp39-Wheels (build_vendor.bat lädt nur Pillow/reportlab explizit als Linux-Wheels, der Rest kommt vom Windows-Host und fällt auf dem Server auf Pure-Python-Fallbacks zurück). Alle 20 `.so`-Binärmodule verifiziert `cpython-39-x86_64-linux-gnu`, keine Fremd-Artefakte; `bin/` + `__pycache__` entfernt wie im Bat-Skript.
- **End-to-End verifiziert mit echtem Python 3.9.25** (uv-Standalone, nacktes `-s` ohne installierte Pakete): alle Imports inkl. C-Extensions (`PIL._imaging`, `markupsafe._speedups`, `sqlalchemy.cyextension`), PDF-Smoke (reportlab erzeugt gültiges %PDF) + PNG-Smoke (Pillow), und komplette App gebootet — `python3.9 cron_jobs.py status` lief ausschließlich mit dem neuen vendor/ über den Cron-Bootstrap (zeigt nebenbei das erhaltene Backup-Heartbeat-Detail → Doppel-Heartbeat-Fix nochmals bestätigt).
- **Lieferung:** `_lieferungen/05_Vendor_py39_2026-09-01.zip` (2734 Dateien, 21 MB) inkl. `VENDOR_ANLEITUNG.txt` (Upload mit Rückweg: vendor→vendor_alt umbenennen, neu hochladen, Plesk-Restart, testen, dann vendor_alt löschen). Kein Repo-Code geändert (vendor/ ist gitignored); Teststand unverändert **285/285**, Coverage 79 %.

## 2026-09-02 - Adminbereich: Backups zusammengeführt + klare Gruppen-Hierarchie

- **Nutzer-Feedback 1 (Backup zerrissen):** „Cron & Backup" lag im Wartungscenter, „Backup & Restore" als eigene Seite unter Wartung — wer ein Backup suchte, musste zwei Orte kennen. **Zusammengeführt auf `/admin/backup` („💾 Backups")**: Server-Backups (Button „Jetzt Backup erstellen", Automatik-Status des nächtlichen Cron-Backups, Liste der letzten Backups, Offsite-Hinweis) + DB-Download + Komplett-ZIP + Restore auf einer Seite. `backup_page` liefert dazu `backups`/`backup_cron` mit; `maintenance_backup_now` leitet jetzt auf die Backup-Seite um.
- **Wartungscenter** behält reines Monitoring: Karte heißt jetzt „⏰ Automatik (Cron)" (Heartbeat aller 4 Aufgaben, Plesk-Einrichtungshinweis, Cron-HTTP-Status) + Link „💾 Backups verwalten →"; Backup-Button und -Liste sind dort raus.
- **Nutzer-Feedback 2 (Überschriften):** Auf dem Admin-Dashboard sahen die Gruppentitel („⚽ Spielbetrieb" …) genauso aus wie die Unterpunkte — die Links waren mit `font-weight:850` sogar fetter als die h3-Titel. **Fix:** Gruppentitel als dezente GROSSBUCHSTABEN-Labels (11.5px, gesperrt, muted) mit Icon-Chip in Gruppen-Akzentfarbe; jede Gruppe bekommt eine 3px-Akzentlinie oben (Spielbetrieb Teal, Mitspieler Violett, Wartung Amber, Saisonabschluss Blau — via `--ams-accent`-Custom-Properties, Dark-/Light-Mode-tauglich). Dashboard-Link umbenannt: „💾 Backups — Erstellen, herunterladen, wiederherstellen"; Wartungscenter-Untertitel aktualisiert.
- **Tests:** +3 (Backup-Seite bündelt alle Funktionen; Automatik-Lauf-Detail sichtbar; Dashboard-Gruppen mit Akzent-Klassen + neuer Link-Text), 2 angepasst (Wartungscenter ohne Backup-Button, backup-now-Redirect auf Backup-Seite). Teststand **288/288**, Coverage 79 %.
- **Deploy-FTP:** `routes_admin.py`, `admin_maintenance_routes.py`, `templates/admin/backup.html`, `templates/admin/maintenance.html`, `templates/admin/dashboard.html`, `static/css/style.css` + Plesk-Restart.

## 2026-09-02 - Mehr-Seite: Schnellzugriff-Chip „Spiele & Tipps"

- **Nutzerwunsch:** „Spiele & Tipps" (Spielplan, `main.schedule`) als sechster Chip im Schnellzugriff der Mehr-Seite — eingefügt direkt nach „Schnelltipp", damit die Tipp-Aktionen beieinander stehen (Reihenfolge: Schnelltipp · Spiele & Tipps · Tippübersicht · Vorschau · Rückblick · Liga-Tabelle). Layout ist flex-wrap, keine CSS-Änderung nötig.
- **Test:** +1 `test_mehr_schnellzugriff_chips` (alle 6 Chips + Spielplan-Link). Teststand **289/289**, Coverage 79 %.
- **Deploy-FTP:** nur `templates/more.html`.

## 2026-09-06 - LIVE-Center: echte Spielminute statt Schätzung, Halbzeitpause sichtbar

- **Problem (Nutzerfeedback):** Die angezeigte Spielminute wurde aus der Anstosszeit hochgerechnet (Client- und Server-Stoppuhr, auf 1..90 geklemmt). Folge: falsche Minuten, Halbzeitpause lief einfach weiter, Nachspielzeit/Verzögerungen unsichtbar. Dabei liefert football-data.org v4 laengst echte Live-Daten: Feld `minute` plus Status `PAUSED` (Halbzeit), `IN_PLAY`, `EXTRA_TIME`, `PENALTY_SHOOTOUT`. Diese Daten wurden nie gelesen — die DB-Spalte Match.minute blieb im Alltagsbetrieb leer.
- **Datenpfad:** `sync_football_data.py::_process_football_data` persistiert jetzt die Feed-Minute (`Match.minute`) und die Rohphase (`Match.live_phase`, neuer SPALTEN-Migrations-Eintrag in `sync.py`, VARCHAR(20) — PENALTY_SHOOTOUT ist 17 Zeichen!). EXTRA_TIME/PENALTY_SHOOTOUT zaehlen zusaetzlich zu den Live-Statussen (Passthrough bisher fehlte → Cup-Spiele waeren auf scheduled gefroren, Monotonie-Guard hinke). In der Halbzeit gefriert die letzte Minute, beim Abpfiff wird die Phase zurueckgesetzt.
- **Anzeige:** `/api/live/center` + `/api/live/matchday` senden `minute` (nur echter Feedwert, sonst null) und `live_phase`. `live.html` und `live.js` zeigen: LIVE · X. Min (Feed-Minute), ⏸ Halbzeitpause (PAUSED) oder nur LIVE wenn der Feed schweigt. Schaetzlogik ersatzlos entfernt (estimateInitialLiveMinutes + Fallback in updateMatch + data-kickoff-Anker im Live-Badge); das base-Banner-Countdown bis Anpfiff bleibt davon unberuehrt (echter Countdown, keine Spielminute).
- **Tests:** +6 in `tests/test_live_minutes.py` (Sync-Phasen inkl. Pause/Finish, Feedwerte ohne Minute, Unit-Guard gegen Schätzung, Halbzeit-Badge + API, LIVE ohne Uhr + Quelltext-Guards). Teststand **295/295**, flake8-Hartgate (E9,F63,F7,F82) sauber.
- **Deployment:** kein manueller Migrationsschritt nötig — die neue Spalte `matches.live_phase` wird beim Plesk-Neustart automatisch über `auto_migrate_schema()` (sync.py, läuft bei App-Start) per ALTER TABLE nachgezogen. Wichtig ist nur, dass `sync.py` UND `models.py` zusammen hochgeladen werden.

## 2026-09-06 - Rangliste (Smartphone): Namen endlich lesbar

- **Problem (Nutzerfeedback mit Screenshot):** Im Mobile-Kartenlayout der Rangliste drängten sich Rang, Avatar, Name, Vereinslogo und Trend-Pille in EINE Zeile — der Name hatte nur ~120px und endete als „Meh...", „rud...", „Had...". "Im smartphone mode kann man die Namen so gut wie gar nicht lesen."
- **Lösung (templates/leaderboard.html + style.css):** Neuer Namensblock `.lb-card-id` mit zwei Zeilen — Zeile 1: Name in voller Restbreite (~260px bei 390px Viewport, 15px, Ellipse erst danach), Zeile 2 `.lb-card-sub`: Lieblingsvereins-Miniatur (14px) + Trend-Pille kompakter (10px). Kopf-Abpadding/Abstaende leicht reduziert (gap 10->8, Padding 12/14->10/12, Rang-Minbreite 36->30, Punkte 24->22px). Subzeile wird nur gerendert, wenn Logo/Trend vorhanden. Desktop-Tabelle und Ewige-Tabelle-Karten bleiben unveraendert (dort hatte der Name schon freie Bahn).
- **Test:** +1 `test_rangliste_mobile_karte_gibt_dem_namen_die_zeile` (Render-Reihenfolge Name vor Subzeile + CSS-Regression auf die neuen Selektoren). Teststand **296/296**, flake8-Hartgate sauber.
- **Deploy-FTP:** `templates/leaderboard.html`, `static/css/style.css`.

## 2026-09-06 (2) - LIVE: Minuten-Anzeige trotz Free-Tier (Feed-Vorrang + gekennzeichnete Struktur-Uhr)

- **Nachtrag zum 02.09.-Umbau:** Nutzer meldete live aus dem Stadion/Livingroom: Spiel in der 10. Minute, aber nur "LIVE" ohne Minute. Ursache: Das football-data-FREE-Tier liefert Live-Scores nur verzoegert und die echte `minute` haeufig ueberhaupt nicht - die neue "nur Feed"-Politik zeigte damit konstruktionsbedingt gar keine Uhr mehr.
- **Loesung (routes_api.py::live_clock_for):** dreistufige Prioritaet — 1) Feed-Phase PAUSED => "⏸ Halbzeitpause" (verbindlich), 2) Feed-Minute => exakte Anzeige, 3) Feed stumm => strukturierte Uhr ab Anstoss: 1. Halbzeit bis ~47, Pause-Fenster bis 63 (Uhr steht still, Label "⏸ Halbzeit ≈"), 2. Halbzeit mit 15 Min Abzug, ab 108 Min Stille statt Falschanzeige, nie mehr eine blinde 90er-Stoppuhr. Abgeleitete Werte werden in UI + API als Naeherung markiert ("≈", title-Hinweis), damit sie nicht mit Feed-Daten verwechselt werden. Payload-/API-Felder: minute, minute_derived, halftime (feed|derived|null), overtime; live.js + live.html nutzen dieselbe Logik, das Erstrendering des /live-Pages bekommt die Uhr via live_clock-Map aus der Route.
- **Hinweis fuer echte Feed-Minuten:** wer beim Live-Center die sekundengenaue Minute ohne "≈" will, braucht football-data.org "Livescores" (€12/Monat) — am Code aendert sich nichts, die Feed-Werte haben bereits Vorrang und verdraengen die Naeherung automatisch.
- **Tests:** test_live_minutes.py neu gefasst auf die 3-Stufen-Logik (Feed-Vorrang, verbindliche Feed-Pause, Struktur-Uhr inkl. Halbzzeit-/Spaetphasen-Grenzen, Seite+API fuer ≈-Anzeige & abgeleitete Halbzeit). Teststand **299/299**, Coverage ~81 %, flake8-Hartgate sauber.
- **Deploy-FTP zusaetzlich:** `routes_api.py`, `main_stats_routes.py` (templates/live.html + static/js/live.js waren schon gelistet).

## 2026-09-06 (3) - Live-Rangliste: Trend & +Punkte bleiben dauerhaft sichtbar

- **Problem (Nutzerfeedback):** Rangwechsel (▲/▼) und gutgeschriebene Punkte (+N) wurden in der Live-Rangliste nur 8 Sekunden eingeblendet und waren dann weg — bei 30s-Polling faktisch „meist unsichtbar".
- **Neu:** Die Spalten zeigen jetzt die **Aenderung seit dem Oeffnen der Seite** (neue Basis-Map baseLb, initialisiert aus den serverseitig gerenderten data-Rang/Punkte-Attributen): Rangpfeil + Platzdifferenz und +Punkte bleiben stehen und wachsen mit naechsten Tore/entschiedenen Spielen; Blinken (row-up/row-down/points-flash) feuert weiter nur bei frischer Aenderung seit dem letzten Poll. Faellt ein Punktestand (Korrektur), zeigt eine neue Klasse .points-down den negativen Delta. Kehrt ein Spieler auf seinen Ausgangsrang zurueck, verschwindet der Pfeil (Delta 0).
- **Dateien:** static/js/live.js (setPersistent-Helfer, Delta aus baseLb, beide setTimeout-Loescher entfernt), static/css/style.css (.points-down). Regressionstest +1 in tests/test_routes.py (Quelltext-Guard: keine 8s-Loescher mehr, baseLb/setPersistent vorhanden, .points-down in CSS) + Node-Simulation der Poll-Folgen (persistiert p3, Rueckfall p4). Teststand **300/300**, flake8-Hartgate sauber.
- **Deploy-FTP:** `static/js/live.js`, `static/css/style.css`.

## 2026-09-06 (4) - KI-Bots: Statistik-Cache fror Saisonstart ein (MasterBot tippte blind)

- **Nutzerfrage:** "Warum ist der MasterBot so schlecht? Steht auf dem letzten Platz." Diagnose: Die Bots berechnen Team-Form/Heimstaerke aus fertigen Spielen und cachen sie pro Bot-Instanz — diese Cache wurde NIE geleert. Da der AIManager als Singleton in langlebigen Passenger-Workern lebt, fror der Stand der ersten Tipp-Runde ein: zu Saisonbeginn = keine fertigen Spiele = alle Teams "durchschnittlich" (Form 0.5, Heimschaerke 0.5). EXPERT/MasterBot tippten damit wie Zufallsbots auf Poisson(1.4)/Poisson(1.1)-Basis — gleich schlecht wie RookieBot, die Rangfolge unter den Bots war purer Zufall. Zusätzlich: "Form der letzten 5" wurde in DB-Reihenfolge statt neueste-zuerst gelesen (all_finished ohne order_by).
- **Fix (ai_opponent.py + admin_bots_routes.py):** neue Methode AIOpponent.invalidate_stats_cache(); tip_all_matches leert vor jeder Runde die Caches aller Bots und laedt beendete Spiele nun order_by(kickoff.desc); der Einzel-Bot-Tipp im Admin holt dieselbe Frischekur + sortierte Finished-Liste. Effekt ab der naechsten Bot-Runde: Heim-/Auswaertsstaerke, Form und Torschnitt des laufenden Spieltags fliessen echt ein — der MasterBot sollte bald vor Rookie/Amateur landen. (Beachtlich bleibt: Bots spielen ohne Joker — Menschen holen mit x2-Multiplikator mehr Punkte pro Treffer — und bei erst 1-2 ausgespielten Spieltagen ist die Varianz hoch.)
- **Test:** +1 in tests/test_ai_opponent.py (vergiftete Cache + 6 fertige Spiele: neueste-5-Form muss exakt 5x W sein, der Müll aus der Cache nicht ueberleben). Teststand **301/301**, flake8-Hartgate sauber.
- **Deploy-FTP:** `ai_opponent.py`, `admin_bots_routes.py`. Hinweis: bereits abgegebene Bot-Tipps des laufenden Spieltags bleiben unveraendert (wie bei Menschen auch); erst die naechste Runde (Cron oder Admin -> "Bots tippen lassen") nutzt die frischen Statistiken.

## 2026-09-06 (5) - Rangliste: grüne Sparkline-Minigrafiken entfernt

- **Nutzerwunsch:** "Diese grünen Grafiken mag ich nicht und müssen nicht sein." Die kleinen SVG-Punkteverlaufs-Linien (.lb-sparkline, 60x20 px) hinter den Spielernamen in der Desktop-Rangliste wurden entfernt — Template-Block in `templates/leaderboard.html` raus, CSS-Regeln in `style.css` durch Kommentar ersetzt. Die ▲/▼-Trendpillen bleiben erhalten.
- **Test:** +1 `test_rangliste_ohne_sparklines` (Seite frei von lb-sparkline, Template frei vom Begriff, CSS ohne Selektor, .lb-trend weiterhin vorhanden). Teststand **302/302**, flake8-Hartgate sauber.
- **Deploy-FTP:** `templates/leaderboard.html`, `static/css/style.css` (beide ohnehin schon auf der 06.09.-Liste).

## 2026-09-06 (6) - KI-Bots können jetzt Joker setzen (Parität zu den Menschen)

- **Nutzerfrage:** "Warum kann ein Bot keinen Joker setzen?" Antwort: Es gab dafür keine Regel — die Bot-Tipps schrieben `joker=False` nur hartkodiert (ai_opponent.py, admin_bots_routes.py). Seit heute gilt Parität: **genau ein Joker pro Bot und Spieltag**, gesetzt auf den Tipp mit dem höchsten `joker_score` (Stärke-Differenz + Heimvorteil aus dem Statistik-Cache; der Score läuft über denselben Cache wie die Tipps, also ohne Extra-Queries). Der Rauschfaktor ist Charakter-getreu: EASY-Bots würfeln fast komplett, EXPERT (MasterBot) wählt gezielt. Punkte-Berechnung (x2), Ranglisten-Spalte "Joker" und Stats-Dashboard wirken automatisch mit.
- **Regeltreue:** ein bereits bestehender Joker am Spieltag (z.B. manuell per Bot-Reset-Korrektur) wird nie verdoppelt; "Tippen mit Überschreiben" hebt den alten Joker auf und setzt ihn frisch. Admin → Bots hat einen neuen Schalter "Bot-Joker" (Setting `bot_use_jokers`, Standard AN).
- **Tests:** +7 in neuen `tests/test_bot_joker.py` (Genau-ein-Joker pro Bot/Spieltag, pro Spieltag statt pro Saison, Bestandsschutz, Toggle, Admin-Route, place_bot_joker-Unit, Favoriten-Priorität des Scores). Teststand **309/309**, flake8-Hartgate sauber.
- **Deployment:** `ai_opponent.py`, `admin_bots_routes.py`, `routes_admin.py`, `templates/admin/bots.html`. Keine DB-Aenderung nötig (Prediction.joker existiert bereits). Bereits abgegebene Bot-Tipps des laufenden Spieltags behalten ihren Status; ab der nächsten Bot-Runde (Cron oder Admin) setzen die Bots ihre Joker.

## 2026-09-06 (7) - Bot-Runden: Crash-Isolation, NULL-Ergebnis-Haerte, Sichtbarkeit verpasster Runden

- **Anlass (Nutzerfrage):** "Der MasterBot hat keine Tipps für Spieltag 2 abgegeben?" Ursachen-Faecher im Code, alle gebannt: (1) Der h2h-Vergleich des EXPERT-Bots verglich auch finished-Spiele OHNE Ergebnis (z. B. das nicht ausgetragene Mainz-Gladbach-Spiel) -> TypeError; nur der MasterBot-Pfad betroffen. (2) Noch wichtiger: ein einzelner Bot-Crash warf die ganze Runde um, weil der Commit am Loop-Ende stand -> im Fehlerfall fehlten ALLEN Bots die Tipps. (3) `run_bot_tips` (Cron) tippt nur, wenn der Admin-Schalter "Auto-Tipp" an ist — stand er aus, blieb die Runde komplett ungetippt, bisher aber nirgends sichtbar.
- **Fixes (ai_opponent.py):** Statistik- und h2h-Queries ignorieren finished-Zeilen mit NULL-Ergebnis (`isnot(None)` bzw. Filter im Team-Stats-Loop); der get_tip-Aufruf laeuft pro Bot+Spiel in try/except — ein aussetzender Bot zaehlt nur `errors`, die anderen tippen weiter (Log-Fehlermeldung mit Bot/Spiel/Spieltag).
- **Sichtbarkeit (admin_bots_routes.py + templates/admin/bots.html + cron_jobs.py):** Bots-Seite zeigt neue Spalte "ST n" (Tipps pro Bot fuer den AKTUELLEN Spieltag); aktive Bots ohne Rundentipps werden rot markiert + Hinweistext mit Namen. Warnbanner erklaert zusaetzlich die Auto-Tipp-Voraussetzung (Plesk-Cron UND Schalter). Admin-Flash und Cron-Log melden jetzt Fehlerzahlen ("⚠️ N Bot-Fehler ... Details im Server-Log").
- **Test (tests/test_ai_opponent.py, +3):** NULL-finished-Spiel im h2h-Paar crasht keine Bot-Runde mehr; kuenstlicher Bot-Crash kostet nur diesen Bot (andere tippen + Joker); Admin-Seite zeigt "ST 1" + Warnung bei verpasster Runde. Teststand **312/312**, flake8-Hartgate sauber.
- **Deploy-FTP:** `ai_opponent.py`, `admin_bots_routes.py`, `cron_jobs.py`, `templates/admin/bots.html`. Laufende/abgeschlossene Spiele von ST2 koennen die Bots nachtraeglich NICHT mehr tippen (Anpfiff-Sperre wie beim Menschen) — ST2 bleibt fuer den MasterBot ohne Tipps; ab ST3 greift die runde Logik wieder.


## 2026-09-10 - Sync: Ersatz-Spiele uebernehmen, Tipps bleiben heil (Tippuebersicht ST 1)

- **Anlass (Nutzerfrage):** "Auf einmal fehlen drei Ergebnisse und die vergebenen Punkte bei Spieltag 1?" In der Tippuebersicht zeigten genau drei Spiele (FCB-VFB, ELV-B04, BVB-HSV) fuer ALLE User "—" bei vorhandenen Ergebnissen. Analyse: Die "—" sind kein Anzeigefehler und kein Sichtbarkeitsproblem - fuer diese Spielzeilen existieren schlicht keine Prediction-Zeilen mehr. Die einzige Stelle im System, die Tipps in Masse loescht, ist der Sync-Purge `sync_shared._purge_stale_matches_for_comp`: Liefert der Datenprovider fuer ein Spiel eine neue externe ID (Re-Keying), legt der Sync eine frische Ersatzzeile an, und der Purge loescht die Altzeile - inklusive samtlicher Tipps UND Kommentare aller Benutzer. Punktzahlen in Ranglisten taegten zusaetzlich.
- **Fix (sync_shared.py):** Purge-Verhalten geaendert: (1) Vor dem Loeschen einer Altzeile wird ein Ersatzspiel gleicher Ansetzung/Wettbewerb/Spieltag gesucht und dessen Tipps + Kommentare **umgezogen** (Punkte bleiben an der Prediction gespeichert, Konflikte: der neuere Tipp auf dem Ersatzspiel gewinnt). (2) Altzeilen ohne Ersatzspiel, an denen noch Tipps/Kommentare haengen, werden **nie** geloescht, sondern mit Warnung im Log behalten. (3) Detailzahlen landen in `LAST_PURGE_STATS`; Sync-Meldungen (football-data + OpenLigaDB) haengen "N Tipps zu Ersatz-Spielen umgezogen ..." an, Admin und Cron-Log sehen es damit sofort.
- **Sichtbarkeit (admin_integrity_routes.py):** Neuer Integritaetscheck "Beendete Spiele ohne Tipps": melde (warn) beendete Spiele des aktiven Wettbewerbs mit null Vorhersagen inkl. betroffener Spieltage - genau das Signatur-Muster dieses Vorfalls, das bisher unsichtbar war.
- **Tests:** +5 in `tests/test_sync_purge_tips.py` (Umzug Tipps+Kommentare, Punkte-Erhalt, Konfliktauflösung, Leeren-Purge bleibt, Keep ohne Ersatz) ; alter Test `test_purge_removes_stale_match_with_prediction_and_comment` auf neue Sicherheits-Politik umgeschrieben (erwartet jetzt Keep statt Delete). Suite 317/317.
- **Wiederherstellung (Produktion, einmalig):** Die am 10.09.2026 gemeldeten verwaisten Tippsaetze sind aus der DB geloescht - Restore nur aus einem DB-Backup (Netcup/Plesk-Backupplan) moeglich. Alternativ Tipps per SQL neu einsetzen (predictions-INSERTs, joker-Markierung falls beruehrt) und anschl. Admin -> Wartung -> "Punkte neu berechnen". Danach zaehlen Ranglisten wieder korrekt; die neuen Sync-Schutzregeln verhindern ein erneutes Verschwinden.


## 2026-09-10 (2) - Wartungscenter: "Tipps aus Backup retten" (gezielte Rueckholung nach Sync-Verlust)

- **Anlass (Nutzerfrage):** "Kann ich ein aelteres Backup einspielen, um die Tipps wiederherzustellen? Vom 01.09.-10.09. wurde je ein Backup angelegt." Klarstellung: ein Volleinspielen waere gefaehrlich (alles seit dem Backup-Stand - ST2-Tipps, Ergebnisse, Anmeldungen - waere weg). Noetig ist nur die Rueckholung der verwaisten Tippzeilen.
- **Neues Modul `tip_restore.py`:** Scannt die App-eigenen Tages-Backups (`backups/tippsspiel_*.db`, read-only, Dateinamen nur aus der Backup-Liste), findet Live-Spiele mit 0 Tipps (finished/live, aktiver Wettbewerb) und uebertraegt aus dem neuesten Backup mit passenden Spen­derzeilen (gleiche Ansetzung/Wettbewerb/Spieltag) die Predictions inkl. Kommentare auf die Live-Zeile (match_id wird gemappt). Idempotent: vorhandene (User,Spiel)-Tipps werden nie angefasst; Spender-Tipps unbekannter User uebersprungen; Joker nur wenn der User-slot am Spieltag in Live noch frei ist. Danach automatische Punkte-Neuberechnung + Leaderboard-Cache-Invalidate.
- **Bedienung:** Admin -> Wartung -> Karte "Tipps aus Backup retten": 🔍 Vorschau (read-only, listet Rettbares im Flash/Activity-Log) und 🧯 Restore ausfuehren (Bestaetigungsdialog). Kein SSH, kein SQL noetig.
- **Tests:** +6 in `tests/test_tip_restore.py` (Vorschau, Remap+Idempotenz+Joker-Unterdrueckung+Punkte-Recalc,aelteres Backup bei leerem neuerem, Teilbefuellung bleibt unangetastet, Fremd-User-Skip, Pfad-Schutz). Suite **323/323**.
- **Deploy (FTP + Plesk-Restart):** `tip_restore.py` (neu), `maintenance.py`, `templates/admin/maintenance.html`.


## 2026-09-10 (3) - Tippübersicht besser auffindbar: fester Navi-Punkt + mobiler Tab

- **Anlass (Nutzerwuunsch):** "Viele schauen sich die Tippuebersicht an, aber fuer einige ist sie schwer zu finden." Ursache: Der 👀-Link trug `hidden-desktop` und war damit in der Desktop-Hauptnavigation unsichtbar (nur Umweg ueber die Mehr-Seite); die mobile Bottom-Tabbar (Tippen/Rangliste/LIVE/Mehr) hatte ueberhaupt keinen Eintrag. Die PWA-Kurzverknuepfung existierte bereits.
- **Aenderung (templates/base.html):** Neuer Primär-Navigationspunkt "👀 Tipps" (Title-Tooltip erklaert die Anpfiff-Sichtbarkeit) direkt nach "Tippen" - auf Desktop UND im mobilen Menue sichtbar; der alte reine Mobil-Eintrag entfaellt. Die mobile Bottom-Tabbar bekommt einen eigenen "👀 Tipps"-Tab zwischen Tippen und Rangliste; aktiver Zustand wird wie ueblich markiert.
- **CSS (static/css/style.css):** `.bottom-tabbar` von 4 auf 5 Spalten (`repeat(5, 1fr)`), seitliches Padding 8px->5px fuer die zusaetzliche Spalte; Label-Groessen bleiben unveraendert (mobile-First).
- **Tests:** +4 in `tests/test_tip_overview.py` (Navi-Link ohne hidden-desktop inkl. Tooltip, 5-Spalten-Regel der Tabbar, aktiver Zustand auf /tipps, Manifest-Shortcut zeigt auf /tipps). Suite **327/327**.


## 2026-09-11 - Tippreminder-Banner: von der Vollbreiten-Warnleiste zur kompakten Pille

- **Anlass (Nutzerfeedback):** "Der lange Balken 'ungetippte Spiele' wirkt etwas unschoen in der App." Der Feature-B-Banner lief als randloser, klebriger Vollbreiten-Streifen unter der Navigation - Text links, Pfeil allein am rechten Rand; im Light-Theme als breites Gelb besonders wuchtig. Zusaetzlich enthielt die Template-Pluralbedingung zwei Leerzweige ("ungetippte[ ] Spiel[e]" mit toter 'n'-Regel).
- **Redesign (templates/base.html + static/css/style.css):** Der Banner wird eine zentrierte Pille: `width:min(calc(100% - 24px), 640px)`, Rand + Radius 999px + dezenter Schatten, zwei Zeilen (Titel + Countdown) kompakt. Statt des vereinzelten Pfeils sitzt rechts ein Action-Chip "Jetzt tippen →". Sticky bleibt (top: header + 8px), Urgent-Modus (roter Rand/Puls <1h vor Anpfiff) unveraendert; Hover mit leichtem Lift. Mobile: kleinere Paddings/Schriften via Media-Query. Plural jetzt korrekt: "1 ungetipptes Spiel offen" / "n ungetippte Spiele offen". app.js-Anker (id, data-kickoff, .urgent) bleiben exakt erhalten. aria-label am Link ergaenzt.
- **Tests:** +4 in `tests/test_tipreminder_pill.py` (Pille-Markup + Action-Chip, Singular/Plural deterministisch gegen Bootstrap-Demo-Spiele, Banner verschwindet nach Vollstaendigkeit, CSS-Anker ohne Vollbreiten-border). Suite **331/331**.


## 2026-09-11 (2) - Tippreminder-Pille: "Jetzt tippen" fuehrt jetzt in den Schnelltipp

- **Anlass (Nutzerfeedback):** ""Jetzt tippen" soll aber den Schnelltipp oeffnen" – die ganze Pille verlinkte bisher nur zum Spielplan.
- **Aenderung (templates/base.html + style.css):** Der Vollbreiten-Link wird zu einem Container <div> mit zwei getrennten Zielen: Text+Icon (.tr-main) fuehren weiterhin zum Spielplan des offenen Spieltags, der Action-Chip (.tr-cta, jetzt echter <a>) offnet /schnelltipp/<matchday>. app.js-Anker (ID, data-kickoff, .urgent) bleiben am Container; Hover/Fokus-Stile auf die Kinder umgezogen.
- **Tests:** 4 bestehende Tests in `tests/test_tipreminder_pill.py` auf die Zwei-Ziel-Struktur scharf gestellt (href-Assertions fuer /schnelltipp/3 und /spielplan/3). Suite **331/331**.


## 2026-09-11 (3) - Live-Center: OLB-Live-Boost fuer schnellere Tor-Anzeige

- **Anlass (Nutzerfrage):** "Im Live-Bereich dauert es einige Minuten, bis ein Tor angezeigt wird - geht das schneller?" Analyse der Kette: Client-Poll alle 30s -> /api/live/center ruft fetch_live_match_updates -> football-data mit 30s-Cache. Die Kette war schon ~30s-frisch; die Minuten-Latenz kam vom Provider selbst (football-data Free-Tier liefert Scores zeitverzoegert, Live-Scores waeren ein Paid-Feature).
- **Neu: `sync_openligadb.boost_live_from_openligadb()`** - OpenLigaDB (community-basiert, Bundesliga-Treffer quasi in Echtzeit) holt zusaetzlich die laufenden/begonnenen Spiele und schreibt aktuelle Staende + Status direkt in die DB. Regeln: (1) gar kein Upstream-Call, wenn kein Spiel im Zeitfenster (Anpfiff-20min bis Kickoff+3h15) - damit kostet der Boost ausserhalb von Spielen null; (2) Drosselung 1 Request / 20s, Redis-Cache bevorzugt, In-Prozess-Fallback `(_olb_boost_last_fetch)` falls der Cache deaktiviert ist; (3) Statusaenderungen ausschliesslich ueber `apply_match_update` (Monotonie-Schutz bleibt wirksam), finished Clears live_phase/minute; (4) Betroffene Spiele -> `recalculate_matches_points` + Badge-Check.
- **Einkopplung:** `fetch_live_match_updates()` (fd) faehrt den Boost nach seiner eigenen Verarbeitung undzaehlt `updated` zusammen; faellt fd ganz aus, liefert der Boost trotzdem (`ok=True` + `olb_boost`-Zaehler, im Live-Center-"Sync:"-String sichtbar). Client-Poll `live.js` 30s -> 20s (passt zum Boost-Fenster; Server drosselt, mehr Clients = kein zusätzlicher Provider-Verkehr).
- **Grenze (ehrlich):** Die Spielminute bleibt fd-Vorrang (OLB hat keine Minute), Anzeigeregeln aus 2026-09-05 (nur echte Feed-Daten, "≈"-Uhr nur als ausgewiesener Fallback) bleiben unveraendert.
- **Tests:** +6 in `tests/test_olb_live_boost.py` (Torschiene live, Drosselung ohne Redis, finished-Übergang inkl. minute-clear, kein Call ohne Fenster, Hook-Zusammenrechnung und fd-Ausfall-Pfad). Suite **336/336**.


## 2026-09-11 (4) - Echte Live-Spielminute optional gratis nachuesten (API-Football-Minute-Boost)

- **Anlass (Nutzerfrage):** "Die Spielminute geht nicht genauer, auch nicht ueber andere Dienste?" Recherche: Free-Tiers 2026 - Sportmonks (BL nur paid), TheSportsDB Live ab $9/Monat, football-data.org Live ab 12 EUR; der einzige dauerhaft kostenlose Feed mit echter Schiedsrichterminute (`elapsed`+`additional`) ist **API-Football (api-sports.io)**, Free-Plan 100 Requests/Tag.
- **Neu: `minute_boost.py`** - bedarfsgesteuerter Booster hinter `fetch_live_match_updates()`: Nur wenn jemand das Live-Center oeffnet UND ein Spiel im Fenster liegt, wird (min. 90s Abstand, tagesbudgetgedrosselt auf 90 von 100 mit auto-gestrecktem Intervall bis Mitternacht) `GET /fixtures?live=all` abgerufen. Treffer werden per Team-Token-Subset-Matching + Anstoss-Fenster (±12 min) zugeordnet; mehrdeutig => lieber keine Minute. 1H/2H/ET/BT/P -> live + echte Minute (OHNE "≈", da Feed-Datum), HT -> verbindliche Pause (live_phase=PAUSED), FT/AET/PEN -> finished inkl. Score-Korrektur und Uhr zuruecksetzen. Alles Statushafte ueber apply_match_update (Monotonieschutz), dann Punkte-Recalc + Badges.
- **Admin:** Settings -> APIs -> neues optionales Feld "API-Football Token" (leer lassen = Modul komplett inaktiv, Umgebungsvar APIFOOTBALL_TOKEN als Fallback in config.py). Statuszeile erklaert Budget und ≈-Rueckfall.
- **Ehrliche Grenze:** Ohne Token aendert sich nichts (≈-Uhr bleibt); mit Token kann das Tagesbudget an vollen Spieltagen frueher ausgehen - dann stiller Rueckfall auf die ≈-Uhr, nie eine eingefrorene Exakt-Anzeige. OpenLigaDB liefert weiterhin die Tore in ~20s, API-Football die echte Minute - die Kombination deckt "Tor schnell" und "Minute echt" ab, ohne dass ein Cent fliesst.
- **Tests:** +6 in `tests/test_minute_boost.py` (Minute ohne "≈", HT-Pause, FT-UhrReset, kein Token = kein HTTP, Drossel+Budget, fremde/mehrfach Treffer ignoriert). Suite **342/342**.


## 2026-09-12 (1) - CI #81 rot behoben: GitHub-Paket-Luecke + Frische-Gate

- **Befund:** Actions-Run #81 ("precise minute of play added") - Flake8/Security gruen, alle pytest-Jobs rot. Reproduktion im Sandbox-Klon: `AttributeError: 'SettingsForm' object has no attribute 'apifootball_token'` (tests/test_routes.py). **Ursache:** Das 04-Paket enthielt routes_admin.py mit neuem Feld, aber `forms.py`/`config.py`/`templates/admin/settings.html` standen nie auf der GitHub-Liste -> Repo-Kopie halb neu/halb alt. Live-Server war NICHT betroffen (Hotfix-Ordner enthielt alle 6 Dateien).
- **Fix 1 (Liste):** GITHUB_UPLOAD_FILES ergaenzt um forms.py, config.py, templates/admin/settings.html + docs/reparatur_tippverlust_st1.sql (Nachzigler aus 13). 04-Paket jetzt 45 Dateien.
- **Fix 2 (nie wieder):** Neuer `github_freshness_gate()` im Build: vergleicht jede code-relevante Runtime-Datei per Blob-Hash gegen GitHub main (git fetch + ls-tree) und meldet jede Abweichung, die nicht im 04-Paket steckt, vor dem Bauen. Zusaetzlich `verify_04.py`: klont main, packt das Paket drueber, faehrt pytest - exakt wie die Actions-CI.verify_04 lief nach dem Fix: **342/342 gruen auf Repo-Kopie + Paket** (12.09.2026).
- **Hausputz:** verify_04.py aus dem Runtime-Set genommen (nur Doku/Tests), Ursprungsremote im Workspace-Klon nachgeruestet.


## 2026-09-12 (2) - Tipp-Erinnerungen: zwei einstellbare Wellen

- **Anlass (Nutzerfrage):** "Wie war das mit den Remindern bei fehlenden Tipps - kann ich das aktivieren oder muss das jeder selber machen? Einige Spieler vergessen ihre Tipps." Befund: Zyklus laeuft bereits mit dem Cron (task=all -> run_reminders), Standard = einmal 1 h vor Anpfiff. Gewuenscht: "beides, aber einstellbar" (zweite Welle + globaler Vorlauf).
- **Neu (notification_center.py):** Wellen-Konzept. Welle 1 (kurz vor Anpfiff) respektiert die Profil-Vorlaufzeit des Spielers; der Admin kann mit `reminders_force_lead_hours` einen globalen Standard (`reminders_lead_hours`, 0-24 h) fuer alle erzwingen. Welle 2 (Vorwarnung) sendet zusaetzlich `reminders_second_lead_hours` (1-168 h) vor Anpfiff an alle - eigenes Versand-Log (`kind="match_reminder_w2"`), blockiert Welle 1 nicht und wird pro Spiel nur einmal ausgeloesst. Master-Schalter `reminders_enabled` bleibt oben drauf; manuelle Admin-Erinnerungen (Offene-Tipps-Seite, Test-Button) versenden weiterhin unabhängig vom Fenster (enforce_window opt-in nur im Zyklus).
- **Eligibility:** `upcoming_reminder_matches()` erweitert das Abfragefenster auf den groessten aktiven Wellen-Vorlauf (bis 168 h); die user-genaue Fensterpruefung (`_window_hit`, +5 min Toleranz wegen 15-min-Cron) sitzt jetzt im Versand statt in der Match-Auswahl. `run_reminder_cycle(channels, now=None)` gibt `wave1`/`wave2`-Zaehler zurueck (Heartbeat-Details).
- **Admin-UI:** Einstellungen -> "Tipp-Erinnerungen": vier neue Felder (Welle-1-Vorlauf, Force-Schalter, Welle-2 an/aus [Standard an], Welle-2-Vorlauf) mit Beschreibungen; Werte clampen beim Speichern.
- **Test-Fix:** `tests/test_notification_bulk.py::test_upcoming_reminder_matches_respects_user_windows` auf die neue Architektur umgeschrieben (Fensterpruefung im Versand, nicht mehr in der Spielauswahl). Neu: `tests/test_reminder_waves.py` mit 4 Tests (Vorlauf-Aufloesung/Force/Clamps, beide Wellen mit getrennten Logs, Dedup zweiter Zyklus, Welle-2 aus + manueller Versand, Master aus). Hinweis aus der Debug-Runde: Objekte NACH Update innerhalb derselben Test-Session koennen ueber die Identity-Map veraltet erscheinen - Tests arbeiten deshalb mit frischen Matches statt Updates.
- Suite **346/346**.


## 2026-09-12 (2) - Spielinfos mit echtem Mehrwert: Stadion + Torschuetzen

- **Anlass (Nutzerfrage):** "Kann man eventuell noch eine Info zu Spielen einbauen, die einen echten Mehrwert bietet?" Recherche: OLB-Event-/Goals-Endpoints leer bzw. 404 (live geprueft), football-data Player-/Scorer-Daten nur gegen Bezahlung. Uebrige echte Gratis-Perlen: das venue-Feld im ohnehin geladenen Match-Payload und die goals[] im API-Football-Free-Plan (Token dafuer wird bereits fuer den Minute-Boost angeboten).
- **Neu 1 - Stadion:** `Match.venue` (neue Spalte + Schema-Migration `2026_09_12_001_match_venue`); der fd-Sync persistiert `md["venue"]` (leere Payloads loeschen Bestand nicht). Match-Detail zeigt eine dezent-grau Pill "📍 Allianz Arena" neben dem Wetter-Pill.
- **Neu 2 - Goal-Boost (`minute_boost.boost_goal_scorers_from_apifootball()`):** Nach beendeten Spielen (Kickoff <= jetzt, <= 2 Tage alt) holt EIN Fetch `/fixtures?league=..&season=..&last=9` die Torschuetzen (Schuetze, Vorlage, Minute+Nachspielzeit, Elfmeter/Eigentor) und legt sie als JSON (`kind:"gf"`) in `Match.events` ab - sortiert, dedup-faehig, Fremdformate (live_scoring-Legat) werden nie ueberschrieben. Eigener Budgetwaechter: min. 10 min Abstand, max. 8 Calls/Tag (zusammen mit Minute-Boost <= 98 von 100). Ohne API-Football-Token: kein Request, keine Anzeige - reines Bonusfeature.
- **Anzeige:** Match-Detail bekommt einen "⚽ Torschuetzen"-Block (Zeile pro Tor: Minute, Kuerzel Heim/Auswaerts, Spieler, Elfmeter-/Eigentor-Zusatz, Vorlage). Live-Center/Schnelltipp bleiben unveraendert schnell.
- **Nebenbefund behoben:** app.py laeuft beim Start jetzt `run_pending_migrations()` direkt nach `db.create_all()` - ohne das haette jeder Deploy mit neuen Spalten (Netcup wie Test-Datei-DB) mit "no such column" gebrannt (im Testlauf exakt so aufgetreten und gefixt).
- **Tests:** +5 in `tests/test_match_info_venue_goals.py` (venue persist + Erhalten bei leerem Payload, Goals sortiert inkl. Elfmeter/Eigentor/Seite, kein Token = kein HTTP, Fremd-events unangetastet + kein Call, 2H-Payload wird ignoriert, Detail-Rendering mit Venue + Torschuetzen-Zeilen). Suite **351/351**.


## 2026-09-12 (3) - Torjaeger-Rangliste (Torschuetzenliste)

- **Anlass (Nutzerwunsch):** "die Torjaeger Rangliste haette ich gerne noch" - zusaetzlich als Hilfe fuer die Sonderfrage "Torschuetzenkoenig".
- **Neues Modul `top_scorers.py`:** holt die offizielle Top-Scorer-Liste von API-Football (`GET /statistics/league/top_scorers`, dauerhafter Free-Plan, derselbe optionale Key wie Minute-/Goal-Boost). Ergebnis liegt als JSON im Setting-Cache `top_scorers_data` (keine neue Tabelle). Parsing: Tore, Vorlagen, Elfmeter getroffen/verschossen, Einsaetze, Minuten; Spieler ohne Tor werden gefiltert; Sortierung Tore desc, Name asc; Top 20.
- **Budgetwaechter:** eigener Gate - fruehestens alle 6 h, max. 2 Abrufe/Tag; zusammen mit Minute- (<=90) und Goal-Boost (<=8) damit immer <=100 Calls/Tag des Free-Plans. Ohne Token: kein Request, Seite zeigt Erklaertext statt Leiertabelle. Abruffehler behalten den letzten Erfolgs-Cache (Seite nie kaputt).
- **Auto-Aktualisierung:** Hook in `sync_results()` (Cron-Sync und Admin-Sync-Button) - bewusst VOR den FD-/OLB-Netzwerken, laeuft auch bei Sync-Stoerungen. `force=True` (Intervall-Skip) ist vorbereitet, falls spaeter ein Admin-Button gewuenscht wird.
- **UI:** neue Seite `/torjaeger` (login_required) mit Ranglisten-Tabelle (Bild, Name, Team-Kuerzel via DB-Matching, Tore inkl. Elfmeter-Zusatz, Vorlagen, Einsaetze; Fuehrender leicht hervorgehoben), Stand-Zeitstempel, Karten-Einstieg "🥇 Torjaeger" auf der Mehr-Seite. Mobile-first, keine externen Assets ausser Spielerfotos (wie ueblich optionale CDN-Bilder mit Initial-Fallback).
- **Tests:** +6 in `tests/test_top_scorers.py` (Parse/Sort/Cache, Throttle + Budget + no-token, Listing traegt Fremdfehler den alten Cache weiter inkl. Team-Kuerzel, Seiten-Rendering mit Elfer-Hinweis und "kein Tor = nicht gelistet", Hinweis-Karte ohne Daten, Sync-Hook ruft Refresh genau einmal). Suite **357/357**.


## 2026-09-12 (4) - API-Football im Admin sichtbar machen (Folge des Torjaeger-Wunsches)

- **Anlass (Nutzerfrage):** "hier fehlt doch noch API-Football, oder?" - Der Key war technisch langst andockbar (Feld in Admin -> Einstellungen -> "🌐 APIs", Save/Read-Pfade vorhanden); das Sektions-<details> blieb aber zugeklappt, das Label nannte nur "Live-Minute", und der Status-Hilfetext aus Runde 19 war sprachlich beschadigt ("wird allgaetlich gebohst", kaputte Anfuehrungszeichen).
- **Fix:** API-Abschnitt offnet sich jetzt auch, wenn der API-Football-Key fehlt (Badge "ℹ Free-Key empfohlen", inaktiv-Optik statt Warnrot - es bleibt optional). Hilfetext repariert und benennt alle drei Free-Key-Funktionen (echte Live-Minute, Torschuetzen im Spielbericht, Torjaeger-Rangliste) inkl. gemeinsamem Budget (≤ 100 Calls/Tag) und "Key holen"-Link zu api-football.com. Formular-Label entsprechend erweitert.
- **Kein Funktionscode geaendert** - nur Admin-UI-Beschriftung/Hilfe. Suite bleibt **357/357**; flake8-Gate OK.


## 2026-09-12 (5) - API-Football im Admin-Dashboard sichtbar (Checks + letzte Abrufe)

- **Anlass (Nutzer-Screenshot):** Admin -> API Sync zeigte football-data/OLB-Checks und "Letzter Sync", aber vom dritten Datenstrang (API-Football-Key) fehlte jede Spur - obwohl der Key laengst eingetragen war.
- **Neu:** Aktivitaetsprotokoll Setting `apifootball_activity` (JSON): jeder ECHTE HTTP-Versuch (Erfolg wie Fehler, nie gedrosselte) hinterlaesst Zeitstempel + Status + Kurznotiz je Feed-Typ minute/goals/torjaeger; `record_apifootball_activity()` + `apifootball_activity_summary()` in minute_boost.py, aufgerufen von Minute-Boost, Goal-Boost und top_scorers.
- **Admin -> API Sync:** neuer Check-Kachel-Eintrag "API-Football Token (optional)" (fehlender Key = ℹ️, kein ⚠, bleibt schliesslich optional) + neue Karte "API-Football · Booster": Key-Status, letzter Abruf je Feed (Zeit UTC + Ergebnis/Notiz) und "Heutiger Verbrauch x/90 · y/8 · z/2" direkt aus den Budget-Gates (Cache- oder Prozess-Fallback). Warnungszeile, wenn der optionale Free-Key fehlt.
- **Haertung:** Die Karte liest das Diagnostic-Dict defensiv (fehlende/veraltete Schluessel kippen die Admin-Seite nicht - abgesichert durch den bestehenden Test mit gemocktem Alt-Diag). get_sync_diagnostics liefert zusaetzlich "apifootball".
- **Tests:** +3 in `tests/test_apifootball_admin_status.py` (Record-Roundtrip + Notiz-Kirzung, Erfolgs- und HTTP-401-Pfad werden protokolliert + Budget-Zaehler getrennt, Diagnostics/Seite mit und ohne Key). Suite **360/360**.


## 2026-09-12 (6) - Versuche je Datenquelle im Admin-Dashboard (fd/OLB inklusiv)

- **Anschluss an (5):** auf Nachfrage auch football-data.org und OpenLigaDB ins Protokoll - gemeinsamer Speicher `datasource_activity.py` (ein Setting-JSON; Eintraege football-data | openligadb | minute | goals | torjaeger), protokolliert NACH echt stattgefundenen HTTP-Versuchen (Erfolg wie Fehler, Grund als Notiz). Die API-Football-Recorder nutzen jetzt denselben Speicher (Wrapper bleibt API-kompatibel).
- **Sync-Pfad:** `sync_results()` protokolliert den FD-Versuch und - falls der Fallback greift - den OLB-Versuch; die Aggregat-Zeile "Letzter Sync" bleibt unveraendert bestehen.
- **Admin -> API Sync:** neue Tabelle "Versuche je Quelle" unter "Letzter Sync" (Zeit UTC + ✅/⚠️ + Fehlergrund; neutrale "noch nicht protokolliert"-Zustand, kein Alarm-Look). Diagnostics-Dict erhaelt `source_activity`;aeltere/gemockte Diags (ohne den Schluessel) rendern die Karte unveraendert - durch den bestehenden Alt-Diag-Test abgesichert.
- **Tests:** +2 in `tests/test_apifootball_admin_status.py` (fd-Fehler + OLB-Fallback-Grund landen im Protokoll; Seite zeigt Fehlerzeile + neutrale Zeilen), Recorder-Tests auf gemeinsamen Speicher umgestellt. Suite **362/362**; Frische-Gate um `datasource_activity.py` ergaenzt, verify_04 gruen (04-Paket 58 Dateien).


## 2026-09-12 (7) - Torjaeger-Endpoint korrigiert + echte Fehlergruende im Protokoll

- **Anlass (Nutzer-Screenshots nach Deploy):** Admin-Karte zeigte "⚠️ Torjaeger-Liste · API-Meldung (Key/Limit pruefen)", waehrend das api-sports-Dashboard nur 1/100 Requests zeigt. Diagnose: generischer Platzhaltertext verbarg den echten Grund - und der Grund war ein Fehler auf UNSETER Seite: verwendet wurde /statistics/league/top_scorers, offiziell laut Doku ist **GET /players/topscorers?league=..&season=..** (12.09.2026 gegen die API-Football-Dokumentation verifiziert). Der Endpunkt liefert exakt dasselbe Response-Format (player + statistics[]), der Parser blieb unveraendert.
- **Besser protokolliert:** neue Helper `af_errors_text()` verdichten das API-Fehlerfeld (dict/list) zu lesbarem Text; minute/goals/torjaeger schreiben jetzt den ECHTEN API-Grund ins Versuchsprotokoll statt "Key/Limit pruefen". Damit Erklaert der Screenshot-Fall sich selbst, waere er bereits geloggt gewesen.
- **Selbstheilend:** nach einem FEHLgeschlagenen Torjaeger-Versuch erlaubt das Gate den naechsten schon nach 30 Minuten (Erfolg bleibt beim 6-h-Rhythmus) - binnen des Tagesbudgets (2). Ein kaputter Aufruf "bestraft" den Feed nicht mit einem halben Tag Pause.
- **Tests:** URL-Assertionen auf den korrigierten Endpunkt gezogen; +1 Test (echter Fehlertext landet im Protokoll, Drossel direkt danach, Retry nach 40 min erlaubt, Erfolgspa drosselt weiter). Suite **363/363**.


## 2026-09-12 (8) - Plan-Absagen von API-Football: Feed pausiert, Grund sichtbar

- **Anlass (Nutzer-Log nach Deploy):** Die neue Versuchs-Tabelle lieferte den echten Grund fuer die leere Torjaeger-Liste: `Free plans do not have access to this season, try from 2022 to 2024` - API-Football schraenkt Statistik-/Saison-Endpunkte im Free-Plan auf vergangene Saisons (laufende 2026/27 gesperrt). Endpoint und Key waren also korrekt; es ist eine Plan-Grenze der API.
- **Neu - Plan-Bremse:** erkennen alle drei API-Football-Feeds (minute/goals/torjaeger) an einem "plan"-Stichwort im Fehlerfeld und pausieren den betreffenden Feed bis zum Folgetag (Setting `apifootball_plan_block`, tageweise). Pro Tag bleibt 1 Probelauf - kein Budget-Verbrennen gegen eine klare Absage, automatische Wiederholung, falls der Plan sich aendert.
- **Neu - Ehrlichkeit auf /torjaeger:** ohne Daten zeigt die Seite jetzt den letzten echten API-Grund inkl. Zeit des Versuches (aus dem Versuchsprotokoll), statt nur "noch keine Daten".
- **Doku-Hinweis im Admin:** API-Football-Statustext erwaehnt die Saison-/Plan-Grenze und verweist auf Admin -> API Sync.
- **Einordnung fuer die Sonderfrage "Torschuetzenkoenig":** aktuelle Torschuetzenlisten sind damit aus KEINER der zwei eingebundenen Gratis-Quellen befüllbar (fd: Scorer nur Paid; API-Football Free: letzte Saison gesperrt). Optional gegen laufende Kosten: API-Football Standard-Plan; bewusst NICHT eingebaut (Kosten-Regel des Projekts). Live-Minuten bleiben unberuehrt, solange /fixtures?live=all im Free-Plan zugelaesst bleibt (kein Saison-Parameter) - sollte auch das abgewiesen werden, greift dieselbe Plan-Bremse.
- **Tests:** +2 (Plan-Absage pausiert Feed + Grund im Protokoll; Seite zeigt Grund + Selbstheilungs-Hinweis), Counter-Fix im Test. Suite **365/365**.


## 2026-09-12 (9) - Sync-Diagnose für die Stadion-Info

- **Anlass (Nutzer-Screenshot):** Migration `2026_09_12_001_match_venue` war um 11:03 gelaufen, aber auf der Match-Detailseite erschien keine 📍-Pille. Von aussen nicht unterscheidbar: liefert football-data im Free-Plan überhaupt `venue`-Werte (anonym ist der Zugriff 403), oder fehlt ein deploytes Datei-Update?
- **Fix - Selbst-Diagnose:** `_process_football_data` zaehlt jetzt pro Sync-Lauf, wie viele Spiele der Feed MIT Stadionangabe geliefert hat, und haengt es an die Sync-Meldung an: "✅ football-data.org: 0 neu, 306 aktualisiert, 0 live · 📍 0 mit Stadionangabe". Damit entscheidet ein Blick auf Admin -> API Sync über die Ursache: Zahl >0 ohne Pillen = Template/Deploy-Lücke; Zahl 0 = die API liefert keine Stadien (dann bleibt die Pille hohl und der Ball bleibt bei football-data bzw. einem Spaeter-Upgrade).
- **Kein Verhalten geaendert** - nur Messaging + Zaehler (`venues` im Ergebnis-Dict). Test erweitert (1 mit / 0 mit Stadionangabe über zwei Sync-Laeufe). Suite **365/365**.


## 2026-09-12 (10) - Heimstadien als Festdaten (Pille fuellt sich trotz Free-Plan)

- **Diagnose steht (Nutzer-Log):** "📍 0 mit Stadionangabe" - football-data liefert im genutzten Plan kein `venue`, OLB ebenso nicht (live geprueft). Die Sync-Pille blieb daher datenlos leer.
- **Loesung - neues Modul `stadiums.py`:** kuratierte Heimstadium-Karte (Name -> Stadion) fuer die 18 Erstligisten 2025/26 (Wikipedia/stadion.de, 12.09.2026 gegengeprueft) plus stabile Zweitliga-/Absteiger-Namen (u.a. Holstein-Stadion, Vonovia Ruhrstadion, Fritz-Walter-Stadion). Normalisierung inkl. Umlautkonvertierung (Moenchengladbach/Duesseldorf/Nuernberg - erste Version hatte genau dort Luecken, im Test gefangen).
- **Sync-Regel:** Feed-Wert hat IMMER Vorrang; die Karte fuellt ausschliesslich echte Luecken (neues Match ohne Feed-venue oder Bestand leer). Auswaertsteams werden nie belegt. Unbekannter Verein -> Feld bleibt leer (kein Schaetzen). Kein Ueberschreiben bei Folgesyncs (2. Lauf mit stiller API laesst "Speicher XI" stehen - getestet).
- **Diagnose-Meldung nachgezogen:** "📍 Stadion: n aus Feed, m aus Festdaten" - damit bleibt unterscheidbar, woher Werte kommen; `venues`/`venues_map` im Sync-Ergebnis.
- **Import-Absicherung:** `sync_football_data` importiert die Karte with try/except ImportError - wer beim FTP nur das alte Sync-File erwischt, laeuft ohne Stadion-Fallback weiter (kein Crash).
- **Tests:** +3 (`tests/test_stadiums_map.py`: Lookups inkl. Umlaut-Faelle, Sync-Backfill/Feed-Vorrang/Zweitlauf-Heiligung, Stille bei Unbekanntem). Suite **368/368**.


## 2026-09-12 (11) - Stadion-Pille mit Google-Maps-Link

- **Nutzerwuenschen:** "Kann man beim Stadion ein Google Maps Link hinterlegen?" - Ja, ganz ohne API-Key/Sprechpartner-Komplikation: Der offizielle Maps-Suchlink (https://www.google.com/maps/search/?api=1&query=..) funktioniert schluessellos, Desktop wie Mobil (Mobilapp-Sprung inklusive).
- **Umsetzung:** `stadiums.maps_url(venue, club)` haengt den Vereinsnamen als Kontext an die Arena-Suche an (Sponsortitel wie "MEWA Arena" treffen so eindeutig) und escaped den Query-String korrekt. Match-Detail rendert die Pille als <a target=_blank rel=noopener noreferrer> mit kleinem ↗ und Hover-Framework; ohne Link (kein Stadion hinterlegt) bleibt alles wie bisher reiner Text. Fehler im URL-Bau faehrt die Pille harmlos auf Text zurueck.
- **Tests:** +1 (maps_url-Format inkl. Escape-Faellen), Rendering-Test um Link-Nachweis erweitert (Jinja escaped & -> &amp;, Test kennt jetzt die HTML-Schreibweise). Suite **369/369**. Nebenbefund: sed-Ersatz mit & im Suchmuster hatte die Testdatei beschadigt - ueber Python sauber repariert, alle Tests erneut gruen.


## 2026-09-12 (12) - Kompass-Icon fuer Direkt-Routing neben der Stadion-Pille

- **Anlass:** Nutzerentscheid "b)" aus der Erklaerung zum Maps-Link: Pille bleibt die universelle Stadion-Suche (Steckbrief, FOTOS, "In der Naehe -> Parken"), ein kleines **🧭-Piktogramm** direkt daneben springt per `maps/dir/?api=1&destination=..` ohne Zwischenschritt ins **Sofort-Routing** (Startort = aktuelle Position, Freigabe regelt Maps selbst).
- **Umsetzung:** `stadiums.maps_route_url()` (Query identisch zur Suche inkl. Vereins-Kontext, damit Sponsortitel treffen), Context-Variable `venue_route_url` in der Detail-Route (gleiche try/except-Heilung: ohne URL rendert die Pille als Text weiter), runde Mini-Schaltflaeche im Pillen-Design (hover-Akzent), `aria-label` fuer Screenreader.
- **Tests:** +1 (dir-URL-Format/Escape/None-Faelle), Rendering-Test prueft jetzt beide Links (Suche + `maps/dir/?api=1&destination=Allianz%20Arena`). Suite **370/370**.


## 2026-09-12 (13) - Aufsteiger-Luecke: Elversberg/Paderborn/Schalke mit Stadion + Wetter

- **Anlass (Nutzer):** "bei Elversberg wird kein Stadion und kein Wetter angezeigt". Blick in die Saisonrealitaet (OLB live): BL1 2026/27 spielt mit **SV 07 Elversberg, SC Paderborn 04 und FC Schalke 04** - die drei Aufsteiger fehlten in BEIDEN statischen Karten (Wetter-Koordinaten nur 18er-Stand 2025/26, Stadionkarte analog).
- **Wetter (`stats_live.py`):** drei neue Koordinaten (Ursapharm-Arena an der Kaiserlinde, Home Deluxe Arena, VELTINS-Arena - Namen gegengeprueft am 12.09.) + generischer **Namens-Fallback** `_coords_for_team()`: erst Kuerzel-Lookup, bei fremdem TLA zaehlt der Vereinsname (21 Keywords) - damit fuehrt eine anders geschriebene Feed-Abkuerzung nie wieder zum kompletten Wetter-Ausfall eines Vereins.
- **Stadion (`stadiums.py`):** drei Eintraege nachgezogen (Pille + Maps-/Routing-Links funktionieren damit automatisch).
- **Tests:** +1 Stadion-Lookup Aufsteiger, +4 Wetter (`tests/test_stadiums_weather.py`: Direkt-Treffer, TLA-Fremdschreiblaeue faellt auf Namen zurueck, Unbekanntes bleibt leer, Einfallstor-Test "Code in BEIDEN Karten"). Suite **375/375**.


## 2026-09-12 (14) - Fruehwarnung "Festdaten-Luecke" (Sync-Meldung + Admin-Zeile)

- **Anlass:** Frage "Wie laeuft das bei neuen Aufsteigern?" - Antwort war: lautlos. Das aendert diese Runde.
- **Sync:** `_process_football_data` sammelt jetzt Heimteams, die WEDER vom Feed (venue) noch von der statischen Karte abgedeckt sind (dedupliziert, max. 12). Meldet sie in der Sync-Zeile an: "... - Stadion: 0 aus Feed, 153 aus Festdaten - 🛈 ohne Stadion-Karte: SV 07 Elversberg, SC Paderborn 07 …" und persistiert die Liste als Setting `stadium_gap_teams` (JSON, ensure_ascii=False). Der JEWEILIGE letzte Lauf schreibt - nach Karten-Pflege + Sync heilt die Anzeige von selbst (im Test belegt: 2. Lauf -> "[]").
- **Admin-Seite `/admin/sync`:** kleine Zeile "🛈 Festdaten-Pflege: <Namen> ohne Stadion-Karte – hier bleiben Pille und Wetter leer. Je ein Eintrag in stadiums.py und stats_live.py, nach dem nächsten Sync ist diese Zeile weg." Bewusst Info-Look (kein ⚠️ - Pflegezustand, kein Fehler, gemäß Admin-Sicht-Regel). Defekter Setting-Wert degradiert still auf [].
- **Tests:** Sync-Seite erweitert (Fehlliste, msg-Suffix, Persistenz, Selbstheilung) + neue `tests/test_stadium_gap_watch.py` (3: Zeile sichtbar, nach Pflege weg, kaputter Wert lautlos). Suite **378/378**. Nebenbefund: .venv-Restore war diesmal nur ein Rumpf (pip-Grund, requirements-Zeilen mit CR) - mit /tmp-Datei und tr -d \r sauber neu gebaut.


## 2026-09-13 (15) - Combo-Pille: Stadion-Suche + 🧭-Routing in einer Zeile

- **Nutzerfeedback:** "Mit der Routing Pille werden im Smartphone-Modus jetzt zwei Zeilen angezeigt. Das ist unschön." Ursache: Pille und Kompass waren zwei eigene Flex-Items im Badges-Container (`flex-wrap: wrap`) - bei schmalem Viewport brach der Kompass um.
- **Loesung:** Beide Links stecken jetzt in EINER gemeinsamen Huelle `.tu-venue-combo` (Rahmen/Hintergrund nur noch aussen, innen duenne Trennlinie). Garantiet gegen Umbruch zusaetzlich: `white-space: nowrap` + `max-width: 100%`, und der Arena-Text laeuft bei Platznot mit Ellipse aus (`.tvp-text`, ↗-Pfeil via `flex:none` gesichert) - auf dem Smartphone also z.B. "📍 Stadion An der Alten Först…" statt zweiter Zeile; antippen bleibt beides getrennt (Text = Suche, Kompass = Direkt-Routing).
- **Tests:** +1 Struktur-/CSS-Test (Combo genau einmal im Template; nowrap/overflow/Ellipse in der CSS). Rendering-Tests bleiben groen, da "📍 Allianz Arena" zusammenhaengig im Text-Span steht. Suite **379/379**.


## 2026-09-13 (16) - Badges-Zeile endgueltig einzeilig (Combo + Wetter)

- **Nachzieh-Feedback:** "Es sind immer noch zwei Zeilen zusammen mit dem Wetter" (Screenshot). Die Combo-Pille war intern einzeilig, aber Container `.tu-top-badges` durfte weiter umbrechen -> Wetter-Pill rutschte als zweites Flex-Item in Zeile 2.
- **Fix (nur CSS, eine Datei):** `.tu-top-badges` auf `flex-wrap: nowrap` + `overflow:hidden`; Status-Badge und Wetter-Pille `flex:none` (nie schrumpfbar), Stadion-Combo `flex:0 1 auto; min-width:0` - uebrigem Platz fehlt, kuerzt ausschliesslich der Arena-Text zur Ellipse ("📍 Stadion An der Alten Först…"). Combo-los-Fallback (reine Text-Pille) analog schrumpfbar gemacht. Container wird ausschliesslich im Match-Detail genutzt, keine Nebeneffekte.
- **Tests:** Combo-/Einzeiligkeits-Test erweitert (nowrap im Container, flex:none an Wetter+Status, Ellipse-Anker bleiben); Suite **379/379**. Nebenbefund: .venv-Rumpf erneut (bewusster guarded-Rebuild mit CR-Bereinigung) und ein vom eigenen Patch entfernter Test-Lookup (`at`) - ergaenzt, alles gruen.


## 2026-09-13 (17) - Status wandert zur Anpfiff-Zeile: Badges gehoeren Stadion + Wetter

- **Nutzerfeedback:** Nach dem Einzeilig-Fix war der Stadionname nur noch "Allia..." zu erahnen - Vorschlag "Passt das Geplant nicht besser neben Datum und Uhrzeit?" - ja, genau so.
- **Umsetzung:** Status-Pill (geplant/LIVE/Endstand) sitzt jetzt IN der Anpfiff-Zeile (.tu-kickoff-row hinter "Uhr"); die Badges-Zeile enthaelt nur noch Stadion-Combo + Wetter und bekommt dafuer die volle Kartenbreite. Zusaetzlich: sind weder Stadion noch Wetter vorhanden, faellt die Badges-Zeile gleich ganz weg (kein Leerstreifen). CSS-Einzeilig-Regeln bleiben als Sicherheitsnetz (lange Namen wie "Stadion An der Alten Foersterei" koennen auf sehr kleinen Geraeten immer noch ellipseieren); die nun gegenstandslose Regel .tu-top-badges .status wurde entfernt.
- **Tests:** +1 Strukturtest (Kickoff-Zeile vor Badges, Status nicht mehr darin, Badges nur bei Inhalt), Einzeilig-Test auf neue Lage gezogen. Rendering-/Live-Tests unveraendert groen (Markup nur verschoben). Suite **380/380**.


## 2026-09-13 (18) - Admin-Sync-Seite aufgeraeumt: 2 Karten statt 3, keine Doppelmeldung

- **Anlass (Nutzer-Screenshot):** "Kannst du hier aufräumen und besser strukturieren?" - die Seite zeigte dreimal dasselbe: Booster-Karte mit 3 API-Football-Zeilen, darunter die Versuche-Tabelle mit exakt denselben 3 Zeilen, dazu die Sync-Meldung identisch in "Letzter Sync" UND in der fuellenden Tabelle; ausserdem rohes ISO "2026-09-13T10:30:03.218724+00:00".
- **Neue Struktur:** "Sync-Lauf" (Status + lokal lesbare Zeit + Zaehler + Stadion-Aufteilung + Fehlliste, alles aus den strukturierten res-Feldern - die rohe msg nur noch bei Fehlern) und "Datenquellen" (EINER Tabelle fuer alle fuenf Feeds mit Status/Zeit/Grund; Key-Zustand und Tagesverbrauch als Caption/Fußnote; football-data-Zeile zeigt ihre Sync-Meldung nicht erneut, wenn der Sync-Lauf-Karte sie schon zeigt - Feinfilter nur bei ok==True). Booster-Karte und Versuche-Tabelle entfallen als eigene Bloecke.
- **Zeitformat:** neuer Helper `sync._fmt_utc()` (ISO -> '13.09.2026 10:30 Uhr UTC', kaputte Werte auf rohen Anfang zuruck) fuer last_sync und alle Activity-Eintraege (at_fmt).
- **Nebenbefund:** Erster Splice-Versuch landete im falschen Endanker (index traf das Title-{% endblock %} in Zeile 2) und beschaeftigte das Template - sauber aus den bekannten Stuecken neu aufgebaut, danach grep-Kontrolle (1x content-Block, 3x h2). Tests an neue Begriffe gezogen statt stumm geloescht. Suite **380/380**.


## 2026-09-13 (19) - Torjaeger-Liste keyfrei gemacht: Quelle gewechselt auf OpenLigaDB

- **Anlass:** "Gibt es evtl. noch eine andere kostenlose Datenquelle fuer die Torjäger? Wenn nicht, kann Torjäger aus Mehr entfernt werden." Recherche: **OpenLigaDB `GET /getgoalgetters/{bl1|bl2}/{saison}`** liefert die aktuelle Torschuetzenliste (live verifiziert 13.09., Name+Tore) - die Alternative zum Remove. API-Football war weiterhin nur bis 2024 gut (Free-Plan), football-data Scorer = Bezahltier, TheSportsDB ohne Saison-Scorer-Aggregat.
- **top_scorers.py komplett neu (Cache-Geruest bleibt):** einzige Quelle jetzt OLB, keyfrei; Parsing goalGetterName/goalCount (Tore desc, Gleichstand alphabetisch, Top 20, torlos raus); Takt 30 min statt 6 h (OLB hat kein Konto), Fehler-Retry nach 10 min; CACHE_VERSION 2 verwirft das alte API-Football-Schema; kein Plan-Gate, kein `apifootball_token`, keine Vorlagen-/Einsatz-Spalten mehr. Sync-Hook in sync_openligadb heisst jetzt `_refresh_top_scorers_hook()` (Testbarkeit, unveraendert lautlos).
- **Nebeneffekte:** Torjaeger zaehlt nicht mehr zum API-Football-Budget (minute_boost summary + sync.html-Verbrauchszeile ohne Torjaeger-Segment; Aktivitaet laeuft weiter ueber den gemeinsamen Quellen-Speicher, Label "OpenLigaDB · Torjäger-Liste"), settings.html-Texte korrigiert (Key nur noch fuer Minute/Torschuetzen noetig), Seite ohne API-Football-Erwaehnung.
- **Tests:** test_top_scorers.py neu geschrieben (7: Parsing/Sort, keyfrei, Takt+Fehler-Schnellretry, Cache-Ehrlichkeit bei 503, Seite mit/ohne Daten, Hook-Fehlerresilienz); af-Status-Tests auf goals-Planbremse + geteilten Speicher umgezogen. Ein Assertions-Wortkrieg entpuppte sich als eigener Tippfehler ("nächster" vs. Template "der nächste"). Suite **381/381** (7 Tests neu geschrieben, +1 Fehlerresilienz-Fall).


## 2026-09-13 (20) - OLB-Spielereignisse als gratis Nachzueger (Tore & Karten)

- **Anlass:** Nutzerfrage nach weiteren kostenlosen Quellen pro Spiel (Torschuetzen, Karten). Live-Pruefung: TheSportsDB Felder leer, ESPN von hier 403 (unverifizierbar/undokumentiert), football-data events = Paid, API-Football-History bleibt Free-Plan-blockt. Einzige saubere Gratis-Option: **OpenLigaDB matchEvents** im bereits genutzten getmatchdata-Payload (aktuell leer, 0 Ereignisse BL1 - live getestet); nimmt man, damit es automatisch greift.
- **sync_openligadb.py:** `_olb_event_rows()` normalisiert Goal/OwnGoal/Yellow/YellowRed/Red (Elfer-Fehlschuetze und Wechsel bewusst draussen), numerische UND Text-Eventtypen; `_apply_olb_events()` mergt in das events-JSON beider OLB-Pfade (Vollsync + Nachzug): Goal-Boost-Zeilen haben bei Tor-Minute+Seite Vorrang (keine Duplikate), Fremdformate (live_scoring) bleiben unangetastet, laeuft nur bei finished, idempotent. Sync-Meldung ergaenzt "🥇 n Spiele mit neuen Ereignissen" nur wenn >0 (sonst lautlos), res["events"] Zaehler.
- **Seite:** match_detail zeigt unter den Torschuetzen eine "🟨 Karten & Platzverweise"-Sektion (Gelb/Gelb-Rot/Rot mit Quelle-Hinweis); gf-Zeilen aus OLB laufen automatisch durch die bestehende Tore-Sektion.
- **Tests:** +6 (`tests/test_olb_events.py`: Normalisierung/Filter, numerische Typen, Merge ohne Duplikate + Fremdformat-Schutz + Idempotenz, finished-Guard, Vollsync-Integration inkl. Meldungszaehler, Rendering beider Sektionen). Suite **387/387**.


## 2026-09-13 (21) - Torjaeger mit Verein: Nachname-Abgleich gegen football-data-Kader

- **Anlass:** Nutzerfrage "mehr Infos zu den Torjaegern, zumindest die Mannschaft?". OLB `getgoalgetters` nennt nur Name+Tore; `getplayers` ist 404. Die gratis-Loesung nutzt den LAENGST vorhandenen football-data-Free-Token: `/competitions/BL1/clubs` (+ ggf. `/clubs/{id}` fuer die `squad`-Listen) liefert die Kader - daraus Nachname->Verein-Tabelle.
- **`top_scorers.refresh_squad_map()`:** 1 Listen-Request pro Lauf, max. 4 Vereins-Detailabruefe als Nachzug pro Auffrischung (Rate-Limit-freundlich), Ergebnis 7 Tage gecacht (`topscorers_squad_map`), bei Gegenwind bleibt der alte Stand stehen; ohne fd-Token kompletter Skip (Liste laeuft dann wie bisher). Nach einem erfolgreichen Ranglisten-Fetch wird die Map automatisch dazugebucht.
- **Zuordnung ehrlich:** Nur EINDEUTIGE Nachnamen bekommen Verein (+Logo aus der eigenen DB, Umlaut-normalisiert, Klammersuffixe bereinigt); zwei "Mueller" in der Liga -> Feld bleibt leer statt zu raten. Anzeige unter dem Spielernamen.
- **Tests:** +4 (Annotation eindeutig/mehrdeutig, Skip ohne Token, Cache-Zweitaufruf, Seitenrendering mit "FCB") - ein selbst eingebauter Tautologie-assert wurde vor Release entfernt. Suite **391/391**.


## 2026-09-13 (22) - Admin-Zeitdoppler behoben + Vereinsabgleich sichtbar gemacht

- **Nutzer-Screenshots (Live, 13.09. abends):** (a) Torjaeger-Seite ohne Vereins-Anzeige, (b) Datenquellen-Zeilen mit "13.09.2026 19:20 Uhr UTC Uhr UTC".
- **Duplikat:** `_fmt_utc` liefert bereits "...Uhr UTC", die Datenquellen-Zeile haengte zusaetzlich ein hartes " Uhr UTC" an (seit ㉳ unentdeckt, weil der Test nur den Praefix pruefte). Fix in templates/admin/sync.html: `{{ at_fmt or (at[:16] ~ ' Uhr UTC') }}` - Fallback-Pfad bleibt lesbar. Regressionstest: "Uhr UTC Uhr" darf nicht im HTML stehen.
- **Zeiten erklaert (kein Bug):** Torjaeger "Stand 21:20" ist Lokalzeit (de_local), Admin "19:20 Uhr UTC" dieselbe Minute in UTC (CEST=UTC+2). Bewusst gemischt: Seite = fuer Spieler, Admin = fuer Feed-Vergleich.
- **Sichtbarmachung:** Nach einem erfolgreichen Torjaeger-Fetch steht im Quellen-Protokoll jetzt "n Spieler · x/n mit Verein" (bzw. "... (Kader-Aufbau laeuft, m Clubs erkannt)" oder "· ohne Vereinsabgleich (kein football-data-Token)"). Damit ist auf einen Blick erkennbar, ob der Vereinsabgleich laeuft, teilaufgebaut ist, oder das Modul auf dem Server noch ohne Map-Code ist (Notiz bleibt dann beim alten Wortlaut) - Ferndiagnose statt Raten. fetch liefert zusaetzlich res["teams"].
- Suite **392/392** (+1 Notiz-Test, +1 Dup-Regression). Alle drei Hotfix-Ordner per SHA-Check auf Repo-Stand gebracht (sync.html-Update in torjaeger_olb UND stadien_festdaten nachgezogen).


## 2026-09-13 (23) - Modul-Stempel + Pycache-Falle + Akzent-Match (Torjaeger)

- **Beweislage aus dem Nutzer-Screenshot:** Sync um 19:34 UTC lief, aber die Torjaeger-Notiz blieb beim ALTEN Wortlaut "20 Spieler" (kein "x/n mit Verein", kein Skip-Hinweis) -> auf dem Server aendert die neue top_scorers.py nichts, waehrend das neue Template (sync.html, Dup-Fix sichtbar) wirkt. Klassischer Verdacht: FTP-Client hat alte Timestamps mitgesetzt, Python nutzt das __pycache__ weiter.
- **Gegenmittel:** (a) HINWEIS erzaehlt jetzt das Loeschen von __pycache__ nach Upload. (b) Modul-Selbstausweis: top_scorers.MODULE_VERSION "2026-09-13c" steht am Ende der Quellen-Notiz UND dezent auf der Torjaeger-Seite (meta.module_version) - eine Screenshot-Zeile entscheidet kinftig, welche Version laeuft (alter Stand ohne Stempel = Beweis "nicht deployt").
- **Eigener Bug gefunden:** Nachname-Match zerlegte nur deutsche Umlaute; football-data schreibt Spieleramen mit Akzenten (Matanovic') - OLB-Kuerzel trafen dann nie. _surname_key normalisiert jetzt NFKD (combining marks entfernt), Test mit Matanovic'/Matanovic + KOE-Kurzel.
- Suite **394/394** (+3: Akzentmatch, Stempel in Notiz+Meta). Alle Hotfix-Ordner wieder SHA-synchron.


## 2026-09-13 (24) - Stummer Kader-Ausfall ist vorbei: Grund + Abbruch nach erstem Fehler

- **Aus dem Live-Bild (19:34-Deploy):** "Uhr UTC"-Doppler weg (Fix wirkt!), Torjaeger-Notiz blieb aber nuchtern "20 Spieler" -> Vereinsabgleich schlug fehl, ohne Grund zu nennen. Genau dafuer war der Stempel-Ansatz zu grob: Der else-Zweig nennt jetzt den echten Grund ("Vereinsabgleich ausgesetzt (HTTP 429)" o.a.), der Fertig-Zweig den Baustatus "(Kader-Aufbau laeuft, 18 Clubs erkannt)".
- **Eigener Bug im Detail-Loop:** bei Nicht-200 (Rate-Limit) wurden alle restlichen 18 Clubs schnell durchgeprobt - bricht jetzt nach dem ersten Fehlschlag ab; done-Schwelle beruecksichtigt den Abbruch (kein falsches "fertig").
- **Umlaut-Falle im eigenen Test:** Notizen in Moduldateien sind ASCII ("laeuft"), Assertion mit "laeuft" korrigiert - und eine Tautologie-Regression ("Kader-Aufbau" NOT in note bei voller Map) gleich mit raus.
- Suite **395/395** (+1 Rate-Limit-Test, +1 Baustatus-Fall im Notiz-Test). Hotfix-Ordner nachgezogen.


## 2026-09-13 (25) - 404-Ursache gefunden: erfundener fd-Endpoint durch /standings ersetzt

- **Ferndiagnosetest bestanden:** Das neue Protokoll zeigte sofort "Vereinsabgleich ausgesetzt (404) · Modul 2026-09-13c" - die eigene Diagnose hat ihren Zweck erfuellt.
- **Fehler:** football-data v4 hat KEINEN Endpoint /competitions/{code}/clubs (den hatte ich aus aelteren API-Generationen "gewusst"). Korrekter Weg: GET /competitions/{code}/standings (gratis) -> Team-Referenzen der Hinrundentabelle -> GET /clubs/{id} fuer die squad-Felder (wie schon vorher etappenweise, 4/Lauf). Tabelle leer (vor MD1) -> eigener Zweig "keine Tabelle (Saisonstart?)" im Protokoll statt stummem Fehler.
- **Zusaetzlich:** Map fertig + 0 Treffer wird ausdruecklich als moegliche Free-Plan-Grenze ("fd-Kader ohne squad-Felder") benannt. Stempel hoch auf 2026-09-13d.
- **Tests:** 16 im ts-File (neuer Regressionstest "kein erfundener clubs-Endpoint mehr"; Akzentfall korrigiert: "Matanovic" <-> "Matanovic'" mit korrekter Transliteration). Suite **396/396**.


## 2026-09-13 (26) - Kader-Abrufe komplett auf den fd-Wrapper des Hauptsyncs umgestellt

- **Erkenntnis aus Stempel d (Server: weiter HTTP 404):** auch der standings-Abruf als roher requests-Call scheiterte - der Hauptsync ruft NIE nackige URLs, sondern _fd_request(...): Base-URL aus Config, Token, PFLICHT-Parameter `?season=`, Response-Cache mit 10-min stale fallback und anstaendige Fehlertexte. Mein Eigenbau hatte (a) ohne Saisonparameter gefragt und (b) ggf. andere Base/Pfade. Der Wegfall des Eigenbaus loescht beide Fehlerklassen.
- **Umbau top_scorers.refresh_squad_map:** steht/saemt jetzt ausschliesslich ueber `sync_football_data._fd_request(path, ttl)` (standings 1 h, /clubs/{id} 1 Tag) - kein eigenes requests-, kein eigenes Token-, kein Rate-Limit-Handling mehr; Fehlermeldungen des Wrappers (Token fehlt, 429, 404, Netzwerk) erscheinen unveraendert in der Admin-Notiz. no-fd-token-Sonderzweig entfernt (der Wrapper meldet das selbst, inkl. "Admin → Einstellungen"-Hinweis). Stempel 2026-09-13e.
- **Tests:** Fakes haeangen jetzt am selben Punkt wie das Leben (`_fd_request` statt requests+URL-Raetsel): Abbruch-Test zaehlt genau EINEN Detail-Versuch bei Rate-Limit; Map-Cache-Zustand wird in Szenario-Tests explizit geleert (ein Test lief zuerst durch den cached-Short-circuit ins Leere). Suite **396/396**.


## 2026-09-13 (27) - Drittes 404, aber selbstgebaut keins mehr: Club-Referenzen aus dem Match-Feed

- **Protokoll (Stempel e):** "Vereinsabgleich ausgesetzt (API-Fehler 404 (Token/Quota pruefen))" - der korrekte Wrapper-Aufruf `/competitions/BL1/standings?season=2026` ist auf dem Server also genuine 404 (Free-Plan ohne standings fuer die aktuelle Saison). Nebenbefund: die Tabellen-Seite nutzt denselben Endpunkt, faellt bei Fehler aber still auf DB-Berechnung (`compute_live_standings`) zurueck - deshalb fiel der 404 dort nie auf.
- **Loesung ohne Raten:** Vereins-Referenzen (id/name/shortName) stecken laengst im BEWAEHRTEN `/competitions/BL1/matches?season=` - exakt der Call, der 306 Spiele zuverlaessig liefert - und teilen sich den `_fd_request`-Cache (frischer Sync -> 0 zusaetzliche HTTP). Kader bleiben `/clubs/{id}`, etappenweise. Neue Fehlerzweige: "Match-Feed ohne Vereine (Saisonstart?)".
- Stempel 2026-09-13f. Regressionstest verbietet jetzt BOTH erfundene/stumme Pfade (clubs + standings) und verlangt matches?season=. Suite **396/396** (16 ts-Tests). Falls /clubs/{id} auf dem Server ebenfalls 404t, sagt die Notiz das wrtlich - dann ist die Liste honest ohne Vereine (mehr lsst fd-Free nicht zu) und ich wrde zurueckbauen auf "nur OLB, ohne Map".


## 2026-09-13 (28) - Vereinsabgleich auf TheSportsDB umgestellt (dritter Anlauf, keyfrei)

- **Beweiskette komplett:** Stempel g-Protokoll zeigte nach erfolgreichem Match-Feed-Schritt "ausgesetzt (API-Fehler 404)" - damit ist auch /clubs/{id} mit dem Free-Key dicht. Alle football-data-Wege (competitions/clubs, standings, clubs/{id}) sind serverseitig als 404 belegt; der Modul-Code ruft football-data jetzt GAR NICHT mehr auf (Regressionstest sichert das).
- **Neue Basis:** TheSportsDB-Spielersuche (searchplayers.php, kostenlos + keyfrei, live verifiziert 13.09.). Regeln gegen die dreckigen Daten: Treffer nur bei exakter Nachname-PLUS Initial-Uebereinstimmung; Vereinsstring muss eindeutig einem DB-Liga-Team zuordenbar sein (Token-Subset); "_Retried Soccer" & Co. -> als Niete gemerkt, 7 Tage kein erneuter Anlauf; Netzfehler werden NICHT als Niete gespeichert (naechster Lauf erneut). Budget 6 Nachschlagungen pro Ranglisten-Aktualisierung -> 20er-Liste in <=4 Laeufen durch; woechentliche Auffrischung (Transfers!).
- **Notizformat:** "20 Spieler · 14/20 mit Verein (TheSportsDB: 6 nachgeschlagen)" bzw. "(TheSportsDB-Panne, n offen)" · Stempel 2026-09-13g.
- **Tests:** File neu geschnitten (12): Parsing/Notiz, keyfrei, Drossel+Fehler-Cache, Hit-Bindung (Kurzname dynamisch aus DB - Order-Bug im eigenen Test behoben), Muell-/Fremdverein-Ablehnung + kein Nachpollern, Initial-/Nachnamens-Fehltreffer, Netz-Panne-Retries, "kein football-data mehr im Code", Sync-Hook, Seite mit/ohne Daten. Suite **392/392** (4 fd-Map-Tests entfielen).


## 2026-09-13 (29) - Aliassammlung: Ablehnungen sichtbar + manuelle Zuordnung mit Sofortwirkung

- **Anlass:** Nutzerwunsch nach der versprochenen "kleinen haendischen Aliassammlung" fuer die 8 von 20 abgelehnten Torjaeger-Namen. (Hinweis: dieser Round war beim ersten Versuch mittig abgebrochen - nur das Modul kam an, Kabel drunter/Drueber fehlten; jetzt vollstaendig und gegengeprueft.)
- **top_scorers (Stempel h):** Ablehnungen landen im Map-Feld 'rejected' mit Grund (Fund+Verein der Suche, Alias-Fehler) - Pruning gegenueber lebenden Namen; squad_review() liefert (Spieler, Grund, Schluessel) fuer die Admin-Seite; Aliasse (Setting 'topscorers_squad_aliases', Zeilen 'nachname = Verein/Kuerzel', Trenner =/:/->/→) werden VOR dem done_at-Cache-Kurzschluss angewandt - echte Logikverbesserung, sonst haette eine Handzuordnung bis zu 7 Tage auf Wirkung warten muessen; kaputte Aliasse ueberschreiben nichts und erklaeren sich in der Review-Liste. Notiz: "... · n abgelehnt (Aliasse moeglich)".
- **Admin:** API-Sync-Seite zeigt unter der 🥇-Zeile eine Karte mit allen unzugeordneten Namen inkl. Grund und kopierfertigem "key = ..."-Vorschlag; Einstellungen -> APIs bekommt das TextArea "Torjäger-Aliasse" (forms.py-Feld + routes_admin-Vorbelegen/Speichern, 1000 Zeichen).
- **Tests:** +5 (Rejected-Recording, Alias ueberholt Suche ohne neuen HTTP-Aufruf, kaputter Alias meldet statt zu ueberschreiben, Admin-Liste rendert, Settings-Feld zeigt gespeicherten Text). Beim Umbau zweimal in eigene Fallen getappt und transparent behoben: (1) 7-Tage-Cache frass Alias-Aenderungen, (2) function-slicing hat squad_review verschluckt. Suite **397/397**.


## 2026-09-13 (30) - Torjaeger-Seite bekommt den Vereins-Picker fuer Admins

- **Wunsch:** Zuordnung direkt am Spieler per Auswahlliste statt Textfeld-Frickeln.
- **Wie:** `main_stats_routes` haengt der Seite nur fuer Admins `squad_teams` (alle DB-Teams, sortiert) an; pro Zeile ein kleines `select` (JS-onchange-Submit, CSRF-Token aus base-Konvention) + POST `/torjaeger/verein` (endpoint main.top_scorers_club, login+is_admin, sonst 403). Der Picker schreibt **durch dieselbe Funktion** (`set_manual_link` in top_scorers) wie das Einstellungs-Textfeld - eine Aliassammlung, kein zweiter Mechanismus. Reset ("— ohne Verein —") loescht Alias + Map-Eintrag + tried-Merkblatt; Suche darf dann wieder. Stempel i.
- **Beim Bau gefangen und behoben:** Blueprint-Namespace - `url_for('top_scorers')` baut ohne `main.` keine URL (BuildError im Redirect und im Sync-Hinweis); Tests auf Teilstring-Namen und Logout-zwischen-Logins korrigiert.
- **Tests:** +4 (Picker setzt Alias+Zeile ohne HTTP, Reset entlaeuft names/tried, 403 fuer tippende Nutzer + 'passt nicht' bei unbekannter Team-id, Picker nur im Admin-HTML). Suite **401/401**.


## 2026-09-13 (31) - Picker respektiert die Spieleransicht

- **Fund des Nutzers:** Im Spieler-Modus (Session-Flag `player_preview_mode`) zeigte die Torjaeger-Seite weiter die Vereins-Dropdowns - base.html gateet Admin-UI seit je mit `is_admin and not player_preview_mode`, die neue Stats-Route nur mit `is_admin`.
- **Fix:** GET uebergibt `squad_teams` im Preview leer (Template blendet den Picker automatisch aus, Liste bleibt); POST `/torjaeger/verein` antwortet im Modus wie der Adminbereich: Info-Flash + Redirect auf die Startseite, KEIN stiller Schreibvorgang. Stempel j.
- **Tests:** +2 (Picker unsichtbar im Modus bei weiter voller Liste; POST blockiert und schreibt nichts). Suite **403/403**. Nebenfund: venv-Rebuild aus repo-eigener requirements.txt (zuverlaessiger als das fruehere /tmp-Konstrukt).


## 2026-09-14 (32) - WhatsApp-Gruppeneingang fuer die App

- **Wunsch:** Die Vereins-WhatsApp-Gruppe soll aus der App erreichbar sein. Speicherort-Entscheidung des Nutzers: Admin-Feld (nicht im Repo), sichtbar nur für Eingeloggte, Ort Startseite + Mehr-Seite.
- **Umsetzung:** Setting `whatsapp_group_url`; neuer Settings-Block „💬 Community" (Feld + Statuszeile „Link hinterlegt/kein Eingang"). `routes_main._whatsapp_group_url()` liefert den Wert nur, wenn er mit http(s):// beginnt (kaputte/giftige Werte rendern nichts), Dashboard zeigt einen `payment-reminder-card`-Kasten (gleiche Optik, 💬 + Button „Gruppe öffnen", target=_blank rel=noopener), Mehr-Seite eine `more-card` unter „Mitspieler einladen". Speichern ergänzt fehlendes https:// automatisch; Link mit Leerzeichen => Flash-Fehler (Vorlage zeigt keine Feldfehler, Umweg über das bewährte Flash) + alter Eintrag bewusst geleert. Der Invite-Link lebt nur in der DB, nie im Code/GitHub.
- **Neuer Hotfix-Ordner** `hotfix_whatsapp_gruppe/` (sechs Dateien, HINWEIS mit Selbstbeweis-Hinweis: Block „Community" fehlte vorher). Suite **408/408** (+5: Roundtrip inkl. Schema-Auto, Leerzeichen-Ablehnung, Dashboard show/hide, Mehr show/hide, No-Render bei `javascript:`-Wert).


## 2026-09-15 (33) - WhatsApp-Eingang dezenter, mit echtem Logo

- **Userfeedback (Screenshot):** Die gestrige Startseite-Karte klang zu wichtig neben der Naechster-Schritt-Box; Wunsch nach dezenter Darstellung + WhatsApp-Logo.
- **Umsetzung:** Dashboard block by block zur Einzeiler-Zeile `.wa-quiet` (inline-flex, 14 px, Muted-Text, Hover unterstrichen) umgebaut - Text "In die WhatsApp-Gruppe der Tipprunde" + halbleiser Klammer "Los-Tausch, Fragen, Feiern", davor das offizielle WhatsApp-Glyph als Inline-SVG (#25D366, CC0-Pfad, aria-hidden). Kein Riesen-Button mehr, keine payment-reminder-Kartenoptik, keine neue Statische-Datei (SVG im Template, CSS-Regel in style.css). Mehr-Seiten-Karte behaelt ihre Kachel-Form (fuigt sich dort ein), nur das Icon: Emoji -> Logo. Ziel-Attribute (target=_blank rel=noopener) unveraendert.
- **Test-Anpassung mit Lehre:** Der erste Patch-Versuch scheiterte an einem `\u`-Escape im Heredoc (literaler Backslash traf echten O-Umlaut) - der Patch wurde nicht geschrieben, pytest zeigte den alten Stand; Nachzug mit echten Umlauten, zusaetzliche Regressions-Asserts (kein Grossbutton "Gruppe oeffnen" mehr, Logo-Farbe im HTML). Suite **408/408** wie vorher (nur umgeschrieben, keine Zahl getauscht).


## 2026-09-15 (34) - WhatsApp-Zeile ohne Untertitel

- Nutzerwunsch: der Klammerzusatz "Los-Tausch, Fragen, Feiern" fliegt - die Zeile ist nur noch Logo + "In die WhatsApp-Gruppe der Tipprunde". Die damit tote CSS-Regel `.wa-quiet small` wurde gleich mit entfernt (keine Leiche im Stylesheet), Test-Assert verriegelt das Wegbleiben. Rein kosmetisch, keine Logik veraendert. Suite 408/408.

## 2026-09-15 (35) - WhatsApp-Runde (32)–(34) auf GitHub komplettiert + Regressionstests

- **Befund (Übergabe 15.09., frischer Klon):** Der Push der WhatsApp-Runde war auf GitHub unvollständig – `routes_main.py` (Helper + Kontext-Übergabe) und `templates/dashboard.html` (die ruhige `.wa-quiet`-Zeile) hatten die `GITHUB_UPLOAD_FILES`-Liste nie erreicht, die 5 Regressionstests aus (32) ebenso nicht. Folge: GitHub lag bei 403 Tests, die Mehr-Seiten-Karte war toter Code (Template-Variable `whatsapp_group_url` wurde nirgends injiziert), die Startseite-Zeile existierte im Repo nicht. Der Server war nicht betroffen (FTP-Hotfix enthielt die vollständigen Dateien). **Dritter Nachzügler im selben Klon-Check:** `verify_04.py` (in Block 16 als neu dokumentiert, aber nie in der Git-Historie) – wurde jetzt nach der Doku-Spezifikation neu aufgebaut: frischer Klon + 04-Zip-Overlay + harter flake8-Gate + volle pytest-Suite, „vor jedem GitHub-Upload: `python verify_04.py`“.
- **Fix (an den dokumentierten Live-Stand angelehnt):** `routes_main.py` bekommt `_whatsapp_group_url()` – Schema-Gate, das nur http/https-Werte an Templates übergibt (javascript:/data:-Werte in der DB rendern nichts) – und die Dashboard- sowie Mehr-Route geben den Wert weiter. `templates/dashboard.html` zeigt unterhalb der Zahlungserinnerung die Zeile in der Live-Form: Inline-SVG-Logo (#25D366, aria-hidden) + „In die WhatsApp-Gruppe der Tipprunde“ (ohne Untertitel), `target=_blank rel=noopener`.
- **Tests:** neue Suite `tests/test_whatsapp_group.py` (+5: https:// wird bei kuerzem Link automatisch ergänzt, Leerzeichen ⇒ Flash + alter Eintrag wird geleert, Startseite show/hide inkl. Verriegelung der Untertitel-Finalform, Schema-Gate verwirft `javascript:` auf Startseite UND Mehr-Seite, Mehr-Karte show/hide). Suite **408/408** – damit stimmt GitHub wieder mit dem dokumentierten Stand der Übergabe überein.
- **Prozess:** 4 Dateien (routes_main.py, dashboard.html, test_whatsapp_group.py, verify_04.py) + README/CHANGELOG in `GITHUB_UPLOAD_FILES` aufgenommen; README-Badges nachgezogen (285/285→408/408, Coverage 79→83 %). Kein Netcup-Deploy nötig (Feature läuft dort bereits); optional: `routes_main.py` + `templates/dashboard.html` neu hochladen, falls Bytesync zum Server gewünscht ist.

## 2026-09-15 (36) - Coverage-Runde: cron_jobs.py & backup.py auf 100 %

- **Ziel (der in der Übergabe als „Kür“ dokumentierte letzte Restpunkt):** `cron_jobs.py` (43 % bei Übergabe, 52 % im frischen Klon) und `backup.py` (82 %) – beide Fachmodule der Produktions-Absicherung hatten ihre kritischsten Pfade ungedeckt.
- **Neu in `tests/test_cron_backup.py` (+14):** backup.py: relativer DB-Pfad wird gegen die App-Root (nicht CWD) gelöst, list_backups-Happy-Path (neueste zuerst, Fremd-Dateien ignoriert, stat-Fehler wird übersprungen), Rotations-OSError (nicht löschbare Datei bricht nicht ab). cron_jobs.py: Task-Körper `run_sync`/`run_reminders`/`run_bot_tips` (deaktiviert, aktiv ohne Fehler, aktiv mit Fehlerzähler)/`run_backup` (Erfolg + Fehler)/`run_status` (alle vier Zustände ok/warn/error/never, Detail- und Alter-Zweige) mit gepatchten Fachmodulen; Dispatch `reminder`/`bots`; alle Bootstrap-Zweige (vendor/-Einbindung, `.python-venvs`-Suche, Venv-site-packages-Rückkehr, Re-Exec-Fehlerpfad mit gepatchtem `os.execl` – kein echter Prozess-Tausch) und der echte Skript-Eintritt `python cron_jobs.py status` als Subprozess.
- **Einziges `# pragma: no cover`:** dotenv-Import-Fehler im Modul-Header (in allen Setups installiert, import-time nicht auslösbar) – im Stil des vorhandenen Pragma in backup.py.
- **Ergebnis:** Suite **423/423**, Coverage 83 %, `cron_jobs.py` **100 %**, `backup.py` **100 %**.
- **Deploy:** `cron_jobs.py` trägt nur die Pragma-Kommentarzeile (keine Funktionsänderung) – FTP-Upload nicht nötig, die Datei wandert mit dem nächsten kompletten Deploy mit; Tests landen über das 04-Paket auf GitHub.
