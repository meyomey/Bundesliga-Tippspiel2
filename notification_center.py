"""Zentrale Benachrichtigungslogik fuer Reminder.

Buendelt E-Mail, Push, Telegram und WhatsApp. Die einzelnen Integrationen
existierten bereits; dieses Modul entscheidet nur noch anhand der User-
Praeferenzen, welche Kanaele fuer ein konkretes Spiel genutzt werden.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from extensions import db
from models import Match, NotificationLog, Prediction, User
from competition_helpers import filter_matches_for_active_competition


def _truthy(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "nein", "off", "")



def _already_sent(user, match, channel, kind="match_reminder"):
    return NotificationLog.query.filter_by(
        user_id=user.id, match_id=match.id, channel=channel, kind=kind
    ).first() is not None


def _mark_sent(user, match, channel, kind="match_reminder"):
    if _already_sent(user, match, channel, kind):
        return
    db.session.add(NotificationLog(
        user_id=user.id, match_id=match.id, channel=channel, kind=kind
    ))
    try:
        db.session.flush()
    except Exception:
        db.session.rollback()

def user_wants_match_reminder(user, match) -> bool:
    """Prueft allgemeine Reminder-Bedingungen fuer einen User."""
    if not user or user.email.endswith("@bot.local"):
        return False
    if Prediction.query.filter_by(user_id=user.id, match_id=match.id).first():
        return False
    if not _truthy(getattr(user, "notify_enabled", True), True):
        return False
    if _truthy(getattr(user, "notify_only_favorite", False), False):
        fav = getattr(user, "favorite_team_id", None)
        if not fav or fav not in (match.home_team_id, match.away_team_id):
            return False
    return True


def reminder_message(match, plain=True):
    ko = match.kickoff.strftime("%d.%m. %H:%M") if match.kickoff else "?"
    teams = f"{match.home_team.name} – {match.away_team.name}"
    if plain:
        return f"⚽ Tipp-Erinnerung: {teams} startet um {ko}. Du hast noch nicht getippt."
    return f"⚽ *Tipp-Erinnerung*\n\n{teams} startet um *{ko}*.\nDu hast noch nicht getippt."


def send_user_notification(user, match, channels=None) -> dict:
    """Sendet eine Reminder-Nachricht an einen User ueber konfigurierte Kanaele."""
    channels = channels or ["email", "push", "telegram", "whatsapp"]
    result = {"email": False, "push": False, "telegram": False, "whatsapp": False}

    if not user_wants_match_reminder(user, match):
        return result

    # E-Mail
    if "email" in channels and _truthy(getattr(user, "notify_email", True), True) and not _already_sent(user, match, "email"):
        try:
            from mail_helpers import send_email
            from scoring import get_setting
            base = get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", "")).rstrip("/")
            match_url = (base + f"/match/{match.id}") if base else f"/match/{match.id}"
            result["email"] = send_email(
                f"⚽ Tipp-Erinnerung: {match.home_team.short_name} – {match.away_team.short_name}",
                [user.email],
                f"Hallo {user.username},\n\n{reminder_message(match)}\n\nJetzt tippen: {match_url}\n",
            )
            if result["email"]:
                _mark_sent(user, match, "email")
        except Exception as e:
            current_app.logger.warning(f"Notification E-Mail fehlgeschlagen fuer User {user.id}: {e}")

    # Push
    if "push" in channels and _truthy(getattr(user, "notify_push", True), True) and user.push_subscription and not _already_sent(user, match, "push"):
        try:
            from push_routes import _send_push_to_users
            sent, _failed = _send_push_to_users([user], {
                "title": "⚽ Tipp-Erinnerung",
                "body": reminder_message(match),
                "url": f"/match/{match.id}",
                "tag": f"reminder-{match.id}-{user.id}",
            })
            result["push"] = sent > 0
            if result["push"]:
                _mark_sent(user, match, "push")
        except Exception as e:
            current_app.logger.warning(f"Notification Push fehlgeschlagen fuer User {user.id}: {e}")

    # Telegram
    if "telegram" in channels and _truthy(getattr(user, "notify_telegram", True), True) and not _already_sent(user, match, "telegram"):
        try:
            from telegram_bot import notify_user_telegram
            result["telegram"] = notify_user_telegram(user, reminder_message(match, plain=True))
            if result["telegram"]:
                _mark_sent(user, match, "telegram")
        except Exception as e:
            current_app.logger.warning(f"Notification Telegram fehlgeschlagen fuer User {user.id}: {e}")

    # WhatsApp
    if "whatsapp" in channels and _truthy(getattr(user, "notify_whatsapp", True), True) and not _already_sent(user, match, "whatsapp"):
        if user.whatsapp_phone and user.whatsapp_apikey:
            try:
                from whatsapp import send_whatsapp_message
                result["whatsapp"] = send_whatsapp_message(
                    user.whatsapp_phone, user.whatsapp_apikey, reminder_message(match, plain=False)
                )
                if result["whatsapp"]:
                    _mark_sent(user, match, "whatsapp")
            except Exception as e:
                current_app.logger.warning(f"Notification WhatsApp fehlgeschlagen fuer User {user.id}: {e}")

    return result


def send_match_reminders(match, channels=None) -> dict:
    """Sendet Reminder fuer ein Spiel an alle berechtigten User."""
    summary = {"users": 0, "email": 0, "push": 0, "telegram": 0, "whatsapp": 0}
    users = User.query.filter(~User.email.like("%@bot.local")).all()
    for user in users:
        res = send_user_notification(user, match, channels=channels)
        if any(res.values()):
            summary["users"] += 1
        for k, v in res.items():
            if v:
                summary[k] += 1
    return summary


def upcoming_reminder_matches(default_hours=1):
    """Findet Spiele, die ins Reminder-Zeitfenster fallen."""
    now = datetime.now(timezone.utc)
    max_hours = 24
    q = Match.query.filter(
        Match.status == "scheduled",
        Match.kickoff > now,
        Match.kickoff <= now + timedelta(hours=max_hours),
    )
    q = filter_matches_for_active_competition(q)
    matches = q.order_by(Match.kickoff.asc()).all()
    result = []
    for match in matches:
        # Es reicht, wenn mindestens ein User sein individuelles Fenster erreicht hat.
        for user in User.query.filter(~User.email.like("%@bot.local")).all():
            hours = getattr(user, "notify_hours_before", None) or default_hours
            try:
                hours = max(0, min(24, int(hours)))
            except Exception:
                hours = default_hours
            if now <= match.kickoff <= now + timedelta(hours=hours, minutes=5):
                result.append(match)
                break
    return result



def _next_open_match_for_user(user):
    """Naechstes offenes Spiel ohne Tipp fuer Test-/Preview-Zwecke."""
    now = datetime.now(timezone.utc)
    q = Match.query.filter(Match.status == "scheduled", Match.kickoff > now)
    q = filter_matches_for_active_competition(q)
    for match in q.order_by(Match.kickoff.asc()).all():
        if not Prediction.query.filter_by(user_id=user.id, match_id=match.id).first():
            return match
    return None


def send_test_missing_tip_notification(user, channels=None) -> dict:
    """Sendet eine Test-Benachrichtigung fuer fehlende Tipps an genau einen User.

    Die Testfunktion schreibt bewusst keinen NotificationLog-Eintrag, damit echte
    Erinnerungen spaeter nicht blockiert werden. Sie nutzt die aktivierten Kanaele
    des Users und prueft nur, ob der jeweilige Kanal grundsaetzlich konfiguriert ist.
    """
    channels = channels or ["email", "push", "telegram", "whatsapp"]
    result = {"email": False, "push": False, "telegram": False, "whatsapp": False}
    if not user:
        return result

    match = _next_open_match_for_user(user)
    base = ""
    try:
        from scoring import get_setting
        base = get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", "")).rstrip("/")
    except Exception:
        base = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")

    if match:
        teams = f"{match.home_team.name} – {match.away_team.name}"
        ko = match.kickoff.strftime("%d.%m. %H:%M") if match.kickoff else "?"
        path = f"/match/{match.id}"
        text = (
            f"🧪 Test: Tipp-Erinnerung\n\n"
            f"Hallo {user.username},\n\n"
            f"so wuerde eine Erinnerung aussehen:\n"
            f"{teams} startet am {ko} Uhr. Du hast dafuer noch keinen Tipp abgegeben."
        )
    else:
        path = "/meine-offenen-tipps"
        text = (
            f"🧪 Test: Tipp-Erinnerung\n\n"
            f"Hallo {user.username},\n\n"
            f"so wuerde eine Erinnerung aussehen, wenn vor Anpfiff noch ein Tipp fehlt."
        )
    url = (base + path) if base else path
    text_with_link = f"{text}\n\nJetzt tippen: {url}"

    if "email" in channels and _truthy(getattr(user, "notify_email", True), True) and user.email:
        try:
            from mail_helpers import send_email
            result["email"] = send_email(
                "🧪 Test: Tipp-Erinnerung bei fehlendem Tipp",
                [user.email],
                text_with_link,
            )
        except Exception as e:
            current_app.logger.warning(f"Test-Reminder E-Mail fehlgeschlagen fuer User {user.id}: {e}")

    if "push" in channels and _truthy(getattr(user, "notify_push", True), True) and user.push_subscription:
        try:
            from push_routes import _send_push_to_users
            sent, _failed = _send_push_to_users([user], {
                "title": "🧪 Test: Tipp-Erinnerung",
                "body": "So wirst du bei fehlenden Tipps erinnert.",
                "url": path,
                "tag": f"test-reminder-{user.id}",
            })
            result["push"] = sent > 0
        except Exception as e:
            current_app.logger.warning(f"Test-Reminder Push fehlgeschlagen fuer User {user.id}: {e}")

    if "telegram" in channels and _truthy(getattr(user, "notify_telegram", True), True):
        try:
            from telegram_bot import notify_user_telegram
            result["telegram"] = notify_user_telegram(user, text_with_link)
        except Exception as e:
            current_app.logger.warning(f"Test-Reminder Telegram fehlgeschlagen fuer User {user.id}: {e}")

    if "whatsapp" in channels and _truthy(getattr(user, "notify_whatsapp", True), True):
        if user.whatsapp_phone and user.whatsapp_apikey:
            try:
                from whatsapp import send_whatsapp_message
                result["whatsapp"] = send_whatsapp_message(user.whatsapp_phone, user.whatsapp_apikey, text_with_link)
            except Exception as e:
                current_app.logger.warning(f"Test-Reminder WhatsApp fehlgeschlagen fuer User {user.id}: {e}")

    return result

def run_reminder_cycle(channels=None) -> dict:
    """Kompletter Reminder-Lauf fuer Scheduler/Cron."""
    total = {"matches": 0, "users": 0, "email": 0, "push": 0, "telegram": 0, "whatsapp": 0, "enabled": True}
    try:
        from scoring import get_setting
        enabled = get_setting("reminders_enabled", True)
        if not _truthy(enabled, True):
            total["enabled"] = False
            return total
    except Exception:
        pass
    for match in upcoming_reminder_matches():
        total["matches"] += 1
        res = send_match_reminders(match, channels=channels)
        for k in ("users", "email", "push", "telegram", "whatsapp"):
            total[k] += res.get(k, 0)
    db.session.commit()
    return total
