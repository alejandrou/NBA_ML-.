from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal

from sqlalchemy.orm import Session

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.loaders.player_page_stats import (
    load_player_page_stats,
)
from nba_data.scraping.normalizers.player_page import normalize_player_page_regular_season
from nba_data.scraping.parsers.player_page import parse_player_page_regular_season
from nba_data.scraping.player_page_acquisition import PLAYER_ID_PATTERN

# v2 fixes the `YYYY-YY` century rollover in `_season_end_year` (F4E-013). Rows
# written under v1 carry the wrong `season_year` for century-crossing labels.
DEFAULT_PLAYER_STATS_PARSER_VERSION = "player-page-parser-v2"
# The player-id fragment is imported from acquisition on purpose: discovery must
# accept every id acquisition is allowed to write. Only the id range is shared —
# the rest of the cache filename shape stays strict.
_PLAYER_CACHE_FILE_RE = re.compile(
    rf"^players-(?P<initial>[a-z])-(?P<player_id>{PLAYER_ID_PATTERN})\.html-[0-9a-f]{{16}}\.html\.gz$",
    re.IGNORECASE,
)

PlayerCacheDiscoveryStatus = Literal["ok", "no_matching_pages"]


class PlayerCacheRootNotFoundError(ValueError):
    """Raised when the configured player-page cache root does not exist."""


@dataclass(frozen=True)
class OfflinePlayerStatsBackfillEntry:
    player_identifier: str
    source_url: str
    cache_path: str
    status: Literal["loaded", "skipped", "failed"]
    tables_parsed: int
    rows_selected: int
    rows_skipped: int
    loaded_or_updated_rows: int
    unresolved_rows: int
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "player_identifier": self.player_identifier,
            "source_url": self.source_url,
            "cache_path": self.cache_path,
            "status": self.status,
            "tables_parsed": self.tables_parsed,
            "rows_selected": self.rows_selected,
            "rows_skipped": self.rows_skipped,
            "loaded_or_updated_rows": self.loaded_or_updated_rows,
            "unresolved_rows": self.unresolved_rows,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OfflinePlayerStatsBackfillReport:
    player_pages_processed: int
    tables_parsed: int
    rows_selected: int
    rows_skipped: int
    rows_loaded_or_updated: int
    unresolved_players_or_seasons: int
    cache_root: str
    discovery_status: PlayerCacheDiscoveryStatus
    elapsed_seconds: float
    entries: tuple[OfflinePlayerStatsBackfillEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "player_pages_processed": self.player_pages_processed,
            "tables_parsed": self.tables_parsed,
            "rows_selected": self.rows_selected,
            "rows_skipped": self.rows_skipped,
            "rows_loaded_or_updated": self.rows_loaded_or_updated,
            "unresolved_players_or_seasons": self.unresolved_players_or_seasons,
            "cache_root": self.cache_root,
            "discovery_status": self.discovery_status,
            "elapsed_seconds": self.elapsed_seconds,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def run_offline_player_stats_backfill(
    session: Session,
    *,
    cache: HtmlCache,
    limit: int | None = None,
    player: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    parser_version: str = DEFAULT_PLAYER_STATS_PARSER_VERSION,
) -> OfflinePlayerStatsBackfillReport:
    """Run cache-only player-page processing into regular-season player-season stats tables."""

    _validate_inputs(
        limit=limit,
        player=player,
        start_year=start_year,
        end_year=end_year,
        parser_version=parser_version,
    )
    normalized_player = player.strip().lower() if player else None
    started = perf_counter()

    cache_root = resolve_player_cache_root(cache.root_dir)
    cache_entries = _discover_player_cache_entries(cache_root, player_identifier=normalized_player)
    discovery_status = discovery_status_for(cache_entries)
    if limit is not None:
        cache_entries = cache_entries[:limit]

    entries = tuple(
        _process_one_player_page(
            session,
            cache_path=cache_path,
            player_identifier=player_identifier,
            source_url=source_url,
            start_year=start_year,
            end_year=end_year,
            parser_version=parser_version,
        )
        for cache_path, player_identifier, source_url in cache_entries
    )

    return OfflinePlayerStatsBackfillReport(
        player_pages_processed=len(entries),
        tables_parsed=sum(entry.tables_parsed for entry in entries),
        rows_selected=sum(entry.rows_selected for entry in entries),
        rows_skipped=sum(entry.rows_skipped for entry in entries),
        rows_loaded_or_updated=sum(entry.loaded_or_updated_rows for entry in entries),
        unresolved_players_or_seasons=sum(entry.unresolved_rows for entry in entries),
        cache_root=str(cache_root),
        discovery_status=discovery_status,
        elapsed_seconds=perf_counter() - started,
        entries=entries,
    )


def _validate_inputs(
    *,
    limit: int | None,
    player: str | None,
    start_year: int | None,
    end_year: int | None,
    parser_version: str,
) -> None:
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


def _discover_player_cache_entries(
    cache_root: Path,
    *,
    player_identifier: str | None,
) -> list[tuple[Path, str, str]]:
    root = resolve_player_cache_root(cache_root)

    entries: list[tuple[Path, str, str]] = []
    for path in sorted(root.rglob("*.html.gz"), key=lambda value: value.resolve(strict=False).as_posix().lower()):
        resolved = path.resolve(strict=False)
        if root not in resolved.parents and resolved != root:
            continue
        if "basketball-reference" not in resolved.parts:
            continue
        match = _PLAYER_CACHE_FILE_RE.fullmatch(path.name)
        if match is None:
            continue

        current_player = match.group("player_id").lower()
        if player_identifier is not None and current_player != player_identifier:
            continue

        source_url = (
            "https://www.basketball-reference.com/players/"
            f"{match.group('initial').lower()}/{current_player}.html"
        )
        if _read_cached_gzip(resolved) is None:
            continue
        entries.append((resolved, current_player, source_url))
    return entries


def _process_one_player_page(
    session: Session,
    *,
    cache_path: Path,
    player_identifier: str,
    source_url: str,
    start_year: int | None,
    end_year: int | None,
    parser_version: str,
) -> OfflinePlayerStatsBackfillEntry:
    try:
        html = _required_html(cache_path)
        parsed = parse_player_page_regular_season(html)
        normalized = normalize_player_page_regular_season(
            parsed,
            basketball_reference_player_id=player_identifier,
            start_year=start_year,
            end_year=end_year,
        )
        if not normalized.selected_rows:
            return OfflinePlayerStatsBackfillEntry(
                player_identifier=player_identifier,
                source_url=source_url,
                cache_path=str(cache_path),
                status="skipped",
                tables_parsed=normalized.tables_parsed,
                rows_selected=normalized.rows_selected,
                rows_skipped=normalized.rows_skipped,
                loaded_or_updated_rows=0,
                unresolved_rows=0,
                reason="No supported regular-season aggregate rows were selected.",
            )

        with session.begin_nested():
            load_report = load_player_page_stats(
                session,
                normalized.selected_rows,
                source_url=source_url,
                cache_path=str(cache_path),
                parser_version=parser_version,
            )
    except Exception as exc:
        return OfflinePlayerStatsBackfillEntry(
            player_identifier=player_identifier,
            source_url=source_url,
            cache_path=str(cache_path),
            status="failed",
            tables_parsed=0,
            rows_selected=0,
            rows_skipped=0,
            loaded_or_updated_rows=0,
            unresolved_rows=0,
            reason=str(exc),
        )

    unresolved_rows = sum(
        entry.reason in {"missing_player", "missing_season", "missing_player_season"}
        for entry in load_report.entries
    )
    status: Literal["loaded", "skipped", "failed"]
    if load_report.failed_rows:
        status = "failed"
        reason = "Player-page stats loader reported failed rows."
    elif load_report.loaded_rows:
        status = "loaded"
        reason = None
    else:
        status = "skipped"
        reason = "Player-page stats loader did not load any rows."

    return OfflinePlayerStatsBackfillEntry(
        player_identifier=player_identifier,
        source_url=source_url,
        cache_path=str(cache_path),
        status=status,
        tables_parsed=normalized.tables_parsed,
        rows_selected=normalized.rows_selected,
        rows_skipped=normalized.rows_skipped + load_report.skipped_rows,
        loaded_or_updated_rows=load_report.loaded_rows,
        unresolved_rows=unresolved_rows,
        reason=reason,
    )


def _required_html(path: Path) -> str:
    html = _read_cached_gzip(path)
    if html is None:
        msg = f"Cached HTML file is unreadable or empty: {path}"
        raise ValueError(msg)
    return html


def _read_cached_gzip(path: Path) -> str | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as file:
            html = file.read()
    except OSError:
        return None
    cleaned = html.strip()
    return cleaned if cleaned else None


__all__ = [
    "DEFAULT_PLAYER_STATS_PARSER_VERSION",
    "OfflinePlayerStatsBackfillEntry",
    "OfflinePlayerStatsBackfillReport",
    "PlayerCacheDiscoveryStatus",
    "PlayerCacheRootNotFoundError",
    "discovery_status_for",
    "resolve_player_cache_root",
    "run_offline_player_stats_backfill",
]
