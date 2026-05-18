"""E-Mail, Token, Mail-Einstellungen."""
from flask import current_app
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer

from extensions import db, mail
from scoring import get_setting, set_setting


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_reset_token(user_id, expires_sec=3600):
    return _serializer().dumps({"user_id": user_id}, salt="pw-reset")


def verify_reset_token(token, max_age=3600):
    try:
        data = _serializer().loads(token, salt="pw-reset", max_age=max_age)
        from models import User
        return db.session.get(User, data.get("user_id"))
    except Exception:
        return None


def apply_mail_settings():
    """Übernimmt gespeicherte SMTP-Einstellungen in die Flask-Mail-Config."""
    try:
        app = current_app._get_current_object()
        server = get_setting("mail_server")
        if server:
            app.config["MAIL_SERVER"] = server
        port = get_setting("mail_port")
        if port:
            app.config["MAIL_PORT"] = int(port)
        username = get_setting("mail_username")
        if username:
            app.config["MAIL_USERNAME"] = username
        password = get_setting("mail_password")
        if password:
            app.config["MAIL_PASSWORD"] = password
        sender = get_setting("mail_default_sender")
        if sender:
            app.config["MAIL_DEFAULT_SENDER"] = sender
        use_tls = get_setting("mail_use_tls")
        if use_tls is not None:
            app.config["MAIL_USE_TLS"] = bool(use_tls)
        use_ssl = get_setting("mail_use_ssl")
        if use_ssl is not None:
            app.config["MAIL_USE_SSL"] = bool(use_ssl)
        # Mail-Instanz reinitialisieren
        mail.init_app(app)
    except Exception:
        pass


def send_email(subject, recipients, body, html=None):
    """Sendet eine E-Mail. Liefert True/False."""
    try:
        msg = Message(subject, recipients=recipients, body=body, html=html)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Mail-Fehler: {e}")
        return False


def send_password_reset(user):
    token = generate_reset_token(user.id)
    from flask import url_for
    reset_url = url_for("auth.password_reset", token=token, _external=True)
    send_email(
        "Passwort zurücksetzen – Wulmstörper Tipprunde",
        [user.email],
        f"Hallo {user.username},\n\n"
        f"um dein Passwort zurückzusetzen, klicke auf diesen Link:\n\n"
        f"{reset_url}\n\n"
        f"Der Link ist 1 Stunde gültig.\n"
        f"Falls du das nicht angefordert hast, ignoriere diese Mail.",
    )


def send_kickoff_reminder(user, match):
    """Sendet eine Anpfiff-Erinnerung per E-Mail."""
    kickoff_str = match.kickoff.strftime("%d.%m.%Y %H:%M")
    send_email(
        f"⚽ Anpfiff-Erinnerung: {match.home_team.name} vs {match.away_team.name}",
        [user.email],
        f"Hallo {user.username},\n\n"
        f"das Spiel {match.home_team.name} vs {match.away_team.name} "
        f"beginnt um {kickoff_str} Uhr.\n"
        f"Du hast noch keinen Tipp abgegeben!\n\n"
        f"Jetzt tippen: https://tippspiel.example.com/spielplan",
    )


def apply_vapid_settings():
    """Spiegelt gespeicherte VAPID-Keys aus der DB in app.config."""
    try:
        pub = get_setting("vapid_public", "")
        priv = get_setting("vapid_private", "")
        if pub:
            current_app.config["VAPID_PUBLIC_KEY"] = pub
        if priv:
            current_app.config["VAPID_PRIVATE_KEY"] = priv
    except Exception:
        pass
