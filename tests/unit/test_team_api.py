from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.teams import TeamListResponse, TeamResponse
from nba_data.api.services import teams as team_service
from nba_data.db.models.core import Team


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
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


@contextmanager
def offline_core_session(*, create_teams_table: bool = True) -> Iterator[Session]:
    """An offline `core` schema; omit the table to make the real query fail for real."""
    # Sync routes run in the threadpool, so the SQLite connection must cross threads.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
            if create_teams_table:
                Team.__table__.create(connection)
            with Session(bind=connection) as session:
                yield session
    finally:
        engine.dispose()


@contextmanager
def app_reading_from(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    *,
    raise_server_exceptions: bool = True,
) -> Iterator[TestClient]:
    """A real app whose only substitution is the request session."""
    monkeypatch.setattr("nba_data.api.app.create_db_engine", FakeEngine)
    monkeypatch.setattr("nba_data.api.app.create_session_factory", lambda received: object())

    app = create_app()
    app.dependency_overrides[get_request_session] = lambda: session
    try:
        with TestClient(app, raise_server_exceptions=raise_server_exceptions) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def vertical_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Serve requests through the real router, service, and query repository."""
    with offline_core_session() as session:
        session.add_all(
            [
                Team(
                    id=3,
                    basketball_reference_team_id="AAA",
                    current_abbreviation="AAA",
                    current_name="Bulls",
                ),
                Team(
                    id=1,
                    basketball_reference_team_id="BBB",
                    current_abbreviation="BBB",
                    current_name="Bulls",
                ),
                Team(
                    id=2,
                    basketball_reference_team_id="CCC",
                    current_abbreviation=None,
                    current_name="Celtics",
                ),
                Team(
                    id=4,
                    basketball_reference_team_id="SEA",
                    current_abbreviation="SEA",
                    current_name="Seattle SuperSonics",
                ),
                Team(
                    id=5,
                    basketball_reference_team_id="OKC",
                    current_abbreviation="OKC",
                    current_name="Oklahoma City Thunder",
                ),
            ]
        )
        session.commit()

        with app_reading_from(monkeypatch, session) as test_client:
            yield test_client


@pytest.mark.unit
def test_list_teams_returns_the_approved_collection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        team_service,
        "list_teams",
        lambda session, *, page, page_size: TeamListResponse(
            items=[
                TeamResponse(
                    basketball_reference_team_id="ATL",
                    current_abbreviation="ATL",
                    current_name="Atlanta Hawks",
                )
            ],
            page=page,
            page_size=page_size,
            total=1,
        ),
    )

    response = client.get("/api/v1/teams", params={"page": 2, "page_size": 1})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "basketball_reference_team_id": "ATL",
                "current_abbreviation": "ATL",
                "current_name": "Atlanta Hawks",
            }
        ],
        "page": 2,
        "page_size": 1,
        "total": 1,
    }


@pytest.mark.unit
def test_empty_team_page_returns_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        team_service,
        "list_teams",
        lambda session, *, page, page_size: TeamListResponse(
            items=[], page=page, page_size=page_size, total=1
        ),
    )

    response = client.get("/api/v1/teams?page=999")

    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 999, "page_size": 50, "total": 1}


@pytest.mark.unit
def test_get_team_returns_existing_team_and_404_for_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = TeamResponse(
        basketball_reference_team_id="ATL",
        current_abbreviation=None,
        current_name="Atlanta Hawks",
    )
    monkeypatch.setattr(
        team_service,
        "get_team",
        lambda session, *, basketball_reference_team_id: (
            team if basketball_reference_team_id == "ATL" else None
        ),
    )

    existing = client.get("/api/v1/teams/ATL")
    missing = client.get("/api/v1/teams/UNKNOWN")

    assert existing.status_code == 200
    assert existing.json() == team.model_dump()
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Team not found"}


@pytest.mark.unit
def test_team_routes_validate_inputs_and_expose_only_get(client: TestClient) -> None:
    assert client.get("/api/v1/teams?page=0").status_code == 422
    assert client.get("/api/v1/teams?page_size=101").status_code == 422
    assert client.get("/api/v1/teams/ABCDEFGHIJK").status_code == 422
    empty_code = client.get("/api/v1/teams/")
    assert empty_code.status_code == 404
    assert empty_code.json() == {"detail": "Team not found"}
    assert client.get("/api/v1/teams/ATL/extra").status_code == 404
    assert client.post("/api/v1/teams").status_code == 405
    assert client.delete("/api/v1/teams/ATL").status_code == 405


@pytest.mark.unit
def test_team_routes_serve_real_rows_through_the_whole_stack(
    vertical_client: TestClient,
) -> None:
    listed = vertical_client.get("/api/v1/teams", params={"page_size": 2})

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [
            {
                "basketball_reference_team_id": "AAA",
                "current_abbreviation": "AAA",
                "current_name": "Bulls",
            },
            {
                "basketball_reference_team_id": "BBB",
                "current_abbreviation": "BBB",
                "current_name": "Bulls",
            },
        ],
        "page": 1,
        "page_size": 2,
        "total": 5,
    }

    detail = vertical_client.get("/api/v1/teams/CCC")

    assert detail.status_code == 200
    assert detail.json() == {
        "basketball_reference_team_id": "CCC",
        "current_abbreviation": None,
        "current_name": "Celtics",
    }
    assert vertical_client.get("/api/v1/teams/UNKNOWN").status_code == 404


@pytest.mark.unit
def test_team_codes_are_exact_and_synthetic_codes_are_not_resolvable(
    vertical_client: TestClient,
) -> None:
    assert vertical_client.get("/api/v1/teams/AAA").status_code == 200
    assert vertical_client.get("/api/v1/teams/aaa").status_code == 404
    assert vertical_client.get("/api/v1/teams/TOT").status_code == 404


@pytest.mark.unit
def test_relocated_teams_are_independently_reachable_without_lineage(
    vertical_client: TestClient,
) -> None:
    sea = vertical_client.get("/api/v1/teams/SEA")
    okc = vertical_client.get("/api/v1/teams/OKC")

    assert sea.status_code == 200
    assert sea.json() == {
        "basketball_reference_team_id": "SEA",
        "current_abbreviation": "SEA",
        "current_name": "Seattle SuperSonics",
    }
    assert okc.status_code == 200
    assert okc.json() == {
        "basketball_reference_team_id": "OKC",
        "current_abbreviation": "OKC",
        "current_name": "Oklahoma City Thunder",
    }


@pytest.mark.unit
def test_a_failing_database_returns_the_documented_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 500 contract through the real query path, not a stub route bolted onto the app."""
    with (
        offline_core_session(create_teams_table=False) as session,
        app_reading_from(monkeypatch, session, raise_server_exceptions=False) as test_client,
    ):
        response = test_client.get("/api/v1/teams")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal Server Error"}
    # The driver names the missing table and echoes the statement; neither may reach a client.
    assert "teams" not in response.text
    assert "SELECT" not in response.text.upper()


@pytest.mark.unit
def test_team_routes_are_registered_with_approved_openapi_fields(client: TestClient) -> None:
    openapi = client.app.openapi()

    detail_path = "/api/v1/teams/{basketball_reference_team_id}"
    assert set(openapi["paths"]) >= {"/api/v1/teams", detail_path}
    assert set(openapi["paths"]["/api/v1/teams"]) == {"get"}
    assert set(openapi["paths"][detail_path]) == {"get"}
    path_parameter = openapi["paths"][detail_path]["get"]["parameters"][0]
    assert path_parameter["name"] == "basketball_reference_team_id"
    assert path_parameter["schema"]["type"] == "string"
    assert path_parameter["schema"]["minLength"] == 1
    assert path_parameter["schema"]["maxLength"] == 10
    assert set(openapi["components"]["schemas"]["TeamResponse"]["properties"]) == {
        "basketball_reference_team_id",
        "current_abbreviation",
        "current_name",
    }
