from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import ConnectionTimeout, QueryCanceled
from sqlalchemy.exc import OperationalError, ProgrammingError

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.api.services import readiness
from nba_data.config.settings import Settings, get_settings

_QUERY_CANCELED_SQLSTATE = "57014"


class _ScalarResult:
    def __init__(self, values: Sequence[str]) -> None:
        self._values = tuple(values)

    def all(self) -> list[str]:
        return list(self._values)


class FakeSession:
    """The narrow Session surface the readiness probe actually uses."""

    def __init__(
        self,
        *,
        revisions: Sequence[str] | None = None,
        core_tables: Sequence[str] = ("teams", "seasons"),
        dialect: str = "postgresql",
        failure: Exception | None = None,
        fail_on: str | None = None,
    ) -> None:
        self.revisions = tuple(readiness.migration_heads() if revisions is None else revisions)
        self.core_tables = tuple(core_tables)
        self.dialect = dialect
        self.failure = failure
        self.fail_on = fail_on
        self.statements: list[str] = []

    def get_bind(self) -> SimpleNamespace:
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect))

    def execute(self, statement: Any, params: Any = None) -> object:
        self._record(statement)
        return object()

    def scalars(self, statement: Any, params: Any = None) -> _ScalarResult:
        sql = self._record(statement)
        if "alembic_version" in sql:
            return _ScalarResult(self.revisions)
        return _ScalarResult(self.core_tables)

    def _record(self, statement: Any) -> str:
        sql = str(statement)
        self.statements.append(sql)
        if self.failure is not None and (self.fail_on is None or self.fail_on in sql):
            raise self.failure
        return sql


class _CanceledQuery(Exception):
    """Stands in for `psycopg.errors.QueryCanceled`, which carries this SQLSTATE."""

    sqlstate = _QUERY_CANCELED_SQLSTATE


@contextmanager
def readiness_client(session: FakeSession, *, timeout_seconds: float = 2.0) -> Iterator[TestClient]:
    app = create_app()
    settings = Settings(_env_file=None, api_readiness_timeout_seconds=timeout_seconds)
    app.dependency_overrides[get_request_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_readiness_returns_ready_when_the_database_is_migrated_and_stocked() -> None:
    with readiness_client(FakeSession()) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ready"}


@pytest.mark.unit
def test_readiness_reports_503_when_the_database_is_unreachable() -> None:
    session = FakeSession(
        failure=OperationalError("SELECT 1", {}, Exception("connection refused")),
        fail_on="SELECT 1",
    )

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


@pytest.mark.unit
def test_readiness_reports_503_when_establishing_the_connection_times_out() -> None:
    """A connect bound is a different bound from the probe's, so it reports the
    connection failure it is, not `api_readiness_timeout_seconds` being exceeded."""
    session = FakeSession(
        failure=OperationalError(
            "SELECT 1", {}, ConnectionTimeout("connection timeout expired")
        ),
        fail_on="SELECT 1",
    )

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert ConnectionTimeout.sqlstate != _QUERY_CANCELED_SQLSTATE
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


@pytest.mark.unit
def test_the_canceled_query_sqlstate_matches_the_real_driver() -> None:
    """Pin the fake below to psycopg, so the timeout path cannot drift from the driver."""
    assert QueryCanceled.sqlstate == _QUERY_CANCELED_SQLSTATE


@pytest.mark.unit
def test_readiness_reports_503_when_the_probe_exceeds_its_time_bound() -> None:
    orig = _CanceledQuery("canceling statement due to statement timeout")
    session = FakeSession(
        failure=OperationalError("SELECT 1", {}, orig),
        fail_on="SELECT 1",
    )

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database readiness check timed out"}


@pytest.mark.unit
def test_readiness_bounds_the_probe_with_the_configured_timeout() -> None:
    session = FakeSession()

    with readiness_client(session, timeout_seconds=1.5) as client:
        assert client.get("/api/v1/health/ready").status_code == 200

    assert session.statements[0] == "SET LOCAL statement_timeout = 1500"


@pytest.mark.unit
def test_readiness_reports_503_when_the_schema_is_behind_the_migration_head() -> None:
    session = FakeSession(revisions=("0004_player_season_source_team_code",))

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database schema not ready"}


@pytest.mark.unit
def test_readiness_reports_503_when_a_required_table_is_missing() -> None:
    session = FakeSession(core_tables=("teams",))

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database schema not ready"}


@pytest.mark.unit
def test_readiness_reports_503_when_the_alembic_version_table_is_absent() -> None:
    session = FakeSession(
        failure=ProgrammingError(
            "SELECT version_num FROM alembic_version",
            {},
            Exception('relation "alembic_version" does not exist'),
        ),
        fail_on="alembic_version",
    )

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database schema not ready"}


@pytest.mark.unit
def test_readiness_body_never_leaks_the_underlying_failure() -> None:
    leaky = Exception(
        "connection to postgresql://nba:hunter2@db.internal:5432/nba failed; "
        "password authentication failed, see /secret/path/pgpass"
    )
    session = FakeSession(failure=OperationalError("SELECT 1", {}, leaky), fail_on="SELECT 1")

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.text == '{"detail":"Database unavailable"}'
    for secret in ("hunter2", "password", "db.internal", "/secret/path", "postgresql://"):
        assert secret not in response.text


@pytest.mark.unit
def test_readiness_never_falls_through_to_the_unexpected_error_handler() -> None:
    session = FakeSession(failure=RuntimeError("probe exploded with a password in it"))

    with readiness_client(session) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert response.json() != {"detail": "Internal Server Error"}


@pytest.mark.unit
def test_liveness_stays_green_while_readiness_reports_the_same_broken_database() -> None:
    session = FakeSession(
        failure=OperationalError("SELECT 1", {}, Exception("connection refused")),
        fail_on="SELECT 1",
    )

    with readiness_client(session) as client:
        liveness = client.get("/api/v1/health")
        readiness_response = client.get("/api/v1/health/ready")

    assert liveness.status_code == 200
    assert liveness.json() == {"status": "ok"}
    assert readiness_response.status_code == 503
    assert readiness_response.json() == {"detail": "Database unavailable"}


@pytest.mark.unit
def test_liveness_opens_no_session() -> None:
    session = FakeSession()

    with readiness_client(session) as client:
        assert client.get("/api/v1/health").status_code == 200

    assert session.statements == []


@pytest.mark.unit
def test_readiness_route_is_get_only() -> None:
    with readiness_client(FakeSession()) as client:
        assert client.post("/api/v1/health/ready").status_code == 405
        assert client.put("/api/v1/health/ready").status_code == 405
        assert client.patch("/api/v1/health/ready").status_code == 405
        assert client.delete("/api/v1/health/ready").status_code == 405


@pytest.mark.unit
def test_readiness_declares_both_documented_responses_in_openapi() -> None:
    openapi = create_app().openapi()

    assert set(openapi["paths"]["/api/v1/health/ready"]) == {"get"}
    operation = openapi["paths"]["/api/v1/health/ready"]["get"]
    assert operation["tags"] == ["health"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadinessResponse"
    }
    assert operation["responses"]["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadinessErrorResponse"
    }
    assert set(openapi["components"]["schemas"]["ReadinessErrorResponse"]["properties"]["detail"]["enum"]) == {
        "Database unavailable",
        "Database readiness check timed out",
        "Database schema not ready",
    }


@pytest.mark.unit
def test_migration_heads_resolve_independently_of_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = readiness.migration_heads()
    readiness.migration_heads.cache_clear()
    monkeypatch.chdir(tmp_path)

    try:
        assert readiness.migration_heads() == expected
        assert expected  # the packaged migrations resolve to at least one head
    finally:
        readiness.migration_heads.cache_clear()


@pytest.mark.unit
def test_startup_succeeds_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unreachable = Settings(_env_file=None, database_url="postgresql+psycopg://nba:nba@localhost:1/nba")
    monkeypatch.setattr("nba_data.db.session.get_settings", lambda: unreachable)

    app = create_app()

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
