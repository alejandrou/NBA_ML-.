from __future__ import annotations

from sqlalchemy import select
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


class CoreRepository:
    """Portable SQLAlchemy repository for core identity records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_season(self, *, league: str, season_year: int) -> Season:
        league_key = _clean_required(league, field_name="league").upper()
        season = self.session.scalar(
            select(Season).where(
                Season.league == league_key,
                Season.season_year == season_year,
            )
        )
        if season is not None:
            return season

        season = Season(league=league_key, season_year=season_year, label=str(season_year))
        self.session.add(season)
        self.session.flush()
        return season

    def get_or_create_team(
        self,
        *,
        basketball_reference_team_id: str,
        current_abbreviation: str,
        current_name: str | None = None,
    ) -> Team:
        team_id = _clean_required(
            basketball_reference_team_id,
            field_name="basketball_reference_team_id",
        ).upper()
        if team_id == "TOT":
            msg = "TOT must not be loaded as a real team."
            raise ValueError(msg)

        abbreviation = _clean_required(current_abbreviation, field_name="current_abbreviation").upper()
        name = _clean_optional(current_name)
        creation_name = name or abbreviation

        team = self.session.scalar(
            select(Team).where(Team.basketball_reference_team_id == team_id)
        )
        if team is not None:
            if team.current_abbreviation in (None, ""):
                team.current_abbreviation = abbreviation
            if name and _is_fallback_or_empty(team.current_name, fallback=abbreviation):
                team.current_name = name
            self.session.flush()
            return team

        team = Team(
            basketball_reference_team_id=team_id,
            current_abbreviation=abbreviation,
            current_name=creation_name,
        )
        self.session.add(team)
        self.session.flush()
        return team

    def get_or_create_team_alias(
        self,
        *,
        team: Team,
        abbreviation: str,
        name: str | None,
        season_year: int,
    ) -> TeamAlias:
        alias_abbreviation = _clean_required(abbreviation, field_name="abbreviation").upper()
        if alias_abbreviation == "TOT":
            msg = "TOT must not be loaded as a team alias."
            raise ValueError(msg)

        alias = self.session.scalar(
            select(TeamAlias).where(
                TeamAlias.team_id == team.id,
                TeamAlias.abbreviation == alias_abbreviation,
                TeamAlias.from_season_year == season_year,
                TeamAlias.to_season_year == season_year,
            )
        )
        alias_name = _clean_optional(name) or team.current_name or alias_abbreviation
        if alias is not None:
            if _clean_optional(name) and _is_fallback_or_empty(alias.name, fallback=alias_abbreviation):
                alias.name = alias_name
            self.session.flush()
            return alias

        alias = TeamAlias(
            team_id=team.id,
            abbreviation=alias_abbreviation,
            name=alias_name,
            from_season_year=season_year,
            to_season_year=season_year,
        )
        self.session.add(alias)
        self.session.flush()
        return alias

    def get_or_create_team_season(
        self,
        *,
        team: Team,
        season: Season,
        team_abbreviation: str,
    ) -> TeamSeason:
        abbreviation = _clean_required(team_abbreviation, field_name="team_abbreviation").upper()
        if abbreviation == "TOT":
            msg = "TOT must not be loaded as a real team-season."
            raise ValueError(msg)

        team_season = self.session.scalar(
            select(TeamSeason).where(
                TeamSeason.team_id == team.id,
                TeamSeason.season_id == season.id,
            )
        )
        if team_season is not None:
            return team_season

        team_season = TeamSeason(
            team_id=team.id,
            season_id=season.id,
            team_abbreviation=abbreviation,
        )
        self.session.add(team_season)
        self.session.flush()
        return team_season

    def get_or_create_player(
        self,
        *,
        basketball_reference_player_id: str,
        full_name: str | None,
    ) -> Player:
        player_id = _clean_required(
            basketball_reference_player_id,
            field_name="basketball_reference_player_id",
        )
        name = _clean_optional(full_name)
        creation_name = name or player_id

        player = self.session.scalar(
            select(Player).where(Player.basketball_reference_player_id == player_id)
        )
        if player is not None:
            if name and _is_fallback_or_empty(player.full_name, fallback=player_id):
                player.full_name = name
            self.session.flush()
            return player

        player = Player(
            basketball_reference_player_id=player_id,
            full_name=creation_name,
        )
        self.session.add(player)
        self.session.flush()
        return player

    def get_or_create_player_season(
        self,
        *,
        player: Player,
        season: Season,
    ) -> PlayerSeason:
        player_season = self.session.scalar(
            select(PlayerSeason).where(
                PlayerSeason.player_id == player.id,
                PlayerSeason.season_id == season.id,
            )
        )
        if player_season is not None:
            return player_season

        player_season = PlayerSeason(player_id=player.id, season_id=season.id)
        self.session.add(player_season)
        self.session.flush()
        return player_season

    def get_or_create_player_team_season(
        self,
        *,
        player_season: PlayerSeason,
        team_season: TeamSeason,
        roster_number: str | None = None,
        roster_position: str | None = None,
    ) -> PlayerTeamSeason:
        player_team_season = self.session.scalar(
            select(PlayerTeamSeason).where(
                PlayerTeamSeason.player_season_id == player_season.id,
                PlayerTeamSeason.team_season_id == team_season.id,
            )
        )
        if player_team_season is not None:
            number = _clean_optional(roster_number)
            position = _clean_optional(roster_position)
            if number is not None:
                player_team_season.roster_number = number
            if position is not None:
                player_team_season.roster_position = position
            self.session.flush()
            return player_team_season

        player_team_season = PlayerTeamSeason(
            player_season_id=player_season.id,
            team_season_id=team_season.id,
            roster_number=_clean_optional(roster_number),
            roster_position=_clean_optional(roster_position),
        )
        self.session.add(player_team_season)
        self.session.flush()
        return player_team_season


def _clean_required(value: str | None, *, field_name: str) -> str:
    cleaned = _clean_optional(value)
    if cleaned is None:
        msg = f"{field_name} is required."
        raise ValueError(msg)
    return cleaned


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _is_fallback_or_empty(value: str | None, *, fallback: str) -> bool:
    cleaned = _clean_optional(value)
    return cleaned is None or cleaned == fallback
