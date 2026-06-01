from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.nba_team_season_manifest import build_nba_team_season_manifest

CachedHtmlInventoryStatus = Literal[
    "valid",
    "duplicate",
    "missing_metadata",
    "unsupported_path",
    "invalid_or_unreadable",
]

PAGE_TYPE_TEAM_SEASON = "team_season"
_BASKETBALL_REFERENCE_DIR = "basketball-reference"
_CACHE_TEAM_SEASON_FILE_RE = re.compile(
    r"^teams-(?P<team>[a-z]{3})-(?P<season>[0-9]{4})\.html-[0-9a-f]{16}\.html\.gz$",
    re.IGNORECASE,
)
_TEAM_SEASON_LIKE_FILE_RE = re.compile(r"^teams-.*\.html-.*\.html\.gz$", re.IGNORECASE)


@dataclass(frozen=True)
class CachedHtmlInventoryEntry:
    cache_path: str
    status: CachedHtmlInventoryStatus
    source_url: str | None = None
    is_basketball_reference: bool = False
    team_abbreviation: str | None = None
    season_year: int | None = None
    season_end_year: int | None = None
    page_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_path": self.cache_path,
            "status": self.status,
            "source_url": self.source_url,
            "is_basketball_reference": self.is_basketball_reference,
            "team_abbreviation": self.team_abbreviation,
            "season_year": self.season_year,
            "season_end_year": self.season_end_year,
            "page_type": self.page_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class CachedHtmlInventory:
    cache_root: str
    total_discovered_files: int
    valid_candidates: int
    invalid_or_unreadable_files: int
    duplicate_candidates: int
    missing_metadata: int
    unsupported_paths: int
    entries: tuple[CachedHtmlInventoryEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_root": self.cache_root,
            "total_discovered_files": self.total_discovered_files,
            "valid_candidates": self.valid_candidates,
            "invalid_or_unreadable_files": self.invalid_or_unreadable_files,
            "duplicate_candidates": self.duplicate_candidates,
            "missing_metadata": self.missing_metadata,
            "unsupported_paths": self.unsupported_paths,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def build_cached_html_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
    root = cache.root_dir.resolve(strict=False)
    approved_urls = _approved_team_season_urls()
    seen_candidate_keys: set[tuple[str, int, str]] = set()
    entries: list[CachedHtmlInventoryEntry] = []

    for path in _discover_cached_html_files(cache.root_dir):
        entries.append(
            _inventory_one_path(
                path,
                cache_root=root,
                approved_urls=approved_urls,
                seen_candidate_keys=seen_candidate_keys,
            )
        )

    return _build_inventory(cache_root=root, entries=tuple(entries))


def _discover_cached_html_files(cache_root: Path) -> tuple[Path, ...]:
    if not cache_root.exists():
        return ()
    return tuple(
        sorted(
            cache_root.rglob("*.html.gz"),
            key=lambda path: path.resolve(strict=False).as_posix().lower(),
        )
    )


def _inventory_one_path(
    path: Path,
    *,
    cache_root: Path,
    approved_urls: set[str],
    seen_candidate_keys: set[tuple[str, int, str]],
) -> CachedHtmlInventoryEntry:
    cache_path = str(path)
    resolved_path = path.resolve(strict=False)
    if not _is_under_root(resolved_path, cache_root):
        return CachedHtmlInventoryEntry(
            cache_path=cache_path,
            status="unsupported_path",
            error_message="Cached HTML path resolves outside the cache root.",
        )

    relative_path = _relative_to_root(resolved_path, cache_root)
    is_basketball_reference = _is_basketball_reference_path(relative_path)
    metadata = _infer_metadata(relative_path)

    if not is_basketball_reference:
        return CachedHtmlInventoryEntry(
            cache_path=cache_path,
            status="unsupported_path",
            is_basketball_reference=False,
            error_message="Cached HTML path is not under basketball-reference.",
        )

    if metadata is None:
        status: CachedHtmlInventoryStatus = (
            "missing_metadata"
            if _looks_like_basketball_reference_team_season(relative_path)
            else "unsupported_path"
        )
        return CachedHtmlInventoryEntry(
            cache_path=cache_path,
            status=status,
            is_basketball_reference=True,
            error_message=_metadata_error_message(status),
        )

    if metadata.team_abbreviation == "TOT":
        return _unsupported_metadata_entry(
            cache_path=cache_path,
            metadata=metadata,
            error_message="TOT is an aggregate marker, not a real team.",
        )

    if metadata.source_url not in approved_urls:
        return _unsupported_metadata_entry(
            cache_path=cache_path,
            metadata=metadata,
            error_message="Team-season URL is outside the approved Phase 4D catalog.",
        )

    try:
        _read_html_gzip(path)
    except Exception as exc:
        return CachedHtmlInventoryEntry(
            cache_path=cache_path,
            status="invalid_or_unreadable",
            source_url=metadata.source_url,
            is_basketball_reference=True,
            team_abbreviation=metadata.team_abbreviation,
            season_year=metadata.season_end_year,
            season_end_year=metadata.season_end_year,
            page_type=metadata.page_type,
            error_message=str(exc),
        )

    candidate_key = (
        metadata.team_abbreviation,
        metadata.season_end_year,
        metadata.page_type,
    )
    if candidate_key in seen_candidate_keys:
        return CachedHtmlInventoryEntry(
            cache_path=cache_path,
            status="duplicate",
            source_url=metadata.source_url,
            is_basketball_reference=True,
            team_abbreviation=metadata.team_abbreviation,
            season_year=metadata.season_end_year,
            season_end_year=metadata.season_end_year,
            page_type=metadata.page_type,
            error_message="Duplicate cached team-season candidate.",
        )

    seen_candidate_keys.add(candidate_key)
    return CachedHtmlInventoryEntry(
        cache_path=cache_path,
        status="valid",
        source_url=metadata.source_url,
        is_basketball_reference=True,
        team_abbreviation=metadata.team_abbreviation,
        season_year=metadata.season_end_year,
        season_end_year=metadata.season_end_year,
        page_type=metadata.page_type,
    )


@dataclass(frozen=True)
class _CachedHtmlMetadata:
    team_abbreviation: str
    season_end_year: int
    source_url: str
    page_type: str = PAGE_TYPE_TEAM_SEASON


def _infer_metadata(relative_path: Path) -> _CachedHtmlMetadata | None:
    if not _is_basketball_reference_path(relative_path):
        return None
    match = _CACHE_TEAM_SEASON_FILE_RE.fullmatch(relative_path.name)
    if match is None:
        return None

    team = match.group("team").upper()
    season_end_year = int(match.group("season"))
    return _CachedHtmlMetadata(
        team_abbreviation=team,
        season_end_year=season_end_year,
        source_url=f"https://www.basketball-reference.com/teams/{team}/{season_end_year}.html",
    )


def _read_html_gzip(path: Path) -> str:
    if not path.is_file():
        msg = f"Cached HTML path is not a file: {path}"
        raise FileNotFoundError(msg)

    with gzip.open(path, "rt", encoding="utf-8") as file:
        html = file.read()

    if not html.strip():
        msg = "Cached HTML file is empty."
        raise ValueError(msg)

    lowered = html.lstrip().lower()
    if not (lowered.startswith("<!doctype html") or lowered.startswith("<html")):
        msg = "Cached HTML file does not look like an HTML document."
        raise ValueError(msg)

    return html


def _unsupported_metadata_entry(
    *,
    cache_path: str,
    metadata: _CachedHtmlMetadata,
    error_message: str,
) -> CachedHtmlInventoryEntry:
    return CachedHtmlInventoryEntry(
        cache_path=cache_path,
        status="unsupported_path",
        source_url=metadata.source_url,
        is_basketball_reference=True,
        team_abbreviation=metadata.team_abbreviation,
        season_year=metadata.season_end_year,
        season_end_year=metadata.season_end_year,
        page_type=metadata.page_type,
        error_message=error_message,
    )


def _build_inventory(
    *,
    cache_root: Path,
    entries: tuple[CachedHtmlInventoryEntry, ...],
) -> CachedHtmlInventory:
    return CachedHtmlInventory(
        cache_root=str(cache_root),
        total_discovered_files=len(entries),
        valid_candidates=sum(entry.status == "valid" for entry in entries),
        invalid_or_unreadable_files=sum(
            entry.status == "invalid_or_unreadable" for entry in entries
        ),
        duplicate_candidates=sum(entry.status == "duplicate" for entry in entries),
        missing_metadata=sum(entry.status == "missing_metadata" for entry in entries),
        unsupported_paths=sum(entry.status == "unsupported_path" for entry in entries),
        entries=entries,
    )


def _approved_team_season_urls() -> set[str]:
    manifest = build_nba_team_season_manifest()
    return {entry.url for entry in manifest.entries}


def _is_basketball_reference_path(relative_path: Path) -> bool:
    return bool(relative_path.parts) and relative_path.parts[0] == _BASKETBALL_REFERENCE_DIR


def _looks_like_basketball_reference_team_season(relative_path: Path) -> bool:
    return (
        _is_basketball_reference_path(relative_path)
        and _TEAM_SEASON_LIKE_FILE_RE.fullmatch(relative_path.name) is not None
    )


def _relative_to_root(path: Path, cache_root: Path) -> Path:
    try:
        return path.relative_to(cache_root)
    except ValueError:
        return path


def _is_under_root(path: Path, cache_root: Path) -> bool:
    return path == cache_root or cache_root in path.parents


def _metadata_error_message(status: CachedHtmlInventoryStatus) -> str:
    if status == "missing_metadata":
        return "Basketball Reference team-season cache path is missing team or season metadata."
    return "Basketball Reference cache path is not a supported team-season page."
