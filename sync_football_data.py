"""football-data.org-Client: _fd_request, Spielplan-Sync, Live-Standings, Live-Updates.

 Ausgelagert aus sync.py (Refactoring 31.08.2026); sync.py bleibt
Kernmodul und re-exportiert die Namen fuer bestehende Importeure.
"""

from datetime import datetime, timedelta, timezone

import requests
from flask import current_app

from extensions import db
from models import Match, Competition
from scoring import get_setting, set_setting
from match_results import apply_match_update

try:  # fester Heimstadium-Nachschlageweg (12.09.2026); fehlbares Modul = aus
    from stadiums import home_stadium_for  # (Deploy-Rest: Sync laeuft dann weiter)
except ImportError:
    home_stadium_for = None

from sync_shared import (
    current_sync_season_code, _resolve_or_create_team_from_fd, _ensure_competition_team,
    _find_existing_match, _purge_stale_matches_for_comp, purge_summary_suffix,
)

# (83) Sanity-Gate: 45 + 15 + 45 Minuten = physische Mindestdauer eines
# Spiels. Meldet die Quelle FINISHED frueher, ist das nachweislich falsch
# (Produktionsfall 20.09.2026: laufendes Spiel erschien als "ENDE 0:0").
FINISH_SANITY_MIN = 105


def _olb_finish_eintraege(cache):
    """OpenLigaDB-Saisonfeed (0 Euro, kein Key) einmal pro Sync-Lauf laden.

    Liefert Liste (heim_kuerzel, gast_kuerzel, kickoff_utc, ist_fertig) oder
    None, wenn OLB nicht erreichbar/lesbar ist (dann nie handeln)."""
    if "eintraege" in cache:
        return cache["eintraege"]
    cache["eintraege"] = None
    try:
        from sync_openligadb import _OLB_TEAM_MAP
        season = current_sync_season_code()
        r = requests.get(
            f"https://api.openligadb.de/getmatchdata/bl1/{season}", timeout=15)
        if r.status_code == 200:
            eintraege = []
            for md in r.json():
                t1 = _OLB_TEAM_MAP.get(md.get("team1", {}).get("teamName", ""))
                t2 = _OLB_TEAM_MAP.get(md.get("team2", {}).get("teamName", ""))
                ko = md.get("matchDateTimeUTC")
                if not t1 or not t2 or not ko:
                    continue
                try:
                    ko_dt = datetime.fromisoformat(str(ko).replace("Z", "+00:00"))
                except Exception:
                    continue
                eintraege.append((t1, t2, ko_dt,
                                  bool(md.get("matchIsFinished"))))
            cache["eintraege"] = eintraege
    except Exception:
        pass
    return cache["eintraege"]


def _olb_sicher_nicht_fertig(cache, home_short, away_short, kickoff):
    """True = OLB belegt zweifelsfrei, dass das Spiel LAEUFT (nicht fertig).

    False = unklar (OLB nicht erreichbar oder Paarung nicht gefunden) -
    in dem Fall wird niemals gegen den eigenen Status gehandelt."""
    eintraege = _olb_finish_eintraege(cache)
    if eintraege is None:
        return False
    for t1, t2, ko, fertig in eintraege:
        if t1 == home_short and t2 == away_short                 and abs((ko - kickoff).total_seconds()) <= 900:
            return not fertig
    return False

# ============================================================ football-data.org -
def _fd_request(path, ttl_seconds=30):
    """Wrapper für football-data.org-Requests mit Token + Caching."""
    token = get_setting("football_data_token", current_app.config["FOOTBALL_DATA_TOKEN"])
    if not token:
        return None, "Kein football-data.org-Token gesetzt (Admin → Einstellungen)."

    cache_key = f"fd_cache:{path}"
    cached = get_setting(cache_key)
    now_ts = datetime.now(timezone.utc).timestamp()
    if cached and isinstance(cached, dict):
        ts = cached.get("ts", 0)
        if now_ts - ts < ttl_seconds:
            return cached.get("data"), None

    def _stale_cache_data():
        """Liefert gecachte Daten bei API-Fehlern - aber nur, wenn der Cache
        max. 10 Minuten alt ist. Aeltere Daten duerfen nicht mehr geschrieben
        werden, sonst koennen veraltete Stati frischere Zustaende ueberschreiben."""
        if isinstance(cached, dict) and (now_ts - cached.get("ts", 0)) <= 600:
            return cached.get("data")
        return None

    url = f"{current_app.config['FOOTBALL_DATA_BASE']}{path}"
    headers = {"X-Auth-Token": token}
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        stale = _stale_cache_data()
        if stale is not None:
            return stale, None
        return None, f"Netzwerkfehler: {e}"

    if r.status_code == 429:
        stale = _stale_cache_data()
        if stale is not None:
            return stale, None
        return None, "API-Rate-Limit erreicht (10 Calls/Min)."

    if r.status_code != 200:
        stale = _stale_cache_data()
        if stale is not None:
            return stale, None
        return None, f"API-Fehler {r.status_code} (Token/Quota prüfen)"

    try:
        data = r.json()
    except ValueError:
        return None, "API lieferte ungültiges JSON"

    set_setting(cache_key, {"ts": now_ts, "data": data})
    return data, None


def sync_with_football_data():
    """Hauptsync gegen football-data.org (Spielplan + Ergebnisse).

    Primäre Datenquelle – liefert Live-Spielstände, exakte Kickoff-Zeiten
    und Status (IN_PLAY, PAUSED, FINISHED). Benötigt einen kostenlosen
    Token von https://www.football-data.org/client/register
    (10 Calls/min im Free Tier).
    """
    season = current_sync_season_code()
    comp = current_app.config["COMPETITION"]

    comp_obj = Competition.query.filter_by(code=comp, is_active=True).first()
    comp_id = comp_obj.id if comp_obj else 1

    data, err = _fd_request(f"/competitions/{comp}/matches?season={season}", ttl_seconds=60)
    if err:
        return {"ok": False, "source": "football-data.org", "msg": err}

    result = _process_football_data(data, comp_id, source="football-data.org")
    result["source"] = "football-data.org"
    return result


def _process_football_data(data, comp_id, source="football-data.org"):
    """Verarbeitet die Match-Daten und speichert sie in der DB."""
    from scoring import recalculate_all_points, recalculate_matches_points
    from badges import check_and_award_badges
    from models import User

    matches_data = data.get("matches", [])
    updated = 0
    created = 0
    live_count = 0
    venue_feed_count = 0  # Feed-Lieferung (football-data)
    venue_map_count = 0   # gefuellte Luecken aus der festen Heimstadium-Karte
    venue_gap_names = []  # Heimteams ohne Feed-venue UND ohne Karten-Treffer
    new_teams = 0
    current_ext_ids = set()
    affected_match_ids = set()
    vorzeitig = 0        # (83) FINISHED unterhalb der Mindestdauer
    zurueckgenommen = 0  # (83) davon falsch-fertig -> wieder live
    olb_cache = {}

    for md in matches_data:
        ext_id = f"fd:{md['id']}"
        current_ext_ids.add(ext_id)

        home_team_data = md.get("homeTeam", {})
        away_team_data = md.get("awayTeam", {})
        home_team_name = home_team_data.get("name", "")
        away_team_name = away_team_data.get("name", "")
        home_team, home_created = _resolve_or_create_team_from_fd(home_team_data)
        away_team, away_created = _resolve_or_create_team_from_fd(away_team_data)
        if home_created or away_created:
            new_teams += int(bool(home_created)) + int(bool(away_created))
            current_app.logger.info(
                f"Neue Teams aus football-data.org angelegt: "
                f"{home_team.name if home_created else ''} {away_team.name if away_created else ''}".strip()
            )
        if not home_team or not away_team:
            current_app.logger.warning(f"Sync: Team nicht erkannt: {home_team_name} / {away_team_name}")
            continue
        _ensure_competition_team(comp_id, home_team)
        _ensure_competition_team(comp_id, away_team)

        kickoff_str = md["utcDate"]
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except Exception:
            continue

        matchday_num = md.get("matchday") or 1
        existing = _find_existing_match(comp_id, ext_id, matchday_num, home_team, away_team, source_prefix="fd")
        status = md.get("status", "SCHEDULED")
        status_map = {
            "SCHEDULED": "scheduled", "TIMED": "scheduled",
            "IN_PLAY": "live", "PAUSED": "live",
            "EXTRA_TIME": "live", "PENALTY_SHOOTOUT": "live",
            "FINISHED": "finished", "POSTPONED": "scheduled",
            "SUSPENDED": "scheduled", "CANCELLED": "scheduled",
        }
        our_status = status_map.get(status, "scheduled")

        # (83) Sanity-Gate: FINISHED ist unmoeglich, solange die Mindestdauer
        # nicht um ist. Stattdessen gilt der harte Fakt "Anstoss vorbei" =
        # live. Nie wird ein Score/Minute erfunden - nur der unplausible
        # Status abgelehnt. Ein bereits faelschlich fertig geglaubtes 0:0
        # wird mit OLB-Gegenprobe (OLB laeuft noch) per allow_status_reset
        # zurueckgenommen (Monotonie macht falsches "finished" sonst unheilbar).
        notfall_reset = False
        if kickoff is not None:
            jetzt = datetime.now(timezone.utc)
            minuten_seit_anstoss = (jetzt - kickoff).total_seconds() / 60.0
            if minuten_seit_anstoss < FINISH_SANITY_MIN:
                if our_status == "finished":
                    vorzeitig += 1
                    our_status = "live" if kickoff <= jetzt else "scheduled"
                # Bereits haengendes "finished" heilt die OLB-Gegenprobe
                # unabhaengig vom Score (Produktionsfall 20.09.: der Boost
                # hatte das falsche 0:0 schon auf 2:0 geheilt, nur der
                # Status hing noch auf finished). OLB unklar -> nie handeln.
                if (existing is not None and existing.status == "finished"
                        and kickoff <= jetzt
                        and home_team.short_name and away_team.short_name
                        and _olb_sicher_nicht_fertig(
                            olb_cache, home_team.short_name,
                            away_team.short_name, kickoff)):
                    notfall_reset = True
                    zurueckgenommen += 1

        # Echte Spielminute aus dem Feed (KEINE Schaetzung ab Anstosszeit!).
        # football-data.org liefert bei Live-Spielen `minute`; fehlt sie oder
        # ist sie unsinnig, bleibt minute leer und die UI zeigt nur "LIVE".
        raw_minute = md.get("minute")
        try:
            real_minute = int(raw_minute) if raw_minute is not None else None
        except (TypeError, ValueError):
            real_minute = None
        if real_minute is not None and real_minute < 1:
            real_minute = None

        # Stadion: Feed-Wert hat immer Vorrang; nur fuer echte Luecken greift
        # die feste Heimstadium-Karte (Free-Plan von football-data liefert
        # venue laut Diagnose 12.09. nicht, OLB ebenso wenig).
        venue_feed = (md.get("venue") or "").strip()[:80] or None
        if venue_feed:
            venue_feed_count += 1
        mapped_venue = None
        if not venue_feed and home_stadium_for:
            mapped_venue = home_stadium_for(home_team.name)
        # Fruehwarnung fuer die statischen Karten (Aufsteiger koennen dort
        # fehlen, ohne dass es jemand merkt): Heimteam ohne jede Quelle.
        if (home_team is not None and not venue_feed and not mapped_venue
                and home_team.name not in venue_gap_names
                and len(venue_gap_names) < 12):
            venue_gap_names.append(home_team.name)

        score = md.get("score", {})
        full_time = score.get("fullTime", {})
        home_score = full_time.get("home")
        away_score = full_time.get("away")
        half_time = score.get("halfTime", {})
        ht_home = half_time.get("home")
        ht_away = half_time.get("away")

        if existing:
            old_status, old_h, old_a = existing.status, existing.home_score, existing.away_score
            existing.external_id = ext_id
            existing.matchday = matchday_num
            existing.home_team_id = home_team.id
            existing.away_team_id = away_team.id
            apply_match_update(
                existing,
                home_score=home_score if home_score is not None else None,
                away_score=away_score if home_score is not None else None,
                status=our_status,
                kickoff=kickoff,
                is_live=(our_status == "live"),
                allow_status_reset=notfall_reset,
            )
            if venue_feed and existing.venue != venue_feed:
                existing.venue = venue_feed  # nie mit None loeschen (API-liefert nicht immer)
            elif not venue_feed and mapped_venue and not existing.venue:
                existing.venue = mapped_venue
                venue_map_count += 1
            if old_status != our_status or old_h != existing.home_score or old_a != existing.away_score:
                affected_match_ids.add(existing.id)
            updated += 1
        else:
            existing = Match(
                competition_id=comp_id,
                matchday=matchday_num,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                kickoff=kickoff,
                home_score=home_score,
                away_score=away_score,
                status=our_status,
                external_id=ext_id,
                is_live=(our_status == "live"),
                venue=venue_feed or mapped_venue,
            )
            if mapped_venue and not venue_feed:
                venue_map_count += 1
            db.session.add(existing)
            db.session.flush()
            if our_status == "finished":
                affected_match_ids.add(existing.id)
            created += 1

        # Live-Metadaten: Phase (PAUSED = Halbzeit) + echte Minute. Die UI
        # zeigt nur an, was der Feed wirklich liefert - keine Stoppuhr ab Anpfiff.
        if our_status == "live" and existing is not None:
            live_count += 1
            # (83) Phase-Feld nur mit echten Live-Statuswerten fuellen;
            # ein abgewiesenes "FINISHED" darf nicht als Phase landen.
            existing.live_phase = status if status in (
                "IN_PLAY", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT") else None
            if real_minute is not None:
                existing.minute = real_minute
        elif existing is not None and (existing.live_phase is not None or existing.minute is not None):
            existing.live_phase = None

    purged_stale = 0
    if source == "football-data.org" and current_ext_ids:
        purged_stale = _purge_stale_matches_for_comp(comp_id, current_ext_ids)

    db.session.commit()

    if purged_stale > 0:
        recalculate_all_points()
        check_and_award_badges()
    elif affected_match_ids:
        affected_users = recalculate_matches_points(affected_match_ids, commit=True)
        if affected_users:
            users = User.query.filter(User.id.in_(affected_users)).all()
            check_and_award_badges(users=users)

    # Persistenz fuer die kleine Admin-Zeile (sync.html): der JEWEILIGE letzte
    # Lauf schreibt, also heilt die Zeile nach Karten-Pflege von selbst weg.
    import json as _json
    try:
        set_setting("stadium_gap_teams", _json.dumps(venue_gap_names, ensure_ascii=False))
    except Exception:
        pass
    finish_suffix = ""
    if vorzeitig:
        finish_suffix = f" · 🛡️ {vorzeitig} vorzeitige FINISHED abgewiesen"
        if zurueckgenommen:
            finish_suffix += f", {zurueckgenommen} zurückgenommen (live)"

    gap_suffix = ""
    if venue_gap_names:
        shown = ", ".join(venue_gap_names[:3]) + (" …" if len(venue_gap_names) > 3 else "")
        gap_suffix = f" \u00b7 \U0001f6c8 ohne Stadion-Karte: {shown}"

    return {
        "ok": True,
        "msg": f"✅ {source}: {created} neu, {updated} aktualisiert, {live_count} live \u00b7 \U0001f4cd Stadion: {venue_feed_count} aus Feed, {venue_map_count} aus Festdaten{finish_suffix}{gap_suffix}{purge_summary_suffix()}",
        "created": created,
        "updated": updated,
        "live": live_count,
        "finish_vorzeitig": vorzeitig,
        "finish_zurueckgenommen": zurueckgenommen,
        "venues": venue_feed_count,
        "venues_map": venue_map_count,
        "venues_missing": venue_gap_names,
        "new_teams": new_teams,
        "purged_stale": purged_stale,
    }


def fetch_live_standings():
    """Holt die Live-Tabelle von football-data.org."""
    season = current_sync_season_code()
    comp = current_app.config["COMPETITION"]

    data, err = _fd_request(f"/competitions/{comp}/standings?season={season}", ttl_seconds=60)
    if err or not data:
        return None, err or "Keine Daten"

    standings = data.get("standings", [])
    if not standings:
        return None, "Keine Tabellendaten"

    table_data = standings[0].get("table", [])
    rows = []
    for entry in table_data:
        team_data = entry.get("team", {})
        team_name = team_data.get("name", "")
        team_obj, created_team = _resolve_or_create_team_from_fd(team_data)
        if created_team:
            db.session.commit()
        if not team_obj:
            current_app.logger.warning(f"Tabelle: Team nicht erkannt: {team_name}")
            continue
        rows.append({
            "rank": entry.get("position", 0),
            "team": team_obj,
            "played": entry.get("playedGames", 0),
            "won": entry.get("won", 0),
            "drawn": entry.get("draw", 0),
            "lost": entry.get("lost", 0),
            "goals_for": entry.get("goalsFor", 0),
            "goals_against": entry.get("goalsAgainst", 0),
            "goal_diff": entry.get("goalDifference", 0),
            "points": entry.get("points", 0),
            "form": entry.get("form", ""),
        })
    return rows, None


def fetch_live_match_updates(matchday=None):
    """Holt aktuelle Spielstände von football-data.org für heute."""
    season = current_sync_season_code()
    comp = current_app.config["COMPETITION"]

    if matchday:
        data, err = _fd_request(f"/competitions/{comp}/matches?season={season}&matchday={matchday}", ttl_seconds=30)
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        next_week = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
        data, err = _fd_request(
            f"/competitions/{comp}/matches?season={season}&dateFrom={today}&dateTo={next_week}",
            ttl_seconds=30
        )

    # OLB-Live-Boost: football-data.org delayt Scores im Free-Tier Minuten;
    # OpenLigaDB meldet Bundesliga-Tore quasi sofort. Laeuft zusaetzlich (und
    # auch, wenn fd ausfaellt) - processweit auf 1 Request/20s gedrosselt.
    boost = {}
    try:
        from sync_openligadb import boost_live_from_openligadb
        boost = boost_live_from_openligadb(matchday=matchday) or {}
    except Exception as e:
        current_app.logger.debug(f"OLB-Live-Boost uebersprungen: {e}")
    boost_updates = int(boost.get("updated") or 0)

    # Optionaler Minute-Booster (API-Football, Free-Plan mit Budgetwaechter):
    # echte Schiedsrichterminute, sobald im Admin ein optionaler Token steht.
    minute_updates = 0
    try:
        from minute_boost import boost_minutes_from_apifootball
        mb = boost_minutes_from_apifootball() or {}
        minute_updates = int(mb.get("updated") or 0)
    except Exception as e:
        current_app.logger.debug(f"Minute-Boost uebersprungen: {e}")

    # Goal-Boost: Torschuetzen-Listen fuer frisch beendete Spiele (nutzt den
    # optionalen API-Football-Key, eigener Mini-Budgetwaechter).
    goal_updates = 0
    try:
        from minute_boost import boost_goal_scorers_from_apifootball
        gb = boost_goal_scorers_from_apifootball() or {}
        goal_updates = int(gb.get("updated") or 0)
    except Exception as e:
        current_app.logger.debug(f"Goal-Boost uebersprungen: {e}")

    if err or not data:
        return {"ok": bool(boost_updates or minute_updates or goal_updates),
                "msg": (err or ""), "updated": boost_updates, "live": 0,
                "olb_boost": boost_updates, "minute_boost": minute_updates,
                "goals": goal_updates}

    comp_obj = Competition.query.filter_by(code=comp, is_active=True).first()
    comp_id = comp_obj.id if comp_obj else 1

    result = _process_football_data(data, comp_id, source="live-sync")
    if boost_updates:
        result["updated"] = result.get("updated", 0) + boost_updates
        result["olb_boost"] = boost_updates
    if minute_updates:
        result["minute_boost"] = minute_updates
    if goal_updates:
        result["goals"] = goal_updates
    return result


