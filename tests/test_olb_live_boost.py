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


# ------------------------------------------------------------ (106) -------

def test_live_score_rueckschritt_wird_abgewiesen(live_setup):
    """(106) Feed-Ausrutscher (Rueckschritt 2:0 -> 1:0) aendert den Stand
    nicht — Tore duerfen zwischen Ticks nur dazukommen."""
    m, calls, set_payload = live_setup
    m.status, m.home_score, m.away_score, m.is_live = "live", 2, 0, True
    from extensions import db as _db
    _db.session.commit()
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 1, 0))
    r = boost_live_from_openligadb()
    assert r["updated"] == 0
    dbm = Match.query.get(m.id)
    assert (dbm.home_score, dbm.away_score, dbm.status) == (2, 0, "live")


def test_live_score_schritt_ueber_drei_wird_abgewiesen(live_setup):
    """(106) Mehr als 3 Tore in einem Tick: unplausibel, verwerfen."""
    m, calls, set_payload = live_setup
    m.status, m.home_score, m.away_score, m.is_live = "live", 1, 0, True
    from extensions import db as _db
    _db.session.commit()
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 5, 0))
    r = boost_live_from_openligadb()
    assert r["updated"] == 0
    dbm = Match.query.get(m.id)
    assert (dbm.home_score, dbm.away_score) == (1, 0)


def test_boost_protokolliert_aktivitaet(live_setup):
    """(106) Der Boost schreibt ein Aktivitaets-Protokoll (olb-live), damit
    Admin sees ob/was er geholt hat (Nutzerbefund: fehlende Tore waren
    von aussen nicht diagnostizierbar)."""
    m, calls, set_payload = live_setup
    set_payload(_olb_payload("FC Bayern München", "Borussia Dortmund", m.kickoff, 2, 1))
    boost_live_from_openligadb()
    from scoring import get_setting
    from datasource_activity import SETTING_KEY
    import json as _json
    data = _json.loads(get_setting(SETTING_KEY, "") or "{}")
    eintrag = data.get("olb-live") or {}
    assert eintrag, "olb-live-Aktivitaet fehlt"
    assert eintrag.get("ok") is True
    assert "1 Spiel(e) aktualisiert" in (eintrag.get("note") or "")


def test_cron_sync_ruft_live_boost(app, db, monkeypatch):
    """(106) sync_results (Plesk-Cron) ruft den OLB-Live-Boost jetzt in
    jedem Tick — Live-Tore kommen auch ohne Live-Center-Besucher an."""
    import sync_openligadb as sol
    aufgerufe = []

    monkeypatch.setattr(sol, "sync_with_football_data",
                        lambda: {"ok": True, "msg": "fd ok", "updated": 0})
    monkeypatch.setattr(sol, "_fill_missing_from_openligadb", lambda: 0)

    def fake_boost(matchday=None):
        aufgerufe.append(matchday)
        return {"ok": True, "updated": 2}

    monkeypatch.setattr(sol, "boost_live_from_openligadb", fake_boost)
    res = sol.sync_results()
    assert aufgerufe == [None]
    assert "OLB-Live: 2 Update(s)" in (res.get("msg") or "")
