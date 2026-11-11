from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from scripts import backup_database as backup


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for asset in backup.ASSET_ROOTS:
        directory = root / asset
        directory.mkdir(parents=True)
        (directory / "example.bin").write_bytes(b"\x00\xfforiginal\r\n")
    return root


@pytest.fixture
def docker(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is True
        if "pg_dump" in command:
            kwargs["stdout"].write(b"PGDMP\x00\xff\r\n")
        else:
            assert kwargs["stdin"].read() == b"PGDMP\x00\xff\r\n"
            kwargs["stdout"].write(b"archive inventory\n")

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    return calls


@pytest.mark.unit
def test_backups_preserve_binary_bytes_and_previous_snapshots(source, tmp_path, docker):
    first = backup.create_backup(tmp_path / "backups", "nba", source)
    second = backup.create_backup(tmp_path / "backups", "nba", source)
    assert first != second
    manifest = backup.verify_backup(first, source)
    assert len(manifest["assets"]) == 3
    assert (first / "database.dump").read_bytes() == b"PGDMP\x00\xff\r\n"
    assert len(docker) == 4
    assert docker[0][-2:] == ["--dbname", "nba"]


@pytest.mark.unit
@pytest.mark.parametrize("damage", ["same-size", "missing", "extra", "dump"])
def test_verification_detects_content_and_path_damage(source, tmp_path, docker, damage):
    snapshot = backup.create_backup(tmp_path / "backups", "nba", source)
    asset = snapshot / "data/raw/example.bin"
    if damage == "same-size":
        asset.write_bytes(b"X" * asset.stat().st_size)
    elif damage == "missing":
        asset.unlink()
    elif damage == "extra":
        (snapshot / "data/raw/unexpected").write_bytes(b"new")
    else:
        dump = snapshot / "database.dump"
        dump.write_bytes(b"X" * dump.stat().st_size)
    with pytest.raises(ValueError, match="match the manifest"):
        backup.verify_backup(snapshot)


@pytest.mark.unit
def test_a_changed_source_does_not_invalidate_a_historical_backup(source, tmp_path, docker):
    snapshot = backup.create_backup(tmp_path / "backups", "nba", source)
    (source / "reports/example.bin").write_bytes(b"new report")
    backup.verify_backup(snapshot)
    with pytest.raises(ValueError, match="source assets differ"):
        backup.verify_backup(snapshot, source)


@pytest.mark.unit
@pytest.mark.parametrize("destination", [".", "data/backups"])
def test_a_destination_in_the_source_is_rejected_before_docker(source, docker, destination):
    with pytest.raises(ValueError, match="outside"):
        backup.create_backup(source / destination, "nba", source)
    assert docker == []


@pytest.mark.unit
def test_an_incomplete_dump_has_no_completion_manifest(source, tmp_path, monkeypatch):
    def fail(command, **kwargs):
        kwargs["stdout"].write(b"partial")
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(backup.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        backup.create_backup(tmp_path / "backups", "nba", source)
    assert not list((tmp_path / "backups").rglob("manifest.json"))


@pytest.mark.unit
def test_source_changes_during_backup_fail_without_a_manifest(
    source, tmp_path, docker, monkeypatch
):
    copy = backup.shutil.copyfileobj

    def changing_copy(input_stream, output):
        copy(input_stream, output)
        (source / "reports" / f"added-{Path(output.name).parent.name}").write_bytes(b"changed")

    monkeypatch.setattr(backup.shutil, "copyfileobj", changing_copy)
    with pytest.raises(ValueError, match="changed during backup"):
        backup.create_backup(tmp_path / "backups", "nba", source)
    assert not list((tmp_path / "backups").rglob("manifest.json"))


@pytest.mark.unit
def test_manifest_cannot_redirect_verification_outside_asset_roots(source, tmp_path, docker):
    snapshot = backup.create_backup(tmp_path / "backups", "nba", source)
    path = snapshot / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["asset_roots"] = ["../repo"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unexpected asset roots"):
        backup.verify_backup(snapshot)
