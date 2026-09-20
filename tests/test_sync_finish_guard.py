"""Regressionstests zum FINISHED-Sanity-Gate ((83), Produktionsfall 20.09.

football-data.org meldete laufende Spiele als "FINISHED" (0:0) - blind
uebernommen zeigte die App "ENDE" waehrend das Spiel lief, und die Status-
Monotonie machte das unheilbar. Neu: FINISHED unterhalb der Mindestdauer
(105 min) wird abgewiesen, ein falsch-fertig geglaubtes 0:0 mit OLB-
Gegenprobe zurueckgenommen, und der OLB-Nachzug korrigiert vorzeitige 0:0
mit dem echten Endstand. Ohne eindeutige OLB-Lage wird nie gehandelt.
"""
from datetime import datetime, timedelta, timezone

import pytest
import requests

from extensions import db
from models import Match
from sync_football_data import FINISH_SANITY_MIN, _process_football_data
from sync_openligadb import _fill_missing_from_openligadb, _olb_group_order_id


# ------------------------------------------------------------- Helfer

def _fd_payload(match_id, matchday, home, away, status,
                home_score=None, away_score=None, kickoff=None):
    kickoff = kickoff or (datetime.now(timezone.utc) - timedelta(days=1))
    return {
        'matches': [{
            'id': match_id,
            'utcDate': kickoff.isoformat().replace('+00:00', 'Z'),
            'matchday': matchday,
            'status': status,
            'homeTeam': {'id': 1, 'name': home.name, 'shortName': home.short_name,
                         'tla': home.short_name, 'crest': home.logo},
            'awayTeam': {'id': 2, 'name': away.name, 'shortName': away.short_name,
                         'tla': away.short_name, 'crest': away.logo},
            'score': {'fullTime': {'home': home_score, 'away': away_score},
                      'halfTime': {'home': None, 'away': None}},
        }]
    }


def _make_match(db, competition, teams, *, ext_id, status, kickoff_delta,
                home_score=None, away_score=None, is_live=False):
    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + kickoff_delta,
              status=status, home_score=home_score, away_score=away_score,
              external_id=ext_id, is_live=is_live)
    db.session.add(m)
    db.session.commit()
    return m


def _olb_md(match_id, heim_name, gast_name, kickoff_dt, fertig,
            endstand=None):
    daten = {
        'matchID': match_id,
        'team1': {'teamName': heim_name},
        'team2': {'teamName': gast_name},
        'matchDateTimeUTC': kickoff_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'matchIsFinished': fertig,
        'matchResults': [],
        'group': {'groupOrderID': 1},
    }
    if fertig and endstand:
        daten['matchResults'] = [{'resultTypeID': 2,
                                  'pointsTeam1': endstand[0],
                                  'pointsTeam2': endstand[1]}]
    return daten


def _mock_olb(monkeypatch, eintraege_oder_fehler):
    """OLB-HTTP fakeen; None/Exception = unklar (Netzwerk weg)."""
    def faux_get(url, timeout=None, **k):
        if 'openligadb' in url:
            if eintraege_oder_fehler is None:
                raise RuntimeError('OLB unklar (Test)')
            class R:
                status_code = 200
                def json(self):
                    return eintraege_oder_fehler
            return R()
        raise RuntimeError('unerwartete URL (Test): ' + url)
    monkeypatch.setattr(requests, 'get', faux_get)


# ------------------------------------------------------------- Gate

def test_vorzeitiges_fd_finished_wird_live_statt_ennde(db, competition, teams):
    """Spiel laeuft 30 Minuten, fd meldet FINISHED 0:0 -> live statt ENDE."""
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    _make_match(db, competition, teams, ext_id='fd:601', status='live',
                kickoff_delta=timedelta(minutes=-30), home_score=0,
                away_score=0, is_live=True)
    data = _fd_payload(601, 1, teams[0], teams[1], 'FINISHED',
                       home_score=0, away_score=0, kickoff=kickoff)
    res = _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:601').first()
    assert m.status == 'live' and m.is_live is True
    assert m.live_phase is None          # "FINISHED" darf nicht Phase werden
    assert res['finish_vorzeitig'] == 1
    assert res['finish_zurueckgenommen'] == 0


def test_vorzeitiges_finished_vor_anstoss_bleibt_geplant(db, competition, teams):
    """FINISHED fuer ein noch nicht angepfiffenes Spiel wird ignoriert."""
    kickoff = datetime.now(timezone.utc) + timedelta(hours=2)
    _make_match(db, competition, teams, ext_id='fd:602', status='scheduled',
                kickoff_delta=timedelta(hours=2))
    data = _fd_payload(602, 1, teams[0], teams[1], 'FINISHED',
                       home_score=0, away_score=0, kickoff=kickoff)
    _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:602').first()
    assert m.status == 'scheduled'


def test_fd_finished_nach_mindestdauer_gilt_weiter(db, competition, teams, user):
    """Nach 105+ Minuten ist FINISHED plausibel: Regelfall unangetastet."""
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=110)
    _make_match(db, competition, teams, ext_id='fd:603', status='live',
                kickoff_delta=timedelta(minutes=-110), home_score=2,
                away_score=1, is_live=True)
    data = _fd_payload(603, 1, teams[0], teams[1], 'FINISHED',
                       home_score=2, away_score=1, kickoff=kickoff)
    res = _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:603').first()
    assert m.status == 'finished' and m.is_live is False
    assert (m.home_score, m.away_score) == (2, 1)
    assert res['finish_vorzeitig'] == 0


def test_falsch_fertig_0_0_wird_mit_olb_zurueckgenommen(db, competition, teams, monkeypatch):
    """Bereits falsch geglaubtes 0:0 (Produktionsfall): OLB belegt laufend
    -> Ruecknahme auf live (allow_status_reset), sonst unheilbar."""
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=60)
    _make_match(db, competition, teams, ext_id='fd:604', status='finished',
                kickoff_delta=timedelta(minutes=-60), home_score=0,
                away_score=0)
    _mock_olb(monkeypatch, [_olb_md(83191, 'FC Bayern München',
                                    'Borussia Dortmund', kickoff, fertig=False)])
    data = _fd_payload(604, 1, teams[0], teams[1], 'FINISHED',
                       home_score=0, away_score=0, kickoff=kickoff)
    res = _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:604').first()
    assert m.status == 'live' and m.is_live is True
    assert res['finish_zurueckgenommen'] == 1


def test_olb_unklar_niemals_handeln(db, competition, teams, monkeypatch):
    """OLB nicht erreichbar -> keine Ruecknahme, Zustand bleibt stabil."""
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=60)
    _make_match(db, competition, teams, ext_id='fd:605', status='finished',
                kickoff_delta=timedelta(minutes=-60), home_score=0,
                away_score=0)
    _mock_olb(monkeypatch, None)
    data = _fd_payload(605, 1, teams[0], teams[1], 'FINISHED',
                       home_score=0, away_score=0, kickoff=kickoff)
    _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:605').first()
    assert m.status == 'finished'       # unklar -> nie handeln


# ------------------------------------------------------------- OLB-Heilung

def test_olb_endstand_korrigiert_falsches_0_0(db, competition, teams, monkeypatch):
    """Nachtraegliche Heilung: echter OLB-Endstand ueberschreibt das
    vorzeitige 0:0 (finished->finished Score-Korrektur)."""
    kickoff = datetime.now(timezone.utc) - timedelta(hours=3)
    _make_match(db, competition, teams, ext_id='oldb:83191', status='finished',
                kickoff_delta=timedelta(hours=-3), home_score=0, away_score=0)
    _mock_olb(monkeypatch, [_olb_md(83191, 'FC Bayern München',
                                    'Borussia Dortmund', kickoff, fertig=True,
                                    endstand=(3, 2))])
    gefuellt = _fill_missing_from_openligadb()
    m = Match.query.filter_by(external_id='oldb:83191').first()
    assert gefuellt >= 1
    assert m.status == 'finished'
    assert (m.home_score, m.away_score) == (3, 2)


def test_legitimes_0_0_endstand_bleibt_unangetastet(db, competition, teams, monkeypatch):
    """Echtes 0:0 (OLB-Endstand 0:0) wird NICHT 'korrigiert'."""
    kickoff = datetime.now(timezone.utc) - timedelta(hours=3)
    _make_match(db, competition, teams, ext_id='oldb:83192', status='finished',
                kickoff_delta=timedelta(hours=-3), home_score=0, away_score=0)
    _mock_olb(monkeypatch, [_olb_md(83192, 'FC Bayern München',
                                    'Borussia Dortmund', kickoff, fertig=True,
                                    endstand=(0, 0))])
    _fill_missing_from_openligadb()
    m = Match.query.filter_by(external_id='oldb:83192').first()
    assert (m.home_score, m.away_score) == (0, 0)


# ------------------------------------------------------------- OLB-Format

def test_olb_gruppenfeld_flat_und_verschachtelt():
    """OpenLigaDB liefert das Gruppenfeld je nach Endpunkt flach oder
    verschachtelt - beides muss lesbar sein (Fallback: default)."""
    assert _olb_group_order_id({'group': {'groupOrderID': 4}}, default=1) == 4
    assert _olb_group_order_id({'groupOrderID': 7}, default=1) == 7
    assert _olb_group_order_id({}, default=1) == 1


# ------------------------------------------- Produktionsfall 20.09. (2:0)

def test_haengendes_finished_2_0_wird_zurueckgenommen(db, competition, teams, monkeypatch):
    """EXAKTER Produktionsfall: der Live-Boost hatte das falsche 0:0 schon
    auf 2:0 geheilt, nur der Status hing auf finished - auch dieser Zustand
    wird mit OLB-Gegenprobe auf live zurueckgenommen (Score egal)."""
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=64)
    _make_match(db, competition, teams, ext_id='fd:606', status='finished',
                kickoff_delta=timedelta(minutes=-64), home_score=2,
                away_score=0)
    _mock_olb(monkeypatch, [_olb_md(83191, 'FC Bayern München',
                                    'Borussia Dortmund', kickoff, fertig=False)])
    data = _fd_payload(606, 1, teams[0], teams[1], 'FINISHED',
                       home_score=2, away_score=0, kickoff=kickoff)
    res = _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:606').first()
    assert m.status == 'live' and m.is_live is True
    assert (m.home_score, m.away_score) == (2, 0)   # Score unangetastet
    assert res['finish_zurueckgenommen'] == 1


def test_fd_in_play_heilt_haengendes_finished(db, competition, teams, monkeypatch):
    """Meldet die Quelle IN_PLAY (statt FINISHED), heilt die OLB-Gegenprobe
    das haengende finished trotzdem (gleicher Lauf)."""
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=50)
    _make_match(db, competition, teams, ext_id='fd:607', status='finished',
                kickoff_delta=timedelta(minutes=-50), home_score=2,
                away_score=0)
    _mock_olb(monkeypatch, [_olb_md(83191, 'FC Bayern München',
                                    'Borussia Dortmund', kickoff, fertig=False)])
    data = _fd_payload(607, 1, teams[0], teams[1], 'IN_PLAY',
                       kickoff=kickoff)
    _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:607').first()
    assert m.status == 'live' and m.live_phase == 'IN_PLAY'


def test_olb_team_map_deckt_aufsteiger_ab():
    """Die OLB-Namenskarte muss die 2026/27-Aufsteiger enthalten, sonst
    bleibt die Gegenprobe fuer genau diese Teams stumm."""
    from sync_shared import _OLB_TEAM_MAP
    assert _OLB_TEAM_MAP.get('SC Paderborn 07') == 'SCP'
    assert _OLB_TEAM_MAP.get('SV 07 Elversberg') == 'ELV'
