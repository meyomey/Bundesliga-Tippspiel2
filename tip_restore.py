"""Rettungs-Aktion: verlorene Tipps aus einem Tages-Backup zurueckholen.

Hintergrund (10.09.2026): Der Sync-Purge hat einstmals Alt-Spielzeilen mitsamt
aller Predictions/Kommentare geloescht, als der Datenprovider drei Spiele neu
numeriert hatte (neue externe IDs -> Ersatzzeilen ohne Tipps). Dieses Modul
spielt NICHT ein komplettes Backup ein (dabei gainge alles seit dem
Backup-Zeitpunkt verloren), sondern uebertraegt gezielt nur die Tippzeilen,
die in der Live-DB fehlen:

  * Ziel:  Live-Spiele (fertige/laufende) des aktiven Wettbewerbs ohne
           einzige Prediction.
  * Spender: im Backup dasselbe Duell (Wettbewerb/Spieltag/Heim/Auswaerts)
           mit Vorhersagen - deren Tipps (+ Kommentare) werden auf die Live-
           Zeile umgebuft.

Sicherheit: Backup wird ausschliesslich read-only geoeffnet (Datei muss aus
BACKUP_DIR stammen, Auswahl ueber die Backup-Liste der Admin-Seite); die
Aktion ist idempotent (bereits vorhandene (User, Spiel)-Tipps werden
uebersprungen, nie uebgeschrieben); Joker werden nur gesetzt, wenn der User
an dem Spieltag in Live noch keinen Joker hat.
"""
import sqlite3
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import func

from extensions import db
from models import Comment, Match, Prediction, User


def _backup_files():
    """Vorhandene Backups (neuestes zuerst) als Liste von Dicts."""
    try:
        from backup import list_backups
        return list_backups()
    except Exception as e:  # pragma: no cover - Konfig-/Datei-Probleme
        current_app.logger.warning(f"Backup-Liste nicht lesbar: {e}")
        return []


def _resolve_backup(name):
    """Nur exakt in der Backup-Liste vorhandene Dateinamen akzeptieren."""
    if not name:
        return None
    base = str(name).rsplit("/", 1)[-1]
    for b in _backup_files():
        if b["name"] == base:
            return b["path"]
    return None


def _open_ro(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _fixture_key(comp_id, matchday, home_id, away_id):
    return (comp_id, matchday, home_id, away_id)


def _live_targets(comp):
    """Live-Spiele mit 0 Tipps (Kandidaten fuer Datenverlust)."""
    q = (
        db.session.query(Match)
        .outerjoin(Prediction, Prediction.match_id == Match.id)
        .filter(Match.status.in_(("finished", "live")))
        .group_by(Match.id)
        .having(func.count(Prediction.id) == 0)
    )
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    return q.all()


def _backup_index(conn, wanted_keys):
    """Alle Backup-Spiele der Ziel-Ansetzungen, sortiert nach Tippzahl."""
    idx = {}
    try:
        rows = conn.execute(
            "SELECT id, competition_id, matchday, home_team_id, away_team_id "
            "FROM matches"
        ).fetchall()
        counts = {
            r["match_id"]: r["c"]
            for r in conn.execute(
                "SELECT match_id, COUNT(*) AS c FROM predictions GROUP BY match_id"
            ).fetchall()
        }
    except sqlite3.Error:
        return idx
    for r in rows:
        key = _fixture_key(r["competition_id"], r["matchday"], r["home_team_id"], r["away_team_id"])
        if key in wanted_keys:
            idx.setdefault(key, []).append((counts.get(r["id"], 0), r["id"]))
    for key in idx:
        idx[key].sort(reverse=True)  # Spender mit den meisten Tipps zuerst
    return idx


def _parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:  # SA/SQLite speichert teils mit Offset -> naive UTC
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _plan_from_backup(conn, targets, comp):
    """Rein lesender Plan: was wuerde aus diesem Backup zurueckkommen?"""
    live_user_ids = {u.id for u in User.query.all()}
    existing = {
        (p.user_id, p.match_id)
        for p in Prediction.query.filter(
            Prediction.match_id.in_([m.id for m in targets] or [-1])
        ).all()
    }
    joker_md_users = {
        (p.user_id, m.matchday)
        for p, m in db.session.query(Prediction, Match).join(
            Match, Prediction.match_id == Match.id
        ).filter(Prediction.joker.is_(True)).all()
    }
    wanted = {
        _fixture_key(m.competition_id, m.matchday, m.home_team_id, m.away_team_id): m
        for m in targets
    }
    donors = _backup_index(conn, set(wanted))

    preds, comments = [], []
    for key, live_match in wanted.items():
        candidates = donors.get(key, [])
        donor_id = next((mid for cnt, mid in candidates if cnt > 0), None)
        if donor_id is None:
            continue
        rows = conn.execute(
            "SELECT user_id, home_tip, away_tip, joker, points, created_at, updated_at "
            "FROM predictions WHERE match_id = ?",
            (donor_id,),
        ).fetchall()
        for r in rows:
            if r["user_id"] not in live_user_ids:
                continue  # User gibt es in Live nicht (mehr)
            if (r["user_id"], live_match.id) in existing:
                continue  # idempotent: vorhanden laesst man vorhanden
            joker = bool(r["joker"]) and (r["user_id"], live_match.matchday) not in joker_md_users
            preds.append({
                "user_id": r["user_id"], "match_id": live_match.id,
                "home_tip": r["home_tip"], "away_tip": r["away_tip"],
                "joker": joker, "points": int(r["points"] or 0),
                "created_at": _parse_dt(r["created_at"]),
                "updated_at": _parse_dt(r["updated_at"]),
                "match_label": f"ST {live_match.matchday} #{live_match.id}",
            })
        # Kommentare nur, wenn das Live-Spiel noch gar keine hat (kein Duplikat-Risiko)
        if Comment.query.filter(Comment.match_id == live_match.id).count() == 0:
            for c in conn.execute(
                "SELECT user_id, text, created_at FROM comments WHERE match_id = ?",
                (donor_id,),
            ).fetchall():
                if c["user_id"] in live_user_ids:
                    comments.append({
                        "user_id": c["user_id"], "match_id": live_match.id,
                        "text": c["text"], "created_at": _parse_dt(c["created_at"]),
                    })
    return {"predictions": preds, "comments": comments, "comp_id": comp.id if comp else None}


def scan(explicit_backup=None):
    """Findet das neueste Backup mit verwertbaren Spender-Tipps.

    Returns dict(ok, used, files_checked, plan, message).
    """
    from competition_helpers import get_active_competition
    comp = get_active_competition()
    targets = _live_targets(comp)
    if not targets:
        return {"ok": True, "used": None, "files_checked": 0,
                "plan": {"predictions": [], "comments": []},
                "message": "Kein Spiel ohne Tipps gefunden - es gibt nichts zu retten."}
    files = _backup_files()
    if explicit_backup:
        path = _resolve_backup(explicit_backup)
        if not path:
            return {"ok": False, "used": None, "files_checked": 0, "message":
                    f"Backup '{explicit_backup}' nicht in {len(files)} vorhandenen Backups gefunden."}
        files = [f for f in files if f["path"] == path]
    if not files:
        return {"ok": False, "used": None, "files_checked": 0,
                "message": "Keine Backups im Backup-Ordner gefunden."}
    last_error = None
    for f in files:
        conn = None
        try:
            conn = _open_ro(f["path"])
            plan = _plan_from_backup(conn, targets, comp)
        except sqlite3.Error as e:
            last_error = e
            continue
        finally:
            if conn is not None:
                conn.close()
        if plan["predictions"] or plan["comments"]:
            summary = (f"Backup {f['name']}: {len(plan['predictions'])} Tipps "
                       f"({len(plan['comments'])} Kommentare) aus {len(targets)} tippleeren Spielen rettbar")
            return {"ok": True, "used": f["name"], "files_checked": files.index(f) + 1,
                    "plan": plan, "message": summary}
    msg = ("Keines der gepueften Backups enthaelt verwertbare Tipps fuer diese Spiele "
           f"({len(files)} Datei(en) geprueft)")
    if last_error:
        msg += f" - letzte Dateierror: {last_error}"
    return {"ok": True, "used": None, "files_checked": len(files),
            "plan": {"predictions": [], "comments": []}, "message": msg}


def preview_restore(explicit_backup=None):
    """Read-only-Vorschau: fuehrt nichts aus."""
    result = scan(explicit_backup)
    plan = result.get("plan") or {}
    result["details"] = [
        f"{p['match_label']}: User #{p['user_id']} {p['home_tip']}:{p['away_tip']}"
        + (" [Joker]" if p["joker"] else "")
        for p in plan.get("predictions", [])[:30]
    ]
    return result


def run_restore(explicit_backup=None):
    """Fuegt die fehlenden Tipp-/Kommentarzeilen ein und berechnet Punkte neu."""
    result = scan(explicit_backup)
    plan = result.get("plan") or {}
    preds = plan.get("predictions", [])
    comments = plan.get("comments", [])
    if not preds and not comments:
        return result
    users = set()
    for p in preds:
        db.session.add(Prediction(
            user_id=p["user_id"], match_id=p["match_id"],
            home_tip=p["home_tip"], away_tip=p["away_tip"],
            joker=p["joker"], points=p["points"],
            created_at=p["created_at"],
        ))
        users.add(p["user_id"])
    if comments:
        base = datetime.now(timezone.utc)
        for c in comments:
            db.session.add(Comment(
                user_id=c["user_id"], match_id=c["match_id"], text=c["text"],
                created_at=c["created_at"] or base,
            ))
    db.session.commit()
    try:
        from scoring import recalculate_all_points
        recalculate_all_points()
        recalced = "; Punkte neu berechnet"
    except Exception as e:  # pragma: no cover - Defensivpfad
        current_app.logger.error(f"Punkte-Neuberechnung nach Restore fehlgeschlagen: {e}", exc_info=True)
        recalced = f"; WARNUNG: Punkte-Neuberechnung fehlgeschlagen ({e})"
    try:
        from cache import invalidate_leaderboard
        invalidate_leaderboard()
    except Exception:
        pass
    result["message"] = (f"{len(preds)} Tipps fuer {len(users)} User + {len(comments)} Kommentare "
                         f"aus {result['used']} zurueckgeholt{recalced}. "
                         "Erneutes Ausfuehren ist gefahrlos (Duplikate werden uebersprungen).")
    result["inserted_predictions"] = len(preds)
    result["inserted_comments"] = len(comments)
    return result
