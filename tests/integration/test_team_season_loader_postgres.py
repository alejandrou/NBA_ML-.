from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.db.session import create_db_engine
from nba_data.scraping.loaders import TeamSeasonLoadBatch, load_team_season_core


@pytest.mark.integration
def test_postgres_team_season_loader_rerun_is_idempotent() -> None:
    engine = create_db_engine()
    try:
        connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable: {exc}")

    try:
        current_revision = connection.execute(text("select version_num from alembic_version")).scalar()
    except SQLAlchemyError as exc:
        connection.close()
        engine.dispose()
        pytest.skip(f"PostgreSQL schema is not migrated: {exc}")

    compatible_revisions = {"0002_core_team_player_season", "0003_stats_wide_tables"}
    if current_revision not in compatible_revisions:
        connection.close()
        engine.dispose()
        pytest.skip(f"PostgreSQL schema is at {current_revision!r}, not a core-loader test head")

    connection.rollback()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    session = session_factory()

    token = uuid4().hex[:7].upper()
    team_abbreviation = f"T{token}"
    player_one = f"f4002{token.lower()}a"
    player_two = f"f4002{token.lower()}b"

    try:
        batch = TeamSeasonLoadBatch(
            league="NBA",
            season_year=2099,
            team_abbreviation=team_abbreviation,
            team_name=f"Test Team {token}",
            rows=[
                _row(team_abbreviation, player_one, "Integration One"),
                _row(team_abbreviation, player_one, "Integration One", source_table="roster"),
                _aggregate_row(player_two, "Integration Two"),
            ],
        )

        load_team_season_core(session, batch)
        load_team_season_core(session, batch)

        assert _count(
            session,
            Season,
            Season.league == "NBA",
            Season.season_year == 2099,
        ) == 1
        assert _count(session, Team, Team.basketball_reference_team_id == team_abbreviation) == 1
        assert _count(session, TeamAlias, TeamAlias.abbreviation == team_abbreviation) == 1
        assert _count(session, TeamSeason, TeamSeason.team_abbreviation == team_abbreviation) == 1
        assert _count(
            session,
            Player,
            Player.basketball_reference_player_id.in_([player_one, player_two]),
        ) == 2
        assert _player_season_count(session, [player_one, player_two]) == 2
        assert _player_team_season_count(session, team_abbreviation) == 1
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _row(
    team_abbreviation: str,
    player_id: str,
    player_name: str,
    *,
    source_table: str = "totals",
) -> dict[str, object]:
    values: dict[str, object] = {"games": 1}
    stat_scope = "player_team_season"
    if source_table == "roster":
        values = {"number": 99, "pos": "G"}
        stat_scope = "team_roster"

    return {
        "league": "NBA",
        "season_year": 2099,
        "team_abbreviation": team_abbreviation,
        "team_context": "team",
        "source_table": source_table,
        "stat_scope": stat_scope,
        "player_name": player_name,
        "basketball_reference_player_id": player_id,
        "stable_player_key": player_id,
        "identifier_status": "present",
        "values": values,
    }


def _aggregate_row(player_id: str, player_name: str) -> dict[str, object]:
    row = _row("TOT", player_id, player_name)
    row["team_context"] = "aggregate"
    row["stat_scope"] = "player_season_aggregate"
    return row


def _count(session, model: type, *criteria) -> int:
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return session.scalar(statement) or 0


def _player_season_count(session, player_ids: list[str]) -> int:
    statement = (
        select(func.count())
        .select_from(PlayerSeason)
        .join(Player, PlayerSeason.player_id == Player.id)
        .where(Player.basketball_reference_player_id.in_(player_ids))
    )
    return session.scalar(statement) or 0


def _player_team_season_count(session, team_abbreviation: str) -> int:
    statement = (
        select(func.count())
        .select_from(PlayerTeamSeason)
        .join(TeamSeason, PlayerTeamSeason.team_season_id == TeamSeason.id)
        .where(TeamSeason.team_abbreviation == team_abbreviation)
    )
    return session.scalar(statement) or 0
