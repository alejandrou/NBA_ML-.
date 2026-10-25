"""Read the authoritative identity keys for an explicitly database-backed pilot."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from nba_data.db.models import Player, Season, TeamSeason


def load_game_identity_keys(
    session: Session,
) -> tuple[frozenset[str], frozenset[tuple[str, int]]]:
    players = frozenset(
        player for player in session.scalars(select(Player.basketball_reference_player_id))
        if player is not None
    )
    teams = frozenset(
        (code, year) for code, year in session.execute(
            select(TeamSeason.team_abbreviation, Season.season_year)
            .join(Season, Season.id == TeamSeason.season_id)
            .where(Season.league == "NBA")
        )
    )
    return players, teams
