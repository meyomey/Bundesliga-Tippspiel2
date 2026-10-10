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



WAVE_KINDS = {1: "match_reminder", 2: "match_reminder_w2"}


def reminder_second_wave_enabled() -> bool:
    """Zweite, fruehe Reminder-Welle an/aus (Admin-Schalter, Standard: an)."""
    try:
        from scoring import get_setting
        return _truthy(get_setting("reminders_second_wave_enabled", True), True)
    except Exception:
        return True


def reminder_lead_hours(user, wave: int = 1) -> int:
    """Effektive Vorlauf-Stunden fuer einen User (bzw. die zweite Welle).

    Welle 1: ohne globalen Override die persoenliche Profil-Einstellung
    (notify_hours_before); mit 'reminders_force_lead_hours' gilt der vom
    Spielleiter gesetzte Standard fuer ALLE (Profilwerte werden ignoriert).
    Welle 2: immer der globale Wert 'reminders_second_lead_hours'.
    """
    try:
        from scoring import get_setting, _truthy_setting
    except Exception:
        return 1 if wave == 1 else 24
    if wave == 2:
        raw = get_setting("reminders_second_lead_hours", 24)
        lo, hi = 1, 168
    else:
        force = _truthy_setting(get_setting("reminders_force_lead_hours", False), False)
        raw = None
        if not force and user is not None:
            raw = getattr(user, "notify_hours_before", None)
        if raw is None:
            raw = get_setting("reminders_lead_hours", 1)
        lo, hi = 0, 24
    try:
        val = int(raw)
    except (TypeError, ValueError):
        val = 1 if wave == 1 else 24
    return max(lo, min(hi, val))


def _window_hit(match, user, wave: int, now) -> bool:
    """Nur senden, wenn der Anpfiff innerhalb des Wellen-Vorlaufs liegt."""
    if match.kickoff is None:
        return False
    kickoff = match.kickoff
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    lead = reminder_lead_hours(user, wave)
    delta = (kickoff - now).total_seconds()
    return 0 <= delta <= lead * 3600 + 300  # +5 Min Toleranz (15-Minuten-Cron)


def _already_sent(user, match, channel, kind="match_reminder", *, sent_cache=None):
    """Prueft, ob an diesen Kanal fuer das Spiel schon gesendet wurde.

    ``sent_cache`` (Set aus Tupeln (user_id, match_id, channel, kind)) erlaubt
    Bulk-Aufrufen, ohne pro User/Kanal eine SQL-Query zu feuern.
    """
    if sent_cache is not None:
        return (user.id, match.id, channel, kind) in sent_cache
    return NotificationLog.query.filter_by(
        user_id=user.id, match_id=match.id, channel=channel, kind=kind
    ).first() is not None


def _mark_sent(user, match, channel, kind="match_reminder", *, sent_cache=None):
    if _already_sent(user, match, channel, kind, sent_cache=sent_cache):
        return
    db.session.add(NotificationLog(
        user_id=user.id, match_id=match.id, channel=channel, kind=kind
    ))
    if sent_cache is not None:
        # Bulk-Pfad: Cache sofort nachfuehren, Flush uebernimmt der Aufrufer
        # einmal am Ende (statt einem Flush pro User*Kanal).
        sent_cache.add((user.id, match.id, channel, kind))
        return
    try:
        db.session.flush()
    except Exception:
        db.session.rollback()

def user_wants_match_reminder(user, match, *, tipped_user_ids=None) -> bool:
    """Prueft allgemeine Reminder-Bedingungen fuer einen User.

    ``tipped_user_ids`` (Set von user_ids mit Tipp auf ``match``) vermeidet
    im Bulk-Modus eine Query pro User.
    """
    if not user or user.email.endswith("@bot.local"):
        return False
    if tipped_user_ids is not None:
        if user.id in tipped_user_ids:
            return False
    elif Prediction.query.filter_by(user_id=user.id, match_id=match.id).first():
        return False
    if not _truthy(getattr(user, "notify_enabled", True), True):
        return False
    if _truthy(getattr(user, "notify_only_favorite", False), False):
        fav = getattr(user, "favorite_team_id", None)
        if not fav or fav not in (match.home_team_id, match.away_team_id):
            return False
    return True


def _berlin_fmt(value, fmt="%d.%m. %H:%M"):
    """(109) Kickoff in deutscher Lokalzeit formatieren.

    Kickoffs liegen NAIV in UTC in der DB (API-UTC-Zeitstempel). Die UI
    rechnet ueber den de_local-Filter nach Europe/Berlin — die Benachrich-
    tigungen hatten das bisher vergessen und UTC angezeigt (Nutzerbefund:
    „13:30" statt 15:30 im Digest). Naive Werte werden wie in der UI als
    UTC behandelt; zoneinfo ist Python-3.9-Stdlib.
    """
    if not value:
        return "?"
    from datetime import timezone as _tz
    try:
        from zoneinfo import ZoneInfo
        if value.tzinfo is None:
            value = value.replace(tzinfo=_tz.utc)
        value = value.astimezone(ZoneInfo("Europe/Berlin"))
    except Exception:
        pass  # Notfall: roher Stempel (besser als Absturz im Versand)
    return value.strftime(fmt)


def reminder_message(match, plain=True):
    ko = _berlin_fmt(match.kickoff)
    teams = f"{match.home_team.name} – {match.away_team.name}"
    if plain:
        return f"⚽ Tipp-Erinnerung: {teams} startet um {ko}. Du hast noch nicht getippt."
    return f"⚽ *Tipp-Erinnerung*\n\n{teams} startet um *{ko}*.\nDu hast noch nicht getippt."


def send_user_notification(user, match, channels=None, *, tipped_user_ids=None,
                           sent_cache=None, email_base_url=None,
                           wave: int = 1, now=None, enforce_window: bool = False) -> dict:
    """Sendet eine Reminder-Nachricht an einen User ueber konfigurierte Kanaele.

    Optionale Prefetch-Parameter (``tipped_user_ids``, ``sent_cache``,
    ``email_base_url``) ersparen bei Bulk-Laeufen pro User mehrere SQL-Queries.
    """
    channels = channels or ["email", "push", "telegram", "whatsapp"]
    result = {"email": False, "push": False, "telegram": False, "whatsapp": False}
    kind = WAVE_KINDS.get(wave, WAVE_KINDS[1])

    if not user_wants_match_reminder(user, match, tipped_user_ids=tipped_user_ids):
        return result
    if enforce_window:
        # Automatik-Lauf: pro Welle nur im eigenen Zeitfenster senden;
        # manuelle Admin-Erinnerungen (Standard) verschicken dagegen immer.
        if now is None:
            now = datetime.now(timezone.utc)
        if not _window_hit(match, user, wave, now):
            return result

    # (100) Base-URL einmal vor allen Kanaelen berechnen — braucht E-Mail
    # UND jetzt auch der WhatsApp-/CallMeBot-Link.
    try:
        from scoring import get_setting
        _base = (email_base_url if email_base_url is not None
                 else get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", ""))).rstrip("/")
    except Exception:
        _base = ""
    match_url = (_base + f"/match/{match.id}") if _base else f"/match/{match.id}"

    # E-Mail
    if "email" in channels and _truthy(getattr(user, "notify_email", True), True) and not _already_sent(user, match, "email", kind, sent_cache=sent_cache):
        try:
            from mail_helpers import send_email

            result["email"] = send_email(
                f"⚽ Tipp-Erinnerung: {match.home_team.short_name} – {match.away_team.short_name}",
                [user.email],
                f"Hallo {user.username},\n\n{reminder_message(match)}\n\nJetzt tippen: {match_url}\n",
            )
            if result["email"]:
                _mark_sent(user, match, "email", kind, sent_cache=sent_cache)
        except Exception as e:
            current_app.logger.warning(f"Notification E-Mail fehlgeschlagen fuer User {user.id}: {e}")

    # Push
    if "push" in channels and _truthy(getattr(user, "notify_push", True), True) and user.push_subscription and not _already_sent(user, match, "push", kind, sent_cache=sent_cache):
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
                _mark_sent(user, match, "push", kind, sent_cache=sent_cache)
        except Exception as e:
            current_app.logger.warning(f"Notification Push fehlgeschlagen fuer User {user.id}: {e}")

    # Telegram
    if "telegram" in channels and _truthy(getattr(user, "notify_telegram", True), True) and not _already_sent(user, match, "telegram", kind, sent_cache=sent_cache):
        try:
            from telegram_bot import notify_user_telegram
            result["telegram"] = notify_user_telegram(user, reminder_message(match, plain=True))
            if result["telegram"]:
                _mark_sent(user, match, "telegram", kind, sent_cache=sent_cache)
        except Exception as e:
            current_app.logger.warning(f"Notification Telegram fehlgeschlagen fuer User {user.id}: {e}")

    # WhatsApp
    if "whatsapp" in channels and _truthy(getattr(user, "notify_whatsapp", True), True) and not _already_sent(user, match, "whatsapp", kind, sent_cache=sent_cache):
        if user.whatsapp_phone and user.whatsapp_apikey:
            try:
                from whatsapp import send_whatsapp_message
                # (100) CallMeBot-Nachricht enthielt bislang keinen Link
                wa_text = (reminder_message(match, plain=False)
                           + f"\n\n👉 Jetzt tippen: {match_url}")
                result["whatsapp"] = send_whatsapp_message(
                    user.whatsapp_phone, user.whatsapp_apikey, wa_text
                )
                if result["whatsapp"]:
                    _mark_sent(user, match, "whatsapp", kind, sent_cache=sent_cache)
            except Exception as e:
                current_app.logger.warning(f"Notification WhatsApp fehlgeschlagen fuer User {user.id}: {e}")

    return result


def send_match_reminders(match, channels=None, *, wave: int = 1,
                         now=None, enforce_window: bool = False) -> dict:
    """Sendet Reminder fuer ein Spiel an alle berechtigten User.

    Bulk-optimiert: Statt pro User/Kanal bis zu 6 Queries (Tipp vorhanden?
    schon gesendet? Base-URL?) werden Tipps, bisherige Versand-Logs und die
    App-Basis-URL je **einmal** geladen und in Sets weitergereicht (N+1 weg).
    """
    summary = {"users": 0, "email": 0, "push": 0, "telegram": 0, "whatsapp": 0}
    users = User.query.filter(~User.email.like("%@bot.local")).all()

    tipped_user_ids = {
        row[0] for row in db.session.query(Prediction.user_id)
        .filter_by(match_id=match.id).all()
    }
    wave_kind = WAVE_KINDS.get(wave, WAVE_KINDS[1])
    sent_cache = {
        (row.user_id, row.match_id, row.channel, row.kind)
        for row in db.session.query(
            NotificationLog.user_id, NotificationLog.match_id,
            NotificationLog.channel, NotificationLog.kind,
        ).filter_by(match_id=match.id, kind=wave_kind).all()
    }
    try:
        from scoring import get_setting as _get_setting
        email_base_url = _get_setting("public_base_url",
                                      current_app.config.get("PUBLIC_BASE_URL", ""))
    except Exception:
        email_base_url = current_app.config.get("PUBLIC_BASE_URL", "")

    for user in users:
        res = send_user_notification(
            user, match, channels=channels,
            tipped_user_ids=tipped_user_ids, sent_cache=sent_cache,
            email_base_url=email_base_url,
            wave=wave, now=now, enforce_window=enforce_window,
        )
        if any(res.values()):
            summary["users"] += 1
        for k, v in res.items():
            if v:
                summary[k] += 1
    try:
        db.session.flush()  # alle _mark_sent-Inserts auf einen Schlag
    except Exception as e:
        current_app.logger.warning(f"Notification-Log-Bulk-Flush fehlgeschlagen: {e}")
        db.session.rollback()
    return summary


# ============================================================ Digest (100) —
def _digest_link(matches, base):
    """CTA-Link fuer den Digest: ein Spieltag -> /tippen/<md>, mehrere ->
    /meine-offenen-tipps (uebersicht ueber ALLE offenen Tipps)."""
    spieltage = {m.matchday for m in matches}
    pfad = (f"/tippen/{matches[0].matchday}" if len(spieltage) == 1
            else "/meine-offenen-tipps")
    return (base + pfad) if base else pfad


def _digest_zeile(match):
    ko = _berlin_fmt(match.kickoff)
    return f"• {match.home_team.name} – {match.away_team.name} · {ko}"


def send_digest_reminders(matches, channels, *, wave: int = 1, now=None,
                          tipped_by_match=None, sent_cache=None,
                          email_base_url=None) -> dict:
    """(100) E-Mail + WhatsApp als EINE zusammengefasste Nachricht pro User.

    Anlass (Nutzerfeedback + Screenshot): 4 einzelne „Tipp-Erinnerung“-
    Nachrichten fuers selben Spieltag sind Spam. Der Digest listet ALLE
    tipppflichtigen Spiele im Wellen-Fenster mit Link. Dedup bleibt
    spielgenau: Jedes enthaltene Spiel wird individuell markiert — taucht
    spaeter ein weiteres Spiel im Fenster auf, folgt ein Digest nur dafuer.
    Seit (101) gelten ALLE VIER Kanaele: Telegram erhaelt denselben Text
    wie WhatsApp, Push eine kompakte Karte (Gesamtzahl + Digest-Link).
    """
    summary = {"users": 0, "email": 0, "whatsapp": 0, "telegram": 0, "push": 0}
    matches = [m for m in matches if m is not None]
    if not matches or not channels:
        return summary
    now = now or datetime.now(timezone.utc)
    kind = WAVE_KINDS.get(wave, WAVE_KINDS[1])
    users = User.query.filter(~User.email.like("%@bot.local")).all()
    ids = [m.id for m in matches]

    if tipped_by_match is None:
        tipped_by_match = {}
        for uid, mid in (db.session.query(Prediction.user_id, Prediction.match_id)
                         .filter(Prediction.match_id.in_(ids)).all()):
            tipped_by_match.setdefault(mid, set()).add(uid)
    if sent_cache is None:
        sent_cache = {
            (r.user_id, r.match_id, r.channel, r.kind)
            for r in db.session.query(
                NotificationLog.user_id, NotificationLog.match_id,
                NotificationLog.channel, NotificationLog.kind,
            ).filter(NotificationLog.match_id.in_(ids),
                     NotificationLog.kind == kind).all()
        }
    if email_base_url is None:
        try:
            from scoring import get_setting
            email_base_url = get_setting("public_base_url",
                                         current_app.config.get("PUBLIC_BASE_URL", ""))
        except Exception:
            email_base_url = current_app.config.get("PUBLIC_BASE_URL", "")
    base = (email_base_url or "").rstrip("/")

    for user in users:
        user_bekam_etwas = False
        for ch in channels:
            if ch == "email":
                if not user.email or not _truthy(getattr(user, "notify_email", True), True):
                    continue
            elif ch == "whatsapp":
                if not _truthy(getattr(user, "notify_whatsapp", True), True):
                    continue
                if not (user.whatsapp_phone and user.whatsapp_apikey):
                    continue
            elif ch == "telegram":
                if not _truthy(getattr(user, "notify_telegram", True), True):
                    continue
            elif ch == "push":
                if not _truthy(getattr(user, "notify_push", True), True):
                    continue
                if not user.push_subscription:
                    continue
            else:
                continue
            eligible = [m for m in matches
                        if user_wants_match_reminder(
                            user, m, tipped_user_ids=tipped_by_match.get(m.id, set()))
                        and _window_hit(m, user, wave, now)
                        and (user.id, m.id, ch, kind) not in sent_cache]
            if not eligible:
                continue

            link = _digest_link(eligible, base)
            n = len(eligible)
            liste = "\n".join(_digest_zeile(m) for m in eligible)
            gesendet = False
            try:
                if ch == "email":
                    from mail_helpers import send_email
                    thema = (f"⚽ Tipp-Erinnerung: 1 offenes Spiel" if n == 1
                             else f"⚽ Tipp-Erinnerung: {n} offene Spiele")
                    body = (f"Hallo {user.username},\n\n"
                            f"du hast noch nicht getippt ({n} "
                            f"Spiel{'e' if n != 1 else ''}):\n\n"
                            f"{liste}\n\nJetzt tippen: {link}\n")
                    gesendet = send_email(thema, [user.email], body)
                elif ch == "whatsapp":
                    from whatsapp import send_whatsapp_message
                    text = ("⚽ *Tipp-Erinnerung*\n\n"
                            f"Du hast noch nicht getippt ({n} "
                            f"Spiel{'e' if n != 1 else ''}):\n\n"
                            f"{liste}\n\n👉 Jetzt tippen: {link}")
                    gesendet = send_whatsapp_message(
                        user.whatsapp_phone, user.whatsapp_apikey, text)
                elif ch == "telegram":
                    from telegram_bot import notify_user_telegram
                    text = ("⚽ Tipp-Erinnerung\n\n"
                            f"Du hast noch nicht getippt ({n} "
                            f"Spiel{'e' if n != 1 else ''}):\n\n"
                            f"{liste}\n\n👉 Jetzt tippen: {link}")
                    gesendet = notify_user_telegram(user, text)
                else:  # push — kompakte Karte statt Spielliste
                    from push_routes import _send_push_to_users
                    sent, _failed = _send_push_to_users([user], {
                        "title": "⚽ Tipp-Erinnerung",
                        "body": (f"Du hast noch nicht getippt ({n} "
                                 f"Spiel{'e' if n != 1 else ''})."),
                        "url": _digest_link(eligible, ""),
                        "tag": f"digest-{kind}-{user.id}",
                    })
                    gesendet = sent > 0
            except Exception as e:
                current_app.logger.warning(
                    f"Digest-{ch} fehlgeschlagen fuer User {user.id}: {e}")
                gesendet = False
            if gesendet:
                summary[ch] += 1
                user_bekam_etwas = True
                for m in eligible:
                    _mark_sent(user, m, ch, kind, sent_cache=sent_cache)
        if user_bekam_etwas:
            summary["users"] += 1
    try:
        db.session.flush()
    except Exception as e:
        current_app.logger.warning(f"Digest-Log-Bulk-Flush fehlgeschlagen: {e}")
        db.session.rollback()
    return summary


def upcoming_reminder_matches(default_hours=1, now=None):
    """Findet Spiele, die ins Reminder-Zeitfenster einer aktiven Welle fallen.

    Obergrenze = groesster aktiver Wellen-Vorlauf (Welle 1 max. 24 h, Welle 2
    bis 168 h konfigurierbar). Die eigentliche, user-genaue Fenster-Pruefung
    uebernimmt send_user_notification(enforce_window=True) im Zyklus.
    """
    now = now or datetime.now(timezone.utc)
    max_hours = max(24, int(default_hours or 0))
    if reminder_second_wave_enabled():
        max_hours = max(max_hours, reminder_lead_hours(None, wave=2))
    q = Match.query.filter(
        Match.status == "scheduled",
        Match.kickoff > now,
        Match.kickoff <= now + timedelta(hours=max_hours),
    )
    q = filter_matches_for_active_competition(q)
    matches = q.order_by(Match.kickoff.asc()).all()
    return [m for m in matches if m.kickoff is not None]



def _next_open_match_for_user(user):
    """Naechstes offenes Spiel ohne Tipp fuer Test-/Preview-Zwecke.

    Prefetch der eigenen Tipps (1 Query) statt einer Query pro Spiel.
    """
    now = datetime.now(timezone.utc)
    q = Match.query.filter(Match.status == "scheduled", Match.kickoff > now)
    q = filter_matches_for_active_competition(q)
    tipped_match_ids = {
        row[0] for row in db.session.query(Prediction.match_id)
        .filter_by(user_id=user.id).all()
    }
    for match in q.order_by(Match.kickoff.asc()).all():
        if match.id not in tipped_match_ids:
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

    # (104) Vorschau im DIGEST-Format wie ((100)/(101)): die echten
    # Erinnerungen sind zusammengefasste Listen — der Test muss zeigen,
    # was wirklich ankommt (vorher: alter Einzelspiel-Text). Link wie im
    # Digest: ein Spieltag -> /tippen/<md>.
    if match:
        ko = _berlin_fmt(match.kickoff)
        zeile = f"• {match.home_team.name} – {match.away_team.name} · {ko}"
        path = f"/tippen/{match.matchday}"
    else:
        path = "/meine-offenen-tipps"
    url = (base + path) if base else path
    if match:
        mail_thema = "🧪 Test: ⚽ Tipp-Erinnerung: 1 offenes Spiel"
        mail_body = (
            f"Hallo {user.username},\n\n"
            f"du hast noch nicht getippt (1 Spiel):\n\n"
            f"{zeile}\n\nJetzt tippen: {url}\n"
        )
        tg_body = (
            "🧪 Test: ⚽ Tipp-Erinnerung\n\n"
            f"Du hast noch nicht getippt (1 Spiel):\n\n"
            f"{zeile}\n\n👉 Jetzt tippen: {url}"
        )
        wa_body = (
            "🧪 *Test: Tipp-Erinnerung*\n\n"
            f"Du hast noch nicht getippt (1 Spiel):\n\n"
            f"{zeile}\n\n👉 Jetzt tippen: {url}"
        )
        push_body = "Du hast noch nicht getippt (1 Spiel)."
    else:
        generisch = (
            "sobald ein Spiel ohne Tipp kurz bevorsteht, bekommst du hier "
            "eine zusammengefasste Liste aller offenen Spiele."
        )
        mail_thema = "🧪 Test: ⚽ Tipp-Erinnerung"
        mail_body = (
            f"Hallo {user.username},\n\n{generisch}\n\nJetzt tippen: {url}\n"
        )
        tg_body = f"🧪 Test: ⚽ Tipp-Erinnerung\n\n{generisch}\n\n👉 Jetzt tippen: {url}"
        wa_body = f"🧪 *Test: Tipp-Erinnerung*\n\n{generisch}\n\n👉 Jetzt tippen: {url}"
        push_body = "So sehen zusammengefasste Tipp-Erinnerungen aus."

    if "email" in channels and _truthy(getattr(user, "notify_email", True), True) and user.email:
        try:
            from mail_helpers import send_email
            result["email"] = send_email(mail_thema, [user.email], mail_body)
        except Exception as e:
            current_app.logger.warning(f"Test-Reminder E-Mail fehlgeschlagen fuer User {user.id}: {e}")

    if "push" in channels and _truthy(getattr(user, "notify_push", True), True) and user.push_subscription:
        try:
            from push_routes import _send_push_to_users
            sent, _failed = _send_push_to_users([user], {
                "title": "🧪 Test: Tipp-Erinnerung",
                "body": push_body,
                "url": path,
                "tag": f"test-reminder-{user.id}",
            })
            result["push"] = sent > 0
        except Exception as e:
            current_app.logger.warning(f"Test-Reminder Push fehlgeschlagen fuer User {user.id}: {e}")

    if "telegram" in channels and _truthy(getattr(user, "notify_telegram", True), True):
        try:
            from telegram_bot import notify_user_telegram
            result["telegram"] = notify_user_telegram(user, tg_body)
        except Exception as e:
            current_app.logger.warning(f"Test-Reminder Telegram fehlgeschlagen fuer User {user.id}: {e}")

    if "whatsapp" in channels and _truthy(getattr(user, "notify_whatsapp", True), True):
        if user.whatsapp_phone and user.whatsapp_apikey:
            try:
                from whatsapp import send_whatsapp_message
                result["whatsapp"] = send_whatsapp_message(user.whatsapp_phone, user.whatsapp_apikey, wa_body)
            except Exception as e:
                current_app.logger.warning(f"Test-Reminder WhatsApp fehlgeschlagen fuer User {user.id}: {e}")

    return result

def run_reminder_cycle(channels=None, now=None) -> dict:
    """Kompletter Reminder-Lauf fuer Scheduler/Cron (alle aktiven Wellen)."""
    total = {"matches": 0, "users": 0, "email": 0, "push": 0, "telegram": 0, "whatsapp": 0,
              "wave1": 0, "wave2": 0, "enabled": True}
    try:
        from scoring import get_setting
        enabled = get_setting("reminders_enabled", True)
        if not _truthy(enabled, True):
            total["enabled"] = False
            return total
    except Exception:
        pass
    if now is None:
        now = datetime.now(timezone.utc)
    waves = [1, 2] if reminder_second_wave_enabled() else [1]
    matches = upcoming_reminder_matches(now=now)
    total["matches"] = len(matches)
    # (101) ALLE Kanaele als Digest — EINE Nachricht pro User und Kanal
    # (Nutzer: „Bei Telegram und Push sollte es auch so sein“).
    kanaele = channels or ["email", "push", "telegram", "whatsapp"]
    for wave in waves:
        if kanaele and matches:
            d = send_digest_reminders(matches, kanaele, wave=wave, now=now)
            for k in ("users", "email", "whatsapp", "telegram", "push"):
                total[k] += d.get(k, 0)
            total[f"wave{wave}"] += d.get("users", 0)
    db.session.commit()
    return total
