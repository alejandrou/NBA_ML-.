from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import CachedHtmlInventory, build_cached_html_inventory
from nba_data.scraping.offline_loader import (
    OfflineTeamSeasonLoadReport,
    load_offline_team_season_report,
)
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
    OfflineTeamSeasonSource,
    process_offline_team_season_sources,
)
from nba_data.scraping.offline_reporting import (
    OfflineTeamSeasonAuditReport,
    build_offline_team_season_audit_report,
)
from nba_data.validation.team_season import DataQualityIssue

TEAM_NAME_OVERRIDE_DISAGREEMENT = "team_name_override_disagreement"


@dataclass(frozen=True)
class OfflineBackfillReport:
    inventory: CachedHtmlInventory
    selected_inventory_entries: int
    skipped_inventory_entries: int
    processing_report: OfflineTeamSeasonProcessingReport
    load_report: OfflineTeamSeasonLoadReport
    audit_report: OfflineTeamSeasonAuditReport

    def to_dict(self) -> dict[str, object]:
        return {
            "total_inventory_entries": self.inventory.total_discovered_files,
            "selected_inventory_entries": self.selected_inventory_entries,
            "skipped_inventory_entries": self.skipped_inventory_entries,
            "inventory": self.inventory.to_dict(),
            "processing_report": self.processing_report.to_dict(),
            "load_report": self.load_report.to_dict(),
            "audit_report": self.audit_report.to_dict(),
        }


def build_offline_team_season_sources_from_inventory(
    inventory: CachedHtmlInventory,
) -> tuple[OfflineTeamSeasonSource, ...]:
    """Create processor inputs from valid cached inventory entries only."""

    return tuple(
        OfflineTeamSeasonSource.from_path(
            entry.cache_path,
            team_abbreviation=_required_team_abbreviation(entry.team_abbreviation),
            season_year=_required_season_year(entry.season_year),
        )
        for entry in inventory.entries
        if entry.status == "valid"
    )


def run_full_offline_backfill(
    *,
    cache: HtmlCache,
    session: Session,
    max_workers: int = 1,
    required_tables: set[str] | None = None,
    require_stable_player_id: bool = True,
    league: str = "NBA",
    team_name_by_source: Mapping[tuple[str, int], str] | None = None,
) -> OfflineBackfillReport:
    """Run the Phase 4D offline inventory -> process -> load -> audit chain."""

    inventory = build_cached_html_inventory(cache=cache)
    sources = build_offline_team_season_sources_from_inventory(inventory)
    processing_report = process_offline_team_season_sources(
        sources,
        cache=cache,
        max_workers=max_workers,
        required_tables=required_tables,
        require_stable_player_id=require_stable_player_id,
    )
    processing_report, effective_team_name_by_source = _resolve_team_names(
        processing_report,
        caller_team_name_by_source=team_name_by_source,
    )
    load_report = load_offline_team_season_report(
        session,
        processing_report,
        league=league,
        team_name_by_source=effective_team_name_by_source,
    )
    audit_report = build_offline_team_season_audit_report(processing_report, load_report)

    return OfflineBackfillReport(
        inventory=inventory,
        selected_inventory_entries=len(sources),
        skipped_inventory_entries=inventory.total_discovered_files - len(sources),
        processing_report=processing_report,
        load_report=load_report,
        audit_report=audit_report,
    )


def _required_team_abbreviation(value: str | None) -> str:
    if value is None:
        msg = "Valid inventory entries must include team_abbreviation."
        raise ValueError(msg)
    return value


def _required_season_year(value: int | None) -> int:
    if value is None:
        msg = "Valid inventory entries must include season_year."
        raise ValueError(msg)
    return value


def _resolve_team_names(
    processing_report: OfflineTeamSeasonProcessingReport,
    *,
    caller_team_name_by_source: Mapping[tuple[str, int], str] | None,
) -> tuple[OfflineTeamSeasonProcessingReport, dict[tuple[str, int], str]]:
    """Merge parsed names with curated values, giving parsed names authority."""

    caller_values = dict(caller_team_name_by_source or {})
    effective_values = dict(caller_values)
    entries: list[OfflineTeamSeasonEntryResult] = []

    for entry in processing_report.entries:
        key = (entry.source.team_abbreviation, entry.source.season_year)
        derived_name = _clean_team_name(entry.team_name)
        caller_name = _clean_team_name(caller_values.get(key))
        entry_issues = entry.team_name_issues

        if derived_name and caller_name and derived_name != caller_name:
            entry_issues = entry_issues + (
                DataQualityIssue(
                    code=TEAM_NAME_OVERRIDE_DISAGREEMENT,
                    message=(
                        f"Derived team name {derived_name!r} disagrees with caller-supplied "
                        f"team name {caller_name!r} for {key[0]} {key[1]}; the derived "
                        "value wins."
                    ),
                    source_table="team_name",
                ),
            )

        if derived_name and entry.status == "validated":
            effective_values[key] = derived_name
        elif caller_name:
            effective_values[key] = caller_name

        entries.append(replace(entry, team_name_issues=entry_issues))

    return replace(processing_report, entries=tuple(entries)), effective_values


def _clean_team_name(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
