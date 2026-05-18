"""PDF- und CSV-Export-Funktionen."""
from datetime import datetime, timezone
from io import BytesIO


def generate_season_pdf(user):
    """Erstellt einen schönen PDF-Saison-Report für den User."""
    from io import BytesIO
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor, white, black
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        return None

    from stats import get_user_insights
    from scoring import get_setting, get_leaderboard
    from models import MatchdayWinner, UserBadge

    insights = get_user_insights(user)
    stats_total_pts = sum(p.points or 0 for p in user.predictions)
    md_wins = MatchdayWinner.query.filter_by(user_id=user.id).all()
    badges = UserBadge.query.filter_by(user_id=user.id).all()
    total_tips = user.predictions.count()
    finished_preds = [p for p in user.predictions if p.match.status == "finished"]
    n_exact = sum(1 for p in finished_preds
                  if p.points and p.points >= get_setting("points_exact", 4))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=2*cm, rightMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm,
                             title=f"Saison-Report {user.username}")

    teal = HexColor("#14b8a6")
    text_color = HexColor("#0f172a")
    muted = HexColor("#64748b")
    bg_card = HexColor("#f1f5f9")

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                         fontSize=28, textColor=teal,
                         spaceAfter=4, fontName="Helvetica-Bold")
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                         fontSize=16, textColor=text_color,
                         spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold")
    sub = ParagraphStyle("sub", parent=styles["Normal"],
                          fontSize=11, textColor=muted, alignment=TA_LEFT,
                          spaceAfter=12)
    big_num = ParagraphStyle("big", parent=styles["Normal"],
                              fontSize=22, textColor=teal,
                              fontName="Helvetica-Bold", alignment=TA_CENTER)
    label = ParagraphStyle("lbl", parent=styles["Normal"],
                            fontSize=9, textColor=muted, alignment=TA_CENTER,
                            spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["Normal"],
                            fontSize=10, textColor=text_color, alignment=TA_LEFT,
                            spaceAfter=6)

    story = []
    story.append(Paragraph("⚽ Wulmstörper Tipprunde", h1))
    story.append(Paragraph(f"Saison-Report: <b>{user.username}</b>", sub))
    if user.full_name:
        story.append(Paragraph(f"<i>{user.full_name}</i>", sub))
    story.append(Spacer(1, 6))

    cell_style_num = TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg_card),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOX", (0,0), (-1,-1), 0.5, HexColor("#e2e8f0")),
        ("ROUNDEDCORNERS", [10,10,10,10]),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
    ])

    def stat_cell(num, lbl):
        return Table([
            [Paragraph(f"<b>{num}</b>", big_num)],
            [Paragraph(lbl, label)],
        ], style=cell_style_num)

    final_rank = "—"
    try:
        from stats import _compute_rank_through
        from extensions import db
        from models import Match
        finished_mds = sorted({m for (m,) in db.session.query(Match.matchday)
                                .filter_by(status="finished").distinct().all()})
        if finished_mds:
            r = _compute_rank_through(user.id, finished_mds[-1])
            if r:
                final_rank = f"#{r}"
    except Exception:
        pass

    stats_grid = Table([[
        stat_cell(stats_total_pts, "Punkte gesamt"),
        stat_cell(final_rank, "Tabellenplatz"),
        stat_cell(n_exact, "Exakte Tipps"),
        stat_cell(len(md_wins), "Spieltagsiege"),
    ]], colWidths=[4.1*cm]*4)
    story.append(stats_grid)

    if insights:
        story.append(Paragraph("🎲 Dein Tipp-Stil", h2))
        story.append(Paragraph(
            f"Dein häufigster Tipp war <b>{insights['most_common_tip']}</b> "
            f"({insights['most_common_count']}× = {insights['most_common_pct']}% deiner Tipps).",
            body))
        story.append(Paragraph(
            f"Tendenz-Verteilung: 🏠 {insights['tendency_pct']['home']}% Heim · "
            f"⚖ {insights['tendency_pct']['draw']}% Unentschieden · "
            f"✈ {insights['tendency_pct']['away']}% Auswärts",
            body))
        story.append(Paragraph(
            f"Im Schnitt erzielst du <b>{insights['avg_points_per_match']} Punkte pro Spiel</b>.",
            body))

        if insights.get("best"):
            b = insights["best"]
            story.append(Spacer(1, 4))
            story.append(Paragraph("🌟 <b>Glanz-Tipp der Saison</b>", body))
            story.append(Paragraph(
                f"{b.match.home_team.name} {b.match.home_score}:{b.match.away_score} "
                f"{b.match.away_team.name} — Tipp: {b.home_tip}:{b.away_tip} → "
                f"<b>+{b.points} Punkte</b>", body))

        if insights.get("worst"):
            w = insights["worst"]
            story.append(Spacer(1, 4))
            story.append(Paragraph("😅 <b>Daneben gegriffen</b>", body))
            story.append(Paragraph(
                f"{w.match.home_team.name} {w.match.home_score}:{w.match.away_score} "
                f"{w.match.away_team.name} — Tipp: {w.home_tip}:{w.away_tip}", body))

    if md_wins:
        story.append(Paragraph("🏆 Gewonnene Spieltage", h2))
        rows = [["Spieltag", "Punkte", "Exakte Tipps", "Status"]]
        for w in sorted(md_wins, key=lambda x: x.matchday):
            rows.append([
                f"ST {w.matchday}", str(w.points), str(w.exact_count),
                "Geteilt 🤝" if w.is_shared else "Solo 🏆",
            ])
        t = Table(rows, colWidths=[3*cm, 3*cm, 3.5*cm, 4*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), teal),
            ("TEXTCOLOR", (0,0), (-1,0), white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,0), 10),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, bg_card]),
            ("BOX", (0,0), (-1,-1), 0.5, HexColor("#cbd5e1")),
            ("INNERGRID", (0,0), (-1,-1), 0.3, HexColor("#cbd5e1")),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(t)

    if badges:
        story.append(Paragraph(f"🏅 Erspielte Auszeichnungen ({len(badges)})", h2))
        for ub in badges:
            b = ub.badge
            story.append(Paragraph(
                f"<b>{b.icon} {b.name}</b> — <font color='#64748b'>{b.description}</font>",
                body))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"<font color='#94a3b8' size='8'>Erstellt am {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} · "
        f"Wulmstörper Tipprunde · Saison " + get_setting("current_season", "2025/26") + "</font>", body))

    doc.build(story)
    buf.seek(0)
    return buf
