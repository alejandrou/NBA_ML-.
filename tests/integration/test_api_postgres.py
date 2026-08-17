"""The read API must serve real PostgreSQL, alongside whatever it already holds.

The rows seeded here are additions to a live database, not the whole of it, so
nothing asserts the absolute contents of a page. Counts are asserted as a delta
against a baseline taken before seeding, field mapping is asserted through the
by-id route where the seeded rows can be addressed directly, and the list routes
are held to the pagination properties that survive any amount of other data.

The seeded rows are removed again in the fixture teardown, and the baseline is
re-checked afterwards so a leak fails the test rather than the next one.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from nba_data.api import create_app
from nba_data.config.settings import get_settings
from nba_data.db.models.core import Season, Team
from nba_data.db.session import create_session_factory

_REQUIRE_POSTGRES_INTEGRATION_ENV = "NBA_DATA_REQUIRE_POSTGRES_INTEGRATION"
_REQUIRED_VALUES = {"1", "true", "yes", "on"}
_ALEMBIC_INI_PATH = Path(__file__).resolve().parents[2] / "alembic.ini"


@dataclass(frozen=True)
class Baseline:
    """What the database already held before this test added anything."""

    teams: int
    nba_seasons: int


@dataclass(frozen=True)
class ApiSeed:
    team_ids: tuple[int, int]
    team_codes: tuple[str, str]
    team_names: tuple[str, str]
    season_ids: tuple[int, int, int]
    nba_season_years: tuple[int, int]
    non_nba_season_year: int
    baseline: Baseline


@pytest.fixture
def postgres_api_seed() -> Iterator[ApiSeed]:
    engine = _postgres_engine_or_skip()
    session_factory = create_session_factory(engine)
    seed: ApiSeed | None = None

    try:
        seed = _seed_rows(session_factory, _counts(session_factory))
        yield seed
    finally:
        try:
            if seed is not None:
                _cleanup_rows(session_factory, seed)
                _fail_unless_restored(session_factory, seed.baseline)
        finally:
            engine.dispose()


@pytest.mark.integration
def test_postgres_api_serves_the_seeded_teams_by_id(postgres_api_seed: ApiSeed) -> None:
    """Field mapping, asserted where the seeded rows can be addressed directly."""

    with TestClient(create_app()) as client:
        responses = [
            client.get(f"/api/v1/teams/{team_id}")
            for team_id in postgres_api_seed.team_ids
        ]

    assert [response.status_code for response in responses] == [200, 200]
    assert [response.json() for response in responses] == [
        {
            "team_id": postgres_api_seed.team_ids[0],
            "basketball_reference_team_id": postgres_api_seed.team_codes[0],
            "current_abbreviation": postgres_api_seed.team_codes[0],
            "current_name": postgres_api_seed.team_names[0],
            "franchise_id": None,
        },
        {
            "team_id": postgres_api_seed.team_ids[1],
            "basketball_reference_team_id": postgres_api_seed.team_codes[1],
            "current_abbreviation": None,
            "current_name": postgres_api_seed.team_names[1],
            "franchise_id": None,
        },
    ]


@pytest.mark.integration
def test_postgres_api_pages_through_teams_without_repeating_one(
    postgres_api_seed: ApiSeed,
) -> None:
    """Pagination properties that hold whatever else the database contains."""

    with TestClient(create_app()) as client:
        pages = [
            client.get("/api/v1/teams", params={"page": page, "page_size": 2})
            for page in (1, 2)
        ]

    expected_total = postgres_api_seed.baseline.teams + 2
    seen: list[int] = []
    for page_number, response in zip((1, 2), pages, strict=True):
        assert response.status_code == 200
        body = response.json()
        assert body["page"] == page_number
        assert body["page_size"] == 2
        assert body["total"] == expected_total
        assert len(body["items"]) <= 2
        seen.extend(item["team_id"] for item in body["items"])

    assert len(seen) == len(set(seen)), f"a team was served on both pages: {seen}"


@pytest.mark.integration
def test_postgres_api_lists_and_filters_seasons(postgres_api_seed: ApiSeed) -> None:
    with TestClient(create_app()) as client:
        seasons = client.get("/api/v1/seasons", params={"page": 1, "page_size": 2})
        non_nba_season = client.get(
            f"/api/v1/seasons/{postgres_api_seed.non_nba_season_year}"
        )

    # The seeded years are above one billion and the route orders by year
    # descending, so these two head the listing regardless of the real seasons
    # stored alongside them.
    latest_year, earlier_year = postgres_api_seed.nba_season_years
    assert seasons.status_code == 200
    assert seasons.json() == {
        "items": [
            {"season_year": latest_year, "league": "NBA", "label": str(latest_year)},
            {"season_year": earlier_year, "league": "NBA", "label": None},
        ],
        "page": 1,
        "page_size": 2,
        "total": postgres_api_seed.baseline.nba_seasons + 2,
    }

    # Seeded as ABA, so the NBA-only routes must not surface it.
    assert non_nba_season.status_code == 404
    assert non_nba_season.json() == {"detail": "Season not found"}


@pytest.mark.integration
def test_postgres_api_reports_the_database_as_ready() -> None:
    _postgres_engine_or_skip().dispose()

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def _postgres_engine_or_skip() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        connect_args={"connect_timeout": 2},
        pool_pre_ping=True,
    )
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.fail("DATABASE_URL must configure PostgreSQL for this integration test", pytrace=False)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        engine.dispose()
        _skip_or_fail(f"PostgreSQL is unavailable: {exc}")

    # A schema short of the head is out of scope rather than broken, and is
    # skipped for the same reason the constraint suite skips it: CI and
    # `scripts/validate_postgres_local.py` set the require-flag, which turns
    # every skip below back into a failure where it matters.
    try:
        with engine.connect() as connection:
            revisions = set(
                connection.scalars(text("SELECT version_num FROM alembic_version")).all()
            )
    except SQLAlchemyError as exc:
        engine.dispose()
        _skip_or_fail(f"PostgreSQL schema is not migrated: {exc}")

    if not revisions:
        engine.dispose()
        _skip_or_fail("PostgreSQL schema has no Alembic revision")

    heads = set(ScriptDirectory.from_config(Config(str(_ALEMBIC_INI_PATH))).get_heads())
    if revisions != heads:
        engine.dispose()
        _skip_or_fail(
            f"PostgreSQL schema is at {sorted(revisions)}, "
            f"not the migration head {sorted(heads)}"
        )

    return engine


def _counts(session_factory: sessionmaker[Session]) -> Baseline:
    """Only NBA seasons are counted, because only those reach the season routes."""

    with session_factory() as session:
        teams = session.scalar(select(func.count()).select_from(Team)) or 0
        nba_seasons = (
            session.scalar(
                select(func.count()).select_from(Season).where(Season.league == "NBA")
            )
            or 0
        )
    return Baseline(teams=teams, nba_seasons=nba_seasons)


def _fail_unless_restored(session_factory: sessionmaker[Session], baseline: Baseline) -> None:
    current = _counts(session_factory)
    if current != baseline:
        pytest.fail(
            f"cleanup did not restore the database: it held {baseline} before "
            f"seeding and holds {current} now, so this test left rows behind",
            pytrace=False,
        )


def _seed_rows(session_factory: sessionmaker[Session], baseline: Baseline) -> ApiSeed:
    token = uuid4().hex.upper()
    team_codes = (f"F6{token[:6]}A", f"F6{token[:6]}B")
    team_names = (f"F6 {token[:6]} Alpha", f"F6 {token[:6]} Beta")
    latest_year = 1_000_000_000 + (int(token[:8], 16) % 100_000_000)
    nba_season_years = (latest_year, latest_year - 1)
    non_nba_season_year = latest_year + 1

    with session_factory.begin() as session:
        teams = [
            Team(
                basketball_reference_team_id=team_codes[0],
                current_abbreviation=team_codes[0],
                current_name=team_names[0],
                franchise_id=None,
            ),
            Team(
                basketball_reference_team_id=team_codes[1],
                current_abbreviation=None,
                current_name=team_names[1],
                franchise_id=None,
            ),
        ]
        seasons = [
            Season(season_year=latest_year, league="NBA", label=str(latest_year)),
            Season(season_year=latest_year - 1, league="NBA", label=None),
            Season(season_year=non_nba_season_year, league="ABA", label="ABA fixture"),
        ]
        session.add_all([*teams, *seasons])
        session.flush()

        return ApiSeed(
            team_ids=(teams[0].id, teams[1].id),
            team_codes=team_codes,
            team_names=team_names,
            season_ids=(seasons[0].id, seasons[1].id, seasons[2].id),
            nba_season_years=nba_season_years,
            non_nba_season_year=non_nba_season_year,
            baseline=baseline,
        )


def _cleanup_rows(session_factory: sessionmaker[Session], seed: ApiSeed) -> None:
    with session_factory.begin() as session:
        session.execute(delete(Season).where(Season.id.in_(seed.season_ids)))
        session.execute(delete(Team).where(Team.basketball_reference_team_id.in_(seed.team_codes)))


def _skip_or_fail(message: str) -> NoReturn:
    if os.getenv(_REQUIRE_POSTGRES_INTEGRATION_ENV, "").strip().lower() in _REQUIRED_VALUES:
        pytest.fail(message, pytrace=False)
    pytest.skip(message)
