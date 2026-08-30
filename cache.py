"""Redis-Caching fuer die Wulmstörper Tipprunde.

Design-Ziele:
- Redis optional: App laeuft ohne Redis unveraendert weiter.
- Keine blockierenden Redis-Operationen fuer Pattern-Loeschungen (SCAN statt KEYS).
- Zentrale Cache-Key-Helfer fuer Saison/Wettbewerb/Spieltag.
- Rueckwaertskompatibel: Bestehende Aufrufer koennen weiter `cache.get/set` nutzen.

Hinweis: Aktuell werden fuer einige interne Caches noch Python-Objekte/ORM-nahe
Strukturen per pickle serialisiert. Das ist nur fuer einen vertrauenswuerdigen,
nicht oeffentlich erreichbaren Redis gedacht. Langfristig sollten diese Werte in
kleine DTO-Dicts umgebaut werden.
"""
import pickle
from functools import wraps
from typing import Any, Optional, Callable, Iterable

from flask import current_app

try:
    import redis
except ImportError:  # pragma: no cover - wird im Shared Hosting ggf. genutzt
    redis = None


CACHE_VERSION = "v3"


class CacheManager:
    """Zentrale Cache-Verwaltung mit Redis- oder Dummy-Backend."""

    def __init__(self):
        self._redis: Optional[Any] = None
        self._enabled = False
        self._default_ttl = 300  # 5 Minuten

    def init_app(self, app):
        """Initialisiert Redis aus App-Config."""
        self._default_ttl = int(app.config.get("CACHE_DEFAULT_TTL", 300))
        if redis is None:
            app.logger.warning("⚠️ Das Python-Modul 'redis' ist nicht installiert. Cache ist deaktiviert.")
            self._redis = None
            self._enabled = False
            return

        redis_url = app.config.get("REDIS_URL")
        if redis_url:
            try:
                # Socket-Timeouts auf 1s, damit die App nicht haengt, wenn Redis aus ist
                self._redis = redis.from_url(
                    redis_url,
                    decode_responses=False,
                    socket_timeout=1,
                    socket_connect_timeout=1,
                )
                self._redis.ping()
                self._enabled = True
                app.logger.info("✅ Redis Cache verbunden")
            except Exception as e:
                app.logger.warning(f"⚠️ Redis nicht verfuegbar: {e}. Cache deaktiviert.")
                self._redis = None
                self._enabled = False
        else:
            app.logger.info("ℹ️ Kein REDIS_URL konfiguriert. Cache deaktiviert.")

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._redis)

    def get(self, key: str) -> Optional[Any]:
        """Holt Wert aus Cache."""
        if not self.enabled:
            return None
        try:
            data = self._redis.get(key)
            if data is not None:
                return pickle.loads(data)
        except Exception as e:
            try:
                current_app.logger.debug(f"Cache GET failed for {key}: {e}")
            except Exception:
                pass
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Speichert Wert im Cache."""
        if not self.enabled:
            return False
        try:
            ttl = int(ttl or self._default_ttl)
            serialized = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            self._redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            try:
                current_app.logger.debug(f"Cache SET failed for {key}: {e}")
            except Exception:
                pass
            return False

    def delete(self, key: str) -> bool:
        """Loescht einen Key."""
        if not self.enabled:
            return False
        try:
            return bool(self._redis.delete(key))
        except Exception:
            return False

    def delete_many(self, keys: Iterable[str], batch_size: int = 500) -> int:
        """Loescht mehrere Keys in Batches."""
        if not self.enabled:
            return 0
        deleted = 0
        batch = []
        for key in keys:
            batch.append(key)
            if len(batch) >= batch_size:
                try:
                    deleted += int(self._redis.delete(*batch) or 0)
                except Exception:
                    pass
                batch = []
        if batch:
            try:
                deleted += int(self._redis.delete(*batch) or 0)
            except Exception:
                pass
        return deleted

    def iter_keys(self, pattern: str = "*", count: int = 500):
        """Iterator ueber Keys via SCAN.

        Fallback auf KEYS nur fuer sehr alte/mocked Redis-Clients oder Tests.
        """
        if not self.enabled:
            return iter(())

        def _gen():
            try:
                yield from self._redis.scan_iter(match=pattern, count=count)
                return
            except Exception:
                # Fallback fuer Tests/alte Clients. In Produktion sollte scan_iter existieren.
                try:
                    for key in self._redis.keys(pattern):
                        yield key
                except Exception:
                    return
        return _gen()

    def delete_pattern(self, pattern: str) -> int:
        """Loescht alle Keys matching pattern, ohne Redis per KEYS zu blockieren."""
        if not self.enabled:
            return 0
        return self.delete_many(self.iter_keys(pattern))

    def clear(self) -> bool:
        """Leert den gesamten Cache."""
        if not self.enabled:
            return False
        try:
            self._redis.flushdb()
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        """Liefert Cache-Statistiken."""
        if not self.enabled:
            return {"enabled": False}
        try:
            info = self._redis.info()
            hits = int(info.get("keyspace_hits", 0) or 0)
            misses = int(info.get("keyspace_misses", 0) or 0)
            total = hits + misses
            return {
                "enabled": True,
                "keys": self._redis.dbsize(),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "hits": hits,
                "misses": misses,
                "hit_rate": round((hits / total) * 100, 1) if total else 0.0,
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}


# Globaler Cache-Manager
cache = CacheManager()


def _stringify_arg(value):
    if hasattr(value, "id"):
        return str(value.id)
    return str(value)


def cached(ttl: int = 300, key_prefix: str = None, key_builder: Callable = None):
    """Decorator fuer Funktions-Caching."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                func_name = f.__name__
                prefix = key_prefix or func_name
                arg_str = ":".join(_stringify_arg(a) for a in args if not callable(a))
                kwarg_str = ":".join(f"{k}={_stringify_arg(v)}" for k, v in sorted(kwargs.items()))
                parts = [CACHE_VERSION, prefix]
                if arg_str:
                    parts.append(arg_str)
                if kwarg_str:
                    parts.append(kwarg_str)
                cache_key = ":".join(parts)

            cached_value = cache.get(cache_key)
            if cached_value is not None:
                current_app.logger.debug(f"🎯 Cache HIT: {cache_key}")
                return cached_value

            result = f(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            current_app.logger.debug(f"💾 Cache SET: {cache_key}")
            return result

        wrapper.cache_key = lambda *a, **kw: key_builder(*a, **kw) if key_builder else f"{CACHE_VERSION}:{f.__name__}"
        wrapper.invalidate = lambda *a, **kw: cache.delete(wrapper.cache_key(*a, **kw))
        wrapper.invalidate_pattern = lambda pattern: cache.delete_pattern(pattern)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Cache-Key-Helfer
# ---------------------------------------------------------------------------
def cache_key_leaderboard(matchday: int = None, season: str = None, competition: str = None, live: bool = False) -> str:
    """Baut Cache-Key fuer Ranglisten."""
    prefix = "live_leaderboard" if live else "leaderboard"
    return f"{CACHE_VERSION}:{prefix}:{season or 'current'}:{competition or 'all'}:{matchday or 'total'}"


def cache_key_user_stats(user_id: int, season: str = None, competition: str = None, live: bool = False) -> str:
    prefix = "live_stats" if live else "stats"
    return f"{CACHE_VERSION}:{prefix}:user:{user_id}:{season or 'current'}:{competition or 'all'}"


def cache_key_match_detail(match_id: int) -> str:
    return f"{CACHE_VERSION}:match:{match_id}"


def cache_key_live_matches(competition_id=None) -> str:
    return f"{CACHE_VERSION}:live_matches:{competition_id or 'all'}"


# ---------------------------------------------------------------------------
# Domain-Invalidierung
# ---------------------------------------------------------------------------
def invalidate_leaderboard():
    """Invalidiert alle Ranglisten-/Statistik-Caches."""
    patterns = [
        "leaderboard:*", f"{CACHE_VERSION}:leaderboard:*",
        "live_leaderboard:*", f"{CACHE_VERSION}:live_leaderboard:*",
        "standings:*", f"{CACHE_VERSION}:standings:*",
        "stats:*", f"{CACHE_VERSION}:stats:*", f"{CACHE_VERSION}:live_stats:*",
    ]
    deleted = 0
    for pattern in patterns:
        deleted += cache.delete_pattern(pattern)
    try:
        current_app.logger.info(f"🗑️ Leaderboard-/Stats-Cache invalidiert ({deleted} Keys)")
    except Exception:
        pass
    return deleted


def invalidate_match(match_id: int):
    """Invalidiert Cache fuer ein bestimmtes Spiel inkl. Live- und Tipp-Views."""
    deleted = 0
    for key in (f"match:{match_id}", cache_key_match_detail(match_id)):
        deleted += int(bool(cache.delete(key)))
    for pattern in (f"tips:match:{match_id}:*", f"{CACHE_VERSION}:tips:match:{match_id}:*", "live_matches:*", f"{CACHE_VERSION}:live_matches:*"):
        deleted += cache.delete_pattern(pattern)
    return deleted


def invalidate_competition(competition_code_or_id=None):
    """Breite Invalidierung bei Saison-/Wettbewerbswechsel."""
    patterns = [
        "leaderboard:*", f"{CACHE_VERSION}:leaderboard:*",
        "live_leaderboard:*", f"{CACHE_VERSION}:live_leaderboard:*",
        "standings:*", f"{CACHE_VERSION}:standings:*",
        "stats:*", f"{CACHE_VERSION}:stats:*", f"{CACHE_VERSION}:live_stats:*",
        "live_matches:*", f"{CACHE_VERSION}:live_matches:*",
        "match:*", f"{CACHE_VERSION}:match:*",
    ]
    deleted = 0
    for pattern in patterns:
        deleted += cache.delete_pattern(pattern)
    return deleted
