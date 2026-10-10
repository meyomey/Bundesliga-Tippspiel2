"""Tests: Erinnerungs-Zeiten in deutscher Lokalzeit ((109)).

Nutzerbefund: der Digest zeigte fuer alle Spiele „10.10. 13:30“ — real
stossen sie um 15:30 deutscher Zeit an. Kickoffs liegen NAIV in UTC in
der DB; die UI rechnet via de_local-Filter nach Europe/Berlin, die
Benachrichtigungen formatierten den Rohstempel. Seit (109) nutzen alle
drei Textstellen (Digest-Zeile, Einzel-Erinnerung, Test-Benachrichtigung)
denselben Berlin-Helper.
"""
from datetime import datetime

from models import Match

from notification_center import _berlin_fmt, _digest_zeile, reminder_message


def test_sommerzeit_cest_utc_plus_2():
    """13:30 UTC (naiv, wie in der DB) -> 15:30 CEST."""
    assert _berlin_fmt(datetime(2026, 10, 10, 13, 30)) == "10.10. 15:30"


def test_winterzeit_cet_utc_plus_1():
    """Auch im Winter korrekt: 14:30 UTC -> 15:30 CET."""
    assert _berlin_fmt(datetime(2026, 12, 5, 14, 30)) == "05.12. 15:30"


def test_digest_zeile_und_erinnerung_deutsch(db, competition, teams):
    """Die nutzersichtbaren Texte zeigen 15:30, nie die UTC-13:30."""
    m = Match(competition_id=competition.id, matchday=5,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime(2026, 10, 10, 13, 30), status="scheduled")
    db.session.add(m)
    db.session.flush()

    zeile = _digest_zeile(m)
    assert "15:30" in zeile
    assert "13:30" not in zeile
    assert zeile.startswith("• 1. FC Bayern München – Borussia Dortmund") or \
        zeile.startswith("• ")

    nachricht = reminder_message(m)
    assert "15:30" in nachricht
    assert "13:30" not in nachricht


def test_ohne_kickoff_kehrzeichen():
    """Kein Kickoff -> "?" statt Absturz (wie bisher)."""
    assert _berlin_fmt(None) == "?"
