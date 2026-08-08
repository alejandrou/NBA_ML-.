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
        # These rows mirror production, so franchise_id is null: no loader writes it.
        session.add_all(
            [
                Team(
                    id=3,
                    basketball_reference_team_id="BBB",
                    current_abbreviation="BBB",
                    current_name="Bulls",
                    franchise_id=None,
                ),
                Team(
                    id=1,
                    basketball_reference_team_id="AAA",
                    current_abbreviation="AAA",
                    current_name="Bulls",
                    franchise_id=None,
                ),
                Team(
                    id=2,
                    basketball_reference_team_id="CCC",
                    current_abbreviation=None,
                    current_name="Celtics",
                    franchise_id=None,
                ),
            ]
        )
        session.commit()

        with app_reading_from(monkeypatch, session) as test_client:
            yield test_client


@pytest.mark.unit
def test_list_teams_returns_the_approved_collection(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # A populated franchise_id here tests serialization of a nullable field, not real data:
    # the column is null on every production row. Tests that seed the database use null.
    monkeypatch.setattr(
        team_service,
        "list_teams",
        lambda session, *, page, page_size: TeamListResponse(
            items=[
                TeamResponse(
                    team_id=7,
                    basketball_reference_team_id="ATL",
                    current_abbreviation="ATL",
                    current_name="Atlanta Hawks",
                    franchise_id="hawks",
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
                "team_id": 7,
                "basketball_reference_team_id": "ATL",
                "current_abbreviation": "ATL",
                "current_name": "Atlanta Hawks",
                "franchise_id": "hawks",
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
        team_id=7,
        basketball_reference_team_id=None,
        current_abbreviation=None,
        current_name="Atlanta Hawks",
        franchise_id=None,
    )
    monkeypatch.setattr(
        team_service,
        "get_team",
        lambda session, *, team_id: team if team_id == 7 else None,
    )

    existing = client.get("/api/v1/teams/7")
    missing = client.get("/api/v1/teams/8")

    assert existing.status_code == 200
    assert existing.json() == team.model_dump()
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Team not found"}


@pytest.mark.unit
def test_team_routes_validate_inputs_and_expose_only_get(client: TestClient) -> None:
    assert client.get("/api/v1/teams?page=0").status_code == 422
    assert client.get("/api/v1/teams?page_size=101").status_code == 422
    assert client.get("/api/v1/teams/not-an-integer").status_code == 422
    assert client.get("/api/v1/teams/0").status_code == 422
    assert client.post("/api/v1/teams").status_code == 405
    assert client.delete("/api/v1/teams/7").status_code == 405


@pytest.mark.unit
def test_team_routes_serve_real_rows_through_the_whole_stack(
    vertical_client: TestClient,
) -> None:
    listed = vertical_client.get("/api/v1/teams", params={"page_size": 2})

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [
            {
                "team_id": 1,
                "basketball_reference_team_id": "AAA",
                "current_abbreviation": "AAA",
                "current_name": "Bulls",
                "franchise_id": None,
            },
            {
                "team_id": 3,
                "basketball_reference_team_id": "BBB",
                "current_abbreviation": "BBB",
                "current_name": "Bulls",
                "franchise_id": None,
            },
        ],
        "page": 1,
        "page_size": 2,
        "total": 3,
    }

    detail = vertical_client.get("/api/v1/teams/2")

    assert detail.status_code == 200
    assert detail.json() == {
        "team_id": 2,
        "basketball_reference_team_id": "CCC",
        "current_abbreviation": None,
        "current_name": "Celtics",
        "franchise_id": None,
    }
    assert vertical_client.get("/api/v1/teams/999").status_code == 404


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

    assert set(openapi["paths"]) >= {"/api/v1/teams", "/api/v1/teams/{team_id}"}
    assert set(openapi["paths"]["/api/v1/teams"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/teams/{team_id}"]) == {"get"}
    assert set(openapi["components"]["schemas"]["TeamResponse"]["properties"]) == {
        "team_id",
        "basketball_reference_team_id",
        "current_abbreviation",
        "current_name",
        "franchise_id",
    }
