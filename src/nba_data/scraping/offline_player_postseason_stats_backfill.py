from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from sqlalchemy.orm import Session

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.loaders.player_page_stats import load_player_page_stats
from nba_data.scraping.normalizers.player_page import normalize_player_page_postseason
from nba_data.scraping.offline_player_stats_backfill import (
    PlayerCacheDiscoveryStatus,
    _discover_player_cache_entries,
    _required_html,
    _validate_inputs,
    discovery_status_for,
    resolve_player_cache_root,
)
from nba_data.scraping.parsers.player_page import parse_player_page_postseason

# The version stamped on rows this backfill writes. Tracks the regular-season
# lineage in `offline_player_stats_backfill.py`, which documents each bump:
#
#   v2  fixes the `YYYY-YY` century rollover in `_season_end_year` (F4E-013).
#   v3  treats any multi-team marker semantically (F4E-014).
#   v4  keeps `Did not play - ...` placeholder rows out of full-season
#       selection (F4E-022), matching regular-season parser lineage.
DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION = "player-page-postseason-parser-v4"


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

    return OfflinePlayerPostseasonStatsBackfillReport(
        player_pages_processed=len(entries),
        postseason_tables_parsed=sum(entry.tables_parsed for entry in entries),
        aggregate_rows_loaded_or_updated=sum(entry.aggregate_rows_loaded_or_updated for entry in entries),
        team_rows_loaded_or_updated=sum(entry.team_rows_loaded_or_updated for entry in entries),
        rows_skipped=sum(entry.rows_skipped for entry in entries),
        entries_failed=sum(entry.status == "failed" for entry in entries),
        rows_failed=sum(entry.rows_failed for entry in entries),
        unresolved_players_or_seasons_or_team_stints=sum(entry.unresolved_rows for entry in entries),
        unsupported_synthetic_or_tot_rows=sum(entry.unsupported_rows for entry in entries),
        cache_root=str(cache_root),
        discovery_status=discovery_status,
        elapsed_seconds=perf_counter() - started,
        entries=entries,
    )


def _process_one_player_page(
    session: Session,
    *,
    cache_path: object,
    player_identifier: str,
    source_url: str,
    start_year: int | None,
    end_year: int | None,
    parser_version: str,
) -> OfflinePlayerPostseasonStatsBackfillEntry:
    try:
        html = _required_html(cache_path)
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
    unresolved_rows = sum(
        entry.reason in {"missing_player", "missing_season", "missing_player_season", "missing_team_season", "missing_player_team_season"}
        for entry in load_report.entries
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
        unresolved_rows=unresolved_rows,
        unsupported_rows=normalized.unsupported_rows,
        reason=reason,
    )


__all__ = [
    "DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION",
    "OfflinePlayerPostseasonStatsBackfillEntry",
    "OfflinePlayerPostseasonStatsBackfillReport",
    "run_offline_player_postseason_stats_backfill",
]
