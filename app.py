"""Wulmstörper Tipprunde – Hauptanwendung (Flask).

Refactored: Alle Routes sind in separate Blueprint-Module ausgelagert:
  - routes_main.py   → Hauptseiten (Dashboard, Spielplan, Profil, etc.)
  - routes_auth.py   → Login, Register, Passwort-Reset
  - routes_admin.py  → Admin-Bereich
  - routes_api.py    → JSON API-Endpunkte

Utility-Module:
  - scoring.py       → Punkteberechnung, Ranglisten, User-Stats
  - badges.py        → Badge-System (Vergabe, Prüfung, Seeding)
  - stats.py         → Statistiken, Trend, Insights, Form, H2H, Wetter
  - sync.py          → API-Sync, Seeding, Schema-Migration
  - mail_helpers.py  → E-Mail, Token, Mail-Einstellungen
  - avatars.py       → Avatar-Upload
  - export.py        → PDF/CSV-Export
"""
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, session
from flask_login import current_user

from config import Config
from extensions import db, login_manager, mail, cache, csrf, limiter

from models import Competition

# Blueprint-Module
from routes_main import main_bp
from routes_auth import auth_bp
from routes_admin import admin_bp
from routes_api import api_bp

# Utility-Imports für Startup-Seeding
from sync import seed_teams_if_empty, seed_demo_matches, auto_migrate_schema
from badges import seed_badges, seed_prizes
from scoring import get_setting, set_setting
from mail_helpers import apply_mail_settings
from stats import get_open_matches_for_user

import json as _json


# =================================================================== APP -
def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Extensions initialisieren
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(uid):
        from models import User
        return db.session.get(User, int(uid))

    # Blueprints registrieren
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Live-Scoring Blueprint
    from live_scoring import live_bp
    app.register_blueprint(live_bp, url_prefix="/live")

    # Push & PWA Routes
    from push_routes import register_push_routes
    from pwa_routes import register_pwa_routes
    register_push_routes(app)
    register_pwa_routes(app)

    # ── Asset-Version für Cache-Busting ──
    import time
    _asset_version = str(int(time.time()))

    @app.context_processor
    def inject_globals():
        ctx = {"now": lambda: datetime.now(timezone.utc), "asset_version": _asset_version}

        try:
            # Validierung: Nur existierende Wettbewerbe aus Session erlauben
            comp_code = session.get("competition_code")
            if comp_code:
                comp = Competition.query.filter_by(code=comp_code, is_active=True).first()
                ctx["active_competition"] = comp.code if comp else "BL1"
            else:
                first = Competition.query.filter_by(is_active=True).first()
                ctx["active_competition"] = first.code if first else "BL1"
            ctx["all_competitions"] = Competition.query.filter_by(is_active=True).all()
        except Exception:
            ctx["active_competition"] = "BL1"
            ctx["all_competitions"] = []

        if current_user.is_authenticated:
            try:
                open_matches = get_open_matches_for_user(current_user, max_hours=24)
                ctx["open_match_count"] = len(open_matches)
                ctx["next_open_match"] = open_matches[0] if open_matches else None
            except Exception:
                ctx["open_match_count"] = 0
                ctx["next_open_match"] = None
        return ctx

    @app.context_processor
    def inject_vapid_key():
        return {"vapid_public_key": app.config.get("VAPID_PUBLIC_KEY", "")}

    # ── Template-Filter ──
    @app.template_filter("format_number")
    def format_number_filter(value):
        try:
            return f"{int(value):,}".replace(",", ".")
        except (ValueError, TypeError):
            return value

    DE_WEEKDAYS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    DE_WEEKDAYS_LONG  = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    DE_MONTHS_SHORT   = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    DE_MONTHS_LONG    = ["Januar", "Februar", "März", "April", "Mai", "Juni",
                         "Juli", "August", "September", "Oktober", "November", "Dezember"]

    def _german_strftime(value, fmt):
        if not value:
            return "—"
        wd = value.weekday()
        m = value.month - 1
        result = fmt
        result = result.replace("%a", DE_WEEKDAYS_SHORT[wd])
        result = result.replace("%A", DE_WEEKDAYS_LONG[wd])
        result = result.replace("%b", DE_MONTHS_SHORT[m])
        result = result.replace("%B", DE_MONTHS_LONG[m])
        return value.strftime(result)

    @app.template_filter("dt")
    def fmt_dt(value, fmt="%d.%m.%Y %H:%M"):
        return _german_strftime(value, fmt)

    @app.template_filter("de")
    def fmt_de(value, fmt="%a, %d.%m. %H:%M"):
        return _german_strftime(value, fmt)

    @app.template_filter("fromjson")
    def fromjson(value):
        if not value:
            return []
        try:
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (ValueError, TypeError):
            return []

    # ── Bootstrap DB + Demo ──
    with app.app_context():
        db.create_all()

        # SQLite WAL-Modus
        try:
            db.execute("PRAGMA journal_mode=WAL;")
            db.execute("PRAGMA synchronous=NORMAL;")
            db.execute("PRAGMA cache_size=-64000;")
            db.execute("PRAGMA temp_store=MEMORY;")
            app.logger.info("✅ SQLite WAL-Modus aktiviert")
        except Exception:
            pass

        try:
            auto_migrate_schema()
        except Exception as e:
            app.logger.warning(f"Auto-Migration übersprungen: {e}")

        # Seed Competition
        try:
            if Competition.query.count() == 0:
                default_comp = Competition(
                    code="BL1", name="Bundesliga", season=app.config.get("SEASON", "2025") + "/" + str(int(app.config.get("SEASON", "2025")) + 1), is_active=True
                )
                db.session.add(default_comp)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Competition seed failed: {e}")

        seed_teams_if_empty()
        seed_demo_matches()
        seed_badges()
        seed_prizes()

        # Admin sicherstellen
        from models import User
        admin_email = app.config["ADMIN_EMAIL"].lower()
        admin_username = app.config["ADMIN_USERNAME"]
        admin_password = app.config["ADMIN_PASSWORD"]
        admin_reset = os.environ.get("ADMIN_RESET", "").lower() in ("1", "true", "yes")

        try:
            admin = User.query.filter_by(email=admin_email).first()
            if not admin:
                admin = User.query.filter_by(username=admin_username).first()

            if not admin:
                if not User.query.filter(
                    (User.email == admin_email) | (User.username == admin_username)
                ).first():
                    admin = User(username=admin_username, email=admin_email, is_admin=True)
                    admin.set_password(admin_password)
                    db.session.add(admin)
                    db.session.commit()
                    app.logger.info(f"✅ Admin angelegt: {admin_email}")
            elif admin_reset:
                conflict_email = User.query.filter(User.email == admin_email, User.id != admin.id).first()
                conflict_user = User.query.filter(User.username == admin_username, User.id != admin.id).first()
                if not conflict_email:
                    admin.email = admin_email
                if not conflict_user:
                    admin.username = admin_username
                admin.set_password(admin_password)
                admin.is_admin = True
                db.session.commit()
                app.logger.warning(f"⚠️ Admin RESET: {admin.email}")
            elif not admin.is_admin:
                admin.is_admin = True
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Admin-Bootstrap fehlgeschlagen: {e}")

        # Default-Settings
        if get_setting("points_exact") is None:
            set_setting("points_exact", app.config["POINTS_EXACT"])
            set_setting("points_diff", app.config["POINTS_DIFF"])
            set_setting("points_tendency", app.config["POINTS_TENDENCY"])
        if get_setting("pot_amount") is None:
            set_setting("pot_amount", 5)
            set_setting("pot_currency", "€")
            set_setting("pot_intro", "Jeder Mitspieler zahlt seinen Einsatz in den Pott.")

    # ── Flask CLI ──
    @app.cli.command("reset-admin")
    def cli_reset_admin():
        with app.app_context():
            admin = User.query.filter_by(username=app.config["ADMIN_USERNAME"]).first()
            if not admin:
                admin = User(username=app.config["ADMIN_USERNAME"], email=app.config["ADMIN_EMAIL"].lower(), is_admin=True)
                db.session.add(admin)
            admin.email = app.config["ADMIN_EMAIL"].lower()
            admin.is_admin = True
            admin.set_password(app.config["ADMIN_PASSWORD"])
            db.session.commit()
            print(f"✅ Admin zurückgesetzt: {admin.email}")

    @app.cli.command("set-admin-password")
    def cli_set_admin_password():
        import getpass
        with app.app_context():
            email = input(f"Admin-E-Mail [{app.config['ADMIN_EMAIL']}]: ").strip() or app.config["ADMIN_EMAIL"]
            new_pw = getpass.getpass("Neues Passwort: ")
            if len(new_pw) < 6:
                print("❌ Passwort muss mind. 6 Zeichen haben.")
                return
            admin = User.query.filter_by(email=email.lower()).first()
            if not admin:
                admin = User(username="admin", email=email.lower(), is_admin=True)
                db.session.add(admin)
            admin.set_password(new_pw)
            admin.is_admin = True
            db.session.commit()
            print(f"✅ Passwort für {email} gesetzt.")

    return app


# ============================================================== MAIN -
app = create_app()


@app.route("/profile/test-whatsapp", methods=["POST"])
def test_whatsapp():
    from flask import flash, redirect, url_for
    from flask_login import login_required, current_user
    if not current_user.is_authenticated:
        from flask import abort
        abort(403)
    from whatsapp import send_whatsapp_test
    success = send_whatsapp_test(current_user)
    if success:
        flash("✅ WhatsApp-Testnachricht gesendet!", "success")
    else:
        flash("❌ Senden fehlgeschlagen.", "error")
    return redirect(url_for("main.profile"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port, host="0.0.0.0")
