"""Backup-Restore-Drill ((82), Kandidat 6).

Ein Backup ist erst dann ein Backup, wenn ein Restore geuebt wurde: Diese
Tests spielen den Ernstfall auf echter SQLite-DATEI durch — genau wie auf
Netcup (Backup-Datei per FTP zurueckkopieren + Neustart). Die App-Factory
laeuft dazu ein zweites Mal mit Datei-DB statt In-Memory.
"""
import os
import shutil
import sqlite3
import time

import pytest

from app import create_app
from backup import create_database_backup, list_backups
from config import TestConfig
from cron_heartbeat import CRON_TASKS, get_cron_status
from extensions import db
from models import Competition, Match, Prediction, Team, User


def _drill_app(tmp_path, name="drill.db"):
    """Zweite App-Instanz auf echter Datei-DB + eigenem Backup-Ordner."""
    drill_path = tmp_path / name
    drill_uri = "sqlite:///" + str(drill_path)
    backup_dir = tmp_path / "backups"

    class DrillConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = drill_uri
        BACKUP_DIR = str(backup_dir)

    app = create_app(DrillConfig)
    return app, str(drill_path), str(backup_dir)


def _notfall_seed():
    """Bekannter Datenbestand: 2 Spieler, 1 beendetes Spiel, 1 exakter Tipp."""
    comp = Competition(code="TEST", name="Test League", season="2025/26",
                       matchdays=34, teams_count=18)
    db.session.add(comp)
    db.session.flush()
    heim = Team(name="FC Bayern München", short_name="FCB", logo="x.png")
    gast = Team(name="Borussia Dortmund", short_name="BVB", logo="y.png")
    db.session.add_all([heim, gast])
    db.session.flush()
    spieler = User(username="drillspieler", email="drill@example.com")
    spieler.set_password("geheim123")
    db.session.add(spieler)
    db.session.flush()
    from datetime import datetime, timedelta, timezone
    spiel = Match(competition_id=comp.id, matchday=1,
                  home_team_id=heim.id, away_team_id=gast.id,
                  kickoff=datetime.now(timezone.utc) - timedelta(hours=3),
                  status="finished", home_score=2, away_score=1)
    db.session.add(spiel)
    db.session.flush()
    tipp = Prediction(user_id=spieler.id, match_id=spiel.id,
                      home_tip=2, away_tip=1, joker=False, points=4)
    db.session.add(tipp)
    db.session.commit()
    return {"user": spieler, "tipp": tipp, "match": spiel,
            "user_pw": "geheim123"}


def test_restore_drill_vollstaendiger_wiederaufbau(tmp_path):
    """Ernstfall komplett: Backup ziehen → Datenbestand verlieren →
    Backup-Datei zurueckkopieren → alles wieder da, Integritaet ok."""
    app, drill_path, backup_dir = _drill_app(tmp_path)
    with app.app_context():
        db.create_all()
        bestand = _notfall_seed()

        # 1) Backup ziehen (Rotation/Heartbeat wie in Produktion)
        res = create_database_backup()
        assert res["ok"] is True
        assert os.path.exists(res["file"]) and res["size"] > 0
        # Herzschlag schlaegt NACH der Kopie — fuer den live-DB sichtbar:
        assert get_cron_status({"backup": CRON_TASKS["backup"]})[0]["state"] == "ok"
        # IDs als einfache Werte sichern (nach session.remove() detached)
        tipp_id, spiel_id = bestand["tipp"].id, bestand["match"].id

        # 2) DER DATENVERLUST: alles weg (Reihenfolge nach FKs)
        db.session.query(Prediction).delete()
        db.session.query(Match).delete()
        db.session.query(Team).delete()
        db.session.query(User).delete()
        db.session.query(Competition).delete()
        db.session.commit()
        assert db.session.query(User).count() == 0
        assert db.session.query(Prediction).count() == 0

        # 3) DER RESTORE: Engine schliessen + Backup-Datei zurueckkopieren
        #    (Netcup-Praxis: FTP-Kopie ueber die beschaedigte tippspiel.db)
        db.session.remove()
        db.engine.dispose()
        shutil.copyfile(res["file"], drill_path)

        # 4) Verifikation: Bestand vollstaendig zurueck
        spieler = db.session.query(User).filter_by(
            username="drillspieler").first()
        assert spieler is not None
        assert spieler.check_password(bestand["user_pw"])
        tipp = db.session.get(Prediction, tipp_id)
        assert tipp is not None and tipp.points == 4
        spiel = db.session.get(Match, spiel_id)
        assert spiel.status == "finished" and spiel.home_score == 2

        # 5) SQLite-Integritaetscheck auf der restaurierten Datei
        con = sqlite3.connect(drill_path)
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        con.close()

        # 6) Heartbeat des Backups ist IM RESTORE bewusst nicht drin — er
        #    wurde erst nach der Kopie geschrieben (herzschlug in die live-DB,
        #    nicht ins Backup). 'never' hier ist der korrekte Ist-Zustand.
        status = get_cron_status({"backup": CRON_TASKS["backup"]})
        assert status[0]["state"] == "never"


def test_restore_drill_aelteres_backup_punkt_in_time(tmp_path):
    """Zwei Backup-Zeitpunkte: Nach einer Aenderung laesst sich gezielt der
    AELTERE Stand zurueckspielen (point-in-time-Wahl)."""
    app, drill_path, backup_dir = _drill_app(tmp_path, "drill2.db")
    with app.app_context():
        db.create_all()
        bestand = _notfall_seed()

        erst = create_database_backup()
        assert erst["ok"] is True

        # Sekunden-Stempel der Backup-Namen auseinanderhalten
        time.sleep(1.1)
        # Aenderung NACH dem ersten Backup
        bestand["user"].full_name = "Nach der Sicherung"
        db.session.commit()

        zweit = create_database_backup()
        assert zweit["ok"] is True and zweit["file"] != erst["file"]
        assert len(list_backups()) >= 2
        tipp_id, nutzer_id = bestand["tipp"].id, bestand["user"].id

        # Gezielt den AELTEREN Stand zurueckspielen
        db.session.remove()
        db.engine.dispose()
        shutil.copyfile(erst["file"], drill_path)

        spieler = db.session.get(User, nutzer_id)
        assert spieler.full_name is None        # Aenderung ist weg — so gewollt
        assert db.session.get(Prediction, tipp_id) is not None
