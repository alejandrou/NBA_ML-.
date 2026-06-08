from __future__ import annotations

import inspect
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import nba_data.db.models.stats as stats_models
import nba_data.db.repositories.stats as stats_repository_module
from nba_data.db.models import (
    Player,
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
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository, StatsRepository, TeamStintStatsUpsert

CORE_TABLES = (
    Season.__table__,
    Team.__table__,
    TeamAlias.__table__,
    Player.__table__,
    TeamSeason.__table__,
    PlayerSeason.__table__,
    PlayerTeamSeason.__table__,
)

STATS_TABLES = (
    PlayerTeamSeasonRoster.__table__,
    PlayerTeamSeasonTotals.__table__,
    PlayerTeamSeasonPerGame.__table__,
    PlayerTeamSeasonPerMinute.__table__,
    PlayerTeamSeasonPerPoss.__table__,
    PlayerTeamSeasonAdvanced.__table__,
    PlayerTeamSeasonShooting.__table__,
    PlayerTeamSeasonAdjShooting.__table__,
    PlayerTeamSeasonPbp.__table__,
    PlayerSeasonTotals.__table__,
    PlayerSeasonPerGame.__table__,
    PlayerSeasonPerMinute.__table__,
    PlayerSeasonPerPoss.__table__,
    PlayerSeasonAdvanced.__table__,
    PlayerSeasonShooting.__table__,
    PlayerSeasonAdjShooting.__table__,
    PlayerSeasonPbp.__table__,
)

TEAM_STINT_WRAPPERS = (
    ("upsert_player_team_season_roster", PlayerTeamSeasonRoster, {"player_name": "Jayson Tatum"}),
    ("upsert_player_team_season_totals", PlayerTeamSeasonTotals, {"g": 74}),
    ("upsert_player_team_season_per_game", PlayerTeamSeasonPerGame, {"pts_per_game": Decimal("26.9")}),
    ("upsert_player_team_season_per_minute", PlayerTeamSeasonPerMinute, {"pts_per_36": Decimal("29.1")}),
    ("upsert_player_team_season_per_poss", PlayerTeamSeasonPerPoss, {"pts_per_poss": Decimal("38.2")}),
    ("upsert_player_team_season_advanced", PlayerTeamSeasonAdvanced, {"per": Decimal("22.5")}),
    ("upsert_player_team_season_shooting", PlayerTeamSeasonShooting, {"avg_dist": Decimal("13.2")}),
    (
        "upsert_player_team_season_adj_shooting",
        PlayerTeamSeasonAdjShooting,
        {"adj_ts_pct": Decimal("104.0")},
    ),
    ("upsert_player_team_season_pbp", PlayerTeamSeasonPbp, {"pct_pg": Decimal("2.0")}),
)

PLAYER_SEASON_WRAPPERS = (
    ("upsert_player_season_totals", PlayerSeasonTotals, {"g": 82}),
    ("upsert_player_season_per_game", PlayerSeasonPerGame, {"pts_per_game": Decimal("25.1")}),
    ("upsert_player_season_per_minute", PlayerSeasonPerMinute, {"pts_per_36": Decimal("27.7")}),
    ("upsert_player_season_per_poss", PlayerSeasonPerPoss, {"pts_per_poss": Decimal("36.4")}),
    ("upsert_player_season_advanced", PlayerSeasonAdvanced, {"per": Decimal("21.2")}),
    ("upsert_player_season_shooting", PlayerSeasonShooting, {"avg_dist": Decimal("12.7")}),
    (
        "upsert_player_season_adj_shooting",
        PlayerSeasonAdjShooting,
        {"adj_ts_pct": Decimal("102.0")},
    ),
    ("upsert_player_season_pbp", PlayerSeasonPbp, {"pct_pg": Decimal("1.0")}),
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for table in (*CORE_TABLES, *STATS_TABLES):
            table.create(connection)

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        yield test_session

    engine.dispose()


@pytest.mark.unit
def test_team_stint_totals_insert_and_rerun_updates_without_duplicate(
    session: Session,
) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)

    first = repository.upsert_player_team_season_totals(
        player_team_season_id=player_team_season.id,
        values={"g": 70, "pts": 1800},
        **_lineage("first"),
    )
    created_at = first.created_at
    first_updated_at = first.updated_at

    second = repository.upsert_player_team_season_totals(
        player_team_season_id=player_team_season.id,
        values={"g": 71, "pts": None},
        **_lineage("second"),
    )

    assert second.id == first.id
    assert _count(session, PlayerTeamSeasonTotals) == 1
    assert second.g == 71
    assert second.pts is None
    assert second.source_url.endswith("second.html")
    assert second.cache_path.endswith("second.html.gz")
    assert second.parser_version == "parser-second"
    assert second.created_at == created_at
    assert second.updated_at >= first_updated_at


@pytest.mark.unit
def test_aggregate_totals_insert_and_rerun_updates_without_duplicate(
    session: Session,
) -> None:
    _, player_season = _create_core_grains(session)
    repository = StatsRepository(session)

    first = repository.upsert_player_season_totals(
        player_season_id=player_season.id,
        values={"g": 80, "pts": 1900},
        **_lineage("aggregate-first"),
    )
    second = repository.upsert_player_season_totals(
        player_season_id=player_season.id,
        values={"g": 81, "pts": 2000},
        **_lineage("aggregate-second"),
    )

    assert second.id == first.id
    assert _count(session, PlayerSeasonTotals) == 1
    assert second.g == 81
    assert second.pts == 2000
    assert second.source_url.endswith("aggregate-second.html")


@pytest.mark.unit
def test_roster_insert_update_has_no_aggregate_roster_equivalent(session: Session) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)

    first = repository.upsert_player_team_season_roster(
        player_team_season_id=player_team_season.id,
        values={"jersey_number": "0", "position": "SF"},
        **_lineage("roster-first"),
    )
    second = repository.upsert_player_team_season_roster(
        player_team_season_id=player_team_season.id,
        values={"jersey_number": "8", "position": "PF"},
        **_lineage("roster-second"),
    )

    assert second.id == first.id
    assert _count(session, PlayerTeamSeasonRoster) == 1
    assert second.jersey_number == "8"
    assert second.position == "PF"
    assert not hasattr(stats_models, "PlayerSeasonRoster")
    assert not hasattr(repository, "upsert_player_season_roster")


@pytest.mark.unit
@pytest.mark.parametrize(("method_name", "model", "values"), TEAM_STINT_WRAPPERS)
def test_all_team_stint_wrappers_exist_and_insert_rows(
    session: Session,
    method_name: str,
    model: type,
    values: dict[str, object],
) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)
    method = getattr(repository, method_name)

    record = method(
        player_team_season_id=player_team_season.id,
        values=values,
        **_lineage(method_name),
    )

    assert isinstance(record, model)
    assert _count(session, model) == 1


@pytest.mark.unit
@pytest.mark.parametrize(("method_name", "model", "values"), PLAYER_SEASON_WRAPPERS)
def test_all_player_season_wrappers_exist_and_insert_rows(
    session: Session,
    method_name: str,
    model: type,
    values: dict[str, object],
) -> None:
    _, player_season = _create_core_grains(session)
    repository = StatsRepository(session)
    method = getattr(repository, method_name)

    record = method(
        player_season_id=player_season.id,
        values=values,
        **_lineage(method_name),
    )

    assert isinstance(record, model)
    assert _count(session, model) == 1


@pytest.mark.unit
def test_duplicate_batch_grains_fail_before_stats_writes(session: Session) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)
    rows = [
        TeamStintStatsUpsert(
            model=PlayerTeamSeasonTotals,
            player_team_season_id=player_team_season.id,
            values={"g": 70},
            **_lineage("batch-one"),
        ),
        TeamStintStatsUpsert(
            model=PlayerTeamSeasonTotals,
            player_team_season_id=player_team_season.id,
            values={"g": 71},
            **_lineage("batch-two"),
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate stats upsert grain"):
        repository.upsert_player_team_season_stats(rows)

    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
def test_unknown_columns_fail_with_clear_error(session: Session) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)

    with pytest.raises(ValueError, match="Unknown stats columns.*unknown_metric"):
        repository.upsert_player_team_season_totals(
            player_team_season_id=player_team_season.id,
            values={"unknown_metric": 1},
            **_lineage("unknown"),
        )

    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
@pytest.mark.parametrize("protected_column", ["id", "player_team_season_id", "updated_at"])
def test_protected_columns_cannot_be_supplied_in_values(
    session: Session,
    protected_column: str,
) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)

    with pytest.raises(ValueError, match="protected columns"):
        repository.upsert_player_team_season_totals(
            player_team_season_id=player_team_season.id,
            values={protected_column: 123},
            **_lineage(f"protected-{protected_column}"),
        )

    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
def test_wrong_grain_model_routing_fails(session: Session) -> None:
    player_team_season, player_season = _create_core_grains(session)
    repository = StatsRepository(session)

    with pytest.raises(ValueError, match="player_team_season_id upserts"):
        repository.upsert_player_team_season_stat(
            model=PlayerSeasonTotals,
            player_team_season_id=player_team_season.id,
            values={"g": 1},
            **_lineage("wrong-team"),
        )

    with pytest.raises(ValueError, match="player_season_id upserts"):
        repository.upsert_player_season_stat(
            model=PlayerTeamSeasonTotals,
            player_season_id=player_season.id,
            values={"g": 1},
            **_lineage("wrong-aggregate"),
        )


@pytest.mark.unit
def test_missing_team_stint_core_grain_fails_without_creating_core_rows(
    session: Session,
) -> None:
    repository = StatsRepository(session)

    with pytest.raises(ValueError, match="core.player_team_seasons"):
        repository.upsert_player_team_season_totals(
            player_team_season_id=999,
            values={"g": 1},
            **_lineage("missing-team-stint"),
        )

    assert _count(session, PlayerTeamSeasonTotals) == 0
    assert _count(session, PlayerTeamSeason) == 0
    assert _count(session, PlayerSeason) == 0


@pytest.mark.unit
def test_missing_aggregate_core_grain_fails_without_creating_core_rows(
    session: Session,
) -> None:
    repository = StatsRepository(session)

    with pytest.raises(ValueError, match="core.player_seasons"):
        repository.upsert_player_season_totals(
            player_season_id=999,
            values={"g": 1},
            **_lineage("missing-aggregate"),
        )

    assert _count(session, PlayerSeasonTotals) == 0
    assert _count(session, PlayerSeason) == 0
    assert _count(session, Player) == 0


@pytest.mark.unit
def test_repositories_do_not_commit_or_rollback(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)

    def fail_transaction_ownership() -> None:
        raise AssertionError("stats repository must not own transactions")

    monkeypatch.setattr(session, "commit", fail_transaction_ownership)
    monkeypatch.setattr(session, "rollback", fail_transaction_ownership)

    repository.upsert_player_team_season_totals(
        player_team_season_id=player_team_season.id,
        values={"g": 70},
        **_lineage("no-commit"),
    )

    assert _count(session, PlayerTeamSeasonTotals) == 1


@pytest.mark.unit
def test_caller_rollback_removes_inserted_stats_rows(session: Session) -> None:
    player_team_season, _ = _create_core_grains(session)
    repository = StatsRepository(session)

    repository.upsert_player_team_season_totals(
        player_team_season_id=player_team_season.id,
        values={"g": 70},
        **_lineage("rollback"),
    )
    assert _count(session, PlayerTeamSeasonTotals) == 1

    session.rollback()

    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
def test_stats_repository_source_has_no_network_or_loader_boundaries() -> None:
    module_source = inspect.getsource(stats_repository_module)

    for forbidden in (
        "requests",
        "httpx",
        "BasketballReferenceClient",
        "acquisition",
        "HtmlCache",
        "parse_team_season_page",
        "normalize_team_season_page",
    ):
        assert forbidden not in module_source

    assert ".commit(" not in module_source
    assert ".rollback(" not in module_source


def _create_core_grains(session: Session) -> tuple[PlayerTeamSeason, PlayerSeason]:
    repository = CoreRepository(session)
    season = repository.get_or_create_season(league="NBA", season_year=2024)
    team = repository.get_or_create_team(
        basketball_reference_team_id="BOS",
        current_abbreviation="BOS",
        current_name="Boston Celtics",
    )
    repository.get_or_create_team_alias(
        team=team,
        abbreviation="BOS",
        name="Boston Celtics",
        season_year=2024,
    )
    team_season = repository.get_or_create_team_season(
        team=team,
        season=season,
        team_abbreviation="BOS",
    )
    player = repository.get_or_create_player(
        basketball_reference_player_id="tatumja01",
        full_name="Jayson Tatum",
    )
    player_season = repository.get_or_create_player_season(player=player, season=season)
    player_team_season = repository.get_or_create_player_team_season(
        player_season=player_season,
        team_season=team_season,
        roster_number="0",
        roster_position="SF",
    )
    return player_team_season, player_season


def _lineage(label: str) -> dict[str, str]:
    return {
        "source_url": f"https://www.basketball-reference.com/teams/BOS/{label}.html",
        "cache_path": f"cache/{label}.html.gz",
        "parser_version": f"parser-{label}",
    }


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
