# 🚀 Deployment auf Netcup Webhosting

Diese Anleitung führt dich Schritt für Schritt durch das Deployment auf einem
**Netcup Webhosting-Tarif mit Python-Support** (z. B. Webhosting 4000+).

> Netcup nutzt **Plesk** mit **Phusion Passenger** für Python-Apps.
> Dauerhaft laufende Prozesse (z. B. APScheduler) sind nicht erlaubt — wir
> nutzen stattdessen **Plesk-Cron** für Reminder + API-Sync.

---

## 📋 Voraussetzungen

- ✅ Netcup Webhosting-Tarif **mit Python-Support** (im Plesk verfügbar)
- ✅ Eine Domain oder Subdomain (z. B. `tippspiel.deinedomain.de`)
- ✅ FTP/SFTP-Zugang oder Plesk-Filemanager
- ✅ Lokale getestete App (siehe README.md)

---

## 🪟 Schritt 0: Lokal unter Windows testen

```bat
cd Bundesliga-Tippspiel
install.bat        :: einmalig - installiert Python-Dependencies
start.bat          :: startet die App auf http://localhost:5000
```

**Login:** `admin@tippspiel.local` / `admin123`

> Bei Problemen: stelle sicher, dass Python 3.9 oder neuer installiert ist und
> beim Setup "Add Python to PATH" aktiviert war (lokal unterstützt die App
> 3.9–3.13; auf Netcup gilt 3.9).

---

## 🌐 Schritt 1: Domain/Subdomain in Plesk anlegen

1. Im **Netcup CCP** auf dein Webhosting → **Plesk öffnen**
2. **Domains** → neue Subdomain `tippspiel.deinedomain.de` anlegen
   (oder Hauptdomain verwenden)
3. **Document Root** notieren — typischerweise:
   `/var/www/vhosts/deinedomain.de/tippspiel.deinedomain.de/`

---

## 🐍 Schritt 2: Python-Support in Plesk aktivieren

1. In Plesk auf die neue Domain klicken
2. Klicke auf **Python** (im Bereich "Entwicklungstools")
   - Falls nicht sichtbar: in den Hosting-Einstellungen Python aktivieren
3. **Aktivieren** und folgende Werte eintragen:

| Feld | Wert |
|------|------|
| Python-Version | **3.9** |
| Application Mode | **Production** |
| Application Root | `/httpdocs` (oder eigener Pfad) |
| Application URL | `/` |
| Application Startup File | `passenger_wsgi.py` |
| Application Entry Point | `application` |

4. **Apply / Übernehmen** klicken

> ⚠️ **Wichtig:** Auf dem Netcup-Webhosting ist in Plesk aktuell **nur Python 3.9** auswählbar — das ist die feste Rahmenbedingung dieser App. Alle Abhängigkeiten bleiben deshalb 3.9-kompatibel (`requirements.txt`-Pins, CI testet 3.9 als Zielversion). Python 3.9 ist seit Okt. 2025 offiziell EOL (keine Security-Patches mehr vom Python-Team); für diese private Runde akzeptiert und durch app-seitige Härtung (Security-Gate, Rate-Limiting, CSRF) abgefedert. Vendor-Pakete mit `build_vendor.bat` Option **[1] Python 3.9** bauen. Falls Netcup künftig neuere Versionen anbietet, sind Option [2]/[3] und die CI-Matrix (3.10–3.13) bereits vorbereitet.

> Plesk legt jetzt im Hintergrund eine virtuelle Umgebung (venv) an, z. B. unter
> `/var/www/vhosts/deinedomain.de/.python-venvs/tippspiel/`.

---

## 📤 Schritt 3: Dateien hochladen

### Variante A: Per FTP/SFTP (FileZilla, WinSCP)

1. Verbinde dich mit dem FTP-Zugang aus Plesk
2. Lade **alle Dateien** aus dem Projekt-Ordner in den Application Root hoch:
   ```
   passenger_wsgi.py        ← Pflicht! Entry Point
   .htaccess
   app.py
   config.py
   models.py
   forms.py
   utils.py
   extensions.py
   cron_jobs.py
   requirements.txt
   templates/               (kompletter Ordner)
   static/                  (kompletter Ordner)
   ```

   ❌ **NICHT hochladen:**
   - `venv/` (wird auf dem Server neu erstellt)
   - `__pycache__/`
   - `*.db` (SQLite wird automatisch angelegt)
   - `start.bat`, `install.bat` (Windows-only)
   - `.env` (manuell auf dem Server anlegen, siehe Schritt 5)

### Variante B: Per Plesk Filemanager (im Browser)

1. Plesk → **Dateien** → in den Application Root navigieren
2. Lokale Dateien als ZIP packen → hochladen → entpacken

### Variante C: Git (falls Plesk Git-Modul vorhanden)

```bash
# Im Plesk-Panel: Git → Repository verknuepfen
# Push aus deinem lokalen Repo
git push netcup main
```

---

## 🔧 Schritt 4: Python-Dependencies installieren

Plesk bietet einen **"Pip Install"-Button** im Python-Bereich:

1. Plesk → Domain → **Python**
2. Scrolle runter zu **"Pip Install"**
3. Trage als Argument ein: `-r requirements.txt`
4. Klicke **Run**

Falls dein Tarif **eingeschränkten SSH-Zugang** hat:
```bash
ssh dein-user@deinserver.de
cd ~/httpdocs                          # oder dein App-Pfad
source ~/.python-venvs/tippspiel/bin/activate
pip install -r requirements.txt
```

> **Pillow-Problem?** Falls die Installation an Pillow scheitert (fehlendes
> libjpeg), kannst du Avatare deaktivieren — kommentiere `Pillow` in
> requirements.txt aus, das Tippspiel läuft auch ohne Avatar-Resize.

---

## 🔐 Schritt 5: Environment-Variablen setzen (.env)

Im Application Root eine **`.env`** anlegen (Plesk Filemanager → Neue Datei):

```bash
SECRET_KEY=ersetze-mich-durch-32-zeichen-zufallsstring-CHANGE-ME

# E-Mail (Beispiel: dein Netcup-Postfach)
MAIL_SERVER=mx2f50.netcup.net
MAIL_PORT=587
MAIL_USERNAME=tippspiel@deinedomain.de
MAIL_PASSWORD=dein-mailpasswort
MAIL_DEFAULT_SENDER=tippspiel@deinedomain.de

# football-data.org Token (kostenlos: football-data.org/client/register)
FOOTBALL_DATA_TOKEN=

# Cron-Zugang: Secret fuer den HTTP-Cron (/cron/run?key=...) - langen Zufallswert setzen!
# Ohne diesen Wert sind die Plesk-Cron-Aufgaben wirkungslos (Route deaktiviert).
CRON_SECRET=df4335bed8617c1f3f999ef9c5e254da

# Datenbank
# SQLite reicht fuer kleine Tippspiele (bis ~100 User).
# Fuer mehr: PostgreSQL/MySQL bei Netcup im Plesk anlegen, dann hier eintragen:
# DATABASE_URL=mysql+pymysql://user:pass@localhost/tippspiel_db
```

> **WICHTIG:** Die `.env` darf **nicht öffentlich erreichbar** sein.
> Die mitgelieferte `.htaccess` blockiert sie bereits. Zum Testen:
> `https://tippspiel.deinedomain.de/.env` → muss **403 Forbidden** liefern.

---

## 🔄 Schritt 6: App neustarten

Nach jeder Änderung musst du Passenger neuladen:

**Plesk → Python → Restart App** klicken

Alternativ per SSH:
```bash
touch ~/tmp/restart.txt
```
(Passenger erkennt diese Datei und startet die App neu.)

---

## ✅ Schritt 7: Im Browser aufrufen

```
https://tippspiel.deinedomain.de
```

**Erst-Login:** `admin@tippspiel.local` / `admin123`
→ **SOFORT IM PROFIL ÄNDERN!**

Beim ersten Aufruf werden automatisch:
- Datenbank `tippspiel.db` (SQLite) im App-Ordner erstellt
- 18 Bundesliga-Teams gespeichert
- 34 Spieltage mit Demo-Spielen erzeugt
- Admin-User angelegt

---

## ⏰ Schritt 8: Cron-Jobs einrichten (für Reminder + API-Sync + Backup)

**Wichtig:** Netcup führt geplante Aufgaben in einer **chroot-Umgebung ohne
Python** aus (`/usr/bin/python3: No such file or directory`). Die Aufgaben
rufen deshalb die App **per URL** auf — die App (läuft unter Passenger mit
Python 3.9 + `vendor/`) erledigt die Arbeit selbst und schreibt die
Heartbeats. Dafür gibt es die Route **`/cron/run`** (geschützt per
`CRON_SECRET` aus Schritt 5).

Im Plesk auf **„Geplante Aufgaben"** (Websites & Domains → deine Domain →
Geplante Aufgaben → „Aufgabe hinzufügen"). **Zwei Aufgaben** anlegen:

### Aufgabe 1: Automatik alle 15 Minuten (Sync + Bots + Reminder)
| Feld | Wert |
|------|------|
| Aufgabe aktiviert | ✅ |
| Befehl | `wget -q -O /dev/null "https://tipp.wulmstorf.net/cron/run?task=all&key=df4335bed8617c1f3f999ef9c5e254da"` |
| Ausführung | `*/15 * * * *` (alle 15 Min) |
| Benachrichtigen bei Fehlern | ✅ (per E-Mail) |

### Aufgabe 2: Datenbank-Backup täglich um 03:15 Uhr
| Feld | Wert |
|------|------|
| Aufgabe aktiviert | ✅ |
| Befehl | `wget -q -O /dev/null "https://tipp.wulmstorf.net/cron/run?task=backup&key=df4335bed8617c1f3f999ef9c5e254da"` |
| Ausführung | `15 3 * * *` (täglich 03:15 Uhr) |
| Benachrichtigen bei Fehlern | ✅ |

> **`&` in Plesk:** Sollte Plesk das `&` im Befehl beanstanden, den Befehl in
> Anführungszeichen setzen (wie oben) — oder als Aufgabe-Typ „URL abrufen"
> anlegen (falls Plesk das anbietet) mit der URL aus dem Befehl.

> **Fallback ohne wget:** `php -r 'file_get_contents("https://tipp.wulmstorf.net/cron/run?task=all&key=df4335bed8617c1f3f999ef9c5e254da");'`
> (PHP ist im chroot verfügbar).

> **Sofort testen:** Plesk bietet bei jeder Aufgabe einen „Ausführen"-Button (▶).
> Danach im Admin-Bereich → **Wartungscenter → „Cron & Backup"** prüfen: Alle
> Aufgaben zeigen ✅ mit „vor X min". Dort gibt es auch den Button
> **„💾 Jetzt Backup erstellen"** für einen sofortigen Test. Die Seite zeigt
> außerdem die fertigen wget-Befehle an und warnt, falls `CRON_SECRET` fehlt.

> **Offsite-Kopie:** Die Backups liegen in `backups/` auf demselben Server wie
> die App. Für echten Schutz **regelmäßig (mind. wöchentlich) per FTP
> herunterladen** — so überlebt die Tipprunde auch einen Serverausfall.

> **Überwachung:** Jeder Lauf schreibt einen Heartbeat in die Datenbank.
> Das Wartungscenter warnt automatisch, wenn eine Aufgabe überfällig ist
> oder der letzte Lauf fehlgeschlagen ist. So stirbt der Cron nie unbemerkt.

---

## 📊 Schritt 9: API-Token für Live-Ergebnisse

1. Kostenlos registrieren auf https://www.football-data.org/client/register
2. Token kopieren
3. In **Admin → Einstellungen** eintragen (oder in `.env` als `FOOTBALL_DATA_TOKEN`)
4. Im Admin-Bereich auf **"API Sync"** klicken — fertig!

> Free Tier: 10 Calls/Min — reicht völlig.

---

## 🔒 Schritt 10: HTTPS / SSL

Im Plesk:
1. Domain → **SSL/TLS-Zertifikate** → **Let's Encrypt installieren**
2. Häkchen bei "Subdomains absichern" + "Mail absichern"
3. Häkchen bei **"Permanente SEO-sichere 301-Weiterleitung von HTTP zu HTTPS"**

Die mitgelieferte `.htaccess` erzwingt zusätzlich HTTPS.

---

## 🛠 Troubleshooting

### "500 Internal Server Error" beim Aufruf

1. Plesk → Domain → **Logs** → `error_log` öffnen
2. Häufige Ursachen:
   - `passenger_wsgi.py` nicht im Application Root → richtigen Pfad in Plesk setzen
   - Dependencies fehlen → `pip install -r requirements.txt` erneut ausführen
   - Falsche Python-Version → in Plesk auf 3.10/3.11 umstellen

### Statische Dateien (CSS) werden nicht geladen

- Prüfe in `Plesk → Python`, dass **"Application URL"** auf `/` steht
- `/static/css/style.css` muss direkt erreichbar sein (kein 404)
- Notfalls in `.htaccess` die Static-Regeln anpassen

### "Permission denied" beim Avatar-Upload

```bash
ssh user@server
chmod 755 ~/httpdocs/static/uploads
```

### Datenbank ist plötzlich leer / weg

- SQLite-Datei `tippspiel.db` liegt im App-Root
- Nach Re-Deploy NICHT überschreiben — vor Upload sichern!
- Tipp: Datei auf eigenen Pfad legen via `DATABASE_URL=sqlite:////persistent/path/tippspiel.db`

### Mails werden nicht versendet

- Bei Netcup-Mail: Server ist `mx2fXX.netcup.net` (siehe deine Postfach-Einstellungen)
- Port 587 mit STARTTLS, **nicht** 465 (SSL)
- App-Passwort verwenden, nicht das Login-Passwort

---

## 📦 Was wird auf Netcup *nicht* funktionieren?

| Feature | Status | Workaround |
|---------|--------|------------|
| `python app.py` (Dev-Server) | ❌ | Plesk/Passenger nutzt eigenen WSGI |
| APScheduler (Hintergrund-Threads) | ❌ | → `cron_jobs.py` via Plesk-Cron |
| Web Push (`pywebpush`) | ⚠️ | Manchmal cryptography-Compile-Probleme |
| WebSockets / SSE | ❌ | Nicht von Passenger unterstützt |
| systemd Services | ❌ | Kein Root-Zugriff |
| Großer Traffic / >500 User gleichzeitig | ⚠️ | Dann lieber Netcup VPS / Root-Server |

---

## 🚦 Production-Checkliste

- [ ] `SECRET_KEY` in `.env` durch Zufallsstring ersetzt (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Admin-Passwort geändert
- [ ] Mail-Versand funktioniert (Test: Passwort vergessen)
- [ ] HTTPS aktiviert + erzwungen
- [ ] football-data.org Token eingetragen
- [ ] Cron-Jobs laufen (im Plesk-Aufgaben-Log prüfen)
- [ ] Backup eingerichtet (SQLite-File regelmäßig sichern!)
- [ ] `.env` ist nicht öffentlich (Test: 403 erwartet)
- [ ] Demo-Daten gelöscht (Admin → Einstellungen → falls gewünscht)

---

## 💡 Performance-Tipps

- **SQLite reicht** für bis zu ~100 aktive User. Darüber: MySQL/PostgreSQL via Plesk
- **Static Files** werden via Apache/.htaccess direkt ausgeliefert (umgeht Python)
- **CDN** für Logos: bereits eingebaut (`crests.football-data.org` lädt direkt)
- **Bilder optimieren**: Pillow macht das automatisch beim Avatar-Upload

---

## 📞 Support

Bei Netcup-spezifischen Problemen:
- **Wiki:** https://www.netcup-wiki.de/wiki/Python_Webhosting
- **Forum:** https://forum.netcup.de/
- **Support-Ticket:** Im CCP → "Hilfe & Support"

Viel Spaß mit dem Tippspiel! ⚽
