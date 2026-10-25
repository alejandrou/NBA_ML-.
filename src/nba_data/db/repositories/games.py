"""Idempotent writes for the game grain: `core.games` and its two box score tables.

Every upsert matches on the table's natural key and assigns only the columns
whose value differs, so rewriting a game from the same page issues no UPDATE and
leaves `updated_at` alone. Each method reports whether it wrote anything; the
loader turns that into `loaded` or `unchanged`. No method commits.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nba_data.db.models import (
    Game,
    Player,
    PlayerGameTotals,
    Season,
    TeamGameTotals,
    TeamSeason,
)

NBA_LEAGUE = "NBA"


@dataclass(frozen=True)
class TeamSeasonKey:
    team_season_id: int
    season_id: int


@dataclass(frozen=True)
class FinalGameVenue:
    game_id: int
    basketball_reference_game_id: str
    home_team_season_id: int
    venue: str | None
    neutral_site: bool | None


class GameRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def team_seasons(self, season_year: int, codes: Iterable[str]) -> dict[str, TeamSeasonKey]:
        """The `core.team_seasons` rows of these codes in this NBA season; absent codes are omitted."""

        wanted = sorted(set(codes))
        rows = self.session.execute(
            select(TeamSeason.team_abbreviation, TeamSeason.id, TeamSeason.season_id)
            .join(Season, Season.id == TeamSeason.season_id)
            .where(
                Season.league == NBA_LEAGUE,
                Season.season_year == season_year,
                TeamSeason.team_abbreviation.in_(wanted),
            )
        ).all()
        return {
            code: TeamSeasonKey(team_season_id, season_id)
            for code, team_season_id, season_id in rows
        }

    def season_id(self, season_year: int) -> int | None:
        return self.session.scalar(
            select(Season.id).where(Season.league == NBA_LEAGUE, Season.season_year == season_year)
        )

    def player_ids(self, basketball_reference_ids: Iterable[str]) -> dict[str, int]:
        wanted = sorted(set(basketball_reference_ids))
        if not wanted:
            return {}
        rows = self.session.execute(
            select(Player.basketball_reference_player_id, Player.id).where(
                Player.basketball_reference_player_id.in_(wanted)
            )
        ).all()
        return {bref_id: player_id for bref_id, player_id in rows if bref_id is not None}

    def create_player(self, *, basketball_reference_player_id: str, full_name: str) -> int:
        """Create a player from a box score link: stable id, link text, no player-season."""

        player = Player(
            basketball_reference_player_id=basketball_reference_player_id, full_name=full_name
        )
        self.session.add(player)
        self.session.flush()
        return player.id

    def upsert_game(
        self, *, basketball_reference_game_id: str, values: Mapping[str, Any]
    ) -> tuple[int, bool]:
        record = self.session.scalar(
            select(Game).where(Game.basketball_reference_game_id == basketball_reference_game_id)
        )
        if record is None:
            record = Game(basketball_reference_game_id=basketball_reference_game_id, **values)
            self.session.add(record)
            self.session.flush()
            return record.id, True
        changed = _assign_changed(record, values)
        if changed:
            self.session.flush()
        return record.id, changed

    def upsert_team_game_totals(
        self,
        *,
        game_id: int,
        team_season_id: int,
        values: Mapping[str, Any],
    ) -> bool:
        record = self.session.scalar(
            select(TeamGameTotals).where(
                TeamGameTotals.game_id == game_id,
                TeamGameTotals.team_season_id == team_season_id,
            )
        )
        if record is None:
            self.session.add(
                TeamGameTotals(game_id=game_id, team_season_id=team_season_id, **values)
            )
            self.session.flush()
            return True
        changed = _assign_changed(record, values)
        if changed:
            self.session.flush()
        return changed

    def replace_player_game_totals(
        self,
        *,
        game_id: int,
        rows: Mapping[int, Mapping[str, Any]],
    ) -> bool:
        """Make the game's player lines exactly `rows`, keyed by `core.players.id`."""

        existing = {
            record.player_id: record
            for record in self.session.scalars(
                select(PlayerGameTotals).where(PlayerGameTotals.game_id == game_id)
            )
        }
        changed = False
        stale = sorted(set(existing) - set(rows))
        if stale:
            self.session.execute(
                delete(PlayerGameTotals).where(
                    PlayerGameTotals.game_id == game_id,
                    PlayerGameTotals.player_id.in_(stale),
                )
            )
            changed = True
        for player_id, values in rows.items():
            record = existing.get(player_id)
            if record is None:
                self.session.add(PlayerGameTotals(game_id=game_id, player_id=player_id, **values))
                changed = True
            elif _assign_changed(record, values):
                changed = True
        if changed:
            self.session.flush()
        return changed

    def remove_other_team_totals(self, *, game_id: int, team_season_ids: Iterable[int]) -> bool:
        """Remove an obsolete side before upserting a corrected game's teams.

        Player lines reference team totals through a composite foreign key, so
        dependent lines must go first. Both deletes share the game's transaction.
        """
        stale = list(self.session.scalars(
            select(TeamGameTotals.team_season_id).where(
                TeamGameTotals.game_id == game_id,
                TeamGameTotals.team_season_id.not_in(tuple(team_season_ids)),
            )
        ))
        if not stale:
            return False
        self.session.execute(delete(PlayerGameTotals).where(
            PlayerGameTotals.game_id == game_id, PlayerGameTotals.team_season_id.in_(stale),
        ))
        self.session.execute(delete(TeamGameTotals).where(
            TeamGameTotals.game_id == game_id, TeamGameTotals.team_season_id.in_(stale),
        ))
        return True

    def final_game_venues(self, season_id: int) -> list[FinalGameVenue]:
        rows = self.session.execute(
            select(
                Game.id,
                Game.basketball_reference_game_id,
                Game.home_team_season_id,
                Game.venue,
                Game.neutral_site,
            )
            .where(Game.season_id == season_id, Game.status == "final")
            .order_by(Game.game_date, Game.basketball_reference_game_id)
        ).all()
        return [FinalGameVenue(*row) for row in rows]

    def set_neutral_site(self, game_id: int, neutral_site: bool | None) -> None:
        record = self.session.get(Game, game_id)
        if record is None:
            msg = f"core.games row {game_id} does not exist"
            raise ValueError(msg)
        record.neutral_site = neutral_site
        self.session.flush()


def _assign_changed(record: object, values: Mapping[str, Any]) -> bool:
    changed = False
    for column, value in values.items():
        if getattr(record, column) != value:
            setattr(record, column, value)
            changed = True
    return changed


__all__ = ["FinalGameVenue", "GameRepository", "TeamSeasonKey"]
