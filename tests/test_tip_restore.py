"""Spitzenfallschutz: verlorene Tipps aus App-Backup zurueckholen (tip_restore).

Simuliert den Incident vom 10.09.2026: Live zeigt ein finished-Spiel ohne
einzige Prediction (Altzeile wurde nach Provider-Re-Keying purged), das Backup
enthaelt noch die alten Tippzeilen. Der Restore darf genau diese Zeilen
umhaengig (mit neuer match_id) einsetzen - idempotent, ohne die Live-DB zu
ueberschreiben, Joker nur wenn der Slot in Live noch frei ist.
"""
import sqlite3
from datetime import datetime, timezone

import pytest

from extensions import db
from models import Competition, Match, Prediction, Team, User

BACKUP_SCHEMA = """
CREATE TABLE matches (id INTEGER PRIMARY KEY, competition_id INT, matchday INT,
                      home_team_id INT, away_team_id INT, status TEXT, external_id TEXT);
CREATE TABLE predictions (id INTEGER PRIMARY KEY, user_id INT, match_id INT,
                          home_tip INT, away_tip INT, joker INT, points INT,
                          created_at TEXT, updated_at TEXT);
CREATE TABLE comments (id INTEGER PRIMARY KEY, user_id INT, match_id INT,
                       text TEXT, created_at TEXT);
"""


def _write_backup(path, rows):
    con = sqlite3.connect(path)
    with con:
        con.executescript(BACKUP_SCHEMA)
        con.executemany("INSERT INTO matches VALUES (?,?,?,?,?,?,?)", rows["matches"])
        con.executemany("INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?)", rows["preds"])
        con.executemany("INSERT INTO comments VALUES (?,?,?,?,?)", rows["comments"])
    con.close()


@pytest.fixture
def world(db, monkeypatch, tmp_path):
    """Live-Welt + ein Backup (als Datei) + Monkeypatch der Backup-Liste."""
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                            matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    t1 = Team(name="Rest Heim", short_name="RH", logo="x.png")
    t2 = Team(name="Rest Aus", short_name="RA", logo="x.png")
    db.session.add_all([t1, t2])
    db.session.commit()
    users = []
    for i in (1, 2):
        u = User(username=f"rest{i}", email=f"rest{i}@x.test", full_name=f"R{i}")
        u.set_password("pw12345678")
        db.session.add(u)
        users.append(u)
    db.session.commit()
    # Verwaistes Spiel: finished, Ergebnis vorhanden, KEINE Tipps.
    ghost = Match(competition_id=comp.id, matchday=1, home_team_id=t1.id, away_team_id=t2.id,
                  kickoff=datetime(2026, 8, 22, 13, 30, tzinfo=timezone.utc),
                  status="finished", home_score=2, away_score=1, external_id="fd:new")
    # Gesundes Spiel derselben Runde, auf dem u1 bereits seinen Joker hat.
    t3 = Team(name="Dritte", short_name="D3", logo="x.png")
    t4 = Team(name="Vierte", short_name="D4", logo="x.png")
    db.session.add_all([t3, t4])
    db.session.add(ghost)
    db.session.commit()
    other = Match(competition_id=comp.id, matchday=1, home_team_id=t3.id, away_team_id=t4.id,
                  kickoff=datetime(2026, 8, 22, 15, 30, tzinfo=timezone.utc),
                  status="finished", home_score=1, away_score=1, external_id="fd:ok")
    db.session.add(other)
    db.session.commit()
    db.session.add(Prediction(user_id=users[0].id, match_id=other.id, home_tip=1, away_tip=1, joker=True))
    db.session.commit()

    backups = {}

    def add_backup(name, donor_pred_rows, donor_comment_rows):
        f = tmp_path / name
        _write_backup(str(f), {
            "matches": [(900, comp.id, 1, t1.id, t2.id, "finished", "fd:old")],
            "preds": donor_pred_rows,
            "comments": donor_comment_rows,
        })
        backups[name] = str(f)
        monkeypatch.setattr(
            "backup.list_backups",
            lambda: [{"path": p, "name": n, "size": 1, "mtime": "x"}
                     for n, p in sorted(backups.items(), reverse=True)],
        )

    donor = [
        (1, users[0].id, 900, 2, 1, 1, 4, "2026-08-22 09:00:00.000000+00:00", "2026-08-22 09:00:00.000000+00:00"),
        (2, users[1].id, 900, 0, 0, 0, 0, "2026-08-22 09:05:00.000000+00:00", "2026-08-22 09:05:00.000000+00:00"),
    ]
    add_backup("tippspiel_2026-09-05_031500.db", donor,
               [(1, users[0].id, 900, "klassischer Heimsieg", "2026-08-22 13:59:00.000000+00:00")])
    return {"comp": comp, "ghost": ghost, "other": other, "users": users,
            "add_backup": add_backup}


def test_preview_finds_restorable_tips(world):
    import tip_restore
    r = tip_restore.preview_restore()
    assert r["ok"] is True
    assert r["used"] == "tippspiel_2026-09-05_031500.db"
    assert len(r["plan"]["predictions"]) == 2
    assert len(r["plan"]["comments"]) == 1
    assert "2 Tipps" in r["message"]


def test_restore_inserts_remapped_and_is_idempotent(world):
    import tip_restore
    ghost_id = world["ghost"].id
    u1 = world["users"][0].id

    r = tip_restore.run_restore()
    assert r["ok"] is True and r["inserted_predictions"] == 2
    preds = Prediction.query.filter_by(match_id=ghost_id).all()
    assert len(preds) == 2
    restored_u1 = next(p for p in preds if p.user_id == u1)
    assert restored_u1.home_tip == 2 and restored_u1.away_tip == 1
    # Joker-Unterdrueckung: u1 hat seinen ST1-Joker schon auf dem anderen Spiel.
    assert restored_u1.joker is False
    # Originalzeitpunkt bleibt erhalten (tz-aware aus Backup -> naive UTC).
    assert restored_u1.created_at.year == 2026 and restored_u1.created_at.tzinfo is None
    # Punkte wurden nach dem Insert neu berechnet: exaktes 2:1 zaehlt wieder.
    assert restored_u1.points and restored_u1.points > 0

    before = Prediction.query.count()
    again = tip_restore.run_restore()
    assert Prediction.query.count() == before  # nichts doppelt
    assert "nichts zu retten" in again["message"]


def test_older_backup_used_when_newest_has_no_donors(world):
    import tip_restore
    # Neueres Backup ohne Spender-Tipps: Scan muss eine Datei zurueckgehen.
    world["add_backup"]("tippspiel_2026-09-10_031500.db", [], [])
    r = tip_restore.scan()
    assert r["ok"] is True
    assert r["used"] == "tippspiel_2026-09-05_031500.db"
    assert r["files_checked"] == 2


def test_partially_tipped_match_is_left_alone(world):
    """Sobald auch nur EIN Tipp auf dem Spiel liegt, ist es kein Rettungs-
    ziel mehr - vorhandende Staende werden nie angefasst oder aufgefuettert."""
    import tip_restore
    db.session.add(Prediction(user_id=world["users"][1].id, match_id=world["ghost"].id,
                              home_tip=0, away_tip=0))
    db.session.commit()
    r = tip_restore.run_restore()
    assert "nichts zu retten" in r["message"]
    assert Prediction.query.filter_by(match_id=world["ghost"].id).count() == 1


def test_donor_tips_of_unknown_users_are_skipped(world):
    import tip_restore
    # Neuestes Backup enthaelt nur den Tipp eines Users, den es in Live nicht gibt.
    world["add_backup"](
        "tippspiel_2026-09-11_031500.db",
        [(1, 99999, 900, 2, 1, 0, 4, "2026-08-22 09:00:00.000000+00:00", None)],
        [],
    )
    r = tip_restore.scan()
    # leerer Plan im neuesten -> eine Datei zurueck auf das 05.09.-Backup
    assert r["used"] == "tippspiel_2026-09-05_031500.db"
    res = tip_restore.run_restore()
    assert res["inserted_predictions"] == 2
    assert Prediction.query.filter_by(match_id=world["ghost"].id).count() == 2


def test_only_files_from_backup_dir_are_accepted(world):
    import tip_restore
    r = tip_restore.scan(explicit_backup="../../etc/passwd")
    assert r["ok"] is False
    assert "nicht" in r["message"]
