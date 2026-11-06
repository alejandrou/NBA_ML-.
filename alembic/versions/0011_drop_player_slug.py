"""Drop core.players.slug, which nothing has ever written or read.

`0001_initial_raw_core` created the column. Its only rebuild-stable generator is
`basketball_reference_player_id`, which the row already carries, so populating it
would store a second copy of an existing identifier. The downgrade recreates the
column exactly as `0001` declared it but cannot restore a value, so the upgrade
refuses to run if any row holds one. The check is SQL rather than a Python query
so it also travels in `alembic upgrade --sql` output, and it runs under the lock
so no value can arrive between the check and the drop.

Revision ID: 0011_drop_player_slug
Revises: 0010_drop_redundant_team_index
Create Date: 2026-11-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_drop_player_slug"
down_revision: str | None = "0010_drop_redundant_team_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("LOCK TABLE core.players IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM core.players WHERE slug IS NOT NULL) THEN
                RAISE EXCEPTION 'Refusing to drop populated core.players.slug';
            END IF;
        END
        $$
        """
    )
    op.drop_column("players", "slug", schema="core")


def downgrade() -> None:
    op.add_column(
        "players",
        sa.Column("slug", sa.String(length=200), nullable=True),
        schema="core",
    )
