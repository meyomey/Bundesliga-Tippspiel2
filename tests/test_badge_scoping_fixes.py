"""(74) Admin-Fund: „Tagessieger“-Badge (perfect_day) und „Spieltagssieger“
(matchday_winner) trotz 0 gewonnener Spieltage. Ursachen:
- perfect_day wertete partielle Spieltage ab (nur 2/9 fertig, alle exakt
  → „perfekt“) — jetzt nur voll abgelaufene Spieltage.
- matchday_winner zählte ALLE Wettbewerbe/Saisons — jetzt wie das Profil
  (aktiver Wettbewerb + aktuelle Saison).
- Badges wurden nie widerrufen → neue Vollrevalidierung (Wartungsaufgabe).
"""
from datetime import datetime, timedelta, timezone

from badges import DEFAULT_BADGES, revalidate_badges
from models import Badge, Competition, Match, MatchdayWinner, Prediction, UserBadge


import pytest


@pytest.fixture(autouse=True)
def badge_saison_laeuft(db):
    """(78): Badge-Trigger sind saison-scoped — die Tests erzeugen Matches im
    September 2026, also läuft das Saison-Label auf '2026/27'."""
    from scoring import set_setting
    set_setting("current_season", "2026/27")


def _match(db, competition, teams, matchday, finished=True, result_h=1, result_a=0):
    m = Match(
        competition_id=competition.id, matchday=matchday,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status="finished" if finished else "scheduled",
        home_score=result_h if finished else None,
        away_score=result_a if finished else None)
    db.session.add(m)
    db.session.commit()
    return m


def _pred(db, user, match, h, a, points=4):
    p = Prediction(user_id=user.id, match_id=match.id, home_tip=h, away_tip=a, points=points)
    db.session.add(p)
    db.session.commit()
    return p


def _badge(db, code, name, trigger, threshold=0):
    b = Badge(code=code, name=name, description="Test", trigger_type=trigger, threshold=threshold)
    db.session.add(b)
    db.session.commit()
    return b


def test_perfect_day_nur_vollstaendige_spieltage(app, db, competition, teams, user):
    """Partieller Spieltag (2 von 9 fertig, beide exakt) ist NICHT perfekt;
    vollständig abgelaufener Spieltag mit allen exakt schon."""
    from badges import _user_qualifies
    app.config["COMPETITION"] = competition.code
    md = 11
    m1 = _match(db, competition, teams, md, result_h=1, result_a=0)
    m2 = _match(db, competition, teams, md, result_h=2, result_a=1)
    for i in range(3, 10):  # restliche 7 Spiele noch angesetzt
        _match(db, competition, teams, md, finished=False)
    _pred(db, user, m1, 1, 0)
    _pred(db, user, m2, 2, 1)
    b = _badge(db, "perfect_t1", "Perfekt T1", "perfect_day")
    assert _user_qualifies(user, b) is False  # alt: True (2/2 exakt)
    # Nun alle 9 fertig + alle exakt
    others = Match.query.filter_by(competition_id=competition.id, matchday=md, status="scheduled").all()
    scores = [(0, 2), (3, 1), (2, 2), (1, 3), (0, 1), (4, 0), (2, 0)]
    for m, (rh, ra) in zip(others, scores):
        m.status = "finished"
        m.home_score, m.away_score = rh, ra
        db.session.add(Prediction(user_id=user.id, match_id=m.id, home_tip=rh, away_tip=ra, points=4))
    db.session.commit()
    assert _user_qualifies(user, b) is True


def test_matchday_winner_badge_scoped_wie_profil(app, db, competition, teams, user):
    """MatchdayWinner-Zeilen aus ANDERER Saison/Wettbewerb zählen nicht;
    die aktuelle Saison im aktiven Wettbewerb schon."""
    from badges import _user_qualifies
    app.config["COMPETITION"] = competition.code
    comp2 = Competition(name="Testliga 2", code="TEST2", season="2025/26")
    db.session.add(comp2)
    db.session.commit()
    b = _badge(db, "mdw_t1", "Spieltagssieger T", "matchday_winner", 1)
    assert _user_qualifies(user, b) is False  # noch keine Zeile
    # Zeile aus anderer Saison (z. B. alte Saison)
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=1,
                                  user_id=user.id, points=10, season="2024/25"))
    # Zeile aus anderem Wettbewerb (aktuelle Saison)
    db.session.add(MatchdayWinner(competition_id=comp2.id, matchday=1,
                                  user_id=user.id, points=10, season="2026/27"))
    db.session.commit()
    assert _user_qualifies(user, b) is False  # alt: True (2 Zeilen gezählt)
    # Korrekte Zeile: aktive Saison + aktiver Wettbewerb
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=2,
                                  user_id=user.id, points=10, season="2026/27"))
    db.session.commit()
    assert _user_qualifies(user, b) is True


def test_revalidate_widerruft_nicht_mehr_verdiente_badges(db, competition, teams, user):
    """Die Wartungs-Vollrevalidierung widerruft Auto-Badges, deren
    Bedingung nicht mehr erfüllt ist (alterstands-Korrektur), und berührt
    manuelle Badges nicht."""
    from badges import award_badge
    b_auto = _badge(db, "rc_auto", "Auto R", "tips_count", 30)
    b_manual = _badge(db, "rc_manual", "Manuell R", "manual")
    award_badge(user, b_auto)
    award_badge(user, b_manual)
    db.session.commit()
    revalidate_badges()
    db.session.commit()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b_auto.id).first() is None
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b_manual.id).first() is not None


def test_seed_name_perfekter_tag():
    """Klärung (74): Der perfect_day-Badge heißt „Perfekter Tag“ —
    „Tagessieger“ war mit „Spieltagssieger“ (matchday_winner) verwechselt."""
    names = {c: n for c, n, *_ in DEFAULT_BADGES}
    assert names["perfect_day"] == "Perfekter Tag"
    assert names["md_winner_1"] == "Spieltagsieger"
