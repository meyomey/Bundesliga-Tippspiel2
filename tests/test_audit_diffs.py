"""Tests fuer before/after-Diffs im AdminActivityLog."""

import pytest

from audit_log import diff_snapshots, log_admin_action, snapshot_model
from models import AdminActivityLog, SpecialQuestion, User


# ----------------------------------------------------------------------
# Unit: Helper
# ----------------------------------------------------------------------

def test_diff_snapshots_only_changed_fields():
    before = {'a': 1, 'b': 'x', 'c': None}
    after = {'a': 2, 'b': 'x', 'c': None}
    assert diff_snapshots(before, after) == {'a': {'from': 1, 'to': 2}}


def test_diff_snapshots_none_transitions(db, user):
    diff = diff_snapshots({'phone': None}, {'phone': '0123'})
    assert diff == {'phone': {'from': None, 'to': '0123'}}
    assert diff_snapshots({'phone': '0123'}, {'phone': None}) == {'phone': {'from': '0123', 'to': None}}


def test_snapshot_model_normalisiert_datetime(db, user):
    from datetime import datetime, timezone
    user.paid_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    snap = snapshot_model(user, ['username', 'paid_at', 'gibt_es_nicht'])
    assert snap['username'] == user.username
    assert snap['paid_at'] == '2026-01-02T03:04:05+00:00'
    assert 'gibt_es_nicht' not in snap


def test_log_admin_action_legt_diff_in_metadaten(app, db):
    with app.app_context():
        entry = log_admin_action(
            'test_action', 'user', 7, 'Test',
            metadata={'extra': 'bleibt'},
            before={'username': 'alt', 'email': 'a@x.de'},
            after={'username': 'neu', 'email': 'a@x.de'},
        )
        meta = __import__('json').loads(entry.metadata_json)
        assert meta['extra'] == 'bleibt'
        assert meta['diff'] == {'username': {'from': 'alt', 'to': 'neu'}}


def test_log_admin_action_ohne_aenderung_schreibt_kein_diff(app, db):
    with app.app_context():
        entry = log_admin_action(
            'test_action2', 'user', 7, 'Test',
            before={'a': 1}, after={'a': 1},
        )
        assert entry.metadata_json is None


def test_log_admin_action_nicht_dict_metadata_wird_verpackt(app, db):
    with app.app_context():
        entry = log_admin_action(
            'test_action3', metadata=[1, 2],
            before={'a': 1}, after={'a': 9},
        )
        meta = __import__('json').loads(entry.metadata_json)
        assert meta['payload'] == [1, 2]
        assert meta['diff']['a'] == {'from': 1, 'to': 9}


# ----------------------------------------------------------------------
# Route: Admin-User-Edit schreibt before/after-Diff
# ----------------------------------------------------------------------

def _admin_login(client, admin_user):
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'},
                follow_redirects=True)


def test_user_update_loggt_diff(client, db, admin_user, user):
    _admin_login(client, admin_user)
    old_username = user.username
    resp = client.post(f'/admin/user/{user.id}/edit', data={
        'username': old_username + '_geaendert',
        'full_name': '',
        'email': 'neu-' + user.email,
        'phone': '',
        'favorite_team_id': '0',
        'paid_note': '',
        'new_password': 'supergeheim6',
    }, follow_redirects=True)
    assert resp.status_code == 200
    entry = AdminActivityLog.query.filter_by(action='user_update').order_by(
        AdminActivityLog.id.desc()).first()
    assert entry is not None
    diff = entry.diff
    assert diff is not None, 'user_update muss Diff-Metadaten enthalten'
    assert diff['username'] == {'from': old_username, 'to': old_username + '_geaendert'}
    assert 'email' in diff and diff['email']['to'].startswith('neu-')
    # Unveränderte Felder tauchen nicht auf:
    assert 'phone' not in diff and 'has_paid' not in diff
    # Passwortwechsel ist separat markiert:
    assert entry.meta.get('password_changed') is True


def test_user_update_ohne_aenderungen_leerer_diff(client, db, admin_user, user):
    _admin_login(client, admin_user)
    resp = client.post(f'/admin/user/{user.id}/edit', data={
        'username': user.username,
        'full_name': user.full_name or '',
        'email': user.email,
        'phone': user.phone or '',
        'favorite_team_id': str(user.favorite_team_id or 0),
        'paid_note': '',
        'new_password': '',
        'show_full_name': 'y',  # Checkbox aktiv halten (Default des Nutzers)
    }, follow_redirects=True)
    assert resp.status_code == 200
    entry = AdminActivityLog.query.filter_by(action='user_update').order_by(
        AdminActivityLog.id.desc()).first()
    assert entry is not None
    assert entry.diff is None, 'keine Änderung => kein Diff'


# ----------------------------------------------------------------------
# Route: Sonderfragen-Edit schreibt Diff (neben dem alten old/new-Payload)
# ----------------------------------------------------------------------

def test_special_question_edit_loggt_diff(client, db, admin_user, competition, app, monkeypatch):
    from datetime import datetime
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    q = SpecialQuestion(
        competition_id=competition.id,
        text='Wer wird Meister in dieser Saison?',
        answer_type='text',
        points_value=5,
        deadline=datetime(2026, 11, 15, 20, 0),
    )
    db.session.add(q)
    db.session.commit()

    _admin_login(client, admin_user)
    resp = client.post(f'/admin/special-question/{q.id}/edit', data={
        'text': 'Wer wird Meister in der aktuellen Saison?',
        'description': '',
        'answer_type': 'text',
        'options': '',
        'points_value': '5',
        'deadline': '2026-11-15T20:00',
    }, follow_redirects=True)
    assert resp.status_code == 200
    entry = AdminActivityLog.query.filter_by(action='special_question_edit').order_by(
        AdminActivityLog.id.desc()).first()
    assert entry is not None
    diff = entry.diff
    assert diff is not None
    assert diff['text'] == {'from': 'Wer wird Meister in dieser Saison?',
                            'to': 'Wer wird Meister in der aktuellen Saison?'}
    assert 'points_value' not in diff, 'unveränderte Punkte tauchen nicht im Diff auf'
    # Legacy-Payload bleibt erhalten:
    meta = entry.meta
    assert 'old' in meta and 'new' in meta


# ----------------------------------------------------------------------
# UI: Activity-Seite rendert Diffs
# ----------------------------------------------------------------------

def test_activity_page_rendert_diff_block(client, db, admin_user, app):
    with app.app_context():
        log_admin_action(
            'user_update', 'user', 1, 'Spieler aktualisiert',
            before={'username': 'alt_name'}, after={'username': 'neu_name'},
        )
    _admin_login(client, admin_user)
    resp = client.get('/admin/activity')
    assert resp.status_code == 200
    assert 'Änderungen'.encode('utf-8') in resp.data
    assert b'diff-old' in resp.data
    assert b'alt_name' in resp.data and b'neu_name' in resp.data
