"""Regressionstests: Bot-Joker (Nutzerfrage 06.09.: 'Warum kann ein Bot keinen Joker setzen?').

Bisher war joker=False in den Bot-Tipps hart verdrahtet - nicht etwa wegen
einer Regel, sondern weil es nie eingebaut war. Jetzt gilt Paritaet: jeder
aktive Bot setzt pro Spieltag genau EINEN Joker, auf seinen (laut Modell)
vertrauenswuerdigsten Tipp - starke Bots gezielt, schwache mit Rausch.
Admin -> Bots kann das per Schalter 'bot_use_jokers' abschalten.
"""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction
from scoring import set_setting
from ai_opponent import AIManager, AIOpponent, Difficulty, place_bot_joker


def _open_matches(db, competition, teams, matchday, n=4):
    out = []
    for i in range(n):
        m = Match(
            competition_id=competition.id, matchday=matchday,
            home_team_id=teams[i % 4].id, away_team_id=teams[(i + 1) % 4].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1),
            status='scheduled',
        )
        db.session.add(m)
        out.append(m)
    db.session.commit()
    return out


def _activate_all(manager):
    for opp in manager.opponents:
        set_setting(f'bot_active_{opp.name}', '1')


def _joker_count(db, user_id, matchday):
    return (
        Prediction.query.join(Match, Prediction.match_id == Match.id)
        .filter(Prediction.user_id == user_id, Prediction.joker.is_(True),
                Match.matchday == matchday)
        .count()
    )


def test_tip_all_setzt_genau_einen_joker_pro_bot(app, db, competition, teams):
    with app.app_context():
        _open_matches(db, competition, teams, 1, n=4)
        manager = AIManager()
        _activate_all(manager)
        manager.tip_all_matches(matchday=1)

        for opp in manager.opponents:
            assert _joker_count(db, opp.user_id, 1) == 1, \
                f'{opp.name}: genau ein Joker pro Spieltag erwartet'


def test_joker_pro_spieltag_nicht_pro_saison(app, db, competition, teams):
    """Zweiter Spieltag bekommt seinen eigenen Joker (Regel der Menschen)."""
    with app.app_context():
        _open_matches(db, competition, teams, 1, n=3)
        _open_matches(db, competition, teams, 2, n=3)
        manager = AIManager()
        _activate_all(manager)
        master = manager.get_opponent('MasterBot')
        set_setting('bot_active_MasterBot', '1')

        manager.tip_all_matches(matchday=1)
        manager.tip_all_matches(matchday=2)

        assert _joker_count(db, master.user_id, 1) == 1
        assert _joker_count(db, master.user_id, 2) == 1


def test_bereits_gesetzter_joker_bleibt_einziger(app, db, competition, teams):
    """Hat der Bot an dem Spieltag schon einen Joker (z. B. manuell gesetzt),
    kommt kein zweiter dazu."""
    with app.app_context():
        m1, m2 = _open_matches(db, competition, teams, 1, n=2)[:2]
        manager = AIManager()
        bot = manager.get_opponent('ProBot')
        from extensions import db as _db
        _db.session.add(Prediction(
            user_id=bot.user_id, match_id=m1.id, home_tip=1, away_tip=0, joker=True))
        _db.session.commit()

        set_setting(f'bot_active_{bot.name}', '1')
        manager.tip_all_matches(matchday=1)
        assert _joker_count(db, bot.user_id, 1) == 1, 'nur EIN Joker pro Spieltag'


def test_toggle_aus_keine_bot_joker(app, db, competition, teams):
    with app.app_context():
        _open_matches(db, competition, teams, 1, n=3)
        set_setting('bot_use_jokers', '0')
        manager = AIManager()
        _activate_all(manager)
        manager.tip_all_matches(matchday=1)
        for opp in manager.opponents:
            assert _joker_count(db, opp.user_id, 1) == 0


def test_admin_toggle_route_schaltet_joker_setting(app, db, admin_user):
    with app.app_context():
        from models import User
        from flask_login import login_user  # noqa: F401  (nur Referenz)
        client = app.test_client()
        admin = User.query.filter_by(username='admin').first()
        client.post('/auth/login', data={'email': admin.email, 'password': 'admin123'},
                    follow_redirects=True)
        resp = client.post('/admin/bots/toggle-jokers', data={}, follow_redirects=True)
        assert resp.status_code == 200
        from scoring import get_setting, _truthy_setting
        assert _truthy_setting(get_setting('bot_use_jokers', '1')) is False


def test_joker_landet_bei_klarer_duessel_nicht_bei_remismodell(app, db, competition, teams):
    """Unit fuer place_bot_joker: der hoechste Score gewinnt den Joker."""
    with app.app_context():
        m_a, m_b = _open_matches(db, competition, teams, 1, n=2)[:2]
        from models import User
        bot_user = User(username='JokerUnitBot', email='jokerunit@bot.local')
        bot_user.set_password('x' * 12)
        db.session.add(bot_user)
        db.session.commit()
        from extensions import db as _db
        p1 = Prediction(user_id=bot_user.id, match_id=m_a.id, home_tip=1, away_tip=0, joker=False)
        p2 = Prediction(user_id=bot_user.id, match_id=m_b.id, home_tip=2, away_tip=2, joker=False)
        _db.session.add_all([p1, p2])
        _db.session.commit()

        assert place_bot_joker(bot_user.id, 1, [(p1, 0.3), (p2, 0.8)], competition.id) is True
        _db.session.refresh(p1)
        _db.session.refresh(p2)
        assert p2.joker is True and p1.joker is False


def test_joker_score_beuvorzugt_klaren_favoriten(app, db, competition, teams):
    """Der Score fuer ein einseitiges Duell sollte im Schnitt hoeher sein als
    fuer zwei Duelle auf Augenhoehe (EXPERT-Bot = geringer Rauschen)."""
    with app.app_context():
        now = datetime.now(timezone.utc)
        # Team0 deklassiert 5x Team3 -> starke Bilanz
        for i in range(5):
            db.session.add(Match(
                competition_id=competition.id, matchday=1,
                home_team_id=teams[0].id, away_team_id=teams[3].id,
                kickoff=now - timedelta(days=10 - i), status='finished',
                home_score=3, away_score=0))
        fav = Match(competition_id=competition.id, matchday=2,
                     home_team_id=teams[0].id, away_team_id=teams[1].id,
                     kickoff=now + timedelta(days=1))
        even = Match(competition_id=competition.id, matchday=2,
                      home_team_id=teams[1].id, away_team_id=teams[2].id,
                      kickoff=now + timedelta(days=1))
        db.session.add_all([fav, even])
        db.session.commit()

        bot = AIOpponent('ScoreBot', Difficulty.EXPERT)
        s_fav = [bot.joker_score(fav) for _ in range(40)]
        s_even = [bot.joker_score(even) for _ in range(40)]
        assert sum(s_fav) / 40 > sum(s_even) / 40 + 0.2
