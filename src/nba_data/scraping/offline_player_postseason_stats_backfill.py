from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Literal

from sqlalchemy.orm import Session

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.loaders.player_page_stats import load_player_page_stats
from nba_data.scraping.normalizers.player_page import normalize_player_page_postseason
from nba_data.scraping.parsers.player_page import parse_player_page_postseason
from nba_data.scraping.player_page_cache import (
    PlayerCacheDiscoveryStatus,
    discover_player_cache_entries,
    discovery_status_for,
    required_html,
    resolve_player_cache_root,
    validate_backfill_inputs,
)
from nba_data.scraping.player_page_scope import (
    POSTSEASON_UNRESOLVED_REASONS,
    EmptySeasonScopeError,
    classify_unresolved_rows,
    load_season_scope,
    merge_out_of_scope_reasons,
)
from nba_data.validation.parser_contracts import current_parser_version

# The version stamped on rows this backfill writes. `player_page_postseason`'s
# full lineage — every identifier, what changed, and which task introduced it —
# lives in `nba_data.validation.parser_contracts`, alongside the regular-season
# lineage it tracks.
DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION = current_parser_version("player_page_postseason")


@dataclass(frozen=True)
class OfflinePlayerPostseasonStatsBackfillEntry:
    player_identifier: str
    source_url: str
    cache_path: str
    status: Literal["loaded", "skipped", "failed"]
    tables_parsed: int
    aggregate_rows_selected: int
    team_rows_selected: int
    rows_skipped: int
    aggregate_rows_loaded_or_updated: int
    team_rows_loaded_or_updated: int
    rows_failed: int
    unresolved_rows: int
    unsupported_rows: int
    reason: str | None = None
    out_of_scope_rows: int = 0
    out_of_scope_reasons: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "player_identifier": self.player_identifier,
            "source_url": self.source_url,
            "cache_path": self.cache_path,
            "status": self.status,
            "tables_parsed": self.tables_parsed,
            "aggregate_rows_selected": self.aggregate_rows_selected,
            "team_rows_selected": self.team_rows_selected,
            "rows_skipped": self.rows_skipped,
            "aggregate_rows_loaded_or_updated": self.aggregate_rows_loaded_or_updated,
            "team_rows_loaded_or_updated": self.team_rows_loaded_or_updated,
            "rows_failed": self.rows_failed,
            "unresolved_rows": self.unresolved_rows,
            "unsupported_rows": self.unsupported_rows,
            "reason": self.reason,
            "out_of_scope_rows": self.out_of_scope_rows,
            "out_of_scope_reasons": dict(self.out_of_scope_reasons),
        }


@dataclass(frozen=True)
class OfflinePlayerPostseasonStatsBackfillReport:
    player_pages_processed: int
    postseason_tables_parsed: int
    aggregate_rows_loaded_or_updated: int
    team_rows_loaded_or_updated: int
    rows_skipped: int
    entries_failed: int
    rows_failed: int
    unresolved_players_or_seasons_or_team_stints: int
    unsupported_synthetic_or_tot_rows: int
    cache_root: str
    discovery_status: PlayerCacheDiscoveryStatus
    elapsed_seconds: float
    entries: tuple[OfflinePlayerPostseasonStatsBackfillEntry, ...]
    out_of_scope_players_or_seasons_or_team_stints: int = 0
    out_of_scope_reason_counts: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "player_pages_processed": self.player_pages_processed,
            "postseason_tables_parsed": self.postseason_tables_parsed,
            "aggregate_rows_loaded_or_updated": self.aggregate_rows_loaded_or_updated,
            "team_rows_loaded_or_updated": self.team_rows_loaded_or_updated,
            "rows_skipped": self.rows_skipped,
            "entries_failed": self.entries_failed,
            "rows_failed": self.rows_failed,
            "unresolved_players_or_seasons_or_team_stints": self.unresolved_players_or_seasons_or_team_stints,
            "out_of_scope_players_or_seasons_or_team_stints": self.out_of_scope_players_or_seasons_or_team_stints,
            "out_of_scope_reason_counts": dict(self.out_of_scope_reason_counts),
            "unsupported_synthetic_or_tot_rows": self.unsupported_synthetic_or_tot_rows,
            "cache_root": self.cache_root,
            "discovery_status": self.discovery_status,
            "elapsed_seconds": self.elapsed_seconds,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def run_offline_player_postseason_stats_backfill(
    session: Session,
    *,
    cache: HtmlCache,
    limit: int | None = None,
    player: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    parser_version: str = DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION,
) -> OfflinePlayerPostseasonStatsBackfillReport:
    """Run cache-only player-page postseason backfill into postseason stats tables."""

    validate_backfill_inputs(
        limit=limit,
        player=player,
        start_year=start_year,
        end_year=end_year,
        parser_version=parser_version,
    )
    normalized_player = player.strip().lower() if player else None
    started = perf_counter()

    cache_root = resolve_player_cache_root(cache.root_dir)
    cache_entries = discover_player_cache_entries(cache_root, player_identifier=normalized_player)
    discovery_status = discovery_status_for(cache_entries)
    if limit is not None:
        cache_entries = cache_entries[:limit]
    # Only a run with pages to process depends on the season scope, and only
    # such a run could be misread as a success against an unseeded database.
    loaded_season_years = load_season_scope(session) if cache_entries else frozenset()

    entries = tuple(
        _process_one_player_page(
            session,
            cache_path=cache_path,
            player_identifier=player_identifier,
            source_url=source_url,
            start_year=start_year,
            end_year=end_year,
            parser_version=parser_version,
            loaded_season_years=loaded_season_years,
        )
        for cache_path, player_identifier, source_url in cache_entries
    )

    return OfflinePlayerPostseasonStatsBackfillReport(
        player_pages_processed=len(entries),
        postseason_tables_parsed=sum(entry.tables_parsed for entry in entries),
        aggregate_rows_loaded_or_updated=sum(entry.aggregate_rows_loaded_or_updated for entry in entries),
        team_rows_loaded_or_updated=sum(entry.team_rows_loaded_or_updated for entry in entries),
        rows_skipped=sum(entry.rows_skipped for entry in entries),
        entries_failed=sum(entry.status == "failed" for entry in entries),
        rows_failed=sum(entry.rows_failed for entry in entries),
        unresolved_players_or_seasons_or_team_stints=sum(entry.unresolved_rows for entry in entries),
        out_of_scope_players_or_seasons_or_team_stints=sum(
            entry.out_of_scope_rows for entry in entries
        ),
        out_of_scope_reason_counts=merge_out_of_scope_reasons(
            [entry.out_of_scope_reasons for entry in entries]
        ),
        unsupported_synthetic_or_tot_rows=sum(entry.unsupported_rows for entry in entries),
        cache_root=str(cache_root),
        discovery_status=discovery_status,
        elapsed_seconds=perf_counter() - started,
        entries=entries,
    )


def _process_one_player_page(
    session: Session,
    *,
    cache_path: Path,
    player_identifier: str,
    source_url: str,
    start_year: int | None,
    end_year: int | None,
    parser_version: str,
    loaded_season_years: Collection[int],
) -> OfflinePlayerPostseasonStatsBackfillEntry:
    try:
        html = required_html(cache_path)
        parsed = parse_player_page_postseason(html)
        normalized = normalize_player_page_postseason(
            parsed,
            basketball_reference_player_id=player_identifier,
            start_year=start_year,
            end_year=end_year,
        )
        if not normalized.selected_rows:
            return OfflinePlayerPostseasonStatsBackfillEntry(
                player_identifier=player_identifier,
                source_url=source_url,
                cache_path=str(cache_path),
                status="skipped",
                tables_parsed=normalized.tables_parsed,
                aggregate_rows_selected=0,
                team_rows_selected=0,
                rows_skipped=normalized.rows_skipped,
                aggregate_rows_loaded_or_updated=0,
                team_rows_loaded_or_updated=0,
                rows_failed=0,
                unresolved_rows=0,
                unsupported_rows=normalized.unsupported_rows,
                reason="No supported postseason rows were selected.",
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
        return OfflinePlayerPostseasonStatsBackfillEntry(
            player_identifier=player_identifier,
            source_url=source_url,
            cache_path=str(cache_path),
            status="failed",
            tables_parsed=0,
            aggregate_rows_selected=0,
            team_rows_selected=0,
            rows_skipped=0,
            aggregate_rows_loaded_or_updated=0,
            team_rows_loaded_or_updated=0,
            rows_failed=0,
            unresolved_rows=0,
            unsupported_rows=0,
            reason=str(exc),
        )

    aggregate_rows_loaded = sum(
        entry.status == "loaded" and entry.destination_table is not None and "stats.player_postseason_" in entry.destination_table
        for entry in load_report.entries
    )
    team_rows_loaded = sum(
        entry.status == "loaded" and entry.destination_table is not None and "stats.player_team_postseason_" in entry.destination_table
        for entry in load_report.entries
    )
    aggregate_rows_selected = sum(
        row.get("stat_scope") == "player_postseason_aggregate" for row in normalized.selected_rows
    )
    team_rows_selected = sum(
        row.get("stat_scope") == "player_team_postseason" for row in normalized.selected_rows
    )
    unresolved = classify_unresolved_rows(
        load_report.entries,
        loaded_season_years=loaded_season_years,
        unresolved_reasons=POSTSEASON_UNRESOLVED_REASONS,
    )

    if load_report.failed_rows:
        status: Literal["loaded", "skipped", "failed"] = "failed"
        reason = "Player-page postseason stats loader reported failed rows."
    elif aggregate_rows_loaded or team_rows_loaded:
        status = "loaded"
        reason = None
    else:
        status = "skipped"
        reason = "Player-page postseason stats loader did not load any rows."

    return OfflinePlayerPostseasonStatsBackfillEntry(
        player_identifier=player_identifier,
        source_url=source_url,
        cache_path=str(cache_path),
        status=status,
        tables_parsed=normalized.tables_parsed,
        aggregate_rows_selected=aggregate_rows_selected,
        team_rows_selected=team_rows_selected,
        rows_skipped=normalized.rows_skipped + load_report.skipped_rows,
        aggregate_rows_loaded_or_updated=aggregate_rows_loaded,
        team_rows_loaded_or_updated=team_rows_loaded,
        rows_failed=load_report.failed_rows,
        unresolved_rows=unresolved.in_scope,
        unsupported_rows=normalized.unsupported_rows,
        reason=reason,
        out_of_scope_rows=unresolved.out_of_scope,
        out_of_scope_reasons=unresolved.out_of_scope_reasons,
    )


__all__ = [
    "DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION",
    "EmptySeasonScopeError",
    "OfflinePlayerPostseasonStatsBackfillEntry",
    "OfflinePlayerPostseasonStatsBackfillReport",
    "run_offline_player_postseason_stats_backfill",
]
