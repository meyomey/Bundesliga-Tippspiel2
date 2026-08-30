"""Punkteberechnung, Klassifikation, Ranglisten, Statistiken."""
from sqlalchemy import func

from extensions import db
from models import (
    User, Team, Match, Prediction, Setting, SpecialPrediction, MatchdayWinner,
    Competition,
)
from competition_helpers import get_active_competition


# ---------------------------------------------------------------- Settings -
def get_setting(key, default=None):
    s = db.session.get(Setting, key)
    if s and s.value is not None:
        import json
        try:
            return json.loads(s.value)
        except (json.JSONDecodeError, ValueError):
            return s.value
    return default


def set_setting(key, value):
    import json
    s = db.session.get(Setting, key)
    serialized = json.dumps(value)
    if s:
        s.value = serialized
    else:
        db.session.add(Setting(key=key, value=serialized))
    db.session.commit()




# ----------------------------------------------------------- Bot-Helper -
def is_bot_user(user):
    """True, wenn der User ein KI-Bot ist (per Email-Suffix erkannt).

    Robuster als ``username.endswith("Bot")``, weil echte User wie
    "RoboBot" sonst fälschlich gefiltert würden.
    """
    if user is None or not getattr(user, "email", None):
        return False
    return user.email.lower().endswith("@bot.local")


def _truthy_setting(value, default=True):
    """Wandelt einen Setting-Wert (kann String oder Bool sein) in einen Bool um.

    Akzeptiert ``"0"``, ``"false"``, ``"no"``, ``"off"``, ``""`` als ``False``.
    """
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    if s in ("0", "false", "no", "off", "nein", "aus", "n", ""):
        return False
    return True


def is_bot_active(bot_user):
    """True, wenn der Bot in den Einstellungen aktiviert ist.

    Default: inaktiv (False). Bots erscheinen/ tippen nur, wenn sie im Adminbereich
    explizit aktiviert wurden.
    """
    if not is_bot_user(bot_user):
        return True
    raw = get_setting(f"bot_active_{bot_user.username}", False)
    return _truthy_setting(raw, default=False)


def is_admin_only_user(user):
    """Admin-Konten ohne Spielaktivitaet aus Spielerlisten ausblenden.

    So bleibt ein technisches Admin-Konto fuer Verwaltung moeglich, erscheint
    aber nicht als Spieler. Admins, die selbst Tipps/Sonderfragen abgeben,
    bleiben normale Mitspieler.
    """
    if not getattr(user, "is_admin", False):
        return False
    if Prediction.query.filter_by(user_id=user.id).first():
        return False
    if SpecialPrediction.query.filter_by(user_id=user.id).first():
        return False
    return True


def filter_active_users(users):
    """Filtert deaktivierte Bots und reine Admin-Konten aus Spielerlisten.

    Echte User bleiben sichtbar. Admins bleiben sichtbar, sobald sie selbst
    Spielaktivitaet haben (Tipp oder Sonderfrage).
    """
    return [
        u for u in users
        if not is_admin_only_user(u) and ((not is_bot_user(u)) or is_bot_active(u))
    ]


# ----------------------------------------------------------- Punkte-Logik -
def calculate_points(prediction, match):
    """Berechnet die Punkte für einen Tipp basierend auf den Einstellungen."""
    if match.home_score is None or match.away_score is None:
        return 0
    if match.status != "finished":
        return 0

    from flask import current_app
    points_exact = get_setting("points_exact", current_app.config["POINTS_EXACT"])
    points_diff = get_setting("points_diff", current_app.config["POINTS_DIFF"])
    points_tendency = get_setting("points_tendency", current_app.config["POINTS_TENDENCY"])

    h, a = prediction.home_tip, prediction.away_tip
    rh, ra = match.home_score, match.away_score
    base = 0

    if h == rh and a == ra:
        base = points_exact
    elif (h - a) == (rh - ra) and (rh != ra or h != a):
        base = points_diff
    elif (h > a and rh > ra) or (h < a and rh < ra) or (h == a and rh == ra):
        base = points_tendency

    if prediction.joker:
        base *= 2
    return base


def calculate_points_for_score(prediction, home_score, away_score):
    """Berechnet Punkte fuer einen Tipp gegen ein beliebiges Ergebnis (ohne DB-Zugriff)."""
    if home_score is None or away_score is None:
        return 0

    from flask import current_app
    points_exact = get_setting("points_exact", current_app.config["POINTS_EXACT"])
    points_diff = get_setting("points_diff", current_app.config["POINTS_DIFF"])
    points_tendency = get_setting("points_tendency", current_app.config["POINTS_TENDENCY"])

    h, a = prediction.home_tip, prediction.away_tip
    rh, ra = home_score, away_score
    base = 0

    if h == rh and a == ra:
        base = points_exact
    elif (h - a) == (rh - ra) and (rh != ra or h != a):
        base = points_diff
    elif (h > a and rh > ra) or (h < a and rh < ra) or (h == a and rh == ra):
        base = points_tendency

    if prediction.joker:
        base *= 2
    return base


def classify_prediction(prediction, match):
    """Liefert ('exact'|'diff'|'tendency'|'wrong'|'pending') zurueck."""
    if match.status != "finished" or match.home_score is None or match.away_score is None:
        return "pending"
    h, a = prediction.home_tip, prediction.away_tip
    rh, ra = match.home_score, match.away_score
    if h == rh and a == ra:
        return "exact"
    if (h - a) == (rh - ra) and (rh != ra or h != a):
        return "diff"
    if (h > a and rh > ra) or (h < a and rh < ra) or (h == a and rh == ra):
        return "tendency"
    return "wrong"


def classify_prediction_live(prediction, match):
    """Klassifiziert einen Tipp fuer die Live-Anzeige."""
    if match.status == "scheduled" or match.home_score is None or match.away_score is None:
        return "pending"
    if match.status == "finished":
        return classify_prediction(prediction, match)
    h, a = prediction.home_tip, prediction.away_tip
    rh, ra = match.home_score, match.away_score
    if h == rh and a == ra:
        return "exact"
    if (h - a) == (rh - ra) and (rh != ra or h != a):
        return "diff"
    if (h > a and rh > ra) or (h < a and rh < ra) or (h == a and rh == ra):
        return "tendency"
    return "wrong"


def recalculate_all_points():
    """Geht alle finished Matches durch und schreibt die Punkte neu."""
    matches = Match.query.filter_by(status="finished").all()
    for m in matches:
        for p in m.predictions:
            p.points = calculate_points(p, m)
    db.session.commit()
    try:
        recompute_matchday_winners()
    except Exception as e:
        from flask import current_app
        current_app.logger.warning(f"recompute_matchday_winners failed: {e}")


def is_pot_participant(user):
    """True, wenn der User als zahlender Mitspieler im Pott zaehlt."""
    return (not is_bot_user(user)) and (not is_admin_only_user(user))


# ----------------------------------------------------------- Joker-Integritaet -
def locked_joker_conflict(user_id, matchday, competition_id, target_match_id=None):
    """Liefert einen bereits festgelegten Joker, der nicht mehr verschoben werden darf.

    Sobald das bisherige Joker-Spiel nicht mehr offen ist, darf der Joker nicht
    auf ein anderes Spiel verschoben werden.
    """
    q = Prediction.query.join(Match).filter(
        Prediction.user_id == user_id,
        Prediction.joker.is_(True),
        Match.matchday == matchday,
    )
    if competition_id is not None:
        q = q.filter(Match.competition_id == competition_id)
    if target_match_id is not None:
        q = q.filter(Prediction.match_id != target_match_id)
    for pred in q.all():
        if pred.match and not pred.match.is_open():
            return pred
    return None


def keep_single_joker(user_id, matchday, competition_id, keep_match_id):
    """Bereinigt Mehrfachjoker fuer User/Spieltag/Wettbewerb auf genau ein Zielspiel."""
    q = Prediction.query.join(Match).filter(
        Prediction.user_id == user_id,
        Prediction.joker.is_(True),
        Match.matchday == matchday,
    )
    if competition_id is not None:
        q = q.filter(Match.competition_id == competition_id)
    changed = 0
    for pred in q.all():
        if pred.match_id != keep_match_id:
            pred.joker = False
            changed += 1
    return changed


def recalculate_match_points(match_or_id, commit=True):
    """Berechnet Punkte nur fuer ein einzelnes Match neu.

    Deutlich schneller als `recalculate_all_points()` bei manueller Ergebnis-
    aenderung oder Sync-Updates eines einzelnen Spiels. Gibt die betroffenen
    User-IDs zurueck, damit Badges gezielt geprueft werden koennen.
    """
    match = match_or_id if hasattr(match_or_id, "predictions") else db.session.get(Match, match_or_id)
    if not match:
        return set()
    affected_users = set()
    for p in match.predictions:
        p.points = calculate_points(p, match)
        affected_users.add(p.user_id)
    if commit:
        db.session.commit()
        try:
            recompute_matchday_winners()
        except Exception as e:
            from flask import current_app
            current_app.logger.warning(f"recompute_matchday_winners failed: {e}")
    return affected_users


def recalculate_matches_points(match_ids, commit=True):
    """Berechnet Punkte fuer mehrere Matches neu und gibt betroffene User-IDs zurueck."""
    ids = [mid for mid in set(match_ids or []) if mid]
    if not ids:
        return set()
    affected_users = set()
    matches = Match.query.filter(Match.id.in_(ids)).all()
    for match in matches:
        affected_users.update(recalculate_match_points(match, commit=False))
    if commit:
        db.session.commit()
        try:
            recompute_matchday_winners()
        except Exception as e:
            from flask import current_app
            current_app.logger.warning(f"recompute_matchday_winners failed: {e}")
    return affected_users


# ----------------------------------------------------------- Pot & Winners -
def compute_pot_summary():
    """Berechnet die aktuelle Pott-Übersicht."""
    amount = int(get_setting("pot_amount", 5))
    currency = get_setting("pot_currency", "€")
    intro = get_setting("pot_intro", "")
    payment_title = get_setting("payment_info_title", "Zahlung an den Spielleiter")
    payment_text = get_setting("payment_info_text", "")
    prize_notes = get_setting("prize_notes", "")
    participants = [u for u in User.query.filter(~User.email.like("%@bot.local")).all() if is_pot_participant(u)]
    paid = sum(1 for u in participants if u.has_paid)
    total = len(participants)
    return {
        "amount_per": amount,
        "currency": currency,
        "intro": intro,
        "payment_title": payment_title,
        "payment_text": payment_text,
        "prize_notes": prize_notes,
        "paid_count": paid,
        "total_count": total,
        "pot_total": amount * paid,
        "pot_target": amount * total,
        "missing_count": total - paid,
    }


def recompute_matchday_winners():
    """Berechnet die Spieltagsieger neu."""
    season = get_setting("current_season", "2025/26")
    points_exact = get_setting("points_exact", 4)

    comp = get_active_competition()
    finished_q = db.session.query(Match.matchday).filter(Match.status == "finished")
    if comp:
        finished_q = finished_q.filter(Match.competition_id == comp.id)
    finished_mds = finished_q.distinct().all()
    finished_md_set = {md for (md,) in finished_mds}

    mdw_delete_q = MatchdayWinner.query.filter_by(season=season)
    if comp:
        mdw_delete_q = mdw_delete_q.filter(MatchdayWinner.competition_id == comp.id)
    mdw_delete_q.delete()

    for md in sorted(finished_md_set):
        results_q = db.session.query(
            Prediction.user_id,
            func.coalesce(func.sum(Prediction.points), 0).label("pts"),
        ).join(Match, Prediction.match_id == Match.id) \
         .filter(Match.matchday == md, Match.status == "finished")
        if comp:
            results_q = results_q.filter(Match.competition_id == comp.id)
        results = results_q.group_by(Prediction.user_id).all()

        if not results:
            continue
        max_pts = max(r.pts for r in results)
        if max_pts <= 0:
            continue

        top_user_ids = [r.user_id for r in results if r.pts == max_pts]

        if len(top_user_ids) > 1:
            exact_counts = {}
            for uid in top_user_ids:
                exact_q = db.session.query(func.count(Prediction.id)) \
                    .join(Match, Prediction.match_id == Match.id) \
                    .filter(
                        Prediction.user_id == uid,
                        Match.matchday == md, Match.status == "finished",
                        Prediction.points >= points_exact,
                    )
                if comp:
                    exact_q = exact_q.filter(Match.competition_id == comp.id)
                n_exact = exact_q.scalar() or 0
                exact_counts[uid] = n_exact
            max_exact = max(exact_counts.values())
            top_user_ids = [uid for uid, n in exact_counts.items() if n == max_exact]

        is_shared = len(top_user_ids) > 1

        for uid in top_user_ids:
            exact_q = db.session.query(func.count(Prediction.id)) \
                .join(Match, Prediction.match_id == Match.id) \
                .filter(
                    Prediction.user_id == uid,
                    Match.matchday == md, Match.status == "finished",
                    Prediction.points >= points_exact,
                )
            if comp:
                exact_q = exact_q.filter(Match.competition_id == comp.id)
            n_exact = exact_q.scalar() or 0
            db.session.add(MatchdayWinner(
                competition_id=comp.id if comp else None,
                matchday=md, user_id=uid, points=max_pts,
                exact_count=n_exact, is_shared=is_shared, season=season,
            ))
    db.session.commit()


# ----------------------------------------------------------- User-Stats (optimized) -
def get_user_stats(user, matchday=None):
    """Detaillierte Statistik mit exact/diff/tendency/wrong + Punkten."""
    comp = get_active_competition()

    q = Prediction.query.filter_by(user_id=user.id)
    if comp:
        q = q.join(Match).filter(Match.competition_id == comp.id)
        if matchday:
            q = q.filter(Match.matchday == matchday)
    else:
        if matchday:
            q = q.join(Match).filter(Match.matchday == matchday)

    # 🔥 PERFORMANCE: eager-load Match + Team-Beziehungen, um N+1 zu vermeiden
    q = q.options(
        db.joinedload(Prediction.match).joinedload(Match.home_team),
        db.joinedload(Prediction.match).joinedload(Match.away_team),
    )
    preds = q.all()

    counters = {"exact": 0, "diff": 0, "tendency": 0, "wrong": 0, "pending": 0}
    total_pts = 0
    joker_used = 0
    sp_pts = 0

    for p in preds:
        kind = classify_prediction(p, p.match)
        counters[kind] += 1
        total_pts += (p.points or 0)
        if p.joker:
            joker_used += 1

    if not matchday:
        sp_q = SpecialPrediction.query.filter_by(user_id=user.id)
        if comp:
            sp_q = sp_q.filter(SpecialPrediction.competition_id == comp.id)
        sp = sp_q.all()
        sp_pts = sum(s.points or 0 for s in sp)

    finished = counters["exact"] + counters["diff"] + counters["tendency"] + counters["wrong"]
    quote = round((counters["exact"] / finished) * 100) if finished else 0

    return {
        "user": user,
        "points": total_pts + sp_pts,
        "match_points": total_pts,
        "special_points": sp_pts,
        "tips": len(preds),
        "exact": counters["exact"],
        "diff": counters["diff"],
        "tendency": counters["tendency"],
        "wrong": counters["wrong"],
        "pending": counters["pending"],
        "joker_used": joker_used,
        "exact_quote": quote,
    }


def get_live_user_stats(user, matchday=None):
    """Wie get_user_stats, aber beruecksichtigt LIVE-Scores."""
    comp = get_active_competition()

    q = Prediction.query.filter_by(user_id=user.id)
    if comp:
        q = q.join(Match).filter(Match.competition_id == comp.id)
        if matchday:
            q = q.filter(Match.matchday == matchday)
    else:
        if matchday:
            q = q.join(Match).filter(Match.matchday == matchday)

    # 🔥 PERFORMANCE: eager-load
    q = q.options(
        db.joinedload(Prediction.match).joinedload(Match.home_team),
        db.joinedload(Prediction.match).joinedload(Match.away_team),
    )
    preds = q.all()

    counters = {"exact": 0, "diff": 0, "tendency": 0, "wrong": 0, "pending": 0}
    total_pts = 0
    joker_used = 0

    for p in preds:
        kind = classify_prediction_live(p, p.match)
        counters[kind] += 1
        if p.match.status == "finished":
            total_pts += (p.points or 0)
        elif p.match.status == "live":
            total_pts += calculate_points_for_score(p, p.match.home_score, p.match.away_score)
        if p.joker:
            joker_used += 1

    sp_pts = 0
    if not matchday:
        sp_q = SpecialPrediction.query.filter_by(user_id=user.id)
        if comp:
            sp_q = sp_q.filter(SpecialPrediction.competition_id == comp.id)
        sp = sp_q.all()
        sp_pts = sum(s.points or 0 for s in sp)

    finished = counters["exact"] + counters["diff"] + counters["tendency"] + counters["wrong"]
    quote = round((counters["exact"] / finished) * 100) if finished else 0

    return {
        "user": user,
        "points": total_pts + sp_pts,
        "match_points": total_pts,
        "special_points": sp_pts,
        "tips": len(preds),
        "exact": counters["exact"],
        "diff": counters["diff"],
        "tendency": counters["tendency"],
        "wrong": counters["wrong"],
        "pending": counters["pending"],
        "joker_used": joker_used,
        "exact_quote": quote,
    }


def get_leaderboard(matchday=None):
    """Erweiterte Tabelle mit allen Tipp-Kategorien (mit Cache!).
    
    🔥 PERFORMANCE-OPTIMIZED: 
    - Eager loading von Predictions + Matches + Teams
    - Bulk-Berechnung statt N+1 Queries pro User
    """
    from cache import cache, cache_key_leaderboard

    comp = get_active_competition()
    comp_key = comp.code if comp else "all"
    season_key = comp.season if comp else get_setting("current_season", "current")
    cache_key = cache_key_leaderboard(matchday=matchday, season=season_key, competition=comp_key)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # 🔥 PERFORMANCE: Bot-Filterung mit einer einzigen Query statt N Queries
    # Deaktivierte Bots werden komplett aus der Rangliste rausgenommen.
    all_users = User.query.all()
    active_users = filter_active_users(all_users)

    # 🔥 PERFORMANCE: Alle Predictions auf einmal laden mit eager loading
    user_ids = [u.id for u in active_users]
    user_map = {u.id: u for u in active_users}
    
    base_q = db.session.query(Prediction).filter(Prediction.user_id.in_(user_ids)).join(Match)
    if comp:
        base_q = base_q.filter(Match.competition_id == comp.id)
    if matchday:
        base_q = base_q.filter(Match.matchday == matchday)

    all_preds = base_q.options(
        db.joinedload(Prediction.match).joinedload(Match.home_team),
        db.joinedload(Prediction.match).joinedload(Match.away_team),
    ).all()

    # Predictions pro User gruppieren
    preds_by_user = {}
    for p in all_preds:
        preds_by_user.setdefault(p.user_id, []).append(p)

    # Sonderpunkte (nur bei Gesamttabelle)
    sp_points = {}
    if not matchday:
        sp_q = db.session.query(
            SpecialPrediction.user_id,
            func.coalesce(func.sum(SpecialPrediction.points), 0),
        ).filter(SpecialPrediction.user_id.in_(user_ids))
        if comp:
            sp_q = sp_q.filter(SpecialPrediction.competition_id == comp.id)
        sp_rows = sp_q.group_by(SpecialPrediction.user_id).all()
        sp_points = {uid: pts for uid, pts in sp_rows}

    rows = []
    for u in active_users:
        preds = preds_by_user.get(u.id, [])
        counters = {"exact": 0, "diff": 0, "tendency": 0, "wrong": 0, "pending": 0}
        total_pts = 0
        joker_used = 0

        for p in preds:
            kind = classify_prediction(p, p.match)
            counters[kind] += 1
            total_pts += (p.points or 0)
            if p.joker:
                joker_used += 1

        sp_pts = sp_points.get(u.id, 0)
        finished = counters["exact"] + counters["diff"] + counters["tendency"] + counters["wrong"]
        quote = round((counters["exact"] / finished) * 100) if finished else 0

        rows.append({
            "user": u,
            "points": total_pts + sp_pts,
            "match_points": total_pts,
            "special_points": sp_pts,
            "tips": len(preds),
            "exact": counters["exact"],
            "diff": counters["diff"],
            "tendency": counters["tendency"],
            "wrong": counters["wrong"],
            "pending": counters["pending"],
            "joker_used": joker_used,
            "exact_quote": quote,
        })

    rows.sort(key=lambda r: (
        -r["points"], -r["exact"], -r["diff"], -r["tendency"], -r["tips"], r["user"].username
    ))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    cache.set(cache_key, rows, ttl=120)
    return rows


def get_live_leaderboard(matchday=None):
    """Live-Rangliste: Punkte werden fuer laufende Spiele DYNAMISCH berechnet.

    PERFORMANCE-OPTIMIZED:
    - keine N+1-Queries pro User mehr
    - alle Predictions inkl. Match/Teams in einer Bulk-Query
    - Sonderpunkte in einer GROUP-BY-Query
    - deaktivierte Bots werden ausgeschlossen
    """
    comp = get_active_competition()

    all_users = User.query.all()
    active_users = filter_active_users(all_users)
    if not active_users:
        return []

    user_ids = [u.id for u in active_users]

    base_q = db.session.query(Prediction).filter(Prediction.user_id.in_(user_ids)).join(Match)
    if comp:
        base_q = base_q.filter(Match.competition_id == comp.id)
    if matchday:
        base_q = base_q.filter(Match.matchday == matchday)

    all_preds = base_q.options(
        db.joinedload(Prediction.match).joinedload(Match.home_team),
        db.joinedload(Prediction.match).joinedload(Match.away_team),
    ).all()

    preds_by_user = {}
    for p in all_preds:
        preds_by_user.setdefault(p.user_id, []).append(p)

    sp_points = {}
    if not matchday:
        sp_q = db.session.query(
            SpecialPrediction.user_id,
            func.coalesce(func.sum(SpecialPrediction.points), 0),
        ).filter(SpecialPrediction.user_id.in_(user_ids))
        if comp:
            sp_q = sp_q.filter(SpecialPrediction.competition_id == comp.id)
        sp_rows = sp_q.group_by(SpecialPrediction.user_id).all()
        sp_points = {uid: pts for uid, pts in sp_rows}

    rows = []
    for u in active_users:
        preds = preds_by_user.get(u.id, [])
        counters = {"exact": 0, "diff": 0, "tendency": 0, "wrong": 0, "pending": 0}
        total_pts = 0
        joker_used = 0

        for p in preds:
            m = p.match
            kind = classify_prediction_live(p, m)
            counters[kind] += 1
            if m.status == "finished":
                total_pts += (p.points or 0)
            elif m.status == "live":
                total_pts += calculate_points_for_score(p, m.home_score, m.away_score)
            if p.joker:
                joker_used += 1

        sp_pts = sp_points.get(u.id, 0)
        finished = counters["exact"] + counters["diff"] + counters["tendency"] + counters["wrong"]
        quote = round((counters["exact"] / finished) * 100) if finished else 0

        rows.append({
            "user": u,
            "points": total_pts + sp_pts,
            "match_points": total_pts,
            "special_points": sp_pts,
            "tips": len(preds),
            "exact": counters["exact"],
            "diff": counters["diff"],
            "tendency": counters["tendency"],
            "wrong": counters["wrong"],
            "pending": counters["pending"],
            "joker_used": joker_used,
            "exact_quote": quote,
        })

    rows.sort(key=lambda r: (
        -r["points"], -r["exact"], -r["diff"], -r["tendency"], -r["tips"], r["user"].username
    ))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
