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
class ApiSeed:
    team_ids: tuple[int, int]
    team_codes: tuple[str, str]
    season_ids: tuple[int, int, int]
    nba_season_years: tuple[int, int]
    non_nba_season_year: int


@pytest.fixture
def postgres_api_seed() -> Iterator[ApiSeed]:
    engine = _postgres_engine_or_skip()
    session_factory = create_session_factory(engine)
    seed: ApiSeed | None = None

    try:
        _fail_unless_empty(session_factory, when="before seeding")
        seed = _seed_rows(session_factory)
        yield seed
    finally:
        try:
            if seed is not None:
                _cleanup_rows(session_factory, seed)
                _fail_unless_empty(session_factory, when="after cleanup")
        finally:
            engine.dispose()


@pytest.mark.integration
def test_postgres_api_reads_teams_and_filtered_seasons(
    postgres_api_seed: ApiSeed,
) -> None:
    with TestClient(create_app()) as client:
        teams = client.get("/api/v1/teams", params={"page": 1, "page_size": 2})
        seasons = client.get("/api/v1/seasons", params={"page": 1, "page_size": 2})
        non_nba_season = client.get(
            f"/api/v1/seasons/{postgres_api_seed.non_nba_season_year}"
        )

    assert teams.status_code == 200
    assert teams.json() == {
        "items": [
            {
                "team_id": postgres_api_seed.team_ids[0],
                "basketball_reference_team_id": postgres_api_seed.team_codes[0],
                "current_abbreviation": postgres_api_seed.team_codes[0],
                "current_name": _team_name(postgres_api_seed, "Alpha"),
                "franchise_id": None,
            },
            {
                "team_id": postgres_api_seed.team_ids[1],
                "basketball_reference_team_id": postgres_api_seed.team_codes[1],
                "current_abbreviation": None,
                "current_name": _team_name(postgres_api_seed, "Beta"),
                "franchise_id": None,
            },
        ],
        "page": 1,
        "page_size": 2,
        "total": 2,
    }

    latest_year, earlier_year = postgres_api_seed.nba_season_years
    assert seasons.status_code == 200
    assert seasons.json() == {
        "items": [
            {"season_year": latest_year, "league": "NBA", "label": str(latest_year)},
            {"season_year": earlier_year, "league": "NBA", "label": None},
        ],
        "page": 1,
        "page_size": 2,
        "total": 2,
    }

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

    try:
        with engine.connect() as connection:
            revisions = set(
                connection.scalars(text("SELECT version_num FROM alembic_version")).all()
            )
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.fail(f"PostgreSQL schema is not migrated: {exc}", pytrace=False)

    if not revisions:
        engine.dispose()
        pytest.fail("PostgreSQL schema has no Alembic revision", pytrace=False)

    heads = set(ScriptDirectory.from_config(Config(str(_ALEMBIC_INI_PATH))).get_heads())
    if revisions != heads:
        engine.dispose()
        pytest.fail(
            f"PostgreSQL schema is at {sorted(revisions)}, "
            f"not the migration head {sorted(heads)}",
            pytrace=False,
        )

    return engine


def _fail_unless_empty(session_factory: sessionmaker[Session], *, when: str) -> None:
    with session_factory() as session:
        team_count = session.scalar(select(func.count()).select_from(Team)) or 0
        season_count = session.scalar(select(func.count()).select_from(Season)) or 0

    if team_count or season_count:
        pytest.fail(
            f"PostgreSQL database is not isolated ({when}): "
            f"found {team_count} team row(s) and {season_count} season row(s). "
            "This test requires an empty core.teams/core.seasons and must not "
            "run against a populated database.",
            pytrace=False,
        )


def _seed_rows(session_factory: sessionmaker[Session]) -> ApiSeed:
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
            season_ids=(seasons[0].id, seasons[1].id, seasons[2].id),
            nba_season_years=nba_season_years,
            non_nba_season_year=non_nba_season_year,
        )


def _cleanup_rows(session_factory: sessionmaker[Session], seed: ApiSeed) -> None:
    with session_factory.begin() as session:
        session.execute(delete(Season).where(Season.id.in_(seed.season_ids)))
        session.execute(delete(Team).where(Team.basketball_reference_team_id.in_(seed.team_codes)))


def _team_name(seed: ApiSeed, suffix: str) -> str:
    token = seed.team_codes[0][2:-1]
    return f"F6 {token} {suffix}"


def _skip_or_fail(message: str) -> NoReturn:
    if os.getenv(_REQUIRE_POSTGRES_INTEGRATION_ENV, "").strip().lower() in _REQUIRED_VALUES:
        pytest.fail(message, pytrace=False)
    pytest.skip(message)
