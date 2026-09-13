"""Torjaeger-Rangliste (Torschuetzenliste) - seit 13.09.2026 ueber OpenLigaDB.

Hintergrund: Der API-Football-Free-Plan beantwortete die aktuelle Saison bei
players/topscorers planmaessig mit "try from 2022 to 2024" (Live-Test
12.09.2026), football-data.org liefert Scorer nur im Bezahltier. Die
Pruefung am 13.09. fand mit OpenLigaDB `GET /getgoalgetters/{liga}/{saison}`
eine dauerhaft kostenlose, KEYFREIE Quelle fuer die aktuelle
Torschuetzenliste - sie ist jetzt die einzige Quelle dieses Moduls
(kein API-Football-Budgetverbrauch, kein Plan-Gate mehr).

Grundsaetze (unveraendert):
- Nur echte Feed-Daten, kein Geschaetztes. Bei Abruffehlern behaelt die
  zuletzt erfolgreiche Liste (Setting-Cache, JSON) - die Seite bleibt stets
  bedienbar, der letzte Fehlergrund wird auf ihr ausgewiesen.
- Sparsamkeit: fruehestens alle 30 Minuten ein HTTP-Versuch (Seitenbesuch),
  dazu der Sync-Hook nach jedem OLB-Abgleich; nach Fehlschgen 10 Minuten
  (Fehler sollen nicht halbtags brachliegen).
"""
import json
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from minute_boost import _gate_cache
from scoring import get_setting, set_setting

CACHE_KEY = "top_scorers_data"
CACHE_VERSION = 2  # OLB-Umstieg: Felder nur name/goals, altes Schema verwerfen
_URL = "https://api.openligadb.de/getgoalgetters/{league}/{season}"
_OLB_LEAGUES = {"BL1": "bl1", "BL2": "bl2"}
_FAIL_RETRY_SECONDS = 600
_MIN_INTERVAL = 30 * 60
_DAILY_BUDGET = 96  # nur Sanftmut-Deckel; OpenLigaDB hat kein Konto
_GATE_KEY = "topscorers:gate"

# In-Prozess-Fallback, wenn der Redis-Cache deaktiviert ist (Muster wie bei
# den anderen Boostern; Multi-Worker-Fall regelt der Cache).
_STATE_FALLBACK = {"day": "", "count": 0, "last": 0.0}


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _activity_record(ok, note=""):
    """Echte Abruefe (Erfolg WIE Fehler) ins Quellen-Protokoll; nie fatal."""
    try:
        import datasource_activity as _ds
        _ds.record("torjaeger", ok, note)
    except Exception as e:  # pragma: no cover - Protokoll darf nichts kippen
        current_app.logger.debug(f"top-scorers activity: {e}")


def _parse_goalgetters(payload):
    """OpenLigaDB-Liste -> [{name, goals}] (Tore desc, dann Name, Top 20)."""
    rows = []
    for item in (payload or []):
        if not isinstance(item, dict):
            continue
        goals = _to_int(item.get("goalCount"))
        name = str(item.get("goalGetterName") or "").strip()
        if goals < 1 or not name:
            continue  # nur echte Torschuetzen
        rows.append({"name": name, "goals": goals})
    rows.sort(key=lambda r: (-r["goals"], r["name"]))
    return rows[:20]


def load_cache():
    raw = get_setting(CACHE_KEY, "") or ""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("v") != CACHE_VERSION:
        return None
    if not isinstance(data.get("entries"), list):
        return None
    return data


def _stale(data, now=None):
    now = now or datetime.now(timezone.utc)
    if not data:
        return True
    try:
        fetched = datetime.fromisoformat(str(data.get("fetched_at")))
    except (TypeError, ValueError):
        return True
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return now - fetched > timedelta(seconds=_MIN_INTERVAL)


def _gate_allow(now=None):
    """True, wenn abgerufen werden darf; zaehlt den Verbrauch bei True hoch."""
    now = now or datetime.now(timezone.utc)
    cache_obj = _gate_cache()
    day = now.strftime("%Y-%m-%d")
    state = None
    if cache_obj is not None:
        raw = cache_obj.get(_GATE_KEY)
        if isinstance(raw, dict):
            state = raw
    if state is None:
        state = dict(_STATE_FALLBACK)
    if state.get("day") != day:
        state = {"day": day, "count": 0, "last": 0.0}
    if int(state.get("count", 0)) >= _DAILY_BUDGET:
        return False
    interval = _MIN_INTERVAL
    try:
        import datasource_activity as _ds
        last_entry = (_ds.entries() or {}).get("torjaeger")
        if last_entry and not last_entry.get("ok"):
            interval = _FAIL_RETRY_SECONDS  # Fehler nicht halbtags brachliegen
    except Exception:
        pass
    if (now.timestamp() - float(state.get("last") or 0.0)) < interval:
        return False
    state = {"day": day, "count": int(state.get("count", 0)) + 1,
             "last": now.timestamp()}
    _STATE_FALLBACK.update(state)
    if cache_obj is not None:
        cache_obj.set(_GATE_KEY, state, ttl=26 * 3600)
    return True


def fetch_top_scorers(force=False, now=None):
    """Holt die Torschuetzenliste von OpenLigaDB (Setting-Cache, Best effort).

    force=True umgeht das 30-min-Intervall (Sync-Hook); der Tagesdeckel bleibt.
    """
    now = now or datetime.now(timezone.utc)
    comp = (current_app.config.get("COMPETITION") or "BL1")
    league = _OLB_LEAGUES.get(comp)
    if not league:
        return {"ok": False, "skipped": "league-unsupported"}
    if not force and not _gate_allow(now):
        return {"ok": False, "skipped": "throttled"}
    try:
        from sync_shared import current_sync_season_code
        season = current_sync_season_code()
    except Exception:
        season = current_app.config.get("SEASON", "2026")
    url = _URL.format(league=league, season=season)
    try:
        r = requests.get(url, timeout=10)
    except Exception as e:
        current_app.logger.debug(f"top-scorers: Request fehlgeschlagen: {e}")
        _activity_record(False, f"Netzwerk: {e}")
        return {"ok": False, "error": str(e)}
    if r.status_code != 200:
        _activity_record(False, f"HTTP {r.status_code}")
        return {"ok": False, "http": r.status_code}
    try:
        payload = r.json()
    except Exception:
        _activity_record(False, "Antwort kein JSON")
        return {"ok": False, "bad_json": True}
    rows = _parse_goalgetters(payload)
    if not rows:
        _activity_record(False, "Liste leer (Saisonstart?)")
        return {"ok": False, "empty": True}
    set_setting(CACHE_KEY, json.dumps({
        "v": CACHE_VERSION, "fetched_at": now.isoformat(),
        "season": str(season), "entries": rows,
    }, ensure_ascii=False))
    current_app.logger.info(f"top-scorers: Rangliste mit {len(rows)} Spielern aktualisiert")
    _activity_record(True, f"{len(rows)} Spieler")
    return {"ok": True, "count": len(rows)}


def refresh_top_scorers(force=True):
    """Stiller Auto-Refresh-Haken (Sync): Fehler nie laut, nie fatal.

    force=True, weil der Sync selbst der seltene Taktgeber ist - das
    30-min-Intervall bleibt als Schutz vor Sync-Lawinen bestehen.
    """
    try:
        return fetch_top_scorers(force=force)
    except Exception as e:  # Doppel-Sicherung: Hook darf keinen Sync kippen
        current_app.logger.debug(f"top-scorers: Refresh uebersprungen: {e}")
        return {"ok": False, "error": str(e)}


def top_scorers_listing(allow_refresh=True):
    """(entries, meta) fuer die Seite; cache-bevorzugt, ggf. frischer Abruf."""
    data = load_cache()
    if allow_refresh and (data is None or _stale(data)):
        fetch_top_scorers()
        data = load_cache() or data
    entries = (data or {}).get("entries") or []
    meta = {
        "fetched_at": (data or {}).get("fetched_at"),
        "season": (data or {}).get("season"),
        "empty": not entries,
        "source": "OpenLigaDB",
        "last_error": None,
        "last_attempt": None,
    }
    if not entries:
        # Ehrlichkeit statt Raetselraten: letzter fehlgeschlagener Versuch
        # inkl. echtem Grund auf der Seite anzeigen.
        try:
            import datasource_activity as _ds
            act = (_ds.entries() or {}).get("torjaeger") or {}
            if act and not act.get("ok"):
                meta["last_error"] = (act.get("note") or "").strip() or None
                at = str(act.get("at") or "")
                meta["last_attempt"] = at[:16].replace("T", " ") if at else None
        except Exception:
            pass
    return entries, meta
