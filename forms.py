"""WTForms für das Tippspiel."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, BooleanField, IntegerField,
    SubmitField, TextAreaField, SelectField, DateTimeLocalField,
)
from wtforms.validators import (
    DataRequired, InputRequired, Email, Length, EqualTo, NumberRange,
    ValidationError, Optional, Regexp,
)
from models import User



# ----------------------------------------------------------------
# Toleranter Email-Validator
# ----------------------------------------------------------------
# Der Standard-Email-Validator von email_validator lehnt seit v2
# Sonder-TLDs wie .local, .test, .invalid ab. Für die Settings-Seite
# (z.B. "noreply@tippspiel.local" als Absender) und für lokale
# Hostnamen brauchen wir eine entspanntere Validierung, die nur
# das Format prüft.

import re as _re
_EMAIL_FORMAT_RE = _re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?)*$"
)


class EmailFormat:
    """Prüft nur das Format einer E-Mail-Adresse, nicht die Deliverability
    oder reservierte TLDs. Ideal für selbstgehostete Setups."""

    def __init__(self, message=None):
        self.message = message or "Bitte gültige E-Mail-Adresse eingeben."

    def __call__(self, form, field):
        if not field.data:
            return
        value = (field.data or "").strip()
        if not _EMAIL_FORMAT_RE.match(value):
            raise ValidationError(self.message)
        if len(value) > 254:
            raise ValidationError(self.message)


class RegisterForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired(), Length(3, 64)])
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    password = PasswordField("Passwort", validators=[DataRequired(), Length(min=6, max=128)])
    confirm = PasswordField("Passwort wiederholen", validators=[DataRequired(), EqualTo("password", message="Passwörter stimmen nicht überein.")])
    submit = SubmitField("Registrieren")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Benutzername bereits vergeben.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("E-Mail bereits registriert.")


class LoginForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    remember = BooleanField("Angemeldet bleiben")
    submit = SubmitField("Anmelden")


class ProfileForm(FlaskForm):
    username = StringField("Spielername (öffentlich)", validators=[DataRequired(), Length(3, 64)])
    full_name = StringField("Voller Name", validators=[Optional(), Length(0, 120)])
    show_full_name = BooleanField("Vollen Namen öffentlich anzeigen", default=True)
    phone = StringField("Mobilfunk / WhatsApp", validators=[Optional(), Length(0, 40)])
    whatsapp_phone = StringField(
        "WhatsApp-Nummer (CallMeBot)",
        validators=[Optional(), Length(max=20),
                    Regexp(r'^\+?[0-9\s\-]{7,20}$',
                           message="Bitte eine gültige Nummer mit Ländervorwahl eingeben (z.B. +4917612345678)")],
        description="Mit Ländervorwahl, z.B. +4917612345678",
    )
    whatsapp_apikey = StringField(
        "CallMeBot API-Key",
        validators=[Optional(), Length(max=20)],
        description="Du erhältst diesen Key von CallMeBot (einmalige Registrierung nötig)",
    )
    notify_enabled = BooleanField("Benachrichtigungen aktiv", default=True)
    notify_email = BooleanField("E-Mail", default=True)
    notify_push = BooleanField("Push", default=True)
    notify_telegram = BooleanField("Telegram", default=True)
    notify_whatsapp = BooleanField("WhatsApp", default=True)
    notify_hours_before = IntegerField("Erinnerung Stunden vor Anpfiff", default=1, validators=[Optional(), NumberRange(0, 24)])
    notify_only_favorite = BooleanField("Nur Spiele meines Lieblingsvereins", default=False)
    default_tip_view = SelectField(
        "Standard-Tippansicht",
        choices=[("normal", "Normale Tippansicht"), ("quick", "Schnelltipp")],
        default="normal",
        validators=[Optional()],
    )
    favorite_team_id = SelectField("Lieblingsverein", coerce=int, validators=[Optional()])
    avatar = FileField("Avatar (max. 4MB)", validators=[FileAllowed(["png", "jpg", "jpeg", "gif", "webp"])])
    submit = SubmitField("Speichern")


class PasswordResetRequestForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    submit = SubmitField("Reset-Link senden")


class PasswordResetForm(FlaskForm):
    password = PasswordField("Neues Passwort", validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField("Passwort wiederholen", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Passwort ändern")


class TipForm(FlaskForm):
    home_tip = IntegerField("Heim", validators=[InputRequired(), NumberRange(0, 30)])
    away_tip = IntegerField("Auswärts", validators=[InputRequired(), NumberRange(0, 30)])
    joker = BooleanField("Joker (×2)")
    submit = SubmitField("Tipp speichern")


class CommentForm(FlaskForm):
    text = TextAreaField("Kommentar", validators=[DataRequired(), Length(min=2, max=500)])
    submit = SubmitField("Kommentar abschicken")


class MatchResultForm(FlaskForm):
    home_score = IntegerField("Heim-Tore", validators=[InputRequired(), NumberRange(0, 30)])
    away_score = IntegerField("Auswärts-Tore", validators=[InputRequired(), NumberRange(0, 30)])
    submit = SubmitField("Ergebnis speichern")


ANSWER_TYPE_CHOICES = [
    ("text",       "📝 Freitext"),
    ("choice",     "📋 Multiple-Choice (eigene Optionen)"),
    ("team",       "⚽ Mannschaft (eine wählen)"),
    ("multi_team", "⚽⚽ Mehrere Mannschaften (z.B. Absteiger)"),
    ("yes_no",     "✓✗ Ja / Nein"),
    ("number",     "🔢 Zahl"),
]


class SpecialQuestionForm(FlaskForm):
    text = StringField("Frage", validators=[DataRequired(), Length(3, 300)])
    description = StringField("Beschreibung (optional)", validators=[Optional(), Length(0, 500)])

    answer_type = SelectField(
        "Antworttyp",
        choices=ANSWER_TYPE_CHOICES,
        default="text",
        validators=[DataRequired()],
    )

    options = TextAreaField(
        "Antwortoptionen / eingeschränkte Teams (eine pro Zeile)",
        validators=[Optional()],
    )

    multi_count = IntegerField(
        "Anzahl Antworten (bei mehreren Mannschaften)",
        default=1,
        validators=[Optional(), NumberRange(1, 18)],
    )

    number_min = IntegerField(
        "Min. Zahl (bei Zahl-Frage)",
        validators=[Optional()],
    )
    number_max = IntegerField(
        "Max. Zahl (bei Zahl-Frage)",
        validators=[Optional()],
    )

    deadline = DateTimeLocalField(
        "Deadline (Datum & Uhrzeit)",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Bitte Deadline auswählen.")],
    )
    points_value = IntegerField(
        "Punkte bei richtiger Antwort",
        validators=[DataRequired(), NumberRange(1, 100)],
    )
    correct_answer = StringField(
        "Korrekte Antwort (kann später eingetragen werden)",
        validators=[Optional()],
    )
    submit = SubmitField("Speichern")


class SpecialAnswerForm(FlaskForm):
    """Wird dynamisch je Frage gerendert; Antwort als String."""
    answer = StringField("Antwort", validators=[DataRequired(), Length(1, 200)])
    submit = SubmitField("Tipp speichern")


BADGE_TRIGGER_CHOICES = [
    ("manual",          "✋ Manuell (nur Admin vergibt)"),
    ("first_tip",       "🎯 Erster Tipp"),
    ("tips_count",      "📊 X Tipps abgegeben (Schwelle setzen)"),
    ("total_points",    "💯 X Punkte erreicht (Schwelle setzen)"),
    ("exact_count",     "🎯 X exakte Tipps (Schwelle setzen)"),
    ("joker_exact",     "⚡ Joker mit exaktem Tipp eingelöst"),
    ("perfect_day",     "👑 Alle Spiele eines Spieltags exakt"),
    ("matchday_winner", "🏆 X Spieltage gewonnen (Schwelle setzen)"),
]


class BadgeForm(FlaskForm):
    code = StringField("Code (intern, eindeutig)", validators=[DataRequired(), Length(2, 50)])
    name = StringField("Anzeigename", validators=[DataRequired(), Length(2, 100)])
    description = StringField("Beschreibung", validators=[DataRequired(), Length(2, 300)])
    icon = StringField("Icon (Emoji)", default="🏅", validators=[DataRequired(), Length(1, 10)])
    color = StringField("Farbe (Hex)", default="#fbbf24", validators=[Optional(), Length(0, 20)])
    trigger_type = SelectField("Vergabe-Trigger", choices=BADGE_TRIGGER_CHOICES,
                                default="manual", validators=[DataRequired()])
    threshold = IntegerField("Schwelle (nur bei 'X erreicht'-Triggern)", default=0,
                              validators=[Optional(), NumberRange(0, 10000)])
    active = BooleanField("Aktiv", default=True)
    submit = SubmitField("Speichern")


class SettingsForm(FlaskForm):
    points_exact = IntegerField("Punkte für exakten Tipp", default=4, validators=[Optional(), NumberRange(1, 20)])
    points_diff = IntegerField("Punkte für Tordifferenz", default=3, validators=[Optional(), NumberRange(1, 20)])
    points_tendency = IntegerField("Punkte für Tendenz", default=2, validators=[Optional(), NumberRange(1, 20)])
    pot_amount = IntegerField("Einsatz pro Spieler (€)",
                               default=5, validators=[Optional(), NumberRange(0, 10000)])
    pot_currency = StringField("Währungssymbol", default="€",
                                validators=[Optional(), Length(0, 5)])
    pot_intro = TextAreaField("Erläuterung zum Pott (für Spieler)",
                               validators=[Optional(), Length(0, 500)])
    payment_info_title = StringField("Zahlungsinfo Titel", default="Zahlung an den Spielleiter",
                                     validators=[Optional(), Length(0, 120)])
    payment_info_text = TextAreaField("Zahlungsinformationen",
                                      validators=[Optional(), Length(0, 1000)])
    prize_notes = TextAreaField("Hinweis zu Gewinnen / Preisgeldern",
                                validators=[Optional(), Length(0, 1000)])
    football_data_token = PasswordField("football-data.org Token", validators=[Optional()])
    public_base_url = StringField(
        "Öffentliche Basis-URL",
        validators=[Optional(), Length(0, 200)],
        description="z.B. https://tippspiel.example.de – fuer Links in E-Mails/Push.",
    )

    mail_server = StringField("SMTP-Server", validators=[Optional(), Length(0, 120)])
    mail_port = IntegerField("SMTP-Port", default=587, validators=[Optional(), NumberRange(1, 65535)])
    mail_username = StringField("SMTP-Benutzername", validators=[Optional(), Length(0, 200)])
    mail_password = PasswordField("SMTP-Passwort / App-Passwort", validators=[Optional(), Length(0, 200)])
    mail_default_sender = StringField("Absender-Adresse", validators=[Optional(), EmailFormat()])
    mail_use_tls = BooleanField("STARTTLS verwenden", default=True)
    mail_use_ssl = BooleanField("SSL verwenden", default=False)
    mail_test_recipient = StringField("Test-Empfänger", validators=[Optional(), EmailFormat()])

    vapid_public = PasswordField("VAPID Public Key", validators=[Optional()])
    vapid_private = PasswordField("VAPID Private Key", validators=[Optional()])

    telegram_bot_token = PasswordField(
        "Telegram Bot Token",
        validators=[Optional(), Length(0, 100)],
        description="Vom @BotFather auf Telegram. Ermoeglicht Tippen per Chat.",
    )
    telegram_bot_username = StringField(
        "Telegram Bot Username",
        validators=[Optional(), Length(0, 100)],
        description="Username des Bots (z.B. @MeinTippspielBot)",
    )
    telegram_webhook_secret = PasswordField(
        "Telegram Webhook Secret",
        validators=[Optional(), Length(0, 200)],
        description="Geheimer Wert fuer /telegram/webhook/<secret> oder Header X-Telegram-Bot-Api-Secret-Token.",
    )
    reminders_enabled = BooleanField(
        "Automatische Erinnerungen bei fehlenden Tipps aktivieren",
        default=True,
        description="Erinnert Spieler vor Anpfiff ueber ihre aktivierten Kanaele: E-Mail, Push, Telegram oder WhatsApp.",
    )

    registration_mode = SelectField(
        "Registrierung",
        choices=[
            ("open", "Offen – jeder kann sich registrieren"),
            ("invite", "Nur mit Einladungscode"),
            ("closed", "Geschlossen – keine Registrierung"),
        ],
        default="invite",
        validators=[DataRequired()],
        description="Steuert, ob neue Benutzer sich frei, nur per Einladung oder gar nicht registrieren koennen.",
    )

    submit = SubmitField("Einstellungen speichern")


class AdminUserForm(FlaskForm):
    """Admin bearbeitet Spieler-Daten + Bezahl-Status."""
    username = StringField("Spielername", validators=[DataRequired(), Length(3, 64)])
    full_name = StringField("Voller Name", validators=[Optional(), Length(0, 120)])
    show_full_name = BooleanField("Vollen Namen öffentlich anzeigen", default=True)
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    phone = StringField("Mobilfunk / WhatsApp", validators=[Optional(), Length(0, 40)])
    favorite_team_id = SelectField("Lieblingsverein", coerce=int, validators=[Optional()])
    is_admin = BooleanField("Admin-Rechte")
    has_paid = BooleanField("Hat bezahlt")
    paid_note = StringField("Notiz zur Zahlung",
                             validators=[Optional(), Length(0, 200)])
    new_password = PasswordField("Neues Passwort (optional)",
                                  validators=[Optional(), Length(min=6)])
    submit = SubmitField("Speichern")


class PrizeForm(FlaskForm):
    rank = IntegerField("Platz (0 = Sonderpreis)",
                         default=1, validators=[InputRequired(), NumberRange(0, 99)])
    title = StringField("Titel", validators=[DataRequired(), Length(2, 120)])
    description = StringField("Beschreibung", validators=[Optional(), Length(0, 500)])
    icon = StringField("Icon (Emoji)", default="🏆",
                        validators=[DataRequired(), Length(1, 10)])
    color = StringField("Farbe (Hex)", default="#fbbf24",
                         validators=[Optional(), Length(0, 20)])
    amount = StringField("Preis (z.B. '60 €' oder 'Pokal')",
                          validators=[Optional(), Length(0, 50)])
    detail = TextAreaField("Detail-Text", validators=[Optional(), Length(0, 500)])
    active = BooleanField("Aktiv anzeigen", default=True)
    sort_order = IntegerField("Sortier-Reihenfolge",
                                default=0, validators=[Optional(), NumberRange(-100, 100)])
    submit = SubmitField("Speichern")
