"""Shared player-page cache discovery and backfill input validation.

`PLAYER_CACHE_FILE_RE` and `PLAYER_CACHE_LIKE_FILE_RE` are public filename
contracts used by cache discovery and coverage validation. The first recognizes
valid cached player pages; the deliberately looser second recognizes malformed
player-shaped candidates so validation can report rather than silently ignore
them.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path
from typing import Literal

from nba_data.domain.player_id import PLAYER_ID_PATTERN

# The player-id fragment comes from the shared domain leaf so discovery accepts
# every id acquisition is allowed to write, without importing acquisition's own
# module (which pulls in SQLAlchemy, ORM models, and the scraping HTTP client).
# Only the id range is shared; the rest of the cache filename shape stays strict.
PLAYER_CACHE_FILE_RE = re.compile(
    rf"^players-(?P<initial>[a-z])-(?P<player_id>{PLAYER_ID_PATTERN})\.html-[0-9a-f]{{16}}\.html\.gz$",
    re.IGNORECASE,
)
# Looser than `PLAYER_CACHE_FILE_RE`: matches any player-shaped filename
# regardless of whether the id or digest segment is well-formed, mirroring
# `cache_inventory._TEAM_SEASON_LIKE_FILE_RE` — it lets a caller distinguish
# "not a player cache file at all" from "player-shaped but malformed", the way
# team-season candidates get `missing_metadata` instead of silently vanishing.
PLAYER_CACHE_LIKE_FILE_RE = re.compile(r"^players-.*\.html-.*\.html\.gz$", re.IGNORECASE)

PlayerCacheDiscoveryStatus = Literal["ok", "no_matching_pages"]


class PlayerCacheRootNotFoundError(ValueError):
    """Raised when the configured player-page cache root does not exist."""


def validate_backfill_inputs(
    *,
    limit: int | None,
    player: str | None,
    start_year: int | None,
    end_year: int | None,
    parser_version: str,
) -> None:
    """Validate the arguments shared by both player-page backfills."""

    if limit is not None and limit <= 0:
        msg = "limit must be a positive integer"
        raise ValueError(msg)
    if player is not None and not player.strip():
        msg = "player must be a non-empty basketball_reference_player_id"
        raise ValueError(msg)
    if start_year is not None and end_year is not None and start_year > end_year:
        msg = "start_year must be less than or equal to end_year"
        raise ValueError(msg)
    if not parser_version.strip():
        msg = "parser_version is required"
        raise ValueError(msg)


def resolve_player_cache_root(cache_root: Path) -> Path:
    """Return the absolute cache root, refusing to treat a missing root as empty."""

    root = cache_root.resolve(strict=False)
    if not root.is_dir():
        msg = (
            "Player-page cache root does not exist or is not a directory: "
            f"{root}. Check SCRAPER_CACHE_DIR and the working directory."
        )
        raise PlayerCacheRootNotFoundError(msg)
    return root


def discovery_status_for(
    cache_entries: list[tuple[Path, str, str]],
) -> PlayerCacheDiscoveryStatus:
    """Report an existing-but-empty cache root distinctly from a normal run."""

    return "ok" if cache_entries else "no_matching_pages"


def discover_player_cache_entries(
    cache_root: Path,
    *,
    player_identifier: str | None,
) -> list[tuple[Path, str, str]]:
    """Return `(cache_path, player_id, source_url)` for every valid cached player page."""

    root = resolve_player_cache_root(cache_root)

    entries: list[tuple[Path, str, str]] = []
    for path in sorted(
        root.rglob("*.html.gz"),
        key=lambda value: value.resolve(strict=False).as_posix().lower(),
    ):
        resolved = path.resolve(strict=False)
        if root not in resolved.parents and resolved != root:
            continue
        if "basketball-reference" not in resolved.parts:
            continue
        match = PLAYER_CACHE_FILE_RE.fullmatch(path.name)
        if match is None:
            continue

        current_player = match.group("player_id").lower()
        if player_identifier is not None and current_player != player_identifier:
            continue

        source_url = (
            "https://www.basketball-reference.com/players/"
            f"{match.group('initial').lower()}/{current_player}.html"
        )
        if read_cached_gzip(resolved) is None:
            continue
        entries.append((resolved, current_player, source_url))
    return entries


def required_html(path: Path) -> str:
    html = read_cached_gzip(path)
    if html is None:
        msg = f"Cached HTML file is unreadable or empty: {path}"
        raise ValueError(msg)
    return html


def read_cached_gzip(path: Path) -> str | None:
    """Return the decoded, validated HTML content, or None if it is unreadable.

    Returns `None` for a missing/corrupt gzip stream (including one truncated
    mid-stream, which raises `EOFError` rather than `OSError`), invalid UTF-8,
    empty content, or content that does not look like an HTML document — the
    same "is this a candidate at all" contract `cache_inventory._read_html_gzip`
    enforces for team-season pages, so a malformed player page cannot slip
    through as a silently-empty discovery result or crash the build outright.
    """

    try:
        with gzip.open(path, "rt", encoding="utf-8") as file:
            html = file.read()
    except (OSError, UnicodeDecodeError, EOFError):
        return None
    cleaned = html.strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if not (lowered.startswith("<!doctype html") or lowered.startswith("<html")):
        return None
    return cleaned


__all__ = [
    "PlayerCacheDiscoveryStatus",
    "PlayerCacheRootNotFoundError",
    "PLAYER_CACHE_FILE_RE",
    "PLAYER_CACHE_LIKE_FILE_RE",
    "discover_player_cache_entries",
    "discovery_status_for",
    "read_cached_gzip",
    "required_html",
    "resolve_player_cache_root",
    "validate_backfill_inputs",
]
