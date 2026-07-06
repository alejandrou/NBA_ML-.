from sqlalchemy import (
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

import nba_data.db.models as models
from nba_data.db.base import Base

TEAM_STINT_TABLES = (
    "player_team_season_roster",
    "player_team_season_totals",
    "player_team_season_per_game",
    "player_team_season_per_minute",
    "player_team_season_per_poss",
    "player_team_season_advanced",
    "player_team_season_shooting",
    "player_team_season_adj_shooting",
    "player_team_season_pbp",
)

PLAYER_SEASON_TABLES = (
    "player_season_totals",
    "player_season_per_game",
    "player_season_per_minute",
    "player_season_per_poss",
    "player_season_advanced",
    "player_season_shooting",
    "player_season_adj_shooting",
    "player_season_pbp",
)

PLAYER_POSTSEASON_TABLES = (
    "player_postseason_totals",
    "player_postseason_per_game",
    "player_postseason_per_minute",
    "player_postseason_per_poss",
    "player_postseason_advanced",
    "player_postseason_shooting",
    "player_postseason_adj_shooting",
    "player_postseason_pbp",
)

PLAYER_TEAM_POSTSEASON_TABLES = (
    "player_team_postseason_totals",
    "player_team_postseason_per_game",
    "player_team_postseason_per_minute",
    "player_team_postseason_per_poss",
    "player_team_postseason_advanced",
    "player_team_postseason_shooting",
    "player_team_postseason_adj_shooting",
    "player_team_postseason_pbp",
)

EXPECTED_STATS_TABLE_KEYS = {
    *(f"stats.{table_name}" for table_name in TEAM_STINT_TABLES),
    *(f"stats.{table_name}" for table_name in PLAYER_SEASON_TABLES),
    *(f"stats.{table_name}" for table_name in PLAYER_POSTSEASON_TABLES),
    *(f"stats.{table_name}" for table_name in PLAYER_TEAM_POSTSEASON_TABLES),
}

EXPECTED_MODEL_NAMES = (
    "PlayerTeamSeasonRoster",
    "PlayerTeamSeasonTotals",
    "PlayerTeamSeasonPerGame",
    "PlayerTeamSeasonPerMinute",
    "PlayerTeamSeasonPerPoss",
    "PlayerTeamSeasonAdvanced",
    "PlayerTeamSeasonShooting",
    "PlayerTeamSeasonAdjShooting",
    "PlayerTeamSeasonPbp",
    "PlayerSeasonTotals",
    "PlayerSeasonPerGame",
    "PlayerSeasonPerMinute",
    "PlayerSeasonPerPoss",
    "PlayerSeasonAdvanced",
    "PlayerSeasonShooting",
    "PlayerSeasonAdjShooting",
    "PlayerSeasonPbp",
    "PlayerPostseasonTotals",
    "PlayerPostseasonPerGame",
    "PlayerPostseasonPerMinute",
    "PlayerPostseasonPerPoss",
    "PlayerPostseasonAdvanced",
    "PlayerPostseasonShooting",
    "PlayerPostseasonAdjShooting",
    "PlayerPostseasonPbp",
    "PlayerTeamPostseasonTotals",
    "PlayerTeamPostseasonPerGame",
    "PlayerTeamPostseasonPerMinute",
    "PlayerTeamPostseasonPerPoss",
    "PlayerTeamPostseasonAdvanced",
    "PlayerTeamPostseasonShooting",
    "PlayerTeamPostseasonAdjShooting",
    "PlayerTeamPostseasonPbp",
)

LINEAGE_COLUMNS = {"source_url", "cache_path", "parser_version", "created_at", "updated_at"}


def test_stats_tables_are_registered_in_stats_schema() -> None:
    stats_table_keys = {
        table_key for table_key in Base.metadata.tables if table_key.startswith("stats.")
    }

    assert stats_table_keys == EXPECTED_STATS_TABLE_KEYS

    for table_key in EXPECTED_STATS_TABLE_KEYS:
        table = Base.metadata.tables[table_key]
        assert table.schema == "stats"


def test_no_stats_table_uses_jsonb() -> None:
    for table in _stats_tables():
        assert [column.name for column in table.c if isinstance(column.type, JSONB)] == []


def test_team_stint_tables_use_player_team_season_grain() -> None:
    for table_name in (*TEAM_STINT_TABLES, *PLAYER_TEAM_POSTSEASON_TABLES):
        table = Base.metadata.tables[f"stats.{table_name}"]

        assert table.c.player_team_season_id.nullable is False
        assert "player_season_id" not in table.c
        assert _team_stint_constraint_name("uq_stats", table_name) in _constraint_names(table, UniqueConstraint)
        assert _team_stint_constraint_name("fk_stats", table_name) in _constraint_names(table, ForeignKeyConstraint)
        assert _foreign_key_targets(table) == {"core.player_team_seasons.id"}
        assert "source_team_code" not in table.c


def test_player_season_tables_use_player_season_grain() -> None:
    for table_name in (*PLAYER_SEASON_TABLES, *PLAYER_POSTSEASON_TABLES):
        table = Base.metadata.tables[f"stats.{table_name}"]

        assert table.c.player_season_id.nullable is False
        assert "player_team_season_id" not in table.c
        assert _player_season_constraint_name("uq_stats", table_name) in _constraint_names(table, UniqueConstraint)
        assert _player_season_constraint_name("fk_stats", table_name) in _constraint_names(table, ForeignKeyConstraint)
        assert _foreign_key_targets(table) == {"core.player_seasons.id"}
        assert "source_team_code" in table.c


def test_roster_has_only_team_stint_grain() -> None:
    roster = Base.metadata.tables["stats.player_team_season_roster"]

    assert "player_team_season_id" in roster.c
    assert "player_season_id" not in roster.c
    assert "source_team_code" not in roster.c


def test_lineage_columns_are_present_and_non_nullable() -> None:
    for table in _stats_tables():
        assert LINEAGE_COLUMNS.issubset(table.c.keys())
        for column_name in LINEAGE_COLUMNS:
            assert table.c[column_name].nullable is False


def test_official_stat_columns_are_nullable_by_default() -> None:
    non_nullable_columns = {"id", "player_team_season_id", "player_season_id", *LINEAGE_COLUMNS}

    for table in _stats_tables():
        for column in table.c:
            if column.name not in non_nullable_columns:
                assert column.nullable is True


def test_key_column_types_match_stats_contract() -> None:
    roster = Base.metadata.tables["stats.player_team_season_roster"]
    totals = Base.metadata.tables["stats.player_team_season_totals"]
    advanced = Base.metadata.tables["stats.player_team_season_advanced"]
    player_totals = Base.metadata.tables["stats.player_season_totals"]
    postseason_totals = Base.metadata.tables["stats.player_postseason_totals"]

    assert isinstance(roster.c.weight.type, Integer)
    assert isinstance(roster.c.birth_date.type, Date)
    assert isinstance(roster.c.player_name.type, String)
    assert roster.c.player_name.type.length == 200

    assert isinstance(totals.c.fg.type, Integer)
    assert isinstance(totals.c.fg_pct.type, Numeric)
    assert totals.c.fg_pct.type.precision == 10
    assert totals.c.fg_pct.type.scale == 4

    assert isinstance(advanced.c.per.type, Numeric)
    assert advanced.c.per.type.precision == 10
    assert advanced.c.per.type.scale == 4
    assert isinstance(player_totals.c.source_team_code.type, String)
    assert player_totals.c.source_team_code.type.length == 10
    assert isinstance(postseason_totals.c.source_team_code.type, String)
    assert postseason_totals.c.source_team_code.type.length == 10

    for table in _stats_tables():
        assert isinstance(table.c.source_url.type, Text)
        assert isinstance(table.c.cache_path.type, Text)
        assert isinstance(table.c.parser_version.type, String)
        assert table.c.parser_version.type.length == 50
        assert isinstance(table.c.created_at.type, DateTime)
        assert table.c.created_at.type.timezone is True
        assert isinstance(table.c.updated_at.type, DateTime)
        assert table.c.updated_at.type.timezone is True


def test_stats_models_are_exported() -> None:
    for model_name in EXPECTED_MODEL_NAMES:
        assert model_name in models.__all__
        assert getattr(models, model_name).__table__ in _stats_tables()


def _stats_tables() -> list[object]:
    return [Base.metadata.tables[table_key] for table_key in sorted(EXPECTED_STATS_TABLE_KEYS)]


def _constraint_names(table: object, constraint_type: type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
    }


def _foreign_key_targets(table: object) -> set[str]:
    targets: set[str] = set()
    for constraint in table.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            targets.update(element.target_fullname for element in constraint.elements)
    return targets


def _team_stint_constraint_name(prefix: str, table_name: str) -> str:
    suffix = "pts_id" if table_name.startswith("player_team_postseason_") else "player_team_season_id"
    return f"{prefix}_{table_name}_{suffix}"


def _player_season_constraint_name(prefix: str, table_name: str) -> str:
    suffix = "ps_id" if table_name.startswith("player_postseason_") else "player_season_id"
    return f"{prefix}_{table_name}_{suffix}"
