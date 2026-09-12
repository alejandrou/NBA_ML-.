from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

METADATA_SUFFIX = ".meta.json"
METADATA_SCHEMA_VERSION = 1


class CacheMetadataError(RuntimeError):
    """Raised when a provenance sidecar exists but cannot be read.

    A *missing* sidecar means "provenance unknown" and is never an error. A
    sidecar that exists and is unreadable is, so corruption is never reported
    as "never fetched".
    """


@dataclass(frozen=True)
class CacheFetchMetadata:
    """Provenance for one page the scraper actually fetched."""

    fetched_at: datetime
    http_status: int
    final_url: str

    def __post_init__(self) -> None:
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            msg = "fetched_at must be timezone-aware"
            raise ValueError(msg)


def serialize_cache_fetch_metadata(metadata: CacheFetchMetadata) -> str:
    """Render one sidecar's JSON body. The single definition of the format."""

    return json.dumps(
        {
            "schema_version": METADATA_SCHEMA_VERSION,
            "fetched_at": metadata.fetched_at.isoformat(),
            "http_status": metadata.http_status,
            "final_url": metadata.final_url,
        },
        indent=2,
        sort_keys=True,
    )


def write_cache_fetch_metadata(path: Path, metadata: CacheFetchMetadata) -> None:
    """Write a sidecar body to `path`, creating parents as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_cache_fetch_metadata(metadata) + "\n", encoding="utf-8")


class HtmlCache:
    """Filesystem cache for raw HTML stored as `.html.gz` files.

    Each body may carry a `<name>.html.gz.meta.json` provenance sidecar. The
    sidecar is an index, not an invariant: `get` and `exists` behave identically
    whether or not one is present, and pages cached before provenance existed
    have none and are never backfilled.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def get(self, url: str) -> str | None:
        path = self.path_for_url(url)
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return file.read()

    def set(self, url: str, html: str, *, metadata: CacheFetchMetadata | None = None) -> Path:
        path = self.path_for_url(url)
        metadata_path = self.metadata_path_for_url(url)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Drop any sidecar for the previous body first, so no window exists in
        # which a stale sidecar describes a body it did not come from.
        metadata_path.unlink(missing_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as file:
            file.write(html)
        if metadata is not None:
            self._write_metadata_atomically(metadata_path, metadata)
        return path

    def get_metadata(self, url: str) -> CacheFetchMetadata | None:
        path = self.metadata_path_for_url(url)
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"Cache metadata sidecar is unreadable: {path}"
            raise CacheMetadataError(msg) from exc
        except UnicodeDecodeError as exc:
            msg = f"Cache metadata sidecar is not valid UTF-8: {path}"
            raise CacheMetadataError(msg) from exc

        try:
            payload = json.loads(raw)
        except ValueError as exc:
            msg = f"Cache metadata sidecar is not valid JSON: {path}"
            raise CacheMetadataError(msg) from exc

        return _metadata_from_payload(payload, path)

    def exists(self, url: str) -> bool:
        return self.path_for_url(url).exists()

    def metadata_path_for_url(self, url: str) -> Path:
        path = self.path_for_url(url)
        return path.with_name(path.name + METADATA_SUFFIX)

    def path_for_url(self, url: str) -> Path:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        if host == "basketball-reference.com":
            host_dir = "basketball-reference"
        else:
            host_dir = _safe_part(host or "unknown-host")

        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        slug_source = f"{parsed.path}-{parsed.query}".strip("-") or "index"
        slug = _safe_part(slug_source).strip("-")[:80] or "index"
        candidate = self.root_dir / host_dir / f"{slug}-{digest[:16]}.html.gz"

        root = self.root_dir.resolve(strict=False)
        resolved = candidate.resolve(strict=False)
        if root not in resolved.parents and resolved != root:
            msg = f"Cache path escaped root: {resolved}"
            raise ValueError(msg)
        return candidate

    @staticmethod
    def _write_metadata_atomically(path: Path, metadata: CacheFetchMetadata) -> None:
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            write_cache_fetch_metadata(temp_path, metadata)
            os.replace(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


def _metadata_from_payload(payload: object, path: Path) -> CacheFetchMetadata:
    if not isinstance(payload, dict):
        msg = f"Cache metadata sidecar must be a JSON object: {path}"
        raise CacheMetadataError(msg)

    # A sidecar this reader does not understand is an error, never "unknown
    # provenance". Refusing it here stops a future shape from being silently
    # reinterpreted as version 1.
    schema_version = payload.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != METADATA_SCHEMA_VERSION
    ):
        msg = (
            f"Cache metadata sidecar has an unsupported schema_version "
            f"{schema_version!r}; this reader only understands "
            f"{METADATA_SCHEMA_VERSION}: {path}"
        )
        raise CacheMetadataError(msg)

    for field in ("fetched_at", "http_status", "final_url"):
        if field not in payload:
            msg = f"Cache metadata sidecar is missing {field!r}: {path}"
            raise CacheMetadataError(msg)

    raw_fetched_at = payload["fetched_at"]
    if not isinstance(raw_fetched_at, str):
        msg = f"Cache metadata sidecar has a non-string 'fetched_at': {path}"
        raise CacheMetadataError(msg)
    try:
        fetched_at = datetime.fromisoformat(raw_fetched_at)
    except ValueError as exc:
        msg = f"Cache metadata sidecar has an unparseable 'fetched_at': {path}"
        raise CacheMetadataError(msg) from exc

    http_status = payload["http_status"]
    if isinstance(http_status, bool) or not isinstance(http_status, int):
        msg = f"Cache metadata sidecar has a non-integer 'http_status': {path}"
        raise CacheMetadataError(msg)

    final_url = payload["final_url"]
    if not isinstance(final_url, str):
        msg = f"Cache metadata sidecar has a non-string 'final_url': {path}"
        raise CacheMetadataError(msg)

    try:
        return CacheFetchMetadata(
            fetched_at=fetched_at,
            http_status=http_status,
            final_url=final_url,
        )
    except ValueError as exc:
        msg = f"Cache metadata sidecar has a naive 'fetched_at': {path}"
        raise CacheMetadataError(msg) from exc


def _safe_part(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
