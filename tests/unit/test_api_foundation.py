import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nba_data.api import create_app


@pytest.mark.unit
def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()

    assert isinstance(app, FastAPI)


@pytest.mark.unit
def test_health_returns_approved_schema() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_health_route_is_get_only_and_versioned() -> None:
    app = create_app()

    with TestClient(app) as client:
        assert client.get("/health").status_code == 404
        assert client.post("/api/v1/health").status_code == 405
        assert client.put("/api/v1/health").status_code == 405
        assert client.patch("/api/v1/health").status_code == 405
        assert client.delete("/api/v1/health").status_code == 405


@pytest.mark.unit
def test_health_is_registered_in_openapi_without_unapproved_routes() -> None:
    app = create_app()

    openapi = app.openapi()

    assert set(openapi["paths"]) == {
        "/api/v1/health",
        "/api/v1/teams",
        "/api/v1/teams/{team_id}",
    }
    health_operation = openapi["paths"]["/api/v1/health"]["get"]
    assert health_operation["tags"] == ["health"]
    assert health_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }
    assert "post" not in openapi["paths"]["/api/v1/health"]
    assert "put" not in openapi["paths"]["/api/v1/health"]
    assert "patch" not in openapi["paths"]["/api/v1/health"]
    assert "delete" not in openapi["paths"]["/api/v1/health"]
    assert set(openapi["paths"]["/api/v1/teams"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/teams/{team_id}"]) == {"get"}


@pytest.mark.unit
def test_app_instances_have_isolated_dependency_overrides() -> None:
    first_app = create_app()
    second_app = create_app()

    marker = object()
    first_app.dependency_overrides[marker] = lambda: marker

    try:
        assert first_app.dependency_overrides != second_app.dependency_overrides
        assert second_app.dependency_overrides == {}
    finally:
        first_app.dependency_overrides.clear()
