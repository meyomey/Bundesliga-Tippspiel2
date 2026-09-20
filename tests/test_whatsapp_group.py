"""WhatsApp-Gruppen-Eingang: Settings-Speicherung, Schema-Gate und Darstellung.

Regressionstests für die Übergabe-Blöcke (50)–(52): Der Link lebt nur in den
DB-Settings, erscheint für Eingeloggte auf Startseite (ruhige Zeile) und
Mehr-Seite, https:// wird automatisch ergänzt, Leerzeichen verworfen und
unsichere Schema (javascript:) werden nie gerendert.
"""
from scoring import get_setting, set_setting

GROUP_LINK = "https://chat.whatsapp.com/ABC123xyz"


def _login_admin(client, admin_user):
    client.post("/auth/login", data={"email": admin_user.email, "password": "admin123"},
                follow_redirects=True)


def test_settings_fuegt_https_bei_kuerzem_link_ein(client, db, admin_user):
    """Eintrag ohne Schema wird beim Speichern mit https:// angereichert."""
    _login_admin(client, admin_user)
    r = client.post("/admin/settings", data={"whatsapp_group_url": "chat.whatsapp.com/ABC123xyz"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "Einstellungen gespeichert" in r.get_data(as_text=True)
    assert get_setting("whatsapp_group_url", "") == GROUP_LINK


def test_settings_verwirft_link_mit_leerzeichen(client, db, admin_user):
    """Leerzeichen ⇒ Flash-Fehler und der (alte) Eintrag wird geleert, nicht halb kaputt gespeichert."""
    set_setting("whatsapp_group_url", "https://chat.whatsapp.com/ALTEINTRAG")
    _login_admin(client, admin_user)
    r = client.post("/admin/settings", data={"whatsapp_group_url": "https://chat.whatsapp.com/NEU 123"},
                    follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Leerzeichen" in html
    assert get_setting("whatsapp_group_url", "") == ""


def test_startseite_zeigt_wa_eingang_nur_mit_hinterlegtem_link(auth_client, db):
    """Ohne Eintrag rendert die Startseite keine Zeile; mit Eintrag die ruhige .wa-quiet-Zeile."""
    html = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "wa-quiet" not in html

    set_setting("whatsapp_group_url", GROUP_LINK)
    html = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert 'class="wa-quiet"' in html
    assert f'href="{GROUP_LINK}"' in html
    # Finalform aus Update (34): nur Logo + Linktext, ohne Untertitel.
    assert "In die WhatsApp-Gruppe der Tipprunde" in html
    assert "Los-Tausch" not in html


def test_startseite_und_mehr_ignorieren_unsichere_linkschemata(auth_client, db):
    """Schema-Gate: ein javascript:-Wert in der DB wird weder auf Startseite noch Mehr-Seite ausgegeben."""
    set_setting("whatsapp_group_url", "javascript:alert(1)")
    for path in ("/", "/mehr"):
        html = auth_client.get(path, follow_redirects=True).get_data(as_text=True)
        assert "wa-quiet" not in html
        assert "javascript:alert(1)" not in html
        assert 'href="javascript' not in html


def test_mehr_seite_zeigt_whatsapp_karte_nur_mit_hinterlegtem_link(auth_client, db):
    """Mehr-Seite: Kachel mit Gruppenlink erscheint nur, wenn der Link hinterlegt ist."""
    html = auth_client.get("/mehr").get_data(as_text=True)
    assert "WhatsApp-Gruppe" not in html

    set_setting("whatsapp_group_url", GROUP_LINK)
    html = auth_client.get("/mehr").get_data(as_text=True)
    assert "WhatsApp-Gruppe" in html
    assert f'href="{GROUP_LINK}"' in html
