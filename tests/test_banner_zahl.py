"""Tests Banner-Zahl ((99)): Spieltags-Scope statt 24-h-Fenster.

Nutzerbefund (Screenshot): Banner sagte „5 ungetippte Spiele offen“,
während Karte + Bottom-Bar 8 offene Tipps für Spieltag 5 zeigten — der
Banner zählte nur Spiele im 24-h-Urgency-Fenster (Nächster Anpfiff in
21h57m). Jetzt zählt der Banner den ganzen Spieltag seines Zielspieltags;
Sichtbarkeitsfenster + Countdown bleiben unangetastet (Feature-B-Design).
"""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Match, Prediction


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def _spiel(db, competition, teams, stunden_bis):
    m = Match(competition_id=competition.id, matchday=5,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(hours=stunden_bis),
              status="scheduled")
    db.session.add(m)
    db.session.flush()
    return m


def _screenshot_lage(db, user, competition, teams):
    """9 Spiele am ST5: 1 getippt, 8 offen — davon 5 im 24-h-Fenster."""
    Within = [21, 22, 23, 23.5, 23.9]          # offen, < 24 h
    Beyond = [30, 36, 40]                       # offen, > 24 h
    spiele = [_spiel(db, competition, teams, h) for h in Within + Beyond]
    getippt = _spiel(db, competition, teams, 22)  # im Fenster, aber getippt
    db.session.add(Prediction(user_id=user.id, match_id=getippt.id,
                              home_tip=2, away_tip=1, joker=False))
    db.session.commit()
    return spiele


def test_banner_zaehlt_ganzen_spieltag_nicht_nur_24h(client, app, db, user,
                                                     competition, teams,
                                                     monkeypatch):
    """Banner sagt 8 (Spieltag), nicht 5 (24-h-Fenster) — deckungsgleich
    mit Karte UND Bottom-Bar."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _screenshot_lage(db, user, competition, teams)
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert "tipreminder-banner" in body
    assert "8 ungetippte Spiele offen" in body
    assert "5 ungetippte" not in body
    # Konsistenz mit den beiden anderen Anzeigen:
    assert "8 offene Tipp(s) für Spieltag 5" in body      # Karte
    assert "Spieltag 5: 1/9 getippt" in body               # Bottom-Bar


def test_banner_wegklickbar_und_weg_auf_zielseiten(client, app, db, user,
                                                   competition, teams,
                                                   monkeypatch):
    """(107) Nutzerbefund „Banner ist fast überall im Weg“: a) er hat ein
    Ausblenden-Kreuz, b) auf Schnelltipp und Spielplan — seinen eigenen
    Zielen — erscheint er gar nicht (dort ist er redundant)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    _screenshot_lage(db, user, competition, teams)
    _login(client, user.email, "testpass123")
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "tipreminder-banner" in dash
    assert 'id="trClose"' in dash and "Banner für heute ausblenden" in dash
    st = client.get("/schnelltipp/5").get_data(as_text=True)
    assert "tipreminder-banner" not in st
    plan = client.get("/spielplan/5").get_data(as_text=True)
    assert "tipreminder-banner" not in plan


def test_banner_ausserhalb_24h_weiterhin_versteckt(client, app, db, user,
                                                   competition, teams,
                                                   monkeypatch):
    """Urgency-Fenster bleibt: kein Spiel < 24 h → kein Banner (auch wenn
    der Spieltag offene Tipps hat)."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    for h in (30, 36, 40, 44, 48, 52, 56, 60):
        _spiel(db, competition, teams, h)
    db.session.commit()
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert "tipreminder-banner" not in body
    assert "Spieltag 5: 0/8 getippt" in body  # Bottom-Bar bleibt informativ


def test_banner_alle_getippt_kein_banner(client, app, db, user, competition,
                                         teams, monkeypatch):
    """Alles getippt → weder Banner noch offene Zahl."""
    monkeypatch.setitem(app.config, "COMPETITION", competition.code)
    for h in (21, 22, 30):
        m = _spiel(db, competition, teams, h)
        db.session.add(Prediction(user_id=user.id, match_id=m.id,
                                  home_tip=1, away_tip=1, joker=False))
    db.session.commit()
    _login(client, user.email, "testpass123")
    body = client.get("/dashboard").get_data(as_text=True)
    assert "tipreminder-banner" not in body
    assert "ungetippte" not in body
