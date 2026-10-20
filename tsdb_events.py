"""TheSportsDB-Ereignis-Boost (138) - Karten & Auswechslungen key-frei.

Hintergrund (18.10.2026): API-Football verwirft den Free-Key fuer die
laufende Saison ("Free plans do not have access to this season, try from
2022 to 2024"), OpenLigaDB pflegt Karten/Wechsel nicht (matchEvents leer).
TheSportsDB liefert mit dem offiziellen Test-Key "123" (der alte Key "3"
ist dauerhaft abgeschaltet) eine Timeline pro Spiel: Tore (mit Vorlage),
Karten (Gelb/Gelb-Rot/Rot) und Auswechslungen - fuer die Bundesliga
2026/27 live nachgeprueft (ST 6, Schalke-Mainz 2508383).

Grundsaetze (wie die uebrigen Boosts):
- Nur frisch begonnene/ferlige Spiele im 2-Tage-Fenster; ohne Kandidaten
  kein Request.
- 1 eventsround-Call je betroffenem Spieltag + 1 lookuptimeline-Call je
  Match; eigener Throttle + Tagesbudget (Free-Test-Key, konservativ).
- Merge-only: stehende Zeilen (Goal-Boost/OLB) werden nicht ueber-
  schrieben; einzige Ausnahme: leere Vorlage einer gf-Zeile wird aus der
  reicheren TSDB-Timeline nachgefuellt. Keine Duplikate.
- Match-Pairing: intRound == Spieltag UND Anstosszeit ±45 min UND auf
  beiden Seiten je mind. ein Namens-Token-Overlap; nicht eindeutig ->
  bewusst raus.
"""
import json
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from extensions import db
from models import Match

_TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
_TSDB_ROUND_URL = _TSDB_BASE + "/eventsround.php?id={league}&r={round}&s={season}"
_TSDB_TIMELINE_URL = _TSDB_BASE + "/lookuptimeline.php?id={eid}"

# Nur BL1 ist verdrahtet (idLeague von TheSportsDB).
_TSDB_LEAGUE_IDS = {"BL1": "4331"}

_MIN_INTERVAL = 600            # fruehestens alle 10 Minuten ein Lauf mit Calls
_DAILY_BUDGET = 30             # 2-3 x eventsround + 9 x Timeline je Spieltag
_GATE_KEY = "tsdb_events:gate"
_STATE_FALLBACK = {"day": "", "count": 0, "last": 0.0}

_STATUS_CANDIDATE = ("live", "finished")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; WulmstoerperTipprunde/1.0)"}


def _gate_cache():
    try:
        from cache import cache as _c
        if _c.enabled:
            return _c
    except Exception:
        pass
    return None


def _season_label(code):
    """Sync-Saisoncode ("2026") -> TSDB-Label ("2026-2027")."""
    try:
        return "%s-%d" % (code, int(code) + 1)
    except (TypeError, ValueError):
        return None


def _parse_ts(value):
    """TSDB strTimestamp ("2026-10-17T13:30:00", UTC ohne Suffix) -> aware."""
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _name_tokens(name):
    """Robuste Namens-Token (RFC-frei, bewusst simpel): lowercase, nur
    Buchstaben/Zahlen, typische Praefixes weg. Reicht fuer Overlap-Check."""
    import re
    junk = {"fc", "cf", "sc", "ac", "sv", "tsv", "tsg", "vfb", "vfl", "rb",
            "rbl", "bvb", "04", "05", "09", "1.", "der", "de", "club", "cfc"}
    norm = re.sub(r"[^a-zäöüß0-9. ]+", " ", (name or "").lower())
    return {t for t in norm.split() if t and t not in junk}


def _team_tokens_overlap(a, b):
    """Mind. ein gemeinsamer Token (Bayern ueber 'bayern', SV Werder Bremen
    ueber 'Werder Bremen', RB Leipzig ueber 'leipzig')."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    return bool(ta and tb and (ta & tb))


def rows_from_timeline(timeline):
    """TSDB timeline[] -> Zeilen im Seitenformat (Tore/Karten/Wechsel).

    Konventionen (per Live-Probe verifiziert): strTimeline 'Goal'/'Card'/
    'subst' (Subst lowercase!), strHome 'Yes'/'No', intTime Minute,
    strAssist = eingewechselt bei Subst (API-Football-Konvention) bzw.
    Vorlage bei Toren. VAR/Missed-Penalty/nicht erteilte Karten bleiben
    bewusst draussen.
    """
    rows = []
    for ev in timeline or []:
        if not isinstance(ev, dict):
            continue
        kind = str(ev.get("strTimeline") or "").strip().lower()
        detail = str(ev.get("strTimelineDetail") or "").strip()
        try:
            minute = int(ev.get("intTime") or 0)
        except (TypeError, ValueError):
            continue
        if minute < 1:
            continue
        side = {"yes": "home", "no": "away"}.get(
            str(ev.get("strHome") or "").strip().lower())
        if side is None:
            continue
        player = str(ev.get("strPlayer") or "").strip() or None
        assist = str(ev.get("strAssist") or "").strip() or None
        if kind == "goal":
            if detail.lower() == "missed penalty":
                continue  # verschossener Elfmeter: kein Tor
            rows.append({"kind": "gf", "min": minute, "team": side,
                         "player": player, "assist": assist,
                         "penalty": detail.lower() == "penalty",
                         "own_goal": detail.lower() == "own goal",
                         "src": "tsdb"})
        elif kind == "card":
            d = detail.lower()
            if "missing" in d or "missed" in d:
                continue  # nicht erteilte Karte: kein Ereignis
            if "second" in d or "->" in detail:
                label = "yellow_red"
            elif "red" in d:
                label = "rot"
            elif "yellow" in d:
                label = "gelb"
            else:
                continue
            rows.append({"kind": "olb", "type": "card", "card": label,
                         "min": minute, "team": side, "player": player,
                         "src": "tsdb"})
        elif kind == "subst":
            rows.append({"kind": "sub", "min": minute, "team": side,
                         "player": player, "assist": assist, "src": "tsdb"})
        # Var & unbekannte Typen bleiben draussen
    rows.sort(key=lambda r: (r["min"], 0 if r["kind"] == "gf" else 1))
    return rows


def _merge_rows(m, rows):
    """Merge-only in Match.events; Ruecklauf: Anzahl veraenderter Spiele (0/1).

    - gf: (min, team) frei -> append; belegt -> nur leere Vorlage nachfuellen.
    - card: (min, team, card) entscheidet.
    - sub: (min, team, player) entscheidet.
    """
    try:
        existing = json.loads(m.events or "[]")
    except (TypeError, ValueError):
        existing = []
    if not isinstance(existing, list):
        existing = []
    gf_marks = {(int(r.get("min") or 0), r.get("team"))
                for r in existing if isinstance(r, dict) and r.get("kind") == "gf"}
    card_marks = {(int(r.get("min") or 0), r.get("team"), str(r.get("card") or ""))
                  for r in existing if isinstance(r, dict) and r.get("type") == "card"}
    sub_marks = {(int(r.get("min") or 0), r.get("team"), str(r.get("player") or ""))
                 for r in existing if isinstance(r, dict) and r.get("kind") == "sub"}
    changed = False
    for r in rows:
        if r["kind"] == "gf":
            key = (r["min"], r["team"])
            if key in gf_marks:
                for ex in existing:
                    if (isinstance(ex, dict) and ex.get("kind") == "gf"
                            and (int(ex.get("min") or 0), ex.get("team")) == key
                            and not (ex.get("assist") or "").strip()
                            and (r.get("assist") or "").strip()):
                        ex["assist"] = r["assist"]
                        changed = True
                        break
                continue
            gf_marks.add(key)
        elif r.get("type") == "card":
            key = (r["min"], r["team"], r["card"])
            if key in card_marks:
                continue
            card_marks.add(key)
        else:
            key = (r["min"], r["team"], str(r.get("player") or ""))
            if key in sub_marks:
                continue
            sub_marks.add(key)
        existing.append(r)
        changed = True
    if changed:
        existing.sort(key=lambda x: (int(x.get("min") or 0),
                                     0 if isinstance(x, dict) and x.get("kind") == "gf" else 1))
        m.events = json.dumps(existing, ensure_ascii=False)
    return changed


def boost_events_from_thesportsdb(now=None):
    """Karten/Auswechslungen/Vorlagen key-frei nachziehen (siehe Moduldoc)."""
    now = now or datetime.now(timezone.utc)
    comp = (current_app.config.get("COMPETITION") or "BL1")
    league = _TSDB_LEAGUE_IDS.get(comp)
    if not league:
        return {"ok": True, "updated": 0, "skipped": "league-unsupported"}

    from competition_helpers import filter_matches_for_active_competition
    from sync_shared import current_sync_season_code
    cand_q = Match.query.filter(
        Match.kickoff >= now - timedelta(days=2),
        Match.status.in_(_STATUS_CANDIDATE),
    )
    candidates = [m for m in filter_matches_for_active_competition(cand_q).all()
                  if m.matchday]
    if not candidates:
        return {"ok": True, "updated": 0}

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
        return {"ok": True, "updated": 0, "budget": "day-exhausted"}
    if time.time() - float(state.get("last") or 0) < _MIN_INTERVAL:
        return {"ok": True, "updated": 0, "throttled": True}

    season = _season_label(current_sync_season_code())
    if not season:
        return {"ok": True, "updated": 0, "skipped": "season"}

    matchdays = sorted({m.matchday for m in candidates})
    updated = 0
    for md in matchdays:
        if int(state.get("count", 0)) >= _DAILY_BUDGET:
            break
        try:
            r = requests.get(_TSDB_ROUND_URL.format(league=league, round=md,
                                                    season=season),
                             headers=_UA, timeout=10)
            payload = r.json() if r.status_code == 200 else None
        except Exception as e:
            current_app.logger.debug(f"tsdb-events: eventsround fehlgeschlagen: {e}")
            payload = None
        state = {"day": day, "count": int(state.get("count", 0)) + 1,
                 "last": time.time()}
        if not isinstance(payload, dict):
            continue
        for ev in payload.get("events") or []:
            if not isinstance(ev, dict) or not ev.get("idEvent"):
                continue
            ts = _parse_ts(ev.get("strTimestamp"))
            if ts is None:
                continue
            matches = [
                m for m in candidates
                if m.matchday == md
                and abs((ts - (m.kickoff if m.kickoff.tzinfo
                               else m.kickoff.replace(tzinfo=timezone.utc)))
                        .total_seconds()) <= 2700
                and _team_tokens_overlap(ev.get("strHomeTeam"), m.home_team.name)
                and _team_tokens_overlap(ev.get("strAwayTeam"), m.away_team.name)
            ]
            if len(matches) != 1:
                continue
            m = matches[0]
            if int(state.get("count", 0)) >= _DAILY_BUDGET:
                break
            try:
                r2 = requests.get(_TSDB_TIMELINE_URL.format(eid=ev["idEvent"]),
                                  headers=_UA, timeout=10)
                p2 = r2.json() if r2.status_code == 200 else None
            except Exception as e:
                current_app.logger.debug(f"tsdb-events: Timeline fehlgeschlagen: {e}")
                p2 = None
            state = {"day": day, "count": int(state.get("count", 0)) + 1,
                     "last": time.time()}
            timeline = p2.get("timeline") if isinstance(p2, dict) else None
            if not timeline:
                continue
            if _merge_rows(m, rows_from_timeline(timeline)):
                updated += 1
    _STATE_FALLBACK.update(state)
    if cache_obj is not None:
        cache_obj.set(_GATE_KEY, state, ttl=26 * 3600)
    try:  # (139) Admin-Protokoll ("Versuche je Quelle")
        from datasource_activity import record
        record("tsdb_events", True,
               f"{updated} Spiele ergaenzt (Karten/Wechsel/Vorlagen)"
               if updated else "keine Aenderungen")
    except Exception:
        pass
    if updated:
        db.session.commit()
        current_app.logger.info(f"tsdb-events: Ereignisse fuer {updated} Spiele "
                                f"ergaenzt (Karten/Wechsel/Vorlagen, 0 EUR)")
    return {"ok": True, "updated": updated}
