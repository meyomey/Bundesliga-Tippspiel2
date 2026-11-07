# -*- coding: utf-8 -*-
"""(177) Im Ranglisten-Spieltag-Dropdown ist der aktuelle Spieltag
gekennzeichnet („Spieltag N · aktuell“) — unabhaengig davon, welcher
Filter gewaehlt ist. Nutzer-Wunsch: man sieht sofort, wo die Liga steht."""


def _seed_aktuellen_md(db, competition, teams, md):
    """Aktiver Wettbewerb (BL1-Conftest: comp 1!), geplantes Spiel auf md."""
    from datetime import datetime, timedelta, timezone as tz
    from models import Match
    from competition_helpers import get_active_competition
    from cache import cache as _cache
    comp = get_active_competition()
    db.session.add(Match(competition_id=(comp.id if comp else competition.id),
                         matchday=md,
                         home_team_id=teams[0].id, away_team_id=teams[1].id,
                         kickoff=datetime.now(tz.utc) + timedelta(days=2),
                         status="scheduled"))
    db.session.commit()
    _cache.clear()


def test_dropdown_kennt_aktuellen_spieltag_177(auth_client, db, competition, teams):
    _seed_aktuellen_md(db, competition, teams, 3)
    html = auth_client.get("/tabelle").get_data(as_text=True)
    assert "Spieltag 3 · aktuell" in html
    assert "Spieltag 4 · aktuell" not in html


def test_marker_unabhaengig_vom_gewaehlten_filter_177(auth_client, db, competition, teams):
    """Auch beim Filter auf einen anderen Spieltag bleibt die Markierung
    beim echten aktuellen (der gewaehlte ist nur 'selected')."""
    _seed_aktuellen_md(db, competition, teams, 3)   # -> aktueller Spieltag
    _seed_aktuellen_md(db, competition, teams, 6)   # zweiter Tag im Dropdown
    html = auth_client.get("/tabelle/6").get_data(as_text=True)
    z6 = next(z for z in html.splitlines() if "<option" in z and ">Spieltag 6<" in z)
    z3 = next(z for z in html.splitlines() if "<option" in z and "Spieltag 3 · aktuell" in z)
    assert "selected" in z6 and "· aktuell" not in z6
    assert "selected" not in z3 and "· aktuell" in z3
