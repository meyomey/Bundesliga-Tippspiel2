"""Test-Runde 3 ((90)): Admin-Badge-Verwaltung (vorher 28 % Coverage)."""
from extensions import db
from models import Badge, UserBadge


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def _badge_form_daten(**overrides):
    data = {"code": "streak5", "name": "5 Siege in Folge",
            "description": "Fuenf Siege hintereinander — Serie!",
            "icon": "🔥", "color": "#fbbf24",
            "trigger_type": "manual", "threshold": "0"}
    data.update(overrides)
    return data


def test_badges_liste_nur_fuer_admin(client, db, user, admin_user):
    """Spieler -> 302; Admin -> 200 mit Seiteninhalt."""
    _login(client, user.email, "testpass123")
    assert client.get("/admin/badges").status_code == 403  # admin_required
    client.get("/auth/logout")
    _login(client, admin_user.email, "admin123")
    resp = client.get("/admin/badges")
    assert resp.status_code == 200
    assert 'Badge' in resp.get_data(as_text=True)


def test_badge_anlegen_und_duplikat_abfangen(client, db, admin_user):
    """Neues Badge wird gespeichert; doppelter Code wird abgewiesen."""
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/badges/new", data=_badge_form_daten(),
                       follow_redirects=True)
    assert resp.status_code == 200
    assert Badge.query.filter_by(code="streak5").count() == 1

    resp = client.post("/admin/badges/new", data=_badge_form_daten(),
                       follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert Badge.query.filter_by(code="streak5").count() == 1
    assert 'bereits vergeben' in body


def test_badge_bearbeiten(client, db, badge, admin_user):
    """Edit-Formular laden und Namen aendern."""
    _login(client, admin_user.email, "admin123")
    resp = client.get(f"/admin/badges/{badge.id}/edit")
    assert resp.status_code == 200
    resp = client.post(f"/admin/badges/{badge.id}/edit",
                       data=_badge_form_daten(name="Erster Tipp ever"),
                       follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(Badge, badge.id).name == "Erster Tipp ever"


def test_badge_award_und_revoke(client, db, badge, admin_user, user):
    """Badge manuell vergeben und wieder entziehen; Seite listet Spieler."""
    _login(client, admin_user.email, "admin123")
    resp = client.get(f"/admin/badges/{badge.id}/award")
    assert resp.status_code == 200
    assert user.username in resp.get_data(as_text=True)

    resp = client.post(f"/admin/badges/{badge.id}/award",
                       data={"action": "award", "user_ids": str(user.id)},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert UserBadge.query.filter_by(user_id=user.id,
                                     badge_id=badge.id).count() == 1

    resp = client.post(f"/admin/badges/{badge.id}/award",
                       data={"action": "revoke", "user_ids": str(user.id)},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert UserBadge.query.filter_by(user_id=user.id,
                                     badge_id=badge.id).count() == 0


def test_badge_loeschen(client, db, badge, admin_user, user):
    """Loeschen entfernt Badge + Vergaben."""
    db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
    db.session.commit()
    _login(client, admin_user.email, "admin123")
    resp = client.post(f"/admin/badges/{badge.id}/delete",
                       follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(Badge, badge.id) is None
    assert UserBadge.query.filter_by(badge_id=badge.id).count() == 0


def test_badge_recheck(client, db, badge, admin_user):
    """Recheck-POST laeuft durch und meldet Erfolg."""
    _login(client, admin_user.email, "admin123")
    resp = client.post("/admin/badges/recheck", follow_redirects=True)
    assert resp.status_code == 200
    assert 'neu geprüft' in resp.get_data(as_text=True)
