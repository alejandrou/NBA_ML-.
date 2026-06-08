"""add official wide stats tables

Revision ID: 0003_stats_wide_tables
Revises: 0002_core_team_player_season
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_stats_wide_tables"
down_revision: str | None = "0002_core_team_player_season"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEAM_STINT_TABLES = (
    "player_team_season_roster",
    "player_team_season_totals",
    "player_team_season_per_game",
    "player_team_season_per_minute",
    "player_team_season_per_poss",
    "player_team_season_advanced",
    "player_team_season_shooting",
    "player_team_season_adj_shooting",
    "player_team_season_pbp",
)

PLAYER_SEASON_TABLES = (
    "player_season_totals",
    "player_season_per_game",
    "player_season_per_minute",
    "player_season_per_poss",
    "player_season_advanced",
    "player_season_shooting",
    "player_season_adj_shooting",
    "player_season_pbp",
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS stats")

    _create_team_stint_table("player_team_season_roster", _roster_columns())
    _create_team_stint_table("player_team_season_totals", _totals_columns())
    _create_team_stint_table("player_team_season_per_game", _per_game_columns())
    _create_team_stint_table("player_team_season_per_minute", _per_minute_columns())
    _create_team_stint_table("player_team_season_per_poss", _per_poss_columns())
    _create_team_stint_table("player_team_season_advanced", _advanced_columns())
    _create_team_stint_table("player_team_season_shooting", _shooting_columns())
    _create_team_stint_table("player_team_season_adj_shooting", _adjusted_shooting_columns())
    _create_team_stint_table("player_team_season_pbp", _pbp_columns())

    _create_player_season_table("player_season_totals", _totals_columns())
    _create_player_season_table("player_season_per_game", _per_game_columns())
    _create_player_season_table("player_season_per_minute", _per_minute_columns())
    _create_player_season_table("player_season_per_poss", _per_poss_columns())
    _create_player_season_table("player_season_advanced", _advanced_columns())
    _create_player_season_table("player_season_shooting", _shooting_columns())
    _create_player_season_table("player_season_adj_shooting", _adjusted_shooting_columns())
    _create_player_season_table("player_season_pbp", _pbp_columns())


def downgrade() -> None:
    for table_name in reversed(PLAYER_SEASON_TABLES):
        op.drop_table(table_name, schema="stats")

    for table_name in reversed(TEAM_STINT_TABLES):
        op.drop_table(table_name, schema="stats")

    op.execute("DROP SCHEMA IF EXISTS stats")


def _create_team_stint_table(table_name: str, stat_columns: list[sa.Column]) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_team_season_id", sa.Integer(), nullable=False),
        *stat_columns,
        *_lineage_columns(),
        sa.ForeignKeyConstraint(
            ["player_team_season_id"],
            ["core.player_team_seasons.id"],
            name=f"fk_stats_{table_name}_player_team_season_id",
        ),
        sa.UniqueConstraint(
            "player_team_season_id",
            name=f"uq_stats_{table_name}_player_team_season_id",
        ),
        schema="stats",
    )


def _create_player_season_table(table_name: str, stat_columns: list[sa.Column]) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_season_id", sa.Integer(), nullable=False),
        *stat_columns,
        *_lineage_columns(),
        sa.ForeignKeyConstraint(
            ["player_season_id"],
            ["core.player_seasons.id"],
            name=f"fk_stats_{table_name}_player_season_id",
        ),
        sa.UniqueConstraint("player_season_id", name=f"uq_stats_{table_name}_player_season_id"),
        schema="stats",
    )


def _lineage_columns() -> list[sa.Column]:
    return [
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("cache_path", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _int_column(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), nullable=True)


def _num_column(name: str) -> sa.Column:
    return sa.Column(name, sa.Numeric(10, 4), nullable=True)


def _str_column(name: str, length: int) -> sa.Column:
    return sa.Column(name, sa.String(length=length), nullable=True)


def _roster_columns() -> list[sa.Column]:
    return [
        _str_column("jersey_number", 20),
        _str_column("player_name", 200),
        _str_column("position", 20),
        _str_column("height", 20),
        _int_column("weight"),
        sa.Column("birth_date", sa.Date(), nullable=True),
        _str_column("experience", 20),
        _str_column("college", 200),
        _str_column("country_flag", 20),
    ]


def _totals_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _int_column("fg"),
        _int_column("fga"),
        _num_column("fg_pct"),
        _int_column("fg3"),
        _int_column("fg3a"),
        _num_column("fg3_pct"),
        _int_column("fg2"),
        _int_column("fg2a"),
        _num_column("fg2_pct"),
        _num_column("efg_pct"),
        _int_column("ft"),
        _int_column("fta"),
        _num_column("ft_pct"),
        _int_column("orb"),
        _int_column("drb"),
        _int_column("trb"),
        _int_column("ast"),
        _int_column("stl"),
        _int_column("blk"),
        _int_column("tov"),
        _int_column("pf"),
        _int_column("pts"),
        _int_column("tpl_dbl"),
        _str_column("awards", 200),
    ]


def _per_game_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _str_column("position", 20),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _num_column("mp_per_game"),
        _num_column("fg_per_game"),
        _num_column("fga_per_game"),
        _num_column("fg_pct"),
        _num_column("fg3_per_game"),
        _num_column("fg3a_per_game"),
        _num_column("fg3_pct"),
        _num_column("fg2_per_game"),
        _num_column("fg2a_per_game"),
        _num_column("fg2_pct"),
        _num_column("efg_pct"),
        _num_column("ft_per_game"),
        _num_column("fta_per_game"),
        _num_column("ft_pct"),
        _num_column("orb_per_game"),
        _num_column("drb_per_game"),
        _num_column("trb_per_game"),
        _num_column("ast_per_game"),
        _num_column("stl_per_game"),
        _num_column("blk_per_game"),
        _num_column("tov_per_game"),
        _num_column("pf_per_game"),
        _num_column("pts_per_game"),
        _str_column("awards", 200),
    ]


def _per_minute_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _str_column("position", 20),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _num_column("fg_per_36"),
        _num_column("fga_per_36"),
        _num_column("fg_pct"),
        _num_column("fg3_per_36"),
        _num_column("fg3a_per_36"),
        _num_column("fg3_pct"),
        _num_column("fg2_per_36"),
        _num_column("fg2a_per_36"),
        _num_column("fg2_pct"),
        _num_column("efg_pct"),
        _num_column("ft_per_36"),
        _num_column("fta_per_36"),
        _num_column("ft_pct"),
        _num_column("orb_per_36"),
        _num_column("drb_per_36"),
        _num_column("trb_per_36"),
        _num_column("ast_per_36"),
        _num_column("stl_per_36"),
        _num_column("blk_per_36"),
        _num_column("tov_per_36"),
        _num_column("pf_per_36"),
        _num_column("pts_per_36"),
        _str_column("awards", 200),
    ]


def _per_poss_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _num_column("fg_per_poss"),
        _num_column("fga_per_poss"),
        _num_column("fg_pct"),
        _num_column("fg3_per_poss"),
        _num_column("fg3a_per_poss"),
        _num_column("fg3_pct"),
        _num_column("fg2_per_poss"),
        _num_column("fg2a_per_poss"),
        _num_column("fg2_pct"),
        _num_column("efg_pct"),
        _num_column("ft_per_poss"),
        _num_column("fta_per_poss"),
        _num_column("ft_pct"),
        _num_column("orb_per_poss"),
        _num_column("drb_per_poss"),
        _num_column("trb_per_poss"),
        _num_column("ast_per_poss"),
        _num_column("stl_per_poss"),
        _num_column("blk_per_poss"),
        _num_column("tov_per_poss"),
        _num_column("pf_per_poss"),
        _num_column("pts_per_poss"),
        _num_column("ortg"),
        _num_column("drtg"),
        _str_column("awards", 200),
    ]


def _advanced_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _str_column("position", 20),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _num_column("per"),
        _num_column("ts_pct"),
        _num_column("fg3a_per_fga_pct"),
        _num_column("fta_per_fga_pct"),
        _num_column("orb_pct"),
        _num_column("drb_pct"),
        _num_column("trb_pct"),
        _num_column("ast_pct"),
        _num_column("stl_pct"),
        _num_column("blk_pct"),
        _num_column("tov_pct"),
        _num_column("usg_pct"),
        _num_column("ows"),
        _num_column("dws"),
        _num_column("ws"),
        _num_column("ws_per_48"),
        _num_column("obpm"),
        _num_column("dbpm"),
        _num_column("bpm"),
        _num_column("vorp"),
        _str_column("awards", 200),
    ]


def _shooting_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _str_column("position", 20),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _num_column("fg_pct"),
        _num_column("avg_dist"),
        _num_column("pct_fga_fg2a"),
        _num_column("pct_fga_0_3"),
        _num_column("pct_fga_3_10"),
        _num_column("pct_fga_10_16"),
        _num_column("pct_fga_16_plus"),
        _num_column("pct_fga_fg3a"),
        _num_column("fg_pct_fg2a"),
        _num_column("fg_pct_0_3"),
        _num_column("fg_pct_3_10"),
        _num_column("fg_pct_10_16"),
        _num_column("fg_pct_16_plus"),
        _num_column("fg_pct_fg3a"),
        _num_column("pct_ast_fg2"),
        _num_column("pct_ast_fg3"),
        _num_column("pct_fga_dunk"),
        _int_column("dunks_made"),
        _num_column("pct_fg3a_corner3"),
        _num_column("fg_pct_corner3"),
        _int_column("heaves_made"),
        _int_column("heaves_att"),
        _str_column("awards", 200),
    ]


def _adjusted_shooting_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _str_column("position", 20),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _num_column("fg_pct"),
        _num_column("adj_fg_pct"),
        _num_column("fg2_pct"),
        _num_column("adj_fg2_pct"),
        _num_column("fg3_pct"),
        _num_column("adj_fg3_pct"),
        _num_column("efg_pct"),
        _num_column("adj_efg_pct"),
        _num_column("ft_pct"),
        _num_column("adj_ft_pct"),
        _num_column("ts_pct"),
        _num_column("adj_ts_pct"),
        _num_column("fg3a_per_fga_pct"),
        _num_column("adj_fg3a_per_fga_pct"),
        _num_column("fta_per_fga_pct"),
        _num_column("adj_fta_per_fga_pct"),
        _num_column("fg_pts_added"),
        _num_column("ts_pts_added"),
        _str_column("awards", 200),
    ]


def _pbp_columns() -> list[sa.Column]:
    return [
        _int_column("rk"),
        _str_column("player_name_display", 200),
        _str_column("position", 20),
        _int_column("age"),
        _int_column("g"),
        _int_column("gs"),
        _int_column("mp"),
        _num_column("pct_pg"),
        _num_column("pct_sg"),
        _num_column("pct_sf"),
        _num_column("pct_pf"),
        _num_column("pct_c"),
        _num_column("on_court_plus_minus"),
        _num_column("net_plus_minus"),
        _int_column("bad_pass_turnover"),
        _int_column("lost_ball_turnover"),
        _int_column("fouls_shooting"),
        _int_column("fouls_offensive"),
        _int_column("drawn_shooting"),
        _int_column("drawn_offensive"),
        _int_column("and1s"),
        _int_column("own_shots_blocked"),
        _int_column("assisted_points"),
        _str_column("awards", 200),
    ]
