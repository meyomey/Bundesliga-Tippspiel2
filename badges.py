"""Badge-System: Vergabe, Prüfung, Seeding."""
from extensions import db
from models import User, Badge, UserBadge, Prediction, MatchdayWinner, Setting, Team, Match


def seed_badges():
    if Badge.query.count() == 0:
        for code, name, desc, icon, color, ttype, thresh in DEFAULT_BADGES:
            db.session.add(Badge(
                code=code, name=name, description=desc, icon=icon,
                color=color, trigger_type=ttype, threshold=thresh,
            ))
        db.session.commit()


DEFAULT_BADGES = [
    ("first_tip",    "Tipp-Premiere",  "Ersten Tipp abgegeben",                  "🎯", "#10b981", "first_tip",    1),
    ("loyal",        "Treuer Tipper",  "30 Tipps abgegeben",                     "🏆", "#f59e0b", "tips_count",   30),
    ("veteran",      "Veteran",        "100 Tipps abgegeben",                    "🎖", "#8b5cf6", "tips_count",  100),
    ("100_points",   "Hundertschaft",  "100 Punkte erreicht",                    "💯", "#ef4444", "total_points",100),
    ("500_points",   "Halbtausend",    "500 Punkte erreicht",                    "🚀", "#3b82f6", "total_points",500),
    ("sharp_shooter","Scharfschütze",  "10 exakte Tipps",                        "🎯", "#ec4899", "exact_count",  10),
    ("joker_master", "Joker-Meister",  "Joker mit exaktem Tipp eingelöst",       "⚡", "#fbbf24", "joker_exact",   0),
    ("perfect_day",  "Perfekter Tag",  "Alle Spiele eines Spieltags exakt",      "👑", "#fbbf24", "perfect_day",   0),
    ("md_winner_1",  "Spieltagsieger", "Erster Spieltagsieg",                    "🏆", "#14b8a6", "matchday_winner", 1),
    ("md_winner_3",  "Triple-Sieger",  "3 Spieltage gewonnen",                   "🥇", "#f59e0b", "matchday_winner", 3),
    ("md_winner_5",  "Serien-Sieger",  "5 Spieltage gewonnen",                   "🔥", "#ef4444", "matchday_winner", 5),
    ("champion",     "Saisonchampion", "Sondertrophäe vom Admin",                "🏅", "#fbbf24", "manual",        0),
    ("season_mvp",   "MVP der Saison", "Vom Admin handverlesen",                 "⭐", "#fde047", "manual",        0),
]


# Default-Preise für die Gewinner-Seite
DEFAULT_PRIZES = [
    (1, "1. Platz", "Saisonsieger des Tippspiels", "🥇", "#fbbf24",
     "50% des Potts", "Der Hauptgewinn geht an den besten Tipper der Saison.", 1),
    (2, "2. Platz", "Vize-Champion", "🥈", "#9ca3af",
     "30% des Potts", "Auch der zweite Platz wird belohnt.", 2),
    (3, "3. Platz", "Bronze-Rang", "🥉", "#b45309",
     "20% des Potts", "Top 3 ist nicht ohne!", 3),
    (0, "Trostpreis", "Letzter Platz / Schlechtester Tipper", "🍺", "#3b82f6",
     "Eine Runde Bier", "Damit auch der Letzte was vom Tippspiel hat.", 99),
]


def seed_prizes():
    from models import Prize
    from competition_helpers import get_active_competition
    comp = get_active_competition()
    if Prize.query.count() == 0:
        for rank, title, desc, icon, color, amount, detail, order in DEFAULT_PRIZES:
            db.session.add(Prize(
                competition_id=comp.id if comp else None,
                rank=rank, title=title, description=desc,
                icon=icon, color=color, amount=amount, detail=detail,
                sort_order=order,
            ))
        db.session.commit()


def award_badge(user, code_or_badge):
    """Vergibt Badge an User. Akzeptiert Code-String oder Badge-Objekt."""
    badge = (
        code_or_badge if isinstance(code_or_badge, Badge)
        else Badge.query.filter_by(code=code_or_badge).first()
    )
    if not badge:
        return False
    existing = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
    if existing:
        return False
    db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
    db.session.commit()
    return True


def revoke_badge(user, badge):
    """Entzieht ein Badge wieder."""
    ub = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
    if ub:
        db.session.delete(ub)
        db.session.commit()
        return True
    return False


def _user_qualifies(user, badge):
    """Prüft, ob ein User die Bedingungen eines Badges erfüllt."""
    from scoring import get_setting
    t = badge.trigger_type
    threshold = badge.threshold or 0

    if t == "manual":
        return False

    if t == "first_tip":
        return user.predictions.count() >= 1

    if t == "tips_count":
        return user.predictions.count() >= threshold

    if t == "total_points":
        return sum(p.points or 0 for p in user.predictions) >= threshold

    if t in ("exact_count", "joker_exact"):
        # "Exakt" = Endstand exakt (Klassifikation), nicht per Punkte:
        # ein Joker-Tipp mit 2+2=4 Punkten ist kein exakter Treffer
        # (und ein Joker-Diff mit 3+3=6 waere sonst einer, (73)).
        from scoring import classify_prediction
        finished_preds = [p for p in user.predictions if p.match.status == "finished"]
        n_exact = sum(1 for p in finished_preds
                      if classify_prediction(p, p.match) == "exact")
        if t == "exact_count":
            return n_exact >= threshold
        return any(
            p.joker and classify_prediction(p, p.match) == "exact"
            for p in finished_preds
        )

    if t == "perfect_day":
        from sqlalchemy import func
        from competition_helpers import get_active_competition
        comp = get_active_competition()
        finished_preds = [p for p in user.predictions if p.match.status == "finished" and (not comp or p.match.competition_id == comp.id)]
        # Gruppiere nach Spieltag
        md_groups = {}
        for p in finished_preds:
            md_groups.setdefault(p.match.matchday, []).append(p)
        # "Perfekt" = jeder Tipp Endstand exakt (nicht per Punkte, (73)) —
        # und nur auf VOLLSTAENDIG abgelaufenen Spieltagen: ein partieller
        # Spieltag (nur 2 von 9 Spielen fertig) wuerde "alle exakt"
        # trivial erfuellen ((74), in Produktion gefundene Fehlzuteilung).
        from scoring import classify_prediction
        for md, preds in md_groups.items():
            total_q = Match.query.filter_by(matchday=md, status="finished")
            all_q = Match.query.filter_by(matchday=md)
            if comp:
                total_q = total_q.filter(Match.competition_id == comp.id)
                all_q = all_q.filter(Match.competition_id == comp.id)
            total_md = total_q.count()
            total_all = all_q.count()
            if total_all > 0 and total_md == total_all and len(preds) >= total_all:
                if all(classify_prediction(p, p.match) == "exact" for p in preds):
                    return True
        return False

    if t == "matchday_winner":
        # Wie das Profil: aktiver Wettbewerb + aktuelle Saison. Die alte
        # Logikaenzählte ALLE Wettbewerbe/Saisons — dadurch konnte das
        # Badge erscheinen, obwohl das Profil 0 Spieltagssiege zeigte ((74)).
        from competition_helpers import get_active_competition
        comp = get_active_competition()
        season = get_setting("current_season", "2025/26")
        q = MatchdayWinner.query.filter_by(user_id=user.id, season=season)
        if comp:
            q = q.filter(MatchdayWinner.competition_id == comp.id)
        wins = q.count()
        return wins >= threshold

    return False


def revalidate_badges():
    """Vollrevalidierung aller Auto-Badges: verleiht fehlende UND widerruft
    nicht mehr verdiente (alle Trigger ausser 'manual'). Zur Korrektur
    alter/falscher Vergaben — manuell via Admin → Wartung → 'badges'
    ausloesen. Der normale Save-Pfad (check_and_award_badges) widerruft
    bewusst nichts, um kein Hin-und-her-Verliehen zu erzeugen."""
    badges = Badge.query.filter_by(active=True).all()
    for badge in badges:
        if badge.trigger_type == "manual":
            continue
        for user in User.query.all():
            qualifies = _user_qualifies(user, badge)
            has = UserBadge.query.filter_by(
                user_id=user.id, badge_id=badge.id).first() is not None
            if qualifies and not has:
                award_badge(user, badge)
            elif not qualifies and has:
                revoke_badge(user, badge)
    db.session.commit()


def check_and_award_badges(users=None):
    """Geht aktive Badges durch und vergibt sie automatisch.

    `users` kann eine Liste/Query/User-Objekt sein, um nach Tipp- oder
    Ergebnisupdates nur betroffene User zu pruefen. Ohne Parameter bleibt das
    bisherige Vollverhalten erhalten.
    """
    badges = Badge.query.filter_by(active=True).all()
    if users is None:
        users = User.query.all()
    elif isinstance(users, User):
        users = [users]
    else:
        users = list(users)
    for badge in badges:
        if badge.trigger_type == "manual":
            continue
        for user in users:
            if _user_qualifies(user, badge):
                award_badge(user, badge)
