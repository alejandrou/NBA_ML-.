from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Literal

from sqlalchemy import Date, Integer, Numeric, select
from sqlalchemy.orm import Session

from nba_data.db.models import (
    Player,
    PlayerPostseasonAdjShooting,
    PlayerPostseasonAdvanced,
    PlayerPostseasonPbp,
    PlayerPostseasonPerGame,
    PlayerPostseasonPerMinute,
    PlayerPostseasonPerPoss,
    PlayerPostseasonShooting,
    PlayerPostseasonTotals,
    PlayerSeason,
    PlayerSeasonAdjShooting,
    PlayerSeasonAdvanced,
    PlayerSeasonPbp,
    PlayerSeasonPerGame,
    PlayerSeasonPerMinute,
    PlayerSeasonPerPoss,
    PlayerSeasonShooting,
    PlayerSeasonTotals,
    PlayerTeamPostseasonAdjShooting,
    PlayerTeamPostseasonAdvanced,
    PlayerTeamPostseasonPbp,
    PlayerTeamPostseasonPerGame,
    PlayerTeamPostseasonPerMinute,
    PlayerTeamPostseasonPerPoss,
    PlayerTeamPostseasonShooting,
    PlayerTeamPostseasonTotals,
    PlayerTeamSeason,
    PlayerTeamSeasonAdjShooting,
    PlayerTeamSeasonAdvanced,
    PlayerTeamSeasonPbp,
    PlayerTeamSeasonPerGame,
    PlayerTeamSeasonPerMinute,
    PlayerTeamSeasonPerPoss,
    PlayerTeamSeasonRoster,
    PlayerTeamSeasonShooting,
    PlayerTeamSeasonTotals,
    Season,
    TeamSeason,
)
from nba_data.db.repositories import StatsRepository

StatsLoadStatus = Literal["loaded", "skipped", "failed"]
StatsModel = type[Any]

PROTECTED_VALUE_KEYS = frozenset(
    {
        "id",
        "player_team_season_id",
        "player_season_id",
        "source_url",
        "cache_path",
        "parser_version",
        "created_at",
        "updated_at",
    }
)

CONTEXT_VALUE_KEYS = frozenset(
    {
        "basketball_reference_player_id",
        "identifier_status",
        "stable_player_key",
        "team",
        "team_abbreviation",
        "team_id",
        "tm",
    }
)

ROSTER_COLUMNS = MappingProxyType(
    {
        "number": "jersey_number",
        "player": "player_name",
        "pos": "position",
        "height": "height",
        "weight": "weight",
        "birth_date": "birth_date",
        "years_experience": "experience",
        "college": "college",
        "flag": "country_flag",
    }
)

TOTALS_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "fg": "fg",
        "fga": "fga",
        "fg_pct": "fg_pct",
        "fg3": "fg3",
        "fg3a": "fg3a",
        "fg3_pct": "fg3_pct",
        "fg2": "fg2",
        "fg2a": "fg2a",
        "fg2_pct": "fg2_pct",
        "efg_pct": "efg_pct",
        "ft": "ft",
        "fta": "fta",
        "ft_pct": "ft_pct",
        "orb": "orb",
        "drb": "drb",
        "trb": "trb",
        "ast": "ast",
        "stl": "stl",
        "blk": "blk",
        "tov": "tov",
        "pf": "pf",
        "pts": "pts",
        "tpl_dbl": "tpl_dbl",
        "awards": "awards",
    }
)

PER_GAME_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "pos": "position",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp_per_g": "mp_per_game",
        "fg_per_g": "fg_per_game",
        "fga_per_g": "fga_per_game",
        "fg_pct": "fg_pct",
        "fg3_per_g": "fg3_per_game",
        "fg3a_per_g": "fg3a_per_game",
        "fg3_pct": "fg3_pct",
        "fg2_per_g": "fg2_per_game",
        "fg2a_per_g": "fg2a_per_game",
        "fg2_pct": "fg2_pct",
        "efg_pct": "efg_pct",
        "ft_per_g": "ft_per_game",
        "fta_per_g": "fta_per_game",
        "ft_pct": "ft_pct",
        "orb_per_g": "orb_per_game",
        "drb_per_g": "drb_per_game",
        "trb_per_g": "trb_per_game",
        "ast_per_g": "ast_per_game",
        "stl_per_g": "stl_per_game",
        "blk_per_g": "blk_per_game",
        "tov_per_g": "tov_per_game",
        "pf_per_g": "pf_per_game",
        "pts_per_g": "pts_per_game",
        "awards": "awards",
    }
)

PER_MINUTE_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "pos": "position",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "fg_per_minute_36": "fg_per_36",
        "fga_per_minute_36": "fga_per_36",
        "fg_pct": "fg_pct",
        "fg3_per_minute_36": "fg3_per_36",
        "fg3a_per_minute_36": "fg3a_per_36",
        "fg3_pct": "fg3_pct",
        "fg2_per_minute_36": "fg2_per_36",
        "fg2a_per_minute_36": "fg2a_per_36",
        "fg2_pct": "fg2_pct",
        "efg_pct": "efg_pct",
        "ft_per_minute_36": "ft_per_36",
        "fta_per_minute_36": "fta_per_36",
        "ft_pct": "ft_pct",
        "orb_per_minute_36": "orb_per_36",
        "drb_per_minute_36": "drb_per_36",
        "trb_per_minute_36": "trb_per_36",
        "ast_per_minute_36": "ast_per_36",
        "stl_per_minute_36": "stl_per_36",
        "blk_per_minute_36": "blk_per_36",
        "tov_per_minute_36": "tov_per_36",
        "pf_per_minute_36": "pf_per_36",
        "pts_per_minute_36": "pts_per_36",
        "awards": "awards",
    }
)

PER_POSS_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "fg_per_poss": "fg_per_poss",
        "fga_per_poss": "fga_per_poss",
        "fg_pct": "fg_pct",
        "fg3_per_poss": "fg3_per_poss",
        "fg3a_per_poss": "fg3a_per_poss",
        "fg3_pct": "fg3_pct",
        "fg2_per_poss": "fg2_per_poss",
        "fg2a_per_poss": "fg2a_per_poss",
        "fg2_pct": "fg2_pct",
        "efg_pct": "efg_pct",
        "ft_per_poss": "ft_per_poss",
        "fta_per_poss": "fta_per_poss",
        "ft_pct": "ft_pct",
        "orb_per_poss": "orb_per_poss",
        "drb_per_poss": "drb_per_poss",
        "trb_per_poss": "trb_per_poss",
        "ast_per_poss": "ast_per_poss",
        "stl_per_poss": "stl_per_poss",
        "blk_per_poss": "blk_per_poss",
        "tov_per_poss": "tov_per_poss",
        "pf_per_poss": "pf_per_poss",
        "pts_per_poss": "pts_per_poss",
        "off_rtg": "ortg",
        "def_rtg": "drtg",
        "awards": "awards",
    }
)

ADVANCED_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "pos": "position",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "per": "per",
        "ts_pct": "ts_pct",
        "fg3a_per_fga_pct": "fg3a_per_fga_pct",
        "fta_per_fga_pct": "fta_per_fga_pct",
        "orb_pct": "orb_pct",
        "drb_pct": "drb_pct",
        "trb_pct": "trb_pct",
        "ast_pct": "ast_pct",
        "stl_pct": "stl_pct",
        "blk_pct": "blk_pct",
        "tov_pct": "tov_pct",
        "usg_pct": "usg_pct",
        "ows": "ows",
        "dws": "dws",
        "ws": "ws",
        "ws_per_48": "ws_per_48",
        "obpm": "obpm",
        "dbpm": "dbpm",
        "bpm": "bpm",
        "vorp": "vorp",
        "awards": "awards",
    }
)

SHOOTING_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "pos": "position",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "fg_pct": "fg_pct",
        "avg_dist": "avg_dist",
        "pct_fga_fg2a": "pct_fga_fg2a",
        "pct_fga_00_03": "pct_fga_0_3",
        "pct_fga_03_10": "pct_fga_3_10",
        "pct_fga_10_16": "pct_fga_10_16",
        "pct_fga_16_xx": "pct_fga_16_plus",
        "pct_fga_fg3a": "pct_fga_fg3a",
        "fg_pct_fg2a": "fg_pct_fg2a",
        "fg_pct_00_03": "fg_pct_0_3",
        "fg_pct_03_10": "fg_pct_3_10",
        "fg_pct_10_16": "fg_pct_10_16",
        "fg_pct_16_xx": "fg_pct_16_plus",
        "fg_pct_fg3a": "fg_pct_fg3a",
        "pct_ast_fg2": "pct_ast_fg2",
        "pct_ast_fg3": "pct_ast_fg3",
        "pct_fga_dunk": "pct_fga_dunk",
        "fg_dunk": "dunks_made",
        "pct_fg3a_corner3": "pct_fg3a_corner3",
        "fg_pct_corner3": "fg_pct_corner3",
        "fg3_heave": "heaves_made",
        "fg3a_heave": "heaves_att",
        "awards": "awards",
    }
)

ADJ_SHOOTING_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "pos": "position",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "fg_pct": "fg_pct",
        "adj_fg_pct": "adj_fg_pct",
        "fg2_pct": "fg2_pct",
        "adj_fg2_pct": "adj_fg2_pct",
        "fg3_pct": "fg3_pct",
        "adj_fg3_pct": "adj_fg3_pct",
        "efg_pct": "efg_pct",
        "adj_efg_pct": "adj_efg_pct",
        "ft_pct": "ft_pct",
        "adj_ft_pct": "adj_ft_pct",
        "ts_pct": "ts_pct",
        "adj_ts_pct": "adj_ts_pct",
        "fg3a_per_fga_pct": "fg3a_per_fga_pct",
        "adj_fg3a_per_fga_pct": "adj_fg3a_per_fga_pct",
        "fta_per_fga_pct": "fta_per_fga_pct",
        "adj_fta_per_fga_pct": "adj_fta_per_fga_pct",
        "fg_pts_added": "fg_pts_added",
        "ts_pts_added": "ts_pts_added",
        "awards": "awards",
    }
)

PBP_COLUMNS = MappingProxyType(
    {
        "ranker": "rk",
        "name_display": "player_name_display",
        "pos": "position",
        "age": "age",
        "games": "g",
        "games_started": "gs",
        "mp": "mp",
        "pct_1": "pct_pg",
        "pct_2": "pct_sg",
        "pct_3": "pct_sf",
        "pct_4": "pct_pf",
        "pct_5": "pct_c",
        "plus_minus_on": "on_court_plus_minus",
        "plus_minus_net": "net_plus_minus",
        "tov_bad_pass": "bad_pass_turnover",
        "tov_lost_ball": "lost_ball_turnover",
        "fouls_shooting": "fouls_shooting",
        "fouls_offensive": "fouls_offensive",
        "drawn_shooting": "drawn_shooting",
        "drawn_offensive": "drawn_offensive",
        "and1s": "and1s",
        "own_shots_blk": "own_shots_blocked",
        "astd_pts": "assisted_points",
        "awards": "awards",
    }
)


@dataclass(frozen=True)
class TeamSeasonStatsLoadEntry:
    row_index: int
    status: StatsLoadStatus
    reason: str
    source_table: str | None = None
    stat_scope: str | None = None
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
            "stat_scope": self.stat_scope,
            "team_abbreviation": self.team_abbreviation,
            "player_identifier": self.player_identifier,
            "destination_table": self.destination_table,
            "grain_id": self.grain_id,
            "stats_row_id": self.stats_row_id,
            "message": self.message,
        }


@dataclass(frozen=True)
class TeamSeasonStatsLoadReport:
    total_rows: int
    loaded_rows: int
    skipped_rows: int
    failed_rows: int
    entries: tuple[TeamSeasonStatsLoadEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_rows": self.total_rows,
            "loaded_rows": self.loaded_rows,
            "skipped_rows": self.skipped_rows,
            "failed_rows": self.failed_rows,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class _StatsRoute:
    method_name: str
    model: StatsModel
    destination_table: str
    columns: Mapping[str, str]
    aggregate: bool


@dataclass(frozen=True)
class _PreparedStatsWrite:
    row_index: int
    route: _StatsRoute
    grain_id: int
    values: Mapping[str, Any]
    source_table: str
    stat_scope: str
    team_abbreviation: str
    player_identifier: str

    @property
    def duplicate_key(self) -> tuple[str, int]:
        return (self.route.destination_table, self.grain_id)


TEAM_STINT_ROUTES = MappingProxyType(
    {
        "roster": _StatsRoute(
            method_name="upsert_player_team_season_roster",
            model=PlayerTeamSeasonRoster,
            destination_table="stats.player_team_season_roster",
            columns=ROSTER_COLUMNS,
            aggregate=False,
        ),
        "totals": _StatsRoute(
            method_name="upsert_player_team_season_totals",
            model=PlayerTeamSeasonTotals,
            destination_table="stats.player_team_season_totals",
            columns=TOTALS_COLUMNS,
            aggregate=False,
        ),
        "per_game": _StatsRoute(
            method_name="upsert_player_team_season_per_game",
            model=PlayerTeamSeasonPerGame,
            destination_table="stats.player_team_season_per_game",
            columns=PER_GAME_COLUMNS,
            aggregate=False,
        ),
        "per_minute": _StatsRoute(
            method_name="upsert_player_team_season_per_minute",
            model=PlayerTeamSeasonPerMinute,
            destination_table="stats.player_team_season_per_minute",
            columns=PER_MINUTE_COLUMNS,
            aggregate=False,
        ),
        "per_poss": _StatsRoute(
            method_name="upsert_player_team_season_per_poss",
            model=PlayerTeamSeasonPerPoss,
            destination_table="stats.player_team_season_per_poss",
            columns=PER_POSS_COLUMNS,
            aggregate=False,
        ),
        "advanced": _StatsRoute(
            method_name="upsert_player_team_season_advanced",
            model=PlayerTeamSeasonAdvanced,
            destination_table="stats.player_team_season_advanced",
            columns=ADVANCED_COLUMNS,
            aggregate=False,
        ),
        "shooting": _StatsRoute(
            method_name="upsert_player_team_season_shooting",
            model=PlayerTeamSeasonShooting,
            destination_table="stats.player_team_season_shooting",
            columns=SHOOTING_COLUMNS,
            aggregate=False,
        ),
        "adj_shooting": _StatsRoute(
            method_name="upsert_player_team_season_adj_shooting",
            model=PlayerTeamSeasonAdjShooting,
            destination_table="stats.player_team_season_adj_shooting",
            columns=ADJ_SHOOTING_COLUMNS,
            aggregate=False,
        ),
        "pbp": _StatsRoute(
            method_name="upsert_player_team_season_pbp",
            model=PlayerTeamSeasonPbp,
            destination_table="stats.player_team_season_pbp",
            columns=PBP_COLUMNS,
            aggregate=False,
        ),
    }
)

PLAYER_SEASON_ROUTES = MappingProxyType(
    {
        "totals": _StatsRoute(
            method_name="upsert_player_season_totals",
            model=PlayerSeasonTotals,
            destination_table="stats.player_season_totals",
            columns=TOTALS_COLUMNS,
            aggregate=True,
        ),
        "per_game": _StatsRoute(
            method_name="upsert_player_season_per_game",
            model=PlayerSeasonPerGame,
            destination_table="stats.player_season_per_game",
            columns=PER_GAME_COLUMNS,
            aggregate=True,
        ),
        "per_minute": _StatsRoute(
            method_name="upsert_player_season_per_minute",
            model=PlayerSeasonPerMinute,
            destination_table="stats.player_season_per_minute",
            columns=PER_MINUTE_COLUMNS,
            aggregate=True,
        ),
        "per_poss": _StatsRoute(
            method_name="upsert_player_season_per_poss",
            model=PlayerSeasonPerPoss,
            destination_table="stats.player_season_per_poss",
            columns=PER_POSS_COLUMNS,
            aggregate=True,
        ),
        "advanced": _StatsRoute(
            method_name="upsert_player_season_advanced",
            model=PlayerSeasonAdvanced,
            destination_table="stats.player_season_advanced",
            columns=ADVANCED_COLUMNS,
            aggregate=True,
        ),
        "shooting": _StatsRoute(
            method_name="upsert_player_season_shooting",
            model=PlayerSeasonShooting,
            destination_table="stats.player_season_shooting",
            columns=SHOOTING_COLUMNS,
            aggregate=True,
        ),
        "adj_shooting": _StatsRoute(
            method_name="upsert_player_season_adj_shooting",
            model=PlayerSeasonAdjShooting,
            destination_table="stats.player_season_adj_shooting",
            columns=ADJ_SHOOTING_COLUMNS,
            aggregate=True,
        ),
        "pbp": _StatsRoute(
            method_name="upsert_player_season_pbp",
            model=PlayerSeasonPbp,
            destination_table="stats.player_season_pbp",
            columns=PBP_COLUMNS,
            aggregate=True,
        ),
    }
)

POSTSEASON_PLAYER_SEASON_ROUTES = MappingProxyType(
    {
        "totals": _StatsRoute(
            method_name="upsert_player_postseason_totals",
            model=PlayerPostseasonTotals,
            destination_table="stats.player_postseason_totals",
            columns=TOTALS_COLUMNS,
            aggregate=True,
        ),
        "per_game": _StatsRoute(
            method_name="upsert_player_postseason_per_game",
            model=PlayerPostseasonPerGame,
            destination_table="stats.player_postseason_per_game",
            columns=PER_GAME_COLUMNS,
            aggregate=True,
        ),
        "per_minute": _StatsRoute(
            method_name="upsert_player_postseason_per_minute",
            model=PlayerPostseasonPerMinute,
            destination_table="stats.player_postseason_per_minute",
            columns=PER_MINUTE_COLUMNS,
            aggregate=True,
        ),
        "per_poss": _StatsRoute(
            method_name="upsert_player_postseason_per_poss",
            model=PlayerPostseasonPerPoss,
            destination_table="stats.player_postseason_per_poss",
            columns=PER_POSS_COLUMNS,
            aggregate=True,
        ),
        "advanced": _StatsRoute(
            method_name="upsert_player_postseason_advanced",
            model=PlayerPostseasonAdvanced,
            destination_table="stats.player_postseason_advanced",
            columns=ADVANCED_COLUMNS,
            aggregate=True,
        ),
        "shooting": _StatsRoute(
            method_name="upsert_player_postseason_shooting",
            model=PlayerPostseasonShooting,
            destination_table="stats.player_postseason_shooting",
            columns=SHOOTING_COLUMNS,
            aggregate=True,
        ),
        "adj_shooting": _StatsRoute(
            method_name="upsert_player_postseason_adj_shooting",
            model=PlayerPostseasonAdjShooting,
            destination_table="stats.player_postseason_adj_shooting",
            columns=ADJ_SHOOTING_COLUMNS,
            aggregate=True,
        ),
        "pbp": _StatsRoute(
            method_name="upsert_player_postseason_pbp",
            model=PlayerPostseasonPbp,
            destination_table="stats.player_postseason_pbp",
            columns=PBP_COLUMNS,
            aggregate=True,
        ),
    }
)

POSTSEASON_TEAM_STINT_ROUTES = MappingProxyType(
    {
        "totals": _StatsRoute(
            method_name="upsert_player_team_postseason_totals",
            model=PlayerTeamPostseasonTotals,
            destination_table="stats.player_team_postseason_totals",
            columns=TOTALS_COLUMNS,
            aggregate=False,
        ),
        "per_game": _StatsRoute(
            method_name="upsert_player_team_postseason_per_game",
            model=PlayerTeamPostseasonPerGame,
            destination_table="stats.player_team_postseason_per_game",
            columns=PER_GAME_COLUMNS,
            aggregate=False,
        ),
        "per_minute": _StatsRoute(
            method_name="upsert_player_team_postseason_per_minute",
            model=PlayerTeamPostseasonPerMinute,
            destination_table="stats.player_team_postseason_per_minute",
            columns=PER_MINUTE_COLUMNS,
            aggregate=False,
        ),
        "per_poss": _StatsRoute(
            method_name="upsert_player_team_postseason_per_poss",
            model=PlayerTeamPostseasonPerPoss,
            destination_table="stats.player_team_postseason_per_poss",
            columns=PER_POSS_COLUMNS,
            aggregate=False,
        ),
        "advanced": _StatsRoute(
            method_name="upsert_player_team_postseason_advanced",
            model=PlayerTeamPostseasonAdvanced,
            destination_table="stats.player_team_postseason_advanced",
            columns=ADVANCED_COLUMNS,
            aggregate=False,
        ),
        "shooting": _StatsRoute(
            method_name="upsert_player_team_postseason_shooting",
            model=PlayerTeamPostseasonShooting,
            destination_table="stats.player_team_postseason_shooting",
            columns=SHOOTING_COLUMNS,
            aggregate=False,
        ),
        "adj_shooting": _StatsRoute(
            method_name="upsert_player_team_postseason_adj_shooting",
            model=PlayerTeamPostseasonAdjShooting,
            destination_table="stats.player_team_postseason_adj_shooting",
            columns=ADJ_SHOOTING_COLUMNS,
            aggregate=False,
        ),
        "pbp": _StatsRoute(
            method_name="upsert_player_team_postseason_pbp",
            model=PlayerTeamPostseasonPbp,
            destination_table="stats.player_team_postseason_pbp",
            columns=PBP_COLUMNS,
            aggregate=False,
        ),
    }
)


def load_team_season_stats(
    session: Session,
    rows: Iterable[Mapping[str, Any]],
    *,
    source_url: str,
    cache_path: str,
    parser_version: str,
) -> TeamSeasonStatsLoadReport:
    """Load normalized team-season stats rows without committing the transaction."""

    normalized_rows = tuple(rows)
    entries_by_index: dict[int, TeamSeasonStatsLoadEntry] = {}
    prepared_writes: list[_PreparedStatsWrite] = []

    for index, row in enumerate(normalized_rows):
        prepared_or_entry = _prepare_row(session, row, index)
        if isinstance(prepared_or_entry, TeamSeasonStatsLoadEntry):
            entries_by_index[index] = prepared_or_entry
        else:
            prepared_writes.append(prepared_or_entry)

    duplicate_keys = {
        key for key, count in Counter(write.duplicate_key for write in prepared_writes).items()
        if count > 1
    }
    for write in prepared_writes:
        if write.duplicate_key in duplicate_keys:
            entries_by_index[write.row_index] = _entry_from_write(
                write,
                status="failed",
                reason="duplicate_stats_grain",
                message=(
                    "Multiple normalized rows target "
                    f"{write.route.destination_table} grain_id={write.grain_id}."
                ),
            )

    repository = StatsRepository(session)
    for write in prepared_writes:
        if write.row_index in entries_by_index:
            continue
        try:
            with session.begin_nested():
                record = _execute_write(
                    repository,
                    write,
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
    return TeamSeasonStatsLoadReport(
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
) -> _PreparedStatsWrite | TeamSeasonStatsLoadEntry:
    source_table = _optional_string(row.get("source_table"))
    stat_scope = _optional_string(row.get("stat_scope"))
    team_abbreviation = _optional_string(row.get("team_abbreviation"))
    player_identifier = _optional_string(row.get("basketball_reference_player_id"))

    if source_table is None or stat_scope is None:
        return _entry_from_row(row, row_index, "failed", "missing_routing_fields")
    if player_identifier is None:
        return _entry_from_row(row, row_index, "failed", "missing_player_id")

    aggregate = _is_aggregate_row(row)
    route_or_entry = _route_for_row(
        row=row,
        row_index=row_index,
        source_table=source_table,
        stat_scope=stat_scope,
        aggregate=aggregate,
    )
    if isinstance(route_or_entry, TeamSeasonStatsLoadEntry):
        return route_or_entry

    values = row.get("values")
    if not isinstance(values, Mapping):
        return _entry_from_row(row, row_index, "failed", "invalid_values")

    try:
        stats_values = _stats_values(
            values=values,
            columns=route_or_entry.columns,
            model=route_or_entry.model,
        )
    except ValueError as exc:
        return _entry_from_row(row, row_index, "failed", "invalid_values", message=str(exc))

    grain_id_or_entry = _resolve_grain_id(
        session,
        row=row,
        row_index=row_index,
        aggregate=route_or_entry.aggregate,
    )
    if isinstance(grain_id_or_entry, TeamSeasonStatsLoadEntry):
        return grain_id_or_entry

    return _PreparedStatsWrite(
        row_index=row_index,
        route=route_or_entry,
        grain_id=grain_id_or_entry,
        values=stats_values,
        source_table=source_table,
        stat_scope=stat_scope,
        team_abbreviation=team_abbreviation or "",
        player_identifier=player_identifier,
    )


def _route_for_row(
    *,
    row: Mapping[str, Any],
    row_index: int,
    source_table: str,
    stat_scope: str,
    aggregate: bool,
) -> _StatsRoute | TeamSeasonStatsLoadEntry:
    if aggregate:
        if _normalize_team_abbreviation(row.get("team_abbreviation")) != "TOT":
            return _entry_from_row(row, row_index, "skipped", "invalid_aggregate_routing")
        if stat_scope != "player_season_aggregate":
            return _entry_from_row(row, row_index, "skipped", "unsupported_stat_scope")
        route = PLAYER_SEASON_ROUTES.get(source_table)
        if route is None:
            reason = (
                "unsupported_aggregate_roster"
                if source_table == "roster"
                else "unsupported_source_table"
            )
            return _entry_from_row(row, row_index, "skipped", reason)
        return route

    if _normalize_team_abbreviation(row.get("team_abbreviation")) == "TOT":
        return _entry_from_row(row, row_index, "skipped", "invalid_tot_routing")
    if source_table == "roster" and stat_scope != "team_roster":
        return _entry_from_row(row, row_index, "skipped", "unsupported_stat_scope")
    if source_table != "roster" and stat_scope != "player_team_season":
        return _entry_from_row(row, row_index, "skipped", "unsupported_stat_scope")

    route = TEAM_STINT_ROUTES.get(source_table)
    if route is None:
        return _entry_from_row(row, row_index, "skipped", "unsupported_source_table")
    return route


def _resolve_grain_id(
    session: Session,
    *,
    row: Mapping[str, Any],
    row_index: int,
    aggregate: bool,
) -> int | TeamSeasonStatsLoadEntry:
    league = _optional_string(row.get("league")) or "NBA"
    season_year = row.get("season_year")
    player_identifier = _optional_string(row.get("basketball_reference_player_id"))
    if not isinstance(season_year, int):
        return _entry_from_row(row, row_index, "failed", "invalid_season_year")
    if player_identifier is None:
        return _entry_from_row(row, row_index, "failed", "missing_player_id")

    season = session.scalar(
        select(Season).where(
            Season.league == league.upper(),
            Season.season_year == season_year,
        )
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
    if aggregate:
        return player_season.id

    team_abbreviation = _normalize_team_abbreviation(row.get("team_abbreviation"))
    if team_abbreviation is None:
        return _entry_from_row(row, row_index, "failed", "missing_team_abbreviation")

    team_season = session.scalar(
        select(TeamSeason).where(
            TeamSeason.season_id == season.id,
            TeamSeason.team_abbreviation == team_abbreviation,
        )
    )
    if team_season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_team_season")

    player_team_season = session.scalar(
        select(PlayerTeamSeason).where(
            PlayerTeamSeason.player_season_id == player_season.id,
            PlayerTeamSeason.team_season_id == team_season.id,
        )
    )
    if player_team_season is None:
        return _entry_from_row(row, row_index, "skipped", "missing_player_team_season")
    return player_team_season.id


def _stats_values(
    *,
    values: Mapping[str, Any],
    columns: Mapping[str, str],
    model: StatsModel,
) -> dict[str, Any]:
    value_keys = set(values)
    protected_keys = sorted(value_keys & PROTECTED_VALUE_KEYS)
    if protected_keys:
        joined = ", ".join(protected_keys)
        msg = f"Stats values may not include protected keys: {joined}."
        raise ValueError(msg)

    stat_value_keys = value_keys - CONTEXT_VALUE_KEYS
    unknown_keys = sorted(stat_value_keys - set(columns))
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        msg = f"Unknown normalized stats keys: {joined}."
        raise ValueError(msg)

    mapped: dict[str, Any] = {}
    for source_key, column_name in columns.items():
        column = model.__table__.columns[column_name]
        mapped[column_name] = _convert_value(values.get(source_key), column.type)
    return mapped


def _convert_value(value: object, column_type: object) -> object:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(column_type, Integer):
        return _to_int(value)
    if isinstance(column_type, Numeric):
        return _to_decimal(value)
    if isinstance(column_type, Date):
        return _to_date(value)
    return _to_string(value)


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        msg = "Boolean values are not valid integer stats."
        raise ValueError(msg)
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned.removeprefix("-").isdigit():
            return int(cleaned)
    msg = f"Expected integer-compatible value, got {value!r}."
    raise ValueError(msg)


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        msg = "Boolean values are not valid decimal stats."
        raise ValueError(msg)
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, int | float):
        decimal_value = Decimal(str(value))
    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            decimal_value = Decimal(cleaned)
        except InvalidOperation as exc:
            msg = f"Expected decimal-compatible value, got {value!r}."
            raise ValueError(msg) from exc
    else:
        msg = f"Expected decimal-compatible value, got {value!r}."
        raise ValueError(msg)

    if not decimal_value.is_finite():
        msg = f"Expected finite decimal-compatible value, got {value!r}."
        raise ValueError(msg)
    return decimal_value


def _to_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def _to_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _execute_write(
    repository: StatsRepository,
    write: _PreparedStatsWrite,
    *,
    source_url: str,
    cache_path: str,
    parser_version: str,
) -> object:
    method = getattr(repository, write.route.method_name)
    lineage = {
        "values": write.values,
        "source_url": source_url,
        "cache_path": cache_path,
        "parser_version": parser_version,
    }
    if write.route.aggregate:
        return method(player_season_id=write.grain_id, **lineage)
    return method(player_team_season_id=write.grain_id, **lineage)


def _is_aggregate_row(row: Mapping[str, Any]) -> bool:
    return (
        _normalize_team_abbreviation(row.get("team_abbreviation")) == "TOT"
        or _optional_string(row.get("team_context")) == "aggregate"
        or _optional_string(row.get("stat_scope")) == "player_season_aggregate"
    )


def _entry_from_write(
    write: _PreparedStatsWrite,
    *,
    status: StatsLoadStatus,
    reason: str,
    stats_row_id: int | None = None,
    message: str | None = None,
) -> TeamSeasonStatsLoadEntry:
    return TeamSeasonStatsLoadEntry(
        row_index=write.row_index,
        status=status,
        reason=reason,
        source_table=write.source_table,
        stat_scope=write.stat_scope,
        team_abbreviation=write.team_abbreviation,
        player_identifier=write.player_identifier,
        destination_table=write.route.destination_table,
        grain_id=write.grain_id,
        stats_row_id=stats_row_id,
        message=message,
    )


def _entry_from_row(
    row: Mapping[str, Any],
    row_index: int,
    status: StatsLoadStatus,
    reason: str,
    *,
    message: str | None = None,
) -> TeamSeasonStatsLoadEntry:
    return TeamSeasonStatsLoadEntry(
        row_index=row_index,
        status=status,
        reason=reason,
        source_table=_optional_string(row.get("source_table")),
        stat_scope=_optional_string(row.get("stat_scope")),
        team_abbreviation=_optional_string(row.get("team_abbreviation")),
        player_identifier=_optional_string(row.get("basketball_reference_player_id")),
        message=message,
    )


def _normalize_team_abbreviation(value: object) -> str | None:
    cleaned = _optional_string(value)
    return cleaned.upper() if cleaned else None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


__all__ = [
    "PLAYER_SEASON_ROUTES",
    "POSTSEASON_PLAYER_SEASON_ROUTES",
    "POSTSEASON_TEAM_STINT_ROUTES",
    "TeamSeasonStatsLoadEntry",
    "TeamSeasonStatsLoadReport",
    "load_team_season_stats",
]
