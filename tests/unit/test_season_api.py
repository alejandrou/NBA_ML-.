from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.seasons import SeasonListResponse, SeasonResponse
from nba_data.api.services import seasons as season_service
from nba_data.db.models.core import Season


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


@pytest.fixture
def vertical_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Serve requests through the real router, service, and query repository."""
    # Sync routes run in the threadpool, so the SQLite connection must cross threads.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        Season.__table__.create(connection)
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Season(id=1, season_year=2023, league="NBA", label="2023"),
                    Season(id=2, season_year=2024, league="NBA", label="2024"),
                    Season(id=3, season_year=2025, league="NBA", label=None),
                    Season(id=4, season_year=1975, league="ABA", label="1975"),
                ]
            )
            session.commit()

            monkeypatch.setattr("nba_data.api.app.create_db_engine", FakeEngine)
            monkeypatch.setattr("nba_data.api.app.create_session_factory", lambda received: object())

            app = create_app()
            app.dependency_overrides[get_request_session] = lambda: session
            try:
                with TestClient(app) as test_client:
                    yield test_client
            finally:
                app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.unit
def test_list_seasons_returns_the_approved_collection(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        season_service,
        "list_seasons",
        lambda session, *, page, page_size: SeasonListResponse(
            items=[SeasonResponse(season_year=2024, league="NBA", label="2024")],
            page=page,
            page_size=page_size,
            total=1,
        ),
    )

    response = client.get("/api/v1/seasons", params={"page": 2, "page_size": 1})

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"season_year": 2024, "league": "NBA", "label": "2024"}],
        "page": 2,
        "page_size": 1,
        "total": 1,
    }


@pytest.mark.unit
def test_empty_season_page_returns_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        season_service,
        "list_seasons",
        lambda session, *, page, page_size: SeasonListResponse(
            items=[], page=page, page_size=page_size, total=1
        ),
    )

    response = client.get("/api/v1/seasons?page=999")

    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 999, "page_size": 50, "total": 1}


@pytest.mark.unit
def test_get_season_returns_existing_season_and_404_for_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    season = SeasonResponse(season_year=2024, league="NBA", label=None)
    monkeypatch.setattr(
        season_service,
        "get_season",
        lambda session, *, season_year: season if season_year == 2024 else None,
    )

    existing = client.get("/api/v1/seasons/2024")
    missing = client.get("/api/v1/seasons/1800")

    assert existing.status_code == 200
    assert existing.json() == season.model_dump()
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Season not found"}


@pytest.mark.unit
def test_season_routes_validate_inputs_and_expose_only_get(client: TestClient) -> None:
    assert client.get("/api/v1/seasons?page=0").status_code == 422
    assert client.get("/api/v1/seasons?page_size=101").status_code == 422
    assert client.get("/api/v1/seasons/not-an-integer").status_code == 422
    assert client.get("/api/v1/seasons/0").status_code == 422
    assert client.post("/api/v1/seasons").status_code == 405
    assert client.delete("/api/v1/seasons/2024").status_code == 405


@pytest.mark.unit
def test_season_routes_serve_real_rows_through_the_whole_stack(
    vertical_client: TestClient,
) -> None:
    listed = vertical_client.get("/api/v1/seasons", params={"page_size": 2})

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [
            {"season_year": 2025, "league": "NBA", "label": None},
            {"season_year": 2024, "league": "NBA", "label": "2024"},
        ],
        "page": 1,
        "page_size": 2,
        "total": 3,
    }

    detail = vertical_client.get("/api/v1/seasons/2024")

    assert detail.status_code == 200
    assert detail.json() == {"season_year": 2024, "league": "NBA", "label": "2024"}
    assert vertical_client.get("/api/v1/seasons/1975").status_code == 404


@pytest.mark.unit
def test_season_routes_are_registered_with_approved_openapi_fields(client: TestClient) -> None:
    openapi = client.app.openapi()

    assert set(openapi["paths"]) >= {"/api/v1/seasons", "/api/v1/seasons/{season_year}"}
    assert set(openapi["paths"]["/api/v1/seasons"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/seasons/{season_year}"]) == {"get"}
    assert set(openapi["components"]["schemas"]["SeasonResponse"]["properties"]) == {
        "season_year",
        "league",
        "label",
    }
