"""The game grain's constraints must behave on PostgreSQL.

`core.games`, `stats.team_game_totals`, and `stats.player_game_totals` carry
PostgreSQL-only check conditions (a regular expression among them) that the
offline suite never executes. This drives every rule through the engine that
holds the data.

As in `test_synthetic_team_code_constraints_postgres.py`, every rejection names
the constraint it expects and asserts against the one PostgreSQL reports: a
probe that tripped a foreign key or a NOT NULL instead would otherwise pass
without exercising the rule under test. PostgreSQL evaluates check constraints
in name order and reports the first one that fails, so each probe below breaks
exactly one rule.

Environment authorization, connection lifetime, revision checking, and the
rollback that leaves the database as it was found all belong to
`tests/integration/conftest.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from nba_data.scraping.parsers.box_score import COUNTING_STATS

pytestmark = pytest.mark.integration

Probe = tuple[str, dict[str, object]]

ABSENT_PARTICIPATIONS = (
    "did_not_play",
    "did_not_dress",
    "not_with_team",
    "suspended",
    "other_absence",
    "inactive",
)

_LINEAGE = {
    "source_url": "https://www.basketball-reference.com/boxscores/probe.html",
    "cache_path": "boxscores/probe.html",
    "parser_version": "probe",
}


@dataclass(frozen=True)
class Seeds:
    season_id: int
    home_team_season_id: int
    away_team_season_id: int
    other_season_team_season_id: int
    player_id: int
    second_player_id: int


@pytest.fixture
def seeds(postgres_connection: Connection) -> Seeds:
    """Parents for every foreign key, so a rejection can only come from the rule."""

    connection = postgres_connection
    season_id = _scalar(
        connection,
        "insert into core.seasons (season_year, league) "
        "values (-1, 'GAME-PROBE') returning id",
    )
    other_season_id = _scalar(
        connection,
        "insert into core.seasons (season_year, league) "
        "values (-2, 'GAME-PROBE') returning id",
    )
    return Seeds(
        season_id=season_id,
        home_team_season_id=_seed_team_season(connection, season_id),
        away_team_season_id=_seed_team_season(connection, season_id),
        other_season_team_season_id=_seed_team_season(connection, other_season_id),
        player_id=_seed_player(connection),
        second_player_id=_seed_player(connection),
    )


# --- core.games: rejections -------------------------------------------------


def test_a_team_cannot_play_itself(postgres_connection: Connection, seeds: Seeds) -> None:
    probe = _game(seeds, away_team_season_id=seeds.home_team_season_id)

    _assert_rejected_by(postgres_connection, probe, "ck_core_games_distinct_teams")


@pytest.mark.parametrize("side", ["home_team_season_id", "away_team_season_id"])
def test_both_teams_must_belong_to_the_game_season(
    postgres_connection: Connection, seeds: Seeds, side: str
) -> None:
    probe = _game(seeds, **{side: seeds.other_season_team_season_id})
    expected = (
        "fk_core_games_home_team_season"
        if side == "home_team_season_id"
        else "fk_core_games_away_team_season"
    )

    _assert_rejected_by(postgres_connection, probe, expected)


def test_a_game_id_is_stored_once(postgres_connection: Connection, seeds: Seeds) -> None:
    game_id = _bref_game_id()
    _insert(postgres_connection, _game(seeds, basketball_reference_game_id=game_id))

    probe = _game(seeds, basketball_reference_game_id=game_id)

    _assert_rejected_by(postgres_connection, probe, "uq_core_games_bref_id")


@pytest.mark.parametrize(
    "game_id",
    [
        "20231024DEN",  # the `0` separator is missing
        "202310241DEN",  # the separator is not `0`
        "202310240den",
        "202310240DENX",
        "202310240DE",
        " 202310240DEN",
        "202310240DEN ",
        "2023-10-240DEN",
        "",
    ],
)
def test_a_malformed_game_id_is_refused(
    postgres_connection: Connection, seeds: Seeds, game_id: str
) -> None:
    probe = _game(seeds, basketball_reference_game_id=game_id)

    _assert_rejected_by(postgres_connection, probe, "ck_core_games_bref_id_format")


def test_a_final_game_needs_a_game_type(postgres_connection: Connection, seeds: Seeds) -> None:
    probe = _game(seeds, status="final", game_type=None)

    _assert_rejected_by(postgres_connection, probe, "ck_core_games_final_has_game_type")


def test_attendance_cannot_be_negative(postgres_connection: Connection, seeds: Seeds) -> None:
    probe = _game(seeds, attendance=-1)

    _assert_rejected_by(postgres_connection, probe, "ck_core_games_attendance_non_negative")


@pytest.mark.parametrize("game_type", ["unknown", "preseason", "Regular_Season", ""])
def test_a_game_type_outside_the_parser_set_is_refused(
    postgres_connection: Connection, seeds: Seeds, game_type: str
) -> None:
    probe = _game(seeds, game_type=game_type)

    _assert_rejected_by(postgres_connection, probe, "ck_core_games_game_type")


@pytest.mark.parametrize("status", ["cancelled", "Final", ""])
def test_a_status_outside_the_allowed_set_is_refused(
    postgres_connection: Connection, seeds: Seeds, status: str
) -> None:
    probe = _game(seeds, status=status)

    _assert_rejected_by(postgres_connection, probe, "ck_core_games_status")


# --- core.games: acceptances ------------------------------------------------


@pytest.mark.parametrize("game_type", ["regular_season", "play_in", "playoffs", "cup_final"])
def test_every_classified_game_type_can_be_final(
    postgres_connection: Connection, seeds: Seeds, game_type: str
) -> None:
    game_id = _insert(postgres_connection, _game(seeds, game_type=game_type))

    row = postgres_connection.execute(
        text("select status, game_type from core.games where id = :id"), {"id": game_id}
    ).one()
    assert tuple(row) == ("final", game_type)


@pytest.mark.parametrize("status", ["scheduled", "postponed"])
def test_a_game_not_yet_final_needs_no_game_type(
    postgres_connection: Connection, seeds: Seeds, status: str
) -> None:
    game_id = _insert(postgres_connection, _game(seeds, status=status, game_type=None))

    row = postgres_connection.execute(
        text("select status, game_type from core.games where id = :id"), {"id": game_id}
    ).one()
    assert tuple(row) == (status, None)


def test_blank_and_zero_attendance_read_back_distinct(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    blank = _insert(postgres_connection, _game(seeds, attendance=None))
    zero = _insert(postgres_connection, _game(seeds, attendance=0))

    stored = {
        row.id: row.attendance
        for row in postgres_connection.execute(
            text("select id, attendance from core.games where id in (:blank, :zero)"),
            {"blank": blank, "zero": zero},
        )
    }
    assert stored == {blank: None, zero: 0}


def test_the_game_id_and_schedule_fields_read_back_exactly(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _bref_game_id()
    row_id = _insert(
        postgres_connection,
        _game(
            seeds,
            basketball_reference_game_id=game_id,
            game_date=date(2023, 10, 24),
            start_time_et=time(19, 30),
            venue="Ball Arena, Denver, Colorado",
        ),
    )

    row = postgres_connection.execute(
        text(
            "select basketball_reference_game_id, game_date, start_time_et, venue, "
            "neutral_site from core.games where id = :id"
        ),
        {"id": row_id},
    ).one()
    assert row.basketball_reference_game_id == game_id
    assert row.basketball_reference_game_id.encode() == game_id.encode()
    assert row.game_date == date(2023, 10, 24)
    assert row.start_time_et == time(19, 30)
    assert row.venue == "Ball Arena, Denver, Colorado"
    # Never determined, never defaulted to false.
    assert row.neutral_site is None


# --- stats.team_game_totals -------------------------------------------------


def test_a_side_has_one_team_total_per_game(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _insert(postgres_connection, _game(seeds))
    _insert(postgres_connection, _team_total(game_id, seeds.home_team_season_id, is_home=True))

    probe = _team_total(game_id, seeds.away_team_season_id, is_home=True)

    _assert_rejected_by(postgres_connection, probe, "uq_stats_team_game_totals_game_side")


def test_a_team_has_one_total_per_game(postgres_connection: Connection, seeds: Seeds) -> None:
    game_id = _insert(postgres_connection, _game(seeds))
    _insert(postgres_connection, _team_total(game_id, seeds.home_team_season_id, is_home=True))

    probe = _team_total(game_id, seeds.home_team_season_id, is_home=False)

    _assert_rejected_by(postgres_connection, probe, "uq_stats_team_game_totals_game_team")


@pytest.mark.parametrize("column", ["seconds_played", *COUNTING_STATS])
@pytest.mark.parametrize("sparse", [False, True], ids=["populated", "nullable-counters-blank"])
def test_a_team_counter_cannot_be_negative(
    postgres_connection: Connection, seeds: Seeds, column: str, sparse: bool
) -> None:
    game_id = _insert(postgres_connection, _game(seeds))

    counters = {stat: None for stat in COUNTING_STATS if stat != "pts"} if sparse else {}
    probe = _team_total(
        game_id, seeds.home_team_season_id, is_home=True, **(counters | {column: -1})
    )

    _assert_rejected_by(postgres_connection, probe, "ck_stats_team_game_totals_non_negative")


# --- stats.player_game_totals: rejections -----------------------------------


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("starter", True),
        ("seconds_played", 0),
        ("plus_minus", 0),
        *((stat, 0) for stat in COUNTING_STATS),
    ],
)
@pytest.mark.parametrize("participation", ABSENT_PARTICIPATIONS)
def test_a_line_that_was_not_played_carries_nothing(
    postgres_connection: Connection,
    seeds: Seeds,
    participation: str,
    column: str,
    value: object,
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)

    probe = _absent_line(game_id, seeds, participation=participation, **{column: value})

    _assert_rejected_by(postgres_connection, probe, "ck_stats_player_game_totals_absent_line_empty")


def test_a_played_line_needs_its_seconds(postgres_connection: Connection, seeds: Seeds) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)

    probe = _player_line(game_id, seeds, participation="played", seconds_played=None)

    _assert_rejected_by(postgres_connection, probe, "ck_stats_player_game_totals_played_has_seconds")


@pytest.mark.parametrize("other_team", [False, True], ids=["same-team", "other-team"])
def test_a_player_has_one_line_per_game(
    postgres_connection: Connection, seeds: Seeds, other_team: bool
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)
    _insert(postgres_connection, _team_total(game_id, seeds.away_team_season_id, is_home=False))
    _insert(postgres_connection, _player_line(game_id, seeds))

    team_id = seeds.away_team_season_id if other_team else seeds.home_team_season_id
    probe = _player_line(game_id, seeds, team_season_id=team_id)

    _assert_rejected_by(postgres_connection, probe, "uq_stats_player_game_totals_game_player")


def test_a_player_line_needs_its_team_total_for_that_game(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)

    probe = _player_line(game_id, seeds, team_season_id=seeds.away_team_season_id)

    _assert_rejected_by(postgres_connection, probe, "fk_stats_player_game_totals_team_game")


def test_a_team_total_from_another_game_cannot_back_a_player_line(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)
    other_game_id = _insert(postgres_connection, _game(seeds))
    _insert(
        postgres_connection,
        _team_total(other_game_id, seeds.away_team_season_id, is_home=False),
    )

    probe = _player_line(game_id, seeds, team_season_id=seeds.away_team_season_id)

    _assert_rejected_by(postgres_connection, probe, "fk_stats_player_game_totals_team_game")


@pytest.mark.parametrize("participation", ["unknown", "Played", "dnp", ""])
def test_a_participation_outside_the_parser_set_is_refused(
    postgres_connection: Connection, seeds: Seeds, participation: str
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)

    probe = _absent_line(game_id, seeds, participation=participation)

    _assert_rejected_by(postgres_connection, probe, "ck_stats_player_game_totals_participation")


@pytest.mark.parametrize("column", ["seconds_played", *COUNTING_STATS])
@pytest.mark.parametrize("sparse", [False, True], ids=["populated", "nullable-counters-blank"])
def test_a_player_counter_cannot_be_negative(
    postgres_connection: Connection, seeds: Seeds, column: str, sparse: bool
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)

    counters = {stat: None for stat in COUNTING_STATS} if sparse else {}
    probe = _player_line(game_id, seeds, **(counters | {column: -1}))

    _assert_rejected_by(postgres_connection, probe, "ck_stats_player_game_totals_non_negative")


# --- stats.player_game_totals: acceptances ----------------------------------


def test_a_played_zero_second_line_may_have_no_plus_minus(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)
    zeros = {stat: 0 for stat in COUNTING_STATS}

    line_id = _insert(
        postgres_connection,
        _player_line(game_id, seeds, seconds_played=0, plus_minus=None, **zeros),
    )

    row = postgres_connection.execute(
        text("select seconds_played, plus_minus from stats.player_game_totals where id = :id"),
        {"id": line_id},
    ).one()
    assert tuple(row) == (0, None)


def test_a_played_line_of_zeros_and_a_did_not_play_line_stay_distinct(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)
    zeros = {stat: 0 for stat in COUNTING_STATS}
    played = _insert(
        postgres_connection,
        _player_line(game_id, seeds, seconds_played=0, plus_minus=0, **zeros),
    )
    sat = _insert(
        postgres_connection,
        _absent_line(
            game_id,
            seeds,
            player_id=seeds.second_player_id,
            participation="did_not_play",
            participation_reason="Did Not Play",
        ),
    )

    columns = ", ".join(("participation", "seconds_played", "plus_minus", *COUNTING_STATS))
    rows = {
        row.id: row
        for row in postgres_connection.execute(
            text(
                f"select id, {columns} from stats.player_game_totals "
                "where id in (:played, :sat)"
            ),
            {"played": played, "sat": sat},
        )
    }
    assert rows[played].participation == "played"
    assert [rows[played].seconds_played, rows[played].plus_minus] == [0, 0]
    assert all(getattr(rows[played], stat) == 0 for stat in COUNTING_STATS)
    assert rows[sat].participation == "did_not_play"
    assert [rows[sat].seconds_played, rows[sat].plus_minus] == [None, None]
    assert all(getattr(rows[sat], stat) is None for stat in COUNTING_STATS)


@pytest.mark.parametrize("participation", ABSENT_PARTICIPATIONS)
def test_every_absence_keeps_its_line_and_published_reason(
    postgres_connection: Connection, seeds: Seeds, participation: str
) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)
    reason = f"Published reason: {participation}"

    line_id = _insert(
        postgres_connection,
        _absent_line(game_id, seeds, participation=participation, participation_reason=reason),
    )

    row = postgres_connection.execute(
        text(
            "select participation, participation_reason, starter "
            "from stats.player_game_totals where id = :id"
        ),
        {"id": line_id},
    ).one()
    assert tuple(row) == (participation, reason, False)


def test_blank_counters_stay_null_for_a_team_and_a_played_line(
    postgres_connection: Connection, seeds: Seeds
) -> None:
    game_id = _insert(postgres_connection, _game(seeds))
    team_id = _insert(
        postgres_connection,
        _team_total(
            game_id,
            seeds.home_team_season_id,
            is_home=True,
            **{stat: None for stat in COUNTING_STATS if stat != "pts"},
        ),
    )
    player_id = _insert(
        postgres_connection,
        _player_line(game_id, seeds, **{stat: None for stat in COUNTING_STATS}),
    )

    columns = ", ".join(COUNTING_STATS)
    team = postgres_connection.execute(
        text(f"select {columns} from stats.team_game_totals where id = :id"), {"id": team_id}
    ).one()
    player = postgres_connection.execute(
        text(f"select {columns} from stats.player_game_totals where id = :id"), {"id": player_id}
    ).one()
    assert team.pts == 119
    assert all(getattr(team, stat) is None for stat in COUNTING_STATS if stat != "pts")
    assert all(getattr(player, stat) is None for stat in COUNTING_STATS)


def test_plus_minus_may_be_negative(postgres_connection: Connection, seeds: Seeds) -> None:
    game_id = _game_with_home_total(postgres_connection, seeds)

    _insert(postgres_connection, _player_line(game_id, seeds, plus_minus=-17))


# --- probes -----------------------------------------------------------------


def _game(seeds: Seeds, **overrides: object) -> Probe:
    values: dict[str, object] = {
        "basketball_reference_game_id": _bref_game_id(),
        "season_id": seeds.season_id,
        "home_team_season_id": seeds.home_team_season_id,
        "away_team_season_id": seeds.away_team_season_id,
        "game_date": date(2023, 10, 24),
        "start_time_et": None,
        "game_type": "regular_season",
        "status": "final",
        "venue": None,
        "neutral_site": None,
        "attendance": 19_842,
    }
    return _insert_statement("core.games", values | overrides)


def _team_total(game_id: int, team_season_id: int, *, is_home: bool, **overrides: object) -> Probe:
    values: dict[str, object] = {
        "game_id": game_id,
        "team_season_id": team_season_id,
        "is_home": is_home,
        "seconds_played": 14_400,
        **{stat: 10 for stat in COUNTING_STATS},
        "pts": 119,
        **_LINEAGE,
    }
    return _insert_statement("stats.team_game_totals", values | overrides)


def _player_line(game_id: int, seeds: Seeds, **overrides: object) -> Probe:
    """A played line, valid as it stands."""

    values: dict[str, object] = {
        "game_id": game_id,
        "player_id": seeds.player_id,
        "team_season_id": seeds.home_team_season_id,
        "starter": True,
        "participation": "played",
        "participation_reason": None,
        "seconds_played": 2_100,
        **{stat: 1 for stat in COUNTING_STATS},
        "plus_minus": 4,
        **_LINEAGE,
    }
    return _insert_statement("stats.player_game_totals", values | overrides)


def _absent_line(game_id: int, seeds: Seeds, **overrides: object) -> Probe:
    """A line that was not played: no starter flag, no seconds, no stats."""

    empty: dict[str, object] = {
        "starter": False,
        "participation": "did_not_play",
        "seconds_played": None,
        "plus_minus": None,
        **{stat: None for stat in COUNTING_STATS},
    }
    return _player_line(game_id, seeds, **(empty | overrides))


def _game_with_home_total(connection: Connection, seeds: Seeds) -> int:
    game_id = _insert(connection, _game(seeds))
    _insert(connection, _team_total(game_id, seeds.home_team_season_id, is_home=True))
    return game_id


def _insert_statement(table: str, values: dict[str, object]) -> Probe:
    columns = ", ".join(values)
    placeholders = ", ".join(f":{name}" for name in values)
    return f"insert into {table} ({columns}) values ({placeholders}) returning id", values


def _insert(connection: Connection, probe: Probe) -> int:
    statement, parameters = probe
    return int(connection.execute(text(statement), parameters).scalar_one())


def _assert_rejected_by(connection: Connection, probe: Probe, constraint: str) -> None:
    """Run one probe in a savepoint and assert the constraint that refused it.

    The savepoint is rolled back before asserting, because a failed statement
    leaves the transaction unusable until it is.
    """

    statement, parameters = probe
    savepoint = connection.begin_nested()
    error: IntegrityError | None = None
    try:
        connection.execute(text(statement), parameters)
    except IntegrityError as caught:
        error = caught
    finally:
        savepoint.rollback()

    assert error is not None, f"{constraint} accepted {parameters!r}"
    violated = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    assert violated == constraint, (
        f"the probe was rejected by {violated!r} rather than {constraint!r}, so it "
        f"did not exercise the rule under test"
    )


# --- seeds ------------------------------------------------------------------


def _seed_team_season(connection: Connection, season_id: int) -> int:
    code = _unique_letters(6)
    team_id = _scalar(
        connection,
        "insert into core.teams (basketball_reference_team_id, current_name) "
        "values (:code, 'Game probe') returning id",
        {"code": code},
    )
    return _scalar(
        connection,
        "insert into core.team_seasons (team_id, season_id, team_abbreviation) "
        "values (:team_id, :season_id, :code) returning id",
        {"team_id": team_id, "season_id": season_id, "code": code},
    )


def _seed_player(connection: Connection) -> int:
    return _scalar(
        connection,
        "insert into core.players (basketball_reference_player_id, full_name) "
        "values (:bref_id, 'Game Probe') returning id",
        {"bref_id": f"probe{uuid4().hex[:12]}"},
    )


def _scalar(connection: Connection, statement: str, parameters: dict[str, object] | None = None) -> int:
    return int(connection.execute(text(statement), parameters or {}).scalar_one())


def _bref_game_id() -> str:
    """A well-formed id that no other probe in the transaction holds."""

    digits = f"{uuid4().int % 10**8:08d}"
    return f"{digits}0{_unique_letters(3)}"


def _unique_letters(count: int) -> str:
    """Random upper-case letters: never a synthetic team marker, which needs digits or `TOT`."""

    letters = "".join(chr(ord("A") + byte % 26) for byte in uuid4().bytes[:count])
    return "TOX" if letters == "TOT" else letters
