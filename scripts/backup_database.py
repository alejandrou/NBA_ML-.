"""Create and verify dated, non-overwriting backups outside the working tree.

Run only with the owner's approval for the named database and destination.
Uses Docker Compose's postgres service; no credentials or .env are copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOTS = ("data/raw", "data/models", "reports")


def file_record(path: Path) -> dict[str, int | str]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def inventory(root: Path, asset_roots: tuple[str, ...] = ASSET_ROOTS) -> dict:
    """Record paths and contents, refusing links that escape the asset boundary."""
    root = root.resolve()
    files = []
    for asset in asset_roots:
        directory = root / asset
        if directory.is_symlink() or directory.resolve() != root / asset:
            raise ValueError(f"Linked asset directory is unsupported: {asset}")
        if not directory.is_dir():
            raise ValueError(f"Missing asset directory: {asset}")
        for path in sorted(directory.rglob("*")):
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or (
                getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ):
                raise ValueError("Linked assets are unsupported")
            if stat.S_ISREG(metadata.st_mode):
                files.append(path)
    # Small-file opens dominate this archive on Windows. Bound concurrency so
    # full integrity checks remain practical without unbounded disk pressure.
    with ThreadPoolExecutor(max_workers=8) as workers:
        records = workers.map(file_record, files)
        return dict(
            zip((path.relative_to(root).as_posix() for path in files), records, strict=True)
        )


def _copy_asset(source: Path, backup: Path, relative: str) -> None:
    target = backup / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with (source / relative).open("rb") as input_stream, target.open("xb") as output:
        shutil.copyfileobj(input_stream, output)


def verify_backup(backup: Path, source: Path | None = None) -> dict:
    """Rehash the whole snapshot; optionally compare it with the current source."""
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format_version"] != 1:
        raise ValueError("Unsupported backup manifest version")
    roots = tuple(manifest["asset_roots"])
    if roots != ASSET_ROOTS:
        raise ValueError("Unexpected asset roots in manifest")
    if inventory(backup, roots) != manifest["assets"]:
        raise ValueError("Backup asset paths or contents do not match the manifest")
    dump = backup / "database.dump"
    if dump.is_symlink() or dump.resolve() != backup.resolve() / "database.dump":
        raise ValueError("Linked database dump is unsupported")
    if file_record(dump) != manifest["dump"]:
        raise ValueError("Database dump does not match the manifest")
    if source is not None and inventory(source, roots) != manifest["assets"]:
        raise ValueError("Current source assets differ from this backup")
    return manifest


def create_backup(destination: Path, database: str, source: Path = REPO_ROOT) -> Path:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]{0,62}", database):
        raise ValueError("Database must be a plain PostgreSQL database name")
    source = source.resolve()
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError("Backup destination must be outside the working tree")
    # Capture the inventory before the dump/copy, then recheck the source. Run
    # with acquisitions and training stopped; this is not a coordinated DB/FS snapshot.
    assets = inventory(source)
    print(f"Inventoried {len(assets)} source files; dumping database...", flush=True)
    started = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = destination / f"nba-{started}-{uuid4().hex[:8]}"
    backup.mkdir(parents=True, exist_ok=False)
    command = ["docker", "compose", "exec", "-T", "postgres"]
    dump = backup / "database.dump"
    # Binary file handles preserve pg_dump's bytes on PowerShell 5.1 as well.
    with dump.open("xb") as output:
        subprocess.run(
            [*command, "pg_dump", "-U", "nba", "-Fc", "--dbname", database],
            cwd=source,
            stdout=output,
            stderr=subprocess.PIPE,
            check=True,
            timeout=600,
        )
    with dump.open("rb") as stream, (backup / "dump.list").open("xb") as listing:
        subprocess.run(
            [*command, "pg_restore", "--list"],
            cwd=source,
            stdin=stream,
            stdout=listing,
            stderr=subprocess.PIPE,
            check=True,
            timeout=60,
        )
    for asset in ASSET_ROOTS:
        (backup / asset).mkdir(parents=True, exist_ok=False)
    print("Copying assets and checking contents...", flush=True)
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(lambda relative: _copy_asset(source, backup, relative), assets))
    if inventory(source) != assets or inventory(backup) != assets:
        raise ValueError("Assets changed during backup, or the copy differs; snapshot incomplete")
    manifest = {
        "format_version": 1,
        "created_at_utc": started,
        "database": database,
        "asset_roots": list(ASSET_ROOTS),
        "assets": assets,
        "dump": file_record(dump),
    }
    # The manifest is the completion marker. Failed runs retain their partial
    # directory for inspection and never overwrite a previous successful run.
    with (backup / "manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--destination", type=Path, required=True)
    create.add_argument("--database", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--backup", type=Path, required=True)
    verify.add_argument("--compare-source", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            backup = create_backup(args.destination, args.database)
        else:
            backup = args.backup
        manifest = verify_backup(
            backup, REPO_ROOT if args.command == "create" or args.compare_source else None
        )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # Driver and process errors can contain sensitive details; print only class.
        print(
            f"Backup failed ({type(exc).__name__}); no verified backup reported.", file=sys.stderr
        )
        return 1
    print(f"Verified backup: {backup}")
    print(
        f"Assets: {len(manifest['assets'])} files, {sum(item['bytes'] for item in manifest['assets'].values())} bytes"
    )
    print(f"Dump: {manifest['dump']['bytes']} bytes, SHA-256 {manifest['dump']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
