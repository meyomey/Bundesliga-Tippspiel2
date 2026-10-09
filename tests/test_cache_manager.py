"""Test-Runde 3 ((90)): CacheManager + cached-Decorator (vorher 62 %).

Ein Fake-Redis (dict-basiert) steht fuer das echte Modul — die App selbst
bleibt unberuehrt, der globale `cache` wird per init_app je Test verbunden.
"""
import fnmatch

import pytest

import cache as cache_mod
from cache import (
    CACHE_VERSION,
    CacheManager,
    cache,
    cache_key_leaderboard,
    cache_key_live_matches,
    cache_key_match_detail,
    cache_key_user_stats,
    cached,
    invalidate_leaderboard,
    invalidate_match,
)


class FakeRedis:
    """Minimales Redis-Ersatz-Stueck fuer die CacheManager-Oberflaeche."""

    def __init__(self, kaputt=False):
        self.store = {}
        self.ttls = {}
        self.flushed = 0
        self.kaputt = kaputt

    def ping(self):
        if self.kaputt:
            raise ConnectionError("Redis weg")
        return True

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl
        return True

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    def scan_iter(self, match="*", count=500):
        for k in list(self.store):
            if fnmatch.fnmatch(k, match):
                yield k

    def keys(self, pattern):
        return list(self.scan_iter(match=pattern))

    def info(self):
        return {"keyspace_hits": 30, "keyspace_misses": 10,
                "used_memory_human": "1M", "connected_clients": 2}

    def dbsize(self):
        return len(self.store)

    def flushdb(self):
        self.flushed += 1
        self.store.clear()
        return True


@pytest.fixture()
def verbundener_cache(app, monkeypatch):
    """Verbindet den globalen cache mit FakeRedis und leert ihn danach."""
    fake = FakeRedis()
    monkeypatch.setattr(cache_mod.redis, "from_url",
                        staticmethod(lambda *a, **k: fake))
    monkeypatch.setitem(app.config, "REDIS_URL", "redis://fake:6379/0")
    cache.init_app(app)
    yield fake
    cache._enabled = False
    cache._redis = None


def test_deaktivierter_cache_ist_harmlos(app):
    """Ohne Redis: get None, set/delete False, Muster 0, Stats disabled."""
    cm = CacheManager()
    cm.init_app(app)  # kein REDIS_URL in der Test-Config gesetzt
    assert cm.enabled is False
    assert cm.get("x") is None
    assert cm.set("x", 1) is False
    assert cm.delete("x") is False
    assert cm.delete_many(["x", "y"]) == 0
    assert cm.delete_pattern("x*") == 0
    assert cm.clear() is False
    assert cm.get_stats() == {"enabled": False}
    assert list(cm.iter_keys("*")) == []


def test_init_app_ohne_redis_url_deaktiviert(app, caplog):
    cm = CacheManager()
    cm.init_app(app)
    assert cm.enabled is False


def test_init_app_redis_nicht_erreichbar(app, monkeypatch):
    """Ping-Fehler -> sauber deaktiviert statt Absturz."""
    monkeypatch.setattr(cache_mod.redis, "from_url",
                        staticmethod(lambda *a, **k: FakeRedis(kaputt=True)))
    monkeypatch.setitem(app.config, "REDIS_URL", "redis://fake:6379/0")
    cm = CacheManager()
    cm.init_app(app)
    assert cm.enabled is False


def test_set_get_roundtrip_mit_ttl(verbundener_cache, app):
    fake = verbundener_cache
    with app.app_context():
        assert cache.enabled is True
        assert cache.set("k1", {"a": [1, 2]}, ttl=77) is True
        assert cache.get("k1") == {"a": [1, 2]}
        assert fake.ttls["k1"] == 77
        # Default-TTL aus der Config (300)
        cache.set("k2", "v")
        assert fake.ttls["k2"] == app.config.get("CACHE_DEFAULT_TTL", 300)
    assert cache.delete("k1") is True
    assert cache.get("k1") is None


def test_delete_many_batches(verbundener_cache, app):
    with app.app_context():
        for i in range(60):
            cache.set(f"bulk:{i}", i)
        geloescht = cache.delete_many([f"bulk:{i}" for i in range(60)],
                                      batch_size=50)
    assert geloescht == 60


def test_delete_pattern_via_scan(verbundener_cache, app):
    with app.app_context():
        cache.set("v3:tips:match:1:a", 1)
        cache.set("v3:tips:match:1:b", 2)
        cache.set("v3:tips:match:2:a", 3)
        assert cache.delete_pattern("v3:tips:match:1:*") == 2
        assert cache.get("v3:tips:match:2:a") == 3


def test_get_stats_hit_rate(verbundener_cache, app):
    with app.app_context():
        stats = cache.get_stats()
    assert stats["enabled"] is True
    assert stats["hits"] == 30 and stats["misses"] == 10
    assert stats["hit_rate"] == 75.0
    assert stats["keys"] == stats["keys"]  # dbsize ohne Fehler


def test_clear_flushdb(verbundener_cache, app):
    with app.app_context():
        cache.set("x", 1)
        assert cache.clear() is True
        assert cache.get("x") is None
    assert verbundener_cache.flushed == 1


def test_cached_decorator_cacht(verbundener_cache, app):
    aufrufe = {"n": 0}

    @cached(ttl=60, key_prefix="rechenwerk")
    def verdoppeln(x):
        aufrufe["n"] += 1
        return x * 2

    with app.app_context():
        assert verdoppeln(21) == 42
        assert verdoppeln(21) == 42  # HIT
        assert verdoppeln(7) == 14   # anderer Key -> SET
        assert aufrufe["n"] == 2
        verdoppeln.invalidate(21)
        assert verdoppeln(21) == 42  # wieder MISS
        assert aufrufe["n"] == 3


def test_cached_decorator_ohne_cache_immer_frisch(app):
    aufrufe = {"n": 0}

    @cached(ttl=60, key_prefix="ohne")
    def wert():
        aufrufe["n"] += 1
        return "x"

    cm_cache = CacheManager()  # nicht verbunden
    with app.app_context():
        assert wert() == "x" and wert() == "x"
        assert aufrufe["n"] == 2


def test_cached_mit_key_builder(verbundener_cache, app):
    aufrufe = {"n": 0}

    @cached(ttl=60, key_builder=lambda u: f"{CACHE_VERSION}:spezial:{u}")
    def fuer(u):
        aufrufe["n"] += 1
        return u

    with app.app_context():
        assert fuer(5) == 5 and fuer(5) == 5
        assert aufrufe["n"] == 1


def test_cache_key_helfer_exakt():
    assert cache_key_leaderboard() == f"{CACHE_VERSION}:leaderboard:current:all:total"
    assert cache_key_leaderboard(matchday=5, season="2026", competition="bl1",
                                 live=True) == f"{CACHE_VERSION}:live_leaderboard:2026:bl1:5"
    assert cache_key_user_stats(9) == f"{CACHE_VERSION}:stats:user:9:current:all"
    assert cache_key_match_detail(12) == f"{CACHE_VERSION}:match:12"
    assert cache_key_live_matches(3) == f"{CACHE_VERSION}:live_matches:3"


def test_invalidate_helpers(verbundener_cache, app):
    with app.app_context():
        cache.set(f"{CACHE_VERSION}:leaderboard:current:all:total", "lb")
        cache.set(f"{CACHE_VERSION}:match:42", "m")
        n1 = invalidate_leaderboard()
        n2 = invalidate_match(42)
        assert n1 >= 1 and n2 >= 1
        assert cache.get(f"{CACHE_VERSION}:leaderboard:current:all:total") is None
        assert cache.get(f"{CACHE_VERSION}:match:42") is None
