"""Admin: Export-Helfer."""
from io import BytesIO, StringIO
import csv

from flask import send_file

from audit_log import log_admin_action
from competition_helpers import active_match_query
from extensions import db
from models import Match, Prediction, User


def _admin_export_tip_matrix(matchday):
    """CSV-Export der Tippmatrix fuer einen Spieltag."""
    from scoring import filter_active_users
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff, Match.id).all()
    users = filter_active_users(User.query.order_by(User.username.asc()).all())
    match_ids = [m.id for m in matches]
    preds = Prediction.query.filter(Prediction.match_id.in_(match_ids)).all() if match_ids else []
    pred_map = {(p.user_id, p.match_id): p for p in preds}
    text = StringIO()
    writer = csv.writer(text, delimiter=";")
    header = ["Spieler", "Gesamt ST-Punkte"] + [f"{m.home_team.short_name}-{m.away_team.short_name}" for m in matches]
    writer.writerow(header)
    for u in users:
        row = [u.username]
        total = sum((pred_map.get((u.id, m.id)).points or 0) for m in matches if pred_map.get((u.id, m.id)))
        row.append(total)
        for m in matches:
            p = pred_map.get((u.id, m.id))
            if p:
                val = f"{p.home_tip}:{p.away_tip}"
                if p.joker:
                    val += " ⚡"
                if m.status == "finished":
                    val += f" ({p.points or 0})"
                row.append(val)
            else:
                row.append("—")
        writer.writerow(row)
    output = BytesIO(text.getvalue().encode("utf-8-sig"))
    output.seek(0)
    log_admin_action("export_tip_matrix", "matchday", matchday, f"Tippmatrix ST {matchday} exportiert")
    return send_file(output, mimetype="text/csv; charset=utf-8", as_attachment=True, download_name=f"tippmatrix_st{matchday}.csv")
