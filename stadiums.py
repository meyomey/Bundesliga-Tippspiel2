"""Heimstadien als feste Hinterlegung (12.09.2026).

Hintergrund: football-data.org liefert im genutzten Free-Plan KEIN `venue`
(Sync-Diagnose 12.09.: "0 von 306 mit Stadionangabe"), OpenLigaDB ebenfalls
nicht (live geprueft). Ein Heimstadion ist aber kein Live-Zustand, sondern eine
stabile oeffentliche Tatsache - das fuellen wir statisch nach.

Regeln:
- Der Feed gewinnt immer: hat ein Match ein `venue` aus der API, wird das
  nie durch die Karte ueberschrieben (sync_football_data.py).
- Nur Heimteam-Namen mit eindeutig passenden Schluesselwoertern bekommen ein
  Stadion; alles andere bleibt leer (kein Schaetzen).
- Sponsornamen koennen zur neuen Saison wechseln - dann hier pflegen, die
  Logik bleibt unveraendert.
"""

# Schluessel = Tiny-Wortliste im Team-Namen (normalisiert, alle mussen
# vorkommen), Wert = Stadionname. Stand: Saisonliste 2025/26 (Wikipedia/
# stadion.de, 12.09.2026 gegengeprueft) + bekannte Zweitliga-Stadien.
_STADIUMS = [
    (("bayern",), "Allianz Arena"),
    (("borussia", "dortmund"), "Signal Iduna Park"),
    (("dortmund",), "Signal Iduna Park"),
    (("stuttgart",), "MHPArena"),
    (("eintracht", "frankfurt"), "Deutsche Bank Park"),
    (("freiburg",), "Europa-Park Stadion"),
    (("werder", "bremen"), "Weserstadion"),
    (("hamburger", "sv"), "Volksparkstadion"),
    (("hsv",), "Volksparkstadion"),
    (("heidenheim",), "Voith-Arena"),
    (("hoffenheim",), "PreZero Arena"),
    (("koeln",), "RheinEnergieStadion"),
    (("leipzig",), "Red Bull Arena Leipzig"),
    (("leverkusen",), "BayArena"),
    (("mainz",), "MEWA Arena"),
    (("moenchengladbach",), "Borussia-Park"),
    (("augsburg",), "WWK Arena"),
    (("wolfsburg",), "Volkswagen Arena"),
    (("pauli",), "Millerntor-Stadion"),
    (("union", "berlin"), "Stadion An der Alten Försterei"),
    # Absteiger/Aufsteiger-Kandidaten & 2. Liga (stabile Namen)
    (("holstein", "kiel"), "Holstein-Stadion"),
    (("bochum",), "Vonovia Ruhrstadion"),
    (("braunschweig",), "Eintracht-Stadion"),
    (("hertha",), "Olympiastadion Berlin"),
    (("nuernberg",), "Max-Morlock-Stadion"),
    (("kaiserslautern",), "Fritz-Walter-Stadion"),
    (("dresden",), "Rudolf-Harbig-Stadion"),
    (("arminia", "bielefeld"), "SchücoArena"),
    (("fortuna", "duesseldorf"), "Merkur Spiel-Arena"),
    (("gruether", "furth"), "Sportpark Ronhof"),
    # Aufsteiger 2026/27 (Namen via Transfermarkt-Vereinsseite, 12.09.2026)
    (("elversberg",), "Ursapharm-Arena an der Kaiserlinde"),
    (("paderborn",), "Home Deluxe Arena"),
    (("schalke",), "VELTINS-Arena"),
]


def _normalize(name):
    text = (name or "").lower().replace("ä", "ae").replace("ö", "oe") \
        .replace("ü", "ue").replace("ß", "ss")
    return {t for t in "".join(c if c.isalnum() else " " for c in text).split()
            if len(t) > 1}


def maps_url(venue_name, club_name=None):
    """Schluessellose Google-Maps-Such-URL fuer ein Stadion.

    Verein als Kontext dranhaengen, weil Arena-Namen mit Sponsortiteln
    ("MEWA Arena", "Voith-Arena") so eindeutiger treffen. Desktop oeffnet
    die Webkarte, Smartphones leitet die URL in die Maps-App.
    """
    if not venue_name:
        return None
    from urllib.parse import quote
    query = f"{venue_name}, {club_name}" if club_name else venue_name
    return "https://www.google.com/maps/search/?api=1&query=" + quote(query)


def maps_route_url(venue_name, club_name=None):
    """Direktes Routing (Maps-URL 'dir', schluessellos): ein Tipp, und die
    Navigationsansicht mit Ziel Stadion startet - Startort ist die aktuelle
    Position (Maps erfragt dafuer selbst die Freigabe)."""
    if not venue_name:
        return None
    from urllib.parse import quote
    query = f"{venue_name}, {club_name}" if club_name else venue_name
    return "https://www.google.com/maps/dir/?api=1&destination=" + quote(query)


def home_stadium_for(team_name):
    """Stadionname fuer ein Heimteam - oder None, wenn die Karte es nicht
    eindeutig deckt (dann bleibt das Feld schlicht leer)."""
    toks = _normalize(team_name)
    if not toks:
        return None
    for keys, stadium in _STADIUMS:
        if all(k in toks for k in keys):
            return stadium
    return None
