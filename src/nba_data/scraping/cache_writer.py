"""Atomic, never-overwrite cache writes for gated acquisitions.

The same writer lives as a private copy in `nba_team_season_acquisition.py` and
`player_page_acquisition.py`. Those copies are left as they are so no existing
Basketball Reference acquisition path changes; new acquisitions use this one.
Unlike those copies, this writer publishes with a primitive that refuses an
existing target, so it stays safe when two processes write the same page.
"""

from __future__ import annotations

import gzip
import os
import uuid
from pathlib import Path

from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache, write_cache_fetch_metadata


class CacheWriteError(RuntimeError):
    """Raised when a cache write cannot complete safely."""


def validate_html_for_cache(html: str) -> None:
    """Refuse content that is empty or does not look like an HTML document."""

    if not isinstance(html, str) or not html.strip():
        msg = "Fetched content is empty and will not be cached"
        raise ValueError(msg)

    lowered = html.lstrip().lower()
    if not (lowered.startswith("<!doctype html") or lowered.startswith("<html")):
        msg = "Fetched content does not look like an HTML document"
        raise ValueError(msg)


def write_html_to_cache_safely(
    cache: HtmlCache,
    url: str,
    html: str,
    *,
    metadata: CacheFetchMetadata | None = None,
) -> Path:
    """Write one body, and its sidecar when given, or leave nothing behind.

    Never overwrites an existing body or sidecar, and verifies the body reads
    back byte for byte before publishing it. The existence check up front only
    gives an early, clear refusal: the publish itself refuses a target that
    another writer created after that check, and the body goes first, so of two
    concurrent writers only the one that published the body writes a sidecar.
    A failed sidecar removes the body again only while it is still the file
    this writer published.
    """

    final_path = cache.path_for_url(url)
    metadata_path = cache.metadata_path_for_url(url)
    _refuse_existing(final_path, metadata_path)

    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")
    metadata_temp_path = metadata_path.with_name(f".{metadata_path.name}.{uuid.uuid4().hex}.tmp")
    published_body: os.stat_result | None = None

    try:
        with gzip.open(temp_path, "wt", encoding="utf-8", newline="") as file:
            file.write(html)
        with gzip.open(temp_path, "rt", encoding="utf-8", newline="") as file:
            if file.read() != html:
                msg = f"Cache write verification failed for {final_path}"
                raise CacheWriteError(msg)
        if metadata is not None:
            write_cache_fetch_metadata(metadata_temp_path, metadata)
        body = temp_path.stat()
        _publish(temp_path, final_path, "cache file")
        published_body = body
        if metadata is not None:
            _publish(metadata_temp_path, metadata_path, "cache metadata file")
    except Exception:
        if published_body is not None:
            _remove_if_same_file(final_path, published_body)
        raise
    finally:
        temp_path.unlink(missing_ok=True)
        metadata_temp_path.unlink(missing_ok=True)

    return final_path


def _publish(temp_path: Path, final_path: Path, what: str) -> None:
    """Give a finished temp file its final name, refusing a name that exists.

    `os.replace` would silently replace a file another writer published after
    the existence check. On Windows `os.rename` refuses an existing target;
    elsewhere a hard link does, and the caller removes the temp name. Both keep
    the file's identity, which the rollback relies on.
    """

    try:
        if os.name == "nt":
            os.rename(temp_path, final_path)
        else:
            os.link(temp_path, final_path)
    except FileExistsError as exc:
        msg = f"Refusing to overwrite existing {what}: {final_path}"
        raise CacheWriteError(msg) from exc


def _remove_if_same_file(path: Path, published: os.stat_result) -> None:
    """Remove `path` only while it is still the file this writer published."""

    try:
        if os.path.samestat(path.stat(), published):
            path.unlink()
    except FileNotFoundError:
        pass


def _refuse_existing(final_path: Path, metadata_path: Path) -> None:
    if final_path.exists():
        msg = f"Refusing to overwrite existing cache file: {final_path}"
        raise CacheWriteError(msg)
    if metadata_path.exists():
        msg = f"Refusing to overwrite existing cache metadata file: {metadata_path}"
        raise CacheWriteError(msg)


__all__ = [
    "CacheWriteError",
    "validate_html_for_cache",
    "write_html_to_cache_safely",
]
