"""Helper fuer aktive Wettbewerbe und Competition-Filter.

Ziel: Alle fachlichen Match-/Prediction-Queries koennen denselben, validierten
Wettbewerb verwenden. Der Wert aus der Session wird nie blind vertraut, sondern
gegen die DB validiert. Ohne Request-Kontext faellt der Helper auf Config bzw.
den ersten aktiven Wettbewerb zurueck (wichtig fuer Scheduler/Cron/Tests).
"""
from flask import current_app, has_app_context, has_request_context, session
from sqlalchemy import or_

from extensions import db
from models import Competition, Match, Team, CompetitionTeam


def get_active_competition():
    """Liefert den aktuell aktiven Wettbewerb oder ``None``.

    Prioritaet:
    1. validierter ``session['competition_code']`` im Request-Kontext
    2. ``current_app.config['COMPETITION']`` falls aktiv vorhanden
    3. erster aktiver Wettbewerb
    4. beliebiger erster Wettbewerb
    """
    comp = None

    if has_request_context():
        code = session.get("competition_code")
        if code:
            comp = Competition.query.filter_by(code=code, is_active=True).first()
            if comp:
                return comp
            # manipulierte/alte Session bereinigen
            session.pop("competition_code", None)

    default_code = current_app.config.get("COMPETITION") if has_app_context() else None
    if default_code:
        comp = Competition.query.filter_by(code=default_code, is_active=True).first()
        if comp:
            if has_request_context():
                session.setdefault("competition_code", comp.code)
            return comp

    comp = Competition.query.filter_by(is_active=True).order_by(Competition.id.asc()).first()
    if not comp:
        comp = Competition.query.order_by(Competition.id.asc()).first()

    if comp and has_request_context():
        session.setdefault("competition_code", comp.code)
    return comp


def get_active_competition_id():
    comp = get_active_competition()
    return comp.id if comp else None


def get_active_competition_code(default="BL1"):
    comp = get_active_competition()
    return comp.code if comp else default


def filter_matches_for_active_competition(query):
    """Haengt ``Match.competition_id == active.id`` an eine Match-Query.

    Funktioniert fuer Queries, in denen ``Match`` direkt vorkommt oder bereits
    gejoint wurde.
    """
    comp = get_active_competition()
    if comp:
        query = query.filter(Match.competition_id == comp.id)
    return query


def active_match_query():
    """Basisquery fuer Matches des aktiven Wettbewerbs."""
    q = Match.query
    return filter_matches_for_active_competition(q)


def active_matchdays():
    """Sortierte Spieltage des aktiven Wettbewerbs."""
    q = db.session.query(Match.matchday).distinct()
    q = filter_matches_for_active_competition(q)
    return sorted([r[0] for r in q.all()])


def filter_competition_scoped(query, model, include_global=True):
    """Filtert Modelle mit optionaler ``competition_id`` auf den aktiven Wettbewerb.

    ``include_global=True`` beruecksichtigt alte/ globale Datensaetze mit
    ``competition_id IS NULL``. Das ist wichtig fuer Bestandsdaten nach der
    Auto-Migration. Neue Datensaetze sollten immer eine ``competition_id``
    bekommen.
    """
    comp = get_active_competition()
    if not comp or not hasattr(model, "competition_id"):
        return query
    col = getattr(model, "competition_id")
    if include_global:
        return query.filter(or_(col == comp.id, col.is_(None)))
    return query.filter(col == comp.id)


def active_competition_teams(order_by_name=True):
    """Teams des aktiven Wettbewerbs.

    Priorität:
    1. Teams, die im aktiven Spielplan vorkommen (korrekt nach Auf-/Abstieg)
    2. CompetitionTeam-Zuordnungen, falls noch kein Spielplan geladen ist
    3. Fallback: alle Teams

    Damit werden alte Absteiger, die historisch in der globalen Team-Tabelle
    bleiben, nicht mehr in aktuellen Auswahlfragen angezeigt.
    """
    comp = get_active_competition()
    team_ids = set()
    if comp:
        pairs = Match.query.filter(Match.competition_id == comp.id).with_entities(
            Match.home_team_id, Match.away_team_id
        ).all()
        team_ids = {tid for row in pairs for tid in row if tid}
        if not team_ids:
            team_ids = {
                tid for (tid,) in CompetitionTeam.query
                .filter_by(competition_id=comp.id)
                .with_entities(CompetitionTeam.team_id).all()
                if tid
            }
    q = Team.query
    if team_ids:
        q = q.filter(Team.id.in_(team_ids))
    if order_by_name:
        q = q.order_by(Team.name.asc())
    return q.all()


def competition_label(name, season):
    """Anzeige-Label 'Name · Saison' ohne Jahres-Doppelungen.

    Historisch schrieb der Saisonwechsel die Saison auch in den Namen
    (z. B. name='Bundesliga 2026', season='2026' -> 'Bundesliga 2026 2026').
    Diese Funktion dedupliziert robust:
      ('Bundesliga', '2025/26')         -> 'Bundesliga · 2025/26'
      ('Bundesliga 2026', '2026')       -> 'Bundesliga 2026'
      ('Bundesliga 2026', '2026/27')    -> 'Bundesliga 2026/27'
      ('Bundesliga 2025/26', '2025/26') -> 'Bundesliga 2025/26'
    """
    name = (str(name) if name is not None else "").strip()
    season = (str(season) if season is not None else "").strip()
    if not name:
        return season
    if not season:
        return name
    if season in name:
        return name
    first_year = season.split("/")[0]
    if first_year and name.endswith(" " + first_year):
        # 'Bundesliga 2026' + '2026/27' -> 'Bundesliga 2026/27'
        return name + season[len(first_year):]
    return f"{name} · {season}"
