"""Regressionsschutz fuer den CI-Workflow ((98), Anlass Run #103).

Ein '#' INNERHALB des IGNORE_39-Blockskalars ist in YAML kein Kommentar:
Es wird Teil des Werts und erreicht pip-audit als Argument (Exit 2).
Dieser Test parses den Block textuell und waecht darueber - ohne
YAML-Abhaengigkeit.
"""
import re

PFAD = ".github/workflows/tests.yml"


def _ignore39_zeilen():
    zeilen = open(PFAD, encoding="utf-8").read().splitlines()
    start = next(i for i, z in enumerate(zeilen)
                 if z.strip() == "IGNORE_39: >-")
    block = []
    for z in zeilen[start + 1:]:
        if not z.startswith("        ") or z.strip() == "":
            break
        block.append(z.strip())
    return block


def test_ignore39_enthaelt_keine_kommentarzeichen():
    """Kein '#' im Wert - Blockskalare kennen keine Kommentare."""
    for z in _ignore39_zeilen():
        assert "#" not in z, f"Blockskalar-Kommentar wuerde pip-audit brechen: {z!r}"


def test_ignore39_zeilen_sind_valide_ignore_flags():
    """Jede Zeile besteht ausschliesslich aus --ignore-vuln <ID>-Paaren."""
    for z in _ignore39_zeilen():
        for token in z.split():
            assert re.fullmatch(r"--ignore-vuln|[A-Z]+-\d{4}-\d+|GHSA-[a-z0-9-]+", token), \
                f"Unerwartetes Token im IGNORE_39-Wert: {token!r}"


def test_urllib3_und_werkzeug_stands():
    """Die (97)/(98)-Fixes bleiben verdrahtet: urllib3-Ignore da,
    Werkzeug-Pin auf der CVE-Fix-Version."""
    block = " ".join(_ignore39_zeilen())
    assert "PYSEC-2026-4175" in block and "PYSEC-2026-4176" in block
    assert "PYSEC-2026-4177" in block
    req39 = open("requirements_py39.txt", encoding="utf-8").read()
    assert "Werkzeug==3.1.9" in req39
