from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.teams import TeamListResponse, TeamResponse
from nba_data.api.services import teams as team_service


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


@pytest.mark.unit
def test_list_teams_returns_the_approved_collection(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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
