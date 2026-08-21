"""The read API must serve real PostgreSQL, in a database that holds only this.

The lane's database is disposable and starts empty — `tests/integration/conftest.py`
refuses to run otherwise — so these assertions are exact rather than deltas
against whatever else was stored. Exact totals and exact ordering are what
actually pin the contract; a delta assertion passes even when the route serves
the wrong page.

Nothing here commits. Rows are seeded through the outer Connection the fixture
owns and rolls back, and each HTTP request gets a fresh Session joined to that
same Connection, so the API reads exactly what this test wrote and the database
is left as it was found.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class ApiSeed:
    """Identity is carried as natural keys; no surrogate id leaves this seed."""

    team_codes: tuple[str, str]
    team_names: tuple[str, str]
    nba_season_years: tuple[int, int]
    non_nba_season_year: int


@pytest.fixture
def api_seed(postgres_connection: Connection) -> Iterator[ApiSeed]:
    """Two teams and three seasons, written inside the rolled-back transaction."""

    token = _unique_token()
    team_codes = (f"{token}A", f"{token}B")
    team_names = (f"{token} Alpha", f"{token} Beta")
    latest_year = 2_099
    seed = ApiSeed(
        team_codes=team_codes,
        team_names=team_names,
        nba_season_years=(latest_year, latest_year - 1),
        non_nba_season_year=latest_year + 1,
    )

    postgres_connection.execute(
        text(
            "insert into core.teams "
            "(basketball_reference_team_id, current_abbreviation, current_name) "
            "values (:first_code, :first_code, :first_name), "
            "(:second_code, null, :second_name)"
        ),
        {
            "first_code": team_codes[0],
            "first_name": team_names[0],
            "second_code": team_codes[1],
            "second_name": team_names[1],
        },
    )
    postgres_connection.execute(
        text(
            "insert into core.seasons (season_year, league, label) values "
            "(:latest, 'NBA', :latest_label), "
            "(:earlier, 'NBA', null), "
            "(:non_nba, 'ABA', 'ABA fixture')"
        ),
        {
            "latest": seed.nba_season_years[0],
            "latest_label": str(seed.nba_season_years[0]),
            "earlier": seed.nba_season_years[1],
            "non_nba": seed.non_nba_season_year,
        },
    )
    yield seed


@pytest.mark.integration
def test_postgres_api_serves_the_seeded_teams_by_code(
    postgres_api_client: TestClient, api_seed: ApiSeed
) -> None:
    """Field mapping, including the nullable abbreviation, through real psycopg."""

    responses = [
        postgres_api_client.get(f"/api/v1/teams/{team_code}")
        for team_code in api_seed.team_codes
    ]

    assert [response.status_code for response in responses] == [200, 200]
    assert [response.json() for response in responses] == [
        {
            "basketball_reference_team_id": api_seed.team_codes[0],
            "current_abbreviation": api_seed.team_codes[0],
            "current_name": api_seed.team_names[0],
        },
        {
            "basketball_reference_team_id": api_seed.team_codes[1],
            "current_abbreviation": None,
            "current_name": api_seed.team_names[1],
        },
    ]


@pytest.mark.integration
def test_postgres_api_pages_through_teams_without_repeating_one(
    postgres_api_client: TestClient, api_seed: ApiSeed
) -> None:
    """Exact pages, because the database holds only what the fixture seeded."""

    pages = [
        postgres_api_client.get("/api/v1/teams", params={"page": page, "page_size": 1})
        for page in (1, 2, 3)
    ]

    assert [response.status_code for response in pages] == [200, 200, 200]
    first, second, beyond = (response.json() for response in pages)

    assert first == {
        "items": [
            {
                "basketball_reference_team_id": api_seed.team_codes[0],
                "current_abbreviation": api_seed.team_codes[0],
                "current_name": api_seed.team_names[0],
            }
        ],
        "page": 1,
        "page_size": 1,
        "total": 2,
    }
    assert second == {
        "items": [
            {
                "basketball_reference_team_id": api_seed.team_codes[1],
                "current_abbreviation": None,
                "current_name": api_seed.team_names[1],
            }
        ],
        "page": 2,
        "page_size": 1,
        "total": 2,
    }
    # A valid page past the end is empty, not an error, and does not change the total.
    assert beyond == {"items": [], "page": 3, "page_size": 1, "total": 2}

    served = [
        item["basketball_reference_team_id"]
        for body in (first, second)
        for item in body["items"]
    ]
    assert served == sorted(set(served)), f"a team was served on both pages: {served}"


@pytest.mark.integration
def test_postgres_api_lists_and_filters_seasons(
    postgres_api_client: TestClient, api_seed: ApiSeed
) -> None:
    seasons = postgres_api_client.get("/api/v1/seasons", params={"page": 1, "page_size": 2})
    non_nba_season = postgres_api_client.get(
        f"/api/v1/seasons/{api_seed.non_nba_season_year}"
    )

    latest_year, earlier_year = api_seed.nba_season_years
    assert seasons.status_code == 200
    assert seasons.json() == {
        "items": [
            {"season_year": latest_year, "league": "NBA", "label": str(latest_year)},
            {"season_year": earlier_year, "league": "NBA", "label": None},
        ],
        "page": 1,
        "page_size": 2,
        # The ABA season is stored but must not be counted by an NBA-only route.
        "total": 2,
    }

    assert non_nba_season.status_code == 404
    assert non_nba_season.json() == {"detail": "Season not found"}


@pytest.mark.integration
def test_postgres_api_reports_the_database_as_ready(postgres_api_client: TestClient) -> None:
    response = postgres_api_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def _unique_token() -> str:
    """Eight random letters, so the seeded codes cannot collide or look synthetic.

    Codes are generated rather than fixed so no assertion can quietly come to
    depend on a particular real team's code being present.
    """

    return "".join(chr(ord("A") + byte % 26) for byte in uuid4().bytes[:8])
