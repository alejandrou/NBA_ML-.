"""Add source_team_code to player season stats tables.

Revision ID: 0004_player_season_src_team
Revises: 0003_stats_wide_tables
Create Date: 2026-07-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_player_season_src_team"
down_revision = "0003_stats_wide_tables"
branch_labels = None
depends_on = None


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
    for table_name in PLAYER_SEASON_TABLES:
        op.add_column(
            table_name,
            sa.Column("source_team_code", sa.String(length=10), nullable=True),
            schema="stats",
        )


def downgrade() -> None:
    for table_name in reversed(PLAYER_SEASON_TABLES):
        op.drop_column(table_name, "source_team_code", schema="stats")
