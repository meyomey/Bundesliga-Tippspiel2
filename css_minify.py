"""(90) Build-Helfer: erzeugt static/css/style.min.css aus style.css.

Wird von build_lieferungen.py bei jedem Build automatisch frisch erzeugt;
tests/test_style_minify.py prueft, dass die committete Min-Version exakt zum
Quell-Stand passt (Frische-Guard). Gehoert NICHT auf den Server (Dev-Tool).
"""
from pathlib import Path

SRC = Path("static/css/style.css")
DST = Path("static/css/style.min.css")


def minify_css_file(src=SRC, dst=DST):
    """Minifiziert src nach dst. Liefert (bytes_in, bytes_out)."""
    from csscompressor import compress
    text = Path(src).read_text(encoding="utf-8")
    out = compress(text)
    Path(dst).write_text(out, encoding="utf-8")
    return len(text), len(out)


if __name__ == "__main__":
    a, b = minify_css_file()
    print(f"style.min.css: {a} -> {b} Bytes ({100 * b // a} % vom Original)")
