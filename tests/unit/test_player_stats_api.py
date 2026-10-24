from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.player_stats import (
    STAT_BODIES,
    AggregateStatIdentity,
    StintStatIdentity,
)
from nba_data.db.models.core import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamSeason,
)
from nba_data.db.repositories.queries.player_stats import AGGREGATE_TABLES, STINT_TABLES
from nba_data.domain.stat_dimensions import SeasonType, StatFamily

CORE_TABLES = (Season, Team, Player, TeamSeason, PlayerSeason, PlayerTeamSeason)
REGULAR_AGGREGATES = AGGREGATE_TABLES[SeasonType.REGULAR]
REGULAR_STINTS = STINT_TABLES[SeasonType.REGULAR]
BASE = "/api/v1/players/jamesle01/seasons"
FAMILIES = [family.value for family in StatFamily]

# Written out rather than imported: the contract names these, and a test that
# read them from the code under test would agree with any change to it.
LINEAGE_COLUMNS = {"source_url", "cache_path", "parser_version", "created_at", "updated_at"}
EXCLUDED_COLUMNS = {
    "id",
    "player_season_id",
    "player_team_season_id",
    "source_team_code",
    "player_name_display",
    *LINEAGE_COLUMNS,
}
AGGREGATE_IDENTITY = ["season_year", "season_type", "source_team_code", "is_multi_team"]
STINT_IDENTITY = ["season_year", "season_type", "basketball_reference_team_id"]
LINEAGE: dict[str, Any] = {
    "source_url": "https://www.basketball-reference.com/players/j/jamesle01.html",
    "cache_path": "data/raw/players/j/jamesle01.html",
    "parser_version": "player-page-v4",
}


class FakeEngine:
    def dispose(self) -> None:
        pass


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Serve requests through the real router, service, and query repository.

    `jamesle01` played 2004 for `MIA` then `CLE` (a `2TM` season), with a row in
    every regular family; the `MIA` stint rows are inserted first, so row ids
    would order them wrongly. 2003 holds a `CLE` totals row only, with the
    columns an older page lacks left `NULL`, and no stint stat rows at all.
    `rookiaa01` has a season and nothing else.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for model in (*CORE_TABLES, *REGULAR_AGGREGATES.values(), *REGULAR_STINTS.values()):
            model.__table__.create(connection)  # type: ignore[attr-defined]
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Season(id=1, season_year=2003, league="NBA", label="2003"),
                    Season(id=2, season_year=2004, league="NBA", label="2004"),
                    Season(id=3, season_year=1975, league="ABA", label="1975"),
                    Team(id=1, basketball_reference_team_id="CLE", current_name="Cavaliers"),
                    Team(id=2, basketball_reference_team_id="MIA", current_name="Heat"),
                    TeamSeason(id=1, team_id=1, season_id=1, team_abbreviation="CLE"),
                    TeamSeason(id=2, team_id=1, season_id=2, team_abbreviation="CLE"),
                    TeamSeason(id=3, team_id=2, season_id=2, team_abbreviation="MIA"),
                    Player(
                        id=5, basketball_reference_player_id="jamesle01", full_name="LeBron James"
                    ),
                    Player(
                        id=6, basketball_reference_player_id="rookiaa01", full_name="Aaron Rookie"
                    ),
                    PlayerSeason(id=10, player_id=5, season_id=1),
                    PlayerSeason(id=11, player_id=5, season_id=2),
                    PlayerSeason(id=12, player_id=5, season_id=3),
                    PlayerSeason(id=13, player_id=6, season_id=2),
                    PlayerTeamSeason(id=1, player_season_id=10, team_season_id=1),
                    PlayerTeamSeason(id=2, player_season_id=11, team_season_id=3),
                    PlayerTeamSeason(id=3, player_season_id=11, team_season_id=2),
                ]
            )
            for family in StatFamily:
                session.add_all(
                    [
                        REGULAR_AGGREGATES[family](
                            id=1,
                            player_season_id=11,
                            source_team_code="2TM",
                            player_name_display="LeBron James",
                            g=80,
                            **LINEAGE,
                        ),
                        REGULAR_STINTS[family](
                            id=1, player_team_season_id=2, g=30, rk=7, **LINEAGE
                        ),
                        REGULAR_STINTS[family](
                            id=2, player_team_season_id=3, g=50, rk=3, **LINEAGE
                        ),
                    ]
                )
            totals_2004 = session.get(REGULAR_AGGREGATES[StatFamily.TOTALS], 1)
            assert totals_2004 is not None
            totals_2004.fg_pct = Decimal("0.4660")  # type: ignore[attr-defined]
            totals_2004.pts = 2175  # type: ignore[attr-defined]
            session.add(
                REGULAR_AGGREGATES[StatFamily.TOTALS](
                    id=2,
                    player_season_id=10,
                    source_team_code="CLE",
                    g=79,
                    pts=1654,
                    fg_pct=Decimal("0.4170"),
                    **LINEAGE,
                )
            )
            session.commit()
            session.expunge_all()

            monkeypatch.setattr("nba_data.api.app.create_db_engine", FakeEngine)
            monkeypatch.setattr(
                "nba_data.api.app.create_session_factory", lambda received: object()
            )
            app = create_app()
            app.dependency_overrides[get_request_session] = lambda: session
            try:
                with TestClient(app) as test_client:
                    yield test_client
            finally:
                app.dependency_overrides.clear()
    engine.dispose()


def _stat_fields(body: type[Any], identity: type[Any]) -> set[str]:
    return set(body.model_fields) - set(identity.model_fields)


@pytest.mark.unit
@pytest.mark.parametrize("family", list(StatFamily))
def test_each_body_publishes_exactly_its_tables_stored_columns(family: StatFamily) -> None:
    """A column added to a stat table fails here until it is published or excluded."""
    aggregate_body, stint_list_body = STAT_BODIES[family]
    stint_body = stint_list_body.model_fields["items"].annotation.__args__[0]  # type: ignore[union-attr]

    for season_type in SeasonType:
        aggregate_columns = {
            column.name for column in AGGREGATE_TABLES[season_type][family].__table__.columns
        }
        stint_columns = {
            column.name for column in STINT_TABLES[season_type][family].__table__.columns
        }
        assert _stat_fields(aggregate_body, AggregateStatIdentity) == (
            aggregate_columns - EXCLUDED_COLUMNS
        )
        assert _stat_fields(stint_body, StintStatIdentity) == stint_columns - EXCLUDED_COLUMNS


@pytest.mark.unit
@pytest.mark.parametrize("family", FAMILIES)
def test_every_family_serves_its_aggregate(client: TestClient, family: str) -> None:
    response = client.get(f"{BASE}/2004/regular/aggregate/{family}")

    assert response.status_code == 200
    body = response.json()
    expected_stats = {
        column.name for column in REGULAR_AGGREGATES[StatFamily(family)].__table__.columns
    } - EXCLUDED_COLUMNS
    assert list(body)[:4] == AGGREGATE_IDENTITY
    assert set(body) == set(AGGREGATE_IDENTITY) | expected_stats
    assert body["season_year"] == 2004
    assert body["season_type"] == "regular"
    assert body["source_team_code"] == "2TM"
    assert body["is_multi_team"] is True
    assert body["g"] == 80


@pytest.mark.unit
@pytest.mark.parametrize("family", FAMILIES)
def test_every_family_serves_its_stints_ordered_by_team_code(
    client: TestClient, family: str
) -> None:
    response = client.get(f"{BASE}/2004/regular/stints/{family}")

    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["page_size"], body["total"]) == (1, 50, 2)
    assert [(item["basketball_reference_team_id"], item["g"]) for item in body["items"]] == [
        ("CLE", 50),
        ("MIA", 30),
    ]
    expected_stats = {
        column.name for column in REGULAR_STINTS[StatFamily(family)].__table__.columns
    } - EXCLUDED_COLUMNS
    for item in body["items"]:
        assert list(item)[:3] == STINT_IDENTITY
        assert set(item) == set(STINT_IDENTITY) | expected_stats
        assert item["season_type"] == "regular"
        assert item["rk"] in (3, 7)


@pytest.mark.unit
def test_no_body_carries_lineage_or_the_display_name(client: TestClient) -> None:
    for family in FAMILIES:
        aggregate = client.get(f"{BASE}/2004/regular/aggregate/{family}").json()
        stints = client.get(f"{BASE}/2004/regular/stints/{family}").json()["items"]
        for body in (aggregate, *stints):
            assert not LINEAGE_COLUMNS & set(body), family
            assert "player_name_display" not in body, family
            assert not {"id", "player_season_id", "player_team_season_id"} & set(body), family


@pytest.mark.unit
def test_rates_are_json_numbers(client: TestClient) -> None:
    response = client.get(f"{BASE}/2004/regular/aggregate/totals")

    assert '"fg_pct":0.466' in response.text
    assert isinstance(response.json()["fg_pct"], float)


@pytest.mark.unit
def test_an_older_season_publishes_missing_stats_as_null(client: TestClient) -> None:
    response = client.get(f"{BASE}/2003/regular/aggregate/totals")

    assert response.status_code == 200
    body = response.json()
    assert body["pts"] == 1654
    assert body["fg_pct"] == 0.417
    assert body["source_team_code"] == "CLE"
    assert body["is_multi_team"] is False
    for missing in ("fg2", "fg2a", "fg2_pct", "tpl_dbl", "awards", "rk"):
        assert missing in body
        assert body[missing] is None


@pytest.mark.unit
def test_a_season_without_stint_stat_rows_is_an_empty_page(client: TestClient) -> None:
    """2003 has `CLE` membership, but no stint stat row: membership is not invented."""
    response = client.get(f"{BASE}/2003/regular/stints/totals")

    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "page_size": 50, "total": 0}


@pytest.mark.unit
def test_stints_paginate(client: TestClient) -> None:
    pages = [
        client.get(f"{BASE}/2004/regular/stints/advanced?page={page}&page_size=1").json()
        for page in (1, 2, 3)
    ]

    assert [[item["basketball_reference_team_id"] for item in page["items"]] for page in pages] == [
        ["CLE"],
        ["MIA"],
        [],
    ]
    assert {page["total"] for page in pages} == {2}


@pytest.mark.unit
def test_missing_resources_return_the_fixed_404_bodies(client: TestClient) -> None:
    cases = {
        "/api/v1/players/unknown01/seasons/2004/regular/aggregate/totals": "Player not found",
        "/api/v1/players/unknown01/seasons/2004/regular/stints/totals": "Player not found",
        "/api/v1/players/JAMESLE01/seasons/2004/regular/aggregate/totals": "Player not found",
        f"{BASE}/1999/regular/aggregate/totals": "Player season not found",
        f"{BASE}/1999/regular/stints/totals": "Player season not found",
        f"{BASE}/1975/regular/aggregate/totals": "Player season not found",
        f"{BASE}/2003/regular/aggregate/advanced": "Statistics not found",
        "/api/v1/players/rookiaa01/seasons/2004/regular/aggregate/pbp": "Statistics not found",
    }
    for path, detail in cases.items():
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.json() == {"detail": detail}, path


@pytest.mark.unit
def test_unrecognized_path_values_are_422(client: TestClient) -> None:
    for path in (
        f"{BASE}/2004/playoffs/aggregate/totals",
        f"{BASE}/2004/playoffs/stints/totals",
        f"{BASE}/2004/regular/aggregate/roster",
        f"{BASE}/2004/regular/stints/roster",
        f"{BASE}/2004/regular/aggregate/TOTALS",
        f"{BASE}/2004.5/regular/aggregate/totals",
        f"{BASE}/twenty/regular/stints/totals",
        f"{BASE}/2004/regular/stints/totals?page=0",
        f"{BASE}/2004/regular/stints/totals?page_size=101",
    ):
        assert client.get(path).status_code == 422, path


@pytest.mark.unit
def test_recognized_but_unserved_postseason_routes_are_404(client: TestClient) -> None:
    for grain in ("aggregate", "stints"):
        response = client.get(f"{BASE}/2004/postseason/{grain}/totals")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


@pytest.mark.unit
def test_stat_routes_expose_only_get(client: TestClient) -> None:
    for grain in ("aggregate", "stints"):
        path = f"{BASE}/2004/regular/{grain}/totals"
        assert client.post(path).status_code == 405
        assert client.put(path).status_code == 405
        assert client.patch(path).status_code == 405
        assert client.delete(path).status_code == 405


@pytest.mark.unit
def test_openapi_publishes_one_typed_body_per_family_and_grain() -> None:
    openapi = create_app().openapi()
    prefix = "/api/v1/players/{basketball_reference_player_id}/seasons/{season_year}"

    references = set()
    for grain in ("aggregate", "stints"):
        for family in FAMILIES:
            operation = openapi["paths"][f"{prefix}/regular/{grain}/{family}"]["get"]
            schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
            references.add(schema["$ref"])
    assert len(references) == 16

    assert not [path for path in openapi["paths"] if "{season_type}" in path or "{family}" in path]
    totals = openapi["components"]["schemas"]["TotalsAggregateResponse"]["properties"]
    assert totals["fg_pct"] == {"anyOf": [{"type": "number"}, {"type": "null"}], "title": "Fg Pct"}
