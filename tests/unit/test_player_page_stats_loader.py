from __future__ import annotations

import inspect
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import nba_data.scraping.loaders.player_page_stats as player_stats_loader_module
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerSeasonAdvanced,
    PlayerSeasonPerGame,
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
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.loaders.player_page_stats import load_player_page_stats

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
    PlayerSeasonAdvanced.__table__,
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
def test_player_page_stats_loader_upserts_idempotently_with_source_team_code(session: Session) -> None:
    _create_player_season(session, player_id="hardeja01", season_year=2021, full_name="James Harden")

    first = load_player_page_stats(session, [_row(values={"games": 44, "pts": 1083})], **_lineage())
    second = load_player_page_stats(session, [_row(values={"games": 45, "pts": 1090})], **_lineage())

    record = session.scalar(select(PlayerSeasonTotals))

    assert first.loaded_rows == 1
    assert second.loaded_rows == 1
    assert _count(session, PlayerSeasonTotals) == 1
    assert record is not None
    assert record.g == 45
    assert record.pts == 1090
    assert record.source_team_code == "2TM"


@pytest.mark.unit
def test_player_page_stats_loader_skips_unresolved_player_season(session: Session) -> None:
    report = load_player_page_stats(session, [_row()], **_lineage())

    assert report.loaded_rows == 0
    assert report.skipped_rows == 1
    assert report.entries[0].reason in {"missing_season", "missing_player", "missing_player_season"}
    assert _count(session, PlayerSeasonTotals) == 0


@pytest.mark.unit
def test_player_page_stats_loader_routes_supported_tables(session: Session) -> None:
    _create_player_season(session, player_id="brownja02", season_year=2024, full_name="Jaylen Brown")

    report = load_player_page_stats(
        session,
        [
            _row(source_table="totals", season_year=2024, basketball_reference_player_id="brownja02"),
            _row(
                source_table="per_game",
                season_year=2024,
                basketball_reference_player_id="brownja02",
                values={"games": 70, "pts_per_g": Decimal("23.1")},
                source_team_code="BOS",
            ),
            _row(
                source_table="advanced",
                season_year=2024,
                basketball_reference_player_id="brownja02",
                values={"games": 70, "mp": 2486, "per": Decimal("19.1")},
                source_team_code="BOS",
            ),
        ],
        **_lineage(),
    )

    assert report.loaded_rows == 3
    assert _count(session, PlayerSeasonTotals) == 1
    assert _count(session, PlayerSeasonPerGame) == 1
    assert _count(session, PlayerSeasonAdvanced) == 1


@pytest.mark.unit
def test_player_page_stats_loader_rejects_tot_source_team_code(session: Session) -> None:
    _create_player_season(session, player_id="hardeja01", season_year=2021, full_name="James Harden")

    report = load_player_page_stats(session, [_row(source_team_code="TOT")], **_lineage())

    assert report.loaded_rows == 0
    assert report.skipped_rows == 1
    assert report.entries[0].reason == "invalid_source_team_code"


@pytest.mark.unit
def test_player_page_stats_loader_source_has_no_network_or_parser_boundaries() -> None:
    module_source = inspect.getsource(player_stats_loader_module)

    for forbidden in (
        "requests",
        "httpx",
        "BasketballReferenceClient",
        "HtmlCache",
        "parse_player_page_regular_season",
        "normalize_player_page_regular_season",
        ".commit(",
        ".rollback(",
    ):
        assert forbidden not in module_source


def _create_player_season(
    session: Session,
    *,
    player_id: str,
    season_year: int,
    full_name: str,
) -> PlayerSeason:
    repository = CoreRepository(session)
    season = repository.get_or_create_season(league="NBA", season_year=season_year)
    player = repository.get_or_create_player(
        basketball_reference_player_id=player_id,
        full_name=full_name,
    )
    return repository.get_or_create_player_season(player=player, season=season)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "league": "NBA",
        "season_year": 2021,
        "source_table": "totals",
        "stat_scope": "player_season_aggregate",
        "player_name": "James Harden",
        "basketball_reference_player_id": "hardeja01",
        "stable_player_key": "hardeja01",
        "identifier_status": "present",
        "source_team_code": "2TM",
        "values": {"games": 44, "pts": 1083},
    }
    row.update(overrides)
    return row


def _lineage() -> dict[str, str]:
    return {
        "source_url": "https://www.basketball-reference.com/players/h/hardeja01.html",
        "cache_path": "cache/players/hardeja01.html.gz",
        "parser_version": "player-page-parser-v1",
    }


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
