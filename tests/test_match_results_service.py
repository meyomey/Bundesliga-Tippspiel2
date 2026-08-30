"""Tests fuer zentralisierte Ergebnis-Aktualisierung."""
from match_results import set_match_result
from models import Prediction


def test_set_match_result_updates_points_and_status(db, user, match):
    pred = Prediction(user_id=user.id, match_id=match.id, home_tip=2, away_tip=1)
    db.session.add(pred)
    db.session.commit()

    set_match_result(match, 2, 1, status="finished")
    db.session.refresh(match)
    db.session.refresh(pred)

    assert match.status == "finished"
    assert match.home_score == 2
    assert match.away_score == 1
    assert pred.points >= 4
