"""Robustheitstests fuer den Telegram-Bot ((82), Kandidat 5).

Deckt die bisher ungetesteten Pfade ab: Token-Pruefung (ungueltig/fremd),
Tip-Fehlerpfade, Aktualisieren statt Duplizieren, Joker-Umzug, Rangliste/
Spielplan/Meine-Tipps-Ausgaben, Dispatch unbekannter Kommandos sowie
send_telegram_message/notify_user_telegram inkl. Netzwerkfehler.
"""
from datetime import datetime, timedelta, timezone

import pytest

from config import TestConfig
from extensions import db
from models import Match, Prediction, Team, User
from scoring import set_setting
from telegram_bot import (generate_telegram_token, notify_user_telegram,
                          process_message, verify_telegram_token)


@pytest.fixture
def tg_user(db, user):
    """Ganz normaler Spieler, verknuepft mit Telegram-Chat 424242."""
    user.phone = "tg:424242"
    db.session.commit()
    return user


@pytest.fixture
def anstoss(db, competition, teams):
    """Zukuenftiges Spiel FCB-BVB (Spieltag 1) im Test-Wettbewerb."""
    monkey_comp = competition
    m = Match(competition_id=monkey_comp.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=5),
              status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture
def gepinnt(app, competition, monkeypatch):
    """Aktiven Wettbewerb pinnen (Falle aus Runde 79: Fallback BL1)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)


# ------------------------------------------------------------ Token

def test_token_ungueltig_fremder_zweck_abgelaufen(app, db, user):
    """Nur Tokens mit Zweck 'telegram' und ohne Ueberschreitung gelten."""
    with app.app_context():
        assert verify_telegram_token("quatsch-mit-soesse") is None
        token = generate_telegram_token(user.id)
        assert verify_telegram_token(token) == user.id
        # Fremder Zweck (hier: manipulierter Payload via anderem Serializer)
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        fremd = s.dumps({"user_id": user.id, "purpose": "sonstwas"},
                        salt="telegram-link")
        assert verify_telegram_token(fremd) is None
        assert verify_telegram_token(token, max_age=-1) is None


def test_start_mit_kaputtem_token_weist_ab(app, db, user, gepinnt):
    """/start mit Muell-Token verlinkt NICHT und aendert kein Telefon."""
    with app.app_context():
        antwort = process_message(424242, "/start quatsch-mit-soesse")
    assert "Ungueltiger oder abgelaufener Token" in antwort
    assert user.phone is None


# ------------------------------------------------------------ /tipp

def test_tip_ohne_verknuepfung_abgewiesen(app, db, gepinnt):
    with app.app_context():
        assert process_message(99999, "/tipp FCB-BVB 2:1") == "Du bist nicht verknuepft."


def test_tip_formatfehler_alle_abgefangen(app, db, tg_user, anstoss, gepinnt):
    """Fehlende Args, Unsinn-Tore, ausserhalb 0-30, unbekanntes Kuerzel."""
    with app.app_context():
        assert "Format" in process_message(424242, "/tipp")
        assert "Format" in process_message(424242, "/tipp FCB-BVB")
        assert "Ungueltige Tore" in process_message(424242, "/tipp FCB-BVB zwei:1")
        assert "zwischen 0 und 30" in process_message(424242, "/tipp FCB-BVB 31:0")
        assert "Team nicht gefunden" in process_message(424242, "/tipp XYZ-QQQ 1:1")


def test_tip_ohne_passendes_spiel(app, db, tg_user, teams, gepinnt):
    """Kuerzel existieren, aber kein anstehendes Spiel der Paarung."""
    with app.app_context():
        antwort = process_message(424242, "/tipp FCB-BVB 2:1")
    assert "Kein anstehendes Spiel" in antwort


def test_tip_speichert_und_aktualisiert_ohne_duplikat(app, db, tg_user, anstoss, gepinnt):
    """Erster Tipp speichert, zweiter aktualisiert dieselbe Prediction."""
    with app.app_context():
        erste = process_message(424242, "/tipp FCB-BVB 2:1")
        assert "gespeichert" in erste
        zweite = process_message(424242, "/tipp FCB-BVB 1:0")
        assert "aktualisiert" in zweite
        preds = Prediction.query.filter_by(user_id=tg_user.id,
                                           match_id=anstoss.id).all()
        assert len(preds) == 1
        assert preds[0].home_tip == 1 and preds[0].away_tip == 0


def test_tip_mit_joker_entzieht_joker_der_paarung(app, db, tg_user, anstoss, competition, teams, gepinnt):
    """Nur ein Joker je Spieltag: der alte Joker im selben Spieltag faellt."""
    zweites = Match(competition_id=competition.id, matchday=1,
                    home_team_id=teams[2].id, away_team_id=teams[3].id,
                    kickoff=datetime.now(timezone.utc) + timedelta(hours=6),
                    status="scheduled")
    db.session.add(zweites)
    db.session.commit()
    with app.app_context():
        erste = process_message(424242, "/tipp B04-RBL 0:0 joker")
        assert "gespeichert" in erste
        p2 = Prediction.query.filter_by(user_id=tg_user.id,
                                        match_id=zweites.id).first()
        assert p2.joker is True
        antwort = process_message(424242, "/tipp FCB-BVB 2:1 joker")
        assert "gespeichert" in antwort
        p2 = Prediction.query.filter_by(user_id=tg_user.id,
                                        match_id=zweites.id).first()
        p1 = Prediction.query.filter_by(user_id=tg_user.id).join(
            Match).filter(Match.away_team_id == teams[1].id).first()
        assert p2.joker is False and p1.joker is True


# ------------------------------------------------------------ Ausgaben

def test_rangliste_zeigt_marker_du(app, db, tg_user, anstoss, gepinnt):
    with app.app_context():
        anstoss.kickoff = datetime.now(timezone.utc) - timedelta(hours=5)
        anstoss.status = "finished"
        anstoss.home_score, anstoss.away_score = 2, 1
        pred = Prediction(user_id=tg_user.id, match_id=anstoss.id,
                          home_tip=2, away_tip=1, joker=False, points=4)
        db.session.add(pred)
        db.session.commit()
        antwort = process_message(424242, "/rangliste")
    assert "Top 10 Rangliste" in antwort
    assert "<< DU" in antwort and tg_user.username in antwort


def test_meine_tipps_zeigt_joker_und_fehlstellen(app, db, tg_user, competition, teams, anstoss, gepinnt):
    """Gesetzter Tipp mit Joker + offene Paarung als 'kein Tipp'."""
    zweites = Match(competition_id=competition.id, matchday=1,
                    home_team_id=teams[2].id, away_team_id=teams[3].id,
                    kickoff=datetime.now(timezone.utc) + timedelta(hours=6),
                    status="scheduled")
    db.session.add(zweites)
    pred = Prediction(user_id=tg_user.id, match_id=anstoss.id,
                      home_tip=2, away_tip=1, joker=True)
    db.session.add(pred)
    db.session.commit()
    with app.app_context():
        antwort = process_message(424242, "/meine_tipps")
    assert "Spieltag 1 - Deine Tipps" in antwort
    assert "FCB vs BVB: 2:1 (Joker)" in antwort
    assert "B04 vs RBL: kein Tipp" in antwort


def test_spielplan_zeigt_ergebnisse(app, db, tg_user, anstoss, gepinnt):
    anstoss.status = "finished"
    anstoss.home_score, anstoss.away_score = 3, 2
    db.session.commit()
    with app.app_context():
        antwort = process_message(424242, "/spielplan")
    assert "Spieltag 1:" in antwort and " 3:2 " in antwort


# ------------------------------------------------------------ /joker

def test_joker_ohne_tipp_zuerst_abgewiesen(app, db, tg_user, anstoss, gepinnt):
    with app.app_context():
        antwort = process_message(424242, "/joker FCB-BVB")
    assert "Bitte erst tippen" in antwort


def test_joker_setzt_und_formatfehler(app, db, tg_user, anstoss, gepinnt):
    with app.app_context():
        db.session.add(Prediction(user_id=tg_user.id, match_id=anstoss.id,
                                  home_tip=1, away_tip=1, joker=False))
        db.session.commit()
        assert "Format" in process_message(424242, "/joker")
        assert "Format" in process_message(424242, "/joker FCB")
        assert "Team nicht gefunden" in process_message(424242, "/joker QQQ-XYZ")
        ok = process_message(424242, "/joker FCB-BVB")
    assert "⚡ Joker gesetzt" in ok


# ------------------------------------------------------------ Dispatch

def test_dispatch_hilfe_unbekannt_und_leer(app, db, gepinnt):
    with app.app_context():
        hilfe = process_message(1, "/hilfe")
        assert "/start TOKEN" in hilfe and "/joker FCB-BVB" in hilfe
        assert process_message(1, "/unsinn") is None
        assert process_message(1, "") is None
        assert process_message(1, None) is None
        # Alias /tip funktioniert wie /tipp (Fehlerpfad reicht als Beweis)
        assert "Du bist nicht verknuepft" in process_message(1, "/tip FCB-BVB 2:1")


# ------------------------------------------------------------ Versand

def test_senden_ohne_token_bricht_still_ab(app, db):
    with app.app_context():
        set_setting("telegram_bot_token", "")
        from telegram_bot import send_telegram_message
        assert send_telegram_message("4711", "Hallo") is False


def test_senden_netzwerkfehler_wird_gefasst(app, db, monkeypatch):
    """Telegram-API-Ausfall → False statt Crash (Dauerregel 2: still)."""
    def explodiert(*a, **k):
        raise ConnectionError("Netz weg")
    monkeypatch.setattr("requests.post", explodiert)
    with app.app_context():
        set_setting("telegram_bot_token", "TESTTOKEN")
        from telegram_bot import send_telegram_message
        assert send_telegram_message("4711", "Hallo") is False


def test_senden_erfolg_und_notify_filter(app, db, tg_user, monkeypatch):
    """Erfolgsfall True; notify lehnt Nicht-Telegram-Handys ab."""
    class FauxResp:
        ok = True
    gesehen = {}
    def faux_post(url, json=None, timeout=None):
        gesehen["url"] = url
        gesehen["chat"] = json["chat_id"]
        return FauxResp()
    monkeypatch.setattr("requests.post", faux_post)
    with app.app_context():
        set_setting("telegram_bot_token", "TESTTOKEN")
        from telegram_bot import send_telegram_message
        assert send_telegram_message("4711", "Hallo") is True
        assert gesehen["chat"] == "4711" and "TESTTOKEN" in gesehen["url"]
        andrer = User(username="hn", email="hn@example.com",
                      phone="+491701234567")
        andrer.set_password("geheim123")
        db.session.add(andrer)
        db.session.commit()
        assert notify_user_telegram(andrer, "Hallo") is False
        assert notify_user_telegram(None, "Hallo") is False
