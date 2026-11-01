"""Drop the redundant non-unique index on core.teams.basketball_reference_team_id.

`uq_core_teams_bref_id` already backs that exact column with a unique B-tree
index, so `ix_core_teams_bref_id`, created by `0001_initial_raw_core`, answers no
lookup the constraint's index cannot. The downgrade recreates it with the same
name and column.

Revision ID: 0010_drop_redundant_team_index
Revises: 0009_games_and_box_scores
Create Date: 2026-11-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_drop_redundant_team_index"
down_revision: str | None = "0009_games_and_box_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_core_teams_bref_id", table_name="teams", schema="core")


def downgrade() -> None:
    op.create_index("ix_core_teams_bref_id", "teams", ["basketball_reference_team_id"], schema="core")
