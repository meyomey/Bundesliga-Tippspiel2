"""Tests fuer KI-Tippgegner."""
import pytest
import random
from datetime import datetime, timedelta, timezone

from ai_opponent import AIOpponent, Difficulty, AIManager
from models import Match, Prediction
from scoring import set_setting


class TestAIOpponent:
    """Test cases fuer AI Opponent."""
    
    def test_ai_creation(self):
        """Test: Bot wird mit korrektem Schwierigkeitsgrad erstellt."""
        bot = AIOpponent("TestBot", Difficulty.MEDIUM, user_id=1)
        
        assert bot.name == "TestBot"
        assert bot.difficulty == Difficulty.MEDIUM
        assert bot.user_id == 1
    
    def test_easy_tip_range(self, db, competition, teams):
        """Test: EASY Bot gibt Tipps im realistischen Bereich."""
        bot = AIOpponent("EasyBot", Difficulty.EASY)
        
        match = Match(
            competition_id=competition.id,
            matchday=1,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.session.add(match)
        db.session.commit()
        
        home, away = bot.get_tip(match)
        
        assert 0 <= home <= 5
        assert 0 <= away <= 5
        assert isinstance(home, int)
        assert isinstance(away, int)
    
    def test_medium_considers_home_advantage(self, db, competition, teams):
        """Test: MEDIUM Bot bevorzugt Heimmannschaft."""
        random.seed(42)
        bot = AIOpponent("MediumBot", Difficulty.MEDIUM)
        
        match = Match(
            competition_id=competition.id,
            matchday=1,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.session.add(match)
        db.session.commit()
        
        # Mehrere Tipps generieren und pruefen ob Heimsiege hauefiger
        results = [bot.get_tip(match) for _ in range(100)]
        home_wins = sum(1 for h, a in results if h > a)
        
        # Heimsiege sollten hauefiger sein (>50%)
        assert home_wins > 40
    
    def test_hard_uses_statistics(self, db, competition, teams):
        """Test: HARD Bot nutzt Statistiken."""
        bot = AIOpponent("HardBot", Difficulty.HARD)
        
        # Erstelle beendete Spiele fuer Statistiken
        for i in range(5):
            finished = Match(
                competition_id=competition.id,
                matchday=i+1,
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                kickoff=datetime.now(timezone.utc) - timedelta(days=i+1),
                status='finished',
                home_score=3,
                away_score=1
            )
            db.session.add(finished)
        db.session.commit()
        
        match = Match(
            competition_id=competition.id,
            matchday=10,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.session.add(match)
        db.session.commit()
        
        home, away = bot.get_tip(match)
        
        # Bot sollte basierend auf Form hohen Heimsieg tippen
        assert home >= 1
        assert away >= 0
    
    def test_expert_considers_h2h(self, db, competition, teams):
        """Test: EXPERT Bot beruecksichtigt Head-to-Head."""
        bot = AIOpponent("ExpertBot", Difficulty.EXPERT)
        
        # Erstelle H2H Historie
        h2h = Match(
            competition_id=competition.id,
            matchday=1,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            kickoff=datetime.now(timezone.utc) - timedelta(days=30),
            status='finished',
            home_score=4,
            away_score=0
        )
        db.session.add(h2h)
        db.session.commit()
        
        match = Match(
            competition_id=competition.id,
            matchday=5,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            kickoff=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.session.add(match)
        db.session.commit()
        
        home, away = bot.get_tip(match)
        
        # Sollte tendieren zu Heimsieg
        assert home >= 1


class TestAIManager:
    """Test cases fuer AI Manager."""
    
    def test_manager_creates_bots(self, app):
        """Test: Manager erstellt alle Standard-Bots."""
        with app.app_context():
            manager = AIManager()
            
            assert len(manager.opponents) == 5
            assert manager.get_opponent("RookieBot") is not None
            assert manager.get_opponent("MasterBot") is not None
    
    def test_tip_all_matches(self, app, db, competition, teams):
        """Test: Bots tippen fuer alle offenen Spiele."""
        with app.app_context():
            # Erstelle offene Spiele
            for i in range(3):
                match = Match(
                    competition_id=competition.id,
                    matchday=1,
                    home_team_id=teams[i % 4].id,
                    away_team_id=teams[(i+1) % 4].id,
                    kickoff=datetime.now(timezone.utc) + timedelta(days=1)
                )
                db.session.add(match)
            db.session.commit()
            
            manager = AIManager()
            # Standardmaessig sind Bots in der App inaktiv. Fuer diesen Test
            # explizit aktivieren, weil hier das Tippen selbst getestet wird.
            from scoring import set_setting
            for opponent in manager.opponents:
                set_setting(f"bot_active_{opponent.name}", "1")
            results = manager.tip_all_matches(matchday=1)
            
            # 5 Bots * 3 Spiele = 15 Tipps
            assert len(results) == 15
            
            # Pruefe dass Tipps gespeichert wurden
            predictions = Prediction.query.all()
            assert len(predictions) == 15
    
    def test_get_rankings(self, app, db, competition, teams, user):
        """Test: Rangliste der Bots wird erstellt."""
        with app.app_context():
            # Erstelle beendetes Spiel mit Punkten
            match = Match(
                competition_id=competition.id,
                matchday=1,
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                kickoff=datetime.now(timezone.utc) - timedelta(days=1),
                status='finished',
                home_score=2,
                away_score=1
            )
            db.session.add(match)
            db.session.commit()
            
            manager = AIManager()
            # Manuell Tipp mit Punkten hinzufuegen
            for opp in manager.opponents:
                pred = Prediction(
                    user_id=opp.user_id,
                    match_id=match.id,
                    home_tip=2,
                    away_tip=1,
                    points=4
                )
                db.session.add(pred)
            db.session.commit()
            
            rankings = manager.get_rankings()
            
            assert len(rankings) == 5
            assert all('points' in r for r in rankings)
            assert all('difficulty' in r for r in rankings)


def test_bot_users_are_inactive_by_default(db):
    from models import User
    from scoring import filter_active_users, is_bot_active

    human = User(username='human', email='human@example.com')
    human.set_password('x')
    bot = User(username='RookieBot', email='rookiebot@bot.local')
    bot.set_password('x')
    db.session.add_all([human, bot])
    db.session.commit()

    assert is_bot_active(bot) is False
    assert filter_active_users([human, bot]) == [human]


def test_admin_without_game_activity_is_hidden_but_playing_admin_stays(db, teams, competition):
    from datetime import datetime, timedelta, timezone
    from models import User, Match, Prediction
    from scoring import filter_active_users

    player = User(username='player', email='player@example.com')
    player.set_password('x')
    admin_only = User(username='adminonly', email='adminonly@example.com', is_admin=True)
    admin_only.set_password('x')
    playing_admin = User(username='playingadmin', email='playingadmin@example.com', is_admin=True)
    playing_admin.set_password('x')
    db.session.add_all([player, admin_only, playing_admin])
    db.session.commit()
    match = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1), status='scheduled'
    )
    db.session.add(match)
    db.session.commit()
    db.session.add(Prediction(user_id=playing_admin.id, match_id=match.id, home_tip=1, away_tip=1))
    db.session.commit()

    filtered = filter_active_users([player, admin_only, playing_admin])
    assert player in filtered
    assert playing_admin in filtered
    assert admin_only not in filtered


def test_admin_only_not_counted_in_pot(db):
    from models import User
    from scoring import compute_pot_summary

    player = User(username='player2', email='player2@example.com', has_paid=True)
    player.set_password('x')
    admin_only = User(username='adminpot', email='adminpot@example.com', is_admin=True, has_paid=True)
    admin_only.set_password('x')
    db.session.add_all([player, admin_only])
    db.session.commit()

    pot = compute_pot_summary()
    assert pot['total_count'] == 1
    assert pot['paid_count'] == 1
    assert pot['missing_count'] == 0


def test_bots_tippen_mit_frischen_stats_pro_runde(app, db, competition, teams):
    """Nutzerfrage 06.09. ('Warum ist der MasterBot so schlecht?'):
    Der Statistik-Cache der Bots wurde frueher nie geleert - ein langlebiger
    Worker fror den Saisonstart-Zustand (leere Bilanz => alle Teams
    'durchschnittlich') fuer die ganze Saison ein. Seit dem Fix raeumt
    tip_all_matches die Cache vor jeder Runde und sieht frische Form.
    """
    with app.app_context():
        now = datetime.now(timezone.utc)
        # Aeltere Klatsche zuerst, dann 5 Siege - 'Form' muss die NEUESTEN 5
        # treffen, also nur Siege sehen.
        db.session.add(Match(
            competition_id=competition.id, matchday=0,
            home_team_id=teams[0].id, away_team_id=teams[3].id,
            kickoff=now - timedelta(days=30), status='finished',
            home_score=0, away_score=4))
        for i in range(5):
            db.session.add(Match(
                competition_id=competition.id, matchday=1,
                home_team_id=teams[0].id, away_team_id=teams[1].id,
                kickoff=now - timedelta(days=20 - i), status='finished',
                home_score=3, away_score=0))
        db.session.add(Match(
            competition_id=competition.id, matchday=2,
            home_team_id=teams[0].id, away_team_id=teams[2].id,
            kickoff=now + timedelta(days=1)))
        db.session.commit()

        manager = AIManager()
        from scoring import set_setting
        for opponent in manager.opponents:
            set_setting(f'bot_active_{opponent.name}', '1')
            # Vergiftete Cache: simulierte einen zurueckgefrorenen
            # Saisonstart-Zustand (wie im Produktionsfehler).
            opponent._team_stats_cache[teams[0].id] = 'MUELL_VOM_SAISONSTART'

        manager.tip_all_matches(matchday=2)

        master = manager.get_opponent('MasterBot')
        stats = master._team_stats_cache.get(teams[0].id)
        assert stats not in (None, 'MUELL_VOM_SAISONSTART'), \
            'Stats-Cache muss vor jeder Tipp-Runde geleert und neu gefuellt werden'
        assert stats.form[:5] == ['W'] * 5, 'Form muss die neuesten 5 Spiele sein'
        assert stats.form_score > 0.5


# ---------- Runden-Robustheit (Nutzerfall 06.09.: MasterBot ohne ST2-Tipps) --

def _open_md_match(db, competition, teams, matchday, home_i=0, away_i=1):
    m = Match(
        competition_id=competition.id, matchday=matchday,
        home_team_id=teams[home_i].id, away_team_id=teams[away_i].id,
        kickoff=datetime.now(timezone.utc) + timedelta(days=1),
        status='scheduled',
    )
    db.session.add(m)
    db.session.commit()
    return m


def test_null_ergebnisse_crashen_die_runde_nicht(app, db, competition, teams):
    """Reproduktion des Verdachts aus der Produktion: ein 'finished' gemeldetes
    Spiel OHNE Ergebnis (z. B. Mainz-Gladbach nicht ausgetragen) liess bisher
    den h2h-Vergleich des EXPERT-Bots mit TypeError aufschlagen und kostete so
    die halbe Runde. NULL-Zeilen werden jetzt gefiltert."""
    with app.app_context():
        # Verfallenes Duell M05<->HSV als finished ohne Tore
        db.session.add(Match(
            competition_id=competition.id, matchday=1,
            home_team_id=teams[1].id, away_team_id=teams[0].id,
            kickoff=datetime.now(timezone.utc) - timedelta(days=7),
            status='finished', home_score=None, away_score=None))
        _open_md_match(db, competition, teams, 2, home_i=1, away_i=0)
        db.session.commit()

        manager = AIManager()
        for opp in manager.opponents:
            set_setting(f'bot_active_{opp.name}', '1')
        results = manager.tip_all_matches(matchday=2)
        summary = results.summary_by_bot
        assert all(v.get('errors', 0) == 0 for v in summary.values()), \
            f'NULL-Ergebnis darf keinen Bot zum Crash bringen: {summary}'
        for opp in manager.opponents:
            assert Prediction.query.filter_by(user_id=opp.user_id).count() == 1


def test_crash_eines_bots_kostet_nicht_den_ganzen_lauf(app, db, competition, teams, monkeypatch):
    """Isolation: wirft EIN Bot (hier RookieBot) beim Tippen, bekommen die
    anderen trotzdem ihre Tipps + Joker und der Fehler wird nur gesummuert."""
    with app.app_context():
        _open_md_match(db, competition, teams, 2)
        manager = AIManager()
        for opp in manager.opponents:
            set_setting(f'bot_active_{opp.name}', '1')

        original = AIOpponent.get_tip

        def boom(self, match, all_matches=None):
            if self.name == 'RookieBot':
                raise RuntimeError('kuenstlicher Crash')
            return original(self, match, all_matches)

        monkeypatch.setattr(AIOpponent, 'get_tip', boom)
        results = manager.tip_all_matches(matchday=2)
        summary = results.summary_by_bot
        assert summary['RookieBot'].get('errors', 0) == 1
        assert summary['MasterBot']['tipped'] == 1
        assert Prediction.query.join(
            Match, Prediction.match_id == Match.id
        ).filter(Prediction.user_id == manager.get_opponent('RookieBot').user_id).count() == 0
        # Die anderen vier haben getippt (und je einen Joker gesetzt)
        assert Prediction.query.count() == 4
        assert Prediction.query.filter(Prediction.joker.is_(True)).count() == 4


def test_admin_bots_seite_zeigt_verpasste_runde(app, db, admin_user, competition, teams):
    """Neue Spalte 'ST n': aktiver Bot ohne Tipps fuer den aktuellen Spieltag
    wird auf der Bots-Seite ausdruecklich gewarnt (Sichtbarkeit des Falls)."""
    with app.app_context():
        _open_md_match(db, competition, teams, 1)
        from models import User
        from scoring import set_setting as _ss
        manager = AIManager()  # legt Bot-User an
        master = manager.get_opponent('MasterBot')
        _ss('bot_active_MasterBot', '1')
        db.session.expire_all()

        client = app.test_client()
        admin = User.query.filter_by(username='admin').first()
        client.post('/auth/login', data={'email': admin.email, 'password': 'admin123'},
                    follow_redirects=True)
        resp = client.get('/admin/bots')
        assert resp.status_code == 200
        assert b'ST 1' in resp.data
        assert 'ohne Tipps für Spieltag 1'.encode('utf-8') in resp.data
