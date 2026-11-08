"""Load the season in progress and its team-seasons from the latest snapshots (F8-014).

Only `core.seasons`, `core.team_aliases`, and `core.team_seasons` are written,
through the same repository methods as the archive. Rosters, player-seasons, and
team-season statistics change daily while a season runs, so none is loaded.

The teams are the ones the latest month snapshots list. Every page is read and
checked before the first write, and the load is one transaction: a run either
loads the whole identity or nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nba_data.db.models import Season, TeamAlias, TeamSeason
from nba_data.db.repositories import CoreRepository
from nba_data.db.repositories.games import NBA_LEAGUE, GameRepository
from nba_data.scraping.current_season_planning import (
    TEAMS_PER_SEASON,
    require_latest_month_pages,
    team_page_url,
)
from nba_data.scraping.parsers.team_season import parse_team_season_page
from nba_data.scraping.snapshot_cache import CURRENT_SEASON_END_YEAR, SnapshotCache


class CurrentSeasonLoadError(ValueError):
    """Raised when the current season cannot be loaded safely; nothing was written."""


@dataclass(frozen=True)
class CurrentSeasonIdentityReport:
    season_end_year: int
    teams: tuple[str, ...]
    seasons_created: int
    team_seasons_created: int
    team_aliases_created: int

    def to_dict(self) -> dict[str, object]:
        return {
            "season_end_year": self.season_end_year,
            "teams": list(self.teams),
            "seasons_created": self.seasons_created,
            "team_seasons_created": self.team_seasons_created,
            "team_aliases_created": self.team_aliases_created,
        }


def require_current_season(season_end_year: int) -> None:
    if season_end_year != CURRENT_SEASON_END_YEAR:
        msg = f"Season {season_end_year} is not the current season {CURRENT_SEASON_END_YEAR}"
        raise CurrentSeasonLoadError(msg)


def run_current_season_identity(
    session: Session,
    *,
    snapshots: SnapshotCache,
    season_end_year: int,
) -> CurrentSeasonIdentityReport:
    """Load the season and its team-seasons in one committed transaction."""

    require_current_season(season_end_year)
    names = _team_names(session, snapshots, season_end_year)

    repository = CoreRepository(session)
    existing_team_seasons = GameRepository(session).team_seasons(season_end_year, names)
    season_exists = GameRepository(session).season_id(season_end_year) is not None
    aliases_before = _alias_count(session, season_end_year)
    try:
        season = repository.get_or_create_season(league=NBA_LEAGUE, season_year=season_end_year)
        for code, name in names.items():
            team = repository.get_or_create_team(
                basketball_reference_team_id=code,
                current_abbreviation=code,
                current_name=name,
            )
            repository.get_or_create_team_alias(
                team=team, abbreviation=code, name=name, season_year=season_end_year
            )
            repository.get_or_create_team_season(team=team, season=season, team_abbreviation=code)
        report = CurrentSeasonIdentityReport(
            season_end_year=season_end_year,
            teams=tuple(names),
            seasons_created=0 if season_exists else 1,
            team_seasons_created=len(names) - len(existing_team_seasons),
            team_aliases_created=_alias_count(session, season_end_year) - aliases_before,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return report


def _team_names(
    session: Session,
    snapshots: SnapshotCache,
    season_end_year: int,
) -> Mapping[str, str]:
    """Each team's name from its latest page, after every page has been checked."""

    teams: set[str] = set()
    for page in require_latest_month_pages(snapshots, season_end_year).values():
        for game in page.games:
            teams.update((game.visitor_code, game.home_code))
    if len(teams) != TEAMS_PER_SEASON:
        msg = (
            f"The latest month snapshots list {len(teams)} teams, not {TEAMS_PER_SEASON}: "
            f"{sorted(teams)}"
        )
        raise CurrentSeasonLoadError(msg)

    previous = _team_codes(session, season_end_year - 1)
    unknown = sorted(teams - previous)
    if unknown:
        msg = f"Team codes not in season {season_end_year - 1}: {', '.join(unknown)}"
        raise CurrentSeasonLoadError(msg)

    names: dict[str, str] = {}
    for team in sorted(teams):
        url = team_page_url(team, season_end_year)
        snapshot = snapshots.latest(url)
        if snapshot is None:
            msg = f"No snapshot of the team page {url}"
            raise CurrentSeasonLoadError(msg)
        name = parse_team_season_page(snapshot.body).team_name
        if name is None:
            msg = f"The latest snapshot of {url} names no team"
            raise CurrentSeasonLoadError(msg)
        names[team] = name
    return names


def _team_codes(session: Session, season_year: int) -> frozenset[str]:
    statement = (
        select(TeamSeason.team_abbreviation)
        .join(Season, Season.id == TeamSeason.season_id)
        .where(Season.league == NBA_LEAGUE, Season.season_year == season_year)
    )
    return frozenset(session.scalars(statement))


def _alias_count(session: Session, season_year: int) -> int:
    statement = (
        select(func.count())
        .select_from(TeamAlias)
        .where(TeamAlias.from_season_year == season_year, TeamAlias.to_season_year == season_year)
    )
    return session.scalar(statement) or 0


__all__ = [
    "CurrentSeasonIdentityReport",
    "CurrentSeasonLoadError",
    "require_current_season",
    "run_current_season_identity",
]
