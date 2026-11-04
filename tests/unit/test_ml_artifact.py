"""The artifact round-trips, refuses a changed byte, and never replaces anything."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from nba_data.ml import artifact
from nba_data.ml.artifact import (
    METADATA_FILENAME,
    MODEL_FILENAME,
    ArtifactConflictError,
    ArtifactIntegrityError,
    load_artifact,
    publish_text,
    save_artifact,
)
from nba_data.ml.models import EloModel, HomeRateModel

METADATA = {"model": "home-rate", "feature_definition_version": "team-pregame-v1"}


def _model(rate: float = 0.55) -> HomeRateModel:
    model = HomeRateModel()
    model.home_rate = rate
    return model


def test_the_artifact_round_trips_under_its_versioned_name(tmp_path: Path) -> None:
    saved = save_artifact(_model(), METADATA, tmp_path)

    model, metadata = load_artifact(saved.path)

    assert saved.path.name == f"home-rate-team-pregame-v1-{saved.sha12}"
    assert len(saved.sha256) == 64 and saved.sha12 == saved.sha256[:12]
    assert isinstance(model, HomeRateModel) and model.home_rate == 0.55
    assert metadata == {**METADATA, "model_sha256": saved.sha256}


def test_elo_saves_through_the_same_interface(tmp_path: Path) -> None:
    saved = save_artifact(EloModel(20, 100), {**METADATA, "model": "elo"}, tmp_path)

    model, _ = load_artifact(saved.path)

    assert isinstance(model, EloModel) and model.k == 20


def test_loading_refuses_a_changed_byte(tmp_path: Path) -> None:
    saved = save_artifact(_model(), METADATA, tmp_path)
    path = saved.path / MODEL_FILENAME
    content = bytearray(path.read_bytes())
    content[len(content) // 2] ^= 1
    path.write_bytes(content)

    with pytest.raises(ArtifactIntegrityError, match="SHA-256"):
        load_artifact(saved.path)


def test_loading_refuses_metadata_with_no_hash(tmp_path: Path) -> None:
    saved = save_artifact(_model(), METADATA, tmp_path)
    (saved.path / METADATA_FILENAME).write_text(json.dumps(METADATA), encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError):
        load_artifact(saved.path)


def test_saving_the_same_artifact_twice_is_a_no_op_and_leaves_no_staging(tmp_path: Path) -> None:
    first = save_artifact(_model(), METADATA, tmp_path)
    second = save_artifact(_model(), METADATA, tmp_path)

    assert first == second
    assert [path.name for path in tmp_path.iterdir()] == [first.path.name]


def test_the_same_model_with_different_metadata_is_refused(tmp_path: Path) -> None:
    saved = save_artifact(_model(), METADATA, tmp_path)
    before = (saved.path / METADATA_FILENAME).read_bytes()

    with pytest.raises(ArtifactConflictError, match="different content"):
        save_artifact(_model(), {**METADATA, "seed": 1}, tmp_path)

    assert (saved.path / METADATA_FILENAME).read_bytes() == before
    assert [path.name for path in tmp_path.iterdir()] == [saved.path.name]


def test_publishing_text_creates_accepts_identical_and_refuses_different(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "report.json"

    publish_text(path, "one")
    publish_text(path, "one")

    with pytest.raises(ArtifactConflictError, match="different content"):
        publish_text(path, "two")
    assert path.read_text(encoding="utf-8") == "one"


def test_an_interrupted_write_leaves_no_report_and_a_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "report.json"
    real_fsync = os.fsync

    def failing_fsync(descriptor: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(artifact.os, "fsync", failing_fsync)
    with pytest.raises(OSError, match="disk full"):
        publish_text(path, "whole report")

    assert list(tmp_path.iterdir()) == []

    monkeypatch.setattr(artifact.os, "fsync", real_fsync)
    publish_text(path, "whole report")

    assert path.read_text(encoding="utf-8") == "whole report"
    assert [entry.name for entry in tmp_path.iterdir()] == ["report.json"]


def test_a_file_that_appears_before_publishing_is_never_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "report.json"
    real_publish = artifact._publish_new

    def racing_publish(source: Path, target: Path) -> None:
        target.write_text("another run", encoding="utf-8")
        real_publish(source, target)

    monkeypatch.setattr(artifact, "_publish_new", racing_publish)

    with pytest.raises(ArtifactConflictError, match="different content"):
        publish_text(path, "this run")

    assert path.read_text(encoding="utf-8") == "another run"
    assert [entry.name for entry in tmp_path.iterdir()] == ["report.json"]
