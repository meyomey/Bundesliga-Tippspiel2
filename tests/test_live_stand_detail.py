"""(137) Live-Stand im Spieldetail: laufende Spiele zeigen den aktuellen
Stand gross in der Mitte — vorher stand dort nur „Dein Tipp X:Y" (Branch
„sonst" = live), während das Live-Center korrekt 0:1 zeigte. Ohne Feed-Score
(Boost noch nicht gelaufen) bleibt die Darstellung unverändert.
"""
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Match, Prediction


def _login(client, user):
    client.post("/auth/login", data={"email": user.email, "password": "admin123"},
                follow_redirects=True)


def _use_test_comp(client):
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"


def _live_match(db, competition, teams, home_score=0, away_score=1):
    m = Match(competition_id=competition.id, matchday=6,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) - timedelta(minutes=38),
              status="live", home_score=home_score, away_score=away_score)
    db.session.add(m)
    db.session.commit()
    return m


def test_live_spiel_zeigt_stand_und_tipp_137(client, db, admin_user,
                                             competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    m = _live_match(db, competition, teams)
    db.session.add(Prediction(user_id=admin_user.id, match_id=m.id,
                              home_tip=2, away_tip=1, joker=True))
    db.session.commit()
    html = client.get(f"/match/{m.id}?embed=1").get_data(as_text=True)
    assert "Live-Stand" in html
    assert "0 : 1" in html                      # aktueller Stand, gross
    assert "2 : 1" in html                      # eigener Tipp daneben (klein)
    assert "status-live" in html                # LIVE-Badge bleibt


def test_live_ohne_feed_score_faellt_auf_altes_verhalten_137(client, db,
                                                             admin_user,
                                                             competition,
                                                             teams):
    _login(client, admin_user)
    _use_test_comp(client)
    m = _live_match(db, competition, teams, home_score=None, away_score=None)
    html = client.get(f"/match/{m.id}?embed=1").get_data(as_text=True)
    assert "Live-Stand" not in html
    assert "None" not in html                   # kein rohes None im Markup


def test_fertig_und_offen_unveraendert_137(client, db, admin_user,
                                           competition, teams):
    _login(client, admin_user)
    _use_test_comp(client)
    fertig = Match(competition_id=competition.id, matchday=5,
                   home_team_id=teams[0].id, away_team_id=teams[1].id,
                   kickoff=datetime.now(timezone.utc) - timedelta(days=7),
                   status="finished", home_score=3, away_score=2)
    db.session.add(fertig)
    db.session.commit()
    html = client.get(f"/match/{fertig.id}?embed=1").get_data(as_text=True)
    assert "tu-result-score" in html and "Live-Stand" not in html
    assert "3 : 2" in html


def test_live_note_css_vorhanden_137():
    css = open("static/css/style.css", encoding="utf-8").read()
    assert ".tu-live-note" in css


def test_live_poll_im_detail_139():
    """(139) Laufende Spiele aktualisieren den Stand alle 30 s aus
    /api/matches/<ST> (read-only) und laden nach dem Abpfiff einmal neu."""
    js = open("static/js/match_detail.js", encoding="utf-8").read()
    assert "/api/matches/' + area.dataset.matchday" in js
    assert "data.status !== 'live'" in js or "dataset.status !== 'live'" in js
    assert "tuLiveScore" in js and "tuLiveNote" in js
    assert "30000" in js
    assert "location.reload()" in js
    t = open("templates/match_detail.html", encoding="utf-8").read()
    assert 'data-status="{{ match.status }}"' in t
    assert 'data-matchday="{{ match.matchday }}"' in t


def test_quellen_fussnote_tsdb_139():
    """(139) Karten- und Auswechslungs-Sektion nennen TheSportsDB als Quelle."""
    t = open("templates/match_detail.html", encoding="utf-8").read()
    assert t.count("TheSportsDB / API-Football") == 2


def test_tsdb_und_olb_events_im_admin_protokoll_139():
    """(139) Beide neuen Cron-Boosts sind im Admin sichtbar + protokollieren."""
    from datasource_activity import SOURCES
    keys = {k for k, _label in SOURCES}
    assert "tsdb_events" in keys and "olb-events" in keys
    src = open("tsdb_events.py", encoding="utf-8").read()
    assert 'record("tsdb_events"' in src
    src2 = open("sync_openligadb.py", encoding="utf-8").read()
    assert 'record("olb-events"' in src2


def test_live_block_traegt_poll_ids_140():
    """(140) Regression „Live-Stand doppelt": Serverblock und Poll-JS teilen
    dieselben IDs — der Poll findet den gerenderten Block und baut nie einen
    zweiten (Nutzer-Screenshot 18.10., Gladbach-Hoffenheim)."""
    t = open("templates/match_detail.html", encoding="utf-8").read()
    assert 'id="tuLiveScore">{{ match.home_score }} : {{ match.away_score }}</div>' in t
    assert 'id="tuLiveNote"' in t
    # Genau EIN Serverblock (kein zweiter Render mehr nötig)
    assert t.count('id="tuLiveScore"') == 1
    js = open("static/js/match_detail.js", encoding="utf-8").read()
    # Upsert reuse zuerst, Erzeugen nur im Fall !score
    assert "document.getElementById('tuLiveScore')" in js
    assert "if (!score)" in js


def test_live_stand_rot_wie_live_seite_141():
    """(141) Der Live-Stand im Detail traegt dasselbe Rot (var(--danger))
    wie der Stand auf der Live-Seite (.lm-score bei status-live)."""
    t = open("templates/match_detail.html", encoding="utf-8").read()
    assert 'class="tu-result-score tu-live-score" id="tuLiveScore"' in t
    js = open("static/js/match_detail.js", encoding="utf-8").read()
    assert "tu-result-score tu-live-score" in js
    css = open("static/css/style.css", encoding="utf-8").read()
    assert ".tu-result-score.tu-live-score { color: var(--danger); }" in css
    # Endstand-Zweig bleibt Primarfarbe (keine Live-Klasse)
    assert css.count(".tu-result-score.tu-live-score") == 1


def test_embed_ohne_topbar_platzhalter_142():
    """(142) Regression „leerer Bereich oben im Popup": die globale
    body-Padding-Kompensation fuer die fixe Navbar gilt nicht im Embed
    (dort gibt es keine Navbar) — auch das mobile Bottom-Polster nicht."""
    css = open("static/css/style.css", encoding="utf-8").read()
    assert "body.embed-mode {\n  padding-top: 0 !important;\n}" in css
    assert "body.embed-mode.match-detail-page {\n  padding-bottom: 0 !important;\n}" in css
