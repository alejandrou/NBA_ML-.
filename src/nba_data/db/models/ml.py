"""The registered models and the forecasts they issued.

The check conditions are frozen as the same literal text in revision
`0012_ml_predictions`; `tests/unit/test_ml_db_models.py` pins the two together.
Behaviour on PostgreSQL is proven in `tests/integration/test_ml_schema_postgres.py`.

Imports nothing numerical: the API reads these tables and must not load the ML stack.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nba_data.db.base import Base

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


class ModelVersion(Base):
    """A saved model. `name` is its directory under the artifact root."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_ml_model_versions_name"),
        UniqueConstraint("artifact_sha256", name="uq_ml_model_versions_artifact_sha256"),
        CheckConstraint(MODEL_VERSIONS_SHA256_FORMAT, name="ck_ml_model_versions_sha256_format"),
        Index(
            "uq_ml_model_versions_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        {"schema": "ml"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    model_family: Mapped[str] = mapped_column(Text, nullable=False)
    feature_definition_version: Mapped[str] = mapped_column(Text, nullable=False)
    training_seasons: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Prediction(Base):
    """One forecast as issued. Rows are written once and never updated."""

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "model_version_id",
            "cutoff_date",
            name="uq_ml_predictions_game_model_cutoff",
        ),
        CheckConstraint(PREDICTIONS_STATUS, name="ck_ml_predictions_status"),
        CheckConstraint(PREDICTIONS_UNAVAILABLE_REASON, name="ck_ml_predictions_unavailable_reason"),
        CheckConstraint(PREDICTIONS_FAVORITE, name="ck_ml_predictions_favorite"),
        CheckConstraint(PREDICTIONS_PROBABILITY_RANGE, name="ck_ml_predictions_probability_range"),
        CheckConstraint(PREDICTIONS_PROBABILITIES_SUM, name="ck_ml_predictions_probabilities_sum"),
        CheckConstraint(PREDICTIONS_FAVORITE_RULE, name="ck_ml_predictions_favorite_rule"),
        CheckConstraint(PREDICTIONS_STATUS_FIELDS, name="ck_ml_predictions_status_fields"),
        Index("ix_ml_predictions_model_version_id", "model_version_id"),
        {"schema": "ml"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("core.games.id", name="fk_ml_predictions_game_id"), nullable=False
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("ml.model_versions.id", name="fk_ml_predictions_model_version_id"),
        nullable=False,
    )
    cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    home_win_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    away_win_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    favorite: Mapped[str | None] = mapped_column(Text)
    availability_included: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
