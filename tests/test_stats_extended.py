"""Zusaetzliche Tests fuer Statistik-/Scoring-Funktionen."""
from datetime import datetime, timedelta, timezone

from models import Match, Prediction, User
from stats import (
    compute_live_standings, get_team_form, get_h2h, get_match_tip_distribution,
    get_open_matches_for_user, get_current_matchday, get_user_stats_20,
    get_matchday_preview, get_matchday_recap,
)
from scoring import get_live_leaderboard, get_user_stats, get_live_user_stats, calculate_points_for_score


def test_standings_form_h2h_and_distribution(db, user, competition, teams, app, monkeypatch):
    monkeypatch.setitem(app.config, 'COMPETITION', competition.code)

    m1 = Match(
        competition_id=competition.id, matchday=1,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=2),
        status='finished', home_score=2, away_score=0
    )
    m2 = Match(
        competition_id=competition.id, matchday=2,
        home_team_id=teams[1].id, away_team_id=teams[0].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1),
        status='finished', home_score=1, away_score=1
    )
    db.session.add_all([m1, m2])
    db.session.commit()
    other = User(username='anderer', email='anderer@example.com')
    other.set_password('x')
    db.session.add(other)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=m1.id, home_tip=2, away_tip=0, points=4, joker=True))
    db.session.add(Prediction(user_id=other.id, match_id=m1.id, home_tip=3, away_tip=1, points=2))
    db.session.commit()

    table = compute_live_standings()
    assert any(r['team'].id == teams[0].id and r['points'] >= 4 for r in table)
    assert get_team_form(teams[0].id, limit=5)
    assert get_h2h(teams[0].id, teams[1].id, limit=5)
    dist = get_match_tip_distribution(m1.id)
    assert dist['total'] == 2
    assert dist['scores']['2:0'] == 1
    assert dist['scores']['3:1'] == 1
    assert dist['most_common_tip'] in ('2:0', '3:1')
    assert dist['most_common_count'] == 1
    only_others = get_match_tip_distribution(m1.id, exclude_user_id=user.id)
    assert only_others['total'] == 1
    assert only_others['scores'] == {'3:1': 1}
    assert only_others['most_common_tip'] == '3:1'


def test_open_matches_current_matchday_and_stats20(db, user, competition, teams):
    open_match = Match(
        competition_id=competition.id, matchday=8,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) + timedelta(hours=2), status='scheduled'
    )
    finished = Match(
        competition_id=competition.id, matchday=7,
        home_team_id=teams[2].id, away_team_id=teams[3].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1), status='finished',
        home_score=1, away_score=1
    )
    db.session.add_all([open_match, finished])
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=finished.id, home_tip=1, away_tip=1, points=4))
    db.session.commit()

    assert get_current_matchday() == 8
    assert open_match in get_open_matches_for_user(user, max_hours=4)
    s20 = get_user_stats_20(user)
    assert s20['finished_count'] >= 1
    assert s20['best_point_streak'] >= 1


def test_live_leaderboard_bulk_and_user_stats(db, user, competition, teams):
    live = Match(
        competition_id=competition.id, matchday=3,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(minutes=30), status='live',
        home_score=1, away_score=0
    )
    db.session.add(live)
    db.session.commit()
    pred = Prediction(user_id=user.id, match_id=live.id, home_tip=1, away_tip=0, joker=False)
    db.session.add(pred)
    db.session.commit()

    rows = get_live_leaderboard(matchday=3)
    row = next(r for r in rows if r['user'].id == user.id)
    assert row['points'] >= 4
    assert get_live_user_stats(user, matchday=3)['points'] >= 4
    assert calculate_points_for_score(pred, 1, 0) >= 4


def test_matchday_preview_and_recap_helpers(db, user, competition, teams):
    m = Match(
        competition_id=competition.id, matchday=4,
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        kickoff=datetime.now(timezone.utc) - timedelta(days=1), status='finished',
        home_score=3, away_score=2
    )
    db.session.add(m)
    db.session.commit()
    db.session.add(Prediction(user_id=user.id, match_id=m.id, home_tip=3, away_tip=2, points=4, joker=True))
    db.session.commit()

    preview = get_matchday_preview(4)
    assert preview['overall_completion_pct'] > 0
    assert preview['matches'][0]['top_score'] == '3:2'
    recap = get_matchday_recap(4)
    assert recap['winner']['user'].id == user.id
    assert recap['best_joker']['points'] == 4


def test_eternal_table_excludes_archived_bots(db, competition):
    """Archivierte KI-Bots duerfen nicht in der Ewigen Tabelle erscheinen."""
    from models import SeasonArchive
    from stats import get_eternal_table

    human = User(username='human_archive', email='human_archive@example.com')
    human.set_password('x')
    bot = User(username='ExpertBot', email='expertbot@bot.local')
    bot.set_password('x')
    db.session.add_all([human, bot])
    db.session.commit()

    db.session.add_all([
        SeasonArchive(competition_id=competition.id, user_id=human.id, season='2024/25', rank=1, points=100),
        SeasonArchive(competition_id=competition.id, user_id=bot.id, season='2024/25', rank=2, points=90),
    ])
    db.session.commit()

    rows = get_eternal_table()
    names = [r['user'].username for r in rows]
    assert 'human_archive' in names
    assert 'ExpertBot' not in names


def test_maintenance_removes_bots_from_season_archive(db, competition):
    """Wartungsaufgabe entfernt Bot-Archivzeilen dauerhaft."""
    from models import SeasonArchive
    from maintenance import run_repair_tasks

    bot = User(username='ArchiveBot', email='archivebot@bot.local')
    bot.set_password('x')
    db.session.add(bot)
    db.session.commit()
    db.session.add(SeasonArchive(competition_id=competition.id, user_id=bot.id, season='2024/25', rank=1, points=50))
    db.session.commit()

    result = run_repair_tasks('archive_bots')
    assert result['ok'] is True
    assert result['removed'] == 1
    assert SeasonArchive.query.filter_by(user_id=bot.id).count() == 0


def test_official_standings_positions_use_external_source_only(db, competition, teams, monkeypatch):
    """Tippkarten sollen offizielle Tabellenplaetze statt lokaler Fantasie-Raenge nutzen."""
    from stats import get_official_standings_positions, get_team_position

    def fake_standings():
        return ([
            {'team': teams[0], 'rank': 7, 'points': 10},
            {'team': teams[1], 'rank': 3, 'points': 14},
        ], None)

    monkeypatch.setattr('sync.fetch_live_standings', fake_standings)
    positions = get_official_standings_positions()
    assert positions[teams[0].id]['rank'] == 7
    assert get_team_position(teams[1].id) == 3

    monkeypatch.setattr('sync.fetch_live_standings', lambda: (None, 'kein token'))
    assert get_official_standings_positions() == {}
    assert get_team_position(teams[0].id) is None
