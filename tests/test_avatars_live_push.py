"""Tests fuer Avatar, Live-Scoring und Push-Helfer."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json

from PIL import Image
from werkzeug.datastructures import FileStorage

from avatars import save_avatar
from live_scoring import LiveMatchManager
from models import Match, Prediction, User
from push_routes import _remind_for_match


def _image_file(filename='avatar.png'):
    buf = BytesIO()
    Image.new('RGBA', (64, 64), (255, 0, 0, 255)).save(buf, format='PNG')
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename, content_type='image/png')


def test_save_avatar_success_and_invalid_ext(app, db, user, tmp_path):
    app.config['UPLOAD_FOLDER'] = str(tmp_path)
    with app.app_context():
        filename, err = save_avatar(_image_file(), user.id)
        assert err is None
        assert filename.endswith('.png')
        assert (tmp_path / filename).exists()

        bad, err = save_avatar(FileStorage(stream=BytesIO(b'x'), filename='bad.exe'), user.id)
        assert bad is None
        assert 'nicht erlaubt' in err


def test_live_match_manager_update_finish_stats(db, user, competition, teams):
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=10),
        status='scheduled'
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=match.id, home_tip=1, away_tip=0))
    db.session.commit()

    mgr = LiveMatchManager()
    assert mgr.update_match(match.id, 1, 0, minute=20) is True
    db.session.refresh(match)
    assert match.status == 'live'
    stats = mgr.get_match_stats(match.id)
    assert stats['predictions_count'] == 1
    assert mgr.finish_match(match.id, 1, 0) is True
    db.session.refresh(match)
    assert match.status == 'finished'


def test_push_remind_for_match(monkeypatch, db, user, competition, teams):
    user.push_subscription = json.dumps({'endpoint': 'https://example.test'})
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=1),
        status='scheduled'
    )
    db.session.add(match)
    db.session.commit()

    monkeypatch.setattr('push_routes._send_push_to_users', lambda users, payload: (len(users), 0))
    sent, failed = _remind_for_match(match)
    assert sent == 1
    assert failed == 0
