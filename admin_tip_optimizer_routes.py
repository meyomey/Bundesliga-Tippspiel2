"""Admin-Tipp-Optimizer: Dixon-Coles-EP-Optimierung je Spieltag (nur Admin).

Seite /admin/tip-optimizer zeigt die Ansetzungen des gewählten Spieltags aus
der App-Datenbank; die Berechnung (Dixon-Coles-Poisson, Power-Margenbereini-
gung, Expected-Points-Optimum unter der 4/3/2-Regel) läuft komplett client-
seitig in static/js/tip_optimizer.js. Der einzige Server-Teilservice ist der
optional abrufbare Quoten-Laden-Endpoint (The-Odds-API, Free-Plan 500 Credits/
Monat, 2 Credits pro Abruf) mit Budgetwächter + Versuchs-Log in
datasource_activity – ohne hinterlegten Key bleibt der Endpunkt stumm
(ℹ️ statt ⚠️, nie ein HTTP-Versuch).
"""
import json
from datetime import datetime, timezone

import requests
from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from routes_admin import admin_bp, admin_required
from extensions import csrf
from models import Match, OddsSnapshot, OptimizerRun, OptimizerRunTip, db
from scoring import get_setting, set_setting
from stats import get_current_matchday
from competition_helpers import active_match_query, get_active_competition
from datasource_activity import record as dsrc_record
from tip_optimizer_model import (backtest, evaluate_run_tips,
                                 fit_season_model, prior_lambdas)

SETTINGS_KEY = "the_odds_api_key"
BUDGET_KEY = "the_…budget"
MONTHLY_CALL_CAP = 60  # Free-Plan: 500 Credits/Monat; 1 Abruf = 2 Credits -> 60 = 120 Credits
REMAINING_FLOOR = 20   # bei weniger verbleibenden Credits ruht der Abruf bis nächsten Monat
SPORT_KEY = "soccer_germany_bundesliga"
REGIONS = "eu"
API_URL = "https://api.the-odds-api.com/v4/sports/" + SPORT_KEY + "/odds"

# Offizielle API-Namen -> Bezeichnungen der App-DB (für die Zuzuordnung der
# Quoten zu den Spielkarten).
DE_NAMES = {
    "bayern munich": "FC Bayern München", "fc bayern munich": "FC Bayern München",
    "borussia dortmund": "Borussia Dortmund", "rb leipzig": "RB Leipzig",
    "bayer leverkusen": "Bayer 04 Leverkusen", "eintracht frankfurt": "Eintracht Frankfurt",
    "vfb stuttgart": "VfB Stuttgart", "sc freiburg": "SC Freiburg",
    "borussia monchengladbach": "Bor. Mönchengladbach", "borussia mönchengladbach": "Bor. Mönchengladbach",
    "fc augsburg": "FC Augsburg", "werder bremen": "SV Werder Bremen", "sv werder bremen": "SV Werder Bremen",
    "mainz 05": "1. FSV Mainz 05", "fsv mainz 05": "1. FSV Mainz 05", "1. fsv mainz 05": "1. FSV Mainz 05",
    "fc cologne": "1. FC Köln", "1. fc cologne": "1. FC Köln", "fc koln": "1. FC Köln", "1. fc koln": "1. FC Köln",
    "1. fc köln": "1. FC Köln",
    "hamburger sv": "Hamburger SV", "union berlin": "1. FC Union Berlin", "1. fc union berlin": "1. FC Union Berlin",
    "tsg hoffenheim": "TSG Hoffenheim", "sc paderborn 07": "SC Paderborn 07", "paderborn": "SC Paderborn 07",
    "sv elversberg": "SV 07 Elversberg", "elversberg": "SV 07 Elversberg", "sv 07 elversberg": "SV 07 Elversberg",
    "fc st. pauli": "FC St. Pauli", "st. pauli": "FC St. Pauli",
    "fc heidenheim": "1. FC Heidenheim", "heidenheim": "1. FC Heidenheim", "1. fc heidenheim": "1. FC Heidenheim",
}


def _de_name(name):
    k = str(name or "").lower().strip()
    return DE_NAMES.get(k, name)


def _fmt_kick(iso):
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
        return dt.strftime("%a, %d.%m. %H:%M")
    except (ValueError, TypeError):
        return ""


def _budget_state():
    """Monatlicher Abruf-Zähler (Setting-JSON). Neuer Monat = frischer Stand."""
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    raw = get_setting(BUDGET_KEY, "") or ""
    try:
        data = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict) or data.get("month") != month:
        data = {"month": month, "used": 0, "remaining": None}
        set_setting(BUDGET_KEY, json.dumps(data))
    return data


def _parse_odds_events(events):
    """The-Odds-API-Antwort -> eine Zeile je Spiel mit Konsens-Quoten.

    Konsens = Median über alle Buchmacher (robust gegen Ausreißer wie
    Sonderquoten kleiner Bookies; gerader Fall = Mittelwert der beiden
    mittleren Werte).
    """
    out = []
    for ev in events or []:
        agg = {"o1": [], "ox": [], "o2": [], "ou25": [], "ou35": [], "btts": []}
        books = 0
        for bk in ev.get("bookmakers") or []:
            books += 1
            for mk in bk.get("markets") or []:
                key = mk.get("key")
                if key == "h2h":
                    for o in mk.get("outcomes") or []:
                        if o.get("name") == ev.get("home_team"):
                            agg["o1"].append(o.get("price"))
                        elif o.get("name") == "Draw":
                            agg["ox"].append(o.get("price"))
                        elif o.get("name") == ev.get("away_team"):
                            agg["o2"].append(o.get("price"))
                elif key == "totals":
                    for o in mk.get("outcomes") or []:
                        if o.get("name") == "Over" and o.get("point") == 2.5:
                            agg["ou25"].append(o.get("price"))
                        elif o.get("name") == "Over" and o.get("point") == 3.5:
                            agg["ou35"].append(o.get("price"))
                elif key == "btts":
                    for o in mk.get("outcomes") or []:
                        if o.get("name") == "Yes":
                            agg["btts"].append(o.get("price"))

        def median(vals):
            clean = sorted(v for v in vals if isinstance(v, (int, float)))
            if not clean:
                return None
            n = len(clean)
            mid = n // 2
            return round(clean[mid] if n % 2 else (clean[mid - 1] + clean[mid]) / 2.0, 3)

        ts = ev.get("commence_time") or ""
        out.append({
            "h": _de_name(ev.get("home_team")), "a": _de_name(ev.get("away_team")),
            "books": books, "ts": ts, "kick": _fmt_kick(ts),
            "o1": median(agg["o1"]), "ox": median(agg["ox"]), "o2": median(agg["o2"]),
            "ou25": median(agg["ou25"]), "ou35": median(agg["ou35"]), "btts": median(agg["btts"]),
        })
    out.sort(key=lambda x: x["ts"] or "")
    return out


def _tracking_stats():
    """Prospektive Modellgüte: gespeicherte Vorhersagen abgelaufener
    Spieltage (matchday < aktuell) gegen die Endstände abgerechnet.
    Returns None, wenn noch nichts bewertbar ist."""
    comp = get_active_competition()
    if not comp:
        return None
    current_md = get_current_matchday()
    runs = (OptimizerRun.query.filter_by(competition_id=comp.id)
            .filter(OptimizerRun.matchday < current_md)
            .order_by(OptimizerRun.matchday.desc(), OptimizerRun.id.desc())
            .all())
    rows = []
    for run in runs:
        res = evaluate_run_tips(run.tips.all())
        if res is None:
            continue
        rows.append({
            "md": run.matchday,
            "when": run.created_at.strftime("%d.%m. %H:%M") if run.created_at else "",
            "when_iso": _iso_z(run.created_at),
            "n": res["n"], "ep_exp": res["ep_exp"], "ep_real": res["ep_real"],
            "pge2_exp": res["pge2_exp"], "pge2_rate": res["pge2_rate"],
            "brier": res["brier"],
        })
    if not rows:
        return None
    n = sum(r["n"] for r in rows)

    def mean(key):
        return round(sum(r[key] * r["n"] for r in rows) / n, 3)

    return {
        "since": rows[-1]["when"],
        "runs": len(rows),
        "n": n,
        "ep_exp": mean("ep_exp"),
        "ep_real": mean("ep_real"),
        "pge2_exp": mean("pge2_exp"),
        "pge2_rate": mean("pge2_rate"),
        "brier": mean("brier"),
        "brier_zufall": round(2.0 / 3.0, 4),
        "rows": rows,
    }


def _iso_z(dt):
    """UTC-Datetime als ISO-8601 mit Z-Suffix (naive UTC). Fuer die
    Client-Umwandlung in lokale Zeit — ohne Z würde JS die Zeit als lokale
    Zeit parsen (Runden-Drift, s. (72))."""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


def _odds_movement(md, matches):
    """Quoten-Bewegung je Spiel des angezeigten Spieltags: erster vs. letzter
    gespeicherter Stand (jeder Online-Abruf legt einen Zeitstempel-Stand an,
    0 € — eigene abgerufene Werte). Returns None, wenn noch nichts da ist."""
    comp = get_active_competition()
    if not comp:
        return None
    snaps = (OddsSnapshot.query
             .filter_by(competition_id=comp.id, matchday=md)
             .order_by(OddsSnapshot.created_at.asc(), OddsSnapshot.id.asc())
             .all())
    if not snaps:
        return None
    by_match = {}
    for s in snaps:
        by_match.setdefault(s.match_id, []).append(s)

    def de2(v):
        return ("%.2f" % v).replace(".", ",")

    def cell(first, last, n):
        if n == 1:
            return (de2(first) if first is not None else "–"), "·"
        if first is None or last is None:
            shown = de2(first if last is None else last)
            return (shown + (" → –" if last is None else " ← –")), "·"
        d = last - first
        arrow = "↓" if d < -0.005 else ("↑" if d > 0.005 else "·")
        return "%s → %s" % (de2(first), de2(last)), arrow

    rows = []
    for m in matches:
        ss = by_match.get(m.id)
        if not ss:
            continue
        first, last = ss[0], ss[-1]
        rows.append({
            "h": m.home_team.name, "a": m.away_team.name, "n": len(ss),
            "first_ts": first.created_at.strftime("%d.%m. %H:%M"),
            "first_ts_iso": _iso_z(first.created_at),
            "c1": cell(first.o1, last.o1, len(ss)),
            "cx": cell(first.ox, last.ox, len(ss)),
            "c2": cell(first.o2, last.o2, len(ss)),
        })
    if not rows:
        return None
    until = max(snap.created_at for snap in snaps)
    return {
        "md": md,
        "total": len(snaps),
        "since": min(snap.created_at for snap in snaps).strftime("%d.%m."),
        "until": until.strftime("%d.%m. %H:%M"),
        "until_iso": _iso_z(until),
        "rows": rows,
    }


def fetch_odds_online():
    """Ein echter The-Odds-API-Abruf (nur wenn Key + Budget es erlauben).

    Returns (dict ok=True + matches/credits) oder (dict ok=False + stage/msg).
    Schreibt immer einen Eintrag ins datasource-Protokoll – aber erst NACH
    echtem HTTP-Kontakt; Key-/Budget-Skips werden bewusst nicht protokolliert.
    """
    key = (get_setting(SETTINGS_KEY, "") or "").strip()
    if not key:
        return {"ok": False, "stage": "no-key",
                "msg": "ℹ️ Kein The-Odds-API-Key hinterlegt – Quotenladen bleibt inaktiv. "
                       "Free-Key: the-odds-api.com registrieren (500 Credits/Monat) → "
                       "Einstellungen → APIs → Key einfügen."}

    budget = _budget_state()
    remaining = budget.get("remaining")
    if int(budget.get("used", 0)) >= MONTHLY_CALL_CAP or (
            isinstance(remaining, (int, float)) and remaining < REMAINING_FLOOR):
        return {"ok": False, "stage": "budget",
                "msg": f"ℹ️ Monatsbudget für Quotenabrufe ruht "
                       f"({budget.get('used', 0)}/{MONTHLY_CALL_CAP} Abrufe"
                       + (f", Credits übrig: {remaining}" if remaining is not None else "")
                       + ") – läuft zum nächsten Monat automatisch weiter."}

    try:
        r = requests.get(API_URL, params={
            "apiKey": key, "regions": REGIONS, "markets": "h2h,totals",
            "oddsFormat": "decimal",
        }, timeout=20)
    except requests.RequestException as e:
        dsrc_record("the_odds_api", False, f"Netzwerk: {type(e).__name__}: {str(e)[:80]}")
        return {"ok": False, "stage": "http",
                "msg": f"Netzwerkfehler beim Quotenabruf: {type(e).__name__}"}

    budget["used"] = int(budget.get("used", 0)) + 1
    rem_header = r.headers.get("x-requests-remaining")
    try:
        budget["remaining"] = int(rem_header) if rem_header is not None else None
    except ValueError:
        budget["remaining"] = None
    set_setting(BUDGET_KEY, json.dumps(budget))

    credits = budget.get("remaining")
    if not r.ok:
        msg = f"HTTP {r.status_code}"
        try:
            j = r.json()
            if isinstance(j, dict) and j.get("message"):
                msg = str(j["message"])[:160]
        except ValueError:
            pass
        if r.status_code == 401:
            msg = "API-Key ungültig (401)."
        elif r.status_code == 429:
            msg = "Rate-Limit / Credits aufgebraucht (429)."
        elif r.status_code == 404:
            msg = "Liga-Key nicht gefunden (404)."
        dsrc_record("the_odds_api", False, f"{r.status_code}: {msg[:100]}")
        return {"ok": False, "stage": "http", "msg": f"⚠️ The-Odds-API: {msg}"
                + (f" · Credits übrig: {credits}" if credits is not None else "")}

    try:
        events = r.json()
    except ValueError:
        dsrc_record("the_odds_api", False, "Antwort ohne JSON.")
        return {"ok": False, "stage": "http", "msg": "⚠️ The-Odds-API: Antwort ohne JSON."}

    matches = _parse_odds_events(events)
    dsrc_record("the_odds_api", True,
                f"{len(matches)} anstehende Spiele · Credits übrig: "
                + (str(credits) if credits is not None else "?"))
    return {"ok": True, "matches": matches, "credits_remaining": credits,
            "budget": int(budget.get("used", 0)),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


@admin_bp.route("/tip-optimizer")
@login_required
@admin_required
def tip_optimizer():
    """Optimizer-Seite: Ansetzungen des gewählten Spieltags + client-seitige EP-Berechnung."""
    md = request.args.get("md", type=int)
    current_md = get_current_matchday()
    if md is None or md < 1:
        md = current_md
    try:
        all_matches = active_match_query().all()
        matchdays = sorted({m.matchday for m in all_matches if m.matchday} | {md})
        matches = [m for m in all_matches if m.matchday == md]
        matches.sort(key=lambda m: m.kickoff or datetime.max)
    except Exception:
        matchdays, matches = [md], []
    budget = _budget_state()
    comp = get_active_competition()
    season = getattr(comp, "season", "") or "" if comp else ""
    # Saisondaten-Anker: Teamstärken-λ, Dixon-Coles-Faktoren und Torsumme
    # werden aus den fertigen Spielen der aktiven Liga gefittet; bei zu
    # wenig Daten greifen die Standalone-Defaults (fitted=False).
    try:
        model = fit_season_model(all_matches)
        priors = {}
        for m in matches:
            pl = prior_lambdas(model, m.home_team.name, m.away_team.name)
            if pl:
                priors["%s|%s" % (m.home_team.name, m.away_team.name)] = pl
    except Exception:
        model = {"rho": [1.00, 1.09, 0.97], "goal_prior": 3.20,
                 "fitted": False, "n": 0, "strengths": {}}
        priors = {}
    return render_template(
        "admin/tip_optimizer.html",
        md=md, current_md=current_md, matchdays=matchdays, matches=matches,
        season=season,
        rho=model["rho"], goal_prior=model["goal_prior"], priors=priors,
        model_fitted=model.get("fitted", False), model_n=model.get("n", 0),
        model_stats=_tracking_stats(),
        odds_move=_odds_movement(md, matches),
        has_key=bool((get_setting(SETTINGS_KEY, "") or "").strip()),
        budget_used=int(budget.get("used", 0)), budget_cap=MONTHLY_CALL_CAP,
        credits_remaining=budget.get("remaining"),
    )


@admin_bp.route("/tip-optimizer/odds")
@login_required
@admin_required
def tip_optimizer_odds():
    """Optionaler Quotenabruf (The-Odds-API) – siehe fetch_odds_online()."""
    return jsonify(fetch_odds_online())


@admin_bp.route("/tip-optimizer/backtest")
@login_required
@admin_required
def tip_optimizer_backtest():
    """Walk-Forward-Backtest der Modell-Grundlage (nur fertige Spiele der
    App-DB; historische Quoten sind nicht verfügbar – s. tip_optimizer_model)."""
    try:
        matches = active_match_query().all()
    except Exception:
        matches = []
    return jsonify(backtest(matches))


# CSRF: Die beiden fetch()-Endpunkte senden kein Form-Token (die Tests laufen
# mit WTF_CSRF_ENABLED=False, in Produktion ist es AN — das war der Bug, der
# „Speichern nicht möglich (HTTP 400)“ / „The CSRF token is missing“ produzierte).
# Exemption ist hier sicher: (1) nur Admin-Session (login_required + admin_required),
# (2) Content-Type: application/json erzwingt bei cross-site-Angriffen ein CORS-
# Preflight, das ohne CORS-Header abgelehnt wird (klassische Simple-Request-
# CSRFs treffen diese Endpunkte nicht), (3) die Antwort enthält keine Sensiblen
# Daten.


@admin_bp.route("/tip-optimizer/odds-log", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def tip_optimizer_odds_log():
    """Legt den gerade befüllten Quoten-Stand (nach „Quoten online laden“)
    je Spiel als Zeitstempel-Stand an – Basis der Quoten-Bewegungs-Karte.
    0 €: es werden nur die bereits abgerufenen Werte gemerkt."""
    data = request.get_json(silent=True) or {}
    comp = get_active_competition()
    if not comp:
        return jsonify({"ok": False, "msg": "Kein aktiver Wettbewerb."}), 400
    md = data.get("matchday")
    items = data.get("items") or []
    if (not isinstance(md, int) or not (1 <= md <= 40)
            or not isinstance(items, list) or not items):
        return jsonify({"ok": False, "msg": "Ungültige Nutzlast."}), 400

    def fnum(it, key):
        try:
            v = float(it.get(key))
            return v if v > 1 else None
        except (TypeError, ValueError):
            return None

    try:
        saved = 0
        now = datetime.now(timezone.utc)
        for it in items[:20]:
            if not isinstance(it, dict):
                continue
            m = (Match.query
                 .filter_by(id=it.get("match_id"),
                            competition_id=comp.id, matchday=md)
                 .first())
            if m is None:
                continue
            o1, ox, o2 = fnum(it, "o1"), fnum(it, "ox"), fnum(it, "o2")
            if o1 is None and ox is None and o2 is None:
                continue
            db.session.add(OddsSnapshot(
                competition_id=comp.id, match_id=m.id, matchday=md,
                created_at=now, o1=o1, ox=ox, o2=o2,
                ou25=fnum(it, "ou25"), btts=fnum(it, "btts"),
                ou35=fnum(it, "ou35"), source="online"))
            saved += 1
        if saved == 0:
            return jsonify({"ok": False, "msg": "Keine gültigen Quoten übermittelt."}), 400
        db.session.commit()
        return jsonify({"ok": True, "count": saved})
    except Exception as e:  # JSON-Fehler statt HTML-500: die UI zeigt die Ursache
        db.session.rollback()
        return jsonify({"ok": False, "msg": "Serverfehler: %s" % str(e)[:160]}), 500


@admin_bp.route("/tip-optimizer/snapshot", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def tip_optimizer_snapshot():
    """Speichert den aktuellen Optimizer-Zustand (Spiele mit vollständigen
    1X2-Quoten) als Vorhersage-Run. Dient der prospektiven Modellgüte-
    Abrechnung, wenn der Spieltag beendet ist (Admin-only)."""
    data = request.get_json(silent=True) or {}
    comp = get_active_competition()
    if not comp:
        return jsonify({"ok": False, "msg": "Kein aktiver Wettbewerb."}), 400
    md = data.get("matchday")
    items = data.get("items") or []
    if (not isinstance(md, int) or not (1 <= md <= 40)
            or not isinstance(items, list) or not items):
        return jsonify({"ok": False, "msg": "Ungültige Nutzlast."}), 400

    def fnum(it, key):
        try:
            v = float(it.get(key))
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    try:
        run = OptimizerRun(competition_id=comp.id, matchday=md,
                           user_id=getattr(current_user, "id", None))
        db.session.add(run)
        db.session.flush()
        saved = 0
        for it in items[:20]:
            if not isinstance(it, dict):
                continue
            m = (Match.query
                 .filter_by(id=it.get("match_id"),
                            competition_id=comp.id, matchday=md)
                 .first())
            if m is None:
                continue
            try:
                tip_h = int(it.get("tip_h"))
                tip_a = int(it.get("tip_a"))
            except (TypeError, ValueError):
                continue
            if not (0 <= tip_h <= 11 and 0 <= tip_a <= 11):
                continue
            db.session.add(OptimizerRunTip(
                run_id=run.id, match_id=m.id, tip_h=tip_h, tip_a=tip_a,
                ep=fnum(it, "ep"), p1=fnum(it, "p1"), px=fnum(it, "px"),
                p2=fnum(it, "p2"), pge2=fnum(it, "pge2"), pge3=fnum(it, "pge3"),
                pex=fnum(it, "pex"), lh=fnum(it, "lh"), la=fnum(it, "la"),
                o1=fnum(it, "o1"), ox=fnum(it, "ox"), o2=fnum(it, "o2")))
            saved += 1
        if saved == 0:
            db.session.rollback()
            return jsonify({"ok": False, "msg": "Keine gültigen Tipps übermittelt."}), 400
        db.session.commit()
        return jsonify({"ok": True, "run_id": run.id, "count": saved})
    except Exception as e:  # JSON-Fehler statt HTML-500: die UI zeigt die Ursache
        db.session.rollback()
        return jsonify({"ok": False, "msg": "Serverfehler: %s" % str(e)[:160]}), 500
