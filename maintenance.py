"""Wartungsfunktionen fuer Admin/Netcup-Betrieb.

Enthaelt bewusst nur Funktionen ohne neue Abhaengigkeiten, damit sie auch im
Shared-Hosting/Vendor-Setup laufen.
"""
import os
import re
import sys
import importlib.util
from urllib.parse import urlparse

import requests
from flask import current_app

from extensions import db
from models import Team, Match, Prediction, Comment, User, SeasonArchive
from scoring import recalculate_all_points, get_setting, is_bot_user
from badges import check_and_award_badges
from stats import evaluate_special_predictions
from scoring import recompute_matchday_winners
from sync import update_known_team_logos


LOGO_DIR = "team_logos"


def _safe_slug(value: str) -> str:
    value = (value or "team").lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "team"


def _guess_ext(url: str, content_type: str = "") -> str:
    path = urlparse(url or "").path.lower()
    for ext in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    if "svg" in content_type:
        return ".svg"
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    return ".png"


def _fallback_svg(team: Team) -> bytes:
    short = (team.short_name or team.name or "?")[:4]
    color = team.color or "#14b8a6"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-generated="wulmstoerper-fallback">
  <rect width="128" height="128" rx="24" fill="{color}"/>
  <circle cx="64" cy="64" r="48" fill="white" opacity="0.18"/>
  <text x="64" y="72" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="800" fill="white">{short}</text>
</svg>'''
    return svg.encode("utf-8")


def _is_generated_fallback(path: str) -> bool:
    """Erkennt generierte oder defekte Platzhalter-Logos.

    Neben unseren markierten Fallbacks werden auch leere/kaputte SVG-Dateien
    erkannt (z.B. ``<svg ...></svg>`` mit nur wenigen Bytes). Solche Dateien
    duerfen bei der Logo-Wartung nicht als gueltige lokale Logos uebersprungen
    werden.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            raw = f.read(800)
        head = raw.decode("utf-8", errors="ignore").strip().lower()
        if size < 100 and head.startswith("<svg") and "</svg>" in head and "<image" not in head and "<path" not in head:
            return True
        return (
            "wulmstoerper-fallback" in head
            or ('<rect width="128" height="128"' in head and '<text x="64" y="72"' in head)
        )
    except OSError:
        return False


def _logo_source_map():
    """Bekannte externe Quell-URLs, auch wenn Team.logo schon lokal ist."""
    try:
        from sync import BUNDESLIGA_TEAMS, KNOWN_TEAM_LOGO_FIXES
        data = {short: logo for _name, short, _ext, logo, _color in BUNDESLIGA_TEAMS}
        data.update({_name: logo for _name, short, _ext, logo, _color in BUNDESLIGA_TEAMS})
        data.update(KNOWN_TEAM_LOGO_FIXES)
        # Namen neuer/haeufiger Aufsteiger als Fallback, falls Kuerzel abweicht.
        data.update({
            "SC Paderborn 07": KNOWN_TEAM_LOGO_FIXES.get("SCP"),
            "FC Schalke 04": KNOWN_TEAM_LOGO_FIXES.get("S04"),
            "SV 07 Elversberg": KNOWN_TEAM_LOGO_FIXES.get("ELV"),
            "Bayer 04 Leverkusen": KNOWN_TEAM_LOGO_FIXES.get("B04"),
            "FC Bayern München": KNOWN_TEAM_LOGO_FIXES.get("FCB"),
            "Borussia Dortmund": KNOWN_TEAM_LOGO_FIXES.get("BVB"),
            "RB Leipzig": KNOWN_TEAM_LOGO_FIXES.get("RBL"),
        })
        return data
    except Exception:
        return {}


def _valid_logo_response(resp) -> bool:
    if not getattr(resp, "ok", False) or not getattr(resp, "content", None):
        return False
    ctype = (resp.headers.get("content-type", "") or "").lower()
    if any(x in ctype for x in ("image/", "svg", "png", "jpeg", "webp")):
        return True
    return resp.content.lstrip().startswith(b"<svg")


def ensure_local_team_logos(force: bool = False) -> dict:
    """Laedt Teamlogos nach static/team_logos und setzt Team.logo auf lokale URLs.

    Bereits lokale Logos werden uebersprungen, ausser ``force=True``.
    Falls ein Download fehlschlaegt, wird ein schlichtes Fallback-SVG erzeugt.
    """
    update_known_team_logos()
    static_dir = current_app.static_folder
    target_dir = os.path.join(static_dir, LOGO_DIR)
    os.makedirs(target_dir, exist_ok=True)

    result = {"updated": 0, "downloaded": 0, "fallback": 0, "skipped": 0, "failed": 0, "replaced_fallback": 0}
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 Wulmstoerper-Tipprunde/1.0"}
    source_map = _logo_source_map()

    for team in Team.query.order_by(Team.name).all():
        old_logo = team.logo or ""
        slug = _safe_slug(team.short_name or team.name)
        source_url = (
            source_map.get(team.short_name)
            or source_map.get((team.short_name or "").upper())
            or source_map.get(team.name)
            or source_map.get(_safe_slug(team.name).upper())
            or old_logo
        )

        if old_logo.startswith("/static/team_logos/") and not force:
            local_path = os.path.join(static_dir, old_logo.replace("/static/", "", 1))
            if os.path.exists(local_path) and not _is_generated_fallback(local_path):
                result["skipped"] += 1
                continue
            if os.path.exists(local_path) and _is_generated_fallback(local_path):
                result["replaced_fallback"] += 1

        data = None
        ext = ".svg"
        if source_url.startswith("http://") or source_url.startswith("https://"):
            try:
                resp = session.get(source_url, headers=headers, timeout=12)
                if _valid_logo_response(resp):
                    ctype = resp.headers.get("content-type", "")
                    ext = _guess_ext(source_url, ctype)
                    data = resp.content
                    result["downloaded"] += 1
            except Exception as e:
                current_app.logger.warning(f"Logo-Download fehlgeschlagen fuer {team.name}: {e}")

        if data is None:
            data = _fallback_svg(team)
            ext = ".svg"
            result["fallback"] += 1

        filename = f"{slug}{ext}"
        rel_url = f"/static/{LOGO_DIR}/{filename}"
        abs_path = os.path.join(target_dir, filename)
        try:
            with open(abs_path, "wb") as f:
                f.write(data)
            if team.logo != rel_url:
                team.logo = rel_url
                result["updated"] += 1
        except OSError as e:
            current_app.logger.warning(f"Logo konnte nicht gespeichert werden fuer {team.name}: {e}")
            result["failed"] += 1

    db.session.commit()
    return result


def _dir_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        testfile = os.path.join(path, ".write_test")
        with open(testfile, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(testfile)
        return True
    except Exception:
        return False


def _pkg_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def run_health_check() -> dict:
    """Admin-Health-Check fuer Wartungscenter und Netcup-Deployment."""
    teams_total = Team.query.count()
    remote_logos = Team.query.filter(Team.logo.like("http%"), Team.logo.isnot(None)).count()
    missing_logos = Team.query.filter((Team.logo.is_(None)) | (Team.logo == "")).count()
    matches = Match.query.count()
    predictions = Prediction.query.count()
    comments = Comment.query.count()

    app_root = current_app.root_path
    vendor_dir = os.path.join(app_root, "vendor")
    uploads_dir = current_app.config.get("UPLOAD_FOLDER", os.path.join(app_root, "static", "uploads"))
    logo_dir = os.path.join(current_app.static_folder, LOGO_DIR)
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    sqlite_path = None
    sqlite_exists = None
    sqlite_writable = None
    if db_uri.startswith("sqlite:///"):
        raw = db_uri.replace("sqlite:///", "", 1)
        sqlite_path = raw if os.path.isabs(raw) else os.path.join(app_root, raw)
        sqlite_exists = os.path.exists(sqlite_path)
        sqlite_writable = _dir_writable(os.path.dirname(sqlite_path))

    public_base_url = get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", ""))
    telegram_secret = get_setting("telegram_webhook_secret", current_app.config.get("TELEGRAM_WEBHOOK_SECRET", ""))
    secret_is_default = current_app.config.get("SECRET_KEY") == current_app.config.get("DEFAULT_SECRET_KEY")
    admin_default_login_active = any(
        admin.check_password("admin123")
        for admin in User.query.filter_by(is_admin=True).all()
    )

    packages = {
        "flask": _pkg_available("flask"),
        "sqlalchemy": _pkg_available("sqlalchemy"),
        "PIL": _pkg_available("PIL"),
        "reportlab": _pkg_available("reportlab"),
        "requests": _pkg_available("requests"),
        "redis": _pkg_available("redis"),
        "flask_limiter": _pkg_available("flask_limiter"),
    }

    checks = {
        "secret_secure": not secret_is_default,
        "admin_password_secure": not admin_default_login_active,
        "public_base_url": bool(public_base_url),
        "telegram_secret": bool(telegram_secret),
        "vendor_exists": os.path.isdir(vendor_dir),
        "uploads_writable": _dir_writable(uploads_dir),
        "logos_writable": _dir_writable(logo_dir),
        "sqlite_exists": sqlite_exists,
        "sqlite_writable": sqlite_writable,
    }
    warnings = []
    if secret_is_default:
        warnings.append("SECRET_KEY nutzt noch den Defaultwert.")
    if admin_default_login_active:
        warnings.append("Mindestens ein Admin-Konto nutzt noch das Passwort admin123.")
    if not public_base_url:
        warnings.append("PUBLIC_BASE_URL / öffentliche Basis-URL ist nicht gesetzt.")
    if not telegram_secret:
        warnings.append("Telegram Webhook Secret ist nicht gesetzt.")
    if not checks["uploads_writable"]:
        warnings.append("Upload-Verzeichnis ist nicht beschreibbar.")
    if not checks["logos_writable"]:
        warnings.append("Logo-Verzeichnis ist nicht beschreibbar.")

    # Cron-Heartbeat + Backups
    from cron_heartbeat import get_cron_status, cron_any_never_or_error
    from backup import list_backups
    from main_cron_routes import _cron_secret
    cron_rows = get_cron_status()
    backups = list_backups()
    cron_secret = _cron_secret()
    if cron_any_never_or_error(cron_rows):
        warnings.append("Cron-Aufgabe überfällig oder noch nie gelaufen - bitte prüfen (Plesk-Cron + Backups).")
    if not cron_secret:
        warnings.append("Cron-HTTP-Zugang ist ohne Secret deaktiviert (CRON_SECRET in .env fehlt) - die Plesk-Cron-Aufgaben können so nichts ausführen.")
    cron_base_url = (get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", ""))
                     or "").rstrip("/")

    return {
        "teams_total": teams_total,
        "remote_logos": remote_logos,
        "missing_logos": missing_logos,
        "matches": matches,
        "predictions": predictions,
        "comments": comments,
        "db_ok": True,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "python_prefix": getattr(sys, "prefix", ""),
        "app_root": app_root,
        "vendor_dir": vendor_dir,
        "uploads_dir": uploads_dir,
        "logo_dir": logo_dir,
        "db_uri": db_uri,
        "sqlite_path": sqlite_path,
        "packages": packages,
        "checks": checks,
        "warnings": warnings,
        "cron": cron_rows,
        "backups": backups,
        "backups_total": len(backups),
        "cron_secret_set": bool(cron_secret),
        "cron_base_url": cron_base_url,
    }



def remove_bots_from_season_archive() -> dict:
    """Entfernt KI-Bots aus der historischen Ewigen-Tabelle-Archivierung."""
    bot_users = [u for u in User.query.all() if is_bot_user(u)]
    bot_ids = [u.id for u in bot_users]
    if not bot_ids:
        return {"ok": True, "removed": 0, "bots": [], "message": "Keine Bot-Konten im Archiv gefunden"}
    removed = SeasonArchive.query.filter(SeasonArchive.user_id.in_(bot_ids)).delete(synchronize_session=False)
    db.session.commit()
    return {
        "ok": True,
        "removed": removed or 0,
        "bots": [u.username for u in bot_users],
        "message": f"{removed or 0} Archiv-Eintrag/Eintraege von KI-Bots entfernt",
    }

def run_repair_tasks(task: str) -> dict:
    """Fuehrt einzelne Wartungsaufgaben aus."""
    if task == "logos":
        return ensure_local_team_logos(force=False)
    if task == "logos_force":
        return ensure_local_team_logos(force=True)
    if task == "points":
        recalculate_all_points()
        return {"ok": True, "message": "Punkte neu berechnet"}
    if task == "badges":
        check_and_award_badges()
        return {"ok": True, "message": "Badges neu geprueft"}
    if task == "specials":
        evaluate_special_predictions()
        return {"ok": True, "message": "Sondertipps neu ausgewertet"}
    if task == "matchday_winners":
        recompute_matchday_winners()
        return {"ok": True, "message": "Spieltagsieger neu berechnet"}
    if task == "archive_bots":
        return remove_bots_from_season_archive()
    raise ValueError(f"Unbekannte Wartungsaufgabe: {task}")
