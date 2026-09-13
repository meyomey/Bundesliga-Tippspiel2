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
        url = url_for("main.match_detail", match_id=m.id)
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    html = client.get(url, follow_redirects=True).get_data(as_text=True)
    assert "⚽ Torschützen" in html and "Harry Kane" in html
    assert "Karten &amp; Platzverweise" in html
    assert "🟨 Gelbe Karte" in html and "Emre Can" in html
    assert "🟥 Platzverweis" in html and "Nico Schlotterbeck" in html
    assert "OpenLigaDB (kostenlose Spielereignisse)" in html
