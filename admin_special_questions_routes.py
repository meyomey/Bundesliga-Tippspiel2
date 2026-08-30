"""Admin: Sonderfragen."""
from datetime import datetime, timedelta, timezone
import json as _json

from flask import current_app, render_template, redirect, url_for, flash, request
from flask_login import current_user

from extensions import db
from models import (
    User, Team, Match, Prediction, Comment, Badge, UserBadge,
    SpecialQuestion, SpecialPrediction, Prize, MatchdayWinner,
)
from forms import AdminUserForm, PrizeForm, BadgeForm, SpecialQuestionForm
from scoring import compute_pot_summary
from stats import evaluate_special_predictions
from badges import check_and_award_badges, award_badge, revoke_badge
from competition_helpers import get_active_competition, filter_competition_scoped, active_competition_teams
from audit_log import log_admin_action


def _special_question_options_text(question):
    """JSON-Optionen einer Sonderfrage wieder als Zeilen-Text darstellen."""
    if not question.options:
        return ""
    try:
        values = _json.loads(question.options)
        if isinstance(values, list):
            return "\n".join(str(v) for v in values)
    except Exception:
        pass
    return question.options or ""


def _build_special_question_options(answer_type, options_text):
    """Antwortoptionen passend zum Antworttyp serialisieren."""
    opt_list = [o.strip() for o in (options_text or "").split("\n") if o.strip()]
    if answer_type in ("choice", "team", "multi_team"):
        return _json.dumps(opt_list) if opt_list else None
    if answer_type == "yes_no":
        return _json.dumps(["Ja", "Nein"])
    return None


def _parse_int_field(name, default=None, minimum=None, maximum=None):
    raw = request.form.get(name, "")
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Ungültiger Zahlenwert bei {name}.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} muss mindestens {minimum} sein.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} darf höchstens {maximum} sein.")
    return value


def _parse_deadline_field():
    raw = (request.form.get("deadline") or "").strip()
    if not raw:
        raise ValueError("Bitte Deadline auswählen.")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ValueError("Deadline bitte im Format Datum/Uhrzeit angeben.")

# ============================================================ Special Questions -
def _admin_special_questions():
    form = SpecialQuestionForm()
    if form.validate_on_submit():
        atype = form.answer_type.data or "text"
        opts_text = form.options.data or ""
        opt_list = [o.strip() for o in opts_text.split("\n") if o.strip()]

        options_json = _build_special_question_options(atype, opts_text)

        correct = (form.correct_answer.data or "").strip() or None

        comp = get_active_competition()
        q = SpecialQuestion(
            competition_id=comp.id if comp else None,
            text=form.text.data,
            description=form.description.data or None,
            answer_type=atype,
            options=options_json,
            multi_count=form.multi_count.data or 1,
            number_min=form.number_min.data,
            number_max=form.number_max.data,
            deadline=form.deadline.data,
            points_value=form.points_value.data,
            correct_answer=correct,
        )
        db.session.add(q)
        db.session.commit()
        evaluate_special_predictions()
        flash(f"Sonderfrage angelegt.", "success")
        return redirect(url_for("admin.special_questions"))

    questions_q = filter_competition_scoped(SpecialQuestion.query, SpecialQuestion)
    questions = questions_q.order_by(SpecialQuestion.deadline.desc()).all()
    min_dt = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    all_teams = active_competition_teams()
    team_by_name = {t.name: t for t in all_teams}
    question_team_options = {}
    for q in questions:
        if q.answer_type in ("team", "multi_team") and q.options:
            try:
                names = [str(v).strip() for v in _json.loads(q.options) if str(v).strip()]
            except Exception:
                names = []
            # Reihenfolge aus Optionen behalten. Falls Team nicht im aktuellen
            # Spielplan gefunden wurde, wird es bewusst nicht angezeigt.
            question_team_options[q.id] = [team_by_name[n] for n in names if n in team_by_name]

    qids = [q.id for q in questions]
    answer_counts = {}
    if qids:
        rows = db.session.query(SpecialPrediction.question_id, db.func.count(SpecialPrediction.id))             .filter(SpecialPrediction.question_id.in_(qids))             .group_by(SpecialPrediction.question_id).all()
        answer_counts = {qid: int(count or 0) for qid, count in rows}
    question_options_text = {q.id: _special_question_options_text(q) for q in questions}

    return render_template(
        "admin/special_questions.html",
        form=form, questions=questions, min_dt=min_dt,
        now_dt=now_dt, all_teams=all_teams,
        question_team_options=question_team_options,
        answer_counts=answer_counts,
        question_options_text=question_options_text,
    )


def _admin_edit_special_question(qid):
    """Bearbeitet bestehende Sonderfragen.

    Sobald Spieler Antworten abgegeben haben, duerfen nur Deadline und Punkte
    geaendert werden. Ohne Antworten darf der Admin die komplette Frage noch
    umbauen.
    """
    q = db.get_or_404(SpecialQuestion, qid)
    answer_count = SpecialPrediction.query.filter_by(question_id=qid).count()
    full_edit_allowed = answer_count == 0

    old_values = {
        "text": q.text,
        "description": q.description,
        "answer_type": q.answer_type,
        "options": q.options,
        "multi_count": q.multi_count,
        "number_min": q.number_min,
        "number_max": q.number_max,
        "deadline": q.deadline.isoformat() if q.deadline else None,
        "points_value": q.points_value,
        "correct_answer": q.correct_answer,
    }

    try:
        q.deadline = _parse_deadline_field()
        q.points_value = _parse_int_field("points_value", q.points_value, minimum=1, maximum=100)

        if full_edit_allowed:
            atype = request.form.get("answer_type", q.answer_type) or "text"
            valid_types = {"text", "choice", "team", "multi_team", "yes_no", "number"}
            if atype not in valid_types:
                raise ValueError("Unbekannter Antworttyp.")

            q.text = (request.form.get("text") or "").strip()
            if len(q.text) < 3:
                raise ValueError("Die Frage muss mindestens 3 Zeichen haben.")
            q.description = (request.form.get("description") or "").strip() or None
            q.answer_type = atype
            q.options = _build_special_question_options(atype, request.form.get("options", ""))
            q.multi_count = _parse_int_field("multi_count", q.multi_count or 1, minimum=1, maximum=18)
            q.number_min = _parse_int_field("number_min", None)
            q.number_max = _parse_int_field("number_max", None)
            if q.number_min is not None and q.number_max is not None and q.number_min > q.number_max:
                raise ValueError("Min. Zahl darf nicht größer als Max. Zahl sein.")
            if atype != "number":
                q.number_min = None
                q.number_max = None
            if atype != "multi_team":
                q.correct_answer = (request.form.get("correct_answer") or "").strip() or None
            else:
                # Mehrfach-Mannschaften werden weiterhin ueber die bestehende
                # Aufloesungs-Maske gepflegt.
                q.correct_answer = None

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Sonderfrage konnte nicht gespeichert werden: {e}", "danger")
        return redirect(url_for("admin.special_questions"), code=303)

    try:
        evaluate_special_predictions()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Sonderfragen-Auswertung nach Bearbeitung fehlgeschlagen")
        flash(f"Sonderfrage gespeichert, aber Auswertung fehlgeschlagen: {e}", "warning")
        return redirect(url_for("admin.special_questions"), code=303)

    changed = {
        "old": old_values,
        "new": {
            "text": q.text,
            "description": q.description,
            "answer_type": q.answer_type,
            "options": q.options,
            "multi_count": q.multi_count,
            "number_min": q.number_min,
            "number_max": q.number_max,
            "deadline": q.deadline.isoformat() if q.deadline else None,
            "points_value": q.points_value,
            "correct_answer": q.correct_answer,
        },
        "answer_count": answer_count,
        "full_edit_allowed": full_edit_allowed,
    }
    log_admin_action("special_question_edit", "special_question", qid, f"Sonderfrage '{q.text[:80]}' bearbeitet", changed)
    if full_edit_allowed:
        flash("Sonderfrage vollständig aktualisiert.", "success")
    else:
        flash(f"Deadline und Punkte aktualisiert. Frage/Antworttyp wurden nicht geändert, weil bereits {answer_count} Antwort(en) vorliegen.", "info")
    return redirect(url_for("admin.special_questions"), code=303)


def _admin_set_special_answer(qid):
    q = db.get_or_404(SpecialQuestion, qid)
    allowed = []
    if q.options and q.answer_type in ("team", "multi_team"):
        try:
            allowed = [str(v).strip() for v in _json.loads(q.options) if str(v).strip()]
        except Exception:
            allowed = []

    if q.answer_type == "multi_team":
        values = [v.strip() for v in request.form.getlist("correct_answer") if v.strip()]
        if allowed:
            values = [v for v in values if v in allowed]
        if q.multi_count and len(values) > q.multi_count:
            flash(f"Maximal {q.multi_count} Mannschaft(en) erlaubt. Es wurden nur die ersten {q.multi_count} gespeichert.", "warning")
            values = values[:q.multi_count]
        q.correct_answer = _json.dumps(values) if values else None
    else:
        ans = request.form.get("correct_answer", "").strip()
        if allowed and ans and ans not in allowed:
            flash("Diese Mannschaft ist für diese Frage nicht als Antwort zugelassen.", "warning")
            ans = ""
        q.correct_answer = ans or None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Sonderfrage-Antwort konnte nicht gespeichert werden")
        flash(f"Antwort konnte nicht gespeichert werden: {e}", "danger")
        return redirect(url_for("admin.special_questions"), code=303)

    try:
        evaluate_special_predictions()
        flash("Antwort gesetzt. Punkte wurden vergeben.", "success")
    except Exception as e:
        # Antwort bleibt gespeichert; nur die Auswertung kann spaeter erneut
        # angestossen werden. So endet der Admin nicht in einem 500er.
        db.session.rollback()
        current_app.logger.exception("Sonderfrage-Auswertung fehlgeschlagen")
        flash(f"Antwort gespeichert, aber Auswertung fehlgeschlagen: {e}", "warning")
    return redirect(url_for("admin.special_questions"), code=303)


def _admin_delete_special_question(qid):
    q = db.get_or_404(SpecialQuestion, qid)
    SpecialPrediction.query.filter_by(question_id=qid).delete()
    db.session.delete(q)
    db.session.commit()
    flash("Sonderfrage gelöscht.", "info")
    return redirect(url_for("admin.special_questions"))
