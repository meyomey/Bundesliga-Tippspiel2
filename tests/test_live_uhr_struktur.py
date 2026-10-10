"""Tests Struktur-Widerspruchs-Check der Live-Uhr ((110)).

Nutzerbefund 10.10.2026 (nach Deploy von (105)-(109), v3.1.79): in der
ganzen Halbzeitpause stand weiter "LIVE · 45. Min". Analyse: der Feed
(API-Football/fd) meldete die ganze Pause frisch "1. Halbzeit / 45." —
der (105)-Frische-Guard misst nur Frische, nicht Widerspruch zur
Spielstruktur. Ab ~50 Min nach Anstoss kann die 1. Halbzeit real nicht
mehr laufen; entsprechend gewinnt dort die Struktur-Uhr. Genauso ist in
der 2. Halbzeit eine deutlich zu kleine Minute eingefroren.
"""
from datetime import datetime, timedelta, timezone

from models import Match

from routes_api import live_clock_for

JETZT = datetime(2026, 10, 10, 14, 25, tzinfo=timezone.utc)  # Samstag


def _live(minute, phase="IN_PLAY", *, anstoss_vor=55, frisch_min=1):
    """Live-Match: Anstoss 'anstoss_vor' Minuten her; letzter Feed-Schreib-
    versuch 'frisch_min' Minuten her (naive UTC)."""
    return Match(
        status="live",
        kickoff=JETZT.replace(tzinfo=None) - timedelta(minutes=anstoss_vor),
        minute=minute,
        live_phase=phase,
        live_synced_at=JETZT.replace(tzinfo=None) - timedelta(minutes=frisch_min),
    )


# ---- Pausenfenster: frisches "45." wird zur Halbzeit-Naeherung ----------

def test_frisches_45_mitten_in_der_pause_ist_halbzeit():
    """DER Befund: Feed schreibt frisch IN_PLAY/45, 55 Min nach Anstoss
    -> 'Halbzeit ≈' statt ewiger '45. Min'."""
    lc = live_clock_for(_live(45, frisch_min=1), now=JETZT)
    assert lc["halftime"] == "derived"
    assert lc["minute"] is None


def test_frisches_46_und_47_auch_halbzeit():
    lc = live_clock_for(_live(46, frisch_min=2), now=JETZT)
    assert lc["halftime"] == "derived"
    lc = live_clock_for(_live(47, frisch_min=2), now=JETZT)
    assert lc["halftime"] == "derived"


def test_paused_bleiht_verbindlich_vor_struktur():
    """Echte PAUSED-Phase (Regel 1) schlaegt den Struktur-Check."""
    lc = live_clock_for(_live(45, phase="PAUSED"), now=JETZT)
    assert lc["halftime"] == "feed"


def test_endwertminute_in_der_nachspielzeit_mit_naehrungsmarke():
    """(112) Nachspielzeit (elapsed 49, Feed haengt bei 47): der Wert
    bleibt, wird aber ehrlich als Naeherung markiert ('≈ 47. Min')."""
    lc = live_clock_for(_live(47, anstoss_vor=49, frisch_min=1), now=JETZT)
    assert lc["minute"] == 47 and lc["derived"] is True


def test_atypisch_kleine_minute_im_fenster_bleiht_feed():
    """Regel 1 (Feed-Prioritaet): eine atypische 34 bei elapsed 60 ist
    kein Endwert-Muster -> verbindlich (Synthetik/Grenzfall, kein
    Pausen-Erkennungsmuster)."""
    lc = live_clock_for(_live(34, anstoss_vor=60, frisch_min=1), now=JETZT)
    assert lc["minute"] == 34


# ---- (112) Endwert-Fenster: ≈-Marke statt verbatim ----------------------

def test_haengende_45_kurz_vor_der_pause_bekommt_naehrungsmarke():
    """DER Screenshot-Fall 10.10. (19:21, elapsed ~51 ist (110)-Halbzeit;
    hier der Streifen davor): frisches 45 bei elapsed 47 -> '≈ 45. Min'
    statt verbatim — der Nutzer sieht, dass der Wert nicht frisch gezählt
    werden kann."""
    lc = live_clock_for(_live(45, anstoss_vor=47, frisch_min=1), now=JETZT)
    assert lc["minute"] == 45 and lc["derived"] is True


def test_endwertminute_in_normalem_spielzeitverlauf_ohne_marke():
    """Feed-Minute 45 im normalen Lauf (elapsed 44 = 45. Spielminute):
    verbindlich ohne ≈ — Regel 1 bleibt: echte Werte haben Vorrang."""
    lc = live_clock_for(_live(45, anstoss_vor=44, frisch_min=1), now=JETZT)
    assert lc["minute"] == 45 and lc["derived"] is False


# ---- 2. Halbzeit: deutlich zu kleine Minute = eingefroren ---------------

def test_haengende_45_in_der_2_halbzeit_wird_struktur():
    """65 Min nach Anstoss (2. Halbzeit): frisches 45 ist eingefroren
    -> Struktur-Minute 51 ('≈')."""
    lc = live_clock_for(_live(45, anstoss_vor=65, frisch_min=1), now=JETZT)
    assert lc["minute"] == 51 and lc["derived"] is True
    assert lc["halftime"] is None


def test_plausible_minute_in_der_2_halbzeit_bleibt_verbindlich():
    """46-50 direkt nach Pausenende ist real (API zaehlt weiter) — nicht
    anfassen."""
    for mi, e in ((46, 64), (48, 66), (52, 70)):
        lc = live_clock_for(_live(mi, anstoss_vor=e, frisch_min=1), now=JETZT)
        assert lc["minute"] == mi, f"Minute {mi} bei elapsed {e}"


def test_h2_start_45_ist_pauserwert_struktur_mindestens_46():
    """(113) DER Abendbefund: direkt nach Pausenende (elapsed 63) haengt
    der Feed noch bei 45 -> Struktur-Uhr (49 ≈), nie wieder "45. Min" in
    der 2. Halbzeit."""
    lc = live_clock_for(_live(45, anstoss_vor=63, frisch_min=1), now=JETZT)
    assert lc["minute"] == 49 and lc["derived"] is True


def test_h2_start_46_ist_verbindlich():
    """Sobald der Feed auf 46 springt (H2 gezaehlt), gilt er verbatim."""
    lc = live_clock_for(_live(46, anstoss_vor=63, frisch_min=1), now=JETZT)
    assert lc["minute"] == 46 and lc["derived"] is False


def test_h2_45_bleibt_stets_struktur_auch_spaeter():
    lc = live_clock_for(_live(45, anstoss_vor=75, frisch_min=1), now=JETZT)
    assert lc["minute"] == 61 and lc["derived"] is True


def test_frische_2_halbzeit_minute_ohne_zeitstempel_ok():
    """Alt-Bestand ohne live_synced_at (frisch=True) laeuft durch dieselben
    Struktur-Regeln."""
    m = _live(45, anstoss_vor=70, frisch_min=1)
    m.live_synced_at = None
    lc = live_clock_for(m, now=JETZT)
    assert lc["minute"] == 56 and lc["derived"] is True
