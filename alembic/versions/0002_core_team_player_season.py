"""add core team player season relationships

Revision ID: 0002_core_team_player_season
Revises: 0001_initial_raw_core
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_team_player_season"
down_revision: str | None = "0001_initial_raw_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_core_teams_bref_id",
        "teams",
        ["basketball_reference_team_id"],
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_teams_bref_id_not_tot",
        "teams",
        "basketball_reference_team_id IS NULL OR basketball_reference_team_id <> 'TOT'",
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_teams_current_abbreviation_not_tot",
        "teams",
        "current_abbreviation IS NULL OR current_abbreviation <> 'TOT'",
        schema="core",
    )
    op.create_check_constraint(
        "ck_core_team_aliases_abbreviation_not_tot",
        "team_aliases",
        "abbreviation <> 'TOT'",
        schema="core",
    )

    op.create_table(
        "team_seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("team_abbreviation", sa.String(length=10), nullable=False),
        sa.CheckConstraint("team_abbreviation <> 'TOT'", name="ck_core_team_seasons_abbrev_not_tot"),
        sa.ForeignKeyConstraint(["season_id"], ["core.seasons.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["core.teams.id"]),
        sa.UniqueConstraint("team_id", "season_id", name="uq_core_team_seasons_team_season"),
        sa.UniqueConstraint(
            "season_id",
            "team_abbreviation",
            name="uq_core_team_seasons_season_abbrev",
        ),
        schema="core",
    )

    op.create_table(
        "player_seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["core.players.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["core.seasons.id"]),
        sa.UniqueConstraint("player_id", "season_id", name="uq_core_player_seasons_player_season"),
        schema="core",
    )
    op.create_index(
        "ix_core_player_seasons_season_id",
        "player_seasons",
        ["season_id"],
        schema="core",
    )

    op.create_table(
        "player_team_seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_season_id", sa.Integer(), nullable=False),
        sa.Column("team_season_id", sa.Integer(), nullable=False),
        sa.Column("roster_number", sa.String(length=20), nullable=True),
        sa.Column("roster_position", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["player_season_id"], ["core.player_seasons.id"]),
        sa.ForeignKeyConstraint(["team_season_id"], ["core.team_seasons.id"]),
        sa.UniqueConstraint(
            "player_season_id",
            "team_season_id",
            name="uq_core_player_team_seasons_player_team",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_player_team_seasons_team_season_id",
        "player_team_seasons",
        ["team_season_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_core_player_team_seasons_team_season_id",
        table_name="player_team_seasons",
        schema="core",
    )
    op.drop_table("player_team_seasons", schema="core")
    op.drop_index(
        "ix_core_player_seasons_season_id",
        table_name="player_seasons",
        schema="core",
    )
    op.drop_table("player_seasons", schema="core")
    op.drop_table("team_seasons", schema="core")

    op.drop_constraint(
        "ck_core_team_aliases_abbreviation_not_tot",
        "team_aliases",
        schema="core",
        type_="check",
    )
    op.drop_constraint(
        "ck_core_teams_current_abbreviation_not_tot",
        "teams",
        schema="core",
        type_="check",
    )
    op.drop_constraint(
        "ck_core_teams_bref_id_not_tot",
        "teams",
        schema="core",
        type_="check",
    )
    op.drop_constraint("uq_core_teams_bref_id", "teams", schema="core", type_="unique")
