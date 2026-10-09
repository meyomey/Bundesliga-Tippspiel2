"""Tests Bundesliga-Tabelle: deutsche Form-Kuerzel ((108)).

Nutzerbefund (Screenshot): die FORM-Spalte zeigte englische Kuerzel
W/D/L — Spielplan, Schnelltipp und Spielbericht uebersetzen dieselben
Feed-Buchstaben bereits zu S/U/N; die Tabelle war der letzte Ausreisser.
Die Anzeige wird uebersetzt, die Feed-Daten (und CSS-Klassen form-W/D/L
als Style-Anker) bleiben unveraendert — serverseitig UND im
Auto-Refresh-Pfad (JavaScript).
"""
from types import SimpleNamespace


def _login(client, email, passwort):
    return client.post("/auth/login", data={"email": email,
                                            "password": passwort},
                       follow_redirects=True)


def _fd_zeile():
    """Eine Tabellenzeile im football-data-Format (inkl. form)."""
    return {
        "rank": 1,
        "team": SimpleNamespace(name="Borussia Dortmund",
                                short_name="BVB",
                                logo="/static/team_logos/bvb.png"),
        "team_logo": "/static/team_logos/bvb.png",
        "team_name": "Borussia Dortmund", "team_short": "BVB",
        "played": 5, "won": 4, "drawn": 1, "lost": 0,
        "goals_for": 11, "goals_against": 4, "goal_diff": 7,
        "form": "L,W,D,W,W", "points": 13,
    }


def test_tabelle_zeigt_deutsche_form_kuerzel(client, db, user, monkeypatch):
    """Serverseitiger Render: S/U/N statt W/D/L — Feed-Klassen bleiben."""
    # Route bindet den Namen beim Import lokal -> hier patchen, nicht sync.*
    monkeypatch.setattr("main_stats_routes.fetch_live_standings",
                        lambda: ([_fd_zeile()], None))
    _login(client, user.email, "testpass123")
    body = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert 'form-dot form-W">S</span>' in body      # Sieg
    assert 'form-dot form-D">U</span>' in body      # Unentschieden
    assert 'form-dot form-L">N</span>' in body      # Niederlage
    # keine englischen Kuerzel mehr sichtbar:
    assert 'form-dot form-W">W' not in body
    assert 'form-dot form-D">D' not in body
    assert 'form-dot form-L">L' not in body


def test_tabelle_auto_refresh_uebersetzt_auch(client, db, user, monkeypatch):
    """JS-Auto-Refresh (rowHtml) kennt dieselbe Uebersetzung (FORM_DE)."""
    monkeypatch.setattr("main_stats_routes.fetch_live_standings",
                        lambda: ([_fd_zeile()], None))
    _login(client, user.email, "testpass123")
    body = client.get("/bundesliga-tabelle").get_data(as_text=True)
    assert "FORM_DE" in body and "W: 'S'" in body
