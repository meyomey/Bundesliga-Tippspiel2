"""Ausgelagerte Main-Route-Logik: PWA-Dateien."""
import os

from flask import current_app, send_from_directory

def _service_worker():
    response = send_from_directory(
        os.path.join(current_app.root_path, "static", "js"),
        "sw.js",
        mimetype="application/javascript",
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response

def _manifest():
    resp = send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "manifest.json",
        mimetype="application/manifest+json",
    )
    # Manifest nicht langfristig cachen: Orientation/Icon-Aenderungen sollen
    # nach Plesk-Restart bzw. Browser-Refresh sauber ankommen.
    resp.headers["Cache-Control"] = "no-cache"
    return resp

def _pwa_icon(size):
    """Robuste Icon-Route fuer PWA/Apple/Favicon.

    Liefert statische Icons, falls vorhanden. Wenn beim Deployment einzelne
    PNGs nicht hochgeladen wurden, wird das Icon dynamisch als PNG erzeugt,
    damit die PWA-Installation nicht an 404-Icons scheitert.
    """
    allowed = {72, 96, 128, 144, 192, 512}
    if size not in allowed:
        size = 192
    filename = f"logo_{size}.png"
    icon_dir = os.path.join(current_app.root_path, "static", "uploads")
    icon_path = os.path.join(icon_dir, filename)
    if os.path.exists(icon_path):
        resp = send_from_directory(icon_dir, filename, mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

    try:
        from generate_pwa_icons import create_icon
        from io import BytesIO
        img = create_icon(size)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        from flask import Response
        resp = Response(buf.getvalue(), mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        # Minimaler PNG-Fallback ohne externe Dateien, falls Pillow/Generator fehlt.
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO
        from flask import Response
        img = Image.new("RGB", (size, size), color=(20, 184, 166))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        text = "W"
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (size - (bbox[2] - bbox[0])) // 2
        y = (size - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), text, fill="white", font=font)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(buf.getvalue(), mimetype="image/png")


# ============================================================ Main Pages -

