"""Require every core team to have a Basketball Reference code.

Revision ID: 0007_team_bref_id_not_null
Revises: 0006_synthetic_team_codes
Create Date: 2026-08-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_team_bref_id_not_null"
down_revision: str | None = "0006_synthetic_team_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "teams",
        "basketball_reference_team_id",
        schema="core",
        existing_type=sa.String(length=10),
        existing_nullable=True,
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "teams",
        "basketball_reference_team_id",
        schema="core",
        existing_type=sa.String(length=10),
        existing_nullable=False,
        nullable=True,
    )
