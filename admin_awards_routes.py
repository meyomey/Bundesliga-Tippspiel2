"""Admin: Saisonabschluss/Siegerehrung."""
from flask import flash, redirect, render_template, send_file, url_for

from audit_log import log_admin_action


def _admin_season_awards_view():
    from awards import compute_season_awards
    return render_template("admin/season_awards.html", data=compute_season_awards())


def _admin_season_awards_pdf():
    from awards import compute_season_awards, generate_awards_pdf
    data = compute_season_awards()
    pdf = generate_awards_pdf(data)
    if pdf is None:
        flash("PDF-Export benötigt reportlab.", "danger")
        return redirect(url_for("admin.season_awards"))
    season = (data.get("season") or "saison").replace("/", "-")
    log_admin_action("season_awards_pdf", "season", season, "Siegerehrungs-PDF exportiert")
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=f"siegerehrung_{season}.pdf")
