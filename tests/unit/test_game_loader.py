"""`load_game` gates, writes, and reruns a finished game; `neutral_sites` decides venues.

The parsed pages are built here, not parsed, so each gate is broken on purpose
and nothing else. SQLite stands in for PostgreSQL; the PostgreSQL-only regular
expression checks are left out of its tables, and
`tests/integration/test_game_loader_postgres.py` loads real fixture pages into
PostgreSQL with every constraint in force.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date, time

import pytest
from sqlalchemy import CheckConstraint, MetaData, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

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
from nba_data.db.repositories.games import FinalGameVenue
from nba_data.db.repositories.queries.game_identities import load_game_identity_keys
from nba_data.scraping.loaders.games import (
    QUARANTINE_BOX_SCORE_UNREADABLE,
    QUARANTINE_DUPLICATE_PLAYER,
    QUARANTINE_MISSING_TEAM_SEASON,
    QUARANTINE_MISSING_TEAM_TOTALS,
    QUARANTINE_PLAYED_WITHOUT_SECONDS,
    QUARANTINE_PLAYER_SUM_MISMATCH,
    QUARANTINE_SCORE_MISMATCH,
    QUARANTINE_TEAM_MISMATCH,
    QUARANTINE_TIED_SCORE,
    QUARANTINE_UNKNOWN_GAME_TYPE,
    QUARANTINE_UNKNOWN_PARTICIPATION,
    QUARANTINE_UNNAMED_PLAYER,
    QUARANTINE_UNREADABLE_START_TIME,
    WARNING_CUP_FINAL_PLUS_MINUS_ZEROS,
    WARNING_HOME_CITY_TIED,
    WARNING_LINE_SCORE_DISAGREES,
    WARNING_LINE_SCORE_UNREADABLE,
    GameLineage,
    derive_neutral_sites,
    load_game,
    neutral_sites,
    parse_start_time,
    venue_city,
)
from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_CUP_FINAL,
    GAME_TYPE_PLAYOFFS,
    GAME_TYPE_REGULAR_SEASON,
    GAME_TYPE_UNKNOWN,
    PARTICIPATION_DID_NOT_PLAY,
    PARTICIPATION_OTHER_ABSENCE,
    PARTICIPATION_PLAYED,
    BoxScorePlayerLine,
    BoxScoreTeam,
    InactivePlayer,
    ParsedBoxScore,
)
from nba_data.scraping.parsers.league_schedule import ScheduleGame
from nba_data.validation.team_season import DataQualityIssue

SEASON = 2024
GAME_ID = "202401100DEN"
LINEAGE = GameLineage(
    source_url=f"https://www.basketball-reference.com/boxscores/{GAME_ID}.html",
    cache_path=f"cache/basketball-reference/boxscores-{GAME_ID}.html.gz",
    parser_version="box-score-parser-v2",
)
TABLES = (Season, Team, Player, PlayerSeason, TeamSeason, Game, TeamGameTotals, PlayerGameTotals)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for model in TABLES:
            table = model.__table__.to_metadata(metadata)  # type: ignore[attr-defined]
            # SQLite cannot evaluate PostgreSQL's `~` regular expression checks.
            for constraint in list(table.constraints):
                if isinstance(constraint, CheckConstraint) and "~" in str(constraint.sqltext):
                    table.constraints.discard(constraint)
        metadata.create_all(connection)

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as test_session:
        _seed_team_seasons(test_session, SEASON, ("BOS", "DEN", "LAL", "LAC"))
        test_session.commit()
        yield test_session
    engine.dispose()


# --- builders -----------------------------------------------------------------


def _line(
    player_id: str,
    pts: int,
    *,
    starter: bool = True,
    seconds: int | None = 2880,
    plus_minus: int | None = 0,
    name: str | None = None,
) -> BoxScorePlayerLine:
    stats: dict[str, int | None] = dict.fromkeys(COUNTING_STATS, 1)
    stats["pts"] = pts
    return BoxScorePlayerLine(
        player_id=player_id,
        name=name if name is not None else player_id.title(),
        starter=starter,
        participation=PARTICIPATION_PLAYED,
        seconds_played=seconds,
        stats=stats,
        plus_minus=plus_minus,
    )


def _dnp(player_id: str, reason: str = "Did Not Play") -> BoxScorePlayerLine:
    return BoxScorePlayerLine(
        player_id=player_id,
        name=player_id.title(),
        starter=False,
        participation=PARTICIPATION_DID_NOT_PLAY,
        reason=reason,
    )


def _team(
    code: str,
    points: int,
    *,
    team_turnovers: int = 1,
    inactive: tuple[InactivePlayer, ...] = (),
    extra: tuple[BoxScorePlayerLine, ...] = (),
    plus_minus: int = 0,
) -> BoxScoreTeam:
    """Five starters whose lines add up to the team totals, team turnovers apart."""

    shares = [points // 5] * 5
    shares[0] += points - sum(shares)
    lines = tuple(
        _line(f"{code.lower()}player{index}", share, plus_minus=plus_minus)
        for index, share in enumerate(shares)
    )
    players = lines + extra
    totals: dict[str, int | None] = {
        stat: sum((line.stats.get(stat) or 0) for line in players if line.stats)
        for stat in COUNTING_STATS
    }
    totals["tov"] = (totals["tov"] or 0) + team_turnovers
    quarters = [points // 4] * 4
    quarters[0] += points - sum(quarters)
    return BoxScoreTeam(
        code=code,
        name=f"{code} Team",
        scorebox_points=points,
        line_score=tuple(quarters),
        line_score_total=points,
        totals_seconds=14400,
        totals=totals,
        players=players,
        inactive_players=inactive,
    )


def _box(**changes: object) -> ParsedBoxScore:
    box = ParsedBoxScore(
        visitor=_team("BOS", 101),
        home=_team("DEN", 110),
        period_labels=("1", "2", "3", "4"),
        scorebox_meta=(),
        attendance=19520,
        play_by_play_linked=True,
        issues=(),
        heading="Boston Celtics at Denver Nuggets Box Score, January 10, 2024",
        game_type=GAME_TYPE_REGULAR_SEASON,
        venue="Ball Arena, Denver, Colorado",
    )
    return replace(box, **changes)  # type: ignore[arg-type]


def _schedule(**changes: object) -> ScheduleGame:
    game = ScheduleGame(
        game_date=date(2024, 1, 10),
        visitor_code="BOS",
        visitor_name="Boston Celtics",
        home_code="DEN",
        home_name="Denver Nuggets",
        game_id=GAME_ID,
        visitor_points=101,
        home_points=110,
        start_time="7:30p",
        attendance=19520,
        arena="Ball Arena",
    )
    return replace(game, **changes)  # type: ignore[arg-type]


def _seed_team_seasons(session: Session, season_year: int, codes: tuple[str, ...]) -> None:
    core = CoreRepository(session)
    season = core.get_or_create_season(league="NBA", season_year=season_year)
    for code in codes:
        team = core.get_or_create_team(basketball_reference_team_id=code, current_abbreviation=code)
        core.get_or_create_team_season(team=team, season=season, team_abbreviation=code)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _load(
    session: Session, schedule: ScheduleGame | None = None, box: ParsedBoxScore | None = None
):  # type: ignore[no-untyped-def]
    return load_game(
        session,
        schedule if schedule is not None else _schedule(),
        box if box is not None else _box(),
        LINEAGE,
        season_end_year=SEASON,
    )


def _rows_by_player(session: Session) -> dict[str, PlayerGameTotals]:
    rows = session.execute(
        select(Player.basketball_reference_player_id, PlayerGameTotals).join(
            Player, Player.id == PlayerGameTotals.player_id
        )
    ).all()
    return {bref_id: row for bref_id, row in rows}


# --- writes -------------------------------------------------------------------


@pytest.mark.unit
def test_a_finished_game_writes_the_game_both_totals_and_every_line(session: Session) -> None:
    box = _box(
        visitor=_team(
            "BOS",
            101,
            extra=(_dnp("bosbench01"),),
            inactive=(InactivePlayer("youngpa01", "Patric Young"),),
        )
    )

    result = _load(session, box=box)

    assert result.status == "loaded"
    assert result.quarantine == ()
    game = session.scalar(select(Game))
    assert game is not None
    assert game.basketball_reference_game_id == GAME_ID
    assert game.game_date == date(2024, 1, 10)
    assert game.start_time_et == time(19, 30)
    assert game.game_type == GAME_TYPE_REGULAR_SEASON
    assert game.status == "final"
    assert game.venue == "Ball Arena, Denver, Colorado"
    assert game.attendance == 19520
    assert game.neutral_site is None

    totals = {row.is_home: row for row in session.scalars(select(TeamGameTotals))}
    assert (totals[False].pts, totals[True].pts) == (101, 110)
    assert totals[False].tov == 6  # five player turnovers and one team turnover
    assert totals[True].seconds_played == 14400
    assert totals[True].source_url == LINEAGE.source_url
    assert totals[True].cache_path == LINEAGE.cache_path
    assert totals[True].parser_version == "box-score-parser-v2"

    rows = _rows_by_player(session)
    assert len(rows) == 5 + 5 + 1 + 1
    assert rows["bosplayer0"].participation == PARTICIPATION_PLAYED
    assert rows["bosplayer0"].seconds_played == 2880
    assert rows["bosplayer0"].plus_minus == 0
    bench = rows["bosbench01"]
    assert (bench.participation, bench.participation_reason) == ("did_not_play", "Did Not Play")
    assert bench.starter is False and bench.seconds_played is None and bench.pts is None
    inactive = rows["youngpa01"]
    assert (inactive.participation, inactive.participation_reason) == ("inactive", "Inactive")
    assert inactive.pts is None and inactive.seconds_played is None and inactive.plus_minus is None
    assert inactive.team_season_id == totals[False].team_season_id
    assert inactive.parser_version == "box-score-parser-v2"


@pytest.mark.unit
def test_a_rerun_of_the_same_pages_is_unchanged_and_writes_nothing(session: Session) -> None:
    first = _load(session)
    session.commit()
    stamps = sorted(row.updated_at for row in session.scalars(select(PlayerGameTotals)))

    second = _load(session)

    assert first.status == "loaded"
    assert second.status == "unchanged"
    assert second.players_created == ()
    assert not session.dirty and not session.new and not session.deleted
    assert _count(session, Game) == 1
    assert _count(session, TeamGameTotals) == 2
    assert _count(session, PlayerGameTotals) == 10
    assert sorted(row.updated_at for row in session.scalars(select(PlayerGameTotals))) == stamps


@pytest.mark.unit
def test_a_corrected_page_updates_in_place_and_drops_a_line_it_no_longer_lists(
    session: Session,
) -> None:
    _load(session, box=_box(visitor=_team("BOS", 101, extra=(_dnp("bosbench01"),))))
    session.commit()

    result = _load(session, box=_box(attendance=0))

    assert result.status == "loaded"
    game = session.scalar(select(Game))
    assert game is not None and game.attendance == 0
    assert _count(session, Game) == 1
    assert "bosbench01" not in _rows_by_player(session)


@pytest.mark.unit
@pytest.mark.parametrize(("published", "stored"), [(None, None), (0, 0), (17000, 17000)])
def test_blank_attendance_is_null_and_zero_is_zero(
    session: Session, published: int | None, stored: int | None
) -> None:
    _load(session, box=_box(attendance=published))

    game = session.scalar(select(Game))
    assert game is not None and game.attendance == stored


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7:30p", time(19, 30)),
        ("12:00p", time(12, 0)),
        ("12:30a", time(0, 30)),
        ("1:00 pm", time(13, 0)),
        ("9:05a", time(9, 5)),
        ("", None),
        (None, None),
    ],
)
def test_start_times_are_read_as_published_eastern(text: str | None, expected: time | None) -> None:
    assert parse_start_time(text) == expected


@pytest.mark.unit
@pytest.mark.parametrize("text", ["7:30", "19:30p", "noon", "7:3p", "0:30p"])
def test_an_unreadable_start_time_is_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="unreadable start time"):
        parse_start_time(text)


@pytest.mark.unit
def test_a_blank_start_time_loads_as_null(session: Session) -> None:
    _load(session, schedule=_schedule(start_time=None))

    game = session.scalar(select(Game))
    assert game is not None and game.start_time_et is None


@pytest.mark.unit
@pytest.mark.parametrize("game_type", [GAME_TYPE_PLAYOFFS, GAME_TYPE_CUP_FINAL])
def test_the_heading_sets_the_stored_game_type(session: Session, game_type: str) -> None:
    result = _load(session, box=_box(game_type=game_type))

    assert result.status == "loaded" and result.game_type == game_type
    game = session.scalar(select(Game))
    assert game is not None and game.game_type == game_type


# --- players ------------------------------------------------------------------


@pytest.mark.unit
def test_missing_players_are_created_from_box_score_links_without_a_player_season(
    session: Session,
) -> None:
    CoreRepository(session).get_or_create_player(
        basketball_reference_player_id="bosplayer0", full_name="Known Name"
    )
    session.commit()
    box = _box(visitor=_team("BOS", 101, inactive=(InactivePlayer("sorbeth01", "Thomas Sorber"),)))

    result = _load(session, box=box)

    assert "sorbeth01" in result.players_created
    assert "bosplayer0" not in result.players_created
    assert len(result.players_created) == 10  # nine new lined players and one inactive
    names = dict(
        session.execute(select(Player.basketball_reference_player_id, Player.full_name)).all()
    )
    assert names["sorbeth01"] == "Thomas Sorber"
    assert names["bosplayer0"] == "Known Name"  # an existing player is never renamed
    assert _count(session, PlayerSeason) == 0


@pytest.mark.unit
def test_a_rerun_creates_no_player_twice(session: Session) -> None:
    _load(session)
    session.commit()
    players = _count(session, Player)

    result = _load(session)

    assert result.players_created == ()
    assert _count(session, Player) == players


@pytest.mark.unit
def test_database_identity_keys_include_inactive_only_players_without_player_pages(
    session: Session,
) -> None:
    _load(session, box=_box(visitor=_team(
        "BOS", 101, inactive=(InactivePlayer("youngpa01", "Patric Young"),),
    )))
    session.commit()
    players, teams = load_game_identity_keys(session)
    assert "youngpa01" in players
    assert ("BOS", SEASON) in teams and ("DEN", SEASON) in teams
    assert _count(session, PlayerSeason) == 0
    assert not session.dirty and not session.new


# --- gates --------------------------------------------------------------------


def _short_tov_team() -> BoxScoreTeam:
    team = _team("BOS", 101, team_turnovers=0)
    return replace(team, totals={**team.totals, "tov": (team.totals["tov"] or 0) - 1})


def _ast_off_team() -> BoxScoreTeam:
    team = _team("BOS", 101)
    return replace(team, totals={**team.totals, "ast": (team.totals["ast"] or 0) + 1})


def _blank_counter_team() -> BoxScoreTeam:
    team = _team("BOS", 101)
    first = replace(team.players[0], stats={**team.players[0].stats, "stl": None})
    return replace(team, players=(first, *team.players[1:]))


GATE_CASES = [
    ("unknown heading", None, {"game_type": GAME_TYPE_UNKNOWN}, QUARANTINE_UNKNOWN_GAME_TYPE),
    (
        "schedule names another visitor",
        {"visitor_code": "LAL"},
        {},
        QUARANTINE_TEAM_MISMATCH,
    ),
    ("no scorebox teams", None, {"visitor": None}, QUARANTINE_TEAM_MISMATCH),
    ("schedule score differs", {"visitor_points": 99}, {}, QUARANTINE_SCORE_MISMATCH),
    ("schedule score blank", {"home_points": None}, {}, QUARANTINE_SCORE_MISMATCH),
    (
        "scorebox differs from totals",
        None,
        {"home": replace(_team("DEN", 110), scorebox_points=111)},
        QUARANTINE_SCORE_MISMATCH,
    ),
    (
        "tied",
        {"visitor_points": 110},
        {"visitor": _team("BOS", 110)},
        QUARANTINE_TIED_SCORE,
    ),
    (
        "no team minutes",
        None,
        {"home": replace(_team("DEN", 110), totals_seconds=None)},
        QUARANTINE_MISSING_TEAM_TOTALS,
    ),
    (
        "no team points",
        None,
        {"home": replace(_team("DEN", 110), totals={})},
        QUARANTINE_MISSING_TEAM_TOTALS,
    ),
    (
        "a counter that does not sum",
        None,
        {"visitor": _ast_off_team()},
        QUARANTINE_PLAYER_SUM_MISMATCH,
    ),
    (
        "turnovers short of the lines",
        None,
        {"visitor": _short_tov_team()},
        QUARANTINE_PLAYER_SUM_MISMATCH,
    ),
    ("a blank counter", None, {"visitor": _blank_counter_team()}, QUARANTINE_PLAYER_SUM_MISMATCH),
    (
        "an unrecognized participation",
        None,
        {
            "visitor": _team(
                "BOS",
                101,
                extra=(replace(_dnp("bosbench01"), participation="benched"),),
            )
        },
        QUARANTINE_UNKNOWN_PARTICIPATION,
    ),
    (
        "an absence with no reason",
        None,
        {
            "visitor": _team(
                "BOS",
                101,
                extra=(replace(_dnp("bosbench01", ""), participation=PARTICIPATION_OTHER_ABSENCE),),
            )
        },
        QUARANTINE_UNKNOWN_PARTICIPATION,
    ),
    (
        "played without seconds",
        None,
        {
            "visitor": _team(
                "BOS", 101, extra=(_line("bosbench01", 0, starter=False, seconds=None),)
            )
        },
        QUARANTINE_PLAYED_WITHOUT_SECONDS,
    ),
    (
        "a player listed twice",
        None,
        {"visitor": _team("BOS", 101, inactive=(InactivePlayer("bosplayer1", "Bos Player One"),))},
        QUARANTINE_DUPLICATE_PLAYER,
    ),
    (
        "a new player with no name",
        None,
        {"visitor": _team("BOS", 101, inactive=(InactivePlayer("nonameyy01", ""),))},
        QUARANTINE_UNNAMED_PLAYER,
    ),
    ("a malformed start time", {"start_time": "7:30"}, {}, QUARANTINE_UNREADABLE_START_TIME),
    (
        "an unreadable player row",
        None,
        {"issues": (DataQualityIssue(code="player_row_unreadable", message="x"),)},
        QUARANTINE_BOX_SCORE_UNREADABLE,
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("schedule_changes", "box_changes", "reason"),
    [case[1:] for case in GATE_CASES],
    ids=[case[0] for case in GATE_CASES],
)
def test_each_gate_quarantines_and_writes_nothing(
    session: Session,
    schedule_changes: dict[str, object] | None,
    box_changes: dict[str, object],
    reason: str,
) -> None:
    players = _count(session, Player)

    result = _load(session, schedule=_schedule(**(schedule_changes or {})), box=_box(**box_changes))

    assert result.status == "quarantined"
    assert reason in {issue.code for issue in result.quarantine}
    assert all(issue.detail for issue in result.quarantine)
    assert _count(session, Game) == 0
    assert _count(session, TeamGameTotals) == 0
    assert _count(session, PlayerGameTotals) == 0
    assert _count(session, Player) == players
    assert not session.new and not session.dirty


@pytest.mark.unit
def test_a_team_season_missing_from_core_is_quarantined(session: Session) -> None:
    schedule = _schedule(visitor_code="NYK")
    box = _box(visitor=_team("NYK", 101))

    result = _load(session, schedule=schedule, box=box)

    assert result.status == "quarantined"
    assert [issue.code for issue in result.quarantine] == [QUARANTINE_MISSING_TEAM_SEASON]
    assert "NYK 2024" in result.quarantine[0].detail
    assert _count(session, Game) == 0


@pytest.mark.unit
def test_a_season_missing_from_core_is_quarantined_not_created(session: Session) -> None:
    result = load_game(session, _schedule(), _box(), LINEAGE, season_end_year=2031)

    assert {issue.code for issue in result.quarantine} == {QUARANTINE_MISSING_TEAM_SEASON}
    assert _count(session, Season) == 1


@pytest.mark.unit
def test_team_turnovers_beyond_the_player_lines_are_allowed(session: Session) -> None:
    result = _load(session, box=_box(visitor=_team("BOS", 101, team_turnovers=3)))

    assert result.status == "loaded"


@pytest.mark.unit
def test_every_failed_gate_is_reported_not_only_the_first(session: Session) -> None:
    result = _load(
        session,
        schedule=_schedule(visitor_points=50, start_time="soon"),
        box=_box(game_type=GAME_TYPE_UNKNOWN),
    )

    assert {issue.code for issue in result.quarantine} == {
        QUARANTINE_UNKNOWN_GAME_TYPE,
        QUARANTINE_SCORE_MISMATCH,
        QUARANTINE_UNREADABLE_START_TIME,
    }


# --- warnings -----------------------------------------------------------------


@pytest.mark.unit
def test_a_line_score_that_disagrees_is_a_warning_not_a_quarantine(session: Session) -> None:
    home = _team("DEN", 110)
    home = replace(home, line_score=(30, 20, 30, 30))  # sums to 110, but the quarters differ

    wrong_total = replace(_team("BOS", 101), line_score_total=100)
    result = _load(session, box=_box(visitor=wrong_total, home=home))

    assert result.status == "loaded"
    assert [issue.code for issue in result.warnings] == [WARNING_LINE_SCORE_DISAGREES]
    assert "BOS" in result.warnings[0].detail


@pytest.mark.unit
def test_an_unreadable_line_score_is_a_warning(session: Session) -> None:
    issue = DataQualityIssue(code="line_score_missing", message="no #line_score table")

    result = _load(session, box=_box(issues=(issue,)))

    assert result.status == "loaded"
    assert [warning.code for warning in result.warnings] == [WARNING_LINE_SCORE_UNREADABLE]


@pytest.mark.unit
def test_overtime_periods_follow_the_schedule(session: Session) -> None:
    def overtime_team(code: str, points: int, quarters: tuple[int, ...]) -> BoxScoreTeam:
        team = _team(code, points)
        return replace(
            team, line_score=quarters, totals_seconds=15900,
            players=tuple(replace(line, seconds_played=3180) for line in team.players),
        )

    visitor = overtime_team("BOS", 101, (25, 25, 25, 20, 6))
    home = overtime_team("DEN", 110, (25, 25, 25, 20, 15))

    result = _load(
        session, schedule=_schedule(overtime_periods=1), box=_box(visitor=visitor, home=home)
    )

    assert result.status == "loaded" and result.warnings == ()


@pytest.mark.unit
@pytest.mark.parametrize("target", ["team_minutes", "player_minutes", "date", "negative"])
def test_invalid_stored_values_are_quarantined_before_any_write(
    session: Session, target: str,
) -> None:
    team = _team("BOS", 101)
    schedule = _schedule()
    reason = "minutes_mismatch"
    if target == "team_minutes":
        team = replace(team, totals_seconds=15900)
    elif target == "player_minutes":
        team = replace(team, players=(replace(team.players[0], seconds_played=100), *team.players[1:]))
    elif target == "date":
        schedule = _schedule(game_date=date(2024, 1, 11))
        reason = "game_id_mismatch"
    else:
        team = replace(team, players=(replace(team.players[0], seconds_played=-1), *team.players[1:]))
        reason = "invalid_box_score_values"
    result = _load(session, schedule=schedule, box=_box(visitor=team))
    assert result.status == "quarantined"
    assert reason in {issue.code for issue in result.quarantine}
    assert _count(session, Game) == _count(session, Player) == 0


@pytest.mark.unit
def test_swapped_quarters_warn_even_when_the_line_score_sums_correctly(session: Session) -> None:
    team = _team("BOS", 101)
    team = replace(team, period_points={1: 20, 2: 31, 3: 25, 4: 25})
    result = _load(session, box=_box(visitor=team))
    assert result.status == "loaded"
    assert [issue.code for issue in result.warnings] == [WARNING_LINE_SCORE_DISAGREES]
    assert "period 1 box 20" in result.warnings[0].detail


# --- Cup-final plus-minus -----------------------------------------------------


@pytest.mark.unit
def test_cup_final_plus_minus_of_all_zeros_is_stored_as_null(session: Session) -> None:
    result = _load(session, box=_box(game_type=GAME_TYPE_CUP_FINAL))

    assert [issue.code for issue in result.warnings] == [WARNING_CUP_FINAL_PLUS_MINUS_ZEROS]
    assert {row.plus_minus for row in _rows_by_player(session).values()} == {None}


@pytest.mark.unit
def test_cup_final_with_real_plus_minus_keeps_it(session: Session) -> None:
    box = _box(
        visitor=_team("BOS", 101, plus_minus=-2),
        home=_team("DEN", 110, plus_minus=2),
        game_type=GAME_TYPE_CUP_FINAL,
    )

    result = _load(session, box=box)

    assert result.warnings == ()
    assert {row.plus_minus for row in _rows_by_player(session).values()} == {-2, 2}


@pytest.mark.unit
def test_a_regular_season_game_keeps_zero_plus_minus(session: Session) -> None:
    _load(session)

    assert {row.plus_minus for row in _rows_by_player(session).values()} == {0}


# --- neutral site -------------------------------------------------------------


def _venue(game_id: int, home: int, venue: str | None) -> FinalGameVenue:
    return FinalGameVenue(
        game_id=game_id,
        basketball_reference_game_id=f"g{game_id}",
        home_team_season_id=home,
        venue=venue,
        neutral_site=None,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("venue", "city"),
    [
        ("Accor Arena, Paris, France", "Paris, France"),
        ("Ball Arena, Denver, Colorado", "Denver, Colorado"),
        ("Ball Arena", None),
        (None, None),
        ("Arena, ", None),
    ],
)
def test_the_venue_city_is_the_text_after_the_first_comma(
    venue: str | None, city: str | None
) -> None:
    assert venue_city(venue) == city


@pytest.mark.unit
def test_a_renamed_arena_in_the_same_city_is_not_neutral() -> None:
    games = [
        _venue(1, 10, "Staples Center, Los Angeles, California"),
        _venue(2, 10, "Staples Center, Los Angeles, California"),
        _venue(3, 10, "Crypto.com Arena, Los Angeles, California"),
    ]

    decided, warnings = neutral_sites(games)

    assert decided == {1: False, 2: False, 3: False}
    assert warnings == []


@pytest.mark.unit
def test_two_teams_sharing_a_city_are_both_at_home() -> None:
    games = [
        _venue(1, 10, "Crypto.com Arena, Los Angeles, California"),
        _venue(2, 10, "Crypto.com Arena, Los Angeles, California"),
        _venue(3, 20, "Crypto.com Arena, Los Angeles, California"),
        _venue(4, 20, "Crypto.com Arena, Los Angeles, California"),
        _venue(5, 20, "Arena CDMX, Mexico City, Mexico"),
    ]

    decided, _ = neutral_sites(games)

    assert decided == {1: False, 2: False, 3: False, 4: False, 5: True}


@pytest.mark.unit
def test_bubble_and_abroad_games_are_neutral_and_a_missing_venue_is_undetermined() -> None:
    games = [
        _venue(1, 10, "Ball Arena, Denver, Colorado"),
        _venue(2, 10, "Ball Arena, Denver, Colorado"),
        _venue(3, 10, "Ball Arena, Denver, Colorado"),
        _venue(4, 10, "HP Field House, Bay Lake, Florida"),
        _venue(5, 10, "Accor Arena, Paris, France"),
        _venue(6, 10, None),
        _venue(7, 10, "T-Mobile Arena, Las Vegas, Nevada"),
    ]

    decided, _ = neutral_sites(games)

    assert decided == {1: False, 2: False, 3: False, 4: True, 5: True, 6: None, 7: True}


@pytest.mark.unit
def test_an_even_split_of_home_cities_leaves_the_team_undetermined() -> None:
    games = [
        _venue(1, 10, "Arena, Toronto, Ontario"),
        _venue(2, 10, "Amalie Arena, Tampa, Florida"),
        _venue(3, 20, "Ball Arena, Denver, Colorado"),
    ]

    decided, warnings = neutral_sites(games)

    assert decided == {1: None, 2: None, 3: False}
    assert [warning.code for warning in warnings] == [WARNING_HOME_CITY_TIED]


@pytest.mark.unit
def test_the_neutral_pass_updates_only_neutral_site_and_reruns_as_a_no_op(
    session: Session,
) -> None:
    for day, venue in ((10, "Ball Arena, Denver, Colorado"), (11, "Ball Arena, Denver, Colorado")):
        game_id = f"202401{day}0DEN"
        _load(
            session,
            schedule=_schedule(game_id=game_id, game_date=date(2024, 1, day)),
            box=_box(venue=venue),
        )
    _load(
        session,
        schedule=_schedule(game_id="202401120DEN", game_date=date(2024, 1, 12)),
        box=_box(venue="Accor Arena, Paris, France"),
    )
    session.commit()

    first = derive_neutral_sites(session, SEASON)
    session.commit()
    second = derive_neutral_sites(session, SEASON)

    assert first.updated == 3
    assert first.neutral_games == (("202401120DEN", "Accor Arena, Paris, France"),)
    assert second.updated == 0
    assert not session.dirty
    stored = dict(
        session.execute(select(Game.basketball_reference_game_id, Game.neutral_site)).all()
    )
    assert stored == {"202401100DEN": False, "202401110DEN": False, "202401120DEN": True}


@pytest.mark.unit
def test_the_neutral_pass_over_an_unknown_season_changes_nothing(session: Session) -> None:
    result = derive_neutral_sites(session, 1990)

    assert (result.updated, result.neutral_games) == (0, ())
