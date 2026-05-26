from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint

import nba_data.db.models as models
from nba_data.db.base import Base
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)


def test_core_relationship_tables_are_registered_in_core_schema() -> None:
    assert Base.metadata.tables["core.team_seasons"] is TeamSeason.__table__
    assert Base.metadata.tables["core.player_seasons"] is PlayerSeason.__table__
    assert Base.metadata.tables["core.player_team_seasons"] is PlayerTeamSeason.__table__

    assert TeamSeason.__table__.schema == "core"
    assert PlayerSeason.__table__.schema == "core"
    assert PlayerTeamSeason.__table__.schema == "core"


def test_core_identifier_constraints_are_explicit() -> None:
    assert "uq_core_teams_bref_id" in _constraint_names(Team, UniqueConstraint)
    assert "ck_core_teams_bref_id_not_tot" in _constraint_names(Team, CheckConstraint)
    assert "ck_core_teams_current_abbreviation_not_tot" in _constraint_names(
        Team, CheckConstraint
    )
    assert "ck_core_team_aliases_abbreviation_not_tot" in _constraint_names(
        TeamAlias, CheckConstraint
    )
    assert "uq_core_players_bref_id" in _constraint_names(Player, UniqueConstraint)
    assert "uq_core_seasons_league_year" in _constraint_names(Season, UniqueConstraint)


def test_team_season_constraints_reject_tot_as_real_team() -> None:
    assert "uq_core_team_seasons_team_season" in _constraint_names(
        TeamSeason, UniqueConstraint
    )
    assert "uq_core_team_seasons_season_abbrev" in _constraint_names(
        TeamSeason, UniqueConstraint
    )
    assert "ck_core_team_seasons_abbrev_not_tot" in _constraint_names(
        TeamSeason, CheckConstraint
    )

    assert TeamSeason.__table__.c.team_abbreviation.nullable is False


def test_player_season_relationship_constraints_are_idempotent_keys() -> None:
    assert "uq_core_player_seasons_player_season" in _constraint_names(
        PlayerSeason, UniqueConstraint
    )
    assert "ix_core_player_seasons_season_id" in _index_names(PlayerSeason)
    assert "uq_core_player_team_seasons_player_team" in _constraint_names(
        PlayerTeamSeason, UniqueConstraint
    )
    assert "ix_core_player_team_seasons_team_season_id" in _index_names(PlayerTeamSeason)

    assert PlayerTeamSeason.__table__.c.roster_number.nullable is True
    assert PlayerTeamSeason.__table__.c.roster_position.nullable is True
    assert "points" not in PlayerTeamSeason.__table__.c


def test_core_relationship_foreign_keys_target_core_tables() -> None:
    assert _foreign_key_targets(TeamSeason) == {
        "core.seasons.id",
        "core.teams.id",
    }
    assert _foreign_key_targets(PlayerSeason) == {
        "core.players.id",
        "core.seasons.id",
    }
    assert _foreign_key_targets(PlayerTeamSeason) == {
        "core.player_seasons.id",
        "core.team_seasons.id",
    }


def test_core_relationships_are_bidirectional() -> None:
    assert Team.team_seasons.property.mapper.class_ is TeamSeason
    assert TeamSeason.team.property.mapper.class_ is Team
    assert Season.team_seasons.property.mapper.class_ is TeamSeason
    assert TeamSeason.season.property.mapper.class_ is Season

    assert Player.player_seasons.property.mapper.class_ is PlayerSeason
    assert PlayerSeason.player.property.mapper.class_ is Player
    assert PlayerSeason.player_team_seasons.property.mapper.class_ is PlayerTeamSeason
    assert PlayerTeamSeason.player_season.property.mapper.class_ is PlayerSeason
    assert TeamSeason.player_team_seasons.property.mapper.class_ is PlayerTeamSeason
    assert PlayerTeamSeason.team_season.property.mapper.class_ is TeamSeason


def test_core_models_are_exported() -> None:
    assert models.TeamSeason is TeamSeason
    assert models.PlayerSeason is PlayerSeason
    assert models.PlayerTeamSeason is PlayerTeamSeason
    assert "TeamSeason" in models.__all__
    assert "PlayerSeason" in models.__all__
    assert "PlayerTeamSeason" in models.__all__


def _constraint_names(model: type, constraint_type: type) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, constraint_type)
    }


def _index_names(model: type) -> set[str]:
    return {index.name for index in model.__table__.indexes if isinstance(index, Index)}


def _foreign_key_targets(model: type) -> set[str]:
    targets: set[str] = set()
    for constraint in model.__table__.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            targets.update(element.target_fullname for element in constraint.elements)
    return targets
