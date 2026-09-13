"""Minute-Boost ueber API-Football (api-sports.io) - echte Schiedsrichterminute gratis.

Hintergrund (11.09.2026): football-data.org liefert im Free-Tier die echte
Spielminute nur unregelmaessig, OpenLigaDB gar keine (deshalb dort nur Score-
Boost + "≈"-Struktur-uhr). API-Football hat im dauerhaft kostenlosen Plan
(100 Requests/Tag) die reale Minute (`elapsed` inkl. Nachspielzeit-Info) im
Live-Feed.

Grundsaetze:
- Bedarfsgesteuert: der Aufruf haengt an fetch_live_match_updates() und
  passiert damit nur, wenn jemand das Live-Center oeffnet UND ein Spiel im
  Fenster liegt. Ausserhalb: null Requests.
- Budgetwaechter: harte Obergrenze pro Tag (inkl. Safe-Rest) und automatischer
  Drehzahl-Regler - wird das Budget knapp, wird der Abstand gestreckt, bis es
  bis Mitternacht reicht; danach stiller Rueckfall (UI zeigt dann die
  bewaehrte "≈"-Uhr, nichts friert ein oder luegt).
- Kein Token gesetzt => Modul ist komplett inaktiv (Flag "no-token").
- Geschriebene Minute ist ECHT (feed-basiert) -> live_clock_for() zeigt sie
  ohne "≈". Statusaenderungen laufen ueber apply_match_update (Monotonie).
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from extensions import db
from models import Match
from match_results import apply_match_update
from scoring import get_setting

_URL = "https://v3.football.api-sports.io/fixtures?live=all"
_MIN_INTERVAL_SECONDS = 90
_DAILY_BUDGET = 90  # von 100 - Safe-Rest fuer die uebrigen Features der App
_GATE_KEY = "minute_boost:gate"

# In-Prozess-Fallback, wenn der Redis-Cache deaktiviert ist (gleiche Idee wie
# beim OLB-Boost; bei mehreren Workern gilt der Cache-Wert, sonst prozesslokal).
_STATE_FALLBACK = {"day": "", "count": 0, "last": 0.0}

_STATUS_LIVE = {"1H", "2H", "ET", "BT", "P"}
_STATUS_FINISHED = {"FT", "AET", "PEN"}
_JUNK_TOKENS = {"fc", "cf", "sc", "ac", "sv", "tsv", "tsg", "vfb", "vfl", "rb",
                "rbl", "bvb", "04", "05", "09", "1.", "der", "de", "club", "cfc"}


def apifootball_token():
    """Token aus Admin-Settings, sonst aus Umgebung (APIFOOTBALL_TOKEN)."""
    tok = (get_setting("apifootball_token", "") or "").strip()
    if not tok:
        tok = (os.environ.get("APIFOOTBALL_TOKEN", "") or "").strip()
    return tok


def _name_tokens(name):
    norm = re.sub(r"[^a-zäöüß0-9. ]+", " ", (name or "").lower())
    return {t for t in norm.split() if t and t not in _JUNK_TOKENS}


def _teams_match(db_match, fixture_item):
    teams = (fixture_item.get("teams") or {})
    home_toks = _name_tokens((teams.get("home") or {}).get("name"))
    away_toks = _name_tokens((teams.get("away") or {}).get("name"))
    if not home_toks or not away_toks:
        return False
    db_home = _name_tokens(db_match.home_team.name)
    db_away = _name_tokens(db_match.away_team.name)
    def _pair(a, b):
        return bool(a) and bool(b) and (a <= b or b <= a)
    return _pair(db_home, home_toks) and _pair(db_away, away_toks)


def _parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_utc(dt):
    """SQLite liefert naive UTC-Stempel, API-Stamps sind aware - vergleichbar machen."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _gate_cache():
    try:
        from cache import cache as _c
        if _c.enabled:
            return _c
    except Exception:
        pass
    return None


def _gate_read(cache_obj, day):
    state = None
    if cache_obj is not None:
        raw = cache_obj.get(_GATE_KEY)
        if isinstance(raw, dict):
            state = raw
    if state is None:
        state = dict(_STATE_FALLBACK)
    if state.get("day") != day:
        state = {"day": day, "count": 0, "last": 0.0}
    return state


def _gate_write(cache_obj, state):
    _STATE_FALLBACK.update(state)
    if cache_obj is not None:
        cache_obj.set(_GATE_KEY, state, ttl=26 * 3600)


# ------------------------------------------------------------ Goal-Boost ----
# Torschuetzen pro Spiel aus demselben (optionalen!) API-Football-Free-Key.
# Eigener Mini-Budget-Zaehler, damit Minute-Boost (max. 90) + Goals zusammen
# die 100 Calls/Tag des Free-Plans nie uebersteigen.
_GOAL_GATE_KEY = "goal_boost:gate"
_GOAL_STATE_FALLBACK = {"day": "", "count": 0, "last": 0.0}
_GOAL_MIN_INTERVAL = 600       # fruehestens alle 10 Minuten ein Fetch
_GOAL_DAILY_BUDGET = 8         # reicht: ein Spieltag-Abend benoetigt 1-2 Calls
_AF_LEAGUE_IDS = {"BL1": 181, "BL2": 79, "WC": 48, "ELC": 39, "FL1": 61, "SA": 135}
_GOAL_FIXTURES_URL = "https://v3.football.api-sports.io/fixtures?league={league}&season={season}&last=9"


def _goal_events_writable(match):
    """True, wenn Match.events leer ist oder nur aus unserem eigenen
    Goal-Boost-Format (kind='gf') besteht - Fremdformate (live_scoring-Legat)
    werden nie ueberschrieben."""
    ev = (match.events or "").strip()
    if not ev:
        return True
    try:
        parsed = json.loads(ev)
    except Exception:
        return False
    if not isinstance(parsed, list):
        return False
    if not parsed:
        return True
    return all(isinstance(x, dict) and x.get("kind") == "gf" for x in parsed)


def _parse_goal_rows(item):
    """goals[] eines API-Football-Fixtures -> kompakte, sortierte Zeilen."""
    # teams sitzt im API-Football-Response auf Top-Level (nicht im fixture)
    home_id = ((item.get("teams") or {}).get("home") or {}).get("id")
    rows = []
    for g in item.get("goals") or []:
        if not isinstance(g, dict):
            continue
        time_obj = g.get("time") or {}
        try:
            elapsed = int(time_obj.get("elapsed"))
        except (TypeError, ValueError):
            continue
        if elapsed < 1:
            continue
        try:
            extra = int(time_obj.get("additional")) if time_obj.get("additional") else None
        except (TypeError, ValueError):
            extra = None
        gtype = g.get("type") or "Goal"
        rows.append({
            "kind": "gf",
            "min": elapsed,
            "extra": extra,
            "team": "home" if (g.get("team") or {}).get("id") == home_id else "away",
            "player": ((g.get("player") or {}).get("name") or "").strip() or None,
            "assist": ((g.get("assist") or {}).get("name") or "").strip() or None,
            "penalty": gtype == "Penalty",
            "own_goal": gtype == "Own Goal",
        })
    rows.sort(key=lambda r: (r["min"], r["extra"] or 0))
    return rows


def boost_goal_scorers_from_apifootball(now=None):
    """Torschuetzen-Listen fuer frisch beendete Spiele in Match.events ablegen.

    Quelle: GET /fixtures?league=..&season=..&last=9 (API-Football, Free-Plan) -
    das goals[]-Array enthaelt Schuetze, Minute (+Nachspielzeit), Elfmeter- und
    Eigentor-Marker. Aufgerufen im Live-Ketten-Hook: nur wenn es frisch
    beendete Spiele OHNE Goals-Daten gibt, max. alle 10 Minuten, max. 8/Tag.
    Ohne Token: kein Request, kein Effekt.
    """
    now = now or datetime.now(timezone.utc)
    token = apifootball_token()
    if not token:
        return {"ok": True, "updated": 0, "skipped": "no-token"}
    if _plan_blocked("goals"):
        return {"ok": True, "updated": 0, "skipped": "plan-blocked"}
    comp = (current_app.config.get("COMPETITION") or "BL1")
    league = _AF_LEAGUE_IDS.get(comp)
    if not league:
        return {"ok": True, "updated": 0, "skipped": "league-unsupported"}

    from competition_helpers import filter_matches_for_active_competition
    cand_q = Match.query.filter(
        Match.status == "finished",
        Match.kickoff >= now - timedelta(days=2),
        Match.kickoff <= now,
    )
    candidates = [m for m in filter_matches_for_active_competition(cand_q).all()
                  if _goal_events_writable(m)]
    if not candidates:
        return {"ok": True, "updated": 0}

    import time as _time
    cache_obj = _gate_cache()
    day = now.strftime("%Y-%m-%d")
    state = None
    if cache_obj is not None:
        raw = cache_obj.get(_GOAL_GATE_KEY)
        if isinstance(raw, dict):
            state = raw
    if state is None:
        state = dict(_GOAL_STATE_FALLBACK)
    if state.get("day") != day:
        state = {"day": day, "count": 0, "last": 0.0}
    if int(state.get("count", 0)) >= _GOAL_DAILY_BUDGET:
        return {"ok": True, "updated": 0, "budget": "day-exhausted"}
    if _time.time() - float(state.get("last") or 0.0) < _GOAL_MIN_INTERVAL:
        return {"ok": True, "updated": 0, "throttled": True}
    state = {"day": day, "count": int(state.get("count", 0)) + 1, "last": _time.time()}
    _GOAL_STATE_FALLBACK.update(state)
    if cache_obj is not None:
        cache_obj.set(_GOAL_GATE_KEY, state, ttl=26 * 3600)

    try:
        from sync_shared import current_sync_season_code
        season = current_sync_season_code()
    except Exception:
        season = current_app.config.get("SEASON", "2026")
    url = _GOAL_FIXTURES_URL.format(league=league, season=season)
    try:
        r = requests.get(url, headers={"x-apisports-key": token}, timeout=8)
    except Exception as e:
        current_app.logger.debug(f"goal-boost: Request fehlgeschlagen: {e}")
        record_apifootball_activity("goals", False, f"Netzwerk: {e}")
        return {"ok": True, "updated": 0, "error": str(e)}
    if r.status_code != 200:
        record_apifootball_activity("goals", False, f"HTTP {r.status_code}")
        return {"ok": True, "updated": 0, "http": r.status_code}
    try:
        payload = r.json()
    except Exception:
        record_apifootball_activity("goals", False, "Antwort kein JSON")
        return {"ok": True, "updated": 0}
    if payload.get("errors"):
        current_app.logger.info(f"goal-boost: API-Football meldet: {payload['errors']}")
        _errtxt = af_errors_text(payload)
        plan_block_mark("goals", _errtxt)
        record_apifootball_activity("goals", False, "API: " + _errtxt)
        return {"ok": True, "updated": 0, "api_errors": True}

    updated = 0
    for item in payload.get("response") or []:
        fix = item.get("fixture") or {}
        status_short = ((fix.get("status") or {}).get("short") or "").upper()
        if status_short not in _STATUS_FINISHED:
            continue
        kickoff = _parse_dt(fix.get("date"))
        if kickoff is None:
            continue
        matches = [m for m in candidates if _teams_match(m, item)
                   and abs((kickoff - _to_utc(m.kickoff)).total_seconds()) <= 900]
        if len(matches) != 1:
            continue
        m = matches[0]
        rows = _parse_goal_rows(item)
        if not rows:
            continue
        new_json = json.dumps(rows, ensure_ascii=False)
        if new_json != (m.events or ""):
            m.events = new_json
            updated += 1
    if updated:
        db.session.commit()
        current_app.logger.info(f"goal-boost: Torschuetzen fuer {updated} Spiele gespeichert")
    record_apifootball_activity("goals", True, f"{updated} Spiele mit Torschuetzen")
    return {"ok": True, "updated": updated}


# ------------------------------------------- Activity-Tracking (Admin) ----
# Kleines Protokoll, damit das Admin-Dashboard ("API Sync") zeigen kann,
# dass der API-Football-Key lebt: letzter Versuch je Feed-Typ + Budget.
def af_errors_text(payload):
    """API-Football-Fehler (dict/list/str) lesbar verdichten - fuer Protokoll
    und Logs, statt generischer Platzhaltertexte."""
    err = (payload or {}).get("errors")
    if not err:
        return ""
    try:
        import json as _json
        txt = _json.dumps(err, ensure_ascii=False)
    except Exception:
        txt = str(err)
    return txt[:130]


_PLAN_BLOCK_KEY = "apifootball_plan_block"


def _plan_blocked(feed):
    """True, wenn die API fur diesen Feed heute schon mit einem Plan-Hinweis
    abgewinkt hat - dann bleibt der Feed heute still (1 Probe am Tag, mehr ist
    Horspiel gegen eine klare Antwort; morgen versucht er automatisch erneut)."""
    try:
        import json as _json
        raw = get_setting(_PLAN_BLOCK_KEY, "") or ""
        if not raw:
            return False
        data = _json.loads(raw)
        return (isinstance(data, dict)
                and data.get(feed) == datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    except Exception:
        return False


def plan_block_mark(feed, errors_text):
    """Merkt 'plan'-Ablehnungen (Case-insensitive) pro Feed fuer den Tag."""
    if "plan" not in (errors_text or "").lower():
        return
    try:
        import json as _json
        from scoring import set_setting
        raw = get_setting(_PLAN_BLOCK_KEY, "") or ""
        try:
            data = _json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[feed] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        set_setting(_PLAN_BLOCK_KEY, _json.dumps(data))
    except Exception:
        pass


def record_apifootball_activity(kind, ok=True, note=""):
    """Kurzprotokoll (minute/goals/torjaeger) im gemeinsamen Quellen-Speicher.

    Bewusst nur echte HTTP-Versuche (Erfolg WIE Fehler), nie gedrosselte.
    Wrapper auf datasource_activity.record - Fehler gefaehrdet nie den Feed.
    """
    try:
        from datasource_activity import record as _rec
        _rec(kind, ok, note)
    except Exception as e:
        current_app.logger.debug(f"apifootball-activity({kind}): {e}")


def _today_gate_count(key, fallback, day):
    cache_obj = _gate_cache()
    state = None
    if cache_obj is not None:
        raw = cache_obj.get(key)
        if isinstance(raw, dict):
            state = raw
    if state is None:
        state = dict(fallback)
    if state.get("day") != day:
        return 0
    return int(state.get("count") or 0)


def apifootball_activity_summary():
    """Alles, was die API-Football-Karte im Admin-Dashboard anzeigt."""
    data = {}
    try:
        import datasource_activity as _ds
        all_entries = _ds.entries()
        data = {k: v for k, v in all_entries.items() if k in ("minute", "goals")}
    except Exception:
        data = {}
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    calls = {"minute": _today_gate_count(_GATE_KEY, _STATE_FALLBACK, day),
             "goals": _today_gate_count(_GOAL_GATE_KEY, _GOAL_STATE_FALLBACK, day)}
    caps = {"minute": _DAILY_BUDGET, "goals": _GOAL_DAILY_BUDGET}
    return {"token": bool(apifootball_token()), "entries": data,
            "calls": calls, "caps": caps}


def boost_minutes_from_apifootball(now=None):
    """Holt elapsed/Status von API-Football und aktualisiert die DB-Spiele.

    Rueckgabe ist ein Summary-Dict fuer den Sync-String; alle Fehlerpfade sind
    bewusst still (Live-Center darf durch einen optionalen Booster nicht
    kaputtgehen).
    """
    now = now or datetime.now(timezone.utc)
    token = apifootball_token()
    if not token:
        return {"ok": True, "updated": 0, "skipped": "no-token"}
    if _plan_blocked("minute"):
        return {"ok": True, "updated": 0, "skipped": "plan-blocked"}

    from competition_helpers import filter_matches_for_active_competition
    cand_q = Match.query.filter(
        Match.kickoff >= now - timedelta(hours=3, minutes=30),
        Match.kickoff <= now + timedelta(minutes=25),
        Match.status.in_(("scheduled", "live")),
    )
    candidates = filter_matches_for_active_competition(cand_q).all()
    if not candidates:
        return {"ok": True, "updated": 0}

    cache_obj = _gate_cache()
    day = now.strftime("%Y-%m-%d")
    state = _gate_read(cache_obj, day)
    budget_left = _DAILY_BUDGET - int(state.get("count", 0))
    if budget_left <= 0:
        return {"ok": True, "updated": 0, "budget": "day-exhausted"}

    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    secs_left = max(1, int((midnight - now).total_seconds()))
    interval = max(_MIN_INTERVAL_SECONDS, secs_left // max(1, budget_left))
    if time.time() - float(state.get("last") or 0.0) < interval:
        return {"ok": True, "updated": 0, "throttled": True}

    state = {"day": day, "count": int(state.get("count", 0)) + 1,
             "last": time.time()}
    _gate_write(cache_obj, state)

    try:
        r = requests.get(_URL, headers={"x-apisports-key": token}, timeout=8)
    except Exception as e:
        current_app.logger.debug(f"minute-boost: Request fehlgeschlagen: {e}")
        record_apifootball_activity("minute", False, f"Netzwerk: {e}")
        return {"ok": True, "updated": 0, "error": str(e)}
    if r.status_code != 200:
        record_apifootball_activity("minute", False, f"HTTP {r.status_code}")
        return {"ok": True, "updated": 0, "http": r.status_code}
    try:
        payload = r.json()
    except Exception:
        record_apifootball_activity("minute", False, "Antwort kein JSON")
        return {"ok": True, "updated": 0}
    if payload.get("errors"):
        current_app.logger.info(f"minute-boost: API-Football meldet: {payload['errors']}")
        _errtxt = af_errors_text(payload)
        plan_block_mark("minute", _errtxt)
        record_apifootball_activity("minute", False, "API: " + _errtxt)
        return {"ok": True, "updated": 0, "api_errors": True}

    updated = 0
    affected_ids = set()
    for item in payload.get("response") or []:
        fix = item.get("fixture") or {}
        kickoff = _parse_dt(fix.get("date"))
        if kickoff is None or abs((kickoff - now).total_seconds()) > 3.5 * 3600 + 600:
            continue
        matches = [m for m in candidates if _teams_match(m, item)
                   and abs((kickoff - _to_utc(m.kickoff)).total_seconds()) <= 720]
        if len(matches) != 1:
            continue  # unklar/kein Match -> lieber keine Minute als die falsche
        m = matches[0]
        status_obj = fix.get("status") or {}
        short = (status_obj.get("short") or "").upper()
        elapsed = status_obj.get("elapsed")
        try:
            elapsed = int(elapsed) if elapsed else None
        except (TypeError, ValueError):
            elapsed = None

        if short in _STATUS_LIVE or short == "HT":
            target_status, target_live = "live", True
        elif short in _STATUS_FINISHED:
            target_status, target_live = "finished", False
        else:
            continue  # NS / TBD / unbekannt: nichts anfassen

        goals = item.get("goals") or {}
        hs, as_ = goals.get("home"), goals.get("away")  # None = Feld unveraendert

        before = (m.status, m.home_score, m.away_score, m.minute, m.live_phase)
        apply_match_update(m, home_score=hs, away_score=as_,
                           status=target_status, is_live=target_live)
        if short == "HT":
            m.minute = elapsed
            m.live_phase = "PAUSED"
        elif short in _STATUS_FINISHED:
            m.minute = None
            m.live_phase = None
        else:
            if elapsed is not None:
                m.minute = max(1, elapsed)
            m.live_phase = "IN_PLAY"
        after = (m.status, m.home_score, m.away_score, m.minute, m.live_phase)
        if before != after:
            updated += 1
            affected_ids.add(m.id)

    if updated:
        db.session.commit()
        from scoring import recalculate_matches_points
        from badges import check_and_award_badges
        from models import User
        affected_users = recalculate_matches_points(affected_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)
        current_app.logger.info(
            f"minute-boost: {updated} Spiele mit API-Football-Minute aktualisiert")
    record_apifootball_activity("minute", True, f"{updated} Spiele aktualisiert")
    return {"ok": True, "updated": updated}
