from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from nba_data.scraping.offline_loader import OfflineTeamSeasonLoadReport
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
)
from nba_data.validation.team_season import DataQualityIssue


@dataclass(frozen=True)
class OfflineTeamSeasonQuarantineEntry:
    reason: Literal["validation_failed", "processing_failed", "loading_failed"]
    source_url: str | None
    cache_path: str | None
    team_abbreviation: str
    season_year: int
    row_count: int
    rows: tuple[dict[str, Any], ...] = ()
    validation_issues: tuple[DataQualityIssue, ...] = ()
    error_message: str | None = None
    retry_hint: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason,
            "source_url": self.source_url,
            "cache_path": self.cache_path,
            "team_abbreviation": self.team_abbreviation,
            "season_year": self.season_year,
            "row_count": self.row_count,
            "rows": list(self.rows),
            "validation_issues": [_issue_to_dict(issue) for issue in self.validation_issues],
            "error_message": self.error_message,
            "retry_hint": self.retry_hint,
        }


@dataclass(frozen=True)
class OfflineTeamSeasonAuditReport:
    total_sources: int
    parsed_rows: int
    validated_rows: int
    loaded_rows: int
    skipped_rows: int
    quarantined_rows: int
    loaded_entries: int
    skipped_entries: int
    failed_entries: int
    quarantined_entries: int
    quarantine_entries: tuple[OfflineTeamSeasonQuarantineEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_sources": self.total_sources,
            "parsed_rows": self.parsed_rows,
            "validated_rows": self.validated_rows,
            "loaded_rows": self.loaded_rows,
            "skipped_rows": self.skipped_rows,
            "quarantined_rows": self.quarantined_rows,
            "loaded_entries": self.loaded_entries,
            "skipped_entries": self.skipped_entries,
            "failed_entries": self.failed_entries,
            "quarantined_entries": self.quarantined_entries,
            "quarantine_entries": [entry.to_dict() for entry in self.quarantine_entries],
        }


def build_offline_team_season_audit_report(
    processing_report: OfflineTeamSeasonProcessingReport,
    load_report: OfflineTeamSeasonLoadReport | None = None,
) -> OfflineTeamSeasonAuditReport:
    """Build a retry-oriented report from offline processing and loading results."""

    quarantine_entries = _processing_quarantines(processing_report)
    if load_report is not None:
        quarantine_entries += _load_quarantines(load_report)

    return OfflineTeamSeasonAuditReport(
        total_sources=processing_report.total_inputs,
        parsed_rows=sum(entry.parsed_row_count for entry in processing_report.entries),
        validated_rows=processing_report.validated_row_count,
        loaded_rows=load_report.loaded_rows if load_report is not None else 0,
        skipped_rows=_skipped_rows(load_report),
        quarantined_rows=sum(entry.row_count for entry in quarantine_entries),
        loaded_entries=load_report.loaded_entries if load_report is not None else 0,
        skipped_entries=load_report.skipped_entries if load_report is not None else 0,
        failed_entries=load_report.failed_entries if load_report is not None else 0,
        quarantined_entries=len(quarantine_entries),
        quarantine_entries=quarantine_entries,
    )


def _processing_quarantines(
    processing_report: OfflineTeamSeasonProcessingReport,
) -> tuple[OfflineTeamSeasonQuarantineEntry, ...]:
    return tuple(
        _processing_quarantine(entry)
        for entry in processing_report.entries
        if entry.status == "failed"
    )


def _processing_quarantine(
    entry: OfflineTeamSeasonEntryResult,
) -> OfflineTeamSeasonQuarantineEntry:
    reason: Literal["validation_failed", "processing_failed"] = (
        "validation_failed" if entry.validation_issues else "processing_failed"
    )
    return OfflineTeamSeasonQuarantineEntry(
        reason=reason,
        source_url=entry.source.url,
        cache_path=entry.source.cache_path,
        team_abbreviation=entry.source.team_abbreviation,
        season_year=entry.source.season_year,
        row_count=len(entry.quarantined_rows),
        rows=entry.quarantined_rows,
        validation_issues=entry.validation_issues,
        error_message=entry.error_message,
        retry_hint=_processing_retry_hint(reason),
    )


def _load_quarantines(
    load_report: OfflineTeamSeasonLoadReport,
) -> tuple[OfflineTeamSeasonQuarantineEntry, ...]:
    return tuple(
        OfflineTeamSeasonQuarantineEntry(
            reason="loading_failed",
            source_url=entry.source_url,
            cache_path=entry.cache_path,
            team_abbreviation=entry.team_abbreviation,
            season_year=entry.season_year,
            row_count=len(entry.quarantined_rows),
            rows=entry.quarantined_rows,
            error_message=entry.error_message,
            retry_hint=(
                "Fix the loader input or database-side issue, then rerun the "
                "same validated report through the idempotent loader path."
            ),
        )
        for entry in load_report.entries
        if entry.status == "failed"
    )


def _skipped_rows(load_report: OfflineTeamSeasonLoadReport | None) -> int:
    if load_report is None:
        return 0
    return sum(entry.input_rows for entry in load_report.entries if entry.status == "skipped")


def _processing_retry_hint(reason: Literal["validation_failed", "processing_failed"]) -> str:
    if reason == "validation_failed":
        return (
            "Fix parser, normalizer, source metadata, or cached HTML input, "
            "then rerun the offline processor before loading."
        )
    return (
        "Fix the cached input or source metadata, then rerun the offline "
        "processor before loading."
    )


def _issue_to_dict(issue: DataQualityIssue) -> dict[str, object]:
    return {
        "code": issue.code,
        "message": issue.message,
        "row_index": issue.row_index,
        "source_table": issue.source_table,
    }
