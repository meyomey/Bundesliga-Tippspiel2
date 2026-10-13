"""Tests Score-Monotonie im Live-Betrieb ((114)).

Nutzerbefund (10.10., RB Leipzig 4:0 bzw. 6:0): "im letzten Spiel wurde
eben 1:0 angezeigt, das war richtig. Dann habe ich Jetzt aktualisieren
gedrueckt, dann stand es wieder 0:0." Ursache: zwei Quellen mit
unterschiedlicher Latenz — der schnelle OLB-Live-Boost schrieb den
aktuellen Stand, der danach laufende football-data-Sync (Free-Tier
verzoegert) ueberschrieb ihn mit seinem veralteten Wert. Fix an der
zentralen Schreibstelle: laufende Spiele duerfen von automatischen
Quellen keinen Score-Rueckschritt mehr erhalten (Paar-weise); ein Tor
kann nicht verschwinden.
"""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Competition, Match, Team

from match_results import apply_match_update


def _live_match(db, competition, teams, hs=1, as_=0):
    m = Match(competition_id=competition.id, matchday=5,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(minutes=55),
              status="live", is_live=True,
              home_score=hs, away_score=as_,
              external_id="fd:4711")
    db.session.add(m)
    db.session.flush()
    return m


def test_live_rueckschritt_wird_verworfen(db, competition, teams):
    """DER Befund: 1:0 -> veralteter Feed sagt 0:0 -> bleibt 1:0."""
    m = _live_match(db, competition, teams, 1, 0)
    changed = apply_match_update(m, home_score=0, away_score=0, status="live")
    assert changed is False
    assert (m.home_score, m.away_score) == (1, 0)


def test_live_vorwaerts_wird_übernommen(db, competition, teams):
    m = _live_match(db, competition, teams, 1, 0)
    changed = apply_match_update(m, home_score=2, away_score=0, status="live")
    assert changed is True
    assert (m.home_score, m.away_score) == (2, 0)


def test_live_gleicher_wert_kein_rueckschritt(db, competition, teams):
    m = _live_match(db, competition, teams, 1, 0)
    changed = apply_match_update(m, home_score=1, away_score=0, status="live")
    assert changed is False
    assert (m.home_score, m.away_score) == (1, 0)


def test_admin_korrektur_rueckschritt_erlaubt(db, competition, teams):
    """Explizite Admin-Aktion (allow_status_reset=True) darf zurücksetzen."""
    m = _live_match(db, competition, teams, 1, 0)
    apply_match_update(m, home_score=0, away_score=0, status="live",
                       allow_status_reset=True)
    assert (m.home_score, m.away_score) == (0, 0)


def test_abschluss_live_zu_finished_bleibt_frei(db, competition, teams):
    """(83)-Pfad: live -> finished mit (korrigiertem) Endstand不受 Rückschritt-
    Sperre — der Abschluss muss immer ankommen können."""
    m = _live_match(db, competition, teams, 1, 0)
    apply_match_update(m, home_score=0, away_score=0, status="finished",
                       is_live=False)
    assert m.status == "finished"
    assert (m.home_score, m.away_score) == (0, 0)


def test_geplant_erstanlage_unberuehrt(db, competition, teams):
    """Nicht-live-Spiele (Erstanlage/Ergebnis-Lieferung) bleiben frei."""
    m = Match(competition_id=competition.id, matchday=5,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(minutes=55),
              status="scheduled")
    db.session.add(m)
    db.session.flush()
    apply_match_update(m, home_score=0, away_score=0, status="live",
                       is_live=True)
    assert (m.home_score, m.away_score, m.status) == (0, 0, "live")


def test_fd_sync_flackert_nicht_mehr(db, competition, teams, monkeypatch):
    """Integration — exakt der Nutzerfall: OLB hat 1:0 geschrieben, der
    fd-Live-Sync danach liefert noch 0:0 -> der Stand bleibt 1:0."""
    from sync_football_data import _process_football_data

    m = _live_match(db, competition, teams, 1, 0)
    m.external_id = "fd:4712"
    db.session.commit()

    ko = datetime.now(timezone.utc) - timedelta(minutes=55)
    payload = {"matches": [{
        "id": 4712,
        "utcDate": ko.isoformat().replace("+00:00", "Z"),
        "matchday": 5,
        "status": "IN_PLAY",
        "homeTeam": {"id": 1, "name": teams[0].name,
                     "shortName": teams[0].short_name,
                     "tla": teams[0].short_name, "crest": teams[0].logo},
        "awayTeam": {"id": 2, "name": teams[1].name,
                     "shortName": teams[1].short_name,
                     "tla": teams[1].short_name, "crest": teams[1].logo},
        "score": {"fullTime": {"home": 0, "away": 0},
                  "halfTime": {"home": None, "away": None}},
    }]}
    _process_football_data(payload, competition.id, source="live-sync")
    db.session.refresh(m)
    assert m.status == "live"
    assert (m.home_score, m.away_score) == (1, 0)
