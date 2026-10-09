"""Tests rechtliche Stammdaten ((96)): DB statt FTP-Edit.

Anlass: Die per FTP auf dem Server eingetragenen Impressums-/Datenschutz-
Angaben wurden beim Komplett-Deploy vom Repo-Platzhalterstand überschrieben.
Jetzt liegen die Werte als Settings in der Datenbank — deploy-sicher und
in den täglichen Backups enthalten; gepflegt unter Admin → Einstellungen.
"""
from scoring import get_setting, set_setting


def test_seiten_oeffentlich_mit_platzhaltern(client, db):
    """Ohne Einstellungen: 200 + ANPASSEN-Fallback (Erinnerung ans Ausfüllen)."""
    imp = client.get("/impressum")
    ds = client.get("/datenschutz")
    assert imp.status_code == 200 and ds.status_code == 200
    assert imp.get_data(as_text=True).count("ANPASSEN") >= 4
    assert ds.get_data(as_text=True).count("ANPASSEN") >= 2


def test_einstellungen_erscheinen_auf_beiden_seiten(client, db):
    """Gesetzte Werte rendern auf Impressum UND Datenschutz, Platzhalter weg."""
    set_setting("recht_anbieter", "Heinz Wulmstörper")
    set_setting("recht_adresse", "Deichweg 1, 21029 Hamburg")
    set_setting("recht_email", "heinz@wulmstorf.example")
    set_setting("recht_verantw", "Heinz Wulmstörper")

    imp = client.get("/impressum").get_data(as_text=True)
    assert "Heinz Wulmstörper" in imp
    assert "Deichweg 1, 21029 Hamburg" in imp
    assert "heinz@wulmstorf.example" in imp
    assert "ANPASSEN" not in imp

    ds = client.get("/datenschutz").get_data(as_text=True)
    assert "Heinz Wulmstörper" in ds
    assert "heinz@wulmstorf.example" in ds
    assert "ANPASSEN" not in ds


def test_admin_rundtrip_speichert_rechtliches(client, db, admin_user):
    """Admin → Einstellungen zeigt die 4 Felder und speichert sie dauerhaft."""
    assert client.post("/auth/login", data={"email": admin_user.email,
                                            "password": "admin123"},
                       follow_redirects=True).status_code == 200
    body = client.get("/admin/settings").get_data(as_text=True)
    assert "Rechtliche Stammdaten" in body
    assert "recht_anbieter" in body

    resp = client.post("/admin/settings", data={
        "registration_mode": "invite",
        "recht_anbieter": "Test Betreiber",
        "recht_adresse": "Testweg 2, 12345 Teststadt",
        "recht_email": "recht@test.example",
        "recht_verantw": "Test Betreiber",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert get_setting("recht_anbieter") == "Test Betreiber"
    assert get_setting("recht_adresse") == "Testweg 2, 12345 Teststadt"
    assert get_setting("recht_email") == "recht@test.example"

    client.get("/auth/logout")
    imp = client.get("/impressum").get_data(as_text=True)
    assert "Test Betreiber" in imp and "ANPASSEN" not in imp


def test_leere_werte_fallen_auf_platzhalter_zurueck(client, db):
    """Nur teilweise gefüllt: gesetzte Werte da, Rest bleibt Platzhalter."""
    set_setting("recht_anbieter", "Nur Der Betreiber")
    set_setting("recht_adresse", "")
    set_setting("recht_email", "")
    set_setting("recht_verantw", "")
    imp = client.get("/impressum").get_data(as_text=True)
    assert "Nur Der Betreiber" in imp
    assert "ANPASSEN" in imp  # Adresse/E-Mail/Verantw noch offen
