"""Kleine Festdaten-Zeile auf /admin/sync (12.09.2026).

Fruehwarnung fuer neue Aufsteiger: Der Sync merkt Vereine ohne Stadion-Karten-
Treffer; die Admin-Seite zeigt einen Hinweis, der nach Pflege + Sync von
selbst verschwindet. Bewusst Info (kein Warn-Icon) - fehlende statische
Daten sind Pflege, kein Fehler.
"""
from scoring import set_setting


def _login_admin(client, admin_user):
    client.post(
        "/auth/login",
        data={"email": admin_user.email, "password": "admin123"},
        follow_redirects=True,
    )


def test_gap_line_shows_unmapped_clubs(app, client, db, admin_user):
    set_setting("stadium_gap_teams", '["SV 07 Elversberg", "SC Paderborn 07"]')
    _login_admin(client, admin_user)
    html = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "Festdaten-Pflege" in html
    assert "SV 07 Elversberg" in html and "SC Paderborn 07" in html
    # Hinweis, kein Alarm: im direkt folgenden Textabschnitt darf kein Warndreieck stehen
    assert "\u26a0\ufe0f" not in html.split("Festdaten-Pflege")[1][:200]


def test_line_disappears_after_maintenance(app, client, db, admin_user):
    set_setting("stadium_gap_teams", "[]")
    _login_admin(client, admin_user)
    html = client.get("/admin/sync", follow_redirects=True).get_data(as_text=True)
    assert "Festdaten-Pflege" not in html


def test_broken_setting_value_degrades_to_silent(app):
    from sync import get_sync_diagnostics
    with app.app_context():
        set_setting("stadium_gap_teams", "{kaputt")
        assert get_sync_diagnostics()["stadium_gaps"] == []
