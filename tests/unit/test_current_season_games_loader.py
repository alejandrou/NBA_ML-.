"""`backfill current-season-games`: status transitions over successive snapshots.

Schedule snapshots are real-shaped HTML; each cached box score holds only its
game id and `parse_box_score_page` is replaced by a builder, so the F8-005 gates
stay covered by `test_game_loader.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, MetaData, create_engine, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import nba_data.scraping.loaders.current_season_games as games_module
from nba_data.db.models import (
    Game,
    Player,
    PlayerGameTotals,
    PlayerSeason,
    Season,
    Team,
    TeamGameTotals,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache
from nba_data.scraping.current_season_planning import CurrentSeasonPlanningError
from nba_data.scraping.game_pilot_manifest import box_score_url, league_schedule_url
from nba_data.scraping.loaders.current_season_games import (
    FIELDS_UPDATED,
    CurrentSeasonGamesReport,
    apply_schedule,
    build_game_id,
    run_current_season_games,
)
from nba_data.scraping.loaders.current_season_identity import CurrentSeasonLoadError
from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_REGULAR_SEASON,
    GAME_TYPE_UNKNOWN,
    PARTICIPATION_PLAYED,
    BoxScorePlayerLine,
    BoxScoreTeam,
    ParsedBoxScore,
)
from nba_data.scraping.parsers.league_schedule import ScheduleGame
from nba_data.scraping.snapshot_cache import SnapshotCache

SEASON = 2027
AS_OF = date(2026, 11, 1)
TABLES = (Season, Team, Player, PlayerSeason, TeamSeason, Game, TeamGameTotals, PlayerGameTotals)
CODES = ("LAL", "DEN", "BOS", "NYK", "MIA", "PHI")
MONTHS = ("october", "november")
VISITOR_POINTS = 101
HOME_POINTS = 99


@dataclass(frozen=True)
class Row:
    game_date: date
    visitor: str
    home: str
    played: bool = False
    start: str = "7:00p"
    arena: str = "Arena"
    notes: str = ""
    visitor_points: int = VISITOR_POINTS

    @property
    def game_id(self) -> str:
        return build_game_id(self.game_date, self.home)


OCT_24 = Row(date(2026, 10, 24), "LAL", "DEN")
OCT_25 = Row(date(2026, 10, 25), "BOS", "NYK")
OCT_26 = Row(date(2026, 10, 26), "MIA", "PHI")
NOV_2 = Row(date(2026, 11, 2), "BOS", "DEN")
NOV_3 = Row(date(2026, 11, 3), "LAL", "NYK")


def _row_html(row: Row) -> str:
    date_text = f"{row.game_date:%a, %b} {row.game_date.day}, {row.game_date.year}"
    box = f'<a href="/boxscores/{row.game_id}.html">Box Score</a>' if row.played else ""
    return (
        f'<tr><th data-stat="date_game" csk="{row.game_id}">{date_text}</th>'
        f'<td data-stat="game_start_time">{row.start}</td>'
        f'<td data-stat="visitor_team_name"><a href="/teams/{row.visitor}/2027.html">'
        f"{row.visitor}</a></td>"
        f'<td data-stat="visitor_pts">{row.visitor_points if row.played else ""}</td>'
        f'<td data-stat="home_team_name"><a href="/teams/{row.home}/2027.html">{row.home}</a></td>'
        f'<td data-stat="home_pts">{HOME_POINTS if row.played else ""}</td>'
        f'<td data-stat="box_score_text">{box}</td><td data-stat="overtimes"></td>'
        f'<td data-stat="attendance"></td><td data-stat="game_duration"></td>'
        f'<td data-stat="arena_name">{row.arena}</td>'
        f'<td data-stat="game_remarks">{row.notes}</td></tr>'
    )


def _schedule_page(rows: list[Row]) -> str:
    links = "".join(f'<a href="/leagues/NBA_2027_games-{month}.html">{month}</a>' for month in MONTHS)
    body = "".join(_row_html(row) for row in rows)
    return f'<html><body>{links}<table id="schedule"><tbody>{body}</tbody></table></body></html>'


class Store:
    """The two page stores, publishing a new observation of the schedule on each call."""

    def __init__(self, root: Path) -> None:
        self.snapshots = SnapshotCache(root / "snapshots")
        self.archive = HtmlCache(root / "cache")
        self.fetched_at = datetime(2026, 10, 1, tzinfo=UTC)

    def _put(self, url: str, html: str) -> None:
        self.fetched_at += timedelta(seconds=7)
        self.snapshots.write(
            url,
            html,
            CacheFetchMetadata(fetched_at=self.fetched_at, http_status=200, final_url=url),
        )

    def publish(self, october: list[Row], november: list[Row]) -> None:
        self._put(league_schedule_url(SEASON), _schedule_page(october))
        self._put(league_schedule_url(SEASON, "october"), _schedule_page(october))
        self._put(league_schedule_url(SEASON, "november"), _schedule_page(november))

    def box_score(self, *rows: Row) -> None:
        for row in rows:
            self.archive.set(box_score_url(row.game_id), row.game_id)

    def run(self, session: Session) -> CurrentSeasonGamesReport:
        return run_current_season_games(
            session,
            snapshots=self.snapshots,
            archive=self.archive,
            season_end_year=SEASON,
            as_of=AS_OF,
        )


BOX_OVERRIDES: dict[str, dict[str, object]] = {}


def _team(code: str, points: int) -> BoxScoreTeam:
    shares = [points // 5] * 5
    shares[0] += points - sum(shares)
    lines = tuple(
        BoxScorePlayerLine(
            player_id=f"{code.lower()}player{index}",
            name=f"{code} Player {index}",
            starter=True,
            participation=PARTICIPATION_PLAYED,
            seconds_played=2880,
            stats={**dict.fromkeys(COUNTING_STATS, 1), "pts": share},
            plus_minus=0,
        )
        for index, share in enumerate(shares)
    )
    totals: dict[str, int | None] = {**dict.fromkeys(COUNTING_STATS, 5), "pts": points}
    return BoxScoreTeam(
        code=code,
        name=code,
        scorebox_points=points,
        line_score=(points - 75, 25, 25, 25),
        line_score_total=points,
        totals_seconds=14400,
        totals=totals,
        players=lines,
        inactive_players=(),
    )


def _fake_parse(html: str) -> ParsedBoxScore:
    game_id = html
    visitor = next(
        row.visitor
        for row in (OCT_24, OCT_25, OCT_26, NOV_2, NOV_3)
        if row.home == game_id[-3:]
    )
    visitor = BOX_VISITORS.get(game_id, visitor)
    box = ParsedBoxScore(
        visitor=_team(visitor, VISITOR_POINTS),
        home=_team(game_id[-3:], HOME_POINTS),
        period_labels=("1", "2", "3", "4"),
        scorebox_meta=(),
        attendance=18000,
        play_by_play_linked=True,
        issues=(),
        heading="Box Score",
        game_type=GAME_TYPE_REGULAR_SEASON,
        venue=BOX_VENUES.get(game_id, "Arena, City, State"),
    )
    return replace(box, **BOX_OVERRIDES.get(game_id, {}))  # type: ignore[arg-type]


BOX_VISITORS: dict[str, str] = {NOV_2.game_id: NOV_2.visitor, NOV_3.game_id: NOV_3.visitor}
BOX_VENUES: dict[str, str] = {}


def _sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for model in TABLES:
            table = model.__table__.to_metadata(metadata)  # type: ignore[attr-defined]
            for constraint in list(table.constraints):
                if isinstance(constraint, CheckConstraint) and "~" in str(constraint.sqltext):
                    table.constraints.discard(constraint)
        metadata.create_all(connection)
    with Session(engine) as session:
        core = CoreRepository(session)
        season = core.get_or_create_season(league="NBA", season_year=SEASON)
        for code in CODES:
            team = core.get_or_create_team(
                basketball_reference_team_id=code, current_abbreviation=code
            )
            core.get_or_create_team_season(team=team, season=season, team_abbreviation=code)
        session.commit()
    return engine


@pytest.fixture(autouse=True)
def _fake_box_scores(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    BOX_OVERRIDES.clear()
    BOX_VENUES.clear()
    monkeypatch.setattr(games_module, "parse_box_score_page", _fake_parse)
    yield
    BOX_OVERRIDES.clear()
    BOX_VENUES.clear()


@pytest.fixture
def session() -> Iterator[Session]:
    engine = _sqlite_engine()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as test_session:
        yield test_session
    engine.dispose()


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path)


def _game(session: Session, row: Row) -> Game:
    session.expire_all()
    game = session.scalar(select(Game).where(Game.basketball_reference_game_id == row.game_id))
    assert game is not None
    return game


def _statuses(session: Session) -> dict[str, str]:
    session.expire_all()
    return dict(
        session.execute(select(Game.basketball_reference_game_id, Game.status)).tuples().all()
    )


def _played(row: Row, **changes: object) -> Row:
    return replace(row, played=True, **changes)  # type: ignore[arg-type]


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
def test_build_game_id_follows_the_published_rule() -> None:
    assert build_game_id(date(2026, 10, 24), "DEN") == "202610240DEN"


@pytest.mark.unit
def test_a_first_load_writes_every_game_as_scheduled_and_finished_games_as_final(
    session: Session, store: Store
) -> None:
    store.publish([_played(OCT_24), OCT_25, OCT_26], [NOV_2])
    store.box_score(OCT_24)

    report = store.run(session)

    assert not report.run_failed
    assert report.schedule_rows == 4
    assert report.transitions == {"new->scheduled": 4, "scheduled->final": 1}
    assert report.statuses == {"final": 1, "scheduled": 3}
    scheduled = _game(session, NOV_2)
    assert scheduled.game_type is None
    assert scheduled.start_time_et == time(19, 0)
    assert scheduled.venue == "Arena"
    assert scheduled.neutral_site is None
    assert report.unscored_before_as_of == [OCT_25.game_id, OCT_26.game_id]
    assert session.scalar(select(func.count()).select_from(TeamGameTotals)) == 2


@pytest.mark.unit
def test_a_rerun_on_the_same_snapshots_writes_nothing(session: Session, store: Store) -> None:
    store.publish([_played(OCT_24), OCT_25, OCT_26], [NOV_2])
    store.box_score(OCT_24)
    store.run(session)
    reports: list[CurrentSeasonGamesReport] = []

    writes = _count_writes(session, lambda: reports.append(store.run(session)))

    assert writes == 0
    assert not reports[0].transitions
    assert not reports[0].run_failed


@pytest.mark.unit
def test_a_later_refresh_finishes_three_postpones_one_and_moves_a_start_time(
    session: Session, store: Store
) -> None:
    store.publish([OCT_24, OCT_25, OCT_26], [NOV_2, NOV_3])
    store.run(session)

    moved = replace(NOV_2, start="9:30p", arena="New Arena")
    finished = [_played(OCT_24), _played(OCT_25), _played(OCT_26)]
    store.publish(finished, [moved])
    store.box_score(OCT_24, OCT_25, OCT_26)
    report = store.run(session)

    assert report.transitions == {
        "scheduled->final": 3,
        "scheduled->postponed": 1,
        FIELDS_UPDATED: 1,
    }
    assert report.statuses == {"final": 3, "postponed": 1, "scheduled": 1}
    assert _game(session, NOV_3).status == "postponed"
    updated = _game(session, NOV_2)
    assert (updated.start_time_et, updated.venue) == (time(21, 30), "New Arena")


@pytest.mark.unit
def test_a_row_marked_postponed_is_postponed_and_returns_when_unmarked(
    session: Session, store: Store
) -> None:
    store.publish([OCT_24], [NOV_2])
    store.run(session)

    store.publish([replace(OCT_24, notes="Postponed")], [NOV_2])
    assert store.run(session).transitions == {"scheduled->postponed": 1}
    assert _game(session, OCT_24).status == "postponed"

    store.publish([OCT_24], [NOV_2])
    assert store.run(session).transitions == {"postponed->scheduled": 1}
    assert _game(session, OCT_24).status == "scheduled"


@pytest.mark.unit
def test_a_postponed_game_rescheduled_under_a_new_id_keeps_the_old_row(
    session: Session, store: Store
) -> None:
    store.publish([OCT_24], [NOV_2])
    store.run(session)

    rescheduled = replace(OCT_24, game_date=date(2026, 11, 20))
    store.publish([OCT_25], [NOV_2, rescheduled])
    report = store.run(session)

    assert report.transitions == {"new->scheduled": 2, "scheduled->postponed": 1}
    assert _game(session, OCT_24).status == "postponed"
    assert _game(session, rescheduled).status == "scheduled"
    # A second pass over the same listing leaves the postponed row alone.
    assert not store.run(session).transitions


@pytest.mark.unit
def test_a_conflicting_change_to_a_final_row_fails_the_run_and_writes_nothing(
    session: Session, store: Store
) -> None:
    store.publish([_played(OCT_24), OCT_25], [NOV_2])
    store.box_score(OCT_24)
    store.run(session)

    store.publish(
        [_played(OCT_24, visitor_points=120), replace(OCT_25, start="9:00p")], [NOV_2, NOV_3]
    )
    report = store.run(session)

    assert report.run_failed
    assert list(report.conflicts) == [OCT_24.game_id]
    assert "score" in report.conflicts[OCT_24.game_id][0]
    assert not report.transitions
    assert _game(session, OCT_25).start_time_et == time(19, 0)
    assert NOV_3.game_id not in _statuses(session)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("october", "reason"),
    [
        ([OCT_25], "no longer listed"),
        ([OCT_24, OCT_25], "no score"),
        ([_played(OCT_24, start="9:00p"), OCT_25], "start_time_et"),
        ([_played(OCT_24, arena="Other Arena"), OCT_25], "venue"),
        ([_played(OCT_24, arena="Aren"), OCT_25], "venue"),
    ],
)
def test_a_final_row_that_loses_its_listing_score_time_or_venue_is_a_conflict(
    session: Session, store: Store, october: list[Row], reason: str
) -> None:
    store.publish([_played(OCT_24), OCT_25], [NOV_2])
    store.box_score(OCT_24)
    store.run(session)

    store.publish(october, [NOV_2])
    report = store.run(session)

    assert report.run_failed
    assert reason in report.conflicts[OCT_24.game_id][0]
    assert _game(session, OCT_24).status == "final"


@pytest.mark.unit
def test_a_changed_team_on_a_scheduled_row_is_a_conflict(session: Session, store: Store) -> None:
    store.publish([OCT_24], [NOV_2])
    store.run(session)

    store.publish([replace(OCT_24, visitor="BOS")], [NOV_2])
    report = store.run(session)

    assert report.conflicts == {OCT_24.game_id: ["away team differs"]}


@pytest.mark.unit
def test_a_scored_row_without_a_box_score_stays_scheduled_and_is_reported(
    session: Session, store: Store
) -> None:
    store.publish([_played(OCT_24), OCT_25], [NOV_2])

    report = store.run(session)

    assert not report.run_failed
    assert report.missing_box_score == [OCT_24.game_id]
    assert _game(session, OCT_24).status == "scheduled"
    assert session.scalar(select(func.count()).select_from(TeamGameTotals)) == 0


@pytest.mark.unit
def test_a_quarantined_box_score_stays_scheduled_and_fails_the_run(
    session: Session, store: Store
) -> None:
    store.publish([_played(OCT_24), _played(OCT_25)], [NOV_2])
    store.box_score(OCT_24, OCT_25)
    BOX_OVERRIDES[OCT_24.game_id] = {"game_type": GAME_TYPE_UNKNOWN}

    report = store.run(session)

    assert report.run_failed
    assert report.quarantined[OCT_24.game_id][0]["code"] == "unknown_game_type"
    assert _game(session, OCT_24).status == "scheduled"
    assert _game(session, OCT_25).status == "final"
    assert report.transitions["scheduled->final"] == 1


@pytest.mark.unit
def test_a_neutral_site_cup_game_keeps_neutral_site_undetermined(
    session: Session, store: Store
) -> None:
    cup = replace(NOV_2, arena="T-Mobile Arena", notes="NBA Cup")
    store.publish([OCT_24], [cup])
    store.run(session)
    assert _game(session, cup).neutral_site is None

    store.publish([OCT_24], [_played(cup)])
    store.box_score(cup)
    BOX_VENUES[cup.game_id] = "T-Mobile Arena, Las Vegas, Nevada"
    report = store.run(session)

    assert report.transitions == {"scheduled->final": 1}
    game = _game(session, cup)
    assert game.status == "final"
    assert game.venue == "T-Mobile Arena, Las Vegas, Nevada"
    assert game.neutral_site is None


@pytest.mark.unit
def test_a_played_row_whose_link_differs_from_the_built_id_fails_the_run(
    session: Session, store: Store
) -> None:
    row = ScheduleGame(
        game_date=date(2026, 10, 24),
        visitor_code="LAL",
        visitor_name="LAL",
        home_code="DEN",
        home_name="DEN",
        game_id="202610250DEN",
        visitor_points=VISITOR_POINTS,
        home_points=HOME_POINTS,
    )

    with pytest.raises(CurrentSeasonLoadError, match="differs from the built game id"):
        apply_schedule(session, (row,), archive=store.archive, season_end_year=SEASON, as_of=AS_OF)

    assert not _statuses(session)


@pytest.mark.unit
def test_a_month_without_a_snapshot_refuses_the_run_rather_than_postponing_its_games(
    session: Session, store: Store
) -> None:
    store.publish([OCT_24], [NOV_2])
    store.run(session)
    fresh = Store(store.snapshots.root_dir.parent / "fresh")
    fresh._put(league_schedule_url(SEASON), _schedule_page([OCT_24]))
    fresh._put(league_schedule_url(SEASON, "october"), _schedule_page([OCT_24]))

    with pytest.raises(CurrentSeasonPlanningError, match="No snapshot of the november"):
        fresh.run(session)

    assert _game(session, NOV_2).status == "scheduled"


@pytest.mark.unit
def test_a_month_dropped_from_the_season_page_refuses_the_run_rather_than_postponing(
    session: Session, store: Store
) -> None:
    store.publish([OCT_24], [NOV_2])
    store.run(session)
    only_october = _schedule_page([OCT_24]).replace(
        '<a href="/leagues/NBA_2027_games-november.html">november</a>', ""
    )
    store._put(league_schedule_url(SEASON), only_october)

    with pytest.raises(CurrentSeasonLoadError, match="stored months: 2026-11"):
        store.run(session)

    assert _game(session, NOV_2).status == "scheduled"


@pytest.mark.unit
def test_a_month_page_with_no_games_refuses_the_run(session: Session, store: Store) -> None:
    store.publish([OCT_24], [NOV_2])
    store.run(session)

    store.publish([OCT_24], [])
    with pytest.raises(CurrentSeasonPlanningError, match="lists no games"):
        store.run(session)

    assert _game(session, NOV_2).status == "scheduled"


@pytest.mark.unit
def test_an_unreadable_start_time_refuses_the_run(session: Session, store: Store) -> None:
    store.publish([replace(OCT_24, start="noon")], [NOV_2])

    with pytest.raises(CurrentSeasonLoadError, match="unreadable start time"):
        store.run(session)

    assert not _statuses(session)


@pytest.mark.unit
def test_refuses_a_schedule_before_the_identity_is_loaded(store: Store) -> None:
    engine = _sqlite_engine()
    with Session(engine) as session:
        session.execute(TeamSeason.__table__.delete())  # type: ignore[attr-defined]
        session.commit()
        store.publish([OCT_24], [NOV_2])

        with pytest.raises(CurrentSeasonLoadError, match="No 2027 team-season"):
            store.run(session)
    engine.dispose()


@pytest.mark.unit
def test_refuses_another_season_and_an_as_of_outside_the_season(
    session: Session, store: Store
) -> None:
    with pytest.raises(CurrentSeasonLoadError, match="not the current season"):
        run_current_season_games(
            session,
            snapshots=store.snapshots,
            archive=store.archive,
            season_end_year=2026,
            as_of=AS_OF,
        )
    with pytest.raises(CurrentSeasonPlanningError, match="outside the 2027 season"):
        run_current_season_games(
            session,
            snapshots=store.snapshots,
            archive=store.archive,
            season_end_year=SEASON,
            as_of=date(2026, 7, 1),
        )


@pytest.mark.unit
def test_a_game_of_the_archive_is_never_touched(session: Session, store: Store) -> None:
    core = CoreRepository(session)
    archive_season = core.get_or_create_season(league="NBA", season_year=2026)
    teams = {
        code: core.get_or_create_team_season(
            team=core.get_or_create_team(
                basketball_reference_team_id=code, current_abbreviation=code
            ),
            season=archive_season,
            team_abbreviation=code,
        )
        for code in ("LAL", "DEN")
    }
    session.add(
        Game(
            basketball_reference_game_id="202604010DEN",
            season_id=archive_season.id,
            home_team_season_id=teams["DEN"].id,
            away_team_season_id=teams["LAL"].id,
            game_date=date(2026, 4, 1),
            status="scheduled",
        )
    )
    session.commit()

    store.publish([OCT_24], [NOV_2])
    store.run(session)

    assert _statuses(session)["202604010DEN"] == "scheduled"
