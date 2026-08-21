"""Loading the same batch twice must leave one of everything on real PostgreSQL.

The loader's upserts rely on `ON CONFLICT` semantics and on the unique
constraints the migrations create, neither of which the offline SQLite lane
proves. Nothing here manages its own connection or transaction: the Session
comes from the shared fixture, which owns the outer transaction and rolls it
back, so the loader keeps its real caller-owned-transaction contract while the
database is left as it was found.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.scraping.loaders import TeamSeasonLoadBatch, load_team_season_core


@pytest.mark.integration
def test_postgres_team_season_loader_rerun_is_idempotent(postgres_session: Session) -> None:
    token = uuid4().hex[:7].upper()
    team_abbreviation = f"T{token}"
    player_one = f"f4002{token.lower()}a"
    player_two = f"f4002{token.lower()}b"

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

    load_team_season_core(postgres_session, batch)
    load_team_season_core(postgres_session, batch)

    # Every count is against a domain or natural key, never a generated id:
    # sequences advance even inside a rolled-back transaction, so an id proves
    # nothing about what the second load did.
    assert _count(
        postgres_session,
        Season,
        Season.league == "NBA",
        Season.season_year == 2099,
    ) == 1
    assert _count(
        postgres_session, Team, Team.basketball_reference_team_id == team_abbreviation
    ) == 1
    assert _count(postgres_session, TeamAlias, TeamAlias.abbreviation == team_abbreviation) == 1
    assert _count(
        postgres_session, TeamSeason, TeamSeason.team_abbreviation == team_abbreviation
    ) == 1
    assert _count(
        postgres_session,
        Player,
        Player.basketball_reference_player_id.in_([player_one, player_two]),
    ) == 2
    assert _player_season_count(postgres_session, [player_one, player_two]) == 2
    assert _player_team_season_count(postgres_session, team_abbreviation) == 1


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


def _count(session: Session, model: type, *criteria) -> int:
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return session.scalar(statement) or 0


def _player_season_count(session: Session, player_ids: list[str]) -> int:
    statement = (
        select(func.count())
        .select_from(PlayerSeason)
        .join(Player, PlayerSeason.player_id == Player.id)
        .where(Player.basketball_reference_player_id.in_(player_ids))
    )
    return session.scalar(statement) or 0


def _player_team_season_count(session: Session, team_abbreviation: str) -> int:
    statement = (
        select(func.count())
        .select_from(PlayerTeamSeason)
        .join(TeamSeason, PlayerTeamSeason.team_season_id == TeamSeason.id)
        .where(TeamSeason.team_abbreviation == team_abbreviation)
    )
    return session.scalar(statement) or 0
