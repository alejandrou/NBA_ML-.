from __future__ import annotations

import random

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from nba_data.domain.team_codes import (
    is_aggregate_only_team_code,
    is_multi_team_marker,
    is_synthetic_team_code,
    multi_team_count,
    normalize_team_code,
    reject_synthetic_team_code_sql,
)

# The width of every column the four check constraints guard. The SQL form of
# the predicate is exact past this length too, but nothing longer can be stored.
CONSTRAINED_COLUMN_LENGTH = 10

# Every value the two forms of the rule are asserted to agree on. The SQL form
# recognizes a count of any length, so the corpus runs well past what a
# `String(10)` column can hold; see `test_sql_form_is_exact_for_a_count_of_any_length`.
AGREEMENT_CORPUS = (
    # Real team codes, including one that ends in a letter pair near the marker shape.
    "BOS",
    "LAL",
    "BRK",
    "PHO",
    "CHO",
    "NOP",
    # The aggregate-only marker, which is synthetic but not a team count.
    "TOT",
    "tot",
    " TOT ",
    # Multi-team markers, including the count that exists in the cache today.
    "2TM",
    "3TM",
    "4TM",
    "5TM",
    "6TM",
    "9TM",
    "10TM",
    "30TM",
    "99TM",
    "100TM",
    "999TM",
    # Counts past what a String(10) column can hold. The SQL form is exact here
    # too, so a later column widening cannot silently open a gap.
    "1000TM",
    "99999999TM",
    "100000000TM",
    "123456789012345TM",
    "5tm",
    " 5TM ",
    # Values that look like markers but are not.
    "0TM",
    "1TM",
    "02TM",
    "007TM",
    "TM",
    "2TMX",
    "TM2",
    "2T",
    "22T",
    "X2TM",
    # Digits and the two marker letters in an order that is not a count.
    "1T2M",
    "T2M",
    "2MT",
    "2TMTM",
    "2 TM",
)


@pytest.mark.unit
@pytest.mark.parametrize("value", ["2TM", "3TM", "4TM", "5TM", "6TM", "10TM", "99TM", "999TM"])
def test_multi_team_marker_accepts_any_count_of_at_least_two(value: str) -> None:
    assert is_multi_team_marker(value) is True
    assert is_synthetic_team_code(value) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    ["0TM", "1TM", "02TM", "TM", "2TMX", "TOT", "BOS", "LAL", "", "   ", None],
)
def test_multi_team_marker_rejects_non_markers(value: str | None) -> None:
    assert is_multi_team_marker(value) is False


@pytest.mark.unit
def test_multi_team_marker_normalizes_case_and_surrounding_space() -> None:
    assert is_multi_team_marker("5tm") is True
    assert is_multi_team_marker(" 5TM ") is True
    assert normalize_team_code(" bos ") == "BOS"
    assert normalize_team_code("   ") is None
    assert normalize_team_code(None) is None


@pytest.mark.unit
def test_multi_team_count_reports_the_team_count() -> None:
    assert multi_team_count("2TM") == 2
    assert multi_team_count("5TM") == 5
    assert multi_team_count("10TM") == 10
    assert multi_team_count("1TM") is None
    assert multi_team_count("BOS") is None


@pytest.mark.unit
def test_tot_keeps_its_own_handling_and_is_not_a_multi_team_marker() -> None:
    assert is_aggregate_only_team_code("TOT") is True
    assert is_multi_team_marker("TOT") is False
    assert is_synthetic_team_code("TOT") is True

    assert is_aggregate_only_team_code("2TM") is False


@pytest.mark.unit
@pytest.mark.parametrize("value", AGREEMENT_CORPUS)
def test_sql_check_constraint_agrees_with_the_python_predicate(value: str) -> None:
    """The rule is necessarily expressed twice, so assert the two forms agree.

    A check constraint cannot call Python, so `reject_synthetic_team_code_sql`
    generates the SQL form from the same constants. This drives the generated
    expression through a real database engine rather than comparing strings.
    """

    sql_accepted = _sql_accepts(value)

    assert sql_accepted is not is_synthetic_team_code(value), (
        f"SQL and Python disagree on {value!r}: "
        f"SQL accepted={sql_accepted}, Python synthetic={is_synthetic_team_code(value)}"
    )


@pytest.mark.unit
def test_nullable_sql_form_allows_null_but_still_rejects_markers() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "create table probe (code text, check "
                f"({reject_synthetic_team_code_sql('code', nullable=True)}))"
            )
            connection.exec_driver_sql("insert into probe (code) values (null)")

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.exec_driver_sql("insert into probe (code) values ('5TM')")
    finally:
        engine.dispose()


@pytest.mark.unit
@pytest.mark.parametrize("digits", [1, 2, 3, 8, 9, 20])
def test_sql_form_is_exact_for_a_count_of_any_length(digits: int) -> None:
    """The two forms must not part company at any count length.

    An expression that enumerated digit positions would have to stop somewhere,
    and past that point the database would accept a marker the Python predicate
    rejects. The digit-stripping form has no such bound: the longest count here
    is far longer than a `String(10)` column can hold, and it is still rejected.
    """

    marker = f"{'9' * digits}TM"
    not_a_marker = f"0{'9' * digits}TM"

    assert is_multi_team_marker(marker) is True
    assert _sql_accepts(marker) is False

    assert is_multi_team_marker(not_a_marker) is False
    assert _sql_accepts(not_a_marker) is True

    if digits >= CONSTRAINED_COLUMN_LENGTH:
        assert len(marker) > CONSTRAINED_COLUMN_LENGTH


@pytest.mark.unit
def test_sql_and_python_forms_agree_across_a_random_sweep() -> None:
    """The corpus is hand-picked, so sweep the shapes nobody thought to list.

    The alphabet is restricted to the characters that can plausibly confuse the
    rule — digits, the two marker letters in either case, a near-miss letter and
    a space — so short random strings land on interesting cases rather than on
    obvious team codes.
    """

    generator = random.Random(20260816)
    alphabet = "0123456789TMtmX "

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "create table probe (code text not null, check "
                f"({reject_synthetic_team_code_sql('code', nullable=False)}))"
            )

        disagreements = []
        for _ in range(2000):
            value = "".join(
                generator.choice(alphabet) for _ in range(generator.randint(0, 7))
            )
            try:
                with engine.begin() as connection:
                    connection.exec_driver_sql("insert into probe (code) values (?)", (value,))
                sql_accepted = True
            except IntegrityError:
                sql_accepted = False

            if sql_accepted is is_synthetic_team_code(value):
                disagreements.append(value)
    finally:
        engine.dispose()

    assert disagreements == []


def _sql_accepts(value: str) -> bool:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "create table probe (code text not null, check "
                f"({reject_synthetic_team_code_sql('code', nullable=False)}))"
            )

        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("insert into probe (code) values (?)", (value,))
            return True
        except IntegrityError:
            return False
    finally:
        engine.dispose()
