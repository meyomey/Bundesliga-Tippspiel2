"""Versuchs-Protokoll je Datenquelle (Admin-Dashboard, 12.09.2026).

Ein schlanker, gemeinsamer Aktivitäts-Speicher für alle Feed-Quellen der App:

    football-data | openligadb | minute | goals | torjaeger

Protokolliert wird bewusst nur der ECHTE Abrufversuch (Erfolg WIE Fehler,
nie Drosselungs-/Fenster-Skips) mit Zeitstempel, ok-Flag und kurzer Notiz
(Fehlergrund). Das Admin-Dashboard ("API Sync") zeigt daraus "letzter Versuch
inkl. Grund" pro Quelle - damit ein stiller Fallback (FD down, OLBspricht)
und ein bockender API-Football-Key gleichermaßen sichtbar werden, ohne dass
irgendwo eine falsche "war alles gut"-Uhr läuft.

Ablage: ein einziges Setting (JSON). Kein Lösch- oder Wartungsaufwand; jeder
Schreibvorgang ersetzt nur den Eintrag seiner Quelle. Fehler hier dürfen den
eigentlichen Feed-NIE gefährden (deshalb komplett in try/except).
"""
import json

# Alle Feed-Typen, die ins Protokoll schreiben dürfen (Reihenfolge = Anzeige
# im Dashboard-Abschnitt "Versuche je Quelle").
SOURCES = [
    ("football-data", "football-data.org (Spielfeld-/Ergebnis-Sync)"),
    ("openligadb", "OpenLigaDB (Fallback + Nachzug)"),
    ("minute", "API-Football · Live-Minute"),
    ("goals", "API-Football · Torschützen"),
    ("torjaeger", "OpenLigaDB · Torjäger-Liste (Torschützen)"),
    ("the_odds_api", "The-Odds-API · Tipp-Optimizer-Quoten (nur bei Abruf)"),
]

SETTING_KEY = "datasourc…ivity"


def record(kind, ok, note=""):
    """Ein Versuch -> Protokoll. Ruft der Aufrufer NACH echtem HTTP-Kontakt
    auf. Fehler hier sind bewusst still (Debug-Log)."""
    from datetime import datetime, timezone
    from scoring import get_setting, set_setting
    try:
        raw = get_setting(SETTING_KEY, "") or ""
        try:
            data = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[str(kind)] = {
            "at": datetime.now(timezone.utc).isoformat(),
            "ok": bool(ok),
            "note": (str(note or "").strip())[:140],
        }
        set_setting(SETTING_KEY, json.dumps(data, ensure_ascii=False))
    except Exception as e:  # pragma: no cover - nur Sicherheitsnetz
        try:
            from flask import current_app
            current_app.logger.debug(f"datasource-activity({kind}): {e}")
        except Exception:
            pass


def entries():
    """Aktuelles Protokoll als Dict (leer, wenn nie protokolliert)."""
    from scoring import get_setting
    try:
        raw = get_setting(SETTING_KEY, "") or ""
        data = json.loads(raw) if raw else {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
