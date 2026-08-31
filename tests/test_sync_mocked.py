"""Sync-Absicherung ohne echte API: football-data.org und OpenLigaDB sind
komplett gemockt. Deckt ab: Mapping, Deduplizierung, Ergebnis-Updates inkl.
Punkte-Neuberechnung, Rate-Limit/Timeout/Cache-Fallback und Purge-Bremse."""
from datetime import datetime, timedelta, timezone

import pytest
import requests as real_requests

import sync
from models import Comment, Competition, Match, Prediction, Team
from scoring import get_setting, set_setting


# ---------------------------------------------------------------- Helfer

def _fd_match(mid, home, away, status="SCHEDULED", matchday=1,
              kickoff="2026-09-05T13:30:00Z", hs=None, as_=None):
    return {
        "id": mid,
        "utcDate": kickoff,
        "matchday": matchday,
        "status": status,
        "homeTeam": {"id": 10000 + mid, "name": home, "shortName": home[:3].upper(), "tla": home[:3].upper()},
        "awayTeam": {"id": 20000 + mid, "name": away, "shortName": away[:3].upper(), "tla": away[:3].upper()},
        "score": {"winner": None,
                  "fullTime": {"home": hs, "away": as_},
                  "halfTime": {"home": None, "away": None}},
    }


class _FakeResp:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code = status
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("kaputt")
        return self._payload


@pytest.fixture
def bl1_comp(db):
    """BL1-Competition - existiert evtl. schon durch den App-Bootstrap-Seed."""
    comp = Competition.query.filter_by(code="BL1").first()
    if comp:
        return comp
    comp = Competition(code="BL1", name="Bundesliga", season="2026",
                       matchdays=34, teams_count=18, is_active=True)
    db.session.add(comp)
    db.session.commit()
    return comp


# ---------------------------------------------------------------- Mapping & Deduplizierung

def test_fd_processing_creates_matches_and_teams(db, bl1_comp):
    data = {"matches": [
        _fd_match(1001, "FC Testwald", "SV Prüfing"),
        _fd_match(1002, "Dynamo Muster", "FC Kilometer", status="FINISHED", hs=3, as_=1),
    ]}
    res = sync._process_football_data(data, bl1_comp.id)
    assert res["ok"] and res["created"] == 2

    m1 = Match.query.filter_by(external_id="fd:1001").one()
    assert m1.status == "scheduled" and m1.competition_id == bl1_comp.id
    assert m1.kickoff.year == 2026 and m1.kickoff.month == 9
    m2 = Match.query.filter_by(external_id="fd:1002").one()
    assert m2.status == "finished" and (m2.home_score, m2.away_score) == (3, 1)
    # Teams automatisch angelegt
    for name in ("FC Testwald", "SV Prüfing", "Dynamo Muster", "FC Kilometer"):
        assert Team.query.filter_by(name=name).first() is not None


def test_fd_processing_second_run_updates_not_duplicates(db, bl1_comp):
    data = {"matches": [_fd_match(1001, "FC Testwald", "SV Prüfing")]}
    first = sync._process_football_data(data, bl1_comp.id)
    assert first["created"] == 1
    again = sync._process_football_data(data, bl1_comp.id)
    assert again["created"] == 0 and again["updated"] == 1
    assert Match.query.filter_by(external_id="fd:1001").count() == 1


# ---------------------------------------------------------------- Ergebnis-Update + Punkte

def test_fd_result_update_recalculates_prediction_points(db, bl1_comp, user, app):
    scheduled = {"matches": [_fd_match(1001, "FC Testwald", "SV Prüfing")]}
    sync._process_football_data(scheduled, bl1_comp.id)
    match = Match.query.filter_by(external_id="fd:1001").one()
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=2, away_tip=1))
    db.session.commit()

    finished = {"matches": [_fd_match(1001, "FC Testwald", "SV Prüfing",
                                      status="FINISHED", hs=2, as_=1)]}
    res = sync._process_football_data(finished, bl1_comp.id)
    assert res["updated"] == 1

    fresh = Match.query.get(match.id)
    assert fresh.status == "finished" and (fresh.home_score, fresh.away_score) == (2, 1)
    pred = Prediction.query.filter_by(user_id=user.id, match_id=match.id).one()
    assert pred.points == app.config["POINTS_EXACT"]  # exakter Tipp


# ---------------------------------------------------------------- Rate-Limit / Timeout / Cache

def test_fd_request_handles_timeout_rate_limit_and_cache(db, app, monkeypatch):
    set_setting("football_data_token", "TESTTOKEN")

    # Timeout -> Fehlermeldung, keine Exception
    def _raise_timeout(url, headers=None, timeout=None):
        raise real_requests.exceptions.Timeout("zu langsam")
    monkeypatch.setattr(sync.requests, "get", _raise_timeout)
    data, err = sync._fd_request("/irgendwas")
    assert data is None and "Netzwerkfehler" in err

    # 429 -> Rate-Limit-Meldung
    monkeypatch.setattr(sync.requests, "get", lambda url, headers=None, timeout=None: _FakeResp(429))
    data, err = sync._fd_request("/irgendwas2")
    assert data is None and "Rate-Limit" in err

    # Frischer Cache schlaegt Netz UND Rate-Limit
    set_setting("fd_cache:/gecached", {"ts": datetime.now(timezone.utc).timestamp(),
                                       "data": {"spiele": 42}})
    data, err = sync._fd_request("/gecached")
    assert data == {"spiele": 42} and err is None

    # bei API-Fehler faellt er auf den (<=10 Minuten alten) Cache zurueck
    data, err = sync._fd_request("/gecached", ttl_seconds=0)
    assert data == {"spiele": 42} and err is None

    # Ungueltiges JSON -> klare Meldung statt Traceback
    monkeypatch.setattr(sync.requests, "get", lambda url, headers=None, timeout=None: _FakeResp(200, bad_json=True))
    data, err = sync._fd_request("/kaputt")
    assert data is None and "JSON" in err


# ---------------------------------------------------------------- Purge-Bremse

def test_purge_safety_blocks_on_incomplete_api_payload(db):
    """API liefert ploetzlich viel zu wenig: Purge wird gebremst (kein Datenverlust).
    Eigener Test-Wettbewerb, damit der App-Bootstrap-Demo-Seed nicht stört."""
    bl1_comp = Competition(code="PURG_SAFE", name="Purge-Test", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
    db.session.add(bl1_comp)
    db.session.commit()
    teams = []
    for i in range(6):
        t = Team(name=f"Purge-Team {i}", short_name=f"P{i}", logo="x.png")
        db.session.add(t)
        teams.append(t)
    db.session.commit()
    for i in range(55):
        db.session.add(Match(competition_id=bl1_comp.id, matchday=1 + (i % 3),
                             home_team_id=teams[i % 6].id, away_team_id=teams[(i + 1) % 6].id,
                             kickoff=datetime.now(timezone.utc) + timedelta(days=i),
                             status="scheduled", external_id=f"fd:{i}"))
    db.session.commit()
    removed = sync._purge_stale_matches_for_comp(bl1_comp.id, {"fd:0"})
    assert removed == 0
    assert Match.query.filter_by(competition_id=bl1_comp.id).count() == 55


def test_purge_removes_stale_match_with_prediction_and_comment(db, user):
    bl1_comp = Competition(code="PURG_DEL", name="Purge-Test-2", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
    db.session.add(bl1_comp)
    db.session.commit()
    t1 = Team(name="Purge A", short_name="PA", logo="x.png")
    t2 = Team(name="Purge B", short_name="PB", logo="x.png")
    db.session.add_all([t1, t2])
    db.session.commit()
    keep = Match(competition_id=bl1_comp.id, matchday=1, home_team_id=t1.id, away_team_id=t2.id,
                 kickoff=datetime.now(timezone.utc) + timedelta(days=1), status="scheduled",
                 external_id="fd:keep")
    stale = Match(competition_id=bl1_comp.id, matchday=1, home_team_id=t2.id, away_team_id=t1.id,
                  kickoff=datetime.now(timezone.utc) + timedelta(days=2), status="scheduled",
                  external_id="fd:stale")
    db.session.add_all([keep, stale])
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=stale.id, home_tip=1, away_tip=1))
    db.session.add(Comment(user_id=user.id, match_id=stale.id, text="weg damit"))
    db.session.commit()

    stale_id, keep_id = stale.id, keep.id
    removed = sync._purge_stale_matches_for_comp(bl1_comp.id, {"fd:keep"})
    assert removed == 1
    assert Match.query.filter_by(id=stale_id).count() == 0
    assert Match.query.filter_by(id=keep_id).count() == 1
    assert Prediction.query.filter_by(match_id=stale_id).count() == 0
    assert Comment.query.filter_by(match_id=stale_id).count() == 0


# ---------------------------------------------------------------- OpenLigaDB-Fallback

def test_openligadb_sync_maps_finished_result(db, bl1_comp, monkeypatch):
    payload = [
        {  # camelCase (aktuelles OLB-Format)
            "matchID": 555,
            "team1": {"teamName": "FC Nordtest"},
            "team2": {"teamName": "FC Südtest"},
            "matchDateTimeUTC": "2026-09-06T15:30:00Z",
            "group": {"groupOrderID": 2},
            "matchIsFinished": True,
            "matchResults": [
                {"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0},   # Halbzeit
                {"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 0},   # Endergebnis
            ],
        },
        {  # PascalCase (altes OLB-Format) - Helper akzeptiert beides
            "MatchID": 556,
            "Team1": {"TeamName": "FC Altformat"},
            "Team2": {"TeamName": "FC Neuformat"},
            "MatchDateTimeUTC": "2026-09-06T18:30:00Z",
            "Group": {"GroupOrderID": 2},
            "MatchIsFinished": False,
            "MatchResults": [],
        },
    ]
    monkeypatch.setattr(sync.requests, "get", lambda url, timeout=None: _FakeResp(200, payload))
    res = sync.sync_with_openligadb()
    assert res["ok"] and res["created"] == 2

    m1 = Match.query.filter_by(external_id="oldb:555").one()
    assert m1.status == "finished" and (m1.home_score, m1.away_score) == (2, 0)
    assert m1.matchday == 2 and m1.competition_id == bl1_comp.id
    m2 = Match.query.filter_by(external_id="oldb:556").one()
    assert m2.status == "scheduled" and m2.home_score is None


def test_store_sync_result_sets_timestamp(db):
    out = sync.store_sync_result({"ok": True, "msg": "alles gut"})
    assert "at" in out
    saved = get_setting("last_sync_result")
    assert saved["ok"] is True and "at" in saved
