"""Tests Versionskennung ((103)): version.py als EINZIGE Quelle der Wahrheit.

Anlass (Nutzerbefund): die App hatte keine sichtbare Versionskennung.
Jetzt: Footer (vX.Y.Z auf jeder Seite) + /healthz (maschinenlesbar).
Der Sync-Guard zwingt version.py und CHANGELOG.md, immer gleich zu stehen.
"""
import re

import version


def test_version_passt_zum_changelog():
    """Sync-Guard: version.py == neueste CHANGELOG-Sektion (Eintragsschritt:
    beide anfassen, sonst schreit dieser Test)."""
    cl = open("CHANGELOG.md", encoding="utf-8").read()
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", cl, re.M)
    assert m, "CHANGELOG ohne Versionssektion?"
    assert m.group(1) == version.APP_VERSION, (
        f"version.py ({version.APP_VERSION}) und CHANGELOG ({m.group(1)}) "
        "laufen auseinander — beim Release BEIDE pflegen!")


def test_version_format_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.APP_VERSION)


def test_footer_zeigt_version_auf_jeder_seite(client):
    """Footer rendert v<version> — auch anonym (Impressum als offene Seite)."""
    body = client.get("/impressum").get_data(as_text=True)
    assert f"v{version.APP_VERSION}" in body


def test_wartungscenter_zeigt_version(client, admin_user):
    """(104) Wartungscenter: App-Kachel mit Version neben Python."""
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"},
                follow_redirects=True)
    body = client.get("/admin/maintenance").get_data(as_text=True)
    assert f"v{version.APP_VERSION}" in body


def test_healthz_liefert_version(client):
    """Monitoring/Deploy-Kontrolle: /healthz nennt die Live-Version."""
    data = client.get("/healthz").get_json()
    assert data["version"] == version.APP_VERSION
    assert data["db"] is True
    assert data["status"] == "ok"
