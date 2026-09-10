"""KI-Tippgegner fuer die Wulmstörper Tipprunde.

Der Bot analysiert:
- Team-Form (letzte 5 Spiele)
- Tabellenposition
- Heim-/Auswärts-Stärke
- Historische Duelle
- Zufallsfaktor (realistisch unterschiedliche Tipps)

Schwierigkeitsgrade:
- EASY: Viel Zufall, einfache Heuristik
- MEDIUM: Balanciert aus Statistik und Zufall
- HARD: Starke Gewichtung auf Form und Tabelle
- EXPERT: Nutzt ML-Modell (falls trainiert)
"""
import random
import json
import math
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

from flask import current_app

def poisson_random(lmbda: float) -> int:
    """Generiert eine Poisson-verteilte Zufallszahl (Knuth-Algorithmus)."""
    if lmbda <= 0:
        return 0
    L = math.exp(-lmbda)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return max(0, k - 1)

from extensions import db
from models import Match, Team, Prediction, User
from competition_helpers import active_match_query, filter_matches_for_active_competition


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class TeamStats:
    """Statistiken fuer eine Mannschaft."""
    team_id: int
    team_name: str
    position: int
    points: int
    goals_scored: int
    goals_conceded: int
    home_wins: int
    home_draws: int
    home_losses: int
    away_wins: int
    away_draws: int
    away_losses: int
    form: List[str]  # ['W', 'D', 'L', 'W', 'W']
    
    @property
    def home_strength(self) -> float:
        """Berechnet Heimstärke (0-1)."""
        total = self.home_wins + self.home_draws + self.home_losses
        if total == 0:
            return 0.5
        return (self.home_wins * 3 + self.home_draws) / (total * 3)
    
    @property
    def away_strength(self) -> float:
        """Berechnet Auswärtsstärke (0-1)."""
        total = self.away_wins + self.away_draws + self.away_losses
        if total == 0:
            return 0.5
        return (self.away_wins * 3 + self.away_draws) / (total * 3)
    
    @property
    def form_score(self) -> float:
        """Berechnet Form-Score (0-1) aus letzten 5 Spielen."""
        if not self.form:
            return 0.5
        weights = [0.35, 0.28, 0.20, 0.12, 0.05]  # Letztes Spiel wichtiger
        score = 0
        for i, result in enumerate(self.form[:5]):
            w = weights[i] if i < len(weights) else 0.05
            if result == 'W':
                score += w
            elif result == 'D':
                score += w * 0.33
        return score


class AIOpponent:
    """KI-Tippgegner der gegen echte Spieler antritt."""
    
    def __init__(self, name: str, difficulty: Difficulty, user_id: int = None):
        self.name = name
        self.difficulty = difficulty
        self.user_id = user_id  # Falls als "User" in DB gespeichert
        self._model_trained = False
        self._team_stats_cache: Dict[int, TeamStats] = {}

    def invalidate_stats_cache(self):
        """Leert die Team-Statistik-Cache.

        Wichtig: Der AIManager haengt als Singleton an einem langlebigen
        Passenger-Worker. Ohne diesen Reset wuerden die Bots mit dem
        Statistik-Stand ihrer allerersten Tipp-Runde spielen - zu Saisonbeginn
        also mit LEERER Tabelle (alle Teams "durchschnittlich") und diesen
        neutralen Werten bis zum Mai denken. Das war der Hauptgrund, warum auch
        der MasterBot wie ein Zufallsbot tippte (Nutzerfrage 06.09.: "Warum ist
        der so schlecht?"). Vor jeder neuen Tipp-Runde wird die Cache geleert.
        """
        self._team_stats_cache.clear()
    
    def get_tip(self, match: Match, all_matches: List[Match] = None) -> Tuple[int, int]:
        """Generiert Tipp fuer ein Spiel.
        
        Returns:
            Tuple (home_goals, away_goals)
        """
        # Statistiken sammeln
        home_stats = self._get_team_stats(match.home_team_id, all_matches)
        away_stats = self._get_team_stats(match.away_team_id, all_matches)
        
        # Basierend auf Schwierigkeitsgrad Tipps generieren
        if self.difficulty == Difficulty.EASY:
            return self._tip_easy(home_stats, away_stats, match)
        elif self.difficulty == Difficulty.MEDIUM:
            return self._tip_medium(home_stats, away_stats, match)
        elif self.difficulty == Difficulty.HARD:
            return self._tip_hard(home_stats, away_stats, match)
        else:  # EXPERT
            return self._tip_expert(home_stats, away_stats, match)
    
    def _get_team_stats(self, team_id: int, all_matches: List[Match] = None) -> TeamStats:
        """Holt oder berechnet Team-Statistiken."""
        if team_id in self._team_stats_cache:
            return self._team_stats_cache[team_id]
        
        team = db.session.get(Team, team_id)
        
        # Alle beendete Spiele des Teams holen
        if all_matches is None:
            q = Match.query.filter(Match.status == "finished")
            q = filter_matches_for_active_competition(q)
            all_matches = q.order_by(Match.kickoff.desc()).all()
        
        team_matches = [
            m for m in all_matches
            if (m.home_team_id == team_id or m.away_team_id == team_id)
            and m.home_score is not None and m.away_score is not None
        ]
        
        # Form berechnen (letzte 5)
        form = []
        for m in team_matches[:5]:
            if m.home_team_id == team_id:
                if m.home_score > m.away_score:
                    form.append('W')
                elif m.home_score == m.away_score:
                    form.append('D')
                else:
                    form.append('L')
            else:
                if m.away_score > m.home_score:
                    form.append('W')
                elif m.away_score == m.home_score:
                    form.append('D')
                else:
                    form.append('L')
        
        # Heim/Auswärts Bilanz
        home_matches = [m for m in team_matches if m.home_team_id == team_id]
        away_matches = [m for m in team_matches if m.away_team_id == team_id]
        
        home_wins = sum(1 for m in home_matches if m.home_score > m.away_score)
        home_draws = sum(1 for m in home_matches if m.home_score == m.away_score)
        home_losses = len(home_matches) - home_wins - home_draws
        
        away_wins = sum(1 for m in away_matches if m.away_score > m.home_score)
        away_draws = sum(1 for m in away_matches if m.away_score == m.home_score)
        away_losses = len(away_matches) - away_wins - away_draws
        
        # Tore
        goals_scored = sum(m.home_score for m in home_matches) + sum(m.away_score for m in away_matches)
        goals_conceded = sum(m.away_score for m in home_matches) + sum(m.home_score for m in away_matches)
        
        # Tabellenposition (simplifiziert - in echt aus Tabelle berechnen)
        points = home_wins * 3 + home_draws + away_wins * 3 + away_draws
        
        stats = TeamStats(
            team_id=team_id,
            team_name=team.name,
            position=0,  # Wird spaeter berechnet
            points=points,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            home_wins=home_wins,
            home_draws=home_draws,
            home_losses=home_losses,
            away_wins=away_wins,
            away_draws=away_draws,
            away_losses=away_losses,
            form=form
        )
        
        self._team_stats_cache[team_id] = stats
        return stats
    
    def _tip_easy(self, home: TeamStats, away: TeamStats, match: Match) -> Tuple[int, int]:
        """Einfacher Bot: Mehr Zufall, wenig Strategie."""
        # Basis: Heimvorteil
        home_prob = 0.5 + (random.random() * 0.2 - 0.1)  # 0.4 - 0.6
        
        # Zufälliges Ergebnis
        if random.random() < home_prob:
            home_goals = random.randint(1, 3)
            away_goals = random.randint(0, 2)
        else:
            home_goals = random.randint(0, 2)
            away_goals = random.randint(1, 3)
        
        return home_goals, away_goals
    
    def _tip_medium(self, home: TeamStats, away: TeamStats, match: Match) -> Tuple[int, int]:
        """Mittlerer Bot: Beruecksichtigt Form und Heimvorteil."""
        # Gewichtete Wahrscheinlichkeit
        home_advantage = 0.6
        form_factor = (home.form_score - away.form_score) * 0.3
        strength_factor = (home.home_strength - away.away_strength) * 0.2
        
        home_prob = home_advantage + form_factor + strength_factor
        home_prob = max(0.3, min(0.7, home_prob))  # Clamp
        
        # Ergebnis basierend auf Wahrscheinlichkeit.
        # Ein einzelner Zufallswert vermeidet ungewollte Verschiebungen der
        # Wahrscheinlichkeiten durch mehrere random()-Aufrufe.
        r = random.random()
        if r < home_prob:  # Heimsieg
            home_goals = random.randint(2, 4)
            away_goals = random.randint(0, 2)
        elif r < min(0.9, home_prob + 0.2):  # Unentschieden
            home_goals = random.randint(1, 2)
            away_goals = home_goals
        else:  # Auswärtssieg
            home_goals = random.randint(0, 2)
            away_goals = random.randint(2, 4)
        
        return home_goals, away_goals
    
    def _tip_hard(self, home: TeamStats, away: TeamStats, match: Match) -> Tuple[int, int]:
        """Schwerer Bot: Starker Fokus auf Statistiken."""
        # Detaillierte Analyse
        home_strength = home.home_strength * 0.7 + home.form_score * 0.3
        away_strength = away.away_strength * 0.7 + away.form_score * 0.3
        
        # Erwartete Tore berechnen
        expected_home = 1.5 + (home_strength - 0.5) * 2
        expected_away = 1.0 + (away_strength - 0.5) * 2
        
        # Tordurchschnitte einbeziehen
        if home.goals_scored + home.goals_conceded > 0:
            home_avg = home.goals_scored / max(len(home.form), 1)
            expected_home = (expected_home + home_avg) / 2
        
        if away.goals_scored + away.goals_conceded > 0:
            away_avg = away.goals_scored / max(len(away.form), 1)
            expected_away = (expected_away + away_avg) / 2
        
        # Poisson-ähnliche Verteilung
        home_goals = poisson_random(expected_home)
        away_goals = poisson_random(expected_away)
        
        # Realistische Begrenzung; bei klar positiver Erwartung keine
        # komplett torlose Heimprognose erzwingen. Das stabilisiert auch Tests.
        home_goals = min(max(home_goals, 0), 5)
        away_goals = min(max(away_goals, 0), 5)
        if expected_home >= 1.3 and home_goals == 0:
            home_goals = 1
        
        return int(home_goals), int(away_goals)
    
    def _tip_expert(self, home: TeamStats, away: TeamStats, match: Match) -> Tuple[int, int]:
        """Expert-Bot: Beste Strategie + kleiner Zufallsfaktor."""
        # Wie HARD, aber mit optimierten Parametern
        home_strength = home.home_strength * 0.6 + home.form_score * 0.4
        away_strength = away.away_strength * 0.6 + away.form_score * 0.4
        
        # Historische Duelle
        h2h_home_wins = 0
        h2h_q = Match.query.filter(
            Match.status == "finished",
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
            ((Match.home_team_id == home.team_id) & (Match.away_team_id == away.team_id)) |
            ((Match.home_team_id == away.team_id) & (Match.away_team_id == home.team_id))
        )
        h2h_q = h2h_q.filter(Match.competition_id == match.competition_id)
        h2h_matches = h2h_q.limit(5).all()
        
        if h2h_matches:
            for m in h2h_matches:
                if m.home_team_id == home.team_id and m.home_score > m.away_score:
                    h2h_home_wins += 1
                elif m.away_team_id == home.team_id and m.away_score > m.home_score:
                    h2h_home_wins += 1
            h2h_factor = (h2h_home_wins / len(h2h_matches) - 0.5) * 0.2
        else:
            h2h_factor = 0
        
        expected_home = 1.4 + (home_strength - 0.5) * 1.8 + h2h_factor
        expected_away = 1.1 + (away_strength - 0.5) * 1.5 - h2h_factor
        
        home_goals = poisson_random(expected_home)
        away_goals = poisson_random(expected_away)
        if expected_home >= 1.3 and home_goals == 0:
            home_goals = 1
        if expected_away >= 1.3 and away_goals == 0:
            away_goals = 1
        
        return min(max(int(home_goals), 0), 5), min(max(int(away_goals), 0), 5)

    def joker_score(self, match: Match, all_matches: List[Match] = None) -> float:
        """Vertrauens-Score fuer die Joker-Wahl (0..1 plus Bot-Lautstärke).

        Basis: dieselbe Staerke-Differenz (Heim-/Auswaertsstaerke + Form,
        plus Heimvorteil), die auch die harten Strategien verwenden. Je
        klarer ein Team favorisiert ist, desto eher lohnt der x2-Multiplikator.
        Der Rausch-Faktor ist Teil des Charakters: ein EASY-Bot setzt seinen
        Joker eher wild als der MasterBot.
        """
        home = self._get_team_stats(match.home_team_id, all_matches)
        away = self._get_team_stats(match.away_team_id, all_matches)
        hs = home.home_strength * 0.6 + home.form_score * 0.4
        as_ = away.away_strength * 0.6 + away.form_score * 0.4
        confidence = min(1.0, abs(hs + 0.08 - as_) * 2)
        noise = {
            Difficulty.EASY: 0.5, Difficulty.MEDIUM: 0.3,
            Difficulty.HARD: 0.15, Difficulty.EXPERT: 0.05,
        }.get(self.difficulty, 0.2)
        return confidence + random.uniform(-noise, noise)


# ------------------------------------------------------------ Bot-Joker ----
def bot_jokers_enabled() -> bool:
    """Bot-Joker sind Standard an (Paritaet zu den menschlichen Spielern);
    Admin -> Bots kann das abschalten (Setting 'bot_use_jokers')."""
    from utils import get_setting
    from scoring import _truthy_setting
    return _truthy_setting(get_setting("bot_use_jokers", "1"), default=True)


def place_bot_joker(user_id: int, matchday: int, candidates, competition_id: int = None) -> bool:
    """Setzt genau EINEN Joker pro Bot und Spieltag - auf den Tipp mit dem
    besten joker_score. Wie beim Menschen gilt: ist der Joker an diesem
    Spieltag schon (ausserhalb der Kandidaten) vergeben, bleibt er stehen.

    :param candidates: Liste (Prediction, score) der frischen Ueberschriebenen
        oder neu angelegten Tipps des Bots fuer diesen Spieltag.
    """
    if not candidates or not bot_jokers_enabled():
        return False
    from models import Prediction as _Pred
    used_q = (
        db.session.query(_Pred.id)
        .join(Match, _Pred.match_id == Match.id)
        .filter(
            _Pred.user_id == user_id,
            _Pred.joker.is_(True),
            Match.matchday == matchday,
        )
    )
    fresh_ids = [p.id for p, _ in candidates if p.id is not None]
    if fresh_ids:
        used_q = used_q.filter(~_Pred.id.in_(fresh_ids))
    if competition_id:
        used_q = used_q.filter(Match.competition_id == competition_id)
    if used_q.first():
        return False  # Joker diese Runde schon genutzt - Paritaet: nur einer pro Spieltag
    pred, _score = max(candidates, key=lambda t: t[1])
    pred.joker = True
    return True


class AIManager:
    """Verwaltet alle KI-Gegner."""
    
    BOTS = [
        ("RookieBot", Difficulty.EASY),
        ("AmateurBot", Difficulty.EASY),
        ("ProBot", Difficulty.MEDIUM),
        ("ExpertBot", Difficulty.HARD),
        ("MasterBot", Difficulty.EXPERT),
    ]
    
    def __init__(self):
        self.opponents: List[AIOpponent] = []
        self._init_opponents()
    
    def _init_opponents(self):
        """Initialisiert Standard-Bots."""
        from utils import get_setting
        for name, diff in self.BOTS:
            # Suche oder erstelle User fuer Bot
            bot_user = User.query.filter_by(username=name).first()
            if not bot_user:
                bot_user = User(
                    username=name,
                    email=f"{name.lower()}@bot.local",
                    is_admin=False
                )
                bot_user.set_password(''.join(random.choices('0123456789abcdef', k=32)))
                db.session.add(bot_user)
                db.session.commit()
            
            # Difficulty aus den Settings laden
            saved_diff_val = get_setting(f"bot_difficulty_{name}", diff.value)
            try:
                bot_diff = Difficulty(saved_diff_val)
            except ValueError:
                bot_diff = diff
            
            self.opponents.append(AIOpponent(name, bot_diff, bot_user.id))

    def set_bot_difficulty(self, name: str, diff_value: str):
        """Setzt die Schwierigkeit eines Bots persistent."""
        from utils import set_setting
        opp = self.get_opponent(name)
        if opp:
            try:
                new_diff = Difficulty(diff_value)
                opp.difficulty = new_diff
                set_setting(f"bot_difficulty_{name}", diff_value)
                return True
            except ValueError:
                pass
        return False
    
    def get_opponent(self, name: str) -> Optional[AIOpponent]:
        """Holt einen spezifischen Bot."""
        for opp in self.opponents:
            if opp.name == name:
                return opp
        return None
    
    def tip_all_matches(self, matchday: int = None, overwrite: bool = False):
        """Laesst alle aktiven Bots Tipps fuer alle offenen Spiele abgeben.

        Args:
            matchday: optionaler Spieltag
            overwrite: vorhandene Bot-Tipps neu berechnen/ueberschreiben

        Rueckgabe bleibt rueckwaertskompatibel: eine Liste einzelner Tipp-Aktionen.
        Zusaetzlich haengt an der Liste ``summary_by_bot`` fuer die Admin-UI.
        """
        from models import Prediction
        from utils import get_setting
        from cache import invalidate_leaderboard

        class TipResults(list):
            pass
        
        query = active_match_query().filter(Match.status == "scheduled")
        if matchday:
            query = query.filter_by(matchday=matchday)
        matches = query.all()
        # Tests/alte Setups koennen Matches in einer nicht aktiven Competition haben.
        # Wenn der aktive Wettbewerb keine offenen Spiele liefert, fallen wir auf alle
        # geplanten Spiele des Spieltags zurueck.
        if not matches:
            fallback_q = Match.query.filter(Match.status == "scheduled")
            if matchday:
                fallback_q = fallback_q.filter_by(matchday=matchday)
            matches = fallback_q.all()
        results = TipResults()
        summary = {}
        
        if not matches:
            results.summary_by_bot = summary
            return results
        
        # Frischer Statistik-Blick pro Runde (siehe invalidate_stats_cache):
        # ohne das hier wuerden Bots den ganzen Saisonverlauf mit den Werten
        # ihres allerersten Tips spielen.
        for opponent in self.opponents:
            opponent.invalidate_stats_cache()

        # Alle beendete Spiele fuer Statistiken laden - neueste zuerst, damit
        # "Form der letzten 5" auch wirklich die letzten 5 Spiele sind.
        all_finished = (
            active_match_query().filter_by(status="finished")
            .order_by(Match.kickoff.desc()).all()
        )
        
        # (user_id, matchday) -> [(Prediction, joker_score)] fuer die
        # Joker-Setzung nach dem Tipp-Loop (genau einer pro Bot+Spieltag).
        joker_cands: Dict[tuple, list] = {}

        for match in matches:
            for opponent in self.opponents:
                summary.setdefault(opponent.name, {"tipped": 0, "skipped": 0, "overwritten": 0, "errors": 0})
                # Pruefe ob Bot aktiv ist
                from scoring import _truthy_setting
                is_active = _truthy_setting(get_setting(f"bot_active_{opponent.name}", False), default=False)
                if not is_active:
                    summary[opponent.name]["skipped"] += 1
                    continue
                    
                existing = Prediction.query.filter_by(
                    user_id=opponent.user_id,
                    match_id=match.id
                ).first()
                
                if existing and not overwrite:
                    summary[opponent.name]["skipped"] += 1
                    continue

                # Ein aussetzender Bot darf nie die ganze Runde kosten
                # (Produktionsfall 06.09.: MasterBot ohne Tipps, Runde evtl.
                # komplett fehlgeschlagen wegen eines Crashes kurz vor commit).
                try:
                    home_tip, away_tip = opponent.get_tip(match, all_finished)
                    if existing and overwrite:
                        existing.home_tip = home_tip
                        existing.away_tip = away_tip
                        existing.joker = False
                        existing.points = 0
                        summary[opponent.name]["overwritten"] += 1
                        action = "overwritten"
                        target = existing
                    else:
                        prediction = Prediction(
                            user_id=opponent.user_id,
                            match_id=match.id,
                            home_tip=home_tip,
                            away_tip=away_tip,
                            joker=False,
                            points=0,
                        )
                        db.session.add(prediction)
                        summary[opponent.name]["tipped"] += 1
                        action = "tipped"
                        target = prediction

                    # Kandidat fuer den Runden-Joker dieses Bots (Statistik-Cache
                    # ist durch get_tip bereits gefuellt -> kein zusaetzlicher Query).
                    joker_cands.setdefault(
                        (opponent.user_id, match.matchday, match.competition_id), []
                    ).append((target, opponent.joker_score(match, all_finished)))

                    results.append({
                        'bot': opponent.name,
                        'match': f"{match.home_team.name} vs {match.away_team.name}",
                        'tip': f"{home_tip}:{away_tip}",
                        'action': action,
                    })
                except Exception as e:  # noqa: BLE001 - Bot-Ausfall ist erwartbar
                    summary[opponent.name]["errors"] += 1
                    current_app.logger.error(
                        f"Bot-Tipp {opponent.name} @ Spiel {match.id} (ST {match.matchday}) fehlgeschlagen: {e}",
                        exc_info=True,
                    )
                    continue
        
        # Joker je Bot+Spieltag auf den vertrauenswuerdigsten frischen Tipp.
        for (uid, md, comp_id), cands in joker_cands.items():
            place_bot_joker(uid, md, cands, comp_id)
        
        db.session.commit()
        try:
            invalidate_leaderboard()
        except Exception:
            pass
        results.summary_by_bot = summary
        return results
    
    def get_rankings(self) -> List[Dict]:
        """Liefert Rangliste der Bots."""
        rankings = []
        for opp in self.opponents:
            user = db.session.get(User, opp.user_id)
            if user:
                total_points = user.total_points()
                predictions_count = user.predictions.count()
                exact_count = sum(1 for p in user.predictions if p.points >= 4)
                
                rankings.append({
                    'name': opp.name,
                    'difficulty': opp.difficulty.value,
                    'points': total_points,
                    'predictions': predictions_count,
                    'exact': exact_count,
                    'avg_points': round(total_points / max(predictions_count, 1), 2)
                })
        
        return sorted(rankings, key=lambda x: x['points'], reverse=True)


# Lazy-Init Singleton (verhindert DB-Query beim Import ohne App-Context)
_ai_manager = None

def get_ai_manager():
    """Liefert die AIManager-Instanz (lazy, nur bei Bedarf)."""
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AIManager()
    return _ai_manager

# Backward-compat: ai_manager als Property-Zugriff
class _AIManagerProxy:
    """Proxy der get_ai_manager() aufruft – bestehender Code funktioniert weiter."""
    def __getattr__(self, name):
        return getattr(get_ai_manager(), name)
    def __bool__(self):
        return True

ai_manager = _AIManagerProxy()


def get_ai_tip(bot_name: str, match_id: int) -> Tuple[int, int]:
    """Hilfsfunktion um schnell einen KI-Tipp zu bekommen."""
    opponent = get_ai_manager().get_opponent(bot_name)
    if not opponent:
        raise ValueError(f"Bot {bot_name} nicht gefunden")
    
    match = db.session.get(Match, match_id)
    if not match:
        raise ValueError(f"Spiel {match_id} nicht gefunden")
    
    return opponent.get_tip(match)
