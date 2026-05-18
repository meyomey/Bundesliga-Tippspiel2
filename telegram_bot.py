"""Telegram Bot für die Wulmstörper Tipprunde."""
import logging
from datetime import datetime, timezone
from extensions import db
from models import User, Match, Prediction, Team

logger = logging.getLogger(__name__)

def generate_telegram_token(user_id):
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps({"user_id": user_id, "purpose": "telegram"}, salt="telegram-link")

def verify_telegram_token(token, max_age=3600):
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app
    try:
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        data = s.loads(token, salt="telegram-link", max_age=max_age)
        if data.get("purpose") == "telegram":
            return data.get("user_id")
    except Exception:
        pass
    return None

def cmd_start(telegram_user_id, token):
    user_id = verify_telegram_token(token)
    if not user_id:
        return "Ungueltiger oder abgelaufener Token."
    user = db.session.get(User, user_id)
    if not user:
        return "Benutzer nicht gefunden."
    user.phone = "tg:" + str(telegram_user_id)
    db.session.commit()
    return ("Dein Telegram-Account ist jetzt verknuepft!\n"
            "Tippen per Chat:\n/tipp FCB-BVB 2:1\n/rangliste\n/spielplan\n/meine_tipps")

def cmd_tip(telegram_user_id, args):
    user = User.query.filter_by(phone="tg:" + str(telegram_user_id)).first()
    if not user:
        return "Du bist nicht verknuepft."
    if not args or len(args) < 2:
        return "Format: /tipp FCB-BVB 2:1"
    match_part = args[0].strip().upper()
    score_part = args[1].strip()
    if "-" not in match_part or ":" not in score_part:
        return "Format: /tipp FCB-BVB 2:1"
    home_short, away_short = match_part.split("-", 1)
    try:
        home_tip, away_tip = score_part.split(":", 1)
        home_tip = int(home_tip.strip())
        away_tip = int(away_tip.strip())
    except (ValueError, TypeError):
        return "Ungueltige Tore. Beispiel: /tipp FCB-BVB 2:1"
    if not (0 <= home_tip <= 30 and 0 <= away_tip <= 30):
        return "Tore muessen zwischen 0 und 30 liegen."
    home_team = Team.query.filter_by(short_name=home_short).first()
    away_team = Team.query.filter_by(short_name=away_short).first()
    if not home_team or not away_team:
        return "Team nicht gefunden. Kuerzel: FCB, BVB, B04, SGE, HSV, etc."
    from sqlalchemy import or_
    now = datetime.now(timezone.utc)
    match = Match.query.filter(
        Match.status == "scheduled", Match.kickoff > now,
        or_((Match.home_team_id == home_team.id) & (Match.away_team_id == away_team.id),
            (Match.home_team_id == away_team.id) & (Match.away_team_id == home_team.id)),
    ).order_by(Match.kickoff.asc()).first()
    if not match:
        return "Kein anstehendes Spiel " + home_short + " vs " + away_short + " gefunden."
    existing = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
    if existing:
        existing.home_tip = home_tip
        existing.away_tip = away_tip
        verb = "aktualisiert"
    else:
        db.session.add(Prediction(
            user_id=user.id, match_id=match.id,
            home_tip=home_tip, away_tip=away_tip, joker=False
        ))
        verb = "gespeichert"
    db.session.commit()
    try:
        from badges import check_and_award_badges
        check_and_award_badges()
    except Exception:
        pass
    ko = match.kickoff.strftime("%d.%m. %H:%M") if match.kickoff else "?"
    return ("Tipp " + verb + "!\n"
            + match.home_team.name + " vs " + match.away_team.name + "\n"
            + ko + "\n" + str(home_tip) + ":" + str(away_tip))

def cmd_rankings(telegram_user_id):
    user = User.query.filter_by(phone="tg:" + str(telegram_user_id)).first()
    if not user:
        return "Du bist nicht verknuepft."
    from scoring import get_leaderboard
    rows = get_leaderboard()[:10]
    if not rows:
        return "Noch keine Ranglistendaten."
    lines = ["Top 10 Rangliste:"]
    for r in rows:
        rank_display = str(r["rank"]) + "."
        marker = " << DU" if r["user"].id == user.id else ""
        lines.append(rank_display + " " + r["user"].username + " - " + str(r["points"]) + " Pkt" + marker)
    return "\n".join(lines)

def cmd_my_tips(telegram_user_id):
    user = User.query.filter_by(phone="tg:" + str(telegram_user_id)).first()
    if not user:
        return "Du bist nicht verknuepft."
    from stats import get_current_matchday
    matchday = get_current_matchday()
    matches = Match.query.filter_by(matchday=matchday).order_by(Match.kickoff).all()
    if not matches:
        return "Keine Spiele fuer Spieltag " + str(matchday) + "."
    lines = ["Spieltag " + str(matchday) + " - Deine Tipps:"]
    for m in matches:
        pred = Prediction.query.filter_by(user_id=user.id, match_id=m.id).first()
        if pred:
            tip_str = str(pred.home_tip) + ":" + str(pred.away_tip)
            if pred.joker:
                tip_str += " (Joker)"
        else:
            tip_str = "kein Tipp"
        ko = m.kickoff.strftime("%d.%m. %H:%M") if m.kickoff else "?"
        lines.append(m.home_team.short_name + " vs " + m.away_team.short_name + ": " + tip_str + " (" + ko + ")")
    return "\n".join(lines)

def cmd_schedule(telegram_user_id):
    from stats import get_current_matchday
    matchday = get_current_matchday()
    matches = Match.query.filter_by(matchday=matchday).order_by(Match.kickoff).all()
    if not matches:
        return "Keine Spiele fuer Spieltag " + str(matchday) + "."
    lines = ["Spieltag " + str(matchday) + ":"]
    for m in matches:
        score = ""
        if m.status == "finished" and m.home_score is not None:
            score = " " + str(m.home_score) + ":" + str(m.away_score)
        elif m.status == "live":
            score = " LIVE " + str(m.home_score or 0) + ":" + str(m.away_score or 0)
        ko = m.kickoff.strftime("%d.%m. %H:%M") if m.kickoff else "?"
        lines.append(m.home_team.short_name + " vs " + m.away_team.short_name + score + " (" + ko + ")")
    return "\n".join(lines)

def process_message(telegram_user_id, text):
    if not text:
        return None
    parts = text.strip().split()
    command = parts[0].lower()
    if command == "/start" and len(parts) > 1:
        return cmd_start(telegram_user_id, parts[1])
    if command in ("/tipp", "/tip"):
        return cmd_tip(telegram_user_id, parts[1:])
    if command in ("/rangliste", "/ranking", "/leaderboard"):
        return cmd_rankings(telegram_user_id)
    if command in ("/meine_tipps", "/mytipps"):
        return cmd_my_tips(telegram_user_id)
    if command in ("/spielplan", "/schedule"):
        return cmd_schedule(telegram_user_id)
    if command in ("/hilfe", "/help"):
        return ("/start TOKEN - Account verknuepfen\n"
                "/tipp FCB-BVB 2:1 - Tipp abgeben\n"
                "/rangliste - Top 10\n"
                "/meine_tipps - Meine Tipps\n"
                "/spielplan - Aktueller Spieltag\n"
                "/hilfe - Diese Hilfe")
    return None

def send_telegram_message(chat_id, text):
    from flask import current_app
    import requests
    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        from scoring import get_setting
        token = get_setting("telegram_bot_token", "")
    if not token:
        logger.warning("Kein Telegram Bot Token konfiguriert.")
        return False
    try:
        resp = requests.post(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
        return resp.ok
    except Exception as e:
        logger.error("Telegram API error: " + str(e))
        return False

def notify_user_telegram(user, message):
    if not user or not user.phone or not user.phone.startswith("tg:"):
        return False
    return send_telegram_message(user.phone.replace("tg:", ""), message)
