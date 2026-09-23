from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.db.models.core import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamSeason,
)

CORE_TABLES = (Season, Team, Player, TeamSeason, PlayerSeason, PlayerTeamSeason)
PLAYER_NOT_FOUND = {"detail": "Player not found"}
PLAYER_SEASON_NOT_FOUND = {"detail": "Player season not found"}


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """An app with no usable session: only requests rejected before any read may succeed."""
    engine = FakeEngine()
    monkeypatch.setattr("nba_data.api.app.create_db_engine", lambda: engine)
    monkeypatch.setattr("nba_data.api.app.create_session_factory", lambda received: object())

    app = create_app()
    app.dependency_overrides[get_request_session] = lambda: object()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()

    assert engine.disposed


@pytest.fixture
def vertical_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Serve requests through the real router, service, and query repository.

    `smithjo01` is stored at id 3 and `smithjo02` at id 2, so surrogate ordering
    would swap them; `jamesle01` is stored at id 1, so `/players/1` finding it
    would mean a surrogate-id route crept in.
    """
    # Sync routes run in the threadpool, so the SQLite connection must cross threads.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        for model in CORE_TABLES:
            model.__table__.create(connection)  # type: ignore[attr-defined]
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Season(id=1, season_year=2003, league="NBA", label="2003"),
                    Season(id=2, season_year=2004, league="NBA", label="2004"),
                    Season(id=3, season_year=2005, league="NBA", label="2005"),
                    Season(id=4, season_year=2004, league="ABA", label="2004"),
                    Team(id=1, basketball_reference_team_id="CLE", current_name="Cavaliers"),
                    Team(id=2, basketball_reference_team_id="MIA", current_name="Heat"),
                    Team(id=3, basketball_reference_team_id="ATL", current_name="Hawks"),
                    TeamSeason(id=1, team_id=1, season_id=1, team_abbreviation="CLE"),
                    TeamSeason(id=2, team_id=1, season_id=2, team_abbreviation="CLE"),
                    TeamSeason(id=3, team_id=2, season_id=2, team_abbreviation="MIA"),
                    TeamSeason(id=4, team_id=3, season_id=4, team_abbreviation="ATL"),
                    Player(
                        id=1,
                        basketball_reference_player_id="jamesle01",
                        full_name="LeBron James",
                        slug="lebron-james",
                    ),
                    Player(
                        id=3, basketball_reference_player_id="smithjo01", full_name="John Smith"
                    ),
                    Player(
                        id=2, basketball_reference_player_id="smithjo02", full_name="John Smith"
                    ),
                    Player(
                        id=6, basketball_reference_player_id="rookiaa01", full_name="Aaron Rookie"
                    ),
                    Player(id=7, basketball_reference_player_id=None, full_name="Aaron Aardvark"),
                    PlayerSeason(id=10, player_id=1, season_id=1),
                    PlayerSeason(id=11, player_id=1, season_id=2),
                    PlayerSeason(id=12, player_id=1, season_id=3),
                    PlayerSeason(id=13, player_id=1, season_id=4),
                    PlayerTeamSeason(id=1, player_season_id=10, team_season_id=1),
                    PlayerTeamSeason(id=2, player_season_id=11, team_season_id=3),
                    PlayerTeamSeason(id=3, player_season_id=11, team_season_id=2),
                    PlayerTeamSeason(id=4, player_season_id=13, team_season_id=4),
                ]
            )
            session.commit()

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


@pytest.mark.unit
def test_player_routes_validate_inputs_and_expose_only_get(client: TestClient) -> None:
    for query in ("page=0", "page_size=0", "page_size=101", "page=abc"):
        assert client.get(f"/api/v1/players?{query}").status_code == 422, query
        assert client.get(f"/api/v1/players/jamesle01/seasons?{query}").status_code == 422, query
    assert client.get(f"/api/v1/players/{'a' * 33}").status_code == 422
    assert client.get(f"/api/v1/players/{'a' * 33}/seasons").status_code == 422
    assert client.get("/api/v1/players/jamesle01/seasons/2004.5").status_code == 422
    assert client.get("/api/v1/players/jamesle01/seasons/twenty").status_code == 422
    for path in ("/api/v1/players", "/api/v1/players/jamesle01"):
        assert client.post(path).status_code == 405, path
    for path in ("/api/v1/players/jamesle01", "/api/v1/players/jamesle01/seasons/2004"):
        assert client.put(path).status_code == 405, path
        assert client.patch(path).status_code == 405, path
        assert client.delete(path).status_code == 405, path


@pytest.mark.unit
def test_an_empty_player_id_is_not_found_rather_than_the_collection(client: TestClient) -> None:
    response = client.get("/api/v1/players/")

    assert response.status_code == 404
    assert response.json() == PLAYER_NOT_FOUND


@pytest.mark.unit
def test_player_collection_excludes_unkeyed_rows_and_orders_by_name_then_id(
    vertical_client: TestClient,
) -> None:
    listed = vertical_client.get("/api/v1/players")

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [
            {"basketball_reference_player_id": "rookiaa01", "full_name": "Aaron Rookie"},
            {"basketball_reference_player_id": "smithjo01", "full_name": "John Smith"},
            {"basketball_reference_player_id": "smithjo02", "full_name": "John Smith"},
            {"basketball_reference_player_id": "jamesle01", "full_name": "LeBron James"},
        ],
        "page": 1,
        "page_size": 50,
        "total": 4,
    }


@pytest.mark.unit
def test_player_pages_partition_the_collection_and_past_the_end_is_empty(
    vertical_client: TestClient,
) -> None:
    pages = [
        vertical_client.get("/api/v1/players", params={"page": page, "page_size": 3}).json()
        for page in (1, 2, 3)
    ]

    assert [
        [item["basketball_reference_player_id"] for item in page["items"]] for page in pages
    ] == [["rookiaa01", "smithjo01", "smithjo02"], ["jamesle01"], []]
    assert {page["total"] for page in pages} == {4}
    assert pages[2] == {"items": [], "page": 3, "page_size": 3, "total": 4}
    assert vertical_client.get("/api/v1/players", params={"page_size": 100}).status_code == 200


@pytest.mark.unit
def test_player_detail_is_served_by_exact_id(vertical_client: TestClient) -> None:
    detail = vertical_client.get("/api/v1/players/jamesle01")

    assert detail.status_code == 200
    assert detail.json() == {
        "basketball_reference_player_id": "jamesle01",
        "full_name": "LeBron James",
    }
    assert vertical_client.get("/api/v1/players/rookiaa01").status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize("pid", ["JAMESLE01", "Jamesle01", "unknown01", "1", "lebron-james"])
def test_unknown_player_ids_are_404_on_every_player_route(
    vertical_client: TestClient, pid: str
) -> None:
    """Exact case, no surrogate id (`jamesle01` is id 1), and no slug lookup."""
    for path in (
        f"/api/v1/players/{pid}",
        f"/api/v1/players/{pid}/seasons",
        f"/api/v1/players/{pid}/seasons/2004",
    ):
        response = vertical_client.get(path)

        assert response.status_code == 404, path
        assert response.json() == PLAYER_NOT_FOUND, path


@pytest.mark.unit
def test_player_seasons_are_nba_only_newest_first_with_team_codes(
    vertical_client: TestClient,
) -> None:
    listed = vertical_client.get("/api/v1/players/jamesle01/seasons")

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [
            {"season_year": 2005, "league": "NBA", "teams": []},
            {"season_year": 2004, "league": "NBA", "teams": ["CLE", "MIA"]},
            {"season_year": 2003, "league": "NBA", "teams": ["CLE"]},
        ],
        "page": 1,
        "page_size": 50,
        "total": 3,
    }


@pytest.mark.unit
def test_player_seasons_paginate(vertical_client: TestClient) -> None:
    second = vertical_client.get(
        "/api/v1/players/jamesle01/seasons", params={"page": 2, "page_size": 2}
    )
    past_end = vertical_client.get(
        "/api/v1/players/jamesle01/seasons", params={"page": 9, "page_size": 2}
    )

    assert second.json() == {
        "items": [{"season_year": 2003, "league": "NBA", "teams": ["CLE"]}],
        "page": 2,
        "page_size": 2,
        "total": 3,
    }
    assert past_end.status_code == 200
    assert past_end.json() == {"items": [], "page": 9, "page_size": 2, "total": 3}


@pytest.mark.unit
def test_a_known_player_without_seasons_gets_an_empty_page(vertical_client: TestClient) -> None:
    response = vertical_client.get("/api/v1/players/rookiaa01/seasons")

    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "page_size": 50, "total": 0}


@pytest.mark.unit
def test_player_season_detail_serves_one_item(vertical_client: TestClient) -> None:
    response = vertical_client.get("/api/v1/players/jamesle01/seasons/2004")

    assert response.status_code == 200
    assert response.json() == {"season_year": 2004, "league": "NBA", "teams": ["CLE", "MIA"]}


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/players/jamesle01/seasons/1999",
        "/api/v1/players/rookiaa01/seasons/2004",
    ],
)
def test_a_known_player_without_that_season_is_player_season_not_found(
    vertical_client: TestClient, path: str
) -> None:
    response = vertical_client.get(path)

    assert response.status_code == 404
    assert response.json() == PLAYER_SEASON_NOT_FOUND


@pytest.mark.unit
def test_detail_strings_never_echo_the_request(vertical_client: TestClient) -> None:
    for path in (
        "/api/v1/players/zzzzzz99",
        "/api/v1/players/zzzzzz99/seasons",
        "/api/v1/players/jamesle01/seasons/1987",
    ):
        response = vertical_client.get(path)

        assert response.status_code == 404, path
        assert "zzzzzz99" not in response.text, path
        assert "1987" not in response.text, path


@pytest.mark.unit
def test_no_private_column_reaches_any_player_body(vertical_client: TestClient) -> None:
    """Surrogate ids, the slug, and the stint roster fields stay private."""
    player_keys = {"basketball_reference_player_id", "full_name"}
    season_keys = {"season_year", "league", "teams"}

    for item in vertical_client.get("/api/v1/players").json()["items"]:
        assert set(item) == player_keys, item
    assert set(vertical_client.get("/api/v1/players/jamesle01").json()) == player_keys
    for item in vertical_client.get("/api/v1/players/jamesle01/seasons").json()["items"]:
        assert set(item) == season_keys, item
    assert set(vertical_client.get("/api/v1/players/jamesle01/seasons/2004").json()) == season_keys
    assert "lebron-james" not in vertical_client.get("/api/v1/players/jamesle01").text


@pytest.mark.unit
def test_player_routes_are_registered_with_approved_openapi_fields(client: TestClient) -> None:
    openapi = client.app.openapi()
    paths = openapi["paths"]
    detail = "/api/v1/players/{basketball_reference_player_id}"
    seasons = f"{detail}/seasons"
    season = f"{seasons}/{{season_year}}"

    assert {"/api/v1/players", detail, seasons, season} <= set(paths)
    assert "/api/v1/players/" not in paths
    for path in ("/api/v1/players", detail, seasons, season):
        assert set(paths[path]) == {"get"}, path

    pid = paths[detail]["get"]["parameters"][0]
    assert pid["name"] == "basketball_reference_player_id"
    assert pid["schema"]["type"] == "string"
    assert pid["schema"]["minLength"] == 1
    assert pid["schema"]["maxLength"] == 32

    schemas = openapi["components"]["schemas"]
    assert set(schemas["PlayerResponse"]["properties"]) == {
        "basketball_reference_player_id",
        "full_name",
    }
    assert set(schemas["PlayerSeasonResponse"]["properties"]) == {"season_year", "league", "teams"}
