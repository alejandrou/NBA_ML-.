"""Add the ml schema: registered models and the forecasts they issued.

The check conditions are literal text, frozen here so that re-running this
revision always produces the schema it produced the first time.
`db/models/ml.py` declares the same text, and `tests/unit/test_ml_db_models.py`
asserts the two still agree.

Additive. The downgrade drops both tables and the schema, without CASCADE, so an
object nobody expected stops it instead of being deleted.

Revision ID: 0012_ml_predictions
Revises: 0011_drop_player_slug
Create Date: 2026-11-08 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_ml_predictions"
down_revision: str | None = "0011_drop_player_slug"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MODEL_VERSIONS_SHA256_FORMAT = "artifact_sha256 ~ '^[0-9a-f]{64}$'"
PREDICTIONS_STATUS = "status IN ('available', 'unavailable')"
PREDICTIONS_UNAVAILABLE_REASON = (
    "unavailable_reason IN ('team_season_missing', 'insufficient_history', 'game_not_scheduled')"
)
PREDICTIONS_FAVORITE = "favorite IN ('home', 'away')"
PREDICTIONS_PROBABILITY_RANGE = (
    "home_win_probability BETWEEN 0 AND 1 AND away_win_probability BETWEEN 0 AND 1"
)
PREDICTIONS_PROBABILITIES_SUM = "home_win_probability + away_win_probability = 1"
PREDICTIONS_FAVORITE_RULE = (
    "status = 'unavailable' "
    "OR (home_win_probability > 0.5 AND favorite IS NOT DISTINCT FROM 'home') "
    "OR (home_win_probability < 0.5 AND favorite IS NOT DISTINCT FROM 'away') "
    "OR (home_win_probability = 0.5 AND favorite IS NULL)"
)
PREDICTIONS_STATUS_FIELDS = (
    "(status = 'available' AND home_win_probability IS NOT NULL "
    "AND away_win_probability IS NOT NULL AND unavailable_reason IS NULL) "
    "OR (status = 'unavailable' AND home_win_probability IS NULL "
    "AND away_win_probability IS NULL AND favorite IS NULL "
    "AND unavailable_reason IS NOT NULL)"
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA ml")

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("model_family", sa.Text(), nullable=False),
        sa.Column("feature_definition_version", sa.Text(), nullable=False),
        sa.Column("training_seasons", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("artifact_sha256", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", name="uq_ml_model_versions_name"),
        sa.UniqueConstraint("artifact_sha256", name="uq_ml_model_versions_artifact_sha256"),
        sa.CheckConstraint(MODEL_VERSIONS_SHA256_FORMAT, name="ck_ml_model_versions_sha256_format"),
        schema="ml",
    )
    op.create_index(
        "uq_ml_model_versions_single_active",
        "model_versions",
        ["is_active"],
        unique=True,
        schema="ml",
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("cutoff_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("unavailable_reason", sa.Text(), nullable=True),
        sa.Column("home_win_probability", sa.Numeric(7, 6), nullable=True),
        sa.Column("away_win_probability", sa.Numeric(7, 6), nullable=True),
        sa.Column("favorite", sa.Text(), nullable=True),
        sa.Column(
            "availability_included",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["game_id"], ["core.games.id"], name="fk_ml_predictions_game_id"),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["ml.model_versions.id"],
            name="fk_ml_predictions_model_version_id",
        ),
        sa.UniqueConstraint(
            "game_id",
            "model_version_id",
            "cutoff_date",
            name="uq_ml_predictions_game_model_cutoff",
        ),
        sa.CheckConstraint(PREDICTIONS_STATUS, name="ck_ml_predictions_status"),
        sa.CheckConstraint(
            PREDICTIONS_UNAVAILABLE_REASON, name="ck_ml_predictions_unavailable_reason"
        ),
        sa.CheckConstraint(PREDICTIONS_FAVORITE, name="ck_ml_predictions_favorite"),
        sa.CheckConstraint(
            PREDICTIONS_PROBABILITY_RANGE, name="ck_ml_predictions_probability_range"
        ),
        sa.CheckConstraint(
            PREDICTIONS_PROBABILITIES_SUM, name="ck_ml_predictions_probabilities_sum"
        ),
        sa.CheckConstraint(PREDICTIONS_FAVORITE_RULE, name="ck_ml_predictions_favorite_rule"),
        sa.CheckConstraint(PREDICTIONS_STATUS_FIELDS, name="ck_ml_predictions_status_fields"),
        schema="ml",
    )
    op.create_index(
        "ix_ml_predictions_model_version_id",
        "predictions",
        ["model_version_id"],
        schema="ml",
    )


def downgrade() -> None:
    op.drop_table("predictions", schema="ml")
    op.drop_table("model_versions", schema="ml")
    op.execute("DROP SCHEMA ml")
