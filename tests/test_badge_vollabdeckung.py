# -*- coding: utf-8 -*-
"""Badge-Vollabdeckung: alle 13 Badge-Definitionen + Winner-Recompute + Mechanik.

Ergaenzt die Fix-Tests aus test_joker_exact_counting.py / test_badge_scoping_fixes.py
um die bislang unbeleuchteten Trigger (first_tip, tips_count, total_points,
Schwellen-Grenzfaelle) und Mechanik-Garantien (Idempotenz, Manuell-Schutz,
Revalidierung in beide Richtungen, users-Listen-Begrenzung).
"""
import pytest
from datetime import datetime, timedelta, timezone

from models import (
    User, Match, Competition, Prediction, Badge, UserBadge, MatchdayWinner,
)


# ----------------------------------------------------------------- Fixtures --
@pytest.fixture(scope="function")
def user2(db):
    u = User(username="probetester2", email="probetester2@example.com",
             full_name="Probe Zwei")
    u.set_password("testpass123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture(autouse=True)
def badge_saison_laeuft(db):
    """(78): Badge-Trigger sind saison-scoped — die Tests erzeugen Matches im
    September 2026, also läuft das Saison-Label auf '2026/27'."""
    from scoring import set_setting
    set_setting("current_season", "2026/27")


@pytest.fixture(scope="function")
def seeded(db):
    """Seedet die Standard-Badges (idempotent, Badge-Tabelle ist vorher leer)."""
    from badges import seed_badges
    seed_badges()
    return True


def make_match(db, comp, teams, md, hs, ra, status="finished",
               home=None, away=None):
    m = Match(
        competition_id=comp.id, matchday=md,
        home_team_id=(home or teams[0]).id,
        away_team_id=(away or teams[1]).id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status=status, home_score=hs, away_score=ra,
    )
    db.session.add(m)
    db.session.commit()
    return m


def tip(db, user, m, h, a, joker=False):
    """Tipp anlegen + Punkte wie die App berechnen."""
    from scoring import calculate_points
    p = Prediction(user_id=user.id, match_id=m.id, home_tip=h,
                   away_tip=a, joker=joker)
    db.session.add(p)
    db.session.commit()
    p.points = calculate_points(p, m)
    db.session.commit()
    return p


def badge_by_code(code):
    return Badge.query.filter_by(code=code).first()


# ------------------------------------------- A) Klassifikation & Punkte ------
def test_klassifikation_alle_faelle_inklusive_pending(db, competition, teams, user):
    from scoring import classify_prediction
    m = make_match(db, competition, teams, 1, 3, 1)          # Endstand 3:1
    faelle = [((3, 1), "exact"), ((2, 0), "diff"), ((2, 1), "tendency"),
              ((0, 2), "wrong"), ((1, 3), "wrong"), ((3, 2), "tendency")]
    for (h, a), erwartet in faelle:
        dummy = Prediction(user_id=user.id, match_id=m.id, home_tip=h, away_tip=a)
        assert classify_prediction(dummy, m) == erwartet, (h, a)
    live = make_match(db, competition, teams, 2, 1, 0, status="live")
    p_live = Prediction(user_id=user.id, match_id=live.id,
                        home_tip=2, away_tip=0)
    assert classify_prediction(p_live, live) == "pending"


def test_punkte_4320_und_joker_verdoppelt_nur_punkte(db, competition, teams, user):
    from scoring import classify_prediction, calculate_points
    m = make_match(db, competition, teams, 1, 3, 1)
    for (h, a), punkte in [((3, 1), 4), ((2, 0), 3), ((2, 1), 2), ((0, 2), 0)]:
        dummy = Prediction(user_id=user.id, match_id=m.id, home_tip=h, away_tip=a)
        assert calculate_points(dummy, m) == punkte, (h, a)
    # Joker: Punkte x2, Klassifikation bleibt joker-unabhaengig ((73))
    j_diff = Prediction(user_id=user.id, match_id=m.id,
                        home_tip=2, away_tip=0, joker=True)
    assert calculate_points(j_diff, m) == 6
    assert classify_prediction(j_diff, m) == "diff"
    j_ex = Prediction(user_id=user.id, match_id=m.id,
                      home_tip=3, away_tip=1, joker=True)
    assert calculate_points(j_ex, m) == 8
    assert classify_prediction(j_ex, m) == "exact"


# ------------------------------------- B) recompute_matchday_winners ---------
def test_recompute_eindeutiger_sieger_setzt_punkte_und_exakt_count(
        db, competition, teams, user, user2):
    from scoring import recompute_matchday_winners
    m = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m, 3, 1)            # exakt -> 4 P
    tip(db, user2, m, 2, 0)           # diff -> 3 P
    recompute_matchday_winners()
    rows = MatchdayWinner.query.all()
    assert len(rows) == 1
    r = rows[0]
    assert r.user_id == user.id and r.points == 4 and r.exact_count == 1
    assert r.is_shared is False and r.season == "2026/27"  # laufende Saison (Fixture)
    assert r.competition_id == competition.id


def test_recompute_tiebreak_punktgleichheit_geteilter_sieg(
        db, competition, teams, user, user2):
    """Beide 7 P (1x exakt + 1x diff) -> geteilter Sieg, beide Zeilen."""
    from scoring import recompute_matchday_winners
    m1 = make_match(db, competition, teams, 1, 3, 1)
    m2 = make_match(db, competition, teams, 1, 2, 1,
                    home=teams[2], away=teams[3])
    tip(db, user, m1, 3, 1)   # exakt 4
    tip(db, user, m2, 1, 0)   # diff 3 -> 7
    tip(db, user2, m1, 2, 0)  # diff 3
    tip(db, user2, m2, 2, 1)  # exakt 4 -> 7
    recompute_matchday_winners()
    rows = MatchdayWinner.query.filter_by(matchday=1).all()
    assert len(rows) == 2
    assert all(r.is_shared for r in rows)
    assert all(r.points == 7 and r.exact_count == 1 for r in rows)


def test_recompute_nur_null_punkte_kein_sieger(db, competition, teams, user, user2):
    from scoring import recompute_matchday_winners
    m = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m, 0, 0)    # falsch -> 0
    tip(db, user2, m, 1, 1)   # falsch -> 0
    recompute_matchday_winners()
    assert MatchdayWinner.query.count() == 0


def test_recompute_ohne_tipps_kein_sieger(db, competition, teams):
    from scoring import recompute_matchday_winners
    make_match(db, competition, teams, 1, 3, 1)
    recompute_matchday_winners()
    assert MatchdayWinner.query.count() == 0


def test_recompute_ersetzt_veraltete_zeilen(db, competition, teams, user, user2):
    from scoring import recompute_matchday_winners
    m = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m, 3, 1)
    # Stale-Zeilen (falscher Sieger + falscher Spieltag 99) werden weggeraeumt:
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=1,
                                  user_id=user2.id, points=99, exact_count=9,
                                  season="2026/27"))
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=99,
                                  user_id=user.id, points=4, exact_count=1,
                                  season="2026/27"))
    db.session.commit()
    recompute_matchday_winners()
    rows = MatchdayWinner.query.all()
    assert len(rows) == 1
    assert rows[0].matchday == 1 and rows[0].user_id == user.id
    assert rows[0].points == 4 and rows[0].exact_count == 1


# ------------------------------------------------ C) Badge-Trigger -----------
def test_trigger_first_tip(db, competition, teams, user, user2, seeded):
    from badges import _user_qualifies, check_and_award_badges
    b = badge_by_code("first_tip")
    assert _user_qualifies(user, b) is False
    m = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m, 1, 1)
    assert _user_qualifies(user, b) is True
    check_and_award_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first()
    assert not UserBadge.query.filter_by(user_id=user2.id, badge_id=b.id).first()


def test_trigger_tips_count_grenze_30(db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("loyal")  # 30 Tipps
    for md in range(1, 30):
        m = make_match(db, competition, teams, md, 1, 0)
        tip(db, user, m, 1, 0)
    assert _user_qualifies(user, b) is False
    m30 = make_match(db, competition, teams, 30, 2, 1)
    tip(db, user, m30, 2, 1)
    assert _user_qualifies(user, b) is True


def test_trigger_total_points_grenze_100(db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("100_points")  # 100 Punkte
    for md in range(1, 25):          # 24 x 4 P = 96 -> knapp drunter
        m = make_match(db, competition, teams, md, 2, 1)
        tip(db, user, m, 2, 1)
    assert _user_qualifies(user, b) is False
    m25 = make_match(db, competition, teams, 25, 3, 1)
    tip(db, user, m25, 3, 1)         # +4 -> exakt 100
    assert _user_qualifies(user, b) is True


def test_trigger_exact_count_grenze_10(db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("sharp_shooter")  # 10 exakt
    for md in range(1, 10):
        m = make_match(db, competition, teams, md, 2, 1)
        tip(db, user, m, 2, 1)          # 9x exakt
    assert _user_qualifies(user, b) is False
    m10 = make_match(db, competition, teams, 10, 3, 1)
    tip(db, user, m10, 2, 0)            # diff zaehlt nicht
    assert _user_qualifies(user, b) is False
    m11 = make_match(db, competition, teams, 11, 1, 0)
    tip(db, user, m11, 1, 0, joker=True)  # Joker-Exakt zaehlt als exakt
    assert _user_qualifies(user, b) is True


def test_trigger_joker_exact_varianten(db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("joker_master")
    m1 = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m1, 3, 1, joker=False)   # exakt ohne Joker -> nein
    assert _user_qualifies(user, b) is False
    m2 = make_match(db, competition, teams, 2, 2, 0)
    tip(db, user, m2, 5, 5, joker=True)    # Joker, aber daneben -> nein
    assert _user_qualifies(user, b) is False
    m3 = make_match(db, competition, teams, 3, 1, 0)
    tip(db, user, m3, 1, 0, joker=True)    # Joker + exakt -> ja
    assert _user_qualifies(user, b) is True


def test_trigger_perfect_day_joker_zaehlt_als_exakt(
        db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("perfect_day")
    m1 = make_match(db, competition, teams, 1, 3, 1)
    m2 = make_match(db, competition, teams, 1, 2, 2,
                    home=teams[2], away=teams[3])
    tip(db, user, m1, 3, 1, joker=True)    # exakt MIT Joker (8 P)
    tip(db, user, m2, 2, 2)
    assert _user_qualifies(user, b) is True


def test_trigger_perfect_day_unvollstaendig_getippt_zaehlt_nicht(
        db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("perfect_day")
    make_match(db, competition, teams, 1, 3, 1)
    m2 = make_match(db, competition, teams, 1, 2, 2,
                    home=teams[2], away=teams[3])
    tip(db, user, m2, 2, 2)                # nur 1 von 2 Spielen getippt
    assert _user_qualifies(user, b) is False


def test_trigger_perfect_day_fremder_wettbewerb_zaehlt_nicht(
        db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b = badge_by_code("perfect_day")
    other = Competition(code="POK", name="Pokal", season="2025/26",
                        matchdays=6, teams_count=16)
    db.session.add(other)
    db.session.commit()
    om1 = make_match(db, other, teams, 1, 3, 1)               # fremder Wettbewerb
    om2 = make_match(db, other, teams, 1, 2, 2,
                     home=teams[2], away=teams[3])
    tip(db, user, om1, 3, 1)
    tip(db, user, om2, 2, 2)               # perfekt — aber im falschen Wettbewerb
    assert _user_qualifies(user, b) is False
    tm = make_match(db, competition, teams, 1, 3, 1)          # aktiver Wettbewerb
    make_match(db, competition, teams, 1, 0, 0,
               home=teams[2], away=teams[3])   # 2. Spiel (ungetippt)
    tip(db, user, tm, 3, 1)                # 1 von 2 -> unvollstaendig
    assert _user_qualifies(user, b) is False


def test_trigger_matchday_winner_saison_scope(db, competition, teams, user, seeded):
    from badges import _user_qualifies
    from scoring import set_setting
    b = badge_by_code("md_winner_1")
    set_setting("current_season", "2025/26")
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=1,
                                  user_id=user.id, points=10, exact_count=2,
                                  season="2024/25"))     # ALTE Saison
    db.session.commit()
    assert _user_qualifies(user, b) is False
    db.session.add(MatchdayWinner(competition_id=competition.id, matchday=2,
                                  user_id=user.id, points=8, exact_count=1,
                                  season="2025/26"))     # aktuelle Saison
    db.session.commit()
    assert _user_qualifies(user, b) is True


def test_trigger_md_winner_3_schwelle_inkl_geteilter_siege(
        db, competition, teams, user, seeded):
    from badges import _user_qualifies
    b3 = badge_by_code("md_winner_3")
    b5 = badge_by_code("md_winner_5")
    for i, md in enumerate([1, 2, 3], start=1):
        db.session.add(MatchdayWinner(competition_id=competition.id, matchday=md,
                                      user_id=user.id, points=7 + i,
                                      exact_count=1, is_shared=(i > 1),
                                      season="2026/27"))
    db.session.commit()
    assert _user_qualifies(user, b3) is True    # 3 Siege (2 davon geteilt) zaehlen
    assert _user_qualifies(user, b5) is False   # Schwelle 5 nicht erreicht


def test_trigger_matchday_winner_geteilter_sieg_zaehlt_voll(
        db, competition, teams, user, user2, seeded):
    from badges import check_and_award_badges
    from scoring import recompute_matchday_winners
    m1 = make_match(db, competition, teams, 1, 3, 1)
    m2 = make_match(db, competition, teams, 1, 2, 1,
                    home=teams[2], away=teams[3])
    tip(db, user, m1, 3, 1)   # exakt 4
    tip(db, user, m2, 1, 0)   # diff 3 -> 7
    tip(db, user2, m1, 2, 0)  # diff 3
    tip(db, user2, m2, 2, 1)  # exakt 4 -> 7  => geteilter Sieg
    recompute_matchday_winners()
    rows = MatchdayWinner.query.filter_by(matchday=1).all()
    assert len(rows) == 2 and all(r.is_shared for r in rows)
    check_and_award_badges()
    b1 = badge_by_code("md_winner_1")
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b1.id).first()
    assert UserBadge.query.filter_by(user_id=user2.id, badge_id=b1.id).first()


# ------------------------------------- D) Vergabe-/Widerrufs-Mechanik --------
def test_award_idempotent_und_revoke(db, competition, teams, user, seeded):
    from badges import award_badge, revoke_badge
    b = badge_by_code("first_tip")
    assert award_badge(user, b) is True
    assert award_badge(user, b) is False          # idempotent
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).count() == 1
    assert revoke_badge(user, b) is True
    assert revoke_badge(user, b) is False
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first() is None


def test_manual_nie_automatisch_und_nie_widerrufen(
        db, competition, teams, user, seeded):
    from badges import award_badge, check_and_award_badges, revalidate_badges
    champ = badge_by_code("champion")             # trigger_type=manual
    m = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m, 3, 1)
    check_and_award_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=champ.id).first() is None
    award_badge(user, champ)                      # Admin-Vergabe simulieren
    check_and_award_badges()
    revalidate_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=champ.id).first()


def test_revalidate_verleiht_fehlende_und_widerruft_unverdiente(
        db, competition, teams, user, seeded):
    from badges import revalidate_badges
    from scoring import calculate_points
    b = badge_by_code("sharp_shooter")            # 10 exakt
    for md in range(1, 11):
        m = make_match(db, competition, teams, md, 2, 1)
        tip(db, user, m, 2, 1)                    # 10x exakt, Badge fehlt
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first() is None
    revalidate_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first()
    # Ergebniskorrektur: ein Exakter wird un-exakt -> 9 -> Widerruf:
    p = Prediction.query.join(Match).filter(
        Prediction.user_id == user.id, Match.matchday == 10).first()
    p.home_tip = 0
    p.points = calculate_points(p, p.match)
    db.session.commit()
    revalidate_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first() is None


def test_check_and_award_user_liste_begrenzt(db, competition, teams, user, user2, seeded):
    from badges import check_and_award_badges
    b = badge_by_code("first_tip")
    m = make_match(db, competition, teams, 1, 3, 1)
    tip(db, user, m, 1, 1)
    tip(db, user2, m, 2, 2)
    check_and_award_badges(users=[user])          # nur 'user' pruefen
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first()
    assert UserBadge.query.filter_by(user_id=user2.id, badge_id=b.id).first() is None
    check_and_award_badges()                      # Volllauf holt user2 nach
    assert UserBadge.query.filter_by(user_id=user2.id, badge_id=b.id).first()


# ------------------------------------- E) Saison-Scope der Karriere-Badges (78)
def _tip_mit_kickoff(db, user, comp, teams, kickoff):
    """Exakter Tipp (2:1 auf 2:1) zu einem frei wählbaren Anstoß."""
    m = Match(
        competition_id=comp.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=kickoff, status="finished", home_score=2, away_score=1)
    db.session.add(m)
    db.session.commit()
    return tip(db, user, m, 2, 1)


def test_season_interval_parsen_und_fehlertoleranz():
    """'2026/27' und '2025/2026' werden gelesen; Kaputtes/Leeres -> None
    (Filter dann inaktiv — es zählt weiter alles, nie still falsch)."""
    from badges import _season_interval
    start, end = _season_interval("2026/27")
    assert (start.year, start.month, start.day) == (2026, 7, 1)
    assert (end.year, end.month, end.day) == (2027, 6, 30)
    start2, end2 = _season_interval("2025/2026")
    assert start2.year == 2025 and end2.year == 2026
    assert _season_interval("") is None
    assert _season_interval(None) is None
    assert _season_interval("ka-pu/tt") is None


def test_karriere_badges_zahlen_nur_laufende_saison(
        db, competition, teams, user, seeded):
    """(78): 10 exakte Tipps in der VORSaison (2025/26) zählen nicht für den
    Scharfschützen, solange die Saison 2026/27 läuft — auch first_tip nicht
    (alle Tipps sind alt). Ein laufender-Saison-Tipp genügt für first_tip."""
    from badges import _user_qualifies
    from scoring import set_setting
    b = badge_by_code("sharp_shooter")
    b_ft = badge_by_code("first_tip")
    alt = datetime(2025, 8, 16, 13, 30, tzinfo=timezone.utc)   # Vorsaison
    for i in range(10):
        _tip_mit_kickoff(db, user, competition, teams, alt + timedelta(days=i))
    assert _user_qualifies(user, b) is False      # 10 exakt — aber alte Saison
    assert _user_qualifies(user, b_ft) is False   # Tipps ja — aber alle alt
    neu = datetime(2026, 9, 12, 13, 30, tzinfo=timezone.utc)   # laufende Saison
    _tip_mit_kickoff(db, user, competition, teams, neu)
    assert _user_qualifies(user, b_ft) is True
    assert _user_qualifies(user, b) is False      # nur 1 der 11 liegt in der Saison
    # Archiv-Blick auf die alte Saison: dort zählen die 10 wieder:
    set_setting("current_season", "2025/26")
    assert _user_qualifies(user, b) is True


def test_revalidate_widerruft_vorsaison_karriere_badges(
        db, competition, teams, user, seeded):
    """(78): Wurde ein Karriere-Badge auf Basis der Vorsaison verliehen, wird er
    nach dem Saisonwechsel beim nächsten Wartungslauf 'badges' widerrufen."""
    from badges import revalidate_badges
    from scoring import set_setting
    b = badge_by_code("sharp_shooter")
    alt = datetime(2025, 8, 16, 13, 30, tzinfo=timezone.utc)
    for i in range(10):
        _tip_mit_kickoff(db, user, competition, teams, alt + timedelta(days=i))
    set_setting("current_season", "2025/26")
    revalidate_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first()
    set_setting("current_season", "2026/27")      # Saisonwechsel
    revalidate_badges()
    assert UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first() is None


def test_seed_karriere_badges_nennen_die_saison():
    """(78): die Seeding-Texte der Karriere-Badges sagen 'in der Saison' (neue
    DBs; Bestand: Admin → Badges → Text manuell anpassen)."""
    from badges import DEFAULT_BADGES
    karriere_types = {"first_tip", "tips_count", "total_points", "exact_count",
                      "joker_exact"}
    for code, name, desc, icon, color, ttype, thresh in DEFAULT_BADGES:
        if ttype in karriere_types:
            assert "Saison" in desc, code
