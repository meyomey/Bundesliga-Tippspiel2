"""Admin-Smoke-Tests fuer wichtige Verwaltungsbereiche.

Diese Tests decken bewusst pragmatische Admin-Flows ab, die im Betrieb auf
Netcup/Plesk wichtig sind: Spielerfilter, Einladungen, Sonderfragen, Bots und
Saisonwechsel-Seite. Ziel ist, Regressionen/500er frueh zu erkennen.
"""
from datetime import datetime, timedelta, timezone

from models import InvitationCode, SpecialQuestion, User


def _login_admin(client, admin_user):
    client.post(
        "/auth/login",
        data={"email": admin_user.email, "password": "admin123"},
        follow_redirects=True,
    )


def test_admin_users_filter_accounts_players_bots_and_admin(client, db, admin_user):
    """Spielerverwaltung: Filter zeigen Konten, Spieler, Bots und Verwaltung."""
    player = User(username="PlayerOne", email="player1@example.com")
    player.set_password("testpass123")
    bot = User(username="SmokeBot", email="smokebot@bot.local")
    bot.set_password("testpass123")
    manager = User(username="ManagerOnly", email="manager@example.com", is_admin=True)
    manager.set_password("testpass123")
    db.session.add_all([player, bot, manager])
    db.session.commit()

    _login_admin(client, admin_user)

    resp_all = client.get("/admin/users")
    assert resp_all.status_code == 200
    assert b"Konten gesamt" in resp_all.data
    assert b"PlayerOne" in resp_all.data
    assert b"SmokeBot" in resp_all.data
    assert b"ManagerOnly" in resp_all.data

    resp_players = client.get("/admin/users?filter=players")
    assert resp_players.status_code == 200
    assert b"PlayerOne" in resp_players.data
    assert b"SmokeBot" not in resp_players.data
    assert b"ManagerOnly" not in resp_players.data

    resp_bots = client.get("/admin/users?filter=bots")
    assert resp_bots.status_code == 200
    assert b"SmokeBot" in resp_bots.data
    assert b"PlayerOne" not in resp_bots.data

    resp_admin = client.get("/admin/users?filter=admin")
    assert resp_admin.status_code == 200
    assert b"ManagerOnly" in resp_admin.data
    assert b"PlayerOne" not in resp_admin.data


def test_admin_invitations_create_deactivate_delete_smoke(client, db, admin_user):
    """Einladungscodes: Admin kann anzeigen, erstellen, deaktivieren, loeschen."""
    _login_admin(client, admin_user)

    resp = client.get("/admin/invitations")
    assert resp.status_code == 200
    assert "Einladung".encode("utf-8") in resp.data

    resp = client.post(
        "/admin/invitations/create",
        data={"email": "invitee@example.com", "max_uses": "1", "days": "14"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    invite = InvitationCode.query.filter_by(email="invitee@example.com").first()
    assert invite is not None
    assert invite.max_uses == 1

    resp = client.post(f"/admin/invitations/{invite.id}/deactivate", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(invite)
    assert invite.uses >= invite.max_uses

    invite_id = invite.id
    resp = client.post(f"/admin/invitations/{invite_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(InvitationCode, invite_id) is None


def test_admin_special_question_create_and_answer_smoke(client, db, admin_user, competition):
    """Sonderfragen: Admin kann Frage anlegen und korrekte Antwort setzen."""
    _login_admin(client, admin_user)

    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
    resp = client.post(
        "/admin/special-questions",
        data={
            "text": "Wird der Herbstmeister Meister?",
            "description": "Smoke-Test",
            "answer_type": "yes_no",
            "options": "",
            "multi_count": "1",
            "number_min": "",
            "number_max": "",
            "deadline": deadline,
            "points_value": "10",
            "correct_answer": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    q = SpecialQuestion.query.filter_by(text="Wird der Herbstmeister Meister?").first()
    assert q is not None
    assert q.answer_type == "yes_no"

    resp = client.post(
        f"/admin/special-question/{q.id}/answer",
        data={"correct_answer": "Ja"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(q)
    assert q.correct_answer == "Ja"


def test_admin_bots_page_smoke(client, admin_user, competition):
    """Bot-Verwaltung: Seite laedt ohne 500er und zeigt Kerntexte."""
    _login_admin(client, admin_user)
    resp = client.get("/admin/bots")
    assert resp.status_code == 200
    assert "KI".encode("utf-8") in resp.data or b"Bot" in resp.data


def test_admin_new_season_page_smoke(client, admin_user, competition):
    """Saisonwechsel-Seite: Sicherheitsseite laedt ohne 500er."""
    _login_admin(client, admin_user)
    resp = client.get("/admin/new-season")
    assert resp.status_code == 200
    assert "Saison".encode("utf-8") in resp.data


def test_admin_prizes_create_edit_delete_smoke(client, db, admin_user, competition):
    """Preise/Pott: Admin kann Preis anlegen, bearbeiten und loeschen."""
    from models import Prize

    _login_admin(client, admin_user)

    resp = client.get("/admin/prizes")
    assert resp.status_code == 200
    assert "Preise".encode("utf-8") in resp.data or b"Pott" in resp.data

    data = {
        "rank": "1",
        "title": "Smoke Preis",
        "description": "Automatischer Testpreis",
        "icon": "🏆",
        "color": "#fbbf24",
        "amount": "10 €",
        "detail": "Testdetail",
        "active": "y",
        "sort_order": "1",
    }
    resp = client.post("/admin/prizes/new", data=data, follow_redirects=True)
    assert resp.status_code == 200
    prize = Prize.query.filter_by(title="Smoke Preis").first()
    assert prize is not None
    assert prize.amount == "10 €"

    data["title"] = "Smoke Preis bearbeitet"
    data["amount"] = "20 €"
    resp = client.post(f"/admin/prizes/{prize.id}/edit", data=data, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(prize)
    assert prize.title == "Smoke Preis bearbeitet"
    assert prize.amount == "20 €"

    prize_id = prize.id
    resp = client.post(f"/admin/prizes/{prize_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(Prize, prize_id) is None


def test_admin_maintenance_page_and_run_smoke(client, admin_user, monkeypatch):
    """Wartungscenter: Seite laedt und Wartungslauf ruft Repair-Task ohne 500er auf."""
    import maintenance

    _login_admin(client, admin_user)

    resp = client.get("/admin/maintenance")
    assert resp.status_code == 200
    assert "Wartungscenter".encode("utf-8") in resp.data

    called = {}

    def fake_run_repair_tasks(task):
        called["task"] = task
        return {"ok": True, "message": f"fake {task}"}

    monkeypatch.setattr(maintenance, "run_repair_tasks", fake_run_repair_tasks)
    resp = client.post(
        "/admin/maintenance/run",
        data={"task": "points"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert called["task"] == "points"
    assert b"fake points" in resp.data or "Wartungscenter".encode("utf-8") in resp.data


def test_admin_player_preview_mode_hides_admin_and_can_exit(client, db, admin_user):
    """Admin kann die App in Spieleransicht ansehen und wieder verlassen."""
    from scoring import set_setting

    admin_user.has_paid = True
    db.session.commit()
    set_setting('payment_info_title', 'Zahlung testen')
    set_setting('payment_info_text', 'Bitte per PayPal an paypal.me/test zahlen')

    _login_admin(client, admin_user)

    resp = client.get('/admin/player-preview/start', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Spieleransicht aktiv'.encode('utf-8') in resp.data
    assert b'player-preview-banner' in resp.data
    # In der Spieleransicht soll ein Admin auch die Zahlungsbox fuer offene Spieler sehen.
    assert b'payment-reminder-card' in resp.data
    assert b'paypal.me/test' in resp.data

    # Direkter Admin-Aufruf wird in der Vorschau abgefangen.
    resp = client.get('/admin/', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Spieleransicht ist aktiv'.encode('utf-8') in resp.data

    resp = client.get('/admin/player-preview/end', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Admin-Bereich'.encode('utf-8') in resp.data
