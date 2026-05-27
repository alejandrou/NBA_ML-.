from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from nba_data.scraping.loaders import (
    TeamSeasonLoadBatch,
    TeamSeasonLoadResult,
    load_team_season_core,
)
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
)


@dataclass(frozen=True)
class OfflineTeamSeasonLoadEntryResult:
    status: Literal["loaded", "skipped", "failed"]
    source_url: str | None
    cache_path: str | None
    team_abbreviation: str
    season_year: int
    input_rows: int = 0
    load_result: TeamSeasonLoadResult | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_url": self.source_url,
            "cache_path": self.cache_path,
            "team_abbreviation": self.team_abbreviation,
            "season_year": self.season_year,
            "input_rows": self.input_rows,
            "load_result": self.load_result.__dict__ if self.load_result is not None else None,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class OfflineTeamSeasonLoadReport:
    total_entries: int
    loaded_entries: int
    skipped_entries: int
    failed_entries: int
    input_rows: int
    loaded_rows: int
    entries: tuple[OfflineTeamSeasonLoadEntryResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_entries": self.total_entries,
            "loaded_entries": self.loaded_entries,
            "skipped_entries": self.skipped_entries,
            "failed_entries": self.failed_entries,
            "input_rows": self.input_rows,
            "loaded_rows": self.loaded_rows,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_offline_team_season_report(
    session: Session,
    processing_report: OfflineTeamSeasonProcessingReport,
    *,
    league: str = "NBA",
    team_name_by_source: Mapping[tuple[str, int], str] | None = None,
) -> OfflineTeamSeasonLoadReport:
    """Load validated offline processor entries through idempotent core loaders."""

    results = tuple(
        _load_one_entry(
            session,
            entry,
            league=league,
            team_name_by_source=team_name_by_source or {},
        )
        for entry in processing_report.entries
    )
    return _build_report(results)


def _load_one_entry(
    session: Session,
    entry: OfflineTeamSeasonEntryResult,
    *,
    league: str,
    team_name_by_source: Mapping[tuple[str, int], str],
) -> OfflineTeamSeasonLoadEntryResult:
    if entry.status != "validated":
        return _entry_result(
            entry,
            status="skipped",
            error_message=entry.error_message or "Processor entry was not validated.",
        )

    rows = list(entry.normalized_rows)
    batch = TeamSeasonLoadBatch(
        league=league,
        season_year=entry.source.season_year,
        team_abbreviation=entry.source.team_abbreviation,
        team_name=team_name_by_source.get(
            (entry.source.team_abbreviation, entry.source.season_year)
        ),
        rows=rows,
    )

    try:
        with session.begin_nested():
            load_result = load_team_season_core(session, batch)
    except Exception as exc:
        return _entry_result(
            entry,
            status="failed",
            input_rows=len(rows),
            error_message=str(exc),
        )

    return _entry_result(
        entry,
        status="loaded",
        input_rows=len(rows),
        load_result=load_result,
    )


def _entry_result(
    entry: OfflineTeamSeasonEntryResult,
    *,
    status: Literal["loaded", "skipped", "failed"],
    input_rows: int = 0,
    load_result: TeamSeasonLoadResult | None = None,
    error_message: str | None = None,
) -> OfflineTeamSeasonLoadEntryResult:
    return OfflineTeamSeasonLoadEntryResult(
        status=status,
        source_url=entry.source.url,
        cache_path=entry.source.cache_path,
        team_abbreviation=entry.source.team_abbreviation,
        season_year=entry.source.season_year,
        input_rows=input_rows,
        load_result=load_result,
        error_message=error_message,
    )


def _build_report(
    entries: tuple[OfflineTeamSeasonLoadEntryResult, ...],
) -> OfflineTeamSeasonLoadReport:
    return OfflineTeamSeasonLoadReport(
        total_entries=len(entries),
        loaded_entries=sum(entry.status == "loaded" for entry in entries),
        skipped_entries=sum(entry.status == "skipped" for entry in entries),
        failed_entries=sum(entry.status == "failed" for entry in entries),
        input_rows=sum(entry.input_rows for entry in entries),
        loaded_rows=sum(
            entry.load_result.input_rows
            for entry in entries
            if entry.load_result is not None
        ),
        entries=entries,
    )
