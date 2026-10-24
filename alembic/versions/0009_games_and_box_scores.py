"""Add the game grain: core.games and the per-game team and player box scores.

The check conditions are literal text, frozen here so that re-running this
revision always produces the schema it produced the first time.
`db/models/core.py` and `db/models/stats.py` declare the same text, and
`tests/unit/test_game_models.py` asserts the two still agree.

The only change to an existing table is `uq_core_team_seasons_id_season`, the
target of the composite keys that hold both of a game's teams to its season.

Revision ID: 0009_games_and_box_scores
Revises: 0008_drop_raw_schema
Create Date: 2026-10-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_games_and_box_scores"
down_revision: str | None = "0008_drop_raw_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GAMES_BREF_ID_FORMAT = "basketball_reference_game_id ~ '^[0-9]{8}0[A-Z]{3}$'"
GAMES_DISTINCT_TEAMS = "home_team_season_id <> away_team_season_id"
GAMES_GAME_TYPE = "game_type IN ('regular_season', 'play_in', 'playoffs', 'cup_final')"
GAMES_STATUS = "status IN ('scheduled', 'final', 'postponed')"
GAMES_FINAL_HAS_GAME_TYPE = "status <> 'final' OR game_type IS NOT NULL"
GAMES_ATTENDANCE_NON_NEGATIVE = "attendance >= 0"

GAME_COUNTERS_NON_NEGATIVE = (
    "seconds_played >= 0 AND pts >= 0 AND fg >= 0 AND fga >= 0 AND fg3 >= 0 "
    "AND fg3a >= 0 AND ft >= 0 AND fta >= 0 AND orb >= 0 AND drb >= 0 "
    "AND trb >= 0 AND ast >= 0 AND stl >= 0 AND blk >= 0 AND tov >= 0 AND pf >= 0"
)

PLAYER_GAME_PARTICIPATION = (
    "participation IN ('played', 'did_not_play', 'did_not_dress', 'not_with_team', "
    "'suspended', 'other_absence', 'inactive')"
)
PLAYER_GAME_PLAYED_HAS_SECONDS = "participation <> 'played' OR seconds_played IS NOT NULL"
PLAYER_GAME_ABSENT_LINE_EMPTY = (
    "participation = 'played' OR (NOT starter AND seconds_played IS NULL "
    "AND fg IS NULL AND fga IS NULL AND fg3 IS NULL AND fg3a IS NULL "
    "AND ft IS NULL AND fta IS NULL AND orb IS NULL AND drb IS NULL "
    "AND trb IS NULL AND ast IS NULL AND stl IS NULL AND blk IS NULL "
    "AND tov IS NULL AND pf IS NULL AND pts IS NULL AND plus_minus IS NULL)"
)

# Every counting stat but `pts`, whose nullability differs between the tables.
COUNTERS = (
    "fg",
    "fga",
    "fg3",
    "fg3a",
    "ft",
    "fta",
    "orb",
    "drb",
    "trb",
    "ast",
    "stl",
    "blk",
    "tov",
    "pf",
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_core_team_seasons_id_season",
        "team_seasons",
        ["id", "season_id"],
        schema="core",
    )

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("basketball_reference_game_id", sa.Text(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("home_team_season_id", sa.Integer(), nullable=False),
        sa.Column("away_team_season_id", sa.Integer(), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("start_time_et", sa.Time(), nullable=True),
        sa.Column("game_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("venue", sa.Text(), nullable=True),
        sa.Column("neutral_site", sa.Boolean(), nullable=True),
        sa.Column("attendance", sa.Integer(), nullable=True),
        sa.UniqueConstraint("basketball_reference_game_id", name="uq_core_games_bref_id"),
        sa.CheckConstraint(GAMES_BREF_ID_FORMAT, name="ck_core_games_bref_id_format"),
        sa.CheckConstraint(GAMES_DISTINCT_TEAMS, name="ck_core_games_distinct_teams"),
        sa.CheckConstraint(GAMES_GAME_TYPE, name="ck_core_games_game_type"),
        sa.CheckConstraint(GAMES_STATUS, name="ck_core_games_status"),
        sa.CheckConstraint(GAMES_FINAL_HAS_GAME_TYPE, name="ck_core_games_final_has_game_type"),
        sa.CheckConstraint(
            GAMES_ATTENDANCE_NON_NEGATIVE, name="ck_core_games_attendance_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["season_id"], ["core.seasons.id"], name="fk_core_games_season_id"
        ),
        sa.ForeignKeyConstraint(
            ["home_team_season_id", "season_id"],
            ["core.team_seasons.id", "core.team_seasons.season_id"],
            name="fk_core_games_home_team_season",
        ),
        sa.ForeignKeyConstraint(
            ["away_team_season_id", "season_id"],
            ["core.team_seasons.id", "core.team_seasons.season_id"],
            name="fk_core_games_away_team_season",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_games_home_team_season_date",
        "games",
        ["home_team_season_id", "game_date"],
        schema="core",
    )
    op.create_index(
        "ix_core_games_away_team_season_date",
        "games",
        ["away_team_season_id", "game_date"],
        schema="core",
    )
    op.create_index("ix_core_games_game_date", "games", ["game_date"], schema="core")

    op.create_table(
        "team_game_totals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("team_season_id", sa.Integer(), nullable=False),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.Column("seconds_played", sa.Integer(), nullable=False),
        *_counter_columns(),
        sa.Column("pts", sa.Integer(), nullable=False),
        *_lineage_columns(),
        sa.ForeignKeyConstraint(
            ["game_id"], ["core.games.id"], name="fk_stats_team_game_totals_game_id"
        ),
        sa.ForeignKeyConstraint(
            ["team_season_id"],
            ["core.team_seasons.id"],
            name="fk_stats_team_game_totals_team_season_id",
        ),
        sa.UniqueConstraint(
            "game_id", "team_season_id", name="uq_stats_team_game_totals_game_team"
        ),
        sa.UniqueConstraint("game_id", "is_home", name="uq_stats_team_game_totals_game_side"),
        sa.CheckConstraint(
            GAME_COUNTERS_NON_NEGATIVE, name="ck_stats_team_game_totals_non_negative"
        ),
        schema="stats",
    )
    op.create_index(
        "ix_stats_team_game_totals_team_season_id",
        "team_game_totals",
        ["team_season_id"],
        schema="stats",
    )

    op.create_table(
        "player_game_totals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("team_season_id", sa.Integer(), nullable=False),
        sa.Column("starter", sa.Boolean(), nullable=False),
        sa.Column("participation", sa.Text(), nullable=False),
        sa.Column("participation_reason", sa.Text(), nullable=True),
        sa.Column("seconds_played", sa.Integer(), nullable=True),
        *_counter_columns(),
        sa.Column("pts", sa.Integer(), nullable=True),
        sa.Column("plus_minus", sa.Integer(), nullable=True),
        *_lineage_columns(),
        sa.ForeignKeyConstraint(
            ["player_id"], ["core.players.id"], name="fk_stats_player_game_totals_player_id"
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "team_season_id"],
            ["stats.team_game_totals.game_id", "stats.team_game_totals.team_season_id"],
            name="fk_stats_player_game_totals_team_game",
        ),
        sa.UniqueConstraint(
            "game_id", "player_id", name="uq_stats_player_game_totals_game_player"
        ),
        sa.CheckConstraint(
            PLAYER_GAME_PARTICIPATION, name="ck_stats_player_game_totals_participation"
        ),
        sa.CheckConstraint(
            PLAYER_GAME_PLAYED_HAS_SECONDS,
            name="ck_stats_player_game_totals_played_has_seconds",
        ),
        sa.CheckConstraint(
            PLAYER_GAME_ABSENT_LINE_EMPTY,
            name="ck_stats_player_game_totals_absent_line_empty",
        ),
        sa.CheckConstraint(
            GAME_COUNTERS_NON_NEGATIVE, name="ck_stats_player_game_totals_non_negative"
        ),
        schema="stats",
    )
    op.create_index(
        "ix_stats_player_game_totals_player_id",
        "player_game_totals",
        ["player_id"],
        schema="stats",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stats_player_game_totals_player_id", table_name="player_game_totals", schema="stats"
    )
    op.drop_table("player_game_totals", schema="stats")
    op.drop_index(
        "ix_stats_team_game_totals_team_season_id",
        table_name="team_game_totals",
        schema="stats",
    )
    op.drop_table("team_game_totals", schema="stats")
    op.drop_index("ix_core_games_game_date", table_name="games", schema="core")
    op.drop_index("ix_core_games_away_team_season_date", table_name="games", schema="core")
    op.drop_index("ix_core_games_home_team_season_date", table_name="games", schema="core")
    op.drop_table("games", schema="core")
    op.drop_constraint(
        "uq_core_team_seasons_id_season", "team_seasons", schema="core", type_="unique"
    )


def _counter_columns() -> list[sa.Column]:
    return [sa.Column(name, sa.Integer(), nullable=True) for name in COUNTERS]


def _lineage_columns() -> list[sa.Column]:
    return [
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("cache_path", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]
