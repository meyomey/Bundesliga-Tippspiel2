"""Tests Ranglisten-Tempo ((94)): Memory-Cache-Fallback, cache-sichere
Serialisierung, Bulk-Rangkarte + Trend-Parameter.

Baseline vor (94), gemessen mit 14 Spielern x 1512 Tipps:
  GET /tabelle = ~950 ms / 2064 Queries (Cache ohne Redis tot, Trends N+1)
Danach: ~40-65 ms / ~50 Queries (23x schneller, 42x weniger Queries).
"""
import time

import pytest
from sqlalchemy import func, inspect as sa_inspect

from extensions import db
from models import Match, Prediction, User


# ------------------------------------------------------------ Fixtures ---
@pytest.fixture()
def memory_cache(app, monkeypatch):
    """Aktiviert den globalen Memory-Cache fuer EINEN Test, raeumt danach auf."""
    monkeypatch.setitem(app.config, "REDIS_URL", None)
    monkeypatch.setitem(app.config, "CACHE_MEMORY_FALLBACK", True)
    from cache import cache
    cache.init_app(app)
    yield cache
    cache._enabled = False
    cache._backend = "none"
    cache._mem = {}


def _spiel(db, competition, teams, spieltag, tage_zurueck, score=(2, 1)):
    m = Match(competition_id=competition.id, matchday=spieltag,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=db.session.query(func.datetime("now")).scalar(),  # Dummy, s. u.
              status="finished", home_score=score[0], away_score=score[1])
    from datetime import datetime, timedelta, timezone
    m.kickoff = datetime.now(timezone.utc) - timedelta(days=tage_zurueck)
    db.session.add(m)
    db.session.flush()
    return m


def _tipp(db, user, match, punkte):
    db.session.add(Prediction(user_id=user.id, match_id=match.id,
                              home_tip=2, away_tip=1, joker=False, points=punkte))


# --------------------------------------------------- Memory-Fallback ---
def test_fallback_aktiviert_ohne_redis(app, memory_cache):
    assert memory_cache.enabled is True
    assert memory_cache._backend == "memory"


def test_fallback_abschaltbar(app, monkeypatch):
    monkeypatch.setitem(app.config, "REDIS_URL", None)
    monkeypatch.setitem(app.config, "CACHE_MEMORY_FALLBACK", False)
    from cache import CacheManager
    cm = CacheManager()
    cm.init_app(app)
    assert cm.enabled is False
    assert cm._backend == "none"


def test_memory_roundtrip_ttl_delete_pattern_clear(app, memory_cache):
    assert memory_cache.set("k1", {"a": 1}, ttl=60) is True
    assert memory_cache.get("k1") == {"a": 1}
    # Abgelaufener Eintrag wird beim Get entfernt
    memory_cache.set("k2", "alt", ttl=60)
    memory_cache._mem["k2"]["bis"] = time.monotonic() - 1
    assert memory_cache.get("k2") is None
    assert "k2" not in memory_cache._mem
    # delete / delete_many / delete_pattern
    assert memory_cache.delete("k1") is True
    assert memory_cache.get("k1") is None
    for i in range(5):
        memory_cache.set(f"muster:{i}", i, ttl=60)
    memory_cache.set("muster:anders", "x", ttl=60)
    assert memory_cache.delete_pattern("muster:*") == 6
    assert memory_cache.set("weg", 1, ttl=60)
    assert memory_cache.delete_many(["weg", "nicht-da"]) == 1
    stats = memory_cache.get_stats()
    assert stats["enabled"] is True and stats["backend"] == "memory"
    assert memory_cache.clear() is True
    assert memory_cache._mem == {}


def test_ohne_redis_und_ohne_flag_ist_cache_aus(app):
    from cache import CacheManager
    cm = CacheManager()
    cm.init_app(app)  # TestConfig: REDIS_URL None, Fallback False
    assert cm.enabled is False
    assert cm.set("x", 1) is False and cm.get("x") is None


# ------------------------------------------- Cache-sichere Rangliste ---
def test_leaderboard_cache_hit_mit_sitzungsfrischen_usern(
        app, db, user, admin_user, competition, teams, monkeypatch, memory_cache):
    """Zweiter Aufruf = Hit: identische Zahlen, User-Objekte NICHT detached,
    lazy favorite_team-Zugriff bleibt sicher (der 500er-Fall von vorher)."""
    from datetime import datetime, timedelta, timezone
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    m1 = Match(competition_id=competition.id, matchday=3,
               home_team_id=teams[0].id, away_team_id=teams[1].id,
               kickoff=datetime.now(timezone.utc) - timedelta(days=14),
               status="finished", home_score=2, away_score=1)
    m2 = Match(competition_id=competition.id, matchday=4,
               home_team_id=teams[1].id, away_team_id=teams[0].id,
               kickoff=datetime.now(timezone.utc) - timedelta(days=7),
               status="finished", home_score=0, away_score=0)
    db.session.add_all([m1, m2])
    db.session.flush()
    _tipp(db, user, m1, 6)
    _tipp(db, admin_user, m1, 1)
    _tipp(db, user, m2, 2)
    _tipp(db, admin_user, m2, 4)
    db.session.commit()

    from scoring import get_leaderboard
    r1 = get_leaderboard()
    r2 = get_leaderboard()  # Hit
    assert [r["rank"] for r in r1] == [r["rank"] for r in r2]
    assert [r["points"] for r in r1] == [r["points"] for r in r2]
    assert [r["user"].id for r in r1] == [r["user"].id for r in r2]
    for r in r2:
        insp = sa_inspect(r["user"])
        assert insp.detached is False      # frisch aus der aktuellen Session
        assert r["user"].favorite_team is None  # lazy-Zugriff wirft nicht
    # Invalidierung leert den Eintrag -> naechster Aufruf rechnet neu
    from cache import invalidate_leaderboard
    invalidate_leaderboard()
    assert memory_cache._mem == {}


# ------------------------------------------------- Bulk-Rangkarte ---
def test_rank_map_gleicht_altem_algorithmus(app, db, user, admin_user,
                                            competition, teams, monkeypatch):
    """rank_map_through liefert exakt die Raenge der alten N-Query-Schleife
    (inkl. 0-Punkte-User, Tie-Break user_id aufsteigend)."""
    from datetime import datetime, timedelta, timezone
    from stats_personal import rank_map_through
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    m1 = Match(competition_id=competition.id, matchday=2,
               home_team_id=teams[0].id, away_team_id=teams[1].id,
               kickoff=datetime.now(timezone.utc) - timedelta(days=14),
               status="finished", home_score=3, away_score=1)
    m2 = Match(competition_id=competition.id, matchday=3,
               home_team_id=teams[1].id, away_team_id=teams[0].id,
               kickoff=datetime.now(timezone.utc) - timedelta(days=7),
               status="finished", home_score=1, away_score=1)
    m3 = Match(competition_id=competition.id, matchday=4,
               home_team_id=teams[0].id, away_team_id=teams[1].id,
               kickoff=datetime.now(timezone.utc) - timedelta(days=1),
               status="scheduled")
    db.session.add_all([m1, m2, m3])
    db.session.flush()
    _tipp(db, user, m1, 10)       # nur bis ST 2 gewertet
    _tipp(db, admin_user, m1, 4)
    _tipp(db, admin_user, m2, 6)  # ST 3 zaehlt NICHT fuer max=2
    db.session.commit()

    karte = rank_map_through(2)
    # Alter Algorithmus (Nachbau der Original-Logik):
    punkte = {}
    for u in User.query.all():
        pts = db.session.query(func.coalesce(func.sum(Prediction.points), 0)) \
            .join(Match, Prediction.match_id == Match.id) \
            .filter(Prediction.user_id == u.id, Match.matchday <= 2,
                    Match.status == "finished").scalar() or 0
        punkte[u.id] = int(pts)
    erwartet = {uid: rank for rank, (uid, _) in
                enumerate(sorted(punkte.items(), key=lambda x: -x[1]), 1)}
    assert karte == erwartet
    assert karte[user.id] == 1 and karte[admin_user.id] == 2


# ------------------------------------------------- Trend-Paritaet ---
def test_trend_mit_bulk_params_identisch_zu_alt(app, db, user, admin_user,
                                                competition, teams, monkeypatch):
    """get_user_trend mit rows+rank_map liefert dasselbe Ergebnis wie der
    alte Weg (eigene get_leaderboard()-Berechnung + Einzel-Replay)."""
    from datetime import datetime, timedelta, timezone
    from stats_personal import get_user_trend, vor_spieltag_rangkarte
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    for md in range(1, 4):
        m = Match(competition_id=competition.id, matchday=md,
                  home_team_id=teams[0].id, away_team_id=teams[1].id,
                  kickoff=datetime.now(timezone.utc) - timedelta(days=3 * (4 - md)),
                  status="finished", home_score=md, away_score=1)
        db.session.add(m)
        db.session.flush()
        _tipp(db, user, m, 3 + md)
        _tipp(db, admin_user, m, md)
    db.session.commit()

    from scoring import get_leaderboard
    rows = get_leaderboard()
    karte, md = vor_spieltag_rangkarte()
    assert karte and md == 2
    for u in (user, admin_user):
        schnell = get_user_trend(u.id, last_n_matchdays=6, rows=rows,
                                 prev_rank_map=karte, prev_map_md=md)
        alt = get_user_trend(u.id, last_n_matchdays=6)
        assert schnell == alt
        assert schnell["current_rank"] is not None


# --------------------------------------------------- Route-Rauch ---
def test_tabelle_200_mit_trends(client, app, db, user, competition, teams,
                                monkeypatch):
    from datetime import datetime, timedelta, timezone
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    m = Match(competition_id=competition.id, matchday=2,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(days=7),
              status="finished", home_score=2, away_score=1)
    db.session.add(m)
    db.session.flush()
    _tipp(db, user, m, 5)
    db.session.commit()
    client.post("/auth/login", data={"email": user.email, "password": "testpass123"},
                follow_redirects=True)
    resp = client.get("/tabelle")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert user.username in body   # Zeile gerendert
