from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from nba_data.api.schemas.player_stats import (
    AdvancedAggregateResponse,
    PbpStintListResponse,
    TotalsAggregateResponse,
)
from nba_data.api.services import player_stats as stat_service
from nba_data.api.services.player_stats import StatisticsNotFoundError
from nba_data.api.services.players import PlayerNotFoundError, PlayerSeasonNotFoundError
from nba_data.db.models.stats import (
    PlayerSeasonAdvanced,
    PlayerSeasonTotals,
    PlayerTeamSeasonPbp,
)
from nba_data.domain.stat_dimensions import SeasonType, StatFamily

SESSION: Any = object()


def _stat_row(table: Any, **values: object) -> dict[str, object]:
    """Every published column of `table` as `null`, overridden by `values`."""
    row: dict[str, object] = {
        column.name: None
        for column in table.__table__.columns
        if column.name not in stat_service.stat_queries.UNPUBLISHED_COLUMNS
    }
    row.update(values)
    return row


@pytest.fixture
def known(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """`jamesle01` exists with a 2004 season (private id 11); nothing else does."""
    calls: dict[str, Any] = {"aggregate": None, "stints": None}

    def fake_get_player(session: object, basketball_reference_player_id: str) -> object | None:
        return SimpleNamespace() if basketball_reference_player_id == "jamesle01" else None

    def fake_player_season_id(session: object, pid: str, season_year: int) -> int | None:
        return 11 if (pid, season_year) == ("jamesle01", 2004) else None

    def fake_aggregate(session: object, table: Any, player_season_id: int) -> object:
        calls["aggregate_table"] = table
        calls["aggregate_id"] = player_season_id
        return calls["aggregate"]

    def fake_list(
        session: object, table: Any, player_season_id: int, *, offset: int, limit: int
    ) -> object:
        calls["stint_table"] = table
        calls["offset"] = offset
        calls["limit"] = limit
        return calls["stints"] or []

    def fake_count(session: object, table: Any, player_season_id: int) -> int:
        return 9

    monkeypatch.setattr(stat_service.player_queries, "get_player", fake_get_player)
    monkeypatch.setattr(stat_service.stat_queries, "get_player_season_id", fake_player_season_id)
    monkeypatch.setattr(stat_service.stat_queries, "get_aggregate_stats", fake_aggregate)
    monkeypatch.setattr(stat_service.stat_queries, "list_stint_stats", fake_list)
    monkeypatch.setattr(stat_service.stat_queries, "count_stint_stats", fake_count)
    return calls


def _aggregate(
    family: StatFamily = StatFamily.TOTALS, *, pid: str = "jamesle01", year: int = 2004
) -> Any:
    return stat_service.get_aggregate_stats(
        SESSION,
        basketball_reference_player_id=pid,
        season_year=year,
        season_type=SeasonType.REGULAR,
        family=family,
    )


@pytest.mark.unit
def test_aggregate_reads_the_family_table_and_maps_the_identity(known: dict[str, Any]) -> None:
    known["aggregate"] = _stat_row(
        PlayerSeasonTotals, source_team_code="CLE", pts=2175, fg_pct=Decimal("0.4660")
    )

    body = _aggregate()

    assert isinstance(body, TotalsAggregateResponse)
    assert known["aggregate_table"] is PlayerSeasonTotals
    assert known["aggregate_id"] == 11
    assert body.season_year == 2004
    assert body.season_type is SeasonType.REGULAR
    assert body.source_team_code == "CLE"
    assert body.is_multi_team is False
    assert body.model_dump(mode="json")["fg_pct"] == 0.466


@pytest.mark.unit
@pytest.mark.parametrize(
    ("source_team_code", "is_multi_team"),
    [("2TM", True), ("5TM", True), ("CLE", False), (None, False)],
)
def test_is_multi_team_follows_the_shared_marker_rule(
    known: dict[str, Any], source_team_code: str | None, is_multi_team: bool
) -> None:
    known["aggregate"] = _stat_row(PlayerSeasonAdvanced, source_team_code=source_team_code)

    body = _aggregate(StatFamily.ADVANCED)

    assert isinstance(body, AdvancedAggregateResponse)
    assert body.is_multi_team is is_multi_team
    assert body.source_team_code == source_team_code


@pytest.mark.unit
def test_aggregate_errors_name_what_is_missing(known: dict[str, Any]) -> None:
    with pytest.raises(PlayerNotFoundError):
        _aggregate(pid="unknown01")
    with pytest.raises(PlayerSeasonNotFoundError):
        _aggregate(year=1999)
    with pytest.raises(StatisticsNotFoundError):
        _aggregate()


@pytest.mark.unit
def test_stints_paginate_and_map_each_row(known: dict[str, Any]) -> None:
    known["stints"] = [
        _stat_row(PlayerTeamSeasonPbp, basketball_reference_team_id="CLE", pct_pg=Decimal("0.1")),
        _stat_row(PlayerTeamSeasonPbp, basketball_reference_team_id="MIA"),
    ]

    body = stat_service.list_stint_stats(
        SESSION,
        basketball_reference_player_id="jamesle01",
        season_year=2004,
        season_type=SeasonType.REGULAR,
        family=StatFamily.PBP,
        page=3,
        page_size=2,
    )

    assert isinstance(body, PbpStintListResponse)
    assert known["stint_table"] is PlayerTeamSeasonPbp
    assert (known["offset"], known["limit"]) == (4, 2)
    assert (body.page, body.page_size, body.total) == (3, 2, 9)
    assert [item.basketball_reference_team_id for item in body.items] == ["CLE", "MIA"]
    assert all(item.season_year == 2004 for item in body.items)
    assert body.model_dump(mode="json")["items"][0]["pct_pg"] == 0.1


@pytest.mark.unit
def test_stints_of_an_unknown_player_or_season_raise(known: dict[str, Any]) -> None:
    for pid, year, error in (
        ("unknown01", 2004, PlayerNotFoundError),
        ("jamesle01", 1999, PlayerSeasonNotFoundError),
    ):
        with pytest.raises(error):
            stat_service.list_stint_stats(
                SESSION,
                basketball_reference_player_id=pid,
                season_year=year,
                season_type=SeasonType.REGULAR,
                family=StatFamily.TOTALS,
                page=1,
                page_size=50,
            )


@pytest.mark.unit
def test_only_the_regular_season_is_served_and_its_tables_are_named() -> None:
    assert stat_service.SERVED_SEASON_TYPES == (SeasonType.REGULAR,)
    assert stat_service.served_stat_tables() == tuple(
        f"stats.{grain}_{family.value}"
        for grain in ("player_season", "player_team_season")
        for family in StatFamily
    )
