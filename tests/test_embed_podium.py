# -*- coding: utf-8 -*-
"""(169) Einbettungs-Widget /embed/podium — öffentlich, iframe-fähig,
dasselbe Podium wie die Landingpage (Partial _lp_podium.html, keine
Parallel-Systeme). Anlass: Nutzer möchte die Rangliste responsive auf
seiner Vereins-Website einbetten (tipp.wulmstorf.net)."""

import pytest


@pytest.fixture()
def podium_seed(db, competition, teams, user):
    """Ein beendetes Spiel (2:1) + exakter Tipp des Users -> 4 Punkte,
    damit get_leaderboard eine Zeile mit points > 0 liefert. Wichtig:
    das Spiel muss auf der AKTIVEN Competition liegen (get_active_competition
    — im BL1-Conftest ist das comp 1), sonst filtert get_leaderboard den
    Tipp weg (Kompetition-Filter) und das Podium bleibt leer."""
    from datetime import datetime, timedelta, timezone as tz
    from models import Match, Prediction
    from cache import cache as _cache
    from competition_helpers import get_active_competition

    _cache.clear()
    comp = get_active_competition()
    m = Match(competition_id=(comp.id if comp else competition.id), matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(tz.utc) - timedelta(days=3),
              status="finished", home_score=2, away_score=1)
    db.session.add(m)
    db.session.flush()
    db.session.add(Prediction(user_id=user.id, match_id=m.id,
                              home_tip=2, away_tip=1, points=4))
    db.session.commit()
    return m


def test_embed_podium_oeffentlich_und_podium_169(client, podium_seed, user):
    """Ohne Login erreichbar; zeigt Überschrift + Podium mit dem Spieler
    (dasselbe Partial wie die Landingpage)."""
    resp = client.get("/embed/podium")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "Wer führt die Liga an?" in body
    assert "lp-podium-card" in body
    assert user.username.encode("utf-8") in resp.data


def test_embed_podium_leer_fall_harmlos_169(client, db):
    """Ohne Punkte keine Ausnahme, sondern freundlicher Leer-Hinweis."""
    from cache import cache as _cache
    _cache.clear()
    resp = client.get("/embed/podium")
    assert resp.status_code == 200
    assert "Noch keine Punkte" in resp.data.decode("utf-8")
    assert "lp-podium-card" not in resp.data.decode("utf-8")


def test_embed_podium_iframe_header_169(app, client, podium_seed):
    """(169) Kern des Features: /embed/ darf auf FREMDEN Seiten eingebettet
    werden — X-Frame-Options ist dort weg, stattdessen CSP frame-ancestors *,
    plus no-store (immer aktuelle Punkte). Alle anderen Pfade behalten
    SAMEORIGIN (Schutz bleibt unangetastet)."""
    r = client.get("/embed/podium")
    assert "X-Frame-Options" not in r.headers
    assert r.headers.get("Content-Security-Policy") == "frame-ancestors *"
    assert "no-store" in r.headers.get("Cache-Control", "")

    r_start = client.get("/")
    assert r_start.headers.get("X-Frame-Options") == "SAMEORIGIN"


def test_landing_nutzt_gleiche_partial_basis_169(client, podium_seed, user):
    """Kein Parallel-System: die Landingpage rendert weiter dasselbe Podium
    (nach dem Partial-Extract von (169)) — Überschrift + Karten vorhanden."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "lp-podium-card" in body
    assert user.username.encode("utf-8") in resp.data


def test_embed_theme_default_dunkel_170(client, podium_seed):
    """(170) Ohne Parameter bleibt das Widget dunkel (App-Default-Look)."""
    body = client.get("/embed/podium").data.decode("utf-8")
    assert 'data-emb-theme="dunkel"' in body
    assert 'data-theme="light"' not in body


def test_embed_theme_hell_170(client, podium_seed):
    """(170) ?theme=hell aktiviert den vorhandenen [data-theme="light"]-
    Block aus style.css — keine zweiten Farbwerte im Projekt."""
    body = client.get("/embed/podium?theme=hell").data.decode("utf-8")
    assert 'data-emb-theme="hell"' in body
    assert 'data-theme="light"' in body


def test_embed_theme_auto_170(client, podium_seed):
    """(170) ?theme=auto entscheidet per matchMedia im Besucher-Browser —
    serverseitig wird nichts fest verdrahtet."""
    body = client.get("/embed/podium?theme=auto").data.decode("utf-8")
    assert "matchMedia" in body and "prefers-color-scheme" in body
    # Am <html>-Tag wird nichts fest genagelt (der Besucher-Browser entscheidet):
    assert '<html lang="de" data-emb-theme="auto" data-theme="light">' not in body


def test_embed_theme_unbekannt_faellt_auf_dunkel_170(client, podium_seed):
    """(170) Unsinnige theme-Werte werden still auf dunkel zurückgesetzt."""
    body = client.get("/embed/podium?theme=quatsch").data.decode("utf-8")
    assert 'data-emb-theme="dunkel"' in body
    assert 'data-theme="light"' not in body


def test_embed_auto_hoehe_postmessage_171(client, podium_seed):
    """(171) Das Widget meldet seine Hoehe per postMessage an den
    iFrame-Rahmen (ResizeObserver + load/resize) — der Rahmen passt die
    Hoehe an, nichts wird abgeschnitten (Nutzer-Feedback: 'muss scrollen')."""
    body = client.get("/embed/podium").data.decode("utf-8")
    assert "wt-embed-hoehe" in body
    assert "postMessage" in body
    assert "ResizeObserver" in body
    # Das Skript ist theme-unabhaengig aktiv (auch dunkel/hell):
    body_hell = client.get("/embed/podium?theme=hell").data.decode("utf-8")
    assert "wt-embed-hoehe" in body_hell
