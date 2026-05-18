"""Flask Extensions Singleton (vermeidet Circular Imports)."""
import os

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from cache import CacheManager

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
cache = CacheManager()
csrf = CSRFProtect()


# ============================================================
# 🔒 Rate Limiter – mit graceful Fallback
# ============================================================
# Auf Shared-Hosting (z.B. Netcup ohne pip) ist Flask-Limiter
# manchmal nicht installiert. In dem Fall liefern wir einen
# No-Op-Limiter, damit die App trotzdem startet (statt eines
# 500-Errors beim Import).
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    _limiter_storage = os.environ.get("REDIS_URL", "memory://")
    if _limiter_storage and not _limiter_storage.startswith(("redis://", "memory://")):
        _limiter_storage = "memory://"

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[],
        storage_uri=_limiter_storage,
    )
    LIMITER_AVAILABLE = True
except ImportError:
    import logging
    logging.warning(
        "⚠️ Flask-Limiter nicht installiert – Rate-Limiting deaktiviert. "
        "Für Produktion: 'pip install Flask-Limiter==3.5.1' bzw. "
        "build_vendor.bat neu ausführen."
    )

    class _NoopLimiter:
        """Fallback wenn Flask-Limiter fehlt – tut nichts, lässt alles durch."""

        def init_app(self, app):
            pass

        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator

        def exempt(self, f):
            return f

        def __getattr__(self, name):
            # Beliebige andere Aufrufe (z.B. .check, .reset) ignorieren
            def _noop(*a, **kw):
                return None
            return _noop

    limiter = _NoopLimiter()
    LIMITER_AVAILABLE = False


login_manager.login_view = "auth.login"
login_manager.login_message = "Bitte melde dich an, um diese Seite zu sehen."
login_manager.login_message_category = "info"
