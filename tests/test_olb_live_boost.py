"""OLB-Live-Boost: schnellere Tor-Anzeige im Live-Center (11.09.2026).

football-data.org delayt Scores im Free-Tier; der Boost holt laufende/gerade
beendete Spiele von OpenLigaDB (nahezu Echtzeit) - mit Fenster-Guard (kein
Call ohne Spiel im Zeitfenster) und 20s-Throttling. Status-Wechsel laufen
uerber apply_match_update, damit die Monotonie-Regeln gelten.
"""
from datetime import datetime, timedelta, timezone

import pytest

from models import Competition, Match, Team

from sync_openligadb import boost_live_from_openligadb


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _olb_payload(home, away, kickoff, hs, as_, finished=False):
    return [{
        "matchID": 4711,
        "matchDateTimeUTC": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matchIsFinished": finished,
        "group": {"groupOrderID": 3},
        "team1": {"teamName": home},
        "team2": {"teamName": away},
        "matchResults": [{"resultTypeID": 2, "pointsTeam1": hs, "pointsTeam2": as_}],
    }]


@pytest.fixture
def live_setup(db):
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    bay = Team(name="FC Bayern München", short_name="FCB", logo="x.png")
    bvb = Team(name="Borussia Dortmund", short_name="BVB", logo="x.png")
    db.session.add_all([bay, bvb])
    db.session.commit()
    m = Match(competition_id=comp.id, matchday=3, home_team_id=bay.id, away_team_id=bvb.id,
              kickoff=datetime.now(timezone.utc) - timedelta(hours=1), status="scheduled")
    db.session.add(m)
    db.session.commit()

    calls = {"n": 0, "payload": None}

    def fake_get(url, timeout=None, **kw):
        calls["n"] += 1
        if calls["payload"] is None:
            return _Resp([], status=503)
        return _Resp(calls["payload"])

    import sync_openligadb
    monkey_target = sync_openligadb.requests
    orig = monkey_target.get
    monkey_target.get = fake_get
    from cache import cache
    cache.delete("olb_live_boost:last_fetch")
    sync_openligadb._olb_boost_last_fetch["ts"] = 0.0
    yield m, calls, lambda p: calls.update(payload=p)
    monkey_target.get = orig
    cache.delete("olb_live_boost:last_fetch")
    sync_openligadb._olb_boost_last_fetch["ts"] = 0.0


def test_goal_from_olb_marks_match_live(live_setup):
    m, calls, set_payload = live_setup
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 2, 1))
    r = boost_live_from_openligadb()
    assert r["updated"] == 1 and calls["n"] == 1
    dbm = Match.query.get(m.id)
    assert (dbm.status, dbm.home_score, dbm.away_score, dbm.is_live) == ("live", 2, 1, True)


def test_throttle_blocks_second_upstream_call(live_setup):
    m, calls, set_payload = live_setup
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 1, 0))
    boost_live_from_openligadb()
    r2 = boost_live_from_openligadb()  # direkt nochmal -> gedrosselt
    assert r2.get("throttled") and calls["n"] == 1


def test_finished_via_olb_clears_minute(live_setup):
    m, calls, set_payload = live_setup
    m.status, m.home_score, m.away_score, m.is_live = "live", 1, 0, True
    m.minute, m.live_phase = 77, "IN_PLAY"
    from extensions import db as _db
    _db.session.commit()
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 3, 0, finished=True))
    r = boost_live_from_openligadb()
    assert r["updated"] == 1
    dbm = Match.query.get(m.id)
    assert dbm.status == "finished" and (dbm.home_score, dbm.away_score) == (3, 0)
    assert dbm.minute is None and dbm.live_phase is None and not dbm.is_live


def test_no_live_window_means_no_http(live_setup):
    from extensions import db as _db
    m, calls, _ = live_setup
    m.kickoff = datetime.now(timezone.utc) + timedelta(days=2)
    _db.session.commit()
    r = boost_live_from_openligadb()
    assert r["updated"] == 0 and calls["n"] == 0


def test_fd_path_gets_boost_counts_via_hook(live_setup, monkeypatch):
    """Der Hook in fetch_live_match_updates zaehlt Boost-Updates ins Ergebnis."""
    import sync_football_data as sfd
    import sync_openligadb
    m, calls, set_payload = live_setup
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 2, 0))

    monkeypatch.setattr(sfd, "_fd_request", lambda path, ttl_seconds=30: (None, "fd down"))
    result = sfd.fetch_live_match_updates(matchday=3)
    assert result["updated"] == 1 and result["olb_boost"] == 1
    assert result["ok"] is True  # fd down, aber Boost liefert -> Live-Center bleibt "gruen"
    assert calls["n"] == 1
