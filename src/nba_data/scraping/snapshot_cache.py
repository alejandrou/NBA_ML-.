"""Timestamped snapshots of Basketball Reference pages that still change.

The archive cache (`HtmlCache`) keeps one body per URL and never overwrites it,
so a page fetched while its season is in progress would be frozen at its first
observation. A snapshot cache keeps every observation instead: each fetch of a
mutable page is a new file named by its `fetched_at`, nothing is ever replaced,
and readers take the latest (ADR 0022).

Layout, under a root kept apart from the archive cache so `cache_inventory` and
the archive backfills never see a snapshot::

    <root>/<host dir>/<slug>-<sha256[:16]>/<fetched_at UTC>.html.gz
    <root>/<host dir>/<slug>-<sha256[:16]>/<fetched_at UTC>.html.gz.meta.json

The host directory, slug and digest are the archive cache's own, so one page has
the same name in both roots. Unlike the archive cache, the sidecar is required:
a snapshot is ordered by the timestamp in its name, and that timestamp must
equal the sidecar's `fetched_at`.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import uuid
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from nba_data.domain.team_codes import is_synthetic_team_code
from nba_data.scraping.cache import (
    METADATA_SUFFIX,
    CacheFetchMetadata,
    CacheMetadataError,
    HtmlCache,
    _metadata_from_payload,
    serialize_cache_fetch_metadata,
    write_cache_fetch_metadata,
)
from nba_data.scraping.cache_writer import (
    CacheWriteError,
    _publish,
    _remove_if_same_file,
    validate_html_for_cache,
)

CURRENT_SEASON_END_YEAR = 2027
"""End year of the season in progress. A card changes it once a season."""

SNAPSHOT_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S%fZ"
BODY_SUFFIX = ".html.gz"

_BASKETBALL_REFERENCE_HOSTS = frozenset(
    {"basketball-reference.com", "www.basketball-reference.com"}
)
_SCHEDULE_PATH_RE = re.compile(
    r"^/leagues/NBA_(?P<year>[0-9]{4})_games(?:-[a-z]+(?:-[0-9]{4})?)?\.html$"
)
_TEAM_SEASON_PATH_RE = re.compile(r"^/teams/(?P<team>[A-Z]{3})/(?P<year>[0-9]{4})\.html$")
_SNAPSHOT_NAME_RE = re.compile(r"^(?P<stamp>[0-9]{8}T[0-9]{12}Z)\.html\.gz$")
_TEMP_SUFFIX = ".tmp"


class SnapshotCacheError(RuntimeError):
    """Raised when the snapshot store is inconsistent and cannot be trusted."""


@dataclass(frozen=True)
class Snapshot:
    """One observation of a mutable page."""

    body: str
    metadata: CacheFetchMetadata
    path: Path


def is_mutable_page(url: str) -> bool:
    """Whether `url` is a page that still changes and belongs in snapshots.

    Declared, not guessed: the league schedule season and month pages and the
    team-season pages of `CURRENT_SEASON_END_YEAR`. Every other page, box
    scores included, is immutable and belongs in the archive cache.
    """

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in _BASKETBALL_REFERENCE_HOSTS:
        return False
    if parsed.params or parsed.query or parsed.fragment:
        return False

    schedule = _SCHEDULE_PATH_RE.match(parsed.path)
    if schedule is not None:
        return int(schedule["year"]) == CURRENT_SEASON_END_YEAR

    team_season = _TEAM_SEASON_PATH_RE.match(parsed.path)
    if team_season is not None:
        return int(team_season["year"]) == CURRENT_SEASON_END_YEAR and not is_synthetic_team_code(
            team_season["team"]
        )
    return False


def snapshot_timestamp(fetched_at: datetime) -> str:
    """The file-name stamp of a fetch time, in UTC with microseconds."""

    if not isinstance(fetched_at, datetime):
        msg = "fetched_at must be a datetime"
        raise ValueError(msg)
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        msg = "fetched_at must be timezone-aware"
        raise ValueError(msg)
    return fetched_at.astimezone(UTC).strftime(SNAPSHOT_TIMESTAMP_FORMAT)


class SnapshotCache:
    """Append-only store of timestamped snapshots of mutable pages."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        # Reused only for its URL-to-name mapping.
        self._names = HtmlCache(self.root_dir)

    def directory_for_url(self, url: str) -> Path:
        """The page's snapshot directory, refused if it resolves outside the root.

        The check runs on the directory itself, after links and junctions are
        resolved, so a link planted at the directory or its host directory
        cannot redirect a write or a read.
        """

        try:
            path = self._names.path_for_url(url)
        except ValueError as exc:
            msg = f"Snapshot path escaped root {self.root_dir}: {url}"
            raise SnapshotCacheError(msg) from exc
        directory = path.with_name(path.name.removesuffix(BODY_SUFFIX))
        self._require_inside_root(directory)
        return directory

    def write(self, url: str, html: str, metadata: CacheFetchMetadata) -> Path:
        """Publish one snapshot, or leave nothing behind.

        Never replaces a file. The sidecar is published before the body, so a
        body is never visible without the sidecar that dates it; if the body
        cannot be published, the sidecar is removed again while it is still the
        file this writer published. A process killed between the two publishes
        leaves an incomplete write behind (`incomplete_writes`).
        """

        if not is_mutable_page(url):
            msg = f"Refusing to snapshot a page that is not mutable: {url}"
            raise CacheWriteError(msg)
        if not isinstance(metadata, CacheFetchMetadata):
            msg = "A snapshot requires its fetch metadata"
            raise CacheWriteError(msg)
        stamp = snapshot_timestamp(metadata.fetched_at)
        _require_readable_metadata(metadata)
        validate_html_for_cache(html)

        directory = self.directory_for_url(url)
        body_path = directory / f"{stamp}{BODY_SUFFIX}"
        metadata_path = _metadata_path(body_path)
        for existing in (body_path, metadata_path):
            if existing.exists():
                msg = f"Refusing to overwrite existing snapshot file: {existing}"
                raise CacheWriteError(msg)

        directory.mkdir(parents=True, exist_ok=True)
        temp_path = body_path.with_name(f".{body_path.name}.{uuid.uuid4().hex}{_TEMP_SUFFIX}")
        metadata_temp_path = metadata_path.with_name(
            f".{metadata_path.name}.{uuid.uuid4().hex}{_TEMP_SUFFIX}"
        )
        # Again now that the directory exists, and for every name written in it.
        for target in (directory, body_path, metadata_path, temp_path, metadata_temp_path):
            self._require_inside_root(target)
        published_metadata: os.stat_result | None = None

        try:
            with gzip.open(temp_path, "wt", encoding="utf-8", newline="") as file:
                file.write(html)
            with gzip.open(temp_path, "rt", encoding="utf-8", newline="") as file:
                if file.read() != html:
                    msg = f"Snapshot write verification failed for {body_path}"
                    raise CacheWriteError(msg)
            write_cache_fetch_metadata(metadata_temp_path, metadata)
            sidecar = metadata_temp_path.stat()
            _publish(metadata_temp_path, metadata_path, "snapshot metadata file")
            published_metadata = sidecar
            _publish(temp_path, body_path, "snapshot file")
        except Exception:
            if published_metadata is not None:
                _remove_if_same_file(metadata_path, published_metadata)
            raise
        finally:
            temp_path.unlink(missing_ok=True)
            metadata_temp_path.unlink(missing_ok=True)

        return body_path

    def history(self, url: str) -> tuple[Snapshot, ...]:
        """Every snapshot of `url`, oldest first, bodies loaded.

        Every snapshot is checked first (see `latest`), then every body is read;
        an unreadable body raises.
        """

        return tuple(_read_body(path, metadata) for path, metadata in self._checked_snapshots(url))

    def latest(self, url: str) -> Snapshot | None:
        """The most recent snapshot of `url`, or None if it was never taken.

        Every snapshot's name and sidecar is checked — a name that is not a
        valid stamp, a body without a sidecar, an unreadable sidecar, or a
        sidecar whose `fetched_at` differs from the name raises — but only the
        newest body is read, so an older unreadable body does not block it. A
        sidecar without a body is an incomplete write, not a snapshot.
        """

        checked = self._checked_snapshots(url)
        if not checked:
            return None
        path, metadata = checked[-1]
        return _read_body(path, metadata)

    def incomplete_writes(self, url: str) -> tuple[Path, ...]:
        """Files a killed writer left for `url`: orphan sidecars and temp files.

        Read-only. None of them is a snapshot and readers ignore them; an orphan
        sidecar only refuses a rewrite with its exact timestamp. Recovery
        (ADR 0022): with no writer running, delete the listed files by hand.
        """

        directory = self.directory_for_url(url)
        if not directory.is_dir():
            return ()
        leftovers = [
            path
            for path in directory.iterdir()
            if path.name.endswith(_TEMP_SUFFIX)
            or (
                path.name.endswith(BODY_SUFFIX + METADATA_SUFFIX)
                and not path.with_name(path.name.removesuffix(METADATA_SUFFIX)).exists()
            )
        ]
        return tuple(sorted(leftovers))

    def _checked_snapshots(self, url: str) -> tuple[tuple[Path, CacheFetchMetadata], ...]:
        directory = self.directory_for_url(url)
        if not directory.is_dir():
            return ()

        dated: list[tuple[datetime, Path]] = []
        for path in directory.glob(f"*{BODY_SUFFIX}"):
            self._require_inside_root(path)
            dated.append((_stamp_from_name(path), path))

        checked: list[tuple[Path, CacheFetchMetadata]] = []
        for fetched_at, path in sorted(dated):
            metadata_path = _metadata_path(path)
            self._require_inside_root(metadata_path)
            checked.append((path, _read_sidecar(path, metadata_path, fetched_at)))
        return tuple(checked)

    def _require_inside_root(self, path: Path) -> None:
        root = self.root_dir.resolve(strict=False)
        resolved = path.resolve(strict=False)
        if root not in resolved.parents:
            msg = f"Snapshot path escaped root {root}: {path} resolves to {resolved}"
            raise SnapshotCacheError(msg)


def _metadata_path(body_path: Path) -> Path:
    return body_path.with_name(body_path.name + METADATA_SUFFIX)


def _require_readable_metadata(metadata: CacheFetchMetadata) -> None:
    """Refuse metadata that the snapshot reader would reject once published."""

    try:
        payload = json.loads(serialize_cache_fetch_metadata(metadata))
        parsed = _metadata_from_payload(payload, Path("<unpublished sidecar>"))
    except (CacheMetadataError, TypeError, ValueError) as exc:
        msg = f"Refusing to snapshot with metadata its reader would reject: {exc}"
        raise CacheWriteError(msg) from exc
    if parsed != metadata:
        msg = f"Refusing to snapshot with metadata that does not read back intact: {metadata!r}"
        raise CacheWriteError(msg)


def _stamp_from_name(path: Path) -> datetime:
    match = _SNAPSHOT_NAME_RE.match(path.name)
    if match is None:
        msg = f"Snapshot file name is not a fetch timestamp: {path}"
        raise SnapshotCacheError(msg)
    try:
        parsed = datetime.strptime(match["stamp"], SNAPSHOT_TIMESTAMP_FORMAT)
    except ValueError as exc:
        msg = f"Snapshot file name is not a valid fetch timestamp: {path}"
        raise SnapshotCacheError(msg) from exc
    return parsed.replace(tzinfo=UTC)


def _read_sidecar(path: Path, metadata_path: Path, fetched_at: datetime) -> CacheFetchMetadata:
    if not metadata_path.exists():
        msg = f"Snapshot has no metadata sidecar: {path}"
        raise SnapshotCacheError(msg)

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        msg = f"Snapshot metadata sidecar is unreadable: {metadata_path}"
        raise CacheMetadataError(msg) from exc
    metadata = _metadata_from_payload(payload, metadata_path)

    if metadata.fetched_at != fetched_at:
        msg = (
            f"Snapshot name says it was fetched at {fetched_at.isoformat()} but its "
            f"sidecar says {metadata.fetched_at.isoformat()}: {path}"
        )
        raise SnapshotCacheError(msg)
    return metadata


def _read_body(path: Path, metadata: CacheFetchMetadata) -> Snapshot:
    try:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
            body = file.read()
    except (OSError, EOFError, zlib.error, UnicodeDecodeError) as exc:
        # gzip.BadGzipFile is an OSError; a truncated stream raises EOFError.
        msg = f"Snapshot body is unreadable: {path}"
        raise SnapshotCacheError(msg) from exc
    return Snapshot(body=body, metadata=metadata, path=path)


__all__ = [
    "CURRENT_SEASON_END_YEAR",
    "Snapshot",
    "SnapshotCache",
    "SnapshotCacheError",
    "is_mutable_page",
    "snapshot_timestamp",
]
