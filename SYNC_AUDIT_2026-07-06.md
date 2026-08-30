# Sync-Audit 2026-07-06

Geprüft wurden gezielt:

- Saisoncode/Saisonwechsel
- football-data.org Vollsync
- OpenLigaDB Fallback
- Aufsteiger/Absteiger
- stale Match Purge
- Team-/CompetitionTeam-Zuordnung
- Logo-Fixes und lokale Logos

## Ergebnis

Der Sync ist nach den Korrekturen deutlich stabiler. Vor allem der OpenLigaDB-Fallback war vorher nicht vollständig stabil.

Aktueller Teststand:

```txt
104/104 Tests bestanden
Coverage ca. 60%
1 Warning: reportlab DeprecationWarning, harmlos
```

## Gefundene Punkte und Fixes

### 1. OpenLigaDB-Fallback konnte crashen

Im OpenLigaDB-Sync gab es einen alten Codepfad mit nicht definierten Variablen:

```txt
source
current_ext_ids
```

Das konnte bei erfolgreicher OpenLigaDB-Antwort zu einem Serverfehler führen.

**Fix:** OpenLigaDB nutzt jetzt eigene `current_ext_ids` und den gemeinsamen stale-purge Helper.

### 2. OpenLigaDB hat Aufsteiger bisher nicht angelegt

football-data.org konnte unbekannte Teams bereits anlegen. OpenLigaDB übersprang unbekannte Teams dagegen.

**Fix:** Neuer Helper:

```txt
_resolve_or_create_team_from_olb()
```

Damit werden neue Teams/Aufsteiger aus OpenLigaDB automatisch angelegt und per `CompetitionTeam` dem aktiven Wettbewerb zugeordnet.

### 3. Quellenwechsel konnte Tipps gefährden

Wenn vorher football-data.org Spiele mit `fd:*` IDs angelegt hatte und später OpenLigaDB als Fallback mit `oldb:*` IDs lief, drohten Duplikate oder Löschungen.

**Fix:** Neuer Match-Finder:

```txt
_find_existing_match()
```

Er matched beim Quellenwechsel über:

- Wettbewerb
- Spieltag
- Heimteam
- Auswärtsteam

Dadurch bleiben vorhandene Matches und damit Tipps/Kommentare erhalten.

### 4. Alte `fd:*`-Saisonspiele dürfen nicht versehentlich umgebogen werden

Bei gleicher Paarung am gleichen Spieltag in neuer Saison darf ein altes `fd:*`-Match nicht einfach auf eine neue externe ID geändert werden.

**Fix:** Matching innerhalb derselben Quelle wird blockiert, wenn die externe ID abweicht. Diese Spiele werden dann als stale erkannt und entfernt.

### 5. Stale Purge vereinheitlicht

Neuer Helper:

```txt
_purge_stale_matches_for_comp()
```

Er löscht nur im aktiven Wettbewerb:

- alte Matches
- zugehörige Predictions
- zugehörige Comments

### 6. Lokale Logos bleiben lokal

`update_known_team_logos()` überschreibt lokale Logos wie:

```txt
/static/team_logos/fcb.svg
```

nicht mehr mit externen URLs. Das wurde zusätzlich getestet.

## Neue/erweiterte Regressionstests

Ergänzt in:

```txt
tests/test_sync_promoted_teams.py
```

Neue Abdeckung:

- OpenLigaDB legt unbekannte Aufsteiger-Teams an.
- OpenLigaDB entfernt stale Matches im aktiven Wettbewerb.
- OpenLigaDB-Fallback erhält bestehende football-data.org Matches und Predictions.
- Lokale Logos werden nicht zurück auf externe URLs geschrieben.

## Einschätzung

### Saisonwechsel

Stabil, weil:

- `season` wird aus `2026/27` korrekt zu `2026` abgeleitet.
- `current_season` bleibt als Label erhalten.
- aktive Competition wird aktualisiert.
- Sync nutzt `current_sync_season_code()` statt starrer Config.

### Aufsteiger

Stabiler als vorher, weil:

- football-data.org erstellt unbekannte Teams.
- OpenLigaDB erstellt unbekannte Teams jetzt ebenfalls.
- `CompetitionTeam` wird automatisch gesetzt.

### Absteiger

Stabil, weil:

- Teams historisch in der globalen `teams`-Tabelle bleiben dürfen.
- aktuelle Teamzahl aus aktiven Matches/CompetitionTeams berechnet wird.
- stale Matches des aktiven Wettbewerbs beim Vollsync entfernt werden.

### Logos

Stabiler, weil:

- bekannte Problem-Logos gezielt korrigiert werden.
- lokale Logos nicht überschrieben werden.
- Wartungscenter Fallback-Logos erkennen und ersetzen kann.

## Rest-Risiko

- Externe APIs können Namen/IDs ändern. Dafür sind Mapping und Tests jetzt besser, aber nicht vollständig zukunftssicher.
- Bei echten API-Daten sollte nach Saisonwechsel weiterhin immer Admin → API Sync und danach Wartungscenter/Sync-Diagnose geprüft werden.
- Wenn football-data.org und OpenLigaDB stark abweichende Teamnamen liefern, kann ein neuer Mapping-Eintrag nötig sein.

## Empfehlung für echten Saisonwechsel

1. Backup erstellen.
2. Saisonwechsel-Assistent nutzen.
3. Neue Saison setzen, z. B. `2026/27`.
4. Spielplan löschen, wenn neue Saison frisch geladen werden soll.
5. API Sync ausführen.
6. Sync-Diagnose prüfen:
   - Saison-Code richtig?
   - Teams aktuell 18?
   - Spiele lokal 306?
   - Aufsteiger vorhanden?
7. Wartung `logos-force` ausführen, wenn Logos fehlen/falsch sind.
8. Plesk-App nach Upload neu starten.
