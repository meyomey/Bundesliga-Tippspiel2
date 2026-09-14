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

MODULE_VERSION = "2026-09-13j"  # j = Picker folgt der Spieleransicht

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

# ------- optionaler Mannschaftsabgleich (13.09.2026, dritter Anlauf) -------
# Alle football-data-Routen sind fuer den Free-Key nachweislich dicht
# (competitions/{c}/clubs 404, standings 404, clubs/{id} 404 - drei
# Server-Protokolle vom 13.09.). Was bleibt, ist die kostenlose, keyfreie
# TheSportsDB-Spielersuche: pro Name liefert sie den aktuellen Verein - mit
# dreckigen Daten (_Retired Soccer & Co.). Deshalb gilt die Regel: ueber-
# nommen wird ein Treffer NUR, wenn sein Verein einem Liga-Team der eigenen
# DB zugeordnet werden kann; alles andere wird als Negativ gemerkt (7 Tage,
# kein erneuter Anlauf). Hoefstens 6 Nachschlagungen pro Ranglisten-Aktua-
# lisierung, Treffer wie Niete cached - die 20-er Liste ist damit nach
# spaetestens vier Laeufen abgearbeitet.

SQUAD_MAP_KEY = "topscorers_squad_map"
ALIASES_KEY = "topscorers_squad_aliases"  # haendisch, Admin -> Einstellungen -> APIs
_TSDB_URL = "https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?p={q}"
_SQUAD_LOOKUP_BUDGET = 6
_SQUAD_RENEW_DAYS = 7


def _surname_key(name):
    """Nachname als Schluessel: 'P. Schick'/'Patrik Schick (C)' -> 'schick'.

    Akzente werden zerlegt (Matanovic\' -> matanovic); deutsche Umlaute
    folgen der ae/oe/ue/ss-Norm (wie stadiums.py).
    """
    import re
    import unicodedata
    txt = unicodedata.normalize("NFKD", str(name or ""))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"\(.*?\)|[.,]", " ", txt)
    parts = [t for t in txt.split() if len(t) > 1]
    if not parts:
        return ""
    return parts[-1].lower().replace("ä", "ae").replace("ö", "oe") \
        .replace("ü", "ue").replace("ß", "ss")


def _initial_keys(name):
    """Firstnamen-Kuerzel ('P.' -> 'p', 'Patrik' -> 'patrik'), None wenn OLB
    nur den Nachnamen nennt - dann wird die Initial-Pruefung uebersprungen."""
    import re
    import unicodedata
    txt = unicodedata.normalize("NFKD", str(name or ""))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"\(.*?\)", " ", txt)
    parts = [t for t in txt.replace(".", " ").split() if t]
    if len(parts) < 2:
        return None
    first = parts[0].lower()
    last = parts[-1].lower()
    if first == last:
        return None
    return first


def _load_aliases():
    """'nachname = Vereinsname/Kuerzel' pro Zeile -> {schluessel: rohwert}."""
    import re
    raw = get_setting(ALIASES_KEY, "") or ""
    out = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s*(?:=|:|->|→)\s*", line, maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            continue
        out[_surname_key(parts[0]) or parts[0].strip().lower()] = parts[1].strip()
    return out


def _load_squad_map():
    raw = get_setting(SQUAD_MAP_KEY, "") or ""
    if not raw:
        return None
    import json
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("v") != 2:
        return None
    return data


def _league_teams():
    """(db_team, satz aus normalisierten Name-Tokens) je Verein der eigenen DB."""
    try:
        from models import Team
        from minute_boost import _name_tokens
        out = []
        for t in Team.query.all():
            out.append((t, set(_name_tokens(t.name or "")), str(t.short_name or "").lower()))
        return out
    except Exception:
        return []


def _tsdb_players(payload):
    players = (payload or {}).get("player") or []
    if isinstance(players, dict):
        players = [players]
    return [p for p in players if isinstance(p, dict)]


def _tsdb_lookup(surname_key, initial, teams, rejected=None, olb_name=""):
    """Ein Suchaufruf. Rueckgabe (treffer|None, netzwerk_ok).

    treffer dict = {short, name, logo}; None + netzwerk_ok = geprüfte Niete;
    None + nicht ok = Spaeter erneut versuchen (nicht als Niete merken).
    """
    import json
    from urllib.parse import quote
    try:
        r = requests.get(_TSDB_URL.format(q=quote(surname_key)), timeout=8)
    except Exception:
        return None, False
    if r.status_code != 200:
        return None, False
    try:
        payload = r.json()
    except Exception:
        return None, False
    for p in _tsdb_players(payload):
        pname = str(p.get("strPlayer") or "").strip()
        if _surname_key(pname) != surname_key:
            continue
        if initial:
            # Firstname-Pruefung: 'P. Schick' darf nicht auf 'Josef Schick' treffen
            pinit = _initial_keys(pname)
            if pinit and pinit != initial and not pinit.startswith(initial):
                continue
        dbt = _match_league_team(str(p.get("strTeam") or ""), teams)
        if dbt is not None:
            return {"short": dbt.short_name or dbt.name,
                    "name": dbt.name, "logo": dbt.logo or None}, True
        if rejected is not None:  # Grund merken - fuer die Alias-Uebersicht
            rejected[surname_key] = {
                "olb": olb_name,
                "why": "Fund '%s', aber Verein '%s' kein Liga-Team" % (
                    str(p.get("strPlayer") or "?").strip(),
                    str(p.get("strTeam") or "?").strip())}
        return None, True  # Spieler ok, aber Verein kein Liga-Team -> Niete
    if rejected is not None:
        rejected[surname_key] = {"olb": olb_name, "why": "kein Treffer in TheSportsDB"}
    return None, True


def _match_league_team(str_team, teams):
    """TheSportsDB-Vereinsstring einem DB-Team zuordnen - nur bei sicherem
    Token-Treffer (wie ueberall im Projekt): 'Freiburg' in 'SC Freiburg',
    'Bayer 04 Leverkusen' <-> 'Bayer Leverkusen'. Kein Match -> None."""
    from minute_boost import _name_tokens
    toks = set(_name_tokens(str_team or ""))
    if not toks:
        return None
    low = str_team.strip().lower()
    for dbt, dtoks, dshort in teams:
        if not dtoks:
            continue
        if dshort and low == dshort:
            return dbt
        if toks <= dtoks or dtoks <= toks:
            return dbt
    return None


def refresh_squad_map(now=None):
    """Abarbeitet die offenen Nachschlage der aktuellen Rangliste (best effort).

    Manuelle Aliasse werden VOR dem Cache-Kurzschluss angewandt - eine
    Handzuordnung wirkt damit sofort, auch wenn die Suche langweilig fertig
    ist (sonst bis zu 7 Tage Blockade durch done_at).
    """
    import json
    from datetime import datetime, timedelta, timezone as _tz
    now = now or datetime.now(_tz.utc)
    data = _load_squad_map() or {"v": 2, "names": {}, "tried": {}}
    names = dict(data.get("names") or {})
    tried = dict(data.get("tried") or {})
    rejected = dict(data.get("rejected") or {})
    aliases = _load_aliases()
    cached = load_cache() or {}
    entries = cached.get("entries") or []
    teams = _league_teams()

    def _store():
        pending_keys = [k for k in (_surname_key(e.get("name")) for e in entries)
                        if k and k not in names and k not in tried and k not in aliases]
        set_setting(SQUAD_MAP_KEY, json.dumps({
            "v": 2, "names": names, "tried": tried, "rejected": rejected,
            "done_at": (now.isoformat() if not pending_keys else None),
        }, ensure_ascii=False))

    def _apply_aliases():
        changed = False
        for e in entries:
            key = _surname_key(e.get("name"))
            if not key or key not in aliases:
                continue
            hit = _match_league_team(aliases[key], teams)
            if hit is not None:
                resolved = {"short": hit.short_name or hit.name,
                            "name": hit.name, "logo": hit.logo or None,
                            "alias": True}
                if names.get(key) != resolved:
                    names[key] = resolved
                    changed = True
                if rejected.pop(key, None) is not None:
                    changed = True
            elif not names.get(key):
                info = {"olb": e.get("name") or key,
                        "why": f"Alias '{aliases[key]}' - kein DB-Verein"}
                if rejected.get(key) != info:
                    rejected[key] = info
                    changed = True
        return changed

    if aliases and _apply_aliases():
        _store()

    if (data or {}).get("done_at"):
        try:
            renew = datetime.fromisoformat(str(data["done_at"]))
        except (TypeError, ValueError):
            renew = now
        if now < renew + timedelta(days=_SQUAD_RENEW_DAYS):
            return {"ok": True, "cached": True, "rejected": len(rejected)}
        data["tried"] = tried = {}  # woechentlich neu pruefen (Transfers!)

    looked = 0
    for e in entries:
        key = _surname_key(e.get("name"))
        if not key or key in names or key in tried or key in aliases:
            continue
        if looked >= _SQUAD_LOOKUP_BUDGET:
            break
        looked += 1
        hit, net_ok = _tsdb_lookup(key, _initial_keys(e.get("name")), teams,
                                   rejected, e.get("name") or key)
        if net_ok:
            tried[key] = now.isoformat()
            if hit:
                names[key] = hit
                rejected.pop(key, None)
    live_keys = {_surname_key(e.get("name")) for e in entries} - {""}
    rejected = {k: v for k, v in rejected.items()
                if k in live_keys and k not in names}
    _store()
    pending = [k for k in (_surname_key(e.get("name")) for e in entries)
               if k and k not in names and k not in tried and k not in aliases]
    return {"ok": True, "found": len(names), "lookups": looked,
            "pending": len(pending), "rejected": len(rejected)}


def set_manual_link(player_name, team_id):
    """Einzigem Schreibpfad fuer die Handzuordnung (Picker UND Textfeld).

    Speichert 'key = Vereinsname' als Alias; ohne team_id wird der Alias
    geloescht und die Zeile zurueckgesetzt (Suche darf dann wieder suchen,
    auch das tried-Merkblatt fuer diesen Schluessel faellt).
    Rueckgabe True bei Erfolg, False bei ungueltigem Spieler/Verein.
    """
    import json
    import re
    key = _surname_key(player_name)
    if not key:
        return False
    team = None
    if team_id not in (None, "", 0):
        try:
            from models import Team
            from extensions import db
            team = db.session.get(Team, int(team_id))
        except (TypeError, ValueError):
            return False
        if team is None:
            return False
    kept = []
    for line in (get_setting(ALIASES_KEY, "") or "").splitlines():
        st = line.strip()
        if not st or st.startswith("#"):
            if st:
                kept.append(st)
            continue
        parts = re.split(r"\s*(?:=|:|->|→)\s*", st, maxsplit=1)
        lk = _surname_key(parts[0]) or parts[0].strip().lower()
        if not (len(parts) == 2 and lk == key):
            kept.append(st)  # eigene Zeilen anderer Spieler bleiben unangetastet
    if team is not None:
        kept.append("%s = %s" % (key, team.name))
    set_setting(ALIASES_KEY, "\n".join(kept))
    data = _load_squad_map() or {"v": 2, "names": {}, "tried": {}}
    names = dict(data.get("names") or {})
    tried = dict(data.get("tried") or {})
    rejected = dict(data.get("rejected") or {})
    if team is not None:
        names[key] = {"short": team.short_name or team.name, "name": team.name,
                      "logo": team.logo or None, "alias": True}
        rejected.pop(key, None)
    else:
        names.pop(key, None)
        tried.pop(key, None)
    data["names"] = names
    data["tried"] = tried
    data["rejected"] = rejected
    data["done_at"] = None  # Notiz-Zaehler beim naechsten Lauf neu ausrechnen
    set_setting(SQUAD_MAP_KEY, json.dumps(data, ensure_ascii=False))
    return True


def squad_review():
    """[(Spielername, Grund)] fuer die Admin-Seite: was ordnet die Suche nicht
    zu? Alias-Schluessel wird mitgeliefert, damit die Zeile nur noch
    kopiert werden muss."""
    data = _load_squad_map() or {}
    rejected = data.get("rejected") or {}
    names = data.get("names") or {}
    cached = load_cache() or {}
    out = []
    for e in (cached.get("entries") or []):
        key = _surname_key(e.get("name"))
        if not key or key in names:
            continue
        info = rejected.get(key) or {}
        why = info.get("why") or "noch nicht nachgesehen"
        out.append({"name": e.get("name") or key, "why": why, "key": key})
    return out


def _annotate_teams(entries):
    """Haengt e['team']/'e['logo'] aus der TheSportsDB-Karte an (nur sichere
    Liga-Treffer; ohne Eintrag bleibt das Feld leer - kein Raten)."""
    data = _load_squad_map()
    names = (data or {}).get("names") or {}
    if not names:
        return entries
    for e in entries:
        hit = names.get(_surname_key(e.get("name")))
        if not hit:
            continue
        e["team"] = hit.get("short") or None
        e["team_name"] = hit.get("name") or None
        e["logo"] = hit.get("logo") or None
        e["team_src"] = "TheSportsDB"
    return entries


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
    sq = {}
    try:  # Mannschaftsabgleich dazubuchen (eigener Cache, nie fatal)
        sq = refresh_squad_map(now=now) or {}
    except Exception as e:
        current_app.logger.debug(f"top-scorers squad-map: {e}")
    # Zaehlt im Admin-Protokoll mit, ob/wie weit der Vereinsabgleich greift
    # (0 von n mit frischer Map = Nachname trifft keinen Kader; ohne fd-Token
    # steht das ausdruecklich da - alte Moduldatei auf dem Server faellt so auf).
    _annotate_teams(rows)
    mit = sum(1 for r in rows if r.get("team"))
    note = f"{len(rows)} Spieler · {mit}/{len(rows)} mit Verein"
    if sq.get("lookups"):
        note += f" (TheSportsDB: {sq['lookups']} nachgeschlagen"
        if sq.get("pending"):
            note += f", {sq['pending']} offen"
        note += ")"
    elif sq.get("pending"):
        note += f" (TheSportsDB-Panne, {sq['pending']} offen)"
    if sq.get("rejected"):
        note += f" · {sq['rejected']} abgelehnt (Aliasse moeglich)"
    note += f" · Modul {MODULE_VERSION}"
    _activity_record(True, note)
    return {"ok": True, "count": len(rows), "teams": mit}


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
    entries = _annotate_teams((data or {}).get("entries") or [])
    meta = {
        "fetched_at": (data or {}).get("fetched_at"),
        "season": (data or {}).get("season"),
        "empty": not entries,
        "source": "OpenLigaDB",
        "module_version": MODULE_VERSION,
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
