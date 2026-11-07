"""Cache-Monitoring Routes für den Admin-Bereich."""
from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from audit_log import log_admin_action


# (175) Marker: REDIS_URL nicht gesetzt = Redis schlicht nicht eingerichtet
# (Netcup-Webhosting hat keinen Redis-Dienst) — das ist das VORGESEHENE Setup
# (Memory-Fallback, (94)) und kein Fehler: Monitor zeigt es als Info, nicht rot.
NICHT_KONFIGURIERT = "NICHT_KONFIGURIERT"


def _get_redis():
    # Kein localhost-Raten mehr (frueher: Default "redis://localhost:6379/0",
    # was auf Servern ohne Redis ewig rote Karten malte): ohne URL ist Redis
    # nicht eingerichtet — identische Semantik wie cache.py (init_app).
    redis_url = current_app.config.get("REDIS_URL")
    if not redis_url:
        return None, NICHT_KONFIGURIERT
    try:
        import redis as redis_lib
        r = redis_lib.from_url(redis_url, decode_responses=True, socket_timeout=2)
        r.ping()
        return r, None
    except Exception as e:
        return None, str(e)


def _admin_cache_view():
    r, error = _get_redis()
    redis_ok = r is not None
    nicht_konfiguriert = (error == NICHT_KONFIGURIERT)
    mem_stats = {}
    if nicht_konfiguriert:
        # (175) Memory-Fallback sichtbar machen: Eintraege/Backend des
        # eingebauten Cache (kein Redis noetig).
        try:
            from cache import cache as app_cache
            mem_stats = app_cache.get_stats()
        except Exception:
            mem_stats = {"enabled": False, "backend": "none", "keys": 0}
    stats = {}
    all_keys = []
    redis_info = {}
    if redis_ok:
        try:
            info = r.info()
            redis_info = {k: v for k, v in info.items() if k in (
                "redis_version", "uptime_in_seconds", "used_memory_human",
                "maxmemory_human", "connected_clients", "total_commands_processed",
                "keyspace_hits", "keyspace_misses", "role", "os", "tcp_port", "hz",
            )}
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            hit_rate = round(hits / total * 100, 1) if total > 0 else 0.0
            uptime_days = int(info.get("uptime_in_seconds", 0)) // 86400
            stats = {
                "hit_rate": hit_rate,
                "keyspace_hits": hits,
                "keyspace_misses": misses,
                "used_memory_human": info.get("used_memory_human", "–"),
                "total_keys": r.dbsize(),
                "uptime_days": uptime_days,
            }
            keys_raw = []
            try:
                for k in r.scan_iter(match="*", count=200):
                    keys_raw.append(k)
                    if len(keys_raw) >= 500:
                        break
            except Exception:
                keys_raw = r.keys("*")[:500]
            for k in sorted(keys_raw):
                ttl = r.ttl(k)
                all_keys.append({"name": k, "ttl": ttl})
        except Exception as e:
            redis_ok = False
            error = str(e)
    return render_template(
        "admin/cache.html", redis_ok=redis_ok, redis_error=error,
        nicht_konfiguriert=nicht_konfiguriert, mem_stats=mem_stats,
        stats=stats, all_keys=all_keys, redis_info=redis_info,
    )


def _admin_cache_flush_memory():
    """(175) Memory-Cache (Fallback ohne Redis) leeren."""
    try:
        from cache import cache as app_cache
        app_cache.clear()
        log_admin_action("cache_flush_memory", "cache", None,
                         "Memory-Cache geleert")
        flash("🧹 Memory-Cache geleert.", "success")
    except Exception as e:
        flash(f"❌ Fehler: {e}", "error")
    return redirect(url_for("admin.admin_cache"))


def _admin_cache_flush_all():
    r, error = _get_redis()
    if r:
        try:
            r.flushdb()
            log_admin_action("cache_flush_all", "cache", None, "Cache vollständig geleert")
            flash("💣 Cache vollständig geleert.", "success")
        except Exception as e:
            flash(f"❌ Fehler: {e}", "error")
    else:
        flash(f"❌ Redis nicht verfügbar: {error}", "error")
    return redirect(url_for("admin.admin_cache"))


def _admin_cache_flush_pattern():
    pattern = request.form.get("pattern", "").strip()
    if not pattern:
        flash("❌ Kein Muster angegeben.", "error")
        return redirect(url_for("admin.admin_cache"))
    r, error = _get_redis()
    if r:
        try:
            keys = []
            try:
                keys = list(r.scan_iter(match=pattern, count=500))
            except Exception:
                keys = r.keys(pattern)
            if keys:
                deleted = 0
                for i in range(0, len(keys), 500):
                    deleted += r.delete(*keys[i:i+500])
                log_admin_action("cache_flush_pattern", "cache", pattern, f"{deleted} Keys geloescht", {"pattern": pattern, "deleted": deleted})
                flash(f"🗑️ {deleted} Keys mit Muster '{pattern}' gelöscht.", "success")
            else:
                flash(f"ℹ️ Keine Keys mit Muster '{pattern}' gefunden.", "info")
        except Exception as e:
            flash(f"❌ Fehler: {e}", "error")
    else:
        flash(f"❌ Redis nicht verfügbar: {error}", "error")
    return redirect(url_for("admin.admin_cache"))


def _admin_cache_delete_key():
    key = request.form.get("key", "").strip()
    if not key:
        flash("❌ Kein Key angegeben.", "error")
        return redirect(url_for("admin.admin_cache"))
    r, error = _get_redis()
    if r:
        try:
            deleted = r.delete(key)
            if deleted:
                log_admin_action("cache_delete_key", "cache", key, f"Key '{key}' geloescht")
                flash(f"🗑️ Key '{key}' gelöscht.", "success")
            else:
                flash(f"ℹ️ Key '{key}' nicht gefunden.", "info")
        except Exception as e:
            flash(f"❌ Fehler: {e}", "error")
    else:
        flash(f"❌ Redis nicht verfügbar: {error}", "error")
    return redirect(url_for("admin.admin_cache"))
