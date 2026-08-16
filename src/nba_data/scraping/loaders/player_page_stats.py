from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from nba_data.db.models import Player, PlayerSeason, PlayerTeamSeason, Season, TeamSeason
from nba_data.db.repositories import StatsRepository
from nba_data.domain.team_codes import is_aggregate_only_team_code, is_synthetic_team_code
from nba_data.scraping.loaders.team_season_stats import (
    PLAYER_SEASON_ROUTES,
    POSTSEASON_PLAYER_SEASON_ROUTES,
    POSTSEASON_TEAM_STINT_ROUTES,
    _optional_string,
    _stats_values,
)

PlayerPageStatsLoadStatus = Literal["loaded", "skipped", "failed"]


@dataclass(frozen=True)
class PlayerPageStatsLoadEntry:
    row_index: int
    status: PlayerPageStatsLoadStatus
    reason: str
    source_table: str | None = None
    season_year: int | None = None
    source_team_code: str | None = None
    team_abbreviation: str | None = None
    player_identifier: str | None = None
    destination_table: str | None = None
    grain_id: int | None = None
    stats_row_id: int | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "row_index": self.row_index,
            "status": self.status,
            "reason": self.reason,
            "source_table": self.source_table,
            "season_year": self.season_year,
            "source_team_code": self.source_team_code,
            "team_abbreviation": self.team_abbreviation,
            "player_identifier": self.player_identifier,
            "destination_table": self.destination_table,
            "grain_id": self.grain_id,
            "stats_row_id": self.stats_row_id,
            "message": self.message,
        }


@dataclass(frozen=True)
class PlayerPageStatsLoadReport:
    total_rows: int
    loaded_rows: int
    skipped_rows: int
    failed_rows: int
    entries: tuple[PlayerPageStatsLoadEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_rows": self.total_rows,
            "loaded_rows": self.loaded_rows,
            "skipped_rows": self.skipped_rows,
            "failed_rows": self.failed_rows,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class _PreparedPlayerStatsWrite:
    row_index: int
    source_table: str
    stat_scope: str
    season_year: int
    source_team_code: str | None
    team_abbreviation: str | None
    player_identifier: str
    destination_table: str
    grain_id: int
    grain_column: str
    values: Mapping[str, Any]
    route_method_name: str

    @property
    def duplicate_key(self) -> tuple[str, int]:
        return (self.destination_table, self.grain_id)


def load_player_page_stats(
    session: Session,
    rows: Iterable[Mapping[str, Any]],
    *,
    source_url: str,
    cache_path: str,
    parser_version: str,
) -> PlayerPageStatsLoadReport:
    """Load normalized player-page regular-season or postseason stats rows."""

    normalized_rows = tuple(rows)
    entries_by_index: dict[int, PlayerPageStatsLoadEntry] = {}
    prepared_writes: list[_PreparedPlayerStatsWrite] = []

    for index, row in enumerate(normalized_rows):
        prepared_or_entry = _prepare_row(session, row, index)
        if isinstance(prepared_or_entry, PlayerPageStatsLoadEntry):
            entries_by_index[index] = prepared_or_entry
        else:
            prepared_writes.append(prepared_or_entry)

    duplicate_keys = {
        key for key, count in Counter(write.duplicate_key for write in prepared_writes).items() if count > 1
    }
    for write in prepared_writes:
        if write.duplicate_key in duplicate_keys:
            entries_by_index[write.row_index] = _entry_from_write(
                write,
                status="failed",
                reason="duplicate_stats_grain",
                message=(
                    "Multiple normalized rows target "
                    f"{write.destination_table} grain_id={write.grain_id}."
                ),
            )

    repository = StatsRepository(session)
    for write in prepared_writes:
        if write.row_index in entries_by_index:
            continue
        try:
            with session.begin_nested():
                method = getattr(repository, write.route_method_name)
                if write.grain_column == "player_season_id":
                    record = method(
                        player_season_id=write.grain_id,
                        values=write.values,
                        source_url=source_url,
                        cache_path=cache_path,
                        parser_version=parser_version,
                    )
                else:
                    record = method(
                        player_team_season_id=write.grain_id,
                        values=write.values,
                        source_url=source_url,
                        cache_path=cache_path,
                        parser_version=parser_version,
                    )
        except Exception as exc:
            entries_by_index[write.row_index] = _entry_from_write(
                write,
                status="failed",
                reason="repository_error",
                message=str(exc),
            )
        else:
            entries_by_index[write.row_index] = _entry_from_write(
                write,
                status="loaded",
                reason="loaded",
                stats_row_id=getattr(record, "id", None),
            )

    entries = tuple(entries_by_index[index] for index in range(len(normalized_rows)))
    counts = Counter(entry.status for entry in entries)
    return PlayerPageStatsLoadReport(
        total_rows=len(normalized_rows),
        loaded_rows=counts["loaded"],
        skipped_rows=counts["skipped"],
        failed_rows=counts["failed"],
        entries=entries,
    )


def _prepare_row(
    session: Session,
    row: Mapping[str, Any],
    row_index: int,
) -> _PreparedPlayerStatsWrite | PlayerPageStatsLoadEntry:
    source_table = _optional_string(row.get("source_table"))
    stat_scope = _optional_string(row.get("stat_scope"))
    player_identifier = _optional_string(row.get("basketball_reference_player_id"))
    source_team_code = _optional_string(row.get("source_team_code"))
    team_abbreviation = _optional_string(row.get("team_abbreviation"))
    season_year = row.get("season_year")

    if source_table is None:
        return _entry_from_row(row, row_index, "failed", "missing_source_table")
    if stat_scope is None:
        return _entry_from_row(row, row_index, "failed", "missing_stat_scope")
    if player_identifier is None:
        return _entry_from_row(row, row_index, "failed", "missing_player_id")
    if not isinstance(season_year, int):
        return _entry_from_row(row, row_index, "failed", "invalid_season_year")

    route = _route_for_row(source_table=source_table, stat_scope=stat_scope)
    if route is None:
        return _entry_from_row(row, row_index, "skipped", "unsupported_source_table")

    values = row.get("values")
    if not isinstance(values, Mapping):
        return _entry_from_row(row, row_index, "failed", "invalid_values")

    try:
        stats_values = _stats_values(values=values, columns=route.columns, model=route.model)
    except ValueError as exc:
        return _entry_from_row(row, row_index, "failed", "invalid_values", message=str(exc))

    if route.aggregate:
        if source_team_code is None:
            return _entry_from_row(row, row_index, "failed", "missing_source_team_code")
        if is_aggregate_only_team_code(source_team_code):
            return _entry_from_row(row, row_index, "skipped", "invalid_source_team_code")
        stats_values["source_team_code"] = source_team_code
        grain_id_or_entry = _resolve_player_season_id(session, row=row, row_index=row_index)
        if isinstance(grain_id_or_entry, PlayerPageStatsLoadEntry):
            return grain_id_or_entry
        return _PreparedPlayerStatsWrite(
            row_index=row_index,
            source_table=source_table,
            stat_scope=stat_scope,
            season_year=season_year,
            source_team_code=source_team_code,
            team_abbreviation=team_abbreviation,
            player_identifier=player_identifier,
            destination_table=route.destination_table,
            grain_id=grain_id_or_entry,
            grain_column="player_season_id",
            values=stats_values,
            route_method_name=route.method_name,
        )

    if team_abbreviation is None:
        return _entry_from_row(row, row_index, "failed", "missing_team_abbreviation")
    if is_synthetic_team_code(team_abbreviation):
        return _entry_from_row(row, row_index, "skipped", "invalid_team_stint_source_team_code")
    grain_id_or_entry = _resolve_player_team_season_id(session, row=row, row_index=row_index)
    if isinstance(grain_id_or_entry, PlayerPageStatsLoadEntry):
        return grain_id_or_entry
    return _PreparedPlayerStatsWrite(
        row_index=row_index,
        source_table=source_table,
        stat_scope=stat_scope,
        season_year=season_year,
        source_team_code=source_team_code,
        team_abbreviation=team_abbreviation,
        player_identifier=player_identifier,
        destination_table=route.destination_table,
        grain_id=grain_id_or_entry,
        grain_column="player_team_season_id",
        values=stats_values,
        route_method_name=route.method_name,
    )


def _route_for_row(*, source_table: str, stat_scope: str) -> Any | None:
    if stat_scope == "player_season_aggregate":
        return PLAYER_SEASON_ROUTES.get(source_table)
    if stat_scope == "player_postseason_aggregate":
        return POSTSEASON_PLAYER_SEASON_ROUTES.get(source_table)
    if stat_scope == "player_team_postseason":
        return POSTSEASON_TEAM_STINT_ROUTES.get(source_table)
    return None


def _resolve_player_season_id(
    session: Session,
    *,
    row: Mapping[str, Any],
    row_index: int,
) -> int | PlayerPageStatsLoadEntry:
    league = _optional_string(row.get("league")) or "NBA"
    season_year = row.get("season_year")
    player_identifier = _optional_string(row.get("basketball_reference_player_id"))

    if not isinstance(season_year, int):
        return _entry_from_row(row, row_index, "failed", "invalid_season_year")
    if player_identifier is None:
        return _entry_from_row(row, row_index, "failed", "missing_player_id")

    season = session.scalar(
        select(Season).where(Season.league == league.upper(), Season.season_year == season_year)
    )
    if season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_season")

    player = session.scalar(
        select(Player).where(Player.basketball_reference_player_id == player_identifier)
    )
    if player is None:
        return _entry_from_row(row, row_index, "skipped", "missing_player")

    player_season = session.scalar(
        select(PlayerSeason).where(
            PlayerSeason.player_id == player.id,
            PlayerSeason.season_id == season.id,
        )
    )
    if player_season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_player_season")
    return player_season.id


def _resolve_player_team_season_id(
    session: Session,
    *,
    row: Mapping[str, Any],
    row_index: int,
) -> int | PlayerPageStatsLoadEntry:
    player_season_id_or_entry = _resolve_player_season_id(session, row=row, row_index=row_index)
    if isinstance(player_season_id_or_entry, PlayerPageStatsLoadEntry):
        return player_season_id_or_entry

    league = _optional_string(row.get("league")) or "NBA"
    season_year = row.get("season_year")
    team_abbreviation = _optional_string(row.get("team_abbreviation"))
    if not isinstance(season_year, int):
        return _entry_from_row(row, row_index, "failed", "invalid_season_year")
    if team_abbreviation is None:
        return _entry_from_row(row, row_index, "failed", "missing_team_abbreviation")

    season = session.scalar(
        select(Season).where(Season.league == league.upper(), Season.season_year == season_year)
    )
    if season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_season")

    team_season = session.scalar(
        select(TeamSeason).where(
            TeamSeason.season_id == season.id,
            TeamSeason.team_abbreviation == team_abbreviation.upper(),
        )
    )
    if team_season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_team_season")

    player_team_season = session.scalar(
        select(PlayerTeamSeason).where(
            PlayerTeamSeason.player_season_id == player_season_id_or_entry,
            PlayerTeamSeason.team_season_id == team_season.id,
        )
    )
    if player_team_season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_player_team_season")
    return player_team_season.id


def _entry_from_write(
    write: _PreparedPlayerStatsWrite,
    *,
    status: PlayerPageStatsLoadStatus,
    reason: str,
    stats_row_id: int | None = None,
    message: str | None = None,
) -> PlayerPageStatsLoadEntry:
    return PlayerPageStatsLoadEntry(
        row_index=write.row_index,
        status=status,
        reason=reason,
        source_table=write.source_table,
        season_year=write.season_year,
        source_team_code=write.source_team_code,
        team_abbreviation=write.team_abbreviation,
        player_identifier=write.player_identifier,
        destination_table=write.destination_table,
        grain_id=write.grain_id,
        stats_row_id=stats_row_id,
        message=message,
    )


def _entry_from_row(
    row: Mapping[str, Any],
    row_index: int,
    status: PlayerPageStatsLoadStatus,
    reason: str,
    *,
    message: str | None = None,
) -> PlayerPageStatsLoadEntry:
    season_year = row.get("season_year")
    return PlayerPageStatsLoadEntry(
        row_index=row_index,
        status=status,
        reason=reason,
        source_table=_optional_string(row.get("source_table")),
        season_year=season_year if isinstance(season_year, int) else None,
        source_team_code=_optional_string(row.get("source_team_code")),
        team_abbreviation=_optional_string(row.get("team_abbreviation")),
        player_identifier=_optional_string(row.get("basketball_reference_player_id")),
        message=message,
    )


__all__ = [
    "PlayerPageStatsLoadEntry",
    "PlayerPageStatsLoadReport",
    "load_player_page_stats",
]
