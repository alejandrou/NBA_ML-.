from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
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
def test_team_routes_validate_inputs_and_expose_only_get(client: TestClient) -> None:
    assert client.get("/api/v1/teams?page=0").status_code == 422
    assert client.get("/api/v1/teams?page_size=101").status_code == 422
    assert client.get("/api/v1/teams/ABCDEFGHIJK").status_code == 422
    empty_code = client.get("/api/v1/teams/")
    assert empty_code.status_code == 404
    assert empty_code.json() == {"detail": "Team not found"}
    assert client.get("/api/v1/teams/ATL/extra").status_code == 404
    assert client.post("/api/v1/teams").status_code == 405
    assert client.put("/api/v1/teams/ATL").status_code == 405
    assert client.patch("/api/v1/teams/ATL").status_code == 405
    assert client.delete("/api/v1/teams/ATL").status_code == 405


@pytest.mark.unit
def test_team_collection_serves_the_approved_fields_and_page_metadata(
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


@pytest.mark.unit
def test_team_collection_orders_by_name_then_natural_key(
    vertical_client: TestClient,
) -> None:
    """The contract's tie-breaker is the natural key, not the surrogate id.

    The two `Bulls` rows are stored with ids 3 and 1, so ordering on the
    surrogate would serve `BBB` before `AAA`. That is the regression this pins.
    """

    listed = vertical_client.get("/api/v1/teams", params={"page_size": 100})

    assert listed.status_code == 200
    assert [
        (item["current_name"], item["basketball_reference_team_id"])
        for item in listed.json()["items"]
    ] == [
        ("Bulls", "AAA"),
        ("Bulls", "BBB"),
        ("Celtics", "CCC"),
        ("Oklahoma City Thunder", "OKC"),
        ("Seattle SuperSonics", "SEA"),
    ]


@pytest.mark.unit
def test_team_pages_partition_the_collection_without_repeating_a_natural_key(
    vertical_client: TestClient,
) -> None:
    pages = [
        vertical_client.get("/api/v1/teams", params={"page": page, "page_size": 2})
        for page in (1, 2, 3)
    ]

    assert [response.status_code for response in pages] == [200, 200, 200]
    assert [len(response.json()["items"]) for response in pages] == [2, 2, 1]
    assert [(response.json()["page"], response.json()["page_size"]) for response in pages] == [
        (1, 2),
        (2, 2),
        (3, 2),
    ]
    assert {response.json()["total"] for response in pages} == {5}

    served = [
        item["basketball_reference_team_id"]
        for response in pages
        for item in response.json()["items"]
    ]
    assert served == ["AAA", "BBB", "CCC", "OKC", "SEA"]
    assert len(served) == len(set(served)), f"a team was served twice: {served}"


@pytest.mark.unit
def test_a_valid_page_past_the_end_is_empty_and_keeps_the_total(
    vertical_client: TestClient,
) -> None:
    """An empty page is a valid answer, not a 404 and not a changed total.

    Also the one place the default `page_size` is pinned, since the request that
    omits it is the request that would silently change size.
    """

    sized = vertical_client.get("/api/v1/teams", params={"page": 999, "page_size": 2})
    defaulted = vertical_client.get("/api/v1/teams", params={"page": 999})

    assert sized.status_code == 200
    assert sized.json() == {"items": [], "page": 999, "page_size": 2, "total": 5}
    assert defaulted.status_code == 200
    assert defaulted.json() == {"items": [], "page": 999, "page_size": 50, "total": 5}


@pytest.mark.unit
def test_team_detail_serves_a_team_by_its_natural_key(vertical_client: TestClient) -> None:
    detail = vertical_client.get("/api/v1/teams/CCC")

    assert detail.status_code == 200
    assert detail.json() == {
        "basketball_reference_team_id": "CCC",
        "current_abbreviation": None,
        "current_name": "Celtics",
    }


@pytest.mark.unit
def test_a_numeric_path_is_not_a_surrogate_id_lookup(vertical_client: TestClient) -> None:
    """`/teams/1` must stay a lookup for the code `"1"`, which no team holds.

    The fixture stores `BBB` at internal `id=1` deliberately. If a later change
    reintroduced surrogate-id routing, `/teams/1` would start answering 200 with
    that row — so this asserts the row is genuinely reachable by its code first,
    which is what makes the 404 below evidence rather than a coincidence.
    """

    by_code = vertical_client.get("/api/v1/teams/BBB")

    assert by_code.status_code == 200
    assert by_code.json() == {
        "basketball_reference_team_id": "BBB",
        "current_abbreviation": "BBB",
        "current_name": "Bulls",
    }

    by_surrogate_id = vertical_client.get("/api/v1/teams/1")

    assert by_surrogate_id.status_code == 404
    assert by_surrogate_id.json() == {"detail": "Team not found"}


@pytest.mark.unit
def test_withdrawn_identity_fields_are_absent_from_every_team_response(
    vertical_client: TestClient,
) -> None:
    """`F5-006` withdrew `team_id` and `franchise_id` from v1."""

    detail = vertical_client.get("/api/v1/teams/AAA")
    listed = vertical_client.get("/api/v1/teams", params={"page_size": 100})

    withdrawn = {"team_id", "franchise_id"}
    assert set(detail.json()) == {
        "basketball_reference_team_id",
        "current_abbreviation",
        "current_name",
    }
    for item in listed.json()["items"]:
        assert withdrawn.isdisjoint(item), item


@pytest.mark.unit
def test_team_codes_are_exact_and_synthetic_codes_are_not_resolvable(
    vertical_client: TestClient,
) -> None:
    """Case-sensitive lookup, and `TOT` is a marker rather than an addressable team."""

    assert vertical_client.get("/api/v1/teams/AAA").status_code == 200

    for unresolvable in ("aaa", "UNKNOWN", "TOT"):
        response = vertical_client.get(f"/api/v1/teams/{unresolvable}")

        assert response.status_code == 404, unresolvable
        assert response.json() == {"detail": "Team not found"}, unresolvable


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
