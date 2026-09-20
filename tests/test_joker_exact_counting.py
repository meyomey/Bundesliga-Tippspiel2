"""(73) Spieler-Fund: In der Tagessieg-Auswertung zählten Joker-Tipps mit
2+2=4 Punkten fälschlich als „exakte Treffer“ (Punktewert statt
Endstand-Klassifikation). Gleiches Muster saß in Badges, Bot-Analyse und
AI-Op-Rangliste. Exakt = Endstand exakt — Joker verdoppelt nur die Punkte.
"""
from datetime import datetime, timedelta, timezone

from models import Badge, Match, Prediction, User
from scoring import recompute_matchday_winners


def _match(db, competition, teams, matchday, result_h, result_a):
    m = Match(
        competition_id=competition.id, matchday=matchday,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status="finished", home_score=result_h, away_score=result_a)
    db.session.add(m)
    db.session.commit()
    return m


def _pred(db, user, match, h, a, points, joker=False):
    p = Prediction(user_id=user.id, match_id=match.id,
                   home_tip=h, away_tip=a, points=points, joker=joker)
    db.session.add(p)
    db.session.commit()
    return p


def _winner(db, user, matchday):
    from models import MatchdayWinner
    return (MatchdayWinner.query
            .filter_by(user_id=user.id, matchday=matchday).all())


def test_tagessieg_joker_vier_punkte_kein_exakter_treffer(app, db, competition, teams, user):
    """Szenario des Spielers: Tipp 2:2 (Tendenz, 2 P) mit Joker = 4 P gesamt.
    Die Tagessieg-Zeile darf exact_count=0 haben — nicht 1."""
    app.config["COMPETITION"] = competition.code
    m = _match(db, competition, teams, 5, 3, 1)  # Tendenz-Treffer
    _pred(db, user, m, 2, 2, points=4, joker=True)
    recompute_matchday_winners()
    rows = _winner(db, user, 5)
    assert len(rows) == 1
    assert rows[0].points == 4
    assert rows[0].exact_count == 0  # alt: 1 (Punkte >= 4)


def test_tagessieg_tiebreak_exakter_endstand_schlaegt_joker_vierer(app, db, competition, teams, user):
    """Gleichstand über Punkte (4:4) → Tiebreak über EXAKTE Treffer:
    der echte 4er (Endstand exakt) muss den Joker-4er (2+2) schlagen."""
    app.config["COMPETITION"] = competition.code
    from models import MatchdayWinner
    user2 = User(username="user2", email="u2@example.com", full_name="Zwei")
    user2.set_password("pw123456")
    db.session.add(user2)
    db.session.commit()
    m1 = _match(db, competition, teams, 6, 3, 1)
    m2 = _match(db, competition, teams, 6, 1, 0)
    _pred(db, user, m1, 2, 2, points=4, joker=True)   # Joker-Tendenz: 2+2
    _pred(db, user2, m2, 1, 0, points=4)              # Endstand exakt
    recompute_matchday_winners()
    winners = (MatchdayWinner.query.filter_by(matchday=6).all())
    assert len(winners) == 1
    assert winners[0].user_id == user2.id
    assert winners[0].exact_count == 1
    assert winners[0].is_shared is False
    assert _winner(db, user, 6) == []


def test_badge_exact_count_zaehlt_nur_endstaende(db, competition, teams, user):
    """„X exakte Tipps“-Badge: Joker-doppelte 2er-Tipps (4 P) zählen nicht."""
    from badges import _user_qualifies
    m1 = _match(db, competition, teams, 7, 2, 1)
    m2 = _match(db, competition, teams, 7, 3, 1)
    m3 = _match(db, competition, teams, 7, 1, 1)
    m4 = _match(db, competition, teams, 7, 2, 1)
    _pred(db, user, m1, 2, 1, points=4)               # exakt
    _pred(db, user, m2, 3, 0, points=4, joker=True)   # Joker-Tendenz (2+2) — nicht exakt
    _pred(db, user, m3, 1, 1, points=4)               # exakt
    _pred(db, user, m4, 2, 1, points=4)               # exakt
    b = Badge(code="x_exakt", name="X exakt", description="Test", trigger_type="exact_count", threshold=3)
    db.session.add(b)
    db.session.commit()
    assert _user_qualifies(user, b) is True           # 3 echte exakte Treffer
    b.threshold = 4
    assert _user_qualifies(user, b) is False          # Joker-4er zählt nicht mit


def test_badge_joker_exact_verlangt_joker_plus_endstand(db, competition, teams, user):
    """joker_exact: Joker + Diff (3+3=6 P) genügt NICHT, Joker + exakt schon."""
    from badges import _user_qualifies
    m1 = _match(db, competition, teams, 8, 3, 1)
    m2 = _match(db, competition, teams, 8, 2, 2)
    _pred(db, user, m1, 4, 2, points=6, joker=True)   # Joker-Diff: 3+3
    b = Badge(code="joker_exact", name="Joker exakt", description="Test", trigger_type="joker_exact")
    db.session.add(b)
    db.session.commit()
    assert _user_qualifies(user, b) is False          # alt: True (6 >= 4)
    _pred(db, user, m2, 2, 2, points=8, joker=True)   # Joker-Exakt: 4+4
    assert _user_qualifies(user, b) is True


def test_badge_perfect_day_zaehlt_nur_endstaende(app, db, competition, teams, user):
    """perfect_day: Spieltag mit exakt + Joker-2er (4 P) ist NICHT perfekt."""
    app.config["COMPETITION"] = competition.code
    from badges import _user_qualifies
    m1 = _match(db, competition, teams, 9, 2, 1)
    m2 = _match(db, competition, teams, 9, 3, 1)
    _pred(db, user, m1, 2, 1, points=4)               # exakt
    _pred(db, user, m2, 2, 2, points=4, joker=True)   # Joker-Tendenz (2+2)
    b = Badge(code="perfect", name="Perfekt", description="Test", trigger_type="perfect_day")
    db.session.add(b)
    db.session.commit()
    assert _user_qualifies(user, b) is False          # alt: True (alle >= 4)
    # Positiv-Kontrolle auf eigenem Spieltag: alle Endstaende exakt
    m3 = _match(db, competition, teams, 10, 0, 2)
    m4 = _match(db, competition, teams, 10, 1, 1)
    _pred(db, user, m3, 0, 2, points=4)
    _pred(db, user, m4, 1, 1, points=4)
    assert _user_qualifies(user, b) is True
