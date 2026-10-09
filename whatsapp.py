"""WhatsApp-Reminder via CallMeBot API.

CallMeBot ist kostenlos und benötigt KEINEN WhatsApp Business Account.
Setup für jeden User (einmalig):
1. User speichert seine Handynummer im Profil (mit Ländervorwahl, z.B. +4917612345678)
2. User schickt einmalig diese WhatsApp-Nachricht an +34 644 59 78 27:
   "I allow callmebot to send me messages"
3. CallMeBot antwortet mit einem API-Key → User trägt diesen im Profil ein
4. Ab sofort können Nachrichten gesendet werden

Doku: https://www.callmebot.com/blog/free-api-whatsapp-messages/
"""
import urllib.parse
import requests
from flask import current_app


def send_whatsapp_message(phone: str, apikey: str, message: str) -> bool:
    """Sendet eine WhatsApp-Nachricht via CallMeBot."""
    phone_clean = "".join(c for c in phone if c.isdigit())
    if not phone_clean or not apikey or not message:
        return False
    encoded_msg = urllib.parse.quote(message)
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone_clean}&text={encoded_msg}&apikey={apikey}"
    )
    try:
        resp = requests.get(url, timeout=10)
        success = resp.status_code == 200 and "Message queued" in (resp.text or "")
        if not success:
            current_app.logger.warning(
                f"CallMeBot Fehler für {phone_clean}: {resp.status_code} – {resp.text[:200]}"
            )
        return success
    except requests.RequestException as e:
        current_app.logger.error(f"CallMeBot Request-Fehler: {e}")
        return False


def send_whatsapp_test(user) -> bool:
    """Sendet eine Test-Nachricht an den User."""
    if not user.whatsapp_phone or not user.whatsapp_apikey:
        return False
    message = (
        "⚽ *Wulmstörper Tipprunde*\n\n"
        "✅ Test erfolgreich! WhatsApp-Erinnerungen sind aktiviert.\n\n"
        "Du wirst 1 Stunde vor jedem Spiel erinnert, wenn du noch nicht getippt hast."
    )
    return send_whatsapp_message(user.whatsapp_phone, user.whatsapp_apikey, message)
