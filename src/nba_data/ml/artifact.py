"""Save and load one model as `<model>-<feature version>-<sha12>/`.

joblib files are pickles: `load_artifact` hashes the bytes before unpickling
them and refuses any mismatch, so it only ever opens what `save_artifact` wrote.
Publishing never replaces a file: an identical rerun is a no-op, and anything
else is refused.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

MODEL_FILENAME = "model.joblib"
METADATA_FILENAME = "metadata.json"
HASH_PREFIX_LENGTH = 12


class ArtifactConflictError(Exception):
    """The target exists with different content."""


class ArtifactIntegrityError(Exception):
    """A stored artifact does not match its recorded hash."""


@dataclass(frozen=True)
class SavedArtifact:
    path: Path
    sha256: str

    @property
    def sha12(self) -> str:
        return self.sha256[:HASH_PREFIX_LENGTH]


def save_artifact(model: Any, metadata: Mapping[str, Any], artifact_dir: Path) -> SavedArtifact:
    """Write the artifact whole, or leave nothing behind but an earlier identical copy."""

    artifact_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=artifact_dir))
    try:
        model_path = staging / MODEL_FILENAME
        joblib.dump(model, model_path, compress=0)
        sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
        document = _metadata_text({**metadata, "model_sha256": sha256})
        (staging / METADATA_FILENAME).write_text(document, encoding="utf-8")

        version = metadata["feature_definition_version"]
        target = artifact_dir / f"{metadata['model']}-{version}-{sha256[:HASH_PREFIX_LENGTH]}"
        try:
            # Refuses an existing target, unlike `os.replace`.
            os.rename(staging, target)
        except OSError as exc:
            if not target.exists():
                raise
            if not _same_artifact(staging, target):
                raise ArtifactConflictError(f"{target} exists with different content") from exc
        return SavedArtifact(target, sha256)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def load_artifact(path: Path) -> tuple[Any, dict[str, Any]]:
    """The model and its metadata, after the bytes match the recorded SHA-256."""

    metadata = json.loads((path / METADATA_FILENAME).read_text(encoding="utf-8"))
    content = (path / MODEL_FILENAME).read_bytes()
    if metadata.get("model_sha256") != hashlib.sha256(content).hexdigest():
        raise ArtifactIntegrityError(f"{path}: {MODEL_FILENAME} does not match its SHA-256")
    return joblib.load(io.BytesIO(content)), metadata


def publish_text(path: Path, text: str) -> None:
    """Create `path` whole; an identical file is fine, a different one is refused."""

    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            _publish_new(temp_path, path)
        except FileExistsError as exc:
            if path.read_bytes() != data:
                raise ArtifactConflictError(f"{path} exists with different content") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _publish_new(source: Path, target: Path) -> None:
    """Publish a finished file whole, refusing an existing target on either platform."""

    if os.name == "nt":
        os.rename(source, target)
    else:
        os.link(source, target)


def _metadata_text(metadata: Mapping[str, Any]) -> str:
    return json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _same_artifact(first: Path, second: Path) -> bool:
    for name in (MODEL_FILENAME, METADATA_FILENAME):
        if not (second / name).is_file():
            return False
        if (first / name).read_bytes() != (second / name).read_bytes():
            return False
    return True
