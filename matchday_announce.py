"""Spieltags-Sieger-Ansage ((115)) — Sieger + Top 3 nach Spieltagsabschluss.

Nutzerwunsch (10.10.2026): nach Abschluss aller Spiele soll der
Spieltagssieger (plus Top 3 der Gesamtrangliste) in die WhatsApp-Gruppe.

CallMeBot (unser 0-€-Weg) kann KEINE Gruppen, nur private Chats — deshalb
zwei Wege:
1. AUTOMATIK: der Cron-Sync prueft nach jedem Lauf, ob ein Spieltag
   komplett beendet ist, und sendet die Ansage einmalig an alle Mitglieder
   mit eingerichtetem WhatsApp (privater Chat, CallMeBot).
2. GRUPPEN-TEXT: im Admin (API-Sync) steht der fertige Text zum Kopieren
   bereit — der Admin postet ihn in die Gruppe.

Beide Wege nutzen denselben Text (sieger_text). Versand-Markierung liegt
in den DB-Settings (md_winner_sent_<comp>_<md>), damit der Cron nicht
doppelt sendet; schlaegt der Versand teils fehl, wird am nächsten Tick
wiederholt.
"""
import time

from extensions import db
from models import Match, MatchdayWinner, User


def _active_comp():
    from competition_helpers import get_active_competition
    return get_active_competition()


def abgeschlossene_spieltage(competition_id):
    """Matchdays des Wettbewerbs, bei denen ALLE Spiele finished sind."""
    rows = (db.session.query(Match.matchday, Match.status)
            .filter(Match.competition_id == competition_id).all())
    pro_md = {}
    for md, status in rows:
        pro_md.setdefault(md, []).append(status)
    return sorted(
        md for md, staende in pro_md.items()
        if staende and all(s == "finished" for s in staende)
    )


def sieger_text(matchday, competition_id=None):
    """Gruppen-/Broadcast-Text: Spieltagssieger + Top 3 der Gesamtrangliste.

    None, wenn (noch) keine Sieger berechnet werden koennen.
    """
    from scoring import get_live_leaderboard, recompute_matchday_winners

    q = MatchdayWinner.query.filter_by(matchday=matchday)
    if competition_id:
        q = q.filter_by(competition_id=competition_id)
    # (159) IMMER frisch rechnen (statt nur bei fehlenden Zeilen): eine
    # aeltere Teilstand-Zeile wuerde sonst unkorigiert angesagt und via
    # Marker fuer immer eingefroren.
    try:
        recompute_matchday_winners()
    except Exception:
        pass
    winners = q.all()
    if not winners:
        return None

    users = {u.id: u for u in User.query.filter(
        User.id.in_([w.user_id for w in winners])).all()}
    namen = [users[w.user_id].username for w in winners if w.user_id in users]
    if not namen:
        return None
    punkte = winners[0].points or 0
    suffix = " je" if len(namen) > 1 else ""
    trenner = " & ".join(namen)

    top3 = get_live_leaderboard()[:3]
    top_zeilen = "\n".join(
        f"{i}. {r['user'].username} – {r['points']} Pkt."
        for i, r in enumerate(top3, 1)
    )
    text = (f"🏆 Spieltag {matchday} ist durch!\n\n"
            f"🥇 Spieltagssieger: {trenner} ({punkte} Pkt.{suffix})\n\n"
            f"📊 Top 3 der Gesamtrangliste:\n{top_zeilen}")
    # (116) Link zur Rangliste am Ende (nur mit voller Basis-URL — in
    # WhatsApp ist ein relativer Pfad nutzlos).
    try:
        from scoring import get_setting
        from flask import current_app
        base = (get_setting("public_base_url", "")
                or current_app.config.get("PUBLIC_BASE_URL", "")).rstrip("/")
        if base:
            text += f"\n\n📊 Rangliste: {base}/tabelle"
    except Exception:
        pass
    return text


def _wa_empfaenger():
    """Alle aktiven Mitglieder mit eingerichtetem WhatsApp, die CallMeBot
    WOLLEN — der Profil-Schalter (notify_whatsapp) gilt auch hier ((116)).
    Bots sind ausgeschlossen."""
    from notification_center import _truthy
    from scoring import filter_active_users
    kandidaten = User.query.filter(
        ~User.email.like("%@bot.local"),
        User.whatsapp_phone.isnot(None),
        User.whatsapp_apikey.isnot(None),
        User.whatsapp_phone != "",
        User.whatsapp_apikey != "",
    ).all()
    aktiv = {u.id for u in filter_active_users(kandidaten)}
    return [u for u in kandidaten if u.id in aktiv
            and _truthy(getattr(u, "notify_whatsapp", True), True)]


def sende_sieger_an_whatsapp(matchday, competition_id=None):
    """Einzelversand des Ansage-Texts (CallMeBot, private Chats).

    Returns (gesendet, fehlgeschlagen); (0, 0) = kein Text/kein Empfaenger.
    """
    from whatsapp import send_whatsapp_message
    text = sieger_text(matchday, competition_id)
    if not text:
        return 0, 0
    gesendet = fehler = 0
    for user in _wa_empfaenger():
        try:
            if send_whatsapp_message(user.whatsapp_phone,
                                     user.whatsapp_apikey, text):
                gesendet += 1
            else:
                fehler += 1
        except Exception:
            fehler += 1
        time.sleep(1.0)  # CallMeBot schonen
    return gesendet, fehler


def _marke(competition_id, matchday):
    return f"md_winner_sent_{competition_id}_{matchday}"


def pruefe_und_sende_offene_sieger():
    """Cron-Hook: sendet Ansagen fuer neu abgeschlossene Spieltage (1x).

    Markiert in den DB-Settings; nur bei Sendefehlern wird beim naechsten
    Tick wiederholt.
    """
    from scoring import get_setting, set_setting

    comp = _active_comp()
    if not comp:
        return {"ok": True, "gesendet": []}
    from notification_center import _truthy
    offene = [md for md in abgeschlossene_spieltage(comp.id)
              if not _truthy(get_setting(_marke(comp.id, md), False), False)]
    if not offene:
        return {"ok": True, "gesendet": []}

    # (118) Schalter-Scope: whatsapp_enabled steuert NUR diese Automatik
    # (Nutzerpraezisierung zu (117)). Aus -> offene Spieltage als erledigt
    # markieren, OHNE zu senden — beim spaeteren Einschalten werden alte
    # Ansagen nicht nachgeholt. Erinnerungen/Tests bleiben unberuehrt an.
    if not _truthy(get_setting("whatsapp_enabled", True), True):
        from datetime import datetime as _dt, timezone as _tz
        for md in offene:
            set_setting(_marke(comp.id, md),
                        _dt.now(_tz.utc).date().isoformat())
        return {"ok": True, "gesendet": [], "uebersprungen": offene}

    from scoring import recompute_matchday_winners
    try:
        recompute_matchday_winners()  # defensive: spaete Korrekturen einfangen
    except Exception:
        pass

    gesendet = []
    from datetime import datetime, timezone
    for md in offene:
        _g, fehler = sende_sieger_an_whatsapp(md, comp.id)
        if fehler == 0:
            set_setting(_marke(comp.id, md),
                        datetime.now(timezone.utc).date().isoformat())
            gesendet.append(md)
    return {"ok": True, "gesendet": gesendet}
