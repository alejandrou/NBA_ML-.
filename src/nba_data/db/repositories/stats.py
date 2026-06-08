from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nba_data.db.models import (
    PlayerSeason,
    PlayerSeasonAdjShooting,
    PlayerSeasonAdvanced,
    PlayerSeasonPbp,
    PlayerSeasonPerGame,
    PlayerSeasonPerMinute,
    PlayerSeasonPerPoss,
    PlayerSeasonShooting,
    PlayerSeasonTotals,
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
)

StatsModel = type[Any]

TEAM_STINT_STATS_MODELS: frozenset[StatsModel] = frozenset(
    {
        PlayerTeamSeasonRoster,
        PlayerTeamSeasonTotals,
        PlayerTeamSeasonPerGame,
        PlayerTeamSeasonPerMinute,
        PlayerTeamSeasonPerPoss,
        PlayerTeamSeasonAdvanced,
        PlayerTeamSeasonShooting,
        PlayerTeamSeasonAdjShooting,
        PlayerTeamSeasonPbp,
    }
)

PLAYER_SEASON_STATS_MODELS: frozenset[StatsModel] = frozenset(
    {
        PlayerSeasonTotals,
        PlayerSeasonPerGame,
        PlayerSeasonPerMinute,
        PlayerSeasonPerPoss,
        PlayerSeasonAdvanced,
        PlayerSeasonShooting,
        PlayerSeasonAdjShooting,
        PlayerSeasonPbp,
    }
)

PROTECTED_VALUE_COLUMNS = frozenset(
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


@dataclass(frozen=True)
class TeamStintStatsUpsert:
    model: StatsModel
    player_team_season_id: int
    values: Mapping[str, Any]
    source_url: str
    cache_path: str
    parser_version: str


@dataclass(frozen=True)
class PlayerSeasonStatsUpsert:
    model: StatsModel
    player_season_id: int
    values: Mapping[str, Any]
    source_url: str
    cache_path: str
    parser_version: str


class StatsRepository:
    """Idempotent repositories for official wide stats rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_player_team_season_roster(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonRoster:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonRoster,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_totals(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonTotals:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonTotals,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_per_game(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonPerGame:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonPerGame,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_per_minute(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonPerMinute:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonPerMinute,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_per_poss(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonPerPoss:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonPerPoss,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_advanced(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonAdvanced:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonAdvanced,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_shooting(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonShooting:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonShooting,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_adj_shooting(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonAdjShooting:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonAdjShooting,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_pbp(
        self,
        *,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerTeamSeasonPbp:
        return self.upsert_player_team_season_stat(
            model=PlayerTeamSeasonPbp,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_totals(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonTotals:
        return self.upsert_player_season_stat(
            model=PlayerSeasonTotals,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_per_game(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonPerGame:
        return self.upsert_player_season_stat(
            model=PlayerSeasonPerGame,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_per_minute(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonPerMinute:
        return self.upsert_player_season_stat(
            model=PlayerSeasonPerMinute,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_per_poss(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonPerPoss:
        return self.upsert_player_season_stat(
            model=PlayerSeasonPerPoss,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_advanced(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonAdvanced:
        return self.upsert_player_season_stat(
            model=PlayerSeasonAdvanced,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_shooting(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonShooting:
        return self.upsert_player_season_stat(
            model=PlayerSeasonShooting,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_adj_shooting(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonAdjShooting:
        return self.upsert_player_season_stat(
            model=PlayerSeasonAdjShooting,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_pbp(
        self,
        *,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> PlayerSeasonPbp:
        return self.upsert_player_season_stat(
            model=PlayerSeasonPbp,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_stat(
        self,
        *,
        model: StatsModel,
        player_team_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> Any:
        row = TeamStintStatsUpsert(
            model=model,
            player_team_season_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )
        self._validate_team_stint_upserts((row,))
        return self._upsert(
            model=model,
            grain_column="player_team_season_id",
            grain_id=player_team_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_season_stat(
        self,
        *,
        model: StatsModel,
        player_season_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> Any:
        row = PlayerSeasonStatsUpsert(
            model=model,
            player_season_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )
        self._validate_player_season_upserts((row,))
        return self._upsert(
            model=model,
            grain_column="player_season_id",
            grain_id=player_season_id,
            values=values,
            source_url=source_url,
            cache_path=cache_path,
            parser_version=parser_version,
        )

    def upsert_player_team_season_stats(
        self,
        rows: Iterable[TeamStintStatsUpsert],
    ) -> list[Any]:
        upserts = tuple(rows)
        self._validate_team_stint_upserts(upserts)
        return [
            self._upsert(
                model=row.model,
                grain_column="player_team_season_id",
                grain_id=row.player_team_season_id,
                values=row.values,
                source_url=row.source_url,
                cache_path=row.cache_path,
                parser_version=row.parser_version,
            )
            for row in upserts
        ]

    def upsert_player_season_stats(
        self,
        rows: Iterable[PlayerSeasonStatsUpsert],
    ) -> list[Any]:
        upserts = tuple(rows)
        self._validate_player_season_upserts(upserts)
        return [
            self._upsert(
                model=row.model,
                grain_column="player_season_id",
                grain_id=row.player_season_id,
                values=row.values,
                source_url=row.source_url,
                cache_path=row.cache_path,
                parser_version=row.parser_version,
            )
            for row in upserts
        ]

    def _validate_team_stint_upserts(self, rows: tuple[TeamStintStatsUpsert, ...]) -> None:
        _reject_duplicate_grains(
            (row.model, row.player_team_season_id) for row in rows
        )
        for row in rows:
            _validate_model_allowed(
                model=row.model,
                allowed_models=TEAM_STINT_STATS_MODELS,
                grain_column="player_team_season_id",
            )
            _validate_values(model=row.model, values=row.values)
            _validate_lineage(
                source_url=row.source_url,
                cache_path=row.cache_path,
                parser_version=row.parser_version,
            )
            self._require_player_team_season(row.player_team_season_id)

    def _validate_player_season_upserts(self, rows: tuple[PlayerSeasonStatsUpsert, ...]) -> None:
        _reject_duplicate_grains((row.model, row.player_season_id) for row in rows)
        for row in rows:
            _validate_model_allowed(
                model=row.model,
                allowed_models=PLAYER_SEASON_STATS_MODELS,
                grain_column="player_season_id",
            )
            _validate_values(model=row.model, values=row.values)
            _validate_lineage(
                source_url=row.source_url,
                cache_path=row.cache_path,
                parser_version=row.parser_version,
            )
            self._require_player_season(row.player_season_id)

    def _require_player_team_season(self, player_team_season_id: int) -> None:
        exists = self.session.scalar(
            select(PlayerTeamSeason.id).where(PlayerTeamSeason.id == player_team_season_id)
        )
        if exists is None:
            msg = (
                "core.player_team_seasons row does not exist for "
                f"player_team_season_id={player_team_season_id}."
            )
            raise ValueError(msg)

    def _require_player_season(self, player_season_id: int) -> None:
        exists = self.session.scalar(
            select(PlayerSeason.id).where(PlayerSeason.id == player_season_id)
        )
        if exists is None:
            msg = f"core.player_seasons row does not exist for player_season_id={player_season_id}."
            raise ValueError(msg)

    def _upsert(
        self,
        *,
        model: StatsModel,
        grain_column: str,
        grain_id: int,
        values: Mapping[str, Any],
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> Any:
        record = self.session.scalar(
            select(model).where(getattr(model, grain_column) == grain_id)
        )
        lineage = {
            "source_url": _clean_required(source_url, field_name="source_url"),
            "cache_path": _clean_required(cache_path, field_name="cache_path"),
            "parser_version": _clean_required(parser_version, field_name="parser_version"),
        }
        if record is None:
            record = model(**{grain_column: grain_id}, **values, **lineage)
            self.session.add(record)
        else:
            for column_name, value in values.items():
                setattr(record, column_name, value)
            for column_name, value in lineage.items():
                setattr(record, column_name, value)
            record.updated_at = datetime.now(UTC)

        self.session.flush()
        self.session.refresh(record)
        return record


def _validate_model_allowed(
    *,
    model: StatsModel,
    allowed_models: frozenset[StatsModel],
    grain_column: str,
) -> None:
    if model not in allowed_models:
        model_name = getattr(model, "__name__", repr(model))
        msg = f"{model_name} is not an approved stats model for {grain_column} upserts."
        raise ValueError(msg)


def _validate_values(*, model: StatsModel, values: Mapping[str, Any]) -> None:
    value_columns = set(values)
    protected_columns = sorted(value_columns & PROTECTED_VALUE_COLUMNS)
    if protected_columns:
        joined = ", ".join(protected_columns)
        msg = f"Stats values may not include protected columns: {joined}."
        raise ValueError(msg)

    model_columns = set(model.__table__.columns.keys())
    allowed_columns = model_columns - PROTECTED_VALUE_COLUMNS
    unknown_columns = sorted(value_columns - allowed_columns)
    if unknown_columns:
        model_name = model.__name__
        joined = ", ".join(unknown_columns)
        msg = f"Unknown stats columns for {model_name}: {joined}."
        raise ValueError(msg)


def _validate_lineage(*, source_url: str, cache_path: str, parser_version: str) -> None:
    _clean_required(source_url, field_name="source_url")
    _clean_required(cache_path, field_name="cache_path")
    _clean_required(parser_version, field_name="parser_version")


def _reject_duplicate_grains(grains: Iterable[tuple[StatsModel, int]]) -> None:
    seen: dict[tuple[StatsModel, int], int] = {}
    for index, grain in enumerate(grains):
        first_index = seen.get(grain)
        if first_index is not None:
            model_name = grain[0].__name__
            msg = (
                "Duplicate stats upsert grain "
                f"{model_name}:{grain[1]}; first seen at row {first_index}."
            )
            raise ValueError(msg)
        seen[grain] = index


def _clean_required(value: object, *, field_name: str) -> str:
    if value is None:
        msg = f"{field_name} is required."
        raise ValueError(msg)
    cleaned = str(value).strip()
    if not cleaned:
        msg = f"{field_name} is required."
        raise ValueError(msg)
    return cleaned


__all__ = [
    "PLAYER_SEASON_STATS_MODELS",
    "TEAM_STINT_STATS_MODELS",
    "PlayerSeasonStatsUpsert",
    "StatsRepository",
    "TeamStintStatsUpsert",
]
