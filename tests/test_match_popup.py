"""(132) Spieldetail-Popup: Klick auf Spielzeilen (Dashboard/Live-Center)
öffnet die vorhandene /match/<id>-Seite als Modal — per iframe mit
?embed=1 (schlanke Shell ohne Navigation). Der Workflow bleibt 0 €:
keine externen Abhängigkeiten, nur eigene Daten.
"""
from datetime import datetime, timedelta, timezone

from models import Match


def _login(client, user):
    client.post("/auth/login", data={"email": user.email, "password": "admin123"},
                follow_redirects=True)


def _use_test_comp(client):
    with client.session_transaction() as sess:
        sess["competition_code"] = "TEST"


def _match(db, competition, teams):
    m = Match(competition_id=competition.id, matchday=1,
              home_team_id=teams[0].id, away_team_id=teams[1].id,
              kickoff=datetime.now(timezone.utc) + timedelta(days=1),
              status="scheduled")
    db.session.add(m)
    db.session.commit()
    return m


def test_embed_modus_rendert_ohne_navigation(client, db, admin_user,
                                             competition, teams):
    """?embed=1 liefert die schlanke Shell (kein navMenu, kein Footer-App-JS),
    ohne embed die volle Seite mit Navigation."""
    _login(client, admin_user)
    _use_test_comp(client)
    m = _match(db, competition, teams)
    embed = client.get(f"/match/{m.id}?embed=1").get_data(as_text=True)
    voll = client.get(f"/match/{m.id}").get_data(as_text=True)
    assert "FC Bayern München" in embed
    assert 'id="navMenu"' not in embed           # keine Navigation im Popup
    assert "embed-mode" in embed
    assert 'id="navMenu"' in voll                # normal bleibt voll


def test_dashboard_und_live_binden_popup_ein(client, db, admin_user,
                                             competition, teams):
    """Dashboard (Spielzeilen-Links) und Live-Center (Karten) laden
    match_popup.js; die bestehenden Links/Karten bleiben erhalten."""
    _login(client, admin_user)
    _use_test_comp(client)
    _match(db, competition, teams)
    dash = client.get("/dashboard").get_data(as_text=True)
    live = client.get("/live").get_data(as_text=True)
    assert dash.count("js/match_popup.js") == 1
    assert live.count("js/match_popup.js") == 1
    assert 'class="match-row"' in dash           # Zeilen-Links intakt
    assert "live-match-card" in live             # Karten intakt


def test_popup_js_vertrag():
    """Delegation lebt SSE-Rerender über; embed-Param gesetzt; ESC/Backdrop
    schließen; Modifikator-Klick lässt den Tab-öffnen-Fall durch."""
    js = open("static/js/match_popup.js", encoding="utf-8").read()
    assert 'e.target.closest(".live-match-card[data-match-id]")' in js
    assert "a.match-row[href*='/match/']" in js
    assert "?embed=1" in js
    assert 'e.key === "Escape"' in js
    assert "e.target === overlay" in js
    assert "e.metaKey || e.ctrlKey || e.shiftKey || e.altKey" in js
    assert "document.addEventListener(\"click\"" in js  # Delegation, nicht Einzelbindung


def test_base_embed_vorhanden_und_minimal():
    """Die Embed-Shell hat keine Navigation und bindet nur die Styles ein."""
    t = open("templates/base_embed.html", encoding="utf-8").read()
    assert "navMenu" not in t and "<nav" not in t
    assert "style.min.css" in t
    assert "{% block content %}{% endblock %}" in t


def test_schnelltipp_details_popup_und_entklemmung_135():
    """(135) Der 📊-Details-Link im Schnelltipp ist bei geschlossenen Karten
    klickbar (pointer-events entklemmt) und oeffnet das Popup, kein Wechsel."""
    css = open("static/css/quick_tip.css", encoding="utf-8").read()
    assert ".qt-match-card.closed .qt-details-link" in css
    assert "pointer-events: auto" in css
    js = open("static/js/match_popup.js", encoding="utf-8").read()
    assert "a.qt-details-link[href*='/match/']" in js
    t = open("templates/quick_tip.html", encoding="utf-8").read()
    assert t.count("js/match_popup.js") == 1
