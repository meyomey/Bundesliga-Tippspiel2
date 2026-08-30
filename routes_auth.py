"""Auth-Routes: Registrierung, Login, Logout, Passwort-Reset."""
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db, limiter
from models import User, InvitationCode
from forms import RegisterForm, LoginForm, PasswordResetRequestForm, PasswordResetForm
from mail_helpers import send_password_reset, verify_reset_token
from scoring import get_setting


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5/minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    registration_mode = get_setting("registration_mode", "invite")
    if registration_mode not in ("open", "invite", "closed"):
        registration_mode = "invite"

    invite_code_value = (request.values.get("invite") or "").strip()
    invite = InvitationCode.query.filter_by(code=invite_code_value).first() if invite_code_value else None
    invite_valid_for_page = bool(invite and invite.is_valid_for_email())
    form = RegisterForm()

    if registration_mode == "closed":
        return render_template(
            "auth/register.html", form=form, invite_required=True, registration_closed=True,
            invite_code=invite_code_value, registration_mode=registration_mode,
        ), 403

    if request.method == "GET" and registration_mode == "invite" and not invite_valid_for_page:
        return render_template(
            "auth/register.html", form=form, invite_required=True, invite_code=invite_code_value,
            registration_mode=registration_mode, registration_closed=False,
        ), 403

    if form.validate_on_submit():
        email = form.email.data.lower()
        invite_code_value = (request.form.get("invite") or "").strip()
        invite = InvitationCode.query.filter_by(code=invite_code_value).first() if invite_code_value else None
        if registration_mode == "invite" and (not invite or not invite.is_valid_for_email(email)):
            flash("Registrierung nur mit gültiger Einladung möglich.", "danger")
            return render_template(
                "auth/register.html", form=form, invite_required=True, invite_code=invite_code_value,
                registration_mode=registration_mode, registration_closed=False,
            ), 403

        u = User(username=form.username.data, email=email)
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.flush()
        if invite:
            invite.uses = (invite.uses or 0) + 1
            invite.used_by_user_id = invite.used_by_user_id or u.id
            invite.used_at = invite.used_at or datetime.now(timezone.utc)
        db.session.commit()
        login_user(u)
        flash("Willkommen beim Tippspiel!", "success")
        return redirect(url_for("main.dashboard"))
    return render_template(
        "auth/register.html", form=form, invite_required=False, invite_code=invite_code_value,
        registration_mode=registration_mode, registration_closed=False,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(email=form.email.data.lower()).first()
        if u and u.check_password(form.password.data):
            login_user(u, remember=form.remember.data)
            return redirect(request.args.get("next") or url_for("main.dashboard"))
        flash("E-Mail oder Passwort falsch.", "danger")
    return render_template("auth/login.html", form=form, registration_mode=get_setting("registration_mode", "invite"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Abgemeldet.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/passwort-vergessen", methods=["GET", "POST"])
@limiter.limit("3/minute")
def password_reset_request():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        u = User.query.filter_by(email=form.email.data.lower()).first()
        if u:
            send_password_reset(u)
        flash("Falls die E-Mail existiert, wurde ein Link gesendet.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/password_reset_request.html", form=form)


@auth_bp.route("/passwort-zuruecksetzen/<token>", methods=["GET", "POST"])
@limiter.limit("5/minute")
def password_reset(token):
    user = verify_reset_token(token)
    if not user:
        flash("Reset-Link ungültig oder abgelaufen.", "danger")
        return redirect(url_for("auth.login"))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Passwort geändert. Du kannst dich jetzt anmelden.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/password_reset.html", form=form)
