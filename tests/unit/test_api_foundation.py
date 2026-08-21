import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import Route
from typer.testing import CliRunner

from nba_data.api import create_app
from nba_data.cli.main import app as cli_app


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
        "/api/v1/health/ready",
        "/api/v1/teams",
        "/api/v1/teams/{basketball_reference_team_id}",
        "/api/v1/seasons",
        "/api/v1/seasons/{season_year}",
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
    assert set(openapi["paths"]["/api/v1/teams/{basketball_reference_team_id}"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/seasons"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/seasons/{season_year}"]) == {"get"}


@pytest.mark.unit
def test_only_approved_documentation_routes_exist_outside_the_versioned_api() -> None:
    """The versioned routes live behind the API router; assert what sits outside it."""
    app = create_app()

    outside_the_api_router = {
        route.path: sorted(route.methods) for route in app.routes if isinstance(route, Route)
    }

    assert outside_the_api_router == {
        "/openapi.json": ["GET", "HEAD"],
        "/docs": ["GET", "HEAD"],
        "/docs/oauth2-redirect": ["GET", "HEAD"],
        "/redoc": ["GET", "HEAD"],
    }
    assert all(path.startswith("/api/v1/") for path in app.openapi()["paths"])


@pytest.mark.unit
def test_unexpected_failures_return_the_documented_error_body() -> None:
    app = create_app()

    @app.get("/boom", include_in_schema=False)
    def boom() -> None:
        raise RuntimeError("forced failure with a /secret/path and a password")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal Server Error"}
    assert "secret" not in response.text
    assert "password" not in response.text


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


@pytest.mark.unit
def test_serve_command_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(target: str, **kwargs: object) -> None:
        captured["target"] = target
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)

    result = CliRunner().invoke(cli_app, ["serve"])

    assert result.exit_code == 0
    assert captured == {
        "target": "nba_data.api:create_app",
        "factory": True,
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
    }


@pytest.mark.unit
def test_serve_command_passes_through_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(target: str, **kwargs: object) -> None:
        captured["target"] = target
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)

    result = CliRunner().invoke(
        cli_app, ["serve", "--host", "0.0.0.0", "--port", "9001", "--reload"]
    )

    assert result.exit_code == 0
    assert captured == {
        "target": "nba_data.api:create_app",
        "factory": True,
        "host": "0.0.0.0",
        "port": 9001,
        "reload": True,
    }
