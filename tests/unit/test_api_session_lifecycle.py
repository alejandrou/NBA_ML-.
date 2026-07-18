from collections.abc import Iterator
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True


@pytest.mark.unit
def test_lifespan_owns_one_engine_and_session_factory_per_app(monkeypatch: pytest.MonkeyPatch) -> None:
    engines: list[FakeEngine] = []
    factory_engines: list[FakeEngine] = []

    def fake_create_engine() -> FakeEngine:
        engine = FakeEngine()
        engines.append(engine)
        return engine

    def fake_create_session_factory(engine: FakeEngine) -> object:
        factory_engines.append(engine)
        return object()

    monkeypatch.setattr("nba_data.api.app.create_db_engine", fake_create_engine)
    monkeypatch.setattr("nba_data.api.app.create_session_factory", fake_create_session_factory)

    first_app = create_app()
    second_app = create_app()

    with TestClient(first_app):
        assert first_app.state.engine is engines[0]
        assert first_app.state.session_factory is not None
        assert not engines[0].disposed
    with TestClient(second_app):
        assert second_app.state.engine is engines[1]
        assert second_app.state.session_factory is not None
        assert not engines[1].disposed

    assert factory_engines == engines
    assert all(engine.disposed for engine in engines)


@pytest.mark.unit
def test_health_does_not_open_a_database_session(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = FakeEngine()
    session_opens = 0

    def session_factory() -> FakeSession:
        nonlocal session_opens
        session_opens += 1
        return FakeSession()

    def fake_create_session_factory(received_engine: FakeEngine) -> object:
        assert received_engine is engine
        return session_factory

    monkeypatch.setattr("nba_data.api.app.create_db_engine", lambda: engine)
    monkeypatch.setattr("nba_data.api.app.create_session_factory", fake_create_session_factory)

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.json() == {"status": "ok"}
    assert session_opens == 0


@pytest.mark.unit
def test_request_session_is_independent_and_closed() -> None:
    sessions: list[FakeSession] = []

    def session_factory() -> FakeSession:
        session = FakeSession()
        sessions.append(session)
        return session

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=session_factory)))

    first_session = _open_and_close_request_session(request)
    second_session = _open_and_close_request_session(request)

    assert first_session is not second_session
    assert sessions == [first_session, second_session]
    assert all(session.closed for session in sessions)


@pytest.mark.unit
def test_request_session_dependency_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = FakeEngine()

    def fail_if_session_is_opened() -> FakeSession:
        raise AssertionError("The overridden dependency must not open an app Session")

    def fake_create_session_factory(received_engine: FakeEngine) -> object:
        assert received_engine is engine
        return fail_if_session_is_opened

    monkeypatch.setattr("nba_data.api.app.create_db_engine", lambda: engine)
    monkeypatch.setattr("nba_data.api.app.create_session_factory", fake_create_session_factory)

    app = create_app()
    override_session = object()

    @app.get("/test/session", include_in_schema=False)
    def read_overridden_session(
        session: Annotated[object, Depends(get_request_session)],
    ) -> dict[str, bool]:
        return {"overridden": session is override_session}

    app.dependency_overrides[get_request_session] = lambda: override_session
    try:
        with TestClient(app) as client:
            response = client.get("/test/session")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"overridden": True}


def _open_and_close_request_session(request: object) -> FakeSession:
    dependency: Iterator[FakeSession] = get_request_session(request)  # type: ignore[arg-type]
    session = next(dependency)
    dependency.close()
    return session
