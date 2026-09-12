"""Torjaeger-Rangliste (Torschuetzenliste) - gratis ueber den API-Football-Key.

Hintergrund (12.09.2026): football-data.org liefert Spieler-/Scorer-Daten nur
im Bezahlplan; API-Football bietet die offizielle Top-Scorer-Liste der Liga im
dauerhaft kostenlosen Plan (GET /statistics/league/top_scorers). Kein Key
gesetzt => Modul ist komplett inaktiv (wie Minute-/Goal-Boost).

Grundsaetze:
- Nur echte Feed-Daten, kein Geschaetztes. Abruffehler behalten die zuletzt
  erfolgreiche Liste (Setting-Cache, JSON) - die Seite bleibt stets bedienbar.
- Budgetwaechter: fruehestens alle 6 h, max. 2 Abrufe/Tag. Zusammen mit
  Minute-Boost (<=90) und Goal-Boost (<=8) bleiben wir immer <=100 Calls/Tag.
- Nutzt denselben Token wie die Booster (Admin -> Einstellungen -> APIs).
"""
import json
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from minute_boost import (apifootball_token, _gate_cache, _name_tokens,
                          _AF_LEAGUE_IDS, _plan_blocked, plan_block_mark,
                          af_errors_text, record_apifootball_activity)
from scoring import get_setting, set_setting

CACHE_KEY = "top_scorers_data"
CACHE_VERSION = 1
# Offizieller Endpoint laut API-Football-Docs (12.09.2026 geprueft):
# GET /players/topscorers?league=..&season=..  - NICHT statistics/...
_URL = ("https://v3.football.api-sports.io/players/topscorers"
        "?league={league}&season={season}")
_FAIL_RETRY_SECONDS = 1800  # nach fehlgeschlagenem Versuch schneller erneut
_MIN_INTERVAL = 6 * 3600
_DAILY_BUDGET = 2
_GATE_KEY = "topscorers:gate"

# In-Prozess-Fallback, wenn der Redis-Cache deaktiviert ist (Muster wie bei
# den anderen Boostern; Multi-Worker-Fall regelt der Cache).
_STATE_FALLBACK = {"day": "", "count": 0, "last": 0.0}


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_top_scorers(payload):
    """API-Football-Response -> kompakte, sortierte Rangliste (Top 20)."""
    rows = []
    for item in (payload.get("response") or []):
        if not isinstance(item, dict):
            continue
        player = item.get("player") or {}
        stats = {}
        for candidate in (item.get("statistics") or []):
            if isinstance(candidate, dict):
                stats = candidate
                break
        goals_obj = stats.get("goals") or {}
        goals = _to_int(goals_obj.get("total"))
        if goals < 1:
            continue  # nur Spieler mit mindestens einem Tor z00e4hlen
        pen = stats.get("penalties") or {}
        games = stats.get("games") or {}
        rows.append({
            "player_id": player.get("id"),
            "name": (player.get("name") or "").strip() or "unbekannt",
            "photo": (player.get("photo") or "").strip() or None,
            "position": (player.get("position") or "").strip() or None,
            "team": ((player.get("team") or {}).get("name") or "").strip(),
            "goals": goals,
            "assists": _to_int(goals_obj.get("assists")),
            "pen_scored": _to_int(pen.get("scored")) or None,
            "pen_missed": _to_int(pen.get("missed")) or None,
            "apps": _to_int(games.get("appearences")),   # API-Tipp bleibt so
            "minutes": _to_int(games.get("minutes")) or None,
        })
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
            interval = _FAIL_RETRY_SECONDS  # Fehler sollen nicht halben Tag brachliegen
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
    """Holt die Top-Scorer-Liste und legt sie im Setting-Cache ab (Best effort).

    force=True umgeht das 6-h-Intervall (Admin-Button), verbraucht aber
    weiterhin das taegliche Budget.
    """
    now = now or datetime.now(timezone.utc)
    token = apifootball_token()
    if not token:
        return {"ok": False, "skipped": "no-token"}
    if _plan_blocked("torjaeger"):
        return {"ok": False, "skipped": "plan-blocked"}
    comp = (current_app.config.get("COMPETITION") or "BL1")
    league = _AF_LEAGUE_IDS.get(comp)
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
        r = requests.get(url, headers={"x-apisports-key": token}, timeout=8)
    except Exception as e:
        current_app.logger.debug(f"top-scorers: Request fehlgeschlagen: {e}")
        record_apifootball_activity("torjaeger", False, f"Netzwerk: {e}")
        return {"ok": False, "error": str(e)}
    if r.status_code != 200:
        record_apifootball_activity("torjaeger", False, f"HTTP {r.status_code}")
        return {"ok": False, "http": r.status_code}
    try:
        payload = r.json()
    except Exception:
        record_apifootball_activity("torjaeger", False, "Antwort kein JSON")
        return {"ok": False, "bad_json": True}
    if payload.get("errors"):
        current_app.logger.info(f"top-scorers: API-Football meldet: {payload['errors']}")
        _errtxt = af_errors_text(payload)
        plan_block_mark("torjaeger", _errtxt)
        record_apifootball_activity("torjaeger", False, "API: " + _errtxt)
        return {"ok": False, "api_errors": True}
    rows = _parse_top_scorers(payload)
    if not rows:
        record_apifootball_activity("torjaeger", False, "Liste leer (Spielfrei?)")
        return {"ok": False, "empty": True}
    set_setting(CACHE_KEY, json.dumps({
        "v": CACHE_VERSION, "fetched_at": now.isoformat(),
        "season": str(season), "entries": rows,
    }, ensure_ascii=False))
    current_app.logger.info(f"top-scorers: Rangliste mit {len(rows)} Spielern aktualisiert")
    record_apifootball_activity("torjaeger", True, f"{len(rows)} Spieler")
    return {"ok": True, "count": len(rows)}


def refresh_top_scorers(force=False):
    """Stiller Auto-Refresh-Haeckchen (Cron/Hook): Fehler nie laut, nie fatal."""
    try:
        return fetch_top_scorers(force=force)
    except Exception as e:  # Doppel-Sicherung: Hook darf keinen Sync-Call kippen
        current_app.logger.debug(f"top-scorers: Refresh uebersprungen: {e}")
        return {"ok": False, "error": str(e)}


def top_scorers_listing(allow_refresh=True):
    """(entries, meta) fuer die Seite; cache-bevorzugt, ggf. frischer Abruf."""
    data = load_cache()
    if allow_refresh and (data is None or _stale(data)):
        fetch_top_scorers()
        data = load_cache() or data
    entries = (data or {}).get("entries") or []
    if entries:
        # Kurze Team-Kuerzel + Logos aus der eigenen DB anreichern (best effort)
        from models import Team
        teams = Team.query.all()
        for row in entries:
            tok = _name_tokens(row.get("team") or "")
            db_team = None
            for t in teams:
                tt = _name_tokens(t.name or "")
                if tok and tt and (tok <= tt or tt <= tok):
                    db_team = t
                    break
            row["short"] = db_team.short_name if db_team else (row.get("team") or "?")[:8]
            row["logo"] = (db_team.logo if db_team else None)
    meta = {
        "fetched_at": (data or {}).get("fetched_at"),
        "season": (data or {}).get("season"),
        "empty": not entries,
        "has_token": bool(apifootball_token()),
        "last_error": None,
        "last_attempt": None,
    }
    if not entries:
        # Ehrlichkeit statt Raterei: letzter fehlgeschlagener Versuch inkl.
        # echtem API-Grund (z. B. Plan-/Saison-Grenze) auf der Seite anzeigen.
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
