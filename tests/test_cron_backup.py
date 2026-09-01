"""Tests fuer Cron-Heartbeat und Datenbank-Backup (Produktions-Absicherung).

Deckt ab: konsistente SQLite-Backups per Backup-API, Rotation alter Dateien,
Fehlerfaelle (kein SQLite / Datei fehlt), Heartbeat-Roundtrip inkl. Alters-
Bewertung (ok/warn/error/never), Admin-Wartungscenter-Anzeige und die
Task-Dispatch-Logik von cron_jobs.py.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import cron_heartbeat
from backup import create_database_backup, list_backups
from cron_heartbeat import cron_any_never_or_error, get_cron_status, record_cron_run
from scoring import set_setting


@pytest.fixture
def file_db(app, monkeypatch, tmp_path):
    """Echte SQLite-Datei + tmp-Backup-Ordner als Backup-Quelle/-Ziel."""
    src = tmp_path / "tippspiel.db"
    con = sqlite3.connect(str(src))
    con.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("INSERT INTO demo VALUES (1, 'muster')")
    con.commit()
    con.close()
    monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI", "sqlite:///" + str(src))
    backup_dir = tmp_path / "backups"
    monkeypatch.setitem(app.config, "BACKUP_DIR", str(backup_dir))
    return {"src": src, "backup_dir": backup_dir}


def _login_admin(client, admin_user):
    client.post("/auth/login", data={"email": admin_user.email,
                                     "password": "admin123"}, follow_redirects=True)


# ---------------------------------------------------------------- Backup

def test_backup_erstellt_konsistente_kopie(app, file_db):
    with app.app_context():
        res = create_database_backup(keep=5)
    assert res["ok"] is True
    assert os.path.exists(res["file"])
    assert res["size"] > 0
    # Inhalt identisch zur Quelle
    con = sqlite3.connect(res["file"])
    assert con.execute("SELECT name FROM demo").fetchone()[0] == "muster"
    con.close()
    # Heartbeat gesetzt
    status = get_cron_status({"backup": cron_heartbeat.CRON_TASKS["backup"]})
    assert status[0]["state"] == "ok"
    assert "tippspiel_" in status[0]["detail"]


def test_backup_rotiert_alte_dateien(app, file_db):
    backup_dir = str(file_db["backup_dir"])
    os.makedirs(backup_dir, exist_ok=True)
    for i in range(8):
        p = os.path.join(backup_dir, f"tippspiel_20200101_0000{i}.db")
        with open(p, "wb") as f:
            f.write(b"alt")
    with app.app_context():
        res = create_database_backup(keep=5)
    assert res["ok"] is True
    assert len(res["removed"]) == 4
    remaining = [n for n in os.listdir(backup_dir) if n.startswith("tippspiel_")]
    assert len(remaining) == 5


def test_backup_verlangt_sqlite(app, monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI",
                        "postgresql://user:pw@localhost/db")
    monkeypatch.setitem(app.config, "BACKUP_DIR", str(tmp_path / "backups"))
    with app.app_context():
        res = create_database_backup()
    assert res["ok"] is False
    assert "nur für SQLite" in res["error"]
    status = get_cron_status({"backup": cron_heartbeat.CRON_TASKS["backup"]})
    assert status[0]["ok"] is False


def test_backup_meldet_fehler_wenn_datei_fehlt(app, monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI",
                        "sqlite:///" + str(tmp_path / "gibt_es_nicht.db"))
    monkeypatch.setitem(app.config, "BACKUP_DIR", str(tmp_path / "backups"))
    with app.app_context():
        res = create_database_backup()
    assert res["ok"] is False
    assert "fehlt" in res["error"]


def test_list_backups_ohne_ordner(app, monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, "BACKUP_DIR", str(tmp_path / "nix"))
    with app.app_context():
        assert list_backups() == []


# ---------------------------------------------------------------- Heartbeat

def test_heartbeat_roundtrip_ok_und_fehler(app, db):
    with app.app_context():
        record_cron_run("sync", ok=True, detail="42 Spiele aktualisiert")
        status = get_cron_status({"sync": cron_heartbeat.CRON_TASKS["sync"]})
        row = status[0]
        assert row["state"] == "ok"
        assert row["ok"] is True
        assert row["detail"] == "42 Spiele aktualisiert"
        assert row["age_minutes"] < 1

        record_cron_run("sync", ok=False, detail="Timeout")
        row = get_cron_status({"sync": cron_heartbeat.CRON_TASKS["sync"]})[0]
        assert row["state"] == "error"
        assert row["ok"] is False


def test_heartbeat_nie_gelaufen(app, db):
    with app.app_context():
        rows = get_cron_status()
    assert all(r["state"] == "never" for r in rows)
    assert cron_any_never_or_error(rows) is True


def test_heartbeat_alters_bewertung_warn_und_error(app, db):
    now = datetime.now(timezone.utc)
    with app.app_context():
        # sync: 100 min alt -> warn (ok bis 90, warn bis 360)
        set_setting("cron_last_run:sync",
                    {"ts": (now - timedelta(minutes=100)).isoformat(), "ok": True})
        # sync: 500 min alt -> error
        set_setting("cron_last_run:reminder",
                    {"ts": (now - timedelta(minutes=500)).isoformat(), "ok": True})
        # backup: 26 h alt -> ok (taeglich); 30 h -> warn; 4 Tage -> error
        set_setting("cron_last_run:backup",
                    {"ts": (now - timedelta(hours=26)).isoformat(), "ok": True})
        rows = {r["task"]: r for r in get_cron_status()}
        assert rows["sync"]["state"] == "warn"
        assert rows["reminder"]["state"] == "error"
        assert rows["backup"]["state"] == "ok"
        set_setting("cron_last_run:backup",
                    {"ts": (now - timedelta(hours=30)).isoformat(), "ok": True})
        assert get_cron_status()[3]["state"] == "warn"
        set_setting("cron_last_run:backup",
                    {"ts": (now - timedelta(days=4)).isoformat(), "ok": True})
        assert get_cron_status()[3]["state"] == "error"


def test_heartbeat_kaputter_eintrag(app, db):
    with app.app_context():
        set_setting("cron_last_run:sync", {"ts": "kein-datum"})
        row = get_cron_status({"sync": cron_heartbeat.CRON_TASKS["sync"]})[0]
        assert row["state"] == "error"


# ---------------------------------------------------------------- Admin-Anzeige

def test_wartungscenter_zeigt_cron_status_und_hinweis(client, db, admin_user):
    _login_admin(client, admin_user)
    resp = client.get("/admin/maintenance")
    assert resp.status_code == 200
    for marker in ["Automatik-Status (Heartbeat)", "noch nie gelaufen",
                   "Jetzt Backup erstellen",
                   "Plesk-Cron noch nicht eingerichtet?",
                   "cron/run?task=all", "cron/run?task=backup",
                   "wget -q -O /dev/null",
                   "CRON_SECRET"]:
        assert marker.encode("utf-8") in resp.data, f"fehlt: {marker}"


def test_wartungscenter_backup_now_erfolg(client, db, admin_user, monkeypatch):
    import backup
    _login_admin(client, admin_user)

    def fake_backup():
        return {"ok": True, "name": "tippspiel_test.db", "size": 123,
                "file": "/tmp/x", "error": None, "removed": []}

    monkeypatch.setattr(backup, "create_database_backup", fake_backup)
    resp = client.post("/admin/maintenance/backup-now", follow_redirects=True)
    assert resp.status_code == 200
    assert "Backup erstellt".encode("utf-8") in resp.data


def test_wartungscenter_backup_now_fehler(client, db, admin_user, monkeypatch):
    import backup
    _login_admin(client, admin_user)

    def fake_backup():
        return {"ok": False, "error": "kaputt", "file": None, "size": 0, "removed": []}

    monkeypatch.setattr(backup, "create_database_backup", fake_backup)
    resp = client.post("/admin/maintenance/backup-now", follow_redirects=True)
    assert resp.status_code == 200
    assert "Backup fehlgeschlagen".encode("utf-8") in resp.data


# ---------------------------------------------------------------- cron_jobs.py

def test_cron_jobs_dispatch_all(monkeypatch):
    import cron_jobs
    called = []
    monkeypatch.setattr(cron_jobs, "run_sync", lambda: called.append("sync") or True)
    monkeypatch.setattr(cron_jobs, "run_bot_tips", lambda: called.append("bots") or True)
    monkeypatch.setattr(cron_jobs, "run_reminders", lambda: called.append("reminder") or True)
    monkeypatch.setattr("cron_heartbeat.record_cron_run", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "all"])
    cron_jobs.main()
    assert called == ["sync", "bots", "reminder"]


def test_cron_jobs_dispatch_backup_und_status(monkeypatch):
    import cron_jobs
    called = []
    monkeypatch.setattr(cron_jobs, "run_backup", lambda: called.append("backup") or True)
    monkeypatch.setattr(cron_jobs, "run_status", lambda: called.append("status") or True)
    monkeypatch.setattr("cron_heartbeat.record_cron_run", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "backup"])
    cron_jobs.main()
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "status"])
    cron_jobs.main()
    assert called == ["backup", "status"]


def test_cron_jobs_unbekannte_task(monkeypatch):
    import cron_jobs
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "quatsch"])
    with pytest.raises(SystemExit) as exc:
        cron_jobs.main()
    assert exc.value.code == 1


def test_cron_jobs_heartbeat_bei_fehler(monkeypatch):
    import cron_jobs
    records = []
    monkeypatch.setattr(cron_jobs, "run_sync", lambda: (_ for _ in ()).throw(RuntimeError("kaputt")))
    monkeypatch.setattr("cron_heartbeat.record_cron_run",
                        lambda task, ok=True, detail=None: records.append((task, ok, detail)))
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "sync"])
    result = cron_jobs.main()
    assert result is None
    assert records == [("sync", False, "RuntimeError: kaputt")]


# ------------------------------------------------- Doppel-Heartbeat (Fix)
# Frueher schrieb create_database_backup() den Heartbeat (mit Detail) und
# _run_task_safe direkt danach ein zweites Mal (ohne Detail) - der zweite
# Write ueberschrieb das nuetzliche Detail im Wartungscenter.

def test_run_task_safe_doppelt_backup_heartbeat_nicht(monkeypatch):
    """Genau EIN Heartbeat pro Backup-Lauf - der mit Detail aus backup.py."""
    import cron_heartbeat as ch
    import cron_jobs
    records = []
    monkeypatch.setattr("cron_heartbeat.record_cron_run",
                        lambda task, ok=True, detail=None: records.append((task, ok, detail)))

    def fake_backup_task():
        # wie backup.py: Fachmodul schreibt den Heartbeat selbst
        ch.record_cron_run("backup", ok=True, detail="tippspiel_x.db (999 Bytes)")
        return True

    assert cron_jobs._run_task_safe("backup", fake_backup_task) is True
    assert records == [("backup", True, "tippspiel_x.db (999 Bytes)")]


def test_run_task_safe_schreibt_heartbeat_fuer_andere_tasks(monkeypatch):
    """Tasks ohne eigenen Heartbeat (sync/bots/reminder) bekommen ihn weiterhin."""
    import cron_jobs
    records = []
    monkeypatch.setattr("cron_heartbeat.record_cron_run",
                        lambda task, ok=True, detail=None: records.append((task, ok, detail)))
    assert cron_jobs._run_task_safe("sync", lambda: True) is True
    assert records == [("sync", True, None)]


def test_run_task_safe_backup_fehler_vor_fachmodul(monkeypatch):
    """Sicherheitsnetz: crasht run_backup VOR backup.py (z. B. ImportError),
    schreibt _run_task_safe trotzdem den Fehler-Heartbeat."""
    import cron_jobs
    records = []
    monkeypatch.setattr("cron_heartbeat.record_cron_run",
                        lambda task, ok=True, detail=None: records.append((task, ok, detail)))
    monkeypatch.setattr(cron_jobs, "run_backup",
                        lambda: (_ for _ in ()).throw(ImportError("flask fehlt")))
    assert cron_jobs._run_task_safe("backup", cron_jobs.run_backup) is False
    assert records == [("backup", False, "ImportError: flask fehlt")]


def test_dispatch_backup_erhaelt_heartbeat_detail(app, db, file_db, monkeypatch):
    """End-to-End: echtes Backup ueber den Task-Wrapper - Detail (Dateiname +
    Groesse) uebersteht _run_task_safe und ist im Wartungscenter sichtbar."""
    import cron_jobs

    def run_backup_im_testkontext():
        # wie cron_jobs.run_backup, nur mit der Test-App statt app.app
        with app.app_context():
            return create_database_backup()["ok"]

    assert cron_jobs._run_task_safe("backup", run_backup_im_testkontext) is True
    with app.app_context():
        status = get_cron_status({"backup": cron_heartbeat.CRON_TASKS["backup"]})
    assert status[0]["state"] == "ok"
    assert "tippspiel_" in status[0]["detail"]
    assert "Bytes" in status[0]["detail"]


def test_bootstrap_noop_wenn_flask_importierbar():
    """Mit Flask im Pfad (lokal/venv) darf der Bootstrap nichts veraendern."""
    import cron_jobs
    before = list(cron_jobs.sys.path)
    cron_jobs._bootstrap_dependencies()
    assert cron_jobs.sys.path == before


def test_bootstrap_ohne_flask_kein_crash(monkeypatch):
    """Ohne Flask, ohne vendor/ und ohne .python-venvs in der Naehe: kein Crash."""
    import cron_jobs
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    # Sicherheitsnetz: re-exec darf den Testprozess niemals ersetzen
    monkeypatch.setattr(cron_jobs.os, "execl",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    cron_jobs._bootstrap_dependencies()  # laeuft still durch


# ---------------------------------------------------------------- Cron-HTTP
# Netcup-Plesk führt Cronjobs im chroot ohne Python aus - die Aufgaben rufen
# deshalb /cron/run per wget/php auf; die App führt die Arbeit selbst aus.

def _set_cron_secret(app, secret="TESTKEY"):
    with app.app_context():
        set_setting("cron_secret", secret)


def test_cron_http_ohne_secret_deaktiviert(client):
    resp = client.get("/cron/run?task=backup&key=x")
    assert resp.status_code == 404
    assert b"deaktiviert" in resp.data


def test_cron_http_falscher_key_403(client, app, db):
    _set_cron_secret(app)
    resp = client.get("/cron/run?task=backup&key=FALSCH")
    assert resp.status_code == 403


def test_cron_http_backup_laeuft_mit_key(client, app, db, monkeypatch):
    import cron_jobs
    _set_cron_secret(app)
    called = []

    def fake_backup():
        # Vertrag wie backup.py: die Backup-Task schreibt ihren Heartbeat
        # selbst (inkl. Detail) - _run_task_safe doppelt ihn nicht.
        called.append("backup")
        record_cron_run("backup", ok=True, detail="tippspiel_fake.db (123 Bytes)")
        return True

    monkeypatch.setattr(cron_jobs, "run_backup", fake_backup)
    resp = client.get("/cron/run?task=backup&key=TESTKEY")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert called == ["backup"]
    with app.app_context():
        status = get_cron_status({"backup": cron_heartbeat.CRON_TASKS["backup"]})
        assert status[0]["ok"] is True  # Heartbeat wurde geschrieben
        # Regression Doppel-Heartbeat: Detail bleibt erhalten
        assert status[0]["detail"] == "tippspiel_fake.db (123 Bytes)"


def test_cron_http_all_fuehrt_sync_bots_reminder_aus(client, app, db, monkeypatch):
    import cron_jobs
    _set_cron_secret(app)
    called = []
    monkeypatch.setattr(cron_jobs, "run_sync", lambda: called.append("sync") or True)
    monkeypatch.setattr(cron_jobs, "run_bot_tips", lambda: called.append("bots") or True)
    monkeypatch.setattr(cron_jobs, "run_reminders", lambda: called.append("reminder") or True)
    resp = client.get("/cron/run?task=all&key=TESTKEY")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert called == ["sync", "bots", "reminder"]


def test_cron_http_fehler_wird_gemeldet(client, app, db, monkeypatch):
    import cron_jobs
    _set_cron_secret(app)
    monkeypatch.setattr(cron_jobs, "run_backup",
                        lambda: (_ for _ in ()).throw(RuntimeError("kaputt")))
    resp = client.get("/cron/run?task=backup&key=TESTKEY")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is False
    with app.app_context():
        status = get_cron_status({"backup": cron_heartbeat.CRON_TASKS["backup"]})
        assert status[0]["ok"] is False


def test_cron_http_unbekannte_task_400(client, app, db):
    _set_cron_secret(app)
    resp = client.get("/cron/run?task=quatsch&key=TESTKEY")
    assert resp.status_code == 400
