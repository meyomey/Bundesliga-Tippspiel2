"""Countdown-Banner (Feature B): kompakte Pille statt Vollbreiten-Balken.

Sichert das Redesign vom 10.09.2026: zentrierte Pille mit Rand, Jetzt-tippen-
Action-Chip, saubere deutsche Pluralformen - und dass die Stellschrauben der
app.js (ID, data-kickoff, .urgent-Klasse) unveraendert erreichbar bleiben.
Determinismus-Hinweis: der App-Bootstrap kann Demo-Spiele seeden; alle Tests
tippen deshalb zunaechst saemtliche anderen offenen Spiele zu, damit der
Banner-Zaehler exakt 1 bzw. 2 anzeigt.
"""
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import Competition, Match, Prediction, Team
from stats import get_open_matches_for_user


@pytest.fixture
def open_match(db):
    comp = Competition.query.filter_by(code="BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", season="2026",
                           matchdays=34, teams_count=18, is_active=True)
        db.session.add(comp)
        db.session.commit()
    t1 = Team(name="Pill Heim", short_name="PH", logo="x.png")
    t2 = Team(name="Pill Aus", short_name="PA", logo="x.png")
    db.session.add_all([t1, t2])
    db.session.commit()
    kickoff = datetime.now(timezone.utc) + timedelta(hours=20)
    m = Match(competition_id=comp.id, matchday=3, home_team_id=t1.id, away_team_id=t2.id,
              kickoff=kickoff, status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def _tip_all_except(user, keep_ids):
    """Alle anderen offenen Spiele innerhalb 24h zutippen -> zaehlerdeterministisch."""
    for m in get_open_matches_for_user(user, max_hours=24):
        if m.id not in keep_ids:
            db.session.add(Prediction(user_id=user.id, match_id=m.id, home_tip=0, away_tip=0))
    db.session.commit()


def _html(auth_client):
    return auth_client.get("/", follow_redirects=True).get_data(as_text=True)


def test_banner_is_compact_pill_with_action_chip(auth_client, user, open_match):
    _tip_all_except(user, {open_match.id})
    html = _html(auth_client)
    assert 'id="tipReminderBanner"' in html          # app.js-Anker bleibt
    assert 'data-kickoff="' in html                  # Countdown-Quelle bleibt
    # Action-Chip fuehrt in den Schnelltipp, der Textteil zum Spielplan (beide mit Matchday)
    assert '<a class="tr-cta" href="/schnelltipp/3"' in html
    assert ">Jetzt tippen<span" in html
    assert '<a class="tr-main" href="/spielplan/3"' in html
    assert "<strong>1 ungetipptes Spiel offen</strong>" in html   # Singular korrekt


def test_banner_plural(auth_client, user, open_match):
    t3 = Team(name="Dritte", short_name="D3", logo="x.png")
    db.session.add(t3)
    db.session.commit()
    m2 = Match(competition_id=open_match.competition_id, matchday=3,
               home_team_id=t3.id, away_team_id=open_match.away_team_id,
               kickoff=open_match.kickoff + timedelta(hours=1), status="scheduled")
    db.session.add(m2)
    db.session.commit()
    _tip_all_except(user, {open_match.id, m2.id})
    html = _html(auth_client)
    assert "<strong>2 ungetippte Spiele offen</strong>" in html   # Plural korrekt


def test_hidden_when_user_has_tipped_everything(auth_client, user, open_match):
    # keep_ids leer -> samtliches offene Spiele (auch unseres) werden zugetippt
    _tip_all_except(user, set())
    html = _html(auth_client)
    assert 'id="tipReminderBanner"' not in html


def test_css_pill_styling_without_fullwidth_border():
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1] / "static" / "css" / "style.css").read_text(encoding="utf-8")
    assert ".tipreminder-banner {" in css
    assert "border-radius: 999px" in css
    assert "width: min(calc(100% - 24px), 640px)" in css
    assert "backdrop-filter: blur(8px)" in css
    assert ".tr-main {" in css and ".tr-cta:hover" in css
    # Der alte randlose Vollbreiten-Look (nur border-bottom) ist raus:
    assert "border-bottom: 1px solid rgba(245,158,11,.4);" not in css
