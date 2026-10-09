"""Tests Frische-Guard der Live-Uhr ((105)).

Nutzerbefund 09.10.2026 (Screenshot): das Live-Center blieb minutenlang bei
"LIVE · 45. Min", statt zur Halbzeit ueberzugehen — der Feed (API-Football,
Tagesbudget erschoepft / Liveticker langsam) hatte die Minute geschrieben
und danach nicht mehr aktualisiert. live_clock_for vertraute der
eingefrorenen Minute unbegrenzt. Seit (105) gilt ein Feed-Wert nur noch
10 Minuten als verbindlich; danach uebernimmt die Struktur-Uhr (UI "≈").
"""
from datetime import datetime, timedelta, timezone

from models import Match
from routes_api import live_clock_for

# Abend von BVB–Werder (Anstoss 20:30 UTC+2 -> 18:30 UTC); Screenshot ~21:25
JETZT = datetime(2026, 10, 9, 21, 25, tzinfo=timezone.utc)


def _live(elapsed, *, minute=45, phase="IN_PLAY", vor_minuten=2):
    """Live-Match: Anstoss 'elapsed' Minuten her, letzter Feed-Schreibversuch
    'vor_minuten' Minuten her (naive UTC wie von den Sync-Schreibern)."""
    return Match(
        status="live",
        kickoff=JETZT.replace(tzinfo=None) - timedelta(minutes=elapsed),
        minute=minute,
        live_phase=phase,
        live_synced_at=JETZT.replace(tzinfo=None) - timedelta(minutes=vor_minuten),
    )


def test_frische_feed_minute_bleibt_verbindlich():
    """Feed-Frische (< 10 Min): echte Minute gilt weiter, ohne '≈'."""
    lc = live_clock_for(_live(45, minute=45, vor_minuten=2), now=JETZT)
    assert lc["minute"] == 45 and lc["derived"] is False
    assert lc["halftime"] is None


def test_eingefrorene_minute_wird_zur_halbzeit_naehrung():
    """DER Nutzerfall: Minute 45 seit 12 Min eingefroren, Anstoss 55 Min her
    -> statt falscher '45. Min' jetzt Halbzeit (Struktur-Uhr, '≈')."""
    lc = live_clock_for(_live(55, minute=45, vor_minuten=12), now=JETZT)
    assert lc["halftime"] == "derived"
    assert lc["minute"] is None


def test_ohne_zeitstempel_gilt_altbestand_weiter():
    """Alt-Bestand vor (105) (live_synced_at=None): bisheriges Verhalten —
    Feed-Minute wird wie gehabt verbindlich genommen (92 -> inkl. Verlaengerung)."""
    m = _live(50, minute=92, vor_minuten=2)
    m.live_synced_at = None
    lc = live_clock_for(m, now=JETZT)
    assert lc["minute"] == 92 and lc["overtime"] is True


def test_frische_pause_laut_feed_bleibt_verbindlich():
    """PAUSED frisch geschrieben: Halbzeit laut Feed (keine Zaehlerei)."""
    lc = live_clock_for(_live(50, phase="PAUSED", vor_minuten=1), now=JETZT)
    assert lc["halftime"] == "feed" and lc["minute"] is None


def test_eingefrorene_pause_frueh_bleibt_halbzeit():
    """Eingefrorene PAUSED kurz nach der Pause-Grenze: die Struktur-Uhr
    landet noch im eigenen Halbzeitfenster -> weiterhin Halbzeit ('≈')."""
    lc = live_clock_for(_live(52, phase="PAUSED", vor_minuten=12), now=JETZT)
    assert lc["halftime"] == "derived"


def test_eingefrorene_pause_spaet_startet_2_halbzeit():
    """Eingefrorene PAUSED laengst ueber die Pause hinaus (Anstoss 70 Min
    her): ehrliche '2. Halbzeit ≈' statt endloser Pause-Anzeige."""
    lc = live_clock_for(_live(70, phase="PAUSED", vor_minuten=12), now=JETZT)
    assert lc["minute"] == 56 and lc["derived"] is True
    assert lc["halftime"] is None


def test_eingefrorene_minute_vor_der_pause_zaehlt_nachspielzeit():
    """Eingefrorene Minute kurz vor der Pause (Anstoss 46 Min her): die
    Struktur-Uhr zeigt die Naehrung 47 ('≈') statt falscher 45."""
    lc = live_clock_for(_live(46, minute=45, vor_minuten=12), now=JETZT)
    assert lc["minute"] == 47 and lc["derived"] is True


def test_aware_zeitstempel_aequivalent_behandelt():
    """Aware-Zeitstempel (andere Schreibweise) laufen durch dieselbe Logik."""
    m = _live(55, minute=45, vor_minuten=2)
    m.live_synced_at = JETZT - timedelta(minutes=12)  # aware
    lc = live_clock_for(m, now=JETZT)
    assert lc["halftime"] == "derived"
