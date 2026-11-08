"""`register_model` refuses what it cannot trust, before touching the database."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nba_data.ml.artifact import ArtifactIntegrityError, save_artifact
from nba_data.ml.models import HomeRateModel
from nba_data.ml.register import ModelRegistrationError, register_model
from nba_data.ml.team_features import FEATURE_DEFINITION_VERSION


class _UntouchedSession:
    """Any use of it fails: these refusals happen before the database."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the database was touched: {name}")


def _metadata(**overrides: object) -> dict[str, object]:
    return {
        "model": "home-rate",
        "feature_definition_version": FEATURE_DEFINITION_VERSION,
        "training_window": "last_5",
        "training_seasons": [2025, 2026],
        "configuration": {},
        "calibration": {"kept": False},
        "metrics": {"stage_5_go": True},
        **overrides,
    }


def _artifact(tmp_path: Path, **overrides: object) -> Path:
    model = HomeRateModel()
    model.home_rate = 0.625
    return save_artifact(model, _metadata(**overrides), tmp_path).path


def test_a_hash_mismatch_is_refused(tmp_path: Path) -> None:
    path = _artifact(tmp_path)
    with (path / "model.joblib").open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(ArtifactIntegrityError):
        register_model(_UntouchedSession(), path)  # type: ignore[arg-type]


def test_an_unknown_feature_definition_is_refused(tmp_path: Path) -> None:
    path = _artifact(tmp_path, feature_definition_version="team-pregame-v0")

    with pytest.raises(ModelRegistrationError, match="team-pregame-v0"):
        register_model(_UntouchedSession(), path)  # type: ignore[arg-type]


@pytest.mark.parametrize("key", ["model", "training_seasons", "metrics", "calibration"])
def test_incomplete_metadata_is_refused(tmp_path: Path, key: str) -> None:
    path = _artifact(tmp_path)
    metadata_path = path / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    del metadata[key]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ModelRegistrationError, match=key):
        register_model(_UntouchedSession(), path)  # type: ignore[arg-type]
