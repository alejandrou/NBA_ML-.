"""Record a saved model in `ml.model_versions`, optionally making it the active one.

Idempotent by artifact hash. `load_artifact` checks the bytes against the
recorded SHA-256 before anything is unpickled. The caller owns the transaction,
so moving the active flag is atomic with the registration.

A replacement becomes active only when it already has an `available` forecast for
every scheduled game the current model has one for, so no forecast disappears.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session, aliased

from nba_data.db.models import Game, ModelVersion, Prediction
from nba_data.ml.artifact import load_artifact
from nba_data.ml.team_features import FEATURE_DEFINITION_VERSION

_REQUIRED_METADATA = (
    "model",
    "model_sha256",
    "feature_definition_version",
    "training_window",
    "training_seasons",
    "configuration",
    "calibration",
    "metrics",
)


class ModelRegistrationError(ValueError):
    """The artifact cannot be registered."""


@dataclass(frozen=True)
class RegisteredModel:
    name: str
    artifact_sha256: str
    created: bool
    is_active: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "artifact_sha256": self.artifact_sha256,
            "created": self.created,
            "is_active": self.is_active,
        }


def register_model(
    session: Session, artifact_path: Path, *, activate: bool = False
) -> RegisteredModel:
    """Verify the artifact and write its row; `activate` moves the single active flag."""

    _, metadata = load_artifact(artifact_path)
    _require_metadata(metadata)
    if metadata["feature_definition_version"] != FEATURE_DEFINITION_VERSION:
        raise ModelRegistrationError(
            f"{artifact_path}: unknown feature definition "
            f"{metadata['feature_definition_version']!r}; "
            f"this code computes {FEATURE_DEFINITION_VERSION!r}"
        )

    name = artifact_path.resolve().name
    sha256 = metadata["model_sha256"]
    version = session.scalars(
        select(ModelVersion).where(ModelVersion.artifact_sha256 == sha256)
    ).one_or_none()
    created = version is None
    if version is None:
        version = _new_version(name, metadata)
        session.add(version)
        session.flush()
    elif version.name != name:
        raise ModelRegistrationError(
            f"{artifact_path}: this artifact is already registered as {version.name!r}"
        )

    if activate and not version.is_active:
        _move_active_flag(session, version)

    return RegisteredModel(name, sha256, created, version.is_active)


def activate_model(session: Session, name: str) -> RegisteredModel:
    """Make a registered model the active one, once it covers what is being served."""

    version = session.scalars(select(ModelVersion).where(ModelVersion.name == name)).one_or_none()
    if version is None:
        raise ModelRegistrationError(f"{name} is not registered")
    if not version.is_active:
        _move_active_flag(session, version)
    return RegisteredModel(version.name, version.artifact_sha256, False, version.is_active)


def _move_active_flag(session: Session, version: ModelVersion) -> None:
    active = session.scalars(select(ModelVersion).where(ModelVersion.is_active)).one_or_none()
    if active is not None:
        missing = _games_losing_a_forecast(session, active.id, version.id)
        if missing:
            shown = ", ".join(missing[:5])
            raise ModelRegistrationError(
                f"{version.name} has no forecast for {len(missing)} scheduled game(s) "
                f"{active.name} covers (first: {shown}). Register it without --activate, run "
                f"`nba-data ml predict --model {version.name}`, then `nba-data ml activate`."
            )
        # Clear first: the partial unique index allows one active row at any instant.
        session.execute(
            update(ModelVersion).where(ModelVersion.id == active.id).values(is_active=False)
        )
    session.execute(
        update(ModelVersion).where(ModelVersion.id == version.id).values(is_active=True)
    )
    session.refresh(version)


def _games_losing_a_forecast(session: Session, active_id: int, candidate_id: int) -> list[str]:
    candidate = aliased(Prediction)
    statement = (
        select(Game.basketball_reference_game_id)
        .join(Prediction, Prediction.game_id == Game.id)
        .where(
            Game.status == "scheduled",
            Prediction.model_version_id == active_id,
            Prediction.status == "available",
            ~exists().where(
                candidate.game_id == Game.id,
                candidate.model_version_id == candidate_id,
                candidate.status == "available",
            ),
        )
        .distinct()
        .order_by(Game.basketball_reference_game_id)
    )
    return list(session.scalars(statement))


def _require_metadata(metadata: Mapping[str, Any]) -> None:
    missing = [key for key in _REQUIRED_METADATA if key not in metadata]
    if missing:
        raise ModelRegistrationError(f"artifact metadata is missing {missing}")


def _new_version(name: str, metadata: Mapping[str, Any]) -> ModelVersion:
    return ModelVersion(
        name=name,
        model_family=metadata["model"],
        feature_definition_version=metadata["feature_definition_version"],
        training_seasons=list(metadata["training_seasons"]),
        configuration={
            "hyperparameters": metadata["configuration"],
            "training_window": metadata["training_window"],
            "calibration": metadata["calibration"],
        },
        metrics=metadata["metrics"],
        artifact_sha256=metadata["model_sha256"],
    )
