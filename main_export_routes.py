"""Ausgelagerte Main-Route-Logik: Exporte."""
import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO

from flask import flash, redirect, send_file, url_for
from flask_login import current_user, login_required
from routes_main import main_bp  # Blueprint-Registrierung statt Lazy-Wrapper in routes_main.py

from models import Match, Prediction
from export import generate_season_pdf
from competition_helpers import get_active_competition

@main_bp.route("/export/pdf", endpoint="export_pdf")
@login_required
def _export_pdf():
    pdf_buf = generate_season_pdf(current_user)
    if pdf_buf is None:
        flash("PDF-Export benötigt das Paket 'reportlab' (pip install reportlab).", "danger")
        return redirect(url_for("main.season_recap"))
    filename = f"Saison-Report_{current_user.username}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return send_file(pdf_buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)

@main_bp.route("/export/csv", endpoint="export_csv")
@login_required
def _export_csv():
    text = StringIO()
    writer = csv.writer(text, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Spieltag", "Datum", "Heim", "Auswärts", "Tipp", "Ergebnis", "Punkte", "Joker"])
    comp = get_active_competition()
    q = Prediction.query.filter_by(user_id=current_user.id).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    for p in q.order_by(Match.matchday.asc(), Match.kickoff.asc()).all():
        m = p.match
        writer.writerow([
            m.matchday, m.kickoff.strftime("%d.%m.%Y %H:%M"),
            m.home_team.name, m.away_team.name,
            f"{p.home_tip}:{p.away_tip}",
            f"{m.home_score}:{m.away_score}" if m.home_score is not None else "—",
            p.points or 0, "Ja" if p.joker else "Nein",
        ])
    output = BytesIO(text.getvalue().encode("utf-8-sig"))
    output.seek(0)
    return send_file(
        output, mimetype="text/csv; charset=utf-8",
        as_attachment=True, download_name=f"tipps_{current_user.username}.csv"
    )


# ------------------------------------------------------------------
# Telegram Bot Webhook
# ------------------------------------------------------------------

