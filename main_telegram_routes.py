"""Ausgelagerte Main-Route-Logik: Telegram und Competition-Wechsel."""
from flask import abort, current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user

from models import Competition
from scoring import get_setting

def _telegram_webhook(secret=None):
    """Webhook für eingehende Telegram-Nachrichten."""
    from telegram_bot import process_message, send_telegram_message
    import json

    try:
        expected_secret = get_setting("telegram_webhook_secret", current_app.config.get("TELEGRAM_WEBHOOK_SECRET", ""))
        if expected_secret:
            provided = secret or request.headers.get("X-Telegram-Bot-Api-Secret-Token") or request.args.get("secret")
            if provided != expected_secret:
                current_app.logger.warning("Telegram Webhook mit falschem Secret abgewiesen.")
                abort(403)
        else:
            current_app.logger.warning("Telegram Webhook ohne Secret konfiguriert. Bitte in Admin → Einstellungen setzen.")
        data = request.get_json(silent=True) or {}
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if chat_id and text:
            reply = process_message(str(chat_id), text)
            if reply:
                send_telegram_message(chat_id, reply)
    except Exception as e:
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            raise
        current_app.logger.error(f"Telegram Webhook Error: {e}")

    return "", 200

def _profile_telegram_token():
    """Generiert einen Telegram-Verknüpfungs-Token für das Profil."""
    from telegram_bot import generate_telegram_token
    token = generate_telegram_token(current_user.id)
    bot_username = None
    from scoring import get_setting
    bot_username = get_setting("telegram_bot_username", "")
    return jsonify({
        "ok": True,
        "token": token,
        "bot_username": bot_username,
    })

def _set_competition(code):
    from flask import session
    comp = Competition.query.filter_by(code=code, is_active=True).first()
    if comp:
        session["competition_code"] = code
        flash(f"Wettbewerb auf '{comp.name}' gewechselt.", "success")
    else:
        flash("Ungültiger Wettbewerb.", "danger")
    return redirect(request.referrer or url_for("main.dashboard"))

