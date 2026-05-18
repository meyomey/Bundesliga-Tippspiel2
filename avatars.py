"""Avatar-Upload und -Verarbeitung."""
import os
from datetime import datetime, timezone

from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename


def save_avatar(file_storage, user_id):
    """Speichert hochgeladenes Avatar als 300x300 PNG.
    Liefert (filename, error_message) zurueck.
    error_message ist None bei Erfolg oder wenn keine Datei mitgesendet wurde.
    """
    if not file_storage:
        return None, None
    if isinstance(file_storage, str):
        return None, None
    if not getattr(file_storage, "filename", None):
        return None, None

    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "gif", "webp"})
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in allowed:
        return None, f"Dateityp .{ext} nicht erlaubt. Erlaubt: {', '.join(sorted(allowed))}"

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    filename = secure_filename(f"avatar_{user_id}_{datetime.now(timezone.utc).timestamp():.0f}.png")
    filepath = os.path.join(upload_dir, filename)

    try:
        img = Image.open(file_storage)
        img.thumbnail((300, 300))
        # Transparenz-ersetzen fuer PNG
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        else:
            img = img.convert("RGB")
        img.save(filepath, "PNG", optimize=True)
        return filename, None
    except Exception as e:
        current_app.logger.error(f"Avatar-Fehler: {e}")
        return None, f"Fehler beim Verarbeiten: {e}"
