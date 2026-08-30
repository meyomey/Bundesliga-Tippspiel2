"""Saisonabschluss / Siegerehrung fuer Admin."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import BytesIO

from extensions import db
from models import User, Prediction, Match, MatchdayWinner, Prize
from scoring import get_leaderboard, filter_active_users, get_setting
from competition_helpers import get_active_competition, filter_competition_scoped


def _human_users():
    return filter_active_users(User.query.filter(~User.email.like("%@bot.local")).all())


def compute_season_awards():
    """Berechnet Podium, Preise und Sonderauszeichnungen fuer die Saison."""
    comp = get_active_competition()
    season = comp.season if comp else get_setting("current_season", "")
    leaderboard = [r for r in get_leaderboard() if not r["user"].email.endswith("@bot.local")]
    users = _human_users()
    user_ids = [u.id for u in users]

    q = Prediction.query.filter(Prediction.user_id.in_(user_ids)).join(Match)
    if comp:
        q = q.filter(Match.competition_id == comp.id)
    preds = q.all()
    finished_preds = [p for p in preds if p.match and p.match.status == "finished"]

    by_user = defaultdict(list)
    for p in finished_preds:
        by_user[p.user_id].append(p)

    def row_user(uid):
        return next((r for r in leaderboard if r["user"].id == uid), None)

    awards = []
    if leaderboard:
        awards.append({"code": "champion", "icon": "👑", "title": "Saison-Champion", "user": leaderboard[0]["user"], "value": f"{leaderboard[0]['points']} Punkte"})
        awards.append({"code": "rote_laterne", "icon": "🦆", "title": "Rote Laterne", "user": leaderboard[-1]["user"], "value": f"{leaderboard[-1]['points']} Punkte"})

    # Exakt-Koenig
    if leaderboard:
        exact = max(leaderboard, key=lambda r: (r.get("exact", 0), r.get("points", 0)))
        awards.append({"code": "exact_king", "icon": "🎯", "title": "Exakt-König", "user": exact["user"], "value": f"{exact['exact']} exakte Tipps"})

    # Joker-Koenig, Remis-Koenig, Heim-/Auswaerts-Fan, Pechvogel
    stats = {}
    for u in users:
        ups = by_user.get(u.id, [])
        joker_pts = sum((p.points or 0) for p in ups if p.joker)
        zero_count = sum(1 for p in ups if (p.points or 0) == 0)
        draw_tips = sum(1 for p in ups if p.home_tip == p.away_tip)
        home_tips = sum(1 for p in ups if p.home_tip > p.away_tip)
        away_tips = sum(1 for p in ups if p.home_tip < p.away_tip)
        stats[u.id] = {
            "user": u, "joker_pts": joker_pts, "zero_count": zero_count,
            "draw_tips": draw_tips, "home_tips": home_tips, "away_tips": away_tips,
            "tips": len(ups),
        }
    if stats:
        joker = max(stats.values(), key=lambda x: x["joker_pts"])
        awards.append({"code": "joker_king", "icon": "⚡", "title": "Joker-König", "user": joker["user"], "value": f"{joker['joker_pts']} Joker-Punkte"})
        remis = max(stats.values(), key=lambda x: x["draw_tips"])
        awards.append({"code": "draw_king", "icon": "⚖", "title": "Remis-König", "user": remis["user"], "value": f"{remis['draw_tips']} Remis-Tipps"})
        home = max(stats.values(), key=lambda x: x["home_tips"])
        awards.append({"code": "home_fan", "icon": "🏠", "title": "Heimsieg-Fan", "user": home["user"], "value": f"{home['home_tips']} Heimsieg-Tipps"})
        away = max(stats.values(), key=lambda x: x["away_tips"])
        awards.append({"code": "away_brave", "icon": "✈", "title": "Auswärts-Mutiger", "user": away["user"], "value": f"{away['away_tips']} Auswärtssieg-Tipps"})
        unlucky = max(stats.values(), key=lambda x: x["zero_count"])
        awards.append({"code": "unlucky", "icon": "😅", "title": "Pechvogel", "user": unlucky["user"], "value": f"{unlucky['zero_count']} Nuller"})

    # Spieltagsjaeger
    mdw_q = filter_competition_scoped(MatchdayWinner.query, MatchdayWinner)
    mdw = mdw_q.all()
    win_counts = Counter(w.user_id for w in mdw)
    if win_counts:
        uid, cnt = win_counts.most_common(1)[0]
        u = db.session.get(User, uid)
        if u:
            awards.append({"code": "matchday_hunter", "icon": "🏆", "title": "Spieltagsjäger", "user": u, "value": f"{cnt} Spieltagsieg(e)"})

    prize_q = filter_competition_scoped(Prize.query.filter_by(active=True), Prize)
    prizes = prize_q.order_by(Prize.sort_order.asc(), Prize.rank.asc()).all()
    prize_rows = []
    for prize in prizes:
        assigned = None
        if prize.rank and prize.rank > 0:
            assigned = next((r["user"] for r in leaderboard if r["rank"] == prize.rank), None)
        elif prize.rank == 0 and leaderboard:
            # Sonderpreis ohne Logik: default auf letzten Platz als Trost/Rote Laterne
            assigned = leaderboard[-1]["user"]
        prize_rows.append({"prize": prize, "user": assigned})

    return {
        "competition": comp,
        "season": season,
        "generated_at": datetime.now(timezone.utc),
        "leaderboard": leaderboard,
        "podium": leaderboard[:3],
        "awards": awards,
        "prizes": prize_rows,
        "matchday_winners": mdw,
        "users_count": len(users),
    }


def generate_awards_pdf(data=None):
    """Erstellt ein PDF fuer die Siegerehrung."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor, white
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        return None

    data = data or compute_season_awards()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm, topMargin=1.6*cm, bottomMargin=1.6*cm)
    styles = getSampleStyleSheet()
    teal = HexColor("#14b8a6")
    dark = HexColor("#0f172a")
    muted = HexColor("#64748b")
    bg = HexColor("#f1f5f9")
    h1 = ParagraphStyle("h1x", parent=styles["Heading1"], fontSize=24, textColor=teal, fontName="Helvetica-Bold")
    h2 = ParagraphStyle("h2x", parent=styles["Heading2"], fontSize=15, textColor=dark, fontName="Helvetica-Bold", spaceBefore=12)
    body = ParagraphStyle("bodyx", parent=styles["Normal"], fontSize=10, textColor=dark, spaceAfter=5)

    story = [Paragraph("🏆 Wulmstörper Tipprunde – Saisonabschluss", h1), Paragraph(f"Saison {data.get('season') or ''}", body), Spacer(1, 8)]
    if data["podium"]:
        story.append(Paragraph("Podium", h2))
        rows = [["Rang", "Spieler", "Punkte", "Exakt"]]
        for r in data["podium"]:
            rows.append([str(r["rank"]), r["user"].username, str(r["points"]), str(r["exact"])])
        story.append(_pdf_table(rows, teal, bg, white))

    if data["prizes"]:
        story.append(Paragraph("Preise", h2))
        rows = [["Preis", "Gewinner", "Wert"]]
        for pr in data["prizes"]:
            rows.append([pr["prize"].title, pr["user"].username if pr["user"] else "—", pr["prize"].amount or "—"])
        story.append(_pdf_table(rows, teal, bg, white))

    if data["awards"]:
        story.append(Paragraph("Sonderauszeichnungen", h2))
        rows = [["Award", "Gewinner", "Wert"]]
        for a in data["awards"]:
            rows.append([f"{a['icon']} {a['title']}", a["user"].username if a.get("user") else "—", a.get("value", "")])
        story.append(_pdf_table(rows, teal, bg, white))

    if data["leaderboard"]:
        story.append(Paragraph("Abschlusstabelle", h2))
        rows = [["Rang", "Spieler", "Punkte", "Exakt", "Diff", "Tendenz"]]
        for r in data["leaderboard"]:
            rows.append([str(r["rank"]), r["user"].username, str(r["points"]), str(r["exact"]), str(r["diff"]), str(r["tendency"])])
        story.append(_pdf_table(rows, teal, bg, white, font_size=8))

    doc.build(story)
    buf.seek(0)
    return buf


def _pdf_table(rows, teal, bg, white, font_size=9):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.colors import HexColor
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), teal),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), font_size),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, bg]),
        ("BOX", (0,0), (-1,-1), 0.5, HexColor("#cbd5e1")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, HexColor("#cbd5e1")),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return t
