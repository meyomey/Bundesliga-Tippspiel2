"""Auth-Routes: Registrierung, Login, Logout, Passwort-Reset."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db, limiter
from models import User
from forms import RegisterForm, LoginForm, PasswordResetRequestForm, PasswordResetForm
from mail_helpers import send_password_reset, verify_reset_token


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5/minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        u = User(username=form.username.data, email=form.email.data.lower())
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Willkommen beim Tippspiel!", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html", form=form)


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
    return render_template("auth/login.html", form=form)


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
