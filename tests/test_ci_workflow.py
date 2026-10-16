"""Regressionsschutz fuer den CI-Workflow.

Geschichte: (98) entstand der Test, weil ein '#' INNERHALB des damaligen
IGNORE_39-Blockskalars in YAML kein Kommentar ist — es wird Teil des Werts
und erreicht pip-audit als Argument (Exit 2, Run #103). Diese Falle gilt
weiterhin fuer JEDE yaml-Blockskalar-Umgebung.
(126) Python-3.9-Dekommissionierung: der Workflow enthaelt keine 3.9-Referenz
mehr, requirements_py39.txt ist geloescht, das Audit laeuft bewusst OHNE
Ignore-Liste (hartes Gate).
"""
import os
import re

PFAD = ".github/workflows/tests.yml"


def _workflow():
    return open(PFAD, encoding="utf-8").read()


def _blockskalar_zeilen(text):
    """Alle Zeilen aus '>-'-Blockskalaren (fuer die '#'-Falle aus Run #103)."""
    zeilen = text.splitlines()
    ergebnis = []
    for i, z in enumerate(zeilen):
        if not re.fullmatch(r"\s*[A-Z_0-9]+: >-", z):
            continue
        for folge in zeilen[i + 1:]:
            if not folge.startswith("        ") or folge.strip() == "":
                break
            ergebnis.append(folge.strip())
    return ergebnis


def test_workflow_hat_keine_39_referenzen():
    """(126) Die 3.9-Aera ist beendet — keine 3.9-Referenzen im Workflow."""
    t = _workflow()
    assert "3.9" not in t, "Workflow referenziert noch 3.9"
    assert "py39" not in t.lower(), "Workflow referenziert noch py39"


def test_requirements_ohne_py39_verweise():
    """(126) requirements.txt pflegt keine 3.9-Sonderdatei mehr.

    Bewusst INHALTLICH geprueft statt per Datei-Existenz: das verify_04-
    Clean-venv arbeitet auf einem GitHub-Klon, der die alte Datei bis zum
    naechsten Push noch physikalisch enthaelt."""
    t = open("requirements.txt", encoding="utf-8").read()
    assert "py39" not in t.lower()


def test_audit_job_laeuft_ohne_ignore_liste():
    """pip-audit ist hartes Gate: ohne $IGNORE-Variablen, ohne Blockskalar-Ignores."""
    t = _workflow()
    assert "pip-audit -r requirements.txt" in t
    assert "$IGNORE" not in t and "IGNORE_39" not in t
    for z in _blockskalar_zeilen(t):
        assert "#" not in z, \
            f"Blockskalar-Kommentar wuerde pip-audit/den Job brechen: {z!r}"


def test_dependabot_konfig_vorhanden():
    """(127) Version-Updates laufen nur MIT .github/dependabot.yml —
    die Datei ist der einzige Aktivierungs-Hebel, kein Web-Toggle."""
    t = open(".github/dependabot.yml", encoding="utf-8").read()
    assert "version: 2" in t
    assert 'package-ecosystem: "pip"' in t
    assert 'package-ecosystem: "github-actions"' in t
    assert 'interval: "weekly"' in t


def test_matrix_ab_311():
    """CI-Matrix = Produktionsversion 3.11 + Abwaertskompatibilitaet 3.12/3.13."""
    t = _workflow()
    assert 'python-version: ["3.11", "3.12", "3.13"]' in t
