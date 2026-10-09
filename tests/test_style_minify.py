"""Tests fuer das CSS-Minify-System ((90)).

style.min.css ist committetes Build-Artefakt: Der Frische-Guard regeneriert
die Min-Version bei jedem Testlauf und vergleicht sie — aendert jemand
style.css ohne Neubau, schlaegt der Test anstatt stillem Veraltens einzuziehen.
"""
from csscompressor import compress


def test_min_css_ist_frisch():
    """Committete style.min.css == Minifizierung des aktuellen style.css."""
    src = open('static/css/style.css', encoding='utf-8').read()
    expected = compress(src)
    actual = open('static/css/style.min.css', encoding='utf-8').read()
    assert actual == expected


def test_min_css_deutlich_kleiner():
    """Min-Version spart messbar Groesse (Ziel < 90 % des Originals)."""
    src = open('static/css/style.css', encoding='utf-8').read()
    actual = open('static/css/style.min.css', encoding='utf-8').read()
    assert len(actual) < len(src) * 0.9


def test_base_bindet_nur_noch_min_css():
    """base.html laedt style.min.css (mit Cache-Buster), nie mehr das Original."""
    t = open('templates/base.html', encoding='utf-8').read()
    assert 'css/style.min.css' in t
    assert 'css/style.css' not in t  # 'css/style.min.css' enthaelt den Teilstring nicht


def test_sw_precache_min_css_und_cache_bump():
    """Service-Worker precacht die Min-Version; Cache-Name gebumpt (v4)."""
    sw = open('static/js/sw.js', encoding='utf-8').read()
    assert "'/static/css/style.min.css'" in sw
    assert "'/static/css/style.css'" not in sw
    assert 'tippspiel-v4' in sw


def test_build_erzeugt_min_css_automatisch():
    """Build erzeugt die Min-Version frisch; GitHub-Liste fuehrt sie auf."""
    build = open('build_lieferungen.py', encoding='utf-8').read()
    assert 'css_minify' in build and 'CSS-Minify' in build
    assert '"static/css/style.min.css"' in build
    assert '"css_minify.py"' in build
