# 🔧 Optimierungs- & Feature-Roadmap

Stand: 2026-07-05

## ✅ Erledigt

### Sicherheit & Stabilitaet

- XSS-Kommentare mit `bleach` entschärft
- `datetime.utcnow()`/naive Defaults bereinigt
- SQLAlchemy `Query.get()` Legacy entfernt
- CSRF fuer Tipp-Autosave ergaenzt
- Rate-Limiting auf kritischen Endpunkten
- Production-Sicherheitsgate fuer `SECRET_KEY` und Default-Admin-Passwort
- Telegram Webhook Secret
- sensible Admin-Settings werden nicht im Formular vorausgefüllt
- NotificationLog gegen doppelte Reminder

### Performance

- `get_leaderboard()` auf Bulk-Queries optimiert
- `get_live_leaderboard()` auf Bulk-Queries optimiert
- Tippübersicht-Livepunkte per JSON statt Full Reload
- Cache-Invalidierung via Redis `SCAN` statt `KEYS`
- Versionierte Cache-Keys
- Bot-Admin Bulk-Queries
- Paginierung fuer Admin-User und Kommentare

### Multi-Wettbewerb/Saison

- Competition-Helper eingefuehrt
- wichtige Queries auf aktive Competition gefiltert
- `competition_id` fuer saisonbezogene Modelle ergaenzt
- Saisonwechsel-Assistent 2.0
- SchemaMigration fuer Hosting ohne SSH
- DB-/Schema-Wartung im Adminbereich

### Netcup/Betrieb

- `build_vendor.bat` fuer Linux-Wheels/Ziel-Python robuster gemacht
- `vendor_manifest.txt`
- Wartungscenter
- lokale Vereinslogos
- Backup/Restore und Komplett-ZIP
- Sync-Diagnose
- Admin Activity Log

### Features

- Tippübersicht/Tippmatrix
- Live-Punkte in Tippübersicht
- Sortierung nach Gesamt live/Spieltag live/Name
- Bottom-Tabbar mobile
- Benachrichtigungszentrale
- Telegram Bot erweitert
- Stats 2.0
- Spieltags-Preview
- Spieltags-Recap 2.0
- Mehr-Seite und Hilfe/Regeln
- User-Usability-Feinschliff ohne neue Features

### Tests

Aktuell lokal:

```txt
134/134 Tests bestanden
Coverage ca. 65%
1 Warning (reportlab DeprecationWarning, harmlos)
```

---

## 🔴 Hohe Prioritaet

### 1. Sync/API noch robuster testen

`sync.py` ist fachlich kritisch und weiterhin komplex.

Naechste Schritte:

- football-data.org Responses mocken
- OpenLigaDB Responses mocken
- Team-Mapping-Fehler testen
- Ergebnis-Updates testen
- Rate-Limit/Timeout/Token-fehlt testen
- Sync-Diff/Preview weiter ausbauen

### 2. Export/PDF verbessern

`export.py` hat noch niedrige Coverage.

Naechste Schritte:

- PDF-Generierung auf Bytes testen
- Umlaute/Sonderzeichen testen
- Admin-Export fuer komplette Saison
- Tippmatrix-Export im UI verlinken
- Export ZIP optional erweitern

### 3. Routen weiter modularisieren

`routes_main.py` und `routes_admin.py` sind sehr groß.

Zielstruktur:

```txt
routes/profile.py
routes/tips.py
routes/stats.py
routes/admin_season.py
routes/admin_maintenance.py
routes/admin_users.py
```

---

## 🟠 Mittlere Prioritaet

### 4. Notification Center Bulk-Optimierung

Aktuell noch viele User/Match-Schleifen.

Verbessern:

- Predictions fuer Reminder gesammelt laden
- NotificationLogs gesammelt laden
- weniger Queries pro Reminder-Lauf

### 5. Inline JS/CSS reduzieren

Viele Templates enthalten noch Inline-CSS/JS.

Schrittweise auslagern:

```txt
static/js/live.js
static/js/tip_overview.js
static/css/tip_overview.css
static/css/admin.css
```

### 6. Lokale Logos finalisieren

- Standardlogos optional direkt ins Repo legen
- Wartungscenter zeigt konkrete Teams mit externen/fehlenden Logos
- Fallback-Logo optisch verbessern

---

## 🟢 Optional

### 7. Alembic/Flask-Migrate

Die interne `SchemaMigration` ist gut fuer Netcup ohne SSH. Alembic waere trotzdem fuer lokale/Docker/PostgreSQL-Setups langfristig sauberer.

### 8. Offene Tipps + Reminder-Button

Sehr praktisches Alltagsfeature:

- Spieltag-Auswahl
- offene Tipps pro User
- Reminder an offene Tipper senden

### 9. Admin Activity Log erweitern

Noch mehr Details loggen:

- before/after bei Ergebnissen
- Settings-Diffs
- Badge-/Prize-Aenderungen
- Backup-Download

### 10. Tests Richtung 60%+

Gute Kandidaten:

- Sync-Mocks
- Export/PDF
- Admin-Routen
- Notification Center Edge Cases
- Cache Monitor Edge Cases
