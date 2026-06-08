from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from sqlalchemy.orm import Session

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import (
    CachedHtmlInventoryEntry,
    build_cached_html_inventory,
)
from nba_data.scraping.loaders import TeamSeasonStatsLoadReport, load_team_season_stats
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonSource,
    process_offline_team_season_sources,
)

DEFAULT_STATS_PARSER_VERSION = "team-season-parser-v1"
_TEAM_ABBREVIATION_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class OfflineStatsBackfillEntry:
    team_abbreviation: str | None
    season_year: int | None
    source_url: str | None
    cache_path: str | None
    status: Literal["loaded", "skipped", "failed"]
    processing_status: str | None
    loaded_rows: int
    skipped_rows: int
    failed_rows: int
    quarantined_rows: int = 0
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "team_abbreviation": self.team_abbreviation,
            "season_year": self.season_year,
            "source_url": self.source_url,
            "cache_path": self.cache_path,
            "status": self.status,
            "processing_status": self.processing_status,
            "loaded_rows": self.loaded_rows,
            "skipped_rows": self.skipped_rows,
            "failed_rows": self.failed_rows,
            "quarantined_rows": self.quarantined_rows,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OfflineStatsBackfillReport:
    total_inventory_entries: int
    valid_inventory_entries: int
    selected_sources: int
    processed_sources: int
    processing_failed_sources: int
    stats_loaded_rows: int
    stats_skipped_rows: int
    stats_failed_rows: int
    stats_quarantined_rows: int
    inventory_seconds: float
    processing_seconds: float
    loading_seconds: float
    total_seconds: float
    entries: tuple[OfflineStatsBackfillEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_inventory_entries": self.total_inventory_entries,
            "valid_inventory_entries": self.valid_inventory_entries,
            "selected_sources": self.selected_sources,
            "processed_sources": self.processed_sources,
            "processing_failed_sources": self.processing_failed_sources,
            "stats_loaded_rows": self.stats_loaded_rows,
            "stats_skipped_rows": self.stats_skipped_rows,
            "stats_failed_rows": self.stats_failed_rows,
            "stats_quarantined_rows": self.stats_quarantined_rows,
            "inventory_seconds": self.inventory_seconds,
            "processing_seconds": self.processing_seconds,
            "loading_seconds": self.loading_seconds,
            "total_seconds": self.total_seconds,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def run_offline_stats_backfill(
    session: Session,
    *,
    cache: HtmlCache,
    max_workers: int = 1,
    limit: int | None = None,
    team: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    parser_version: str = DEFAULT_STATS_PARSER_VERSION,
) -> OfflineStatsBackfillReport:
    """Run cache-only team-season processing into official wide stats tables."""

    total_start = perf_counter()
    normalized_team = _normalize_team_filter(team)
    _validate_inputs(
        max_workers=max_workers,
        limit=limit,
        start_year=start_year,
        end_year=end_year,
        parser_version=parser_version,
    )

    inventory_start = perf_counter()
    inventory = build_cached_html_inventory(cache=cache)
    inventory_seconds = perf_counter() - inventory_start

    selected_entries = _select_inventory_entries(
        inventory.entries,
        team=normalized_team,
        start_year=start_year,
        end_year=end_year,
        limit=limit,
    )
    sources = tuple(_source_from_inventory_entry(entry) for entry in selected_entries)

    processing_start = perf_counter()
    processing_report = process_offline_team_season_sources(
        sources,
        cache=cache,
        max_workers=max_workers,
    )
    processing_seconds = perf_counter() - processing_start

    loading_start = perf_counter()
    entries = _load_processed_entries(
        session,
        selected_entries=selected_entries,
        processed_entries=processing_report.entries,
        parser_version=parser_version,
    )
    loading_seconds = perf_counter() - loading_start

    return OfflineStatsBackfillReport(
        total_inventory_entries=inventory.total_discovered_files,
        valid_inventory_entries=inventory.valid_candidates,
        selected_sources=len(selected_entries),
        processed_sources=processing_report.total_inputs,
        processing_failed_sources=processing_report.failed_entries,
        stats_loaded_rows=sum(entry.loaded_rows for entry in entries),
        stats_skipped_rows=sum(entry.skipped_rows for entry in entries),
        stats_failed_rows=sum(entry.failed_rows for entry in entries),
        stats_quarantined_rows=sum(entry.quarantined_rows for entry in entries),
        inventory_seconds=inventory_seconds,
        processing_seconds=processing_seconds,
        loading_seconds=loading_seconds,
        total_seconds=perf_counter() - total_start,
        entries=entries,
    )


def _validate_inputs(
    *,
    max_workers: int,
    limit: int | None,
    start_year: int | None,
    end_year: int | None,
    parser_version: str,
) -> None:
    if max_workers < 1:
        msg = "max_workers must be at least 1"
        raise ValueError(msg)
    if limit is not None and limit <= 0:
        msg = "limit must be a positive integer"
        raise ValueError(msg)
    if start_year is not None and end_year is not None and start_year > end_year:
        msg = "start_year must be less than or equal to end_year"
        raise ValueError(msg)
    if not parser_version.strip():
        msg = "parser_version is required"
        raise ValueError(msg)


def _normalize_team_filter(team: str | None) -> str | None:
    if team is None:
        return None
    normalized = team.strip().upper()
    if not normalized:
        msg = "team must be a non-empty three-letter team code"
        raise ValueError(msg)
    if normalized == "TOT":
        msg = "TOT is an aggregate marker, not a real team"
        raise ValueError(msg)
    if _TEAM_ABBREVIATION_RE.fullmatch(normalized) is None:
        msg = "team must be a three-letter team code"
        raise ValueError(msg)
    return normalized


def _select_inventory_entries(
    entries: tuple[CachedHtmlInventoryEntry, ...],
    *,
    team: str | None,
    start_year: int | None,
    end_year: int | None,
    limit: int | None,
) -> tuple[CachedHtmlInventoryEntry, ...]:
    selected = [
        entry
        for entry in entries
        if entry.status == "valid"
        and (team is None or entry.team_abbreviation == team)
        and (start_year is None or _required_season_year(entry) >= start_year)
        and (end_year is None or _required_season_year(entry) <= end_year)
    ]
    selected.sort(
        key=lambda entry: (
            _required_season_year(entry),
            _required_team_abbreviation(entry),
            entry.cache_path,
        )
    )
    if limit is not None:
        selected = selected[:limit]
    return tuple(selected)


def _source_from_inventory_entry(entry: CachedHtmlInventoryEntry) -> OfflineTeamSeasonSource:
    return OfflineTeamSeasonSource.from_path(
        entry.cache_path,
        team_abbreviation=_required_team_abbreviation(entry),
        season_year=_required_season_year(entry),
    )


def _load_processed_entries(
    session: Session,
    *,
    selected_entries: tuple[CachedHtmlInventoryEntry, ...],
    processed_entries: tuple[OfflineTeamSeasonEntryResult, ...],
    parser_version: str,
) -> tuple[OfflineStatsBackfillEntry, ...]:
    return tuple(
        _load_one_processed_entry(
            session,
            inventory_entry=inventory_entry,
            processed_entry=processed_entry,
            parser_version=parser_version,
        )
        for inventory_entry, processed_entry in zip(selected_entries, processed_entries, strict=True)
    )


def _load_one_processed_entry(
    session: Session,
    *,
    inventory_entry: CachedHtmlInventoryEntry,
    processed_entry: OfflineTeamSeasonEntryResult,
    parser_version: str,
) -> OfflineStatsBackfillEntry:
    source_url = _required_source_url(inventory_entry)
    cache_path = processed_entry.source.cache_path or inventory_entry.cache_path

    if processed_entry.status != "validated":
        return OfflineStatsBackfillEntry(
            team_abbreviation=processed_entry.source.team_abbreviation,
            season_year=processed_entry.source.season_year,
            source_url=source_url,
            cache_path=cache_path,
            status="failed",
            processing_status=processed_entry.status,
            loaded_rows=0,
            skipped_rows=0,
            failed_rows=0,
            quarantined_rows=len(processed_entry.quarantined_rows),
            reason=processed_entry.error_message or "Offline processing failed.",
        )

    try:
        with session.begin_nested():
            load_report = load_team_season_stats(
                session,
                processed_entry.normalized_rows,
                source_url=source_url,
                cache_path=cache_path,
                parser_version=parser_version,
            )
    except Exception as exc:
        return OfflineStatsBackfillEntry(
            team_abbreviation=processed_entry.source.team_abbreviation,
            season_year=processed_entry.source.season_year,
            source_url=source_url,
            cache_path=cache_path,
            status="failed",
            processing_status=processed_entry.status,
            loaded_rows=0,
            skipped_rows=0,
            failed_rows=len(processed_entry.normalized_rows),
            quarantined_rows=len(processed_entry.normalized_rows),
            reason=str(exc),
        )

    return _entry_from_load_report(
        processed_entry=processed_entry,
        source_url=source_url,
        cache_path=cache_path,
        load_report=load_report,
    )


def _entry_from_load_report(
    *,
    processed_entry: OfflineTeamSeasonEntryResult,
    source_url: str,
    cache_path: str,
    load_report: TeamSeasonStatsLoadReport,
) -> OfflineStatsBackfillEntry:
    if load_report.failed_rows:
        status: Literal["loaded", "skipped", "failed"] = "failed"
        reason = "Stats loader reported failed rows."
    elif load_report.loaded_rows:
        status = "loaded"
        reason = None
    else:
        status = "skipped"
        reason = "Stats loader did not load any rows."

    return OfflineStatsBackfillEntry(
        team_abbreviation=processed_entry.source.team_abbreviation,
        season_year=processed_entry.source.season_year,
        source_url=source_url,
        cache_path=cache_path,
        status=status,
        processing_status=processed_entry.status,
        loaded_rows=load_report.loaded_rows,
        skipped_rows=load_report.skipped_rows,
        failed_rows=load_report.failed_rows,
        quarantined_rows=load_report.failed_rows,
        reason=reason,
    )


def _required_team_abbreviation(entry: CachedHtmlInventoryEntry) -> str:
    if entry.team_abbreviation is None:
        msg = "Valid inventory entries must include team_abbreviation."
        raise ValueError(msg)
    return entry.team_abbreviation


def _required_season_year(entry: CachedHtmlInventoryEntry) -> int:
    if entry.season_year is None:
        msg = "Valid inventory entries must include season_year."
        raise ValueError(msg)
    return entry.season_year


def _required_source_url(entry: CachedHtmlInventoryEntry) -> str:
    if entry.source_url is None:
        msg = "Valid inventory entries must include source_url."
        raise ValueError(msg)
    return entry.source_url


__all__ = [
    "DEFAULT_STATS_PARSER_VERSION",
    "OfflineStatsBackfillEntry",
    "OfflineStatsBackfillReport",
    "run_offline_stats_backfill",
]
