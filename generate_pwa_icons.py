"""Generiert lokale PWA/App-Icons fuer die Wulmstörper Tipprunde.

Keine externen Assets. Erzeugt:
- static/uploads/logo_72.png
- static/uploads/logo_96.png
- static/uploads/logo_128.png
- static/uploads/logo_144.png
- static/uploads/logo_192.png
- static/uploads/logo_512.png
- static/uploads/badge_72.png
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "static" / "uploads"
OUT.mkdir(parents=True, exist_ok=True)

SIZES = [72, 96, 128, 144, 192, 512]
ICON_VERSION = "v2"


def _font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _rounded_mask(size, radius_ratio=0.22):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    r = int(size * radius_ratio)
    d.rounded_rectangle((0, 0, size, size), radius=r, fill=255)
    return mask


def _gradient_bg(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    c1 = (15, 23, 42)     # slate-900
    c2 = (13, 148, 136)   # teal-600
    c3 = (20, 184, 166)   # teal-500
    for y in range(size):
        for x in range(size):
            t = (x * 0.65 + y * 0.95) / (size * 1.6)
            if t < 0.55:
                k = t / 0.55
                c = tuple(int(c1[i] * (1-k) + c2[i] * k) for i in range(3))
            else:
                k = (t - 0.55) / 0.45
                c = tuple(int(c2[i] * (1-k) + c3[i] * k) for i in range(3))
            px[x, y] = c
    return img.convert("RGBA")


def _draw_pitch_lines(draw, size):
    col = (255, 255, 255, 34)
    w = max(1, size // 80)
    pad = int(size * 0.13)
    draw.rounded_rectangle((pad, pad, size-pad, size-pad), radius=int(size*0.06), outline=col, width=w)
    draw.line((size//2, pad, size//2, size-pad), fill=col, width=w)
    draw.ellipse((int(size*0.39), int(size*0.39), int(size*0.61), int(size*0.61)), outline=col, width=w)


def _draw_ball(draw, cx, cy, r):
    # ball base
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(255, 255, 255, 245), outline=(15, 23, 42, 220), width=max(1, r//8))
    # center pentagon-ish
    pts = []
    for i in range(5):
        a = -math.pi/2 + i * 2 * math.pi / 5
        pts.append((cx + math.cos(a) * r * 0.36, cy + math.sin(a) * r * 0.36))
    draw.polygon(pts, fill=(15, 23, 42, 235))
    # seams
    for x, y in pts:
        draw.line((cx, cy, x, y), fill=(15, 23, 42, 190), width=max(1, r//12))
    # outer arcs simplified
    draw.arc((cx-r*0.82, cy-r*0.92, cx+r*0.12, cy+r*0.15), 220, 45, fill=(15, 23, 42, 170), width=max(1, r//14))
    draw.arc((cx-r*0.12, cy-r*0.92, cx+r*0.82, cy+r*0.15), 135, 320, fill=(15, 23, 42, 170), width=max(1, r//14))
    draw.arc((cx-r*0.78, cy-r*0.08, cx+r*0.78, cy+r*0.9), 200, 340, fill=(15, 23, 42, 170), width=max(1, r//14))


def _draw_w_mark(draw, size):
    """Zeichnet ein klares, homescreen-taugliches W ohne Font-Abhaengigkeit."""
    # coordinates within safe area
    pts = [
        (size * 0.22, size * 0.33),
        (size * 0.34, size * 0.70),
        (size * 0.47, size * 0.43),
        (size * 0.58, size * 0.70),
        (size * 0.74, size * 0.31),
    ]
    pts = [(int(x), int(y)) for x, y in pts]
    width = max(5, int(size * 0.075))
    # shadow
    shadow = [(x + int(size * 0.018), y + int(size * 0.025)) for x, y in pts]
    draw.line(shadow, fill=(0, 0, 0, 90), width=width, joint="curve")
    draw.line(pts, fill=(255, 255, 255, 248), width=width, joint="curve")
    # small teal cut/highlight in the middle
    draw.line([(int(size*0.43), int(size*0.58)), (int(size*0.50), int(size*0.43))], fill=(94, 234, 212, 210), width=max(2, width//3))


def create_icon(size):
    scale = 4 if size < 192 else 2
    work = size * scale
    img = _gradient_bg(work)
    draw = ImageDraw.Draw(img, "RGBA")
    _draw_pitch_lines(draw, work)

    # Stylized W + small football
    _draw_w_mark(draw, work)
    _draw_ball(draw, int(work * 0.73), int(work * 0.73), int(work * 0.155))

    # Mask rounded icon
    mask = _rounded_mask(work)
    img.putalpha(mask)
    if work != size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def create_badge(size=72):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    cx = cy = size // 2
    _draw_ball(draw, cx, cy, int(size * 0.36))
    return img


def main():
    for size in SIZES:
        icon = create_icon(size)
        icon.save(OUT / f"logo_{size}.png", "PNG", optimize=True)
        icon.save(OUT / f"logo_{ICON_VERSION}_{size}.png", "PNG", optimize=True)
    badge = create_badge(72)
    badge.save(OUT / "badge_72.png", "PNG", optimize=True)
    badge.save(OUT / f"badge_{ICON_VERSION}_72.png", "PNG", optimize=True)
    print(f"PWA Icons geschrieben nach {OUT}")


if __name__ == "__main__":
    main()
