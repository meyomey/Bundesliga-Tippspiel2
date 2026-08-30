"""Ausgelagerte Main-Route-Logik: Tipps und Sondertipps."""
from datetime import datetime, timezone

import bleach
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db
from models import Comment, Match, Prediction, SpecialPrediction, SpecialQuestion, User
from forms import CommentForm, TipForm
from badges import check_and_award_badges
from scoring import filter_active_users, get_live_leaderboard
from stats import (
    evaluate_special_predictions,
    get_current_matchday,
    get_h2h,
    get_match_tip_distribution,
    get_match_weather,
    get_team_form,
    get_official_standings_positions,
    get_team_position,
)
from competition_helpers import (
    active_match_query,
    active_matchdays,
    filter_competition_scoped,
    get_active_competition,
)

def _my_open_tips(matchday=None):
    """Fokussierte User-Seite: nur Spiele, die mir noch fehlen."""
    if matchday is None:
        matchday = get_current_matchday()
    matchdays = active_matchdays()
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff.asc()).all()
    match_ids = [m.id for m in matches]
    pred_map = {}
    if match_ids:
        pred_map = {
            p.match_id: p for p in Prediction.query.filter(
                Prediction.user_id == current_user.id,
                Prediction.match_id.in_(match_ids),
            ).all()
        }
    open_missing = [m for m in matches if m.is_open() and m.id not in pred_map]
    already_tipped = [m for m in matches if m.id in pred_map]
    locked_or_done = [m for m in matches if not m.is_open() and m.id not in pred_map]
    return render_template(
        "my_open_tips.html",
        matchday=matchday, matchdays=matchdays, matches=matches,
        open_missing=open_missing, already_tipped=already_tipped,
        locked_or_done=locked_or_done, pred_map=pred_map,
    )

def _schedule(matchday=None):
    if matchday is None:
        matchday = get_current_matchday()

    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff).all()
    matchdays = active_matchdays()

    pred_map = {}
    for p in Prediction.query.filter_by(user_id=current_user.id).all():
        pred_map[p.match_id] = p

    comp = get_active_competition()
    joker_used = current_user.joker_used_for_matchday(matchday, comp.id if comp else None)
    joker_prediction = next((p for p in pred_map.values() if p.joker and p.match and p.match.matchday == matchday), None)
    joker_match = joker_prediction.match if joker_prediction else None

    pos_map = get_official_standings_positions()
    form_map = {}
    for m in matches:
        if m.home_team_id not in form_map:
            form_map[m.home_team_id] = get_team_form(m.home_team_id, 5)
        if m.away_team_id not in form_map:
            form_map[m.away_team_id] = get_team_form(m.away_team_id, 5)

    return render_template(
        "schedule.html",
        matches=matches,
        current_md=matchday,
        matchdays=matchdays,
        pred_map=pred_map,
        joker_used=joker_used,
        joker_match=joker_match,
        pos_map=pos_map,
        form_map=form_map,
    )

def _tip_overview(matchday=None):
    """Tippmatrix: alle Tipps pro Spieltag, aber erst ab Spielstart sichtbar."""
    if matchday is None:
        matchday = get_current_matchday()

    sort = request.args.get("sort", "total")
    if sort not in ("total", "matchday", "name"):
        sort = "total"

    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff, Match.id).all()
    matchdays = active_matchdays()
    users = filter_active_users(User.query.order_by(User.username.asc()).all())

    match_ids = [m.id for m in matches]
    user_ids = [u.id for u in users]
    pred_map = {}
    if match_ids and user_ids:
        preds = Prediction.query.filter(
            Prediction.match_id.in_(match_ids),
            Prediction.user_id.in_(user_ids),
        ).all()
        pred_map = {}
        for p in preds:
            pred_map.setdefault(p.user_id, {})[p.match_id] = p

    visible_map = {m.id: (not m.is_open()) for m in matches}
    started_count = sum(1 for v in visible_map.values() if v)

    # Live-Punkte: waehrend laufender Spiele dynamisch berechnen.
    total_live_rows = get_live_leaderboard()
    md_live_rows = get_live_leaderboard(matchday=matchday)
    total_points_map = {r["user"].id: r["points"] for r in total_live_rows}
    md_points_map = {r["user"].id: r["points"] for r in md_live_rows}
    total_rank_map = {r["user"].id: r["rank"] for r in total_live_rows}

    if sort == "matchday":
        users.sort(key=lambda u: (-md_points_map.get(u.id, 0), -total_points_map.get(u.id, 0), u.username.lower()))
    elif sort == "name":
        users.sort(key=lambda u: u.username.lower())
    else:
        users.sort(key=lambda u: (-total_points_map.get(u.id, 0), -md_points_map.get(u.id, 0), u.username.lower()))

    has_live = any(m.status == "live" or m.is_live for m in matches)

    return render_template(
        "tip_overview.html",
        matches=matches,
        matchdays=matchdays,
        current_md=matchday,
        users=users,
        pred_map=pred_map,
        visible_map=visible_map,
        started_count=started_count,
        total_points_map=total_points_map,
        md_points_map=md_points_map,
        total_rank_map=total_rank_map,
        has_live=has_live,
        sort=sort,
    )

def _match_detail(match_id):
    match = db.get_or_404(Match, match_id)
    pred = Prediction.query.filter_by(user_id=current_user.id, match_id=match_id).first()

    tip_form = TipForm(obj=pred)
    comment_form = CommentForm()

    siblings = Match.query.filter_by(
        competition_id=match.competition_id,
        matchday=match.matchday,
    ).order_by(Match.kickoff, Match.id).all()
    sibling_ids = [m.id for m in siblings]
    try:
        idx = sibling_ids.index(match_id)
    except ValueError:
        idx = 0
    prev_id = sibling_ids[idx - 1] if idx > 0 else None
    next_id = sibling_ids[idx + 1] if idx < len(sibling_ids) - 1 else None
    nav_position = idx + 1
    nav_total = len(siblings)

    if tip_form.validate_on_submit() and request.form.get("form") == "tip":
        if not match.is_open():
            flash("Tipps sind nicht mehr möglich – Anpfiff erfolgt.", "danger")
            return redirect(url_for("main.match_detail", match_id=match_id))

        if tip_form.joker.data and not (pred and pred.joker):
            from scoring import locked_joker_conflict, keep_single_joker
            conflict = locked_joker_conflict(current_user.id, match.matchday, match.competition_id, match_id)
            if conflict:
                flash("Joker kann nicht mehr verschoben werden – das bisherige Joker-Spiel hat bereits begonnen.", "danger")
                return redirect(url_for("main.match_detail", match_id=match_id))
            existing = Prediction.query.join(Match).filter(
                Prediction.user_id == current_user.id,
                Prediction.joker.is_(True),
                Match.matchday == match.matchday,
                Match.competition_id == match.competition_id,
                Prediction.match_id != match_id,
            ).all()
            for ep in existing:
                old_label = f"{ep.match.home_team.short_name}-{ep.match.away_team.short_name}"
                ep.joker = False
                flash(f"⚡ Joker von {old_label} hierher verschoben.", "info")

        if pred:
            pred.home_tip = tip_form.home_tip.data
            pred.away_tip = tip_form.away_tip.data
            pred.joker = tip_form.joker.data
        else:
            pred = Prediction(
                user_id=current_user.id, match_id=match_id,
                home_tip=tip_form.home_tip.data, away_tip=tip_form.away_tip.data,
                joker=tip_form.joker.data,
            )
            db.session.add(pred)
        if tip_form.joker.data:
            from scoring import keep_single_joker
            keep_single_joker(current_user.id, match.matchday, match.competition_id, match_id)
        db.session.commit()
        check_and_award_badges(users=[current_user])
        flash("Tipp gespeichert!", "success")
        return redirect(url_for("main.match_detail", match_id=match_id))

    if comment_form.validate_on_submit() and request.form.get("form") == "comment":
        c = Comment(match_id=match_id, user_id=current_user.id, text=bleach.clean(comment_form.text.data, tags=["b", "i", "em", "strong", "code", "span"], attributes={"span": ["class"]}, strip=True))
        db.session.add(c)
        db.session.commit()
        flash("Kommentar gepostet.", "success")
        return redirect(url_for("main.match_detail", match_id=match_id))

    # Kommentare mit Paginierung
    comments_page = request.args.get("comments_page", 1, type=int)
    comments_per_page = 10
    comments_pagination = Comment.query.filter_by(match_id=match_id).order_by(Comment.created_at.desc()).paginate(page=comments_page, per_page=comments_per_page, error_out=False)
    comments = comments_pagination.items
    all_preds = match.predictions.all() if match.status == "finished" else []

    home_form = get_team_form(match.home_team_id, limit=5)
    away_form = get_team_form(match.away_team_id, limit=5)
    h2h = get_h2h(match.home_team_id, match.away_team_id, limit=5)
    home_pos = get_team_position(match.home_team_id)
    away_pos = get_team_position(match.away_team_id)
    tip_dist = get_match_tip_distribution(match_id, exclude_user_id=current_user.id)
    weather = None
    if match.is_open() or match.status == "live":
        try:
            weather = get_match_weather(match)
        except Exception as e:
            current_app.logger.warning(f"Wetter-API Fehler: {e}")

    return render_template(
        "match_detail.html",
        match=match, pred=pred,
        tip_form=tip_form, comment_form=comment_form,
        comments=comments, comments_pagination=comments_pagination, all_preds=all_preds,
        home_form=home_form, away_form=away_form, h2h=h2h,
        home_pos=home_pos, away_pos=away_pos,
        sibling_ids=sibling_ids, prev_id=prev_id, next_id=next_id,
        nav_position=nav_position, nav_total=nav_total,
        siblings=siblings,
        tip_dist=tip_dist, weather=weather,
    )

def _quick_tip(matchday=None):
    if matchday is None:
        return redirect(url_for("main.quick_tip", matchday=get_current_matchday()))
    comp = get_active_competition()
    matchdays = active_matchdays()
    prev_matchday = next_matchday = None
    if matchday in matchdays:
        idx = matchdays.index(matchday)
        prev_matchday = matchdays[idx - 1] if idx > 0 else None
        next_matchday = matchdays[idx + 1] if idx < len(matchdays) - 1 else None
    matches = active_match_query().filter_by(matchday=matchday).order_by(Match.kickoff).all()

    if request.method == "POST":
        joker_match_id = request.form.get("joker_match", type=int)
        valid_joker_match = None
        if joker_match_id:
            valid_joker_match = next((m for m in matches if m.id == joker_match_id and m.is_open()), None)
            if not valid_joker_match:
                flash("Joker-Ziel ist nicht mehr tippbar oder gehört nicht zu diesem Spieltag.", "warning")
                joker_match_id = None
            else:
                from scoring import locked_joker_conflict
                conflict = locked_joker_conflict(current_user.id, matchday, valid_joker_match.competition_id, joker_match_id)
                if conflict:
                    flash("Joker kann nicht mehr verschoben werden – das bisherige Joker-Spiel hat bereits begonnen.", "danger")
                    joker_match_id = None

        # Alte Joker für diesen Spieltag entfernen (wenn neuer Joker gesetzt wurde)
        if joker_match_id:
            old_jokers_q = Prediction.query.join(Match).filter(
                Prediction.user_id == current_user.id,
                Prediction.joker.is_(True),
                Match.matchday == matchday,
            )
            if comp:
                old_jokers_q = old_jokers_q.filter(Match.competition_id == comp.id)
            old_jokers = old_jokers_q.all()
            for oj in old_jokers:
                oj.joker = False

        used_joker = False
        for m in matches:
            if not m.is_open():
                continue
            h = request.form.get(f"home_{m.id}", type=int)
            a = request.form.get(f"away_{m.id}", type=int)
            if h is None or a is None:
                continue
            if not (0 <= h <= 30 and 0 <= a <= 30):
                flash(f"Ungültiger Tipp bei {m.home_team.short_name} – {m.away_team.short_name}: erlaubt sind 0 bis 30 Tore.", "warning")
                continue

            is_joker = (m.id == joker_match_id and not used_joker)
            if is_joker:
                used_joker = True

            pred = Prediction.query.filter_by(user_id=current_user.id, match_id=m.id).first()
            if pred:
                pred.home_tip = h
                pred.away_tip = a
                pred.joker = is_joker
            else:
                db.session.add(Prediction(
                    user_id=current_user.id, match_id=m.id,
                    home_tip=h, away_tip=a, joker=is_joker,
                ))
        if joker_match_id and used_joker:
            from scoring import keep_single_joker
            keep_single_joker(current_user.id, matchday, comp.id if comp else None, joker_match_id)
        db.session.commit()
        check_and_award_badges(users=[current_user])

        try:
            from cache import invalidate_leaderboard
            invalidate_leaderboard()
        except Exception:
            pass

        flash(f"Schnelltipps für Spieltag {matchday} gespeichert.", "success")
        return redirect(url_for("main.schedule", matchday=matchday))

    pred_map = {p.match_id: p for p in Prediction.query.filter_by(user_id=current_user.id).all()}

    pos_map = get_official_standings_positions()
    form_map = {}
    for m in matches:
        if m.home_team_id not in form_map:
            form_map[m.home_team_id] = get_team_form(m.home_team_id, 5)
        if m.away_team_id not in form_map:
            form_map[m.away_team_id] = get_team_form(m.away_team_id, 5)

    return render_template(
        "quick_tip.html",
        matches=matches, matchday=matchday, matchdays=matchdays,
        prev_matchday=prev_matchday, next_matchday=next_matchday,
        pred_map=pred_map,
        pos_map=pos_map, form_map=form_map,
    )

def _special_tips():
    # JSON lokal importieren; Sondertipps speichern Listen als JSON-Text.
    import json

    questions_q = filter_competition_scoped(SpecialQuestion.query, SpecialQuestion)
    questions = questions_q.order_by(SpecialQuestion.deadline.asc()).all()

    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    if request.method == "POST":
        for q in questions:
            deadline = q.deadline.replace(tzinfo=None) if getattr(q.deadline, "tzinfo", None) else q.deadline
            if now_dt > deadline:
                continue
            allowed = []
            if q.options and q.answer_type in ("team", "multi_team"):
                try:
                    allowed = [str(v).strip() for v in json.loads(q.options) if str(v).strip()]
                except Exception:
                    allowed = []

            if q.answer_type == "multi_team":
                values = request.form.getlist(f"q_{q.id}")
                values = [v.strip() for v in values if v.strip()]
                if allowed:
                    values = [v for v in values if v in allowed]
                if not values:
                    continue
                if q.multi_count and len(values) > q.multi_count:
                    flash(f"Bei '{q.text[:40]}': max. {q.multi_count} Antworten erlaubt.", "warning")
                    values = values[:q.multi_count]
                answer = json.dumps(values)
            else:
                answer = request.form.get(f"q_{q.id}", "").strip()
                if allowed and answer and answer not in allowed:
                    continue
                if not answer:
                    continue

            sp = SpecialPrediction.query.filter_by(user_id=current_user.id, question_id=q.id).first()
            if sp:
                sp.answer = answer
                sp.competition_id = q.competition_id
            else:
                db.session.add(SpecialPrediction(
                    competition_id=q.competition_id,
                    user_id=current_user.id, question_id=q.id, answer=answer,
                ))
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Sonderfragen konnten nicht gespeichert werden")
            flash(f"Sonderfragen konnten nicht gespeichert werden: {e}", "danger")
            return redirect(url_for("main.special_tips"), code=303)

        try:
            evaluate_special_predictions()
            flash("Sonderfragen gespeichert.", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Sonderfragen-Auswertung fehlgeschlagen")
            flash(f"Sonderfragen gespeichert, aber Auswertung fehlgeschlagen: {e}", "warning")
        return redirect(url_for("main.special_tips"), code=303)

    sp_q = filter_competition_scoped(SpecialPrediction.query.filter_by(user_id=current_user.id), SpecialPrediction)
    user_answers = {sp.question_id: sp for sp in sp_q.all()}
    user_answer_lists = {}
    for qid, sp in user_answers.items():
        try:
            parsed = json.loads(sp.answer)
            if isinstance(parsed, list):
                user_answer_lists[qid] = parsed
        except (ValueError, TypeError):
            pass

    # Nach Ablauf der Deadline duerfen alle Spieler die Antworten der Runde sehen.
    closed_question_ids = [
        q.id for q in questions
        if (q.deadline.replace(tzinfo=None) if getattr(q.deadline, "tzinfo", None) else q.deadline) < datetime.now(timezone.utc).replace(tzinfo=None)
    ]
    answers_by_question = {}
    answer_lists_by_prediction = {}
    if closed_question_ids:
        from scoring import filter_active_users
        active_user_ids = {u.id for u in filter_active_users(User.query.all())}
        users_by_id = {u.id: u for u in User.query.filter(User.id.in_(active_user_ids)).all()} if active_user_ids else {}
        all_answers = SpecialPrediction.query.filter(SpecialPrediction.question_id.in_(closed_question_ids)).all()
        all_answers = [sp for sp in all_answers if sp.user_id in users_by_id]
        all_answers.sort(key=lambda sp: (users_by_id[sp.user_id].username.lower(), sp.user_id))
        for sp in all_answers:
            sp.display_user = users_by_id.get(sp.user_id)
            answers_by_question.setdefault(sp.question_id, []).append(sp)
            try:
                parsed = json.loads(sp.answer)
                if isinstance(parsed, list):
                    answer_lists_by_prediction[sp.id] = parsed
            except (ValueError, TypeError):
                pass

    parsed_options = {}
    for q in questions:
        if q.answer_type == "choice" and q.options:
            try:
                parsed_options[q.id] = json.loads(q.options)
            except (ValueError, TypeError):
                parsed_options[q.id] = [o.strip() for o in q.options.split("\n") if o.strip()]
        else:
            parsed_options[q.id] = None

    from competition_helpers import active_competition_teams
    all_teams = active_competition_teams()
    team_by_name = {t.name: t for t in all_teams}
    question_team_options = {}
    for q in questions:
        if q.answer_type in ("team", "multi_team") and q.options:
            try:
                names = [str(v).strip() for v in json.loads(q.options) if str(v).strip()]
            except Exception:
                names = []
            question_team_options[q.id] = [team_by_name[n] for n in names if n in team_by_name]

    return render_template(
        "special_tips.html",
        questions=questions, user_answers=user_answers,
        user_answer_lists=user_answer_lists,
        options=parsed_options, all_teams=all_teams,
        question_team_options=question_team_options,
        answers_by_question=answers_by_question,
        answer_lists_by_prediction=answer_lists_by_prediction,
        current_time=datetime.now(timezone.utc).replace(tzinfo=None),
    )


# ================================================ Ewige Tabelle -

