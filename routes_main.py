"""Haupt-Routes: Dashboard, Index, Einladen, Mehr, Hilfe und Tipp-Einstieg.

Seiten-Modul-Logik liegt in den Partner-Modulen (main_tips/stats/pwa/profile/export/telegram_routes),
die ihre Routen direkt auf ``main_bp`` registrieren; dieses Modul haelt nur noch
die hier verbliebenen echten Route-Funktionen."""
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from mail_helpers import send_email
from models import InvitationCode, Match, Prediction, User, UserBadge
from notification_center import send_test_missing_tip_notification
from scoring import compute_pot_summary, get_leaderboard, get_setting
from stats import get_current_matchday
from competition_helpers import (
    active_match_query, filter_matches_for_active_competition,
)


main_bp = Blueprint("main", __name__)


# ============================================================ PWA Routes -
@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    top3 = get_leaderboard()[:3]
    return render_template(
        "landing.html",
        top3=top3,
        current_md=get_current_matchday(),
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    upcoming_q = Match.query.filter(
        Match.kickoff > datetime.now(timezone.utc),
        Match.status == "scheduled"
    )
    upcoming_q = filter_matches_for_active_competition(upcoming_q)
    upcoming = upcoming_q.order_by(Match.kickoff.asc()).all()

    user_points = current_user.total_points()
    leaderboard = get_leaderboard()[:10]
    user_rank = next((r["rank"] for r in get_leaderboard() if r["user"].id == current_user.id), None)
    current_matchday = get_current_matchday()
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()

    live_count = filter_matches_for_active_competition(Match.query.filter_by(status="live")).count()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = Match.query.filter(
        Match.kickoff >= today,
        Match.kickoff < today + timedelta(days=1),
    )
    today_matches_count = filter_matches_for_active_competition(today_q).count()

    md_matches = active_match_query().filter_by(matchday=current_matchday).order_by(Match.kickoff.asc()).all()
    md_match_ids = [m.id for m in md_matches]
    tipped_ids = set()
    if md_match_ids:
        tipped_ids = {
            p.match_id for p in Prediction.query.filter(
                Prediction.user_id == current_user.id,
                Prediction.match_id.in_(md_match_ids),
            ).all()
        }
    open_md_matches = [m for m in md_matches if m.is_open() and m.id not in tipped_ids]
    tipped_count = len([m for m in md_matches if m.id in tipped_ids])
    total_count = len(md_matches)
    finished_count = len([m for m in md_matches if m.status == "finished"])

    if live_count > 0:
        next_action = {
            "kind": "live", "icon": "🔴", "title": f"{live_count} Spiel(e) laufen gerade",
            "text": "Verfolge Live-Punkte und Tabellenbewegungen.",
            "url": url_for("main.live_center"), "button": "Live verfolgen",
        }
    elif open_md_matches:
        next_action = {
            "kind": "tips", "icon": "🎯", "title": f"{len(open_md_matches)} offene Tipp(s) für Spieltag {current_matchday}",
            "text": f"{tipped_count}/{total_count} Spielen getippt. Nächster Anpfiff: " + open_md_matches[0].kickoff.strftime("%d.%m. %H:%M"),
            "url": url_for("main.tip_entry", matchday=current_matchday), "button": "Jetzt tippen",
        }
    elif total_count and finished_count == total_count:
        next_action = {
            "kind": "recap", "icon": "📊", "title": f"Spieltag {current_matchday} ist abgeschlossen",
            "text": "Schau dir den Rückblick und die Spieltagswertung an.",
            "url": url_for("main.matchday_recap", matchday=current_matchday), "button": "Recap ansehen",
        }
    else:
        next_action = {
            "kind": "done", "icon": "✅", "title": f"Alles erledigt für Spieltag {current_matchday}",
            "text": "Du hast aktuell keine offenen Tipps für diesen Spieltag.",
            "url": url_for("main.tip_overview", matchday=current_matchday), "button": "Tippübersicht",
        }

    tip_status = {"tipped": tipped_count, "total": total_count, "open": len(open_md_matches)}
    pot = compute_pot_summary()

    return render_template(
        "dashboard.html",
        upcoming=upcoming,
        user_points=user_points,
        leaderboard=leaderboard,
        user_rank=user_rank,
        current_matchday=current_matchday,
        badges=user_badges,
        live_count=live_count,
        today_matches_count=today_matches_count,
        next_action=next_action,
        tip_status=tip_status,
        pot=pot,
        get_user_prediction=lambda mid: Prediction.query.filter_by(user_id=current_user.id, match_id=mid).first(),
    )

@main_bp.route("/einladen", methods=["GET", "POST"])
@login_required
def invite_users():
    import re
    from mail_helpers import send_email

    base_url = (get_setting("public_base_url", current_app.config.get("PUBLIC_BASE_URL", "")) or "").strip().rstrip("/")
    if not base_url:
        base_url = request.url_root.rstrip("/")
    import secrets
    from datetime import timedelta

    share_invite = InvitationCode.query.filter_by(
        invited_by_user_id=current_user.id, email=None
    ).filter(InvitationCode.uses < InvitationCode.max_uses).order_by(InvitationCode.created_at.desc()).first()
    if not share_invite:
        share_invite = InvitationCode(
            code=secrets.token_urlsafe(18),
            invited_by_user_id=current_user.id,
            email=None, max_uses=25, uses=0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        )
        db.session.add(share_invite)
        db.session.commit()
    invite_url = f"{base_url}{url_for('auth.register')}?invite={share_invite.code}&invited_by={current_user.username}"

    sent = []
    failed = []
    existing = []
    raw_emails = ""
    message = ""

    if request.method == "POST":
        raw_emails = (request.form.get("emails") or "").strip()
        message = (request.form.get("message") or "").strip()
        candidates = [e.strip().lower() for e in re.split(r"[\s,;]+", raw_emails) if e.strip()]
        # Reihenfolge behalten, Duplikate entfernen
        emails = list(dict.fromkeys(candidates))
        valid_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        invalid = [e for e in emails if not valid_re.match(e)]
        emails = [e for e in emails if valid_re.match(e)]

        if not emails and not invalid:
            flash("Bitte mindestens eine E-Mail-Adresse eintragen.", "warning")
        if invalid:
            flash("Ungültige Adresse(n): " + ", ".join(invalid), "warning")

        for email in emails:
            if User.query.filter_by(email=email).first():
                existing.append(email)
                continue
            mail_invite = InvitationCode(
                code=secrets.token_urlsafe(18),
                invited_by_user_id=current_user.id,
                email=email, max_uses=1, uses=0,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.session.add(mail_invite)
            db.session.flush()
            personal_url = f"{base_url}{url_for('auth.register')}?invite={mail_invite.code}&invited_by={current_user.username}"
            subject = f"{current_user.username} lädt dich zur Wulmstörper Tipprunde ein"
            custom = f"\nPersönliche Nachricht:\n{message}\n" if message else ""
            body = (
                f"Hallo,\n\n"
                f"{current_user.username} lädt dich zur Wulmstörper Tipprunde ein.\n"
                f"{custom}\n"
                f"Hier kannst du dein Konto erstellen:\n{personal_url}\n\n"
                f"Viel Spaß beim Tippen!"
            )
            ok = send_email(subject, [email], body)
            if ok:
                sent.append(email)
            else:
                db.session.delete(mail_invite)
                failed.append(email)

        if sent or failed:
            db.session.commit()
        if sent:
            flash(f"✅ Einladung gesendet an: {', '.join(sent)}", "success")
        if existing:
            flash(f"ℹ️ Bereits registriert, nicht erneut eingeladen: {', '.join(existing)}", "info")
        if failed:
            flash(f"❌ Einladung konnte nicht gesendet werden an: {', '.join(failed)}", "danger")
        if sent and not failed:
            return redirect(url_for("main.invite_users"), code=303)

    share_text = f"Mach mit bei unserer Wulmstörper Tipprunde: {invite_url}"
    return render_template(
        "invite.html",
        invite_url=invite_url,
        share_text=share_text,
        raw_emails=raw_emails,
        message=message,
    )


@main_bp.route("/mehr")
@login_required
def more():
    return render_template("more.html")


@main_bp.route("/hilfe")
@main_bp.route("/regeln")
@login_required
def help_rules():
    points = {
        "exact": get_setting("points_exact", current_app.config.get("POINTS_EXACT", 4)),
        "diff": get_setting("points_diff", current_app.config.get("POINTS_DIFF", 3)),
        "tendency": get_setting("points_tendency", current_app.config.get("POINTS_TENDENCY", 2)),
    }
    return render_template(
        "help_rules.html",
        points=points,
        current_matchday=get_current_matchday(),
    )

@main_bp.route("/tippen")
@main_bp.route("/tippen/<int:matchday>")
@login_required
def tip_entry(matchday=None):
    """Zentrale Einstiegroute fuer den Tipp-Button.

    Der Tipp-Einstieg fuehrt bewusst immer zum Schnelltipp. Ohne expliziten
    Spieltag wird der erste Spieltag gesucht, bei dem der aktuelle User noch
    ein offenes Spiel nicht getippt hat. Wenn nichts offen ist, bleibt der
    bisherige aktuelle Spieltag als Fallback erhalten.
    """
    if not (current_user.full_name or "").strip():
        flash("Bitte trage zuerst deinen vollen Namen im Profil ein. Das hilft der privaten Tipprunde bei der Zuordnung.", "warning")
        return redirect(url_for("main.profile"))
    if matchday is None:
        now = datetime.now(timezone.utc)
        open_matches = active_match_query().filter(
            Match.status == "scheduled",
            Match.kickoff > now,
        ).order_by(Match.kickoff.asc(), Match.matchday.asc(), Match.id.asc()).all()
        open_ids = [m.id for m in open_matches]
        tipped_ids = set()
        if open_ids:
            tipped_ids = {
                p.match_id for p in Prediction.query.filter(
                    Prediction.user_id == current_user.id,
                    Prediction.match_id.in_(open_ids),
                ).all()
            }
        next_missing = next((m for m in open_matches if m.id not in tipped_ids), None)
        matchday = next_missing.matchday if next_missing else get_current_matchday()
    return redirect(url_for("main.quick_tip", matchday=matchday))

@main_bp.route("/profil/test-benachrichtigung", methods=["POST"])
@login_required
def test_user_notification():
    from notification_center import send_test_missing_tip_notification
    result = send_test_missing_tip_notification(current_user)
    sent = [k for k, ok in result.items() if ok]
    if sent:
        label_map = {"email": "E-Mail", "push": "Push", "telegram": "Telegram", "whatsapp": "WhatsApp"}
        labels = ", ".join(label_map.get(k, k) for k in sent)
        flash(f"✅ Test-Benachrichtigung gesendet über: {labels}.", "success")
    else:
        flash("ℹ️ Keine Test-Benachrichtigung gesendet. Prüfe, ob deine Kanäle aktiviert und eingerichtet sind.", "info")
    return redirect(url_for("main.profile") + "#benachrichtigungen")
