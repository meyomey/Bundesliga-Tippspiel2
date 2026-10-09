"""Tests Registrierungsseite ((95)): Dopplung behoben + Kontakt-Weg.

Nutzerbefund: bei invite_required erschienen ZWEI „Anmelden"-Zeilen, und
der Einladungs-Hinweis hatte keinen Kontaktweg für Code-Anfragen.
"""
from scoring import get_setting, set_setting


def test_register_ohne_doppeltes_anmelden(client, db):
    """Nur EINE Anmelden-Referenz; die alte Oberzeile ist weg."""
    resp = client.get("/auth/register")
    body = resp.get_data(as_text=True)
    assert resp.status_code in (200, 403)   # 403 = invite required (Design)
    assert "Du hast schon ein Konto?" not in body   # alte Dopplung entfernt
    assert body.count("Schon Konto?") == 1
    assert "Einladungscode" in body or "Registrierung" in body


def test_register_kontakt_fallback_impressum(client, db):
    """Ohne Kontakt-Einstellung: Verweis aufs Impressum (dort steht die Mail)."""
    body = client.get("/auth/register").get_data(as_text=True)
    assert "Noch keinen Einladungscode?" in body
    assert 'href="/impressum"' in body
    assert "mailto:" not in body


def test_register_kontakt_mailto_bei_setting(client, db, app):
    """Mit Admin-Einstellung: mailto-Link statt Impressum-Verweis."""
    set_setting("contact_email", "chef@wulmstorf.example")
    assert get_setting("contact_email") == "chef@wulmstorf.example"
    body = client.get("/auth/register").get_data(as_text=True)
    assert 'href="mailto:chef@wulmstorf.example"' in body
    # Fallback-Text weg (Impressum-Link im Footer bleibt naturlich vorhanden)
    assert "Kontakt: siehe Impressum" not in body


def test_admin_settings_hat_kontaktfeld(client, db, admin_user):
    """Admin-Einstellungen zeigen das neue Feld und speichern den Wert."""
    assert client.post("/auth/login", data={"email": admin_user.email,
                                            "password": "admin123"},
                       follow_redirects=True).status_code == 200
    body = client.get("/admin/settings").get_data(as_text=True)
    assert "Kontakt-E-Mail" in body
    resp = client.post("/admin/settings", data={
        "registration_mode": "invite",
        "contact_email": "anfrage@wulmstorf.example",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert get_setting("contact_email") == "anfrage@wulmstorf.example"
    # Und die Registrierungsseite zeigt den neuen Kontakt sofort:
    client.get("/auth/logout")
    body = client.get("/auth/register").get_data(as_text=True)
    assert "mailto:anfrage@wulmstorf.example" in body
