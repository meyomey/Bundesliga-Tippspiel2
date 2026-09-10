"""Regressionstests: LIVE-Spielminute mit Feed-Vorrang + strukturierter Uhr.

Hintergrund (Nutzerfeedback 02.09. + 06.09.2026):
Alt 1: die Minute wurde blind ab Anstoss hochgezahlt (Halbzeit lief weiter,
nach 90 blieb sie kleben) -> "nicht zu gebrauchen".
Alt 2 (Zwischenstand vom 02.09.): nur noch echte Feed-Minuten anzeigen ->
da das football-data-FREE-Tier die Minute haeufig nicht liefert, stand bei
laufenden Spielen gar keine Minute mehr da -> zu karg.
Neu: live_clock_for() priorisiert verbindliche Feed-Daten (minute, Phase
PAUSED = Halbzeit). Liefert der Feed nichts, zaehlt eine strukturierte Uhr
ab Anstoss (45' erste Halbzeit, 15' Pause mit stillstehender Uhr, zweite
Halbzeit, danach Stille) - in UI als Naeherung mit '≈' gekennzeichnet.
"""
from datetime import datetime, timedelta, timezone

from models import Match
from routes_api import live_clock_for
from sync import _process_football_data


def _fd_payload(match_id, home, away, *, status, minute=None, utc_date,
                 home_score=None, away_score=None, matchday=1):
    md = {
        'id': match_id,
        'utcDate': utc_date.isoformat().replace('+00:00', 'Z'),
        'matchday': matchday,
        'status': status,
        'homeTeam': {'id': 1, 'name': home.name, 'shortName': home.short_name,
                     'tla': home.short_name, 'crest': home.logo},
        'awayTeam': {'id': 2, 'name': away.name, 'shortName': away.short_name,
                     'tla': away.short_name, 'crest': away.logo},
        'score': {'fullTime': {'home': home_score, 'away': away_score},
                  'halfTime': {'home': None, 'away': None}},
    }
    if minute is not None:
        md['minute'] = minute
    return {'matches': [md]}


# ------------------------------------------------------- Sync: Feed -> DB --

def test_sync_uebernimmt_echte_minute_und_pausiert_sie(db, competition, teams):
    """IN_PLAY liefert echte Minute; PAUSED (Halbzeit) haelt die letzte Minute,
    setzt aber die Phase; FINISHED raumt die Live-Phase auf."""
    ko = datetime.now(timezone.utc) - timedelta(minutes=40)

    data = _fd_payload(900, teams[0], teams[1], status='IN_PLAY', minute=34,
                       utc_date=ko, home_score=1, away_score=0)
    _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:900').one()
    assert m.status == 'live'
    assert m.minute == 34
    assert m.live_phase == 'IN_PLAY'

    data = _fd_payload(900, teams[0], teams[1], status='PAUSED',
                       utc_date=ko, home_score=1, away_score=0)
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.status == 'live'
    assert m.live_phase == 'PAUSED'
    assert m.minute == 34

    data = _fd_payload(900, teams[0], teams[1], status='IN_PLAY', minute=56,
                       utc_date=ko, home_score=2, away_score=0)
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.live_phase == 'IN_PLAY'
    assert m.minute == 56

    data = _fd_payload(900, teams[0], teams[1], status='FINISHED', minute=90,
                       utc_date=ko, home_score=2, away_score=1)
    _process_football_data(data, competition.id, source='live-sync')
    db.session.refresh(m)
    assert m.status == 'finished'
    assert m.live_phase is None


def test_sync_sanft_ohne_minutenfeld(db, competition, teams):
    """Ohne minute-Feld im Feed bleibt Match.minute leer (UI schaltet dann
    auf die gekennzeichnete Struktur-Uhr) - der Sync erfindet nichts."""
    ko = datetime.now(timezone.utc) - timedelta(minutes=20)
    data = _fd_payload(901, teams[0], teams[1], status='IN_PLAY', utc_date=ko)
    _process_football_data(data, competition.id, source='live-sync')
    m = Match.query.filter_by(external_id='fd:901').one()
    assert m.status == 'live'
    assert m.minute is None
    assert m.live_phase == 'IN_PLAY'


# ------------------------------------------------ live_clock_for: Logik ----

def _match(**kw):
    defaults = dict(status='live', kickoff=datetime(2026, 9, 6, 13, 30, tzinfo=timezone.utc))
    defaults.update(kw)
    return Match(**defaults)


def test_live_clock_feed_werte_haben_vorrang():
    now = datetime(2026, 9, 6, 13, 53, tzinfo=timezone.utc)
    m = _match(minute=37, live_phase='IN_PLAY')
    lc = live_clock_for(m, now)
    assert lc['minute'] == 37
    assert lc['derived'] is False
    assert lc['halftime'] is None


def test_live_clock_pause_laut_feed_ist_verbindlich():
    """Feed meldet Halbzeit -> kein Minuten gezael, Label 'feed'-Pause -
    auch wenn die Anstossuhr schon weiter waere."""
    now = datetime(2026, 9, 6, 14, 30, tzinfo=timezone.utc)  # 60 min nach Anstoss
    m = _match(minute=45, live_phase='PAUSED')
    lc = live_clock_for(m, now)
    assert lc['minute'] is None
    assert lc['halftime'] == 'feed'


def test_live_clock_strukturierte_uhr_respektiert_halbzeit():
    ko = datetime(2026, 9, 6, 13, 30, tzinfo=timezone.utc)

    def clock(offset_min):
        return live_clock_for(_match(kickoff=ko), ko + timedelta(minutes=offset_min))

    assert clock(10) == {'minute': 11, 'derived': True, 'halftime': None, 'overtime': False}
    assert clock(44) == {'minute': 45, 'derived': True, 'halftime': None, 'overtime': False}
    # Halbzeitfenster: Uhr steht still, KEINE laufende Minute
    assert clock(52) == {'minute': None, 'derived': True, 'halftime': 'derived', 'overtime': False}
    # 2. Halbzeit: 15 Min Pause abgezogen (63. Minute ab Anstoss -> 48. Spielminute)
    assert clock(63) == {'minute': 49, 'derived': True, 'halftime': None, 'overtime': False}
    # Nach 90 nur noch '90+'-Hinweis
    late = clock(106)
    assert late['minute'] == 90 and late['overtime'] is True
    # Und danach: Stille statt Falschanzeige
    assert clock(120) == {'minute': None, 'derived': False, 'halftime': None, 'overtime': False}
    # Vor dem Anstoss erst recht nicht
    assert clock(-5) == {'minute': None, 'derived': False, 'halftime': None, 'overtime': False}


# --------------------------------------------------------- Seite & API -----

def _login_client(client, user, competition):
    client.post('/auth/login', data={'email': user.email, 'password': 'testpass123'},
                follow_redirects=True)
    with client.session_transaction() as sess:
        sess['competition_code'] = competition.code


def test_live_center_leitet_minute_ab_wenn_feed_schweigt(client, db, user, competition, teams, monkeypatch, app):
    """Free-Tier ohne Feed-Minute: UI zeigt gekennzeichnete Naeherung '≈ X. Min'
    statt gar keiner Anzeige - aber nie eine blinde Stoppuhr."""
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('routes_api.fetch_live_match_updates',
                        lambda matchday=None: {'ok': True, 'updated': 0, 'live': 1})
    m = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=23),
        status='live', home_score=0, away_score=0,
    )
    db.session.add(m)
    db.session.commit()
    _login_client(client, user, competition)

    page = client.get('/live')
    assert page.status_code == 200
    assert '≈ 24. Min'.encode('utf-8') in page.data
    assert b'status-live" data-kickoff' not in page.data

    api = client.get('/api/live/center')
    row = api.get_json()['matches'][0]
    assert row['minute'] == 24
    assert row['minute_derived'] is True
    assert row['halftime'] is None


def test_live_center_zeigt_halbzeitpause(client, db, user, competition, teams, monkeypatch, app):
    """Halbzeit laut Feed: Badge 'Halbzeitpause', API minute=None +
    halftime='feed' - obwohl die Anstossuhr laengst weitergeklimmt haette."""
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('routes_api.fetch_live_match_updates',
                        lambda matchday=None: {'ok': True, 'updated': 0, 'live': 1})
    m = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=52),
        status='live', home_score=1, away_score=0, minute=45,
        live_phase='PAUSED',
    )
    db.session.add(m)
    db.session.commit()
    _login_client(client, user, competition)

    page = client.get('/live')
    assert 'Halbzeitpause'.encode('utf-8') in page.data
    assert b'45. Min' not in page.data

    api = client.get('/api/live/center')
    row = api.get_json()['matches'][0]
    assert row['minute'] is None
    assert row['halftime'] == 'feed'
    assert row['live_phase'] == 'PAUSED'


def test_live_center_abgeleitete_halbzeit_ohne_feedphase(client, db, user, competition, teams, monkeypatch, app):
    """Feed schweigt komplett, Anstoss vor 52 Min: UI zeigt 'Halbzeit ≈'
    statt einer weiterlaufenden 53. Minute."""
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)
    monkeypatch.setattr('routes_api.fetch_live_match_updates',
                        lambda matchday=None: {'ok': True, 'updated': 0, 'live': 1})
    m = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=52),
        status='live', home_score=1, away_score=0,
    )
    db.session.add(m)
    db.session.commit()
    _login_client(client, user, competition)

    page = client.get('/live')
    assert 'Halbzeit ≈'.encode('utf-8') in page.data
    assert b'. Min' not in page.data

    api = client.get('/api/live/center')
    row = api.get_json()['matches'][0]
    assert row['minute'] is None
    assert row['halftime'] == 'derived'


def test_livejs_und_template_ohne_blinde_stoppuhr():
    """Quelltext-Guard: die blinde Client-Stoppuhr ist raus; live.js nutzt
    die API-Felder minute/minute_derived/halftime."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    js = (root / 'static' / 'js' / 'live.js').read_text(encoding='utf-8')
    assert 'estimateInitialLiveMinutes' not in js
    assert 'Math.min(90' not in js
    assert 'minute_derived' in js and 'halftime' in js
    html = (root / 'templates' / 'live.html').read_text(encoding='utf-8')
    assert 'data-kickoff' not in html
    assert 'Halbzeit' in html
