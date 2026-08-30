"""Tests fuer interne Schema-Migrationen."""
from models import SchemaMigration, User
from schema_migrations import schema_status, pending_migrations, run_pending_migrations


def _login_admin(client, admin_user):
    client.post('/auth/login', data={'email': admin_user.email, 'password': 'admin123'}, follow_redirects=True)


def test_schema_status_and_run_migrations(db):
    status_before = schema_status()
    assert 'pending_count' in status_before
    results = run_pending_migrations()
    assert isinstance(results, list)
    assert SchemaMigration.query.count() >= len(results)
    status_after = schema_status()
    assert status_after['pending_count'] == 0


def test_user_notification_defaults_migration(db, user):
    user.notify_enabled = None
    user.notify_hours_before = None
    db.session.commit()
    run_pending_migrations()
    refreshed = db.session.get(User, user.id)
    assert refreshed.notify_enabled is not None
    assert refreshed.notify_hours_before is not None


def test_schema_admin_page_and_run(client, admin_user):
    _login_admin(client, admin_user)
    resp = client.get('/admin/schema')
    assert resp.status_code == 200
    assert 'DB-/Schema-Wartung'.encode('utf-8') in resp.data
    resp = client.post('/admin/schema/run', follow_redirects=True)
    assert resp.status_code == 200
