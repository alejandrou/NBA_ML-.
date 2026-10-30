"""Read every finished game the team features may learn from, in one SELECT.

History is every `final` game of type `regular_season` or `cup_final` in an NBA
season. A team is its `core.teams.basketball_reference_team_id`, which is
stable across 2014-15 to 2026-27, so no franchise is inferred. The caller owns
the Session; nothing here adds, flushes, or commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from nba_data.db.models import Game, Season, Team, TeamGameTotals, TeamSeason

STATUS_FINAL = "final"
GAME_TYPE_REGULAR_SEASON = "regular_season"
GAME_TYPE_CUP_FINAL = "cup_final"
HISTORY_GAME_TYPES = (GAME_TYPE_REGULAR_SEASON, GAME_TYPE_CUP_FINAL)


@dataclass(frozen=True)
class TeamBox:
    """One side of a game. A counter is `None` when its cell was blank."""

    team_code: str
    pts: int | None
    seconds_played: int | None
    fg: int | None
    fga: int | None
    fg3: int | None
    ft: int | None
    fta: int | None
    orb: int | None
    drb: int | None
    tov: int | None


@dataclass(frozen=True)
class TeamGameRecord:
    game_id: str
    season_year: int
    game_date: date
    game_type: str | None
    status: str
    # `None` is undetermined; the features treat it as a home game and count it.
    neutral_site: bool | None
    home: TeamBox
    away: TeamBox


def load_team_game_history(session: Session) -> list[TeamGameRecord]:
    """Every history game, ordered by `(game_date, basketball_reference_game_id)`."""

    home_ts = aliased(TeamSeason)
    away_ts = aliased(TeamSeason)
    home_team = aliased(Team)
    away_team = aliased(Team)
    home_box = aliased(TeamGameTotals)
    away_box = aliased(TeamGameTotals)

    statement = (
        select(
            Game.basketball_reference_game_id,
            Season.season_year,
            Game.game_date,
            Game.game_type,
            Game.status,
            Game.neutral_site,
            home_team.basketball_reference_team_id,
            *_box_columns(home_box),
            away_team.basketball_reference_team_id,
            *_box_columns(away_box),
        )
        .join(Season, Season.id == Game.season_id)
        .join(home_ts, home_ts.id == Game.home_team_season_id)
        .join(home_team, home_team.id == home_ts.team_id)
        .join(away_ts, away_ts.id == Game.away_team_season_id)
        .join(away_team, away_team.id == away_ts.team_id)
        .outerjoin(
            home_box,
            and_(home_box.game_id == Game.id, home_box.team_season_id == Game.home_team_season_id),
        )
        .outerjoin(
            away_box,
            and_(away_box.game_id == Game.id, away_box.team_season_id == Game.away_team_season_id),
        )
        .where(
            Season.league == "NBA",
            Game.status == STATUS_FINAL,
            Game.game_type.in_(HISTORY_GAME_TYPES),
        )
        .order_by(Game.game_date, Game.basketball_reference_game_id)
    )

    width = len(_BOX_FIELDS) + 1
    records = []
    # Without this, execute() would autoflush the caller's pending changes.
    with session.no_autoflush:
        rows = session.execute(statement).all()
    for row in rows:
        game_id, season_year, game_date, game_type, status, neutral_site = row[:6]
        home = TeamBox(*row[6 : 6 + width])
        away = TeamBox(*row[6 + width : 6 + 2 * width])
        records.append(
            TeamGameRecord(
                game_id=game_id,
                season_year=season_year,
                game_date=game_date,
                game_type=game_type,
                status=status,
                neutral_site=neutral_site,
                home=home,
                away=away,
            )
        )
    return records


_BOX_FIELDS = ("pts", "seconds_played", "fg", "fga", "fg3", "ft", "fta", "orb", "drb", "tov")


def _box_columns(box: type[TeamGameTotals]) -> list:
    return [getattr(box, field) for field in _BOX_FIELDS]
