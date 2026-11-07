"""Tests fuer Cache-Monitor-Helfer."""
from cache_monitor_routes import _admin_cache_view, _admin_cache_flush_pattern, _admin_cache_delete_key


class FakeRedis:
    def __init__(self):
        self.deleted = []
    def info(self):
        return {
            'redis_version': '7', 'uptime_in_seconds': 86400,
            'used_memory_human': '1M', 'keyspace_hits': 8, 'keyspace_misses': 2,
            'connected_clients': 1,
        }
    def dbsize(self):
        return 2
    def scan_iter(self, match='*', count=200):
        yield 'leaderboard:a'
        yield 'stats:b'
    def ttl(self, key):
        return 60
    def delete(self, *keys):
        self.deleted.extend(keys)
        return len(keys)


def test_cache_monitor_view(monkeypatch, app):
    fake = FakeRedis()
    monkeypatch.setattr('cache_monitor_routes._get_redis', lambda: (fake, None))
    with app.test_request_context('/admin/cache'):
        html = _admin_cache_view()
        assert 'leaderboard:a' in html


def test_cache_monitor_flush_pattern(monkeypatch, app):
    fake = FakeRedis()
    monkeypatch.setattr('cache_monitor_routes._get_redis', lambda: (fake, None))
    with app.test_request_context('/admin/cache/flush-pattern', method='POST', data={'pattern': 'leaderboard:*'}):
        resp = _admin_cache_flush_pattern()
        assert resp.status_code == 302
        assert fake.deleted


def test_cache_monitor_delete_key(monkeypatch, app):
    fake = FakeRedis()
    monkeypatch.setattr('cache_monitor_routes._get_redis', lambda: (fake, None))
    with app.test_request_context('/admin/cache/delete-key', method='POST', data={'key': 'abc'}):
        resp = _admin_cache_delete_key()
        assert resp.status_code == 302
        assert fake.deleted == ['abc']


def test_cache_monitor_ohne_redis_zeigt_memory_info_175(app, monkeypatch):
    """(175) Ohne REDIS_URL (Netcup-Webhosting: kein Redis-Dienst) zeigt der
    Monitor eine INFO-Karte mit Memory-Cache-Statistik und Loesch-Knopf —
    kein rotes Fehl-❌ mehr (frueher riet _get_redis localhost an)."""
    # app ist session-scoped: test_cache.py setzt REDIS_URL auf localhost —
    # hier explizit zuruecksetzen (funktionslokal, wie in test_rangliste_tempo).
    monkeypatch.setitem(app.config, "REDIS_URL", None)
    from cache_monitor_routes import _get_redis, NICHT_KONFIGURIERT
    with app.test_request_context('/admin/cache'):
        r, err = _get_redis()
        assert r is None and err == NICHT_KONFIGURIERT
        html = _admin_cache_view()
    assert 'nicht eingerichtet' in html
    assert 'Memory-Cache leeren' in html
    assert '❌' not in html


def test_cache_monitor_redis_fehler_bleibt_rot_175(app, monkeypatch):
    """(175) Ist REDIS_URL gesetzt aber unerreichbar, bleibt es eine echte
    Fehlerkarte (rot) — davon getrennt vom nicht-eingerichtet-Fall."""
    monkeypatch.setattr('cache_monitor_routes._get_redis',
                        lambda: (None, 'Error 111 connecting to localhost:6379. Connection refused.'))
    with app.test_request_context('/admin/cache'):
        html = _admin_cache_view()
    assert '❌' in html
    assert 'Connection refused' in html
    assert 'Memory-Cache leeren' not in html


def test_cache_monitor_memory_flush_175(app, monkeypatch):
    """(175) Der Memory-Flush-Knopf leert den eingebauten Cache (clear())."""
    import cache_monitor_routes
    from cache import cache as c
    aufgerufen = []
    monkeypatch.setattr(c, 'clear', lambda: aufgerufen.append(1) or True)
    with app.test_request_context('/admin/cache/flush-memory', method='POST'):
        resp = cache_monitor_routes._admin_cache_flush_memory()
    assert resp.status_code == 302
    assert aufgerufen == [1]
