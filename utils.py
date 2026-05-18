"""Rückwärts-Kompatibilitäts-Wrapper.

Alle Funktionen wurden in spezialisierte Module aufgeteilt:
  - scoring.py   → Punkte, Ranglisten, Stats
  - badges.py    → Badge-System
  - stats.py     → Statistiken, Trend, Insights, Form, H2H, Wetter
  - sync.py      → API-Sync, Seeding, Schema-Migration
  - mail_helpers.py → E-Mail, Token
  - avatars.py   → Avatar-Upload
  - export.py    → PDF/CSV-Export

Dieses Modul re-exportiert alles, damit bestehender Code (scheduler.py,
whatsapp.py, etc.) weiterhin funktioniert.
"""

# ── scoring ──
from scoring import (
    get_setting, set_setting,
    calculate_points, calculate_points_for_score,
    classify_prediction, classify_prediction_live,
    recalculate_all_points,
    compute_pot_summary, recompute_matchday_winners,
    get_user_stats, get_live_user_stats,
    get_leaderboard, get_live_leaderboard,
)

# ── badges ──
from badges import (
    seed_badges, seed_prizes,
    award_badge, revoke_badge,
    check_and_award_badges,
)

# ── stats ──
from stats import (
    get_user_trend, get_user_insights,
    get_match_tip_distribution, get_match_weather,
    compute_live_standings, get_team_position,
    get_team_form, get_h2h,
    get_eternal_table, archive_season,
    evaluate_special_predictions,
    get_open_matches_for_user, get_current_matchday,
)

# ── sync ──
from sync import (
    seed_teams_if_empty, seed_demo_matches,
    auto_migrate_schema, sync_results,
    _purge_demo_matches,
    fetch_live_standings, fetch_live_match_updates,
)

# ── mail_helpers ──
from mail_helpers import (
    
    send_password_reset, send_email,
    apply_mail_settings, apply_vapid_settings,
)

# ── avatars ──
from avatars import save_avatar

# ── export ──
from export import generate_season_pdf
