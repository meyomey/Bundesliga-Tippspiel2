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
