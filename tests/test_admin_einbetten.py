# -*- coding: utf-8 -*-
"""(172) Admin-Bereich „Website-Einbettung“ (/admin/einbetten): Copy-Paste-
Snippets für das Ranglisten-Podium auf der Vereins-Website — Live-iFrame
(Hell/Dunkel/Auto) + statische Blöcke. Nutzer-Weg: Admin → API-Sync →
Karte „Website-Einbettung“. Anlass: Nutzer fand die bisher nur als Datei
gelieferte Anleitung im Adminbereich nicht."""


def _als_admin_anmelden(client, db, user):
    user.is_admin = True
    db.session.commit()
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)


def test_admin_einbetten_seite_172(client, db, user):
    """Admin sieht die Seite mit Theme-Tabelle, Live-Snippet (Auto-Höhe)
    und beiden statischen Varianten, jeweils mit Kopier-Knopf."""
    _als_admin_anmelden(client, db, user)
    r = client.get("/admin/einbetten")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Rangliste in die Website einbetten" in body
    assert "/embed/podium?theme=hell" in body      # Live-URL
    assert "wt-embed-hoehe" in body                # Auto-Höhe-Empfänger
    assert "statisch, dunkel" in body and "statisch, hell" in body
    assert body.count("📋 Kopieren") >= 3          # je Block ein Knopf


def test_admin_einbetten_nur_admin_172(client, db, user):
    """Nicht-Admins bekommen 403 (wie überall im Admin-Bereich)."""
    client.post("/auth/login", data={"email": user.email,
                                     "password": "testpass123"},
                follow_redirects=True)
    assert client.get("/admin/einbetten").status_code == 403


def test_sync_karte_verlinkt_einbetten_172(client, db, user):
    """Nutzer-Weg: Auf der Sync-Seite gibt es die Karte „Website-
    Einbettung“ mit Link auf die neue Seite (Auffindbarkeit)."""
    _als_admin_anmelden(client, db, user)
    r = client.get("/admin/sync")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Website-Einbettung" in body
    assert "/admin/einbetten" in body
