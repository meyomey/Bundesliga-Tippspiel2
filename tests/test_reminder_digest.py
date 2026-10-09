"""Digest-Reminder ((100)): E-Mail + WhatsApp als EINE Nachricht pro User.

Anlass (Nutzerfeedback + Screenshot): fuer 4 Spiele desselben Spieltags
kamen 4 einzelne WhatsApp-Nachrichten. Jetzt fasst ein Zyklus alle
tipppflichtigen Spiele des Fensters in EINE Mail + EINE WhatsApp zusammen
(mit Link); Push/Telegram bleiben spielweise. Dedup bleibt spielgenau.
"""
from datetime import datetime, timedelta, timezone

import pytest

from models import Match, NotificationLog, Prediction, User
import notification_center
from notification_center import run_reminder_cycle


def _login(_c, *_a):
    return None


def _mk_user(db, **kw):
    u = User(username="digestuser", email="digest@example.com",
             notify_enabled=True, notify_email=True,
             notify_push=False, notify_telegram=False, notify_whatsapp=True,
             whatsapp_phone="+4917612345678", whatsapp_apikey="key123",
             notify_hours_before=kw.get("hours", 24))
    u.set_password("x")
    db.session.add(u)
    return u


def _mk_match(db, competition, teams, hours_ahead, matchday=5):
    m = Match(competition_id=competition.id, matchday=matchday,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=hours_ahead),
              status="scheduled")
    db.session.add(m)
    db.session.flush()
    return m


@pytest.fixture
def digest_env(app, db, monkeypatch, competition, teams):
    """User + 4 offene Spiele im Fenster (Screenshot-Lage), Fakes für Versand."""
    mails = []
    was = []
    tele = []
    monkeypatch.setattr("mail_helpers.send_email",
                        lambda s, r, b, html=None: mails.append((s, b)) or True)
    monkeypatch.setattr("whatsapp.send_whatsapp_message",
                        lambda phone, key, text: was.append(text) or True)
    monkeypatch.setattr("telegram_bot.notify_user_telegram",
                        lambda u, text: tele.append(text) or True)
    from scoring import set_setting
    set_setting("reminders_force_lead_hours", False)
    set_setting("reminders_second_wave_enabled", False)
    set_setting("reminders_enabled", True)
    set_setting("public_base_url", "https://tipp.example")
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    u = _mk_user(db)
    db.session.commit()
    spiele = [_mk_match(db, competition, teams, h) for h in (2, 5, 9, 20)]
    db.session.commit()
    # Namen JETZT einfangen (Objekte sind spaeter ggf. detached — Session-Falle)
    namen = [m.home_team.name for m in spiele]
    # IDs einfangen: Competition.query.first() wuerde im neuen Context den
    # APP-SEED (BL1) statt der Test-Competition liefern → Match landet im
    # falschen Wettbewerb und wird gefiltert (Debug-Fund, (100)).
    return {"user": u, "mails": mails, "was": was, "tele": tele,
            "spiele": spiele, "namen": namen,
            "comp_id": competition.id,
            "team_ids": [tm.id for tm in teams],
            "team_namen": [tm.name for tm in teams]}


def test_eine_mail_eine_whatsapp_mit_allen_spielen_und_link(app, db, digest_env):
    """Screenshot-Fall: 4 Spiele -> genau 1 Mail + 1 WhatsApp, alle Teams
    drin, CallMeBot-Text enthaelt den Tipp-Link."""
    env = digest_env
    now = datetime.now(timezone.utc)
    with app.app_context():
        total = run_reminder_cycle(now=now)
    assert len(env["mails"]) == 1, "genau EINE E-Mail"
    assert len(env["was"]) == 1, "genau EINE WhatsApp"
    assert len(env["tele"]) == 0, "Telegram blieb ungenannt (Kanal aus)"

    betreff, body = env["mails"][0]
    assert "4 offene Spiele" in betreff
    for name in env["namen"]:
        assert name in body
    assert "Jetzt tippen: https://tipp.example/tippen/5" in body

    wa = env["was"][0]
    assert "👉 Jetzt tippen: https://tipp.example/tippen/5" in wa
    assert wa.count("•") == 4
    # Dedup-Logs bleiben spielgenau (4 Spiele x 2 Kanaele)
    assert NotificationLog.query.filter_by(channel="email", kind="match_reminder").count() == 4
    assert NotificationLog.query.filter_by(channel="whatsapp", kind="match_reminder").count() == 4
    assert total["email"] == 1 and total["whatsapp"] == 1


def test_dedup_zweiter_zyklus_stumm(app, db, digest_env):
    env = digest_env
    with app.app_context():
        run_reminder_cycle(now=datetime.now(timezone.utc))
        n_mail, n_wa = len(env["mails"]), len(env["was"])
        run_reminder_cycle(now=datetime.now(timezone.utc))
    assert (n_mail, n_wa) == (1, 1)
    assert (len(env["mails"]), len(env["was"])) == (1, 1)


def test_neues_spiel_im_fenster_bekommt_eigenen_digest(app, db, digest_env):
    """Nach dem ersten Digest neu im Fenster -> Digest NUR fuer das neue Spiel."""
    env = digest_env
    # Neue Paarung mit FREMDEN Teams (Index 2+3), damit sie von den
    # ersten 4 Spielen (Paarung 0 vs 1) namentlich unterscheidbar ist.
    with app.app_context():
        run_reminder_cycle(now=datetime.now(timezone.utc))
        env["mails"].clear(); env["was"].clear()
        neues = _mk_match_env(db, env, 3, matchday=5, team_idx=(2, 3))
        from extensions import db as _db
        _db.session.commit()
        neuer_name = neues.home_team.name
        run_reminder_cycle(now=datetime.now(timezone.utc))
    assert len(env["mails"]) == 1 and len(env["was"]) == 1
    body = env["mails"][0][1]
    assert "1 Spiel)" in body            # nur das NEUE Spiel im Digest
    assert body.count("•") == 1
    assert neuer_name in body


def _mk_match_env(db, env, hours_ahead, matchday=5, team_idx=(0, 1)):
    """Neues Spiel mit den FIXTURE-IDs (nicht neu abfragen — Session-Falle
    + App-Seed-BL1-Falle). team_idx waehlt die Paarung."""
    m = Match(competition_id=env["comp_id"], matchday=matchday,
              home_team_id=env["team_ids"][team_idx[0]],
              away_team_id=env["team_ids"][team_idx[1]],
              kickoff=datetime.now(timezone.utc) + timedelta(hours=hours_ahead),
              status="scheduled")
    db.session.add(m)
    db.session.flush()
    return m


def test_telegram_auch_als_digest(app, db, digest_env):
    """(101) Telegram gehoert jetzt AUCH zum Digest: 1 Nachricht mit allen
    Spielen + Link — nicht mehr eine pro Spiel."""
    env = digest_env
    u = env["user"]
    u.notify_telegram = True
    from extensions import db as _db
    _db.session.commit()
    with app.app_context():
        run_reminder_cycle(channels=["telegram"], now=datetime.now(timezone.utc))
    assert len(env["tele"]) == 1, "genau EINE Telegram-Nachricht"
    text = env["tele"][0]
    assert "4 Spiele" in text
    assert text.count("•") == 4
    assert "👉 Jetzt tippen: https://tipp.example/tippen/5" in text
    assert len(env["mails"]) == 0 and len(env["was"]) == 0


def test_push_digest_eine_karte_mit_link_und_dedup(app, db, digest_env,
                                                   monkeypatch):
    """(101) Push als kompakte Digest-Karte: Gesamtzahl + relativer
    Digest-Link; zweiter Zyklus bleibt stumm."""
    import json as _json
    env = digest_env
    u = env["user"]
    u.notify_push = True
    u.push_subscription = _json.dumps({"endpoint": "https://push.example/x"})
    from extensions import db as _db
    _db.session.commit()
    aufgerufe = []
    monkeypatch.setattr("push_routes._send_push_to_users",
                        lambda users, payload:
                        aufgerufe.append(payload) or (len(users), 0))
    with app.app_context():
        run_reminder_cycle(channels=["push"],
                           now=datetime.now(timezone.utc))
    assert len(aufgerufe) == 1, "genau EIN Push"
    p = aufgerufe[0]
    assert p["title"] == "⚽ Tipp-Erinnerung"
    assert "4 Spiele" in p["body"]
    assert p["url"] == "/tippen/5"          # Push-URL bleibt relativ
    assert p["tag"].startswith("digest-")
    with app.app_context():
        run_reminder_cycle(channels=["push"],
                           now=datetime.now(timezone.utc))
    assert len(aufgerufe) == 1, "Dedup: zweiter Zyklus sendet nicht erneut"


def test_mehrere_spieltage_link_auf_offene_tipps(app, db, digest_env):
    """Digest ueber 2 Spieltage -> Link auf /meine-offenen-tipps."""
    env = digest_env
    _mk_match_env(db, env, 6, matchday=6)
    from extensions import db as _db
    _db.session.commit()
    with app.app_context():
        run_reminder_cycle(now=datetime.now(timezone.utc))
    body = env["mails"][0][1]
    assert "Jetzt tippen: https://tipp.example/meine-offenen-tipps" in body


def test_manuelle_einzel_erinnerung_whatsapp_mit_link(app, db, digest_env):
    """Admin-Einzelweg (send_user_notification): CallMeBot-Nachricht hat
    jetzt ebenfalls den Link (zweiter Nutzerbefund)."""
    env = digest_env
    u = env["user"]
    m = env["spiele"][0]
    with app.app_context():
        res = notification_center.send_user_notification(
            u, m, channels=["whatsapp"], enforce_window=False)
    assert res["whatsapp"] is True
    wa = env["was"][0]
    assert "👉 Jetzt tippen:" in wa
    assert f"/match/{m.id}" in wa
