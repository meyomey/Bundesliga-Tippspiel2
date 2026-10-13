"""(119) Vorplatzierungs-Pfeile: Referenz = letzter VOLLSTÄNDIGER Spieltag.

Pfeil = Platz jetzt vs. Platz nach dem letzten vollständig abgeschlossenen
Spieltag (dieselbe Quelle wie die Sieger-Ansage (115):
``abgeschlossene_spieltage``). Die Referenz-Rangliste kommt aus
``get_leaderboard(bis_matchday=...)`` — exakt dieselbe Sortierkette inkl.
Sonderpunkte/Tie-Break wie die aktuelle Tabelle, damit Pfeil und Platznummer
nie auseinanderlaufen. Referenz-Zeitpunkt ((120), Nutzerkorrektur): läuft
ein neuerer Spieltag, ist die Referenz der Stand nach dem letzten
vollständigen Spieltag (Bewegung des laufenden ST); liegt der letzte
vollständige Spieltag noch ohne Nachfolger-Ergebnis, bleibt die Bewegung
dieses Spieltags sichtbar (Referenz = Stand nach N−1, wie die TV-Tabelle) —
nicht überall „unverändert".
"""
import pytest
from datetime import datetime

from extensions import db
from models import Match, Prediction, User

from scoring import get_leaderboard
from stats_personal import (vor_spieltag_rangkarte, rang_deltas_berechnen,
                            get_user_trend)


# --------------------------------------------------------------- Aufbauer --

def _spiel(db, comp, teams, md, h_idx, g_idx, h, g):
    m = Match(competition_id=comp.id, matchday=md,
              home_team_id=teams[h_idx].id, away_team_id=teams[g_idx].id,
              kickoff=datetime(2026, 9, 1 + md, 15, 30),
              status="finished", home_score=h, away_score=g)
    db.session.add(m)
    db.session.flush()
    return m


def _offen(db, comp, teams, md, h_idx, g_idx):
    m = Match(competition_id=comp.id, matchday=md,
              home_team_id=teams[h_idx].id, away_team_id=teams[g_idx].id,
              kickoff=datetime(2026, 9, 1 + md, 18, 30),
              status="scheduled")
    db.session.add(m)
    db.session.flush()
    return m


def _tipp(db, u, m, ht, at, pts):
    db.session.add(Prediction(user_id=u.id, match=m,
                              home_tip=ht, away_tip=at, points=pts))


def _zweituser(db):
    u2 = User(username='aaron', email='aaron@example.com',
              full_name='Aaron Zweit')
    u2.set_password('geheim123')
    db.session.add(u2)
    db.session.commit()
    return u2


def _bau_lage(db, competition, teams, user, u2):
    """MD1 + MD2 komplett: U1 führt nach MD1, U2 überholt in MD2.

    Punkte MD1: U1 6 (2× exakt) / U2 3 — Punkte MD2: U1 0 / U2 6 (2× exakt).
    Stand nach MD2: U2 9 (Platz 1) vor U1 6 (Platz 2).
    """
    m1 = _spiel(db, competition, teams, 1, 0, 1, 2, 1)
    m2 = _spiel(db, competition, teams, 1, 2, 3, 1, 1)
    m3 = _spiel(db, competition, teams, 2, 0, 1, 0, 0)
    m4 = _spiel(db, competition, teams, 2, 2, 3, 3, 2)
    _tipp(db, user, m1, 2, 1, 4)   # exakt
    _tipp(db, user, m2, 1, 1, 2)   # exakt
    _tipp(db, user, m3, 1, 1, 0)
    _tipp(db, user, m4, 2, 1, 0)
    _tipp(db, u2, m1, 3, 1, 2)     # Tendenz
    _tipp(db, u2, m2, 2, 1, 1)     # falsch
    _tipp(db, u2, m3, 0, 0, 3)     # exakt
    _tipp(db, u2, m4, 3, 2, 3)     # exakt


@pytest.fixture
def lage(db, competition, teams, user):
    """Zwei vollständige Spieltage, keiner läuft (Zwischen-den-Spieltagen)."""
    u2 = _zweituser(db)
    _bau_lage(db, competition, teams, user, u2)
    db.session.commit()
    return {"comp": competition, "u1": user, "u2": u2}


@pytest.fixture
def lage_laufend(db, competition, teams, user):
    """Wie lage, ABER Spieltag 3 läuft: m5 fertig (U1 +3), m6 offen.

    Live: 9:9 Punkte — U1 Platz 1 (3 Exakte vs. 2). Referenz (Stand nach
    MD2): U2 Platz 1, U1 Platz 2 → U1 ▲1, U2 ▼1.
    """
    u2 = _zweituser(db)
    _bau_lage(db, competition, teams, user, u2)
    m5 = _spiel(db, competition, teams, 3, 0, 1, 1, 0)
    _tipp(db, user, m5, 1, 0, 3)   # exakt
    _offen(db, competition, teams, 3, 2, 3)
    db.session.commit()
    return {"comp": competition, "u1": user, "u2": u2}


def _mit_comp(app, comp, monkeypatch):
    # (118)-Lektion: get_active_competition sonst auf der Seed-BL1!
    monkeypatch.setitem(app.config, "COMPETITION", comp.code)


# --------------------------------------------------- Referenz & Semantik --

def test_referenz_ist_stand_nach_letztem_vollstaendigen_spieltag(
        app, db, lage_laufend, monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    with app.app_context():
        prev_map, ref_md = vor_spieltag_rangkarte()
        assert ref_md == 2
        # Stand nach MD2 (nicht live!): U2 vor U1
        assert prev_map[lage_laufend["u2"].id] == 1
        assert prev_map[lage_laufend["u1"].id] == 2


def test_pfeile_bei_ueberholvorgang(app, db, lage_laufend, monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    with app.app_context():
        deltas, ref_md = rang_deltas_berechnen(get_leaderboard())
        assert ref_md == 2
        d1, d2 = deltas[lage_laufend["u1"].id], deltas[lage_laufend["u2"].id]
        assert d1 == {"delta": 1, "prev_rank": 2}    # ▲1 (live 9:9, mehr Exakte)
        assert d2 == {"delta": -1, "prev_rank": 1}   # ▼1 überholt worden


def test_referenz_friert_waehrend_laufendem_spieltag_ein(
        app, db, lage_laufend, teams, monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    with app.app_context():
        # weiteres MD3-Spiel fertig — Referenz bleibt Stand nach MD2:
        m7 = _spiel(db, lage_laufend["comp"], teams, 3, 1, 2, 0, 0)
        _tipp(db, lage_laufend["u2"], m7, 1, 1, 1)
        db.session.commit()
        _, ref_md = vor_spieltag_rangkarte()
        assert ref_md == 2


def test_abschluss_bewegung_bleibt_sichtbar(app, db, lage_laufend, teams,
                                            monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    with app.app_context():
        # MD3 komplett fertig (letztes Spiel mit U1-Exakttreffer):
        # live U1 12 vor U2 9 — die MD3-Bewegung (U1 ▲1) bleibt sichtbar,
        # statt nach dem Abschluss auf „unverändert" zu fallen ((120)).
        m6 = Match.query.filter_by(competition_id=lage_laufend["comp"].id,
                                   matchday=3, status="scheduled").first()
        m6.status = "finished"
        m6.home_score = 2
        m6.away_score = 2
        _tipp(db, lage_laufend["u1"], m6, 2, 2, 3)
        db.session.commit()
        prev_map, ref_md = vor_spieltag_rangkarte()
        assert ref_md == 2
        deltas, ref_md2 = rang_deltas_berechnen(get_leaderboard())
        assert ref_md2 == 2
        assert deltas[lage_laufend["u1"].id] == {"delta": 1, "prev_rank": 2}
        assert deltas[lage_laufend["u2"].id] == {"delta": -1, "prev_rank": 1}


def test_kein_vollstaendiger_spieltag_keine_pfeile(app, db, competition,
                                                   teams, user, monkeypatch):
    _mit_comp(app, competition, monkeypatch)
    with app.app_context():
        m1 = _spiel(db, competition, teams, 1, 0, 1, 2, 1)
        _offen(db, competition, teams, 1, 2, 3)
        _tipp(db, user, m1, 2, 1, 4)
        db.session.commit()
        assert vor_spieltag_rangkarte() == (None, None)
        assert rang_deltas_berechnen(get_leaderboard()) == ({}, None)


def test_zwischen_den_spieltagen_zeigt_bewegung_des_letzten_st(
        app, db, lage, monkeypatch):
    _mit_comp(app, lage["comp"], monkeypatch)
    with app.app_context():
        # MD1+MD2 fertig, MD3 nicht gestartet: die MD2-Bewegung (U2 überholt
        # U1) bleibt sichtbar — Referenz = Stand nach MD1 ((120), Nutzer-
        # korrektur: nicht überall „unverändert" zeigen).
        prev_map, ref_md = vor_spieltag_rangkarte()
        assert ref_md == 1
        deltas, _ = rang_deltas_berechnen(get_leaderboard())
        assert deltas[lage["u1"].id] == {"delta": -1, "prev_rank": 1}
        assert deltas[lage["u2"].id] == {"delta": 1, "prev_rank": 2}


def test_nur_ein_spieltag_fertig_keine_pfeile(app, db, competition, teams,
                                              user, monkeypatch):
    _mit_comp(app, competition, monkeypatch)
    with app.app_context():
        # nur MD1 fertig, kein neueres Ergebnis: davor gibt es nichts
        # Vergleichbares → gar keine Pfeile.
        m1 = _spiel(db, competition, teams, 1, 0, 1, 2, 1)
        _tipp(db, user, m1, 2, 1, 4)
        db.session.commit()
        assert vor_spieltag_rangkarte() == (None, None)
        assert rang_deltas_berechnen(get_leaderboard()) == ({}, None)


def test_sortierkette_identisch_inkl_tiebreak(app, db, competition, teams,
                                              user, monkeypatch):
    _mit_comp(app, competition, monkeypatch)
    u2 = _zweituser(db)
    with app.app_context():
        m1 = _spiel(db, competition, teams, 1, 0, 1, 2, 1)
        m2 = _spiel(db, competition, teams, 1, 2, 3, 1, 1)
        # Punktgleichheit 6:6 — U1 mit 2 Exakten, U2 ohne Exaktheit:
        _tipp(db, user, m1, 2, 1, 3)
        _tipp(db, user, m2, 1, 1, 3)
        _tipp(db, u2, m1, 3, 1, 3)
        _tipp(db, u2, m2, 2, 1, 3)
        db.session.commit()
        live = get_leaderboard()
        assert [r["user"].id for r in live] == [user.id, u2.id]
        # erstes MD2-Ergebnis (ohne Tipps) → laufender ST → Referenz = MD1:
        _offen(db, competition, teams, 2, 0, 1)
        _spiel(db, competition, teams, 2, 2, 3, 1, 1)
        prev_map, ref_md = vor_spieltag_rangkarte()
        assert ref_md == 1
        # Referenz nutzt DIESELBE Kette (Exact-Tie-Break), nicht Username:
        assert prev_map[user.id] == 1 and prev_map[u2.id] == 2


def test_bis_matchday_filtert_spieltage(app, db, lage, monkeypatch):
    _mit_comp(app, lage["comp"], monkeypatch)
    with app.app_context():
        rows1 = get_leaderboard(bis_matchday=1)
        je = {r["user"].id: r for r in rows1}
        assert je[lage["u1"].id]["points"] == 6
        assert je[lage["u2"].id]["points"] == 3
        assert je[lage["u1"].id]["rank"] == 1
        rows2 = get_leaderboard(bis_matchday=2)
        je2 = {r["user"].id: r for r in rows2}
        assert je2[lage["u2"].id]["points"] == 9
        assert je2[lage["u2"].id]["rank"] == 1


# ------------------------------------------------------------- Seiten -----

def test_tabelle_zeigt_pfeile(auth_client, app, db, lage_laufend,
                              monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    resp = auth_client.get("/tabelle")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "lb-trend up" in html and "▲" in html
    assert "lb-trend down" in html and "▼" in html
    assert "nach Spieltag 2" in html


def test_dashboard_top10_zeigt_pfeile(auth_client, app, db, lage_laufend,
                                      monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    resp = auth_client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "lb-trend up" in html and "▲ 1" in html
    assert "lb-trend down" in html and "▼ 1" in html
    assert "nach Spieltag 2" in html


def test_stats_trend_delta_gleiche_referenz(app, db, lage_laufend,
                                            monkeypatch):
    _mit_comp(app, lage_laufend["comp"], monkeypatch)
    with app.app_context():
        t1 = get_user_trend(lage_laufend["u1"].id)
        t2 = get_user_trend(lage_laufend["u2"].id)
        assert t1["previous_rank"] == 2 and t1["delta"] == 1
        assert t2["previous_rank"] == 1 and t2["delta"] == -1
