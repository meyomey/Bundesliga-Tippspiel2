"""Sync-Purge: Benutzerdaten-Uebernahme bei neu angelegten Ersatz-Spielen.

Hintergrund (Incident 06.09.2026): lieferte football-data.org fuer drei
Spieltag-1-Partien neue externe IDs, legte der Sync Ersatzzeilen an und der
Anschluss-Purge loeschte die Altzeilen mitsamt aller Tipps/Kommentare. Der
Purge zieht Daten jetzt auf die Ersatzzeile um und behält Altzeilen mit
Benutzerdaten, falls es kein Ersatzspiel gibt.
"""
from datetime import datetime, timedelta, timezone

from models import Comment, Competition, Match, Prediction, Team, User
from sync_shared import LAST_PURGE_STATS, _purge_stale_matches_for_comp


def _setup(db, code):
    comp = Competition(code=code, name=f"Purge {code}", season="2026",
                       matchdays=34, teams_count=18, is_active=False)
    db.session.add(comp)
    db.session.commit()
    ta = Team(name=f"Heim {code}", short_name=f"H{code[-3:]}", logo="x.png")
    tb = Team(name=f"Aus {code}", short_name=f"A{code[-3:]}", logo="x.png")
    u1 = User(username=f"purg_{code}_1", email=f"purg_{code}_1@x.test", full_name="P1")
    u1.set_password("pw12345678")
    u2 = User(username=f"purg_{code}_2", email=f"purg_{code}_2@x.test", full_name="P2")
    u2.set_password("pw12345678")
    db.session.add_all([ta, tb, u1, u2])
    db.session.commit()
    return comp, ta, tb, u1, u2


def _stale_match(db, comp, ta, tb, ext, with_scores=True):
    m = Match(competition_id=comp.id, matchday=1, home_team_id=ta.id, away_team_id=tb.id,
              kickoff=datetime(2026, 8, 22, 13, 30, tzinfo=timezone.utc),
              status="finished",
              home_score=2 if with_scores else None, away_score=0 if with_scores else None,
              external_id=ext)
    db.session.add(m)
    db.session.commit()
    return m


def test_tips_and_comments_migrate_to_replacement(db):
    comp, ta, tb, u1, u2 = _setup(db, "MIG")
    old = _stale_match(db, comp, ta, tb, "fd:old")
    repl = _stale_match(db, comp, ta, tb, "fd:new")
    db.session.add_all([
        Prediction(user_id=u1.id, match_id=old.id, home_tip=2, away_tip=0, points=4),
        Prediction(user_id=u2.id, match_id=old.id, home_tip=0, away_tip=0, points=0),
        Comment(user_id=u1.id, match_id=old.id, text="klarer Heimsieg"),
    ])
    db.session.commit()

    removed = _purge_stale_matches_for_comp(comp.id, {"fd:new"})

    assert removed == 1
    assert Match.query.filter_by(id=old.id).count() == 0
    preds = {p.user_id: p for p in Prediction.query.filter_by(match_id=repl.id).all()}
    assert set(preds) == {u1.id, u2.id}
    assert preds[u1.id].home_tip == 2 and preds[u1.id].points == 4  # Punkte bleiben erhalten
    assert Comment.query.filter_by(match_id=repl.id).count() == 1
    assert LAST_PURGE_STATS["migrated_predictions"] == 2
    assert LAST_PURGE_STATS["migrated_comments"] == 1


def test_newer_tip_on_replacement_wins_conflict(db):
    comp, ta, tb, u1, _ = _setup(db, "CNF")
    old = _stale_match(db, comp, ta, tb, "fd:old")
    repl = _stale_match(db, comp, ta, tb, "fd:new")
    db.session.add(Prediction(user_id=u1.id, match_id=old.id, home_tip=2, away_tip=0))
    db.session.add(Prediction(user_id=u1.id, match_id=repl.id, home_tip=1, away_tip=0))
    db.session.commit()

    removed = _purge_stale_matches_for_comp(comp.id, {"fd:new"})

    assert removed == 1
    assert Prediction.query.count() == 1
    assert Prediction.query.one().match_id == repl.id
    assert Prediction.query.one().home_tip == 1


def test_stale_without_tips_still_purged(db):
    comp, ta, tb, _, _ = _setup(db, "EMP")
    old = _stale_match(db, comp, ta, tb, "fd:old")
    _stale_match(db, comp, ta, tb, "fd:keep")

    removed = _purge_stale_matches_for_comp(comp.id, {"fd:keep"})

    assert removed == 1
    assert Match.query.filter_by(id=old.id).count() == 0


def test_stale_with_tips_without_replacement_is_kept(db):
    comp, ta, tb, u1, _ = _setup(db, "KEP")
    # Gegenlaeufige Paarung: kein Ersatzspiel mit gleicher Ansetzung vorhanden.
    old = Match(competition_id=comp.id, matchday=1, home_team_id=tb.id, away_team_id=ta.id,
                kickoff=datetime(2026, 8, 22, 13, 30, tzinfo=timezone.utc),
                status="finished", home_score=1, away_score=1, external_id="fd:old")
    db.session.add(old)
    db.session.commit()
    db.session.add(Prediction(user_id=u1.id, match_id=old.id, home_tip=1, away_tip=1))
    db.session.commit()

    removed = _purge_stale_matches_for_comp(comp.id, {"fd:other"})

    assert removed == 0
    assert Match.query.filter_by(id=old.id).count() == 1
    assert Prediction.query.filter_by(match_id=old.id).count() == 1
    assert LAST_PURGE_STATS["kept_with_tips"] == 1


def test_integrity_flags_finished_matches_without_tips(db):
    from admin_integrity_routes import build_integrity_report

    comp = Competition.query.filter_by(is_active=True).order_by(Competition.id.asc()).first()
    if comp is None:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    ta = Team(name="Int Heim", short_name="IH", logo="x.png")
    tb = Team(name="Int Aus", short_name="IA", logo="x.png")
    db.session.add_all([ta, tb])
    db.session.commit()
    ghost = _stale_match(db, comp, ta, tb, "fd:intghost")
    healthy = Match(competition_id=comp.id, matchday=3, home_team_id=ta.id, away_team_id=tb.id,
                    kickoff=datetime(2026, 9, 5, 13, 30, tzinfo=timezone.utc),
                    status="finished", home_score=1, away_score=0, external_id="fd:intok")
    db.session.add(healthy)
    db.session.commit()
    u = User(username="int_tipper", email="int@x.test", full_name="T")
    u.set_password("pw12345678")
    db.session.add(u)
    db.session.commit()
    db.session.add(Prediction(user_id=u.id, match_id=healthy.id, home_tip=1, away_tip=0))
    db.session.commit()

    checks = build_integrity_report()
    check = next(c for c in checks if c["id"] == "finished_without_tips")
    assert check["level"] == "warn"
    assert check["count"] >= 1
    assert check["message"] != "Alle beendeten Spiele haben mindestens einen Tipp."
