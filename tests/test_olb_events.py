"""OLB-Spielereignisse als gratis Nachzueger (13.09.2026).

Der Feed liefert aktuell null Events - der Pfad ist trotzdem die einzige
kostenlose Quelle fuer Tore/Karten nach Abpfiff und soll automatisch greifen,
sobald OLB pflegt. Geprueft: Normalisierung, Merge-Regeln (kein Ueberschreiben
fremder Zeilen, keine Duplikate gegen den Goal-Boost), Idempotenz, Sync-
Integration und die Karten-Sektion im Spielbericht.
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import sync_openligadb as so
from extensions import db
from models import Competition, Match


def _md(events, finished=True):
    return {
        "matchID": 555,
        "matchDateTime": "2026-09-11T17:30:00Z",
        "matchIsFinished": finished,
        "team1": {"teamId": 1, "shortName": "FCB", "teamName": "FC Bayern München"},
        "team2": {"teamId": 2, "shortName": "BVB", "teamName": "Borussia Dortmund"},
        "matchResults": [{"resultTypeID": 2, "resultName": "FT",
                          "pointsTeam1": 2, "pointsTeam2": 1}],
        "matchEvents": events,
    }


def test_event_rows_normalizes_and_filters():
    md = _md([
        {"matchEventType": "Goal", "minute": 12, "playerName": "Harry Kane",
         "teamId": 1, "isPenalty": True},
        {"matchEventType": "Own Goal", "minute": 55, "playerName": "M. Hummels", "teamId": 2},
        {"matchEventType": "Yellow Card", "minute": 31, "playerName": "Emre Can", "teamId": 2},
        {"matchEventType": "Red Card", "minute": 80, "playerName": "N. Schlotterbeck", "teamId": 1},
        {"matchEventType": "Penalty missed", "minute": 66, "playerName": "Kane", "teamId": 1},
        {"matchEventType": "Change", "minute": 90, "playerName": "Wechsel", "teamId": 1},
    ])
    rows = so._olb_event_rows(md)
    kinds = [(r.get("kind"), r.get("type"), r.get("min")) for r in rows]
    assert (len(rows)) == 4  # Elfer-Fehlschuss + Wechsel fallen raus
    goal12 = next(r for r in rows if r["min"] == 12)
    assert goal12["kind"] == "gf" and goal12["penalty"] is True and goal12["team"] == "home"
    og = next(r for r in rows if r["min"] == 55)
    assert og["own_goal"] is True and og["team"] == "away"
    gelb = next(r for r in rows if r.get("card") == "gelb")
    assert gelb["type"] == "card" and gelb["team"] == "away"
    rot = next(r for r in rows if r.get("card") == "rot")
    assert rot["min"] == 80


def test_numeric_event_types_supported():
    md = _md([
        {"matchEventType": 1, "minute": 70, "playerName": "X", "teamId": 1},
        {"matchEventType": 2, "minute": 71, "playerName": "Y", "teamId": 2},
    ])
    rows = so._olb_event_rows(md)
    assert rows[0]["kind"] == "gf"
    assert rows[1]["card"] == "gelb"


def test_apply_merge_no_dupes_idempotent_and_foreign_kept():
    md = _md([
        {"matchEventType": "Goal", "minute": 12, "playerName": "H. Kane", "teamId": 1},
        {"matchEventType": "Goal", "minute": 55, "playerName": "W. Spieler", "teamId": 2},
        {"matchEventType": "Yellow Card", "minute": 31, "playerName": "E. Can", "teamId": 2},
    ])
    match = SimpleNamespace(events=json.dumps([
        {"kind": "gf", "min": 12, "team": "home", "player": "Harry Kane",
         "assist": "Jamal Musiala", "penalty": False, "own_goal": False},
        {"type": "card", "side": "legacy"},  # Fremdformat (live_scoring-Legat)
    ]))
    added = so._apply_olb_events(md, match)
    rows = json.loads(match.events)
    gf12 = next(r for r in rows if r.get("min") == 12 and r.get("kind") == "gf")
    assert gf12.get("assist") == "Jamal Musiala"      # af-Zeile bleibt, OLB-Duplikat raus
    assert added == 2                                   # 55er-Tor + Gelb
    assert any(r.get("card") == "gelb" for r in rows)
    assert {"type": "card", "side": "legacy"} in rows   # Fremdformat unangetastet
    # 2. Lauf: nichts Neues (Idempotenz)
    assert so._apply_olb_events(md, match) == 0


def test_apply_only_when_finished():
    md = _md([{"matchEventType": "Goal", "minute": 5, "playerName": "X", "teamId": 1}],
             finished=False)
    match = SimpleNamespace(events="[]")
    assert so._apply_olb_events(md, match) == 0
    assert match.events == "[]"


def test_full_sync_stores_events_and_reports(app, db, monkeypatch):
    comp = Competition.query.filter_by(code="BL1").first() or Competition(
        code="BL1", name="Bundesliga", season="2026", matchdays=34,
        teams_count=18, is_active=True)
    db.session.add(comp)
    db.session.commit()
    payload = [_md([
        {"matchEventType": "Goal", "minute": 20, "playerName": "Tore Spieler", "teamId": 1},
        {"matchEventType": "Yellow Card", "minute": 60, "playerName": "Gelber Held", "teamId": 2},
    ])]
    payload[0]["group"] = {"groupOrderID": 4, "groupMatchday": "4. Spieltag"}
    payload[0]["matchDateTimeUTC"] = "2026-09-11T17:30:00Z"

    class Resp:
        status_code = 200

        def json(self):
            return payload

    import requests as _rq
    monkeypatch.setattr(so.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    with app.app_context():
        res = so.sync_with_openligadb()
        assert res["ok"] is True
        assert res["events"] == 1
        assert "neuen Ereignissen" in res["msg"]
        m = Match.query.filter(Match.external_id == "oldb:555").first()
        assert m is not None
        rows = json.loads(m.events)
        assert any(r.get("card") == "gelb" and r.get("min") == 60 for r in rows)


def test_match_detail_renders_cards_and_goals(client, db, user, app):
    with app.app_context():
        comp = Competition.query.filter_by(code="BL1").first() or Competition(
            code="BL1", name="Bundesliga", season="2026", matchdays=34,
            teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
        from models import Team
        bay = Team.query.filter_by(short_name="FCB").first() or Team(
            name="FC Bayern München", short_name="FCB", logo="x.png")
        bvb = Team.query.filter_by(short_name="BVB").first() or Team(
            name="Borussia Dortmund", short_name="BVB", logo="x.png")
        db.session.add_all([t for t in (bay, bvb) if t.id is None])
        db.session.commit()
        m = Match(
            competition_id=comp.id, matchday=4, home_team_id=bay.id, away_team_id=bvb.id,
            kickoff=datetime.now(timezone.utc) - timedelta(hours=20),
            status="finished", home_score=2, away_score=0,
            events=json.dumps([
                {"kind": "gf", "min": 12, "team": "home", "player": "Harry Kane",
                 "assist": "Jamal Musiala", "penalty": False, "own_goal": False},
                {"kind": "olb", "type": "card", "card": "gelb", "min": 31,
                 "team": "away", "player": "Emre Can", "src": "olb"},
                {"kind": "olb", "type": "card", "card": "rot", "min": 80,
                 "team": "away", "player": "Nico Schlotterbeck", "src": "olb"},
            ], ensure_ascii=False),
        )
        db.session.add(m)
        db.session.commit()
        from flask import url_for
        # (126) expliziter Request-Kontext: pytest 9 leakt keinen mehr
        with app.test_request_context("/"):
            url = url_for("main.match_detail", match_id=m.id)
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get(url, follow_redirects=True).get_data(as_text=True)
    assert "⚽ Torschützen" in html and "Harry Kane" in html
    assert "Karten &amp; Platzverweise" in html
    assert "🟨 Gelbe Karte" in html and "Emre Can" in html
    assert "🟥 Platzverweis" in html and "Nico Schlotterbeck" in html
    assert "OpenLigaDB (kostenlose Spielereignisse)" in html


# ------------------ (134) Torschuetzen key-frei aus dem goals-Array ------
# Live-Probe 18.10.2026 (ST6): matchEvents durchgehend leer, aber goals[]
# liefert matchMinute + goalGetterName + isPenalty/isOwnGoal + scoringTeamId
# - auch fuer laufende Spiele. Parser + Merge + Every-Tick-Boost.

def test_goal_rows_aus_goals_array_134():
    md = _md([], finished=False)
    md["team1"]["teamId"] = 7
    md["team2"]["teamId"] = 9
    md["goals"] = [
        {"scoreTeam1": 1, "scoreTeam2": 0, "matchMinute": 4,
         "goalGetterName": "L. Petkov", "scoringTeamId": 7,
         "isPenalty": False, "isOwnGoal": False},
        {"scoreTeam1": 1, "scoreTeam2": 1, "matchMinute": 19,
         "goalGetterName": "I. Maza", "scoringTeamId": 9,
         "isPenalty": False, "isOwnGoal": False},
        {"scoreTeam1": 1, "scoreTeam2": 2, "matchMinute": 76,
         "goalGetterName": "M. Gregoritsch", "scoringTeamId": 9,
         "isPenalty": True, "isOwnGoal": False},
        # ohne scoringTeamId: Seite aus der Score-Kette
        {"scoreTeam1": 2, "scoreTeam2": 2, "matchMinute": 88,
         "goalGetterName": "H. Kane", "isPenalty": False, "isOwnGoal": False},
        # Eigentor: Seite = Beguenstigter, Flag bleibt erhalten
        {"scoreTeam1": 3, "scoreTeam2": 2, "matchMinute": 90,
         "goalGetterName": "Pechvogel", "scoringTeamId": 7,
         "isPenalty": False, "isOwnGoal": True},
        # ohne Minute: bewusst raus (App-Format verlangt min >= 1)
        {"scoreTeam1": 4, "scoreTeam2": 2, "matchMinute": None,
         "goalGetterName": "Ohne Minute", "scoringTeamId": 7},
    ]
    rows = so._olb_goal_rows(md)
    assert [(r["min"], r["team"], r["player"]) for r in rows] == [
        (4, "home", "L. Petkov"), (19, "away", "I. Maza"),
        (76, "away", "M. Gregoritsch"), (88, "home", "H. Kane"),
        (90, "home", "Pechvogel")]
    assert rows[2]["penalty"] is True and rows[4]["own_goal"] is True
    assert all(r["kind"] == "gf" and r["src"] == "olb" for r in rows)


def test_apply_mergiert_goals_und_dedupliziert_134():
    md = _md([], finished=True)
    md["team1"]["teamId"] = 7
    md["team2"]["teamId"] = 9
    md["goals"] = [
        {"scoreTeam1": 1, "scoreTeam2": 0, "matchMinute": 12,
         "goalGetterName": "OLB Schuetze", "scoringTeamId": 7,
         "isPenalty": False, "isOwnGoal": False},
        {"scoreTeam1": 2, "scoreTeam2": 0, "matchMinute": 70,
         "goalGetterName": "Neuer Schuetze", "scoringTeamId": 7,
         "isPenalty": False, "isOwnGoal": False},
    ]
    match = SimpleNamespace(events=json.dumps([
        {"kind": "gf", "min": 12, "team": "home", "player": "Harry Kane",
         "assist": "Jamal Musiala", "penalty": False, "own_goal": False}]))
    assert so._apply_olb_events(md, match) == 1      # nur Minute 70 ist neu
    rows = json.loads(match.events)
    assert next(r for r in rows if r["min"] == 12)["player"] == "Harry Kane"
    assert next(r for r in rows if r["min"] == 70)["player"] == "Neuer Schuetze"


def test_apply_erlaubt_laufende_spiele_134():
    md = _md([], finished=False)                     # live: matchIsFinished false
    md["team1"]["teamId"] = 7
    md["goals"] = [
        {"scoreTeam1": 1, "scoreTeam2": 0, "matchMinute": 14,
         "goalGetterName": "Live Tor", "scoringTeamId": 7,
         "isPenalty": False, "isOwnGoal": False}]
    match = SimpleNamespace(events="[]", status="live")
    assert so._apply_olb_events(md, match) == 1
    assert json.loads(match.events)[0]["player"] == "Live Tor"
    # geplante Spiele bleiben zu (kein Anlass, dort zu schreiben)
    assert so._apply_olb_events(
        md, SimpleNamespace(events="[]", status="scheduled")) == 0


def test_boost_events_from_openligadb_134(app, db, monkeypatch):
    comp = Competition.query.filter_by(code="BL1").first() or Competition(
        code="BL1", name="Bundesliga", season="2026", matchdays=34,
        teams_count=18, is_active=True)
    db.session.add(comp)
    db.session.commit()
    from models import Team
    bay = Team.query.filter_by(short_name="FCB").first() or Team(
        name="FC Bayern München", short_name="FCB", logo="x.png")
    bvb = Team.query.filter_by(short_name="BVB").first() or Team(
        name="Borussia Dortmund", short_name="BVB", logo="x.png")
    db.session.add_all([t for t in (bay, bvb) if t.id is None])
    db.session.commit()
    m = Match(competition_id=comp.id, matchday=6, home_team_id=bay.id,
              away_team_id=bvb.id,
              kickoff=datetime.now(timezone.utc) - timedelta(hours=20),
              status="finished", home_score=2, away_score=0)
    db.session.add(m)
    db.session.commit()

    md = _md([], finished=True)                      # teamName FCB/BVB via Map
    md["goals"] = [
        {"scoreTeam1": 1, "scoreTeam2": 0, "matchMinute": 12,
         "goalGetterName": "Harry Kane", "scoringTeamId": 1,
         "isPenalty": False, "isOwnGoal": False},
        {"scoreTeam1": 2, "scoreTeam2": 0, "matchMinute": 70,
         "goalGetterName": " Jamal Musiala ", "scoringTeamId": 1,
         "isPenalty": False, "isOwnGoal": False},
    ]

    class Resp:
        status_code = 200

        def json(self):
            return [md]

    monkeypatch.setattr(so.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(so, "current_sync_season_code", lambda: "2026")
    monkeypatch.setitem(app.config, "COMPETITION", "BL1")
    so._olb_events_last_fetch["ts"] = 0.0
    with app.app_context():
        res = so.boost_events_from_openligadb()
        assert res["updated"] == 1
        rows = json.loads(db.session.get(Match, m.id).events)
        assert [r["player"] for r in rows] == ["Harry Kane", "Jamal Musiala"]
        # zweiter Aufruf sofort -> gedrosselt (eigener 20-s-Throttle)
        assert so.boost_events_from_openligadb().get("throttled") is True
    so._olb_events_last_fetch["ts"] = 0.0


def test_fd_pfad_bindet_olb_event_boost_ein_134():
    """(134) Hook sitzt im Cron-Sync (je Tick), NICHT im Live-Polling —
    jeder Center-Poll darf keinen zusaetzlichen OLB-Call ausloesen."""
    src = open("sync_football_data.py", encoding="utf-8").read()
    assert "boost_events_from_openligadb" not in src
    src2 = open("sync_openligadb.py", encoding="utf-8").read()
    assert "def boost_events_from_openligadb" in src2
    assert "_olb_goal_rows" in src2
    assert "boost_events_from_openligadb()" in src2
