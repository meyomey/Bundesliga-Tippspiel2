"""Tests fuer das konsolidierte Theme-System ((92)+(93)).

Geschichte: Ein Hell/Dunkel-Theme mit toggleTheme() + Light-Palette existierte
bereits (app.js, Key 'theme', 2 Buttons). (92) baute fälschlich ein
Parallel-System — (93) konsolidiert: EIN Key ('theme'), EINE Engine
(theme.js, Node-getestet), die ORIGINALEN zwei Buttons, die ORIGINALE
Palette + echte Neuerungen (No-Flash, color-scheme, CI-Test).
"""
def test_base_ohne_drittes_system_und_mit_no_flash():
    """Kein zusätzlicher Button, kein Fremd-Key; No-Flash liest 'theme'."""
    t = open('templates/base.html', encoding='utf-8').read()
    assert 'id="themeToggle"' not in t          # Dopplung aus (92) entfernt
    assert 'wt-theme' not in t                  # kein zweiter Key
    assert "localStorage.getItem('theme')" in t  # No-Flash, historischer Key
    assert 'js/theme.js' in t                   # Engine eingebunden
    assert t.count('onclick="toggleTheme()"') == 2  # die 2 ORIGINALEN Buttons
    assert 'data-theme="dark"' in t             # Default dunkel bleibt


def test_originale_palette_bleibt_mit_color_scheme():
    """Der ERSTE Light-Block ist die historische Palette + color-scheme."""
    css = open('static/css/style.css', encoding='utf-8').read()
    first = css.split('[data-theme="light"]', 1)[1].split('}', 1)[0]
    for token in ('--bg:', '--surface:', '--text:', '--border:', '--navbar-bg:'):
        assert token in first
    assert 'color-scheme: light' in first       # echte (93)-Neuerung
    assert '#f8fafc' in css                     # Original-Hintergrund erhalten
    assert '#f2f4f6' not in css                 # (92)-Ersatzpalette entfernt
    assert '.theme-toggle' not in css           # Button-CSS der Dopplung weg
    assert '[data-theme="light"] input' in css  # Formular-Feintuning intakt


def test_theme_js_engine_und_app_delegate():
    """theme.js ist die getestete Engine; app.js delegiert nur noch."""
    js = open('static/js/theme.js', encoding='utf-8').read()
    assert 'module.exports' in js
    for fn in ('initialTheme', 'anwenden', 'umschalten'):
        assert f'function {fn}' in js
    assert "SCHLUESSEL = 'theme'" in js         # historischer Key, kein wt-theme
    app = open('static/js/app.js', encoding='utf-8').read()
    assert 'window.WTTheme.umschalten()' in app  # Delegat
    assert "localStorage.getItem('theme')" not in app  # alte Apply-Zeilen raus


def test_ci_laeuft_theme_test_und_neue_deps():
    """CI: Theme-Node-Test eingebunden; neue Test-Abhaengigkeiten gepinnt.

    (174) Nach Dependabot-Desaster: der Guard prueft das PIN-FORMAT
    (``paket==X.Y.Z``), nicht mehr die exakte Version - sonst reisst
    jeder Dependabot-Bump die komplette CI mit (Fall #34: alle 6
    Python-Jobs rot wegen hartcodiertem 2.3.1)."""
    import re
    ci = open('.github/workflows/tests.yml', encoding='utf-8').read()
    assert 'node tests/js/theme_test.js' in ci
    req = open('requirements.txt', encoding='utf-8').read()
    assert re.search(r'^pytest-timeout==\d+\.\d+\.\d+$', req, re.M), \
        "pytest-timeout muss gepinnt bleiben (==X.Y.Z)"
    assert re.search(r'^csscompressor==\d+\.\d+\.\d+$', req, re.M), \
        "csscompressor muss gepinnt bleiben (==X.Y.Z)"
    ini = open('pytest.ini', encoding='utf-8').read()
    assert 'timeout = 120' in ini
