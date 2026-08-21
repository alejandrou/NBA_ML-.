from __future__ import annotations

import inspect
from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import nba_data.scraping.loaders.team_season_stats as stats_loader_module
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
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.loaders import load_team_season_stats

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

TEAM_STINT_CASES = (
    ("roster", PlayerTeamSeasonRoster, "stats.player_team_season_roster"),
    ("totals", PlayerTeamSeasonTotals, "stats.player_team_season_totals"),
    ("per_game", PlayerTeamSeasonPerGame, "stats.player_team_season_per_game"),
    ("per_minute", PlayerTeamSeasonPerMinute, "stats.player_team_season_per_minute"),
    ("per_poss", PlayerTeamSeasonPerPoss, "stats.player_team_season_per_poss"),
    ("advanced", PlayerTeamSeasonAdvanced, "stats.player_team_season_advanced"),
    ("shooting", PlayerTeamSeasonShooting, "stats.player_team_season_shooting"),
    (
        "adj_shooting",
        PlayerTeamSeasonAdjShooting,
        "stats.player_team_season_adj_shooting",
    ),
    ("pbp", PlayerTeamSeasonPbp, "stats.player_team_season_pbp"),
)

AGGREGATE_CASES = (
    ("totals", PlayerSeasonTotals, "stats.player_season_totals"),
    ("per_game", PlayerSeasonPerGame, "stats.player_season_per_game"),
    ("per_minute", PlayerSeasonPerMinute, "stats.player_season_per_minute"),
    ("per_poss", PlayerSeasonPerPoss, "stats.player_season_per_poss"),
    ("advanced", PlayerSeasonAdvanced, "stats.player_season_advanced"),
    ("shooting", PlayerSeasonShooting, "stats.player_season_shooting"),
    ("adj_shooting", PlayerSeasonAdjShooting, "stats.player_season_adj_shooting"),
    ("pbp", PlayerSeasonPbp, "stats.player_season_pbp"),
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
def test_loader_insert_and_rerun_updates_without_duplicate(session: Session) -> None:
    _create_core_grains(session)

    first = load_team_season_stats(session, [_row(values={"games": 74, "pts": 1987})], **_lineage())
    record = session.scalar(select(PlayerTeamSeasonTotals))
    assert record is not None
    created_at = record.created_at

    second = load_team_season_stats(session, [_row(values={"games": 75, "pts": 2000})], **_lineage())
    updated = session.scalar(select(PlayerTeamSeasonTotals))

    assert first.loaded_rows == 1
    assert second.loaded_rows == 1
    assert _count(session, PlayerTeamSeasonTotals) == 1
    assert updated is not None
    assert updated.id == record.id
    assert updated.g == 75
    assert updated.pts == 2000
    assert updated.created_at == created_at


@pytest.mark.unit
@pytest.mark.parametrize(("source_table", "model", "destination_table"), TEAM_STINT_CASES)
def test_all_team_stint_routes_load_expected_tables(
    session: Session,
    source_table: str,
    model: type,
    destination_table: str,
) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(session, [_row(source_table=source_table)], **_lineage())

    assert report.loaded_rows == 1
    assert report.entries[0].destination_table == destination_table
    assert _count(session, model) == 1


@pytest.mark.unit
@pytest.mark.parametrize(("source_table", "model", "destination_table"), AGGREGATE_CASES)
def test_all_aggregate_routes_load_expected_tables(
    session: Session,
    source_table: str,
    model: type,
    destination_table: str,
) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(
        session,
        [_aggregate_row(source_table=source_table)],
        **_lineage(),
    )

    assert report.loaded_rows == 1
    assert report.entries[0].destination_table == destination_table
    assert _count(session, model) == 1


@pytest.mark.unit
def test_roster_loads_type_converted_values(session: Session) -> None:
    _create_core_grains(session)

    load_team_season_stats(
        session,
        [
            _row(
                source_table="roster",
                values={
                    "number": 0,
                    "player": "Jayson Tatum",
                    "pos": "SF",
                    "height": "6-8",
                    "weight": "210",
                    "birth_date": "1998-03-03",
                    "years_experience": "6",
                    "college": "Duke",
                    "flag": "us",
                },
            )
        ],
        **_lineage(),
    )

    roster = session.scalar(select(PlayerTeamSeasonRoster))
    assert roster is not None
    assert roster.jersey_number == "0"
    assert roster.weight == 210
    assert roster.birth_date == date(1998, 3, 3)


@pytest.mark.unit
def test_team_page_loader_populates_player_name_display_from_source_cell(
    session: Session,
) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(
        session,
        [
            _row(
                player_name="Unmapped context name",
                values={"name_display": "Source Row Name", "games": 74},
            )
        ],
        **_lineage(),
    )

    record = session.scalar(select(PlayerTeamSeasonTotals))

    assert report.loaded_rows == 1
    assert record is not None
    assert record.player_name_display == "Source Row Name"


@pytest.mark.unit
def test_tot_aggregate_loads_player_season_table_without_real_tot_team(
    session: Session,
) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(
        session,
        [
            _aggregate_row(
                values={"games": 82, "pts": 2100, "team_abbreviation": "TOT"}
            )
        ],
        **_lineage(),
    )

    assert report.loaded_rows == 1
    assert _count(session, PlayerSeasonTotals) == 1
    assert _count(session, PlayerTeamSeasonTotals) == 0
    assert session.scalar(
        select(func.count()).select_from(Team).where(Team.basketball_reference_team_id == "TOT")
    ) == 0
    assert session.scalar(
        select(func.count()).select_from(TeamSeason).where(TeamSeason.team_abbreviation == "TOT")
    ) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("fixture_name", "expected_reason"),
    (
        ("empty", "missing_season"),
        ("without_player", "missing_player"),
        ("without_player_season", "missing_player_season"),
        ("without_team_season", "missing_team_season"),
        ("without_player_team_season", "missing_player_team_season"),
    ),
)
def test_missing_core_identity_rows_are_skipped_without_creating_core(
    session: Session,
    fixture_name: str,
    expected_reason: str,
) -> None:
    _create_partial_core(session, fixture_name)

    report = load_team_season_stats(session, [_row()], **_lineage())

    assert report.loaded_rows == 0
    assert report.skipped_rows == 1
    assert report.entries[0].reason == expected_reason
    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("row_factory", "row_kwargs", "reason"),
    (
        ("team", {"source_table": "four_factors"}, "unsupported_source_table"),
        (
            "team",
            {"source_table": "totals", "stat_scope": "team_roster"},
            "unsupported_stat_scope",
        ),
        ("aggregate", {"source_table": "roster"}, "unsupported_aggregate_roster"),
    ),
)
def test_unsupported_rows_are_skipped(
    session: Session,
    row_factory: str,
    row_kwargs: dict[str, object],
    reason: str,
) -> None:
    _create_core_grains(session)

    row = _aggregate_row(**row_kwargs) if row_factory == "aggregate" else _row(**row_kwargs)
    report = load_team_season_stats(session, [row], **_lineage())

    assert report.loaded_rows == 0
    assert report.skipped_rows == 1
    assert report.entries[0].reason == reason


@pytest.mark.unit
def test_unknown_and_protected_values_fail_before_stats_writes(session: Session) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(
        session,
        [
            _row(values={"games": 74, "mystery_metric": 1}),
            _row(values={"games": 74, "player_team_season_id": 1}),
        ],
        **_lineage(),
    )

    assert report.loaded_rows == 0
    assert report.failed_rows == 2
    assert all(entry.reason == "invalid_values" for entry in report.entries)
    assert "Unknown normalized stats keys" in str(report.entries[0].message)
    assert "protected keys" in str(report.entries[1].message)
    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
def test_duplicate_input_grains_fail_before_stats_writes(session: Session) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(
        session,
        [_row(values={"games": 74}), _row(values={"games": 75})],
        **_lineage(),
    )

    assert report.loaded_rows == 0
    assert report.failed_rows == 2
    assert {entry.reason for entry in report.entries} == {"duplicate_stats_grain"}
    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
def test_context_and_grain_values_are_not_forwarded_to_repository(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_core_grains(session)
    original = stats_loader_module.StatsRepository.upsert_player_team_season_totals
    captured_values: dict[str, object] = {}

    def spy_upsert(self: object, **kwargs: object) -> object:
        captured_values.update(kwargs["values"])  # type: ignore[index]
        return original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        stats_loader_module.StatsRepository,
        "upsert_player_team_season_totals",
        spy_upsert,
    )

    report = load_team_season_stats(
        session,
        [_row(values={"games": 74, "team_id": "BOS", "team_abbreviation": "BOS"})],
        **_lineage(),
    )

    assert report.loaded_rows == 1
    assert "team_id" not in captured_values
    assert "team_abbreviation" not in captured_values
    assert "player_team_season_id" not in captured_values
    assert captured_values["g"] == 74


@pytest.mark.unit
def test_report_counts_and_serialization_are_json_safe(session: Session) -> None:
    _create_core_grains(session)

    report = load_team_season_stats(
        session,
        [
            _row(),
            _row(source_table="four_factors"),
            _row(source_table="per_game", values={"unknown_metric": 1}),
        ],
        **_lineage(),
    )

    payload = report.to_dict()

    assert payload["total_rows"] == 3
    assert payload["loaded_rows"] == 1
    assert payload["skipped_rows"] == 1
    assert payload["failed_rows"] == 1
    assert isinstance(payload["entries"], list)
    assert payload["entries"][0]["status"] == "loaded"  # type: ignore[index]


@pytest.mark.unit
def test_loader_does_not_commit_or_rollback(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_core_grains(session)

    def fail_transaction_ownership() -> None:
        raise AssertionError("stats loader must not own transactions")

    monkeypatch.setattr(session, "commit", fail_transaction_ownership)
    monkeypatch.setattr(session, "rollback", fail_transaction_ownership)

    report = load_team_season_stats(session, [_row()], **_lineage())

    assert report.loaded_rows == 1
    assert _count(session, PlayerTeamSeasonTotals) == 1


@pytest.mark.unit
def test_caller_rollback_removes_loaded_stats_rows(session: Session) -> None:
    _create_core_grains(session)

    load_team_season_stats(session, [_row()], **_lineage())
    assert _count(session, PlayerTeamSeasonTotals) == 1

    session.rollback()

    assert _count(session, PlayerTeamSeasonTotals) == 0


@pytest.mark.unit
def test_stats_loader_source_has_no_network_or_parser_boundaries() -> None:
    module_source = inspect.getsource(stats_loader_module)

    for forbidden in (
        "requests",
        "httpx",
        "BasketballReferenceClient",
        "HtmlCache",
        "parse_team_season_page",
        "normalize_team_season_page",
        "offline_processor",
        "offline_backfill",
        ".commit(",
        ".rollback(",
    ):
        assert forbidden not in module_source


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


def _create_partial_core(session: Session, fixture_name: str) -> None:
    if fixture_name == "empty":
        return

    repository = CoreRepository(session)
    season = repository.get_or_create_season(league="NBA", season_year=2024)
    team = repository.get_or_create_team(
        basketball_reference_team_id="BOS",
        current_abbreviation="BOS",
        current_name="Boston Celtics",
    )
    if fixture_name != "without_team_season":
        team_season = repository.get_or_create_team_season(
            team=team,
            season=season,
            team_abbreviation="BOS",
        )
    else:
        team_season = None

    if fixture_name == "without_player":
        return

    player = repository.get_or_create_player(
        basketball_reference_player_id="tatumja01",
        full_name="Jayson Tatum",
    )
    if fixture_name == "without_player_season":
        return

    player_season = repository.get_or_create_player_season(player=player, season=season)
    if fixture_name == "without_player_team_season":
        return
    if team_season is not None:
        repository.get_or_create_player_team_season(
            player_season=player_season,
            team_season=team_season,
        )


def _row(**overrides: object) -> dict[str, object]:
    source_table = str(overrides.pop("source_table", "totals"))
    stat_scope = str(
        overrides.pop(
            "stat_scope",
            "team_roster" if source_table == "roster" else "player_team_season",
        )
    )
    values = overrides.pop("values", _values_for_source_table(source_table))
    row: dict[str, object] = {
        "league": "NBA",
        "season_year": 2024,
        "team_abbreviation": "BOS",
        "team_context": "team",
        "source_table": source_table,
        "stat_scope": stat_scope,
        "player_name": "Jayson Tatum",
        "basketball_reference_player_id": "tatumja01",
        "stable_player_key": "tatumja01",
        "identifier_status": "present",
        "values": values,
    }
    row.update(overrides)
    return row


def _aggregate_row(**overrides: object) -> dict[str, object]:
    source_table = str(overrides.pop("source_table", "totals"))
    values = overrides.pop("values", _values_for_source_table(source_table))
    row = _row(
        source_table=source_table,
        team_abbreviation="TOT",
        team_context="aggregate",
        stat_scope="player_season_aggregate",
        values=values,
    )
    row.update(overrides)
    return row


def _values_for_source_table(source_table: str) -> dict[str, object]:
    return {
        "roster": {
            "number": 0,
            "player": "Jayson Tatum",
            "pos": "SF",
            "weight": 210,
            "birth_date": "not-a-date",
        },
        "totals": {"name_display": "Jayson Tatum", "games": 74, "pts": 1987},
        "per_game": {"name_display": "Jayson Tatum", "pts_per_g": 26.9},
        "per_minute": {"name_display": "Jayson Tatum", "pts_per_minute_36": 29.1},
        "per_poss": {"name_display": "Jayson Tatum", "pts_per_poss": 38.2},
        "advanced": {"name_display": "Jayson Tatum", "per": 22.5},
        "shooting": {"name_display": "Jayson Tatum", "pct_fga_00_03": 0.12},
        "adj_shooting": {"name_display": "Jayson Tatum", "adj_ts_pct": 104.0},
        "pbp": {"name_display": "Jayson Tatum", "pct_1": 2.0},
    }.get(source_table, {"name_display": "Jayson Tatum"})


def _lineage() -> dict[str, str]:
    return {
        "source_url": "https://www.basketball-reference.com/teams/BOS/2024.html",
        "cache_path": "cache/teams/BOS/2024.html.gz",
        "parser_version": "team-season-parser-v1",
    }


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
