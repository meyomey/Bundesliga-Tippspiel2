"""Tests fuer Cron-Heartbeat und Datenbank-Backup (Produktions-Absicherung).

Deckt ab: konsistente SQLite-Backups per Backup-API, Rotation alter Dateien,
Fehlerfaelle (kein SQLite / Datei fehlt), Heartbeat-Roundtrip inkl. Alters-
Bewertung (ok/warn/error/never), Admin-Wartungscenter-Anzeige und die
Task-Dispatch-Logik von cron_jobs.py.
"""
import os
import shutil
import sqlite3
import sys
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
                   "Plesk-Cron noch nicht eingerichtet?",
                   "cron/run?task=all", "cron/run?task=backup",
                   "wget -q -O /dev/null",
                   "CRON_SECRET",
                   "Backups verwalten"]:
        assert marker.encode("utf-8") in resp.data, f"fehlt: {marker}"
    # Zusammenfuehrung: Backup-AKTIONEN leben auf /admin/backup, nicht mehr hier
    assert "Jetzt Backup erstellen".encode("utf-8") not in resp.data


def test_backup_seite_buendelt_alle_backup_funktionen(client, db, admin_user):
    """Regression Zusammenfuehrung: /admin/backup zeigt Server-Backups
    (erstellen + Automatik-Status), Download UND Restore auf einer Seite."""
    _login_admin(client, admin_user)
    resp = client.get("/admin/backup")
    assert resp.status_code == 200
    for marker in ["Server-Backups", "Jetzt Backup erstellen",
                   "noch nie gelaufen",          # Automatik-Status (Heartbeat backup)
                   "Backup herunterladen",
                   "Backup wiederherstellen"]:
        assert marker.encode("utf-8") in resp.data, f"fehlt: {marker}"


def test_backup_seite_zeigt_letzten_automatik_lauf(client, app, db, admin_user):
    _login_admin(client, admin_user)
    with app.app_context():
        record_cron_run("backup", ok=True, detail="tippspiel_x.db (999 Bytes)")
    resp = client.get("/admin/backup")
    assert resp.status_code == 200
    assert "tippspiel_x.db (999 Bytes)".encode("utf-8") in resp.data
    assert "letzter Lauf vor".encode("utf-8") in resp.data


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
    # Redirect fuehrt seit der Zusammenfuehrung auf die Backup-Seite
    assert "Server-Backups".encode("utf-8") in resp.data


def test_wartungscenter_backup_now_fehler(client, db, admin_user, monkeypatch):
    import backup
    _login_admin(client, admin_user)

    def fake_backup():
        return {"ok": False, "error": "kaputt", "file": None, "size": 0, "removed": []}

    monkeypatch.setattr(backup, "create_database_backup", fake_backup)
    resp = client.post("/admin/maintenance/backup-now", follow_redirects=True)
    assert resp.status_code == 200
    assert "Backup fehlgeschlagen".encode("utf-8") in resp.data


def test_admin_dashboard_gruppentitel_und_backup_link(client, db, admin_user):
    """Dashboard: Gruppen mit Akzent-Klassen + Icon-Chip (Hierarchie-Fix) und
    der Wartungs-Link heisst jetzt 'Backups' statt 'Backup & Restore'."""
    _login_admin(client, admin_user)
    resp = client.get("/admin/")
    assert resp.status_code == 200
    for marker in ["ams-play", "ams-people", "ams-tools", "ams-season",
                   "ams-ico", "💾 Backups</span>"]:
        assert marker.encode("utf-8") in resp.data, f"fehlt: {marker}"
    assert "Backup &amp; Restore".encode("utf-8") not in resp.data


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


# ================================================================ Coverage-Runde
# Luecken: backup.py (relativer DB-Pfad, list_backups-Happy-Path, Rotations-
# OSError) und cron_jobs.py (run_*-Körper, Bootstrap-Zweige, Dispatch
# reminder/bots, Skript-Eintrittspunkt).


def test_db_file_path_berechnet_relative_pfade(app, monkeypatch):
    """sqlite:///relativ.db wird gegen die App-Root geloest (nicht gegen CWD)."""
    from backup import _db_file_path
    monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI", "sqlite:///relativ_test.db")
    with app.app_context():
        assert _db_file_path() == os.path.join(app.root_path, "relativ_test.db")


def test_list_backups_listet_dateien_neueste_zuerst(app, monkeypatch, tmp_path):
    bdir = tmp_path / "backups"
    bdir.mkdir()
    (bdir / "tippspiel_20260101_031500.db").write_bytes(b"x" * 100)
    (bdir / "tippspiel_20260102_031500.db").write_bytes(b"x" * 250)
    (bdir / "kein_backup.txt").write_text("darf nicht gelistet werden")
    monkeypatch.setitem(app.config, "BACKUP_DIR", str(bdir))
    with app.app_context():
        items = list_backups()
    assert [i["name"] for i in items] == ["tippspiel_20260102_031500.db",
                                          "tippspiel_20260101_031500.db"]
    assert items[0]["size"] == 250
    assert items[0]["path"].endswith("tippspiel_20260102_031500.db")
    assert items[0]["mtime"]


def test_rotate_ignoriert_loeschfehler(app, monkeypatch, tmp_path):
    """Nicht loeschbare Datei (Rechte o. a.) bricht die Rotation nicht ab."""
    import backup as backup_mod
    bdir = tmp_path / "backups"
    bdir.mkdir()
    for i in range(1, 4):
        (bdir / f"tippspiel_2026010{i}_031500.db").write_bytes(b"x")

    def _loesch_verweigert(*a, **k):
        raise OSError("Zugriff verweigert")

    monkeypatch.setattr(os, "remove", _loesch_verweigert)
    assert backup_mod._rotate(str(bdir), 1) == []
    # alle drei Dateien sind weiterhin vorhanden
    assert len(list(bdir.glob("tippspiel_*.db"))) == 3


def test_cron_jobs_dispatch_reminder_und_bots(monkeypatch):
    import cron_jobs
    called = []
    monkeypatch.setattr(cron_jobs, "run_reminders", lambda: called.append("reminder") or True)
    monkeypatch.setattr(cron_jobs, "run_bot_tips", lambda: called.append("bots") or True)
    monkeypatch.setattr("cron_heartbeat.record_cron_run", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "reminder"])
    cron_jobs.main()
    monkeypatch.setattr("sys.argv", ["cron_jobs.py", "bots"])
    cron_jobs.main()
    assert called == ["reminder", "bots"]


def test_run_sync_gibt_syncergebnis_weiter(monkeypatch):
    """run_sync laeuft den Sync im App-Kontext ab und gibt result['ok'] zurueck."""
    import cron_jobs
    import utils
    monkeypatch.setattr(utils, "sync_results",
                        lambda: {"ok": True, "msg": "3 Spiele gesynced"})
    assert cron_jobs.run_sync() is True


def test_run_reminders_fuehrt_zyklus_aus(monkeypatch):
    import cron_jobs
    import notification_center
    monkeypatch.setattr(notification_center, "run_reminder_cycle",
                        lambda channels=None, now=None: {"wave1": 1, "wave2": 0})
    assert cron_jobs.run_reminders() is True


def test_run_bot_tips_bei_deaktiviertem_autotipp(monkeypatch, capsys):
    import cron_jobs
    import scoring
    monkeypatch.setattr(scoring, "get_setting", lambda key, default=None: "false")
    assert cron_jobs.run_bot_tips() is True
    assert "deaktiviert" in capsys.readouterr().out


def test_run_bot_tips_aktiv_mit_und_ohne_fehler(monkeypatch, capsys):
    from types import SimpleNamespace
    import ai_opponent
    import cron_jobs
    import scoring
    import stats
    monkeypatch.setattr(scoring, "get_setting", lambda key, default=None: "true")
    monkeypatch.setattr(stats, "get_current_matchday", lambda: 3)
    summaries = [
        {"ROOKIE": {"tipped": 2, "skipped": 1, "errors": 0}},
        {"EXPERT": {"tipped": 1, "skipped": 0, "errors": 2}},
    ]

    def fake_tip_all_matches(matchday, overwrite):
        return SimpleNamespace(summary_by_bot=summaries.pop(0))

    monkeypatch.setattr(ai_opponent, "get_ai_manager",
                        lambda: SimpleNamespace(tip_all_matches=fake_tip_all_matches))
    assert cron_jobs.run_bot_tips() is True
    out = capsys.readouterr().out
    assert "Spieltag 3" in out and "2 Tipps" in out
    assert "FEHLER" not in out
    assert cron_jobs.run_bot_tips() is True
    assert "2 FEHLER" in capsys.readouterr().out


def test_run_backup_meldet_erfolg_und_fehler(monkeypatch, capsys):
    import backup as backup_mod
    import cron_jobs
    calls = []

    def fake_backup(keep=None):
        calls.append(1)
        if len(calls) == 1:
            return {"ok": True, "name": "tippspiel_test.db", "size": 42,
                    "error": None, "file": "x", "removed": ["alt.db"]}
        return {"ok": False, "error": "Datenbankdatei fehlt",
                "file": None, "size": 0, "removed": []}

    monkeypatch.setattr(backup_mod, "create_database_backup", fake_backup)
    assert cron_jobs.run_backup() is True
    out = capsys.readouterr().out
    assert "tippspiel_test.db (42 Bytes)" in out and "1 alte entfernt" in out
    assert cron_jobs.run_backup() is False
    assert "FEHLER - Datenbankdatei fehlt" in capsys.readouterr().out


def test_run_status_zeigt_alle_zustaende_aus(monkeypatch, capsys):
    import cron_heartbeat
    import cron_jobs
    rows = [
        {"label": "Sync", "state": "ok", "age_minutes": 12, "detail": "180 Spiele"},
        {"label": "Bots", "state": "warn", "age_minutes": None, "detail": ""},
        {"label": "Backup", "state": "error", "age_minutes": 300, "detail": "OSError: kaputt"},
        {"label": "Reminder", "state": "never", "age_minutes": None, "detail": None},
    ]
    monkeypatch.setattr(cron_heartbeat, "get_cron_status", lambda *a, **k: rows)
    assert cron_jobs.run_status() is True
    out = capsys.readouterr().out
    assert "[OK  ]" in out and "12 min" in out and "180 Spiele" in out
    assert "[WARN]" in out
    assert "[FEHL]" in out and "OSError: kaputt" in out
    assert "[NIE ]" in out


def test_bootstrap_bindet_vendor_ordner_ein(monkeypatch):
    """Ohne importierbares Flask bindet der Bootstrap vendor/ ins sys.path ein."""
    import importlib.util
    import cron_jobs
    repo_root = os.path.dirname(os.path.abspath(cron_jobs.__file__))
    vendor_dir = os.path.join(repo_root, "vendor")
    created = not os.path.isdir(vendor_dir)
    os.makedirs(vendor_dir, exist_ok=True)
    try:
        real_find_spec = importlib.util.find_spec
        calls = {"n": 0}

        def fake_find_spec(name, *a, **k):
            if name == "flask":
                calls["n"] += 1
                # 1. Pruefe: kein Flask; nach Vendor-Einbindung: wieder da
                return None if calls["n"] == 1 else real_find_spec("flask")
            return real_find_spec(name, *a, **k)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
        cron_jobs._bootstrap_dependencies()
        assert vendor_dir in sys.path
    finally:
        if vendor_dir in sys.path:
            sys.path.remove(vendor_dir)
        if created and os.path.isdir(vendor_dir):
            shutil.rmtree(vendor_dir)


def test_bootstrap_liest_plesk_venvs_und_reexec_fehlerpfad(monkeypatch):
    """.python-venvs-Suche findet Kandidaten; fehlgeschlagener Re-Exec wird
    verschluckt (OSError), die Funktion laeuft bis zum Ende durch."""
    import importlib.util
    import cron_jobs
    app_dir = os.path.dirname(os.path.abspath(cron_jobs.__file__))
    parent = os.path.dirname(app_dir)  # erste Ebene ueber dem App-Verzeichnis
    venvs_dir = os.path.join(parent, ".python-venvs")
    venvs_created = not os.path.isdir(venvs_dir)
    fake_venv = os.path.join(venvs_dir, "wulmstorf_tipprunde")
    site = os.path.join(fake_venv, "lib", "python3.13", "site-packages")
    os.makedirs(site)
    py_bin = os.path.join(fake_venv, "bin", "python")
    os.makedirs(os.path.dirname(py_bin))
    open(py_bin, "w").close()
    execl_tried = []
    try:
        real_find_spec = importlib.util.find_spec

        def fake_find_spec(name, *a, **k):
            if name == "flask":
                if not execl_tried and not getattr(fake_find_spec, "seen", False):
                    fake_find_spec.seen = True
                    raise Exception("simulierter find_spec-Fehler")
                return None  # Flask bleibt "nicht da" -> kompletter Suchpfad
            return real_find_spec(name, *a, **k)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
        monkeypatch.setattr(os, "execl",
                            lambda *a, **k: execl_tried.append(a) or (_ for _ in ()).throw(OSError("simuliert")))
        cron_jobs._bootstrap_dependencies()
        assert site in sys.path            # Kandidat wurde gefunden und eingebunden
        assert execl_tried                 # Re-Exec mit venv-Python wurde versucht
    finally:
        if site in sys.path:
            sys.path.remove(site)
        if venvs_created and os.path.isdir(venvs_dir):
            shutil.rmtree(venvs_dir)


def test_cron_jobs_laeuft_als_skript_status():
    """Echter Eintrittspunkt: `python cron_jobs.py status` als Subprozess."""
    import subprocess
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, os.path.join(repo_root, "cron_jobs.py"), "status"],
                       cwd=repo_root, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0
    assert "letzter Lauf" in r.stdout


def test_bootstrap_findet_lokale_venv_site_packages(monkeypatch):
    """Macht der .python-venvs-Kandidat Flask importierbar, endet der Bootstrap
    dort (ohne Re-Exec) - die dritte Suchstufe wird nicht angestoßen."""
    import importlib.util
    import cron_jobs
    app_dir = os.path.dirname(os.path.abspath(cron_jobs.__file__))
    parent = os.path.dirname(app_dir)
    venvs_dir = os.path.join(parent, ".python-venvs")
    venvs_created = not os.path.isdir(venvs_dir)
    fake_venv = os.path.join(venvs_dir, "wulmstorf_tipprunde")
    site = os.path.join(fake_venv, "lib", "python3.13", "site-packages")
    os.makedirs(site)
    execl_attempts = []
    try:
        real_find_spec = importlib.util.find_spec
        calls = {"n": 0}

        def fake_find_spec(name, *a, **k):
            if name == "flask":
                calls["n"] += 1
                # erst nach Einbindung der site-packages ist Flask wieder da
                return None if calls["n"] <= 2 else real_find_spec("flask")
            return real_find_spec(name, *a, **k)

        monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
        monkeypatch.setattr(os, "execl", lambda *a, **k: execl_attempts.append(1))
        cron_jobs._bootstrap_dependencies()
        assert site in sys.path
        assert not execl_attempts
    finally:
        if site in sys.path:
            sys.path.remove(site)
        if venvs_created and os.path.isdir(venvs_dir):
            shutil.rmtree(venvs_dir)


def test_list_backups_ueberspringt_dateien_mit_stat_fehler(app, monkeypatch, tmp_path):
    """Eine zwischen Glob und stat verschwundene Datei wird uebersprungen."""
    bdir = tmp_path / "backups"
    bdir.mkdir()
    (bdir / "tippspiel_20260101_031500.db").write_bytes(b"x" * 10)
    (bdir / "tippspiel_20260102_031500.db").write_bytes(b"x" * 10)
    real_stat = os.stat

    def _stat_mit_fehler(p, *a, **k):
        if str(p).endswith("20260102_031500.db"):
            raise OSError("Datei verschwunden")
        return real_stat(p, *a, **k)

    monkeypatch.setattr(os, "stat", _stat_mit_fehler)
    monkeypatch.setitem(app.config, "BACKUP_DIR", str(bdir))
    with app.app_context():
        items = list_backups()
    assert [i["name"] for i in items] == ["tippspiel_20260101_031500.db"]
