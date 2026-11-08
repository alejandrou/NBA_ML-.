"""`backfill current-season-identity`: the season and its team-seasons, and nothing else."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import MetaData, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import CacheFetchMetadata
from nba_data.scraping.current_season_planning import (
    CurrentSeasonPlanningError,
    team_page_url,
)
from nba_data.scraping.game_pilot_manifest import league_schedule_url
from nba_data.scraping.loaders.current_season_identity import (
    CurrentSeasonLoadError,
    run_current_season_identity,
)
from nba_data.scraping.snapshot_cache import SnapshotCache

TEAMS = tuple(f"T{chr(65 + index // 26)}{chr(65 + index % 26)}" for index in range(30))
TABLES = (Season, Team, TeamAlias, TeamSeason, Player, PlayerSeason, PlayerTeamSeason)


class Snapshots:
    def __init__(self, root: Path) -> None:
        self.cache = SnapshotCache(root)
        self.fetched_at = datetime(2026, 10, 1, tzinfo=UTC)

    def put(self, url: str, html: str) -> None:
        self.fetched_at += timedelta(seconds=7)
        self.cache.write(
            url,
            html,
            CacheFetchMetadata(fetched_at=self.fetched_at, http_status=200, final_url=url),
        )


def _team_page(name: str = "Some Team") -> str:
    return (
        f"<html><body><h1><span>2026-27</span><span>{name}</span><span>Roster</span></h1>"
        '<table id="roster"><thead><tr><th data-stat="player">Player</th></tr></thead><tbody>'
        '<tr><td data-stat="player"><a href="/players/a/rosterpl01.html">Roster Player</a></td>'
        "</tr></tbody></table></body></html>"
    )


def _schedule_page(teams: tuple[str, ...]) -> str:
    rows = "".join(
        f'<tr><th data-stat="date_game">Fri, Oct 23, 2026</th>'
        f'<td data-stat="visitor_team_name"><a href="/teams/{teams[i]}/2027.html">V</a></td>'
        f'<td data-stat="home_team_name"><a href="/teams/{teams[i + 1]}/2027.html">H</a></td></tr>'
        for i in range(0, len(teams) - 1, 2)
    )
    return (
        '<html><body><a href="/leagues/NBA_2027_games-october.html">October</a>'
        f'<table id="schedule"><tbody>{rows}</tbody></table></body></html>'
    )


def _seed_snapshots(root: Path, teams: tuple[str, ...] = TEAMS) -> Snapshots:
    snapshots = Snapshots(root)
    snapshots.put(league_schedule_url(2027), _schedule_page(teams))
    snapshots.put(league_schedule_url(2027, "october"), _schedule_page(teams))
    for team in teams:
        snapshots.put(team_page_url(team, 2027), _team_page(f"{team} Name"))
    return snapshots


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        for model in TABLES:
            model.__table__.to_metadata(metadata)  # type: ignore[attr-defined]
        metadata.create_all(connection)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as test_session:
        core = CoreRepository(test_session)
        season = core.get_or_create_season(league="NBA", season_year=2026)
        for code in TEAMS:
            team = core.get_or_create_team(
                basketball_reference_team_id=code,
                current_abbreviation=code,
                current_name=f"{code} Name",
            )
            core.get_or_create_team_season(team=team, season=season, team_abbreviation=code)
        test_session.commit()
        yield test_session
    engine.dispose()


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _season_2027(session: Session) -> Season | None:
    return session.scalar(select(Season).where(Season.season_year == 2027))


def _count_writes(session: Session, action: Callable[[], object]) -> int:
    """How many INSERT, UPDATE, or DELETE statements `action` sends."""

    statements: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            statements.append(statement)

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        action()
    finally:
        event.remove(bind, "before_cursor_execute", record)
    return len(statements)


@pytest.mark.unit
def test_loads_the_season_and_30_team_seasons_without_any_roster(
    session: Session, tmp_path: Path
) -> None:
    snapshots = _seed_snapshots(tmp_path)

    report = run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)

    assert report.seasons_created == 1
    assert report.team_seasons_created == 30
    assert report.team_aliases_created == 30
    assert report.teams == TEAMS
    assert _season_2027(session) is not None
    assert _count(session, TeamSeason) == 60
    assert _count(session, Team) == 30
    assert _count(session, Player) == 0
    assert _count(session, PlayerSeason) == 0
    assert _count(session, PlayerTeamSeason) == 0


@pytest.mark.unit
def test_a_rerun_writes_nothing(session: Session, tmp_path: Path) -> None:
    snapshots = _seed_snapshots(tmp_path)
    run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)
    reports = []

    writes = _count_writes(
        session,
        lambda: reports.append(
            run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)
        ),
    )

    assert writes == 0
    report = reports[0]
    assert (report.seasons_created, report.team_seasons_created, report.team_aliases_created) == (
        0,
        0,
        0,
    )


@pytest.mark.unit
def test_refuses_a_season_other_than_the_current_one(session: Session, tmp_path: Path) -> None:
    snapshots = _seed_snapshots(tmp_path)

    with pytest.raises(CurrentSeasonLoadError, match="not the current season"):
        run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2026)


@pytest.mark.unit
def test_refuses_a_team_code_absent_from_the_previous_season(
    session: Session, tmp_path: Path
) -> None:
    teams = (*TEAMS[:-1], "NEW")
    snapshots = _seed_snapshots(tmp_path, teams)

    with pytest.raises(CurrentSeasonLoadError, match="not in season 2026: NEW"):
        run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)

    assert _season_2027(session) is None


@pytest.mark.unit
def test_refuses_a_schedule_listing_other_than_30_teams(session: Session, tmp_path: Path) -> None:
    snapshots = _seed_snapshots(tmp_path, TEAMS[:28])

    with pytest.raises(CurrentSeasonLoadError, match="list 28 teams"):
        run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)

    assert _season_2027(session) is None


@pytest.mark.unit
def test_a_missing_team_page_writes_nothing(session: Session, tmp_path: Path) -> None:
    snapshots = Snapshots(tmp_path)
    snapshots.put(league_schedule_url(2027), _schedule_page(TEAMS))
    snapshots.put(league_schedule_url(2027, "october"), _schedule_page(TEAMS))
    for team in TEAMS[:-1]:
        snapshots.put(team_page_url(team, 2027), _team_page())

    with pytest.raises(CurrentSeasonLoadError, match="No snapshot of the team page"):
        run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)

    assert _season_2027(session) is None


@pytest.mark.unit
def test_a_team_page_without_a_name_writes_nothing(session: Session, tmp_path: Path) -> None:
    snapshots = _seed_snapshots(tmp_path)
    snapshots.put(team_page_url(TEAMS[0], 2027), "<html><body>Rate limited</body></html>")

    with pytest.raises(CurrentSeasonLoadError, match="names no team"):
        run_current_season_identity(session, snapshots=snapshots.cache, season_end_year=2027)

    assert _season_2027(session) is None


@pytest.mark.unit
def test_refuses_before_the_first_season_snapshot(session: Session, tmp_path: Path) -> None:
    with pytest.raises(CurrentSeasonPlanningError, match="No snapshot of the season page"):
        run_current_season_identity(
            session, snapshots=SnapshotCache(tmp_path), season_end_year=2027
        )

    assert _season_2027(session) is None
