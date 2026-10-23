"""The game grain's mapped schema, its frozen revision, and the parser agree.

Revision 0009 carries its check conditions as literal text, and the models
declare the same text. Nothing in SQLAlchemy keeps the two equal, and nothing
keeps the allowed `game_type` and `participation` values equal to what the box
score parser emits. These tests are the thing that does.

Behaviour on PostgreSQL is proven in
`tests/integration/test_game_schema_postgres.py`.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

import nba_data.db.models as models
from nba_data.db.base import Base
from nba_data.db.models import Game, PlayerGameTotals, TeamGameTotals, TeamSeason
from nba_data.scraping.parsers import box_score

REVISION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0009_games_and_box_scores.py"
)

# (mapped table, check constraint name, revision constant holding its text)
FROZEN_CHECKS = (
    ("core.games", "ck_core_games_bref_id_format", "GAMES_BREF_ID_FORMAT"),
    ("core.games", "ck_core_games_distinct_teams", "GAMES_DISTINCT_TEAMS"),
    ("core.games", "ck_core_games_game_type", "GAMES_GAME_TYPE"),
    ("core.games", "ck_core_games_status", "GAMES_STATUS"),
    ("core.games", "ck_core_games_final_has_game_type", "GAMES_FINAL_HAS_GAME_TYPE"),
    ("core.games", "ck_core_games_attendance_non_negative", "GAMES_ATTENDANCE_NON_NEGATIVE"),
    (
        "stats.team_game_totals",
        "ck_stats_team_game_totals_non_negative",
        "GAME_COUNTERS_NON_NEGATIVE",
    ),
    (
        "stats.player_game_totals",
        "ck_stats_player_game_totals_participation",
        "PLAYER_GAME_PARTICIPATION",
    ),
    (
        "stats.player_game_totals",
        "ck_stats_player_game_totals_played_has_seconds",
        "PLAYER_GAME_PLAYED_HAS_SECONDS",
    ),
    (
        "stats.player_game_totals",
        "ck_stats_player_game_totals_absent_line_empty",
        "PLAYER_GAME_ABSENT_LINE_EMPTY",
    ),
    (
        "stats.player_game_totals",
        "ck_stats_player_game_totals_non_negative",
        "GAME_COUNTERS_NON_NEGATIVE",
    ),
)

PARSER_GAME_TYPES = {
    value
    for name, value in vars(box_score).items()
    if name.startswith("GAME_TYPE_") and value != box_score.GAME_TYPE_UNKNOWN
}
PARSER_PARTICIPATIONS = {
    value for name, value in vars(box_score).items() if name.startswith("PARTICIPATION_")
}

LINEAGE_COLUMNS = {"source_url", "cache_path", "parser_version", "created_at", "updated_at"}


@pytest.fixture(scope="module")
def revision_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_game_revision_under_test", REVISION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_game_tables_are_registered_in_their_schemas() -> None:
    assert Base.metadata.tables["core.games"] is Game.__table__
    assert Base.metadata.tables["stats.team_game_totals"] is TeamGameTotals.__table__
    assert Base.metadata.tables["stats.player_game_totals"] is PlayerGameTotals.__table__
    assert {"Game", "TeamGameTotals", "PlayerGameTotals"} <= set(models.__all__)


def test_games_columns_keep_unknown_apart_from_false_and_zero() -> None:
    columns = Game.__table__.c

    for name in (
        "basketball_reference_game_id",
        "season_id",
        "home_team_season_id",
        "away_team_season_id",
        "game_date",
        "status",
    ):
        assert columns[name].nullable is False, name
    for name in ("start_time_et", "game_type", "venue", "neutral_site", "attendance"):
        assert columns[name].nullable is True, name

    assert columns.neutral_site.default is None
    assert columns.neutral_site.server_default is None
    # The result lives in `stats.team_game_totals.pts`, nowhere in `core`.
    assert not {"pts", "home_pts", "away_pts", "home_score", "away_score"} & set(columns.keys())
    assert not LINEAGE_COLUMNS & set(columns.keys())


def test_games_keys_and_indexes() -> None:
    table = Game.__table__

    assert _unique_columns(table) == {
        "uq_core_games_bref_id": ("basketball_reference_game_id",),
    }
    assert _foreign_keys(table) == {
        "fk_core_games_season_id": (("season_id",), ("core.seasons.id",)),
        "fk_core_games_home_team_season": (
            ("home_team_season_id", "season_id"),
            ("core.team_seasons.id", "core.team_seasons.season_id"),
        ),
        "fk_core_games_away_team_season": (
            ("away_team_season_id", "season_id"),
            ("core.team_seasons.id", "core.team_seasons.season_id"),
        ),
    }
    assert _indexes(table) == {
        "ix_core_games_home_team_season_date": ("home_team_season_id", "game_date"),
        "ix_core_games_away_team_season_date": ("away_team_season_id", "game_date"),
        "ix_core_games_game_date": ("game_date",),
    }
    assert set(_check_names(table)) == {
        name for table_key, name, _ in FROZEN_CHECKS if table_key == "core.games"
    }


def test_team_seasons_expose_the_composite_key_target() -> None:
    assert _unique_columns(TeamSeason.__table__)["uq_core_team_seasons_id_season"] == (
        "id",
        "season_id",
    )


def test_team_game_totals_keys_and_columns() -> None:
    table = TeamGameTotals.__table__

    assert _unique_columns(table) == {
        "uq_stats_team_game_totals_game_team": ("game_id", "team_season_id"),
        "uq_stats_team_game_totals_game_side": ("game_id", "is_home"),
    }
    assert _foreign_keys(table) == {
        "fk_stats_team_game_totals_game_id": (("game_id",), ("core.games.id",)),
        "fk_stats_team_game_totals_team_season_id": (
            ("team_season_id",),
            ("core.team_seasons.id",),
        ),
    }
    assert _indexes(table) == {"ix_stats_team_game_totals_team_season_id": ("team_season_id",)}
    assert set(_check_names(table)) == {"ck_stats_team_game_totals_non_negative"}

    for name in ("game_id", "team_season_id", "is_home", "seconds_played", "pts"):
        assert table.c[name].nullable is False, name
    for name in box_score.COUNTING_STATS:
        if name != "pts":
            assert table.c[name].nullable is True, name
    assert LINEAGE_COLUMNS.issubset(table.c.keys())


def test_player_game_totals_keys_and_columns() -> None:
    table = PlayerGameTotals.__table__

    assert _unique_columns(table) == {
        "uq_stats_player_game_totals_game_player": ("game_id", "player_id"),
    }
    assert _foreign_keys(table) == {
        "fk_stats_player_game_totals_player_id": (("player_id",), ("core.players.id",)),
        "fk_stats_player_game_totals_team_game": (
            ("game_id", "team_season_id"),
            ("stats.team_game_totals.game_id", "stats.team_game_totals.team_season_id"),
        ),
    }
    assert _indexes(table) == {"ix_stats_player_game_totals_player_id": ("player_id",)}
    assert set(_check_names(table)) == {
        name for table_key, name, _ in FROZEN_CHECKS if table_key == "stats.player_game_totals"
    }
    # Not routed through `core.player_team_seasons`: inactive-only and
    # current-season players have no player-season row.
    assert "player_team_season_id" not in table.c

    for name in ("game_id", "player_id", "team_season_id", "starter", "participation"):
        assert table.c[name].nullable is False, name
    for name in ("participation_reason", "seconds_played", "plus_minus", *box_score.COUNTING_STATS):
        assert table.c[name].nullable is True, name
    assert LINEAGE_COLUMNS.issubset(table.c.keys())


def test_both_box_score_tables_carry_every_parser_counting_stat() -> None:
    for table in (TeamGameTotals.__table__, PlayerGameTotals.__table__):
        assert set(box_score.COUNTING_STATS) <= set(table.c.keys())


def test_allowed_game_types_equal_the_parser_types_without_unknown() -> None:
    allowed = _quoted_values(_check_text(Game.__table__, "ck_core_games_game_type"))

    assert allowed == PARSER_GAME_TYPES
    assert box_score.GAME_TYPE_UNKNOWN not in allowed


def test_allowed_participations_equal_the_parser_values() -> None:
    allowed = _quoted_values(
        _check_text(PlayerGameTotals.__table__, "ck_stats_player_game_totals_participation")
    )

    assert allowed == PARSER_PARTICIPATIONS


def test_the_counter_checks_cover_every_counting_stat() -> None:
    for table, name in (
        (TeamGameTotals.__table__, "ck_stats_team_game_totals_non_negative"),
        (PlayerGameTotals.__table__, "ck_stats_player_game_totals_non_negative"),
    ):
        guarded = set(re.findall(r"(\w+) >= 0", _check_text(table, name)))
        assert guarded == {"seconds_played", *box_score.COUNTING_STATS}, name

    absent = _check_text(PlayerGameTotals.__table__, "ck_stats_player_game_totals_absent_line_empty")
    emptied = set(re.findall(r"(\w+) IS NULL", absent))
    assert emptied == {"seconds_played", "plus_minus", *box_score.COUNTING_STATS}
    assert "NOT starter" in absent


@pytest.mark.parametrize(("table_key", "check_name", "constant"), FROZEN_CHECKS)
def test_the_mapped_check_matches_the_frozen_revision_text(
    revision_module: ModuleType, table_key: str, check_name: str, constant: str
) -> None:
    mapped = _check_text(Base.metadata.tables[table_key], check_name)

    assert _normalized(mapped) == _normalized(getattr(revision_module, constant))


def test_the_revision_does_not_import_the_models_or_the_parser() -> None:
    """Importing either would make an applied revision change retroactively."""

    source = REVISION_PATH.read_text(encoding="utf-8")

    assert "nba_data" not in source


def test_the_revision_chains_on_the_previous_head(revision_module: ModuleType) -> None:
    assert revision_module.revision == "0009_games_and_box_scores"
    assert revision_module.down_revision == "0008_drop_raw_schema"


def _check_names(table: Table) -> list[str]:
    return [
        str(constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]


def _check_text(table: Table, name: str) -> str:
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == name:
            return str(constraint.sqltext)
    raise AssertionError(f"{table.fullname} has no check constraint {name!r}")


def _unique_columns(table: Table) -> dict[str, tuple[str, ...]]:
    return {
        str(constraint.name): tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_keys(table: Table) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    return {
        str(constraint.name): (
            tuple(constraint.column_keys),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def _indexes(table: Table) -> dict[str, tuple[str, ...]]:
    return {
        str(index.name): tuple(column.name for column in index.columns)
        for index in table.indexes
    }


def _quoted_values(condition: str) -> set[str]:
    return set(re.findall(r"'([^']*)'", condition))


def _normalized(condition: str) -> str:
    return " ".join(condition.split())
