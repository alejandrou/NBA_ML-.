from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.db.models.core import Season
from nba_data.scraping.loaders.player_page_stats import PlayerPageStatsLoadEntry
from nba_data.scraping.player_page_scope import (
    POSTSEASON_UNRESOLVED_REASONS,
    REGULAR_UNRESOLVED_REASONS,
    EmptySeasonScopeError,
    classify_unresolved_rows,
    load_season_scope,
    merge_out_of_scope_reasons,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        Season.__table__.create(connection)
        with Session(bind=connection) as session:
            yield session
    engine.dispose()


def _entry(reason: str | None, season_year: int | None) -> PlayerPageStatsLoadEntry:
    return PlayerPageStatsLoadEntry(
        row_index=0,
        status="skipped",
        reason=reason,
        season_year=season_year,
    )


@pytest.mark.unit
@pytest.mark.parametrize("reason", sorted(POSTSEASON_UNRESOLVED_REASONS))
def test_unresolved_reasons_outside_the_scope_are_counted_out_of_scope(reason: str) -> None:
    counts = classify_unresolved_rows(
        (_entry(reason, 1999),),
        loaded_season_years={2021},
        unresolved_reasons=POSTSEASON_UNRESOLVED_REASONS,
    )

    assert (counts.in_scope, counts.out_of_scope) == (0, 1)
    assert counts.out_of_scope_reasons == {reason: 1}


@pytest.mark.unit
@pytest.mark.parametrize("reason", sorted(POSTSEASON_UNRESOLVED_REASONS))
def test_unresolved_reasons_inside_the_scope_stay_unresolved(reason: str) -> None:
    counts = classify_unresolved_rows(
        (_entry(reason, 2021),),
        loaded_season_years={2021},
        unresolved_reasons=POSTSEASON_UNRESOLVED_REASONS,
    )

    assert (counts.in_scope, counts.out_of_scope) == (1, 0)
    assert counts.out_of_scope_reasons == {}


@pytest.mark.unit
def test_the_regular_reason_set_ignores_the_two_postseason_team_grains() -> None:
    """The regular producer resolves no team stint, so those reasons cannot occur."""

    counts = classify_unresolved_rows(
        (_entry("missing_team_season", 1999), _entry("missing_player_team_season", 1999)),
        loaded_season_years={2021},
        unresolved_reasons=REGULAR_UNRESOLVED_REASONS,
    )

    assert (counts.in_scope, counts.out_of_scope) == (0, 0)


@pytest.mark.unit
@pytest.mark.parametrize("reason", (None, "invalid_season_year", "loaded"))
def test_rows_that_are_not_unresolved_are_counted_in_neither_bucket(reason: str | None) -> None:
    counts = classify_unresolved_rows(
        (_entry(reason, 1999),),
        loaded_season_years={2021},
        unresolved_reasons=POSTSEASON_UNRESOLVED_REASONS,
    )

    assert (counts.in_scope, counts.out_of_scope) == (0, 0)


@pytest.mark.unit
def test_a_row_without_a_season_year_can_never_be_called_out_of_scope() -> None:
    counts = classify_unresolved_rows(
        (_entry("missing_player", None),),
        loaded_season_years={2021},
        unresolved_reasons=POSTSEASON_UNRESOLVED_REASONS,
    )

    assert (counts.in_scope, counts.out_of_scope) == (1, 0)


@pytest.mark.unit
def test_out_of_scope_reasons_keep_the_missing_player_signal_visible() -> None:
    """Absorbing a missing player into the out-of-scope count must not hide it."""

    counts = classify_unresolved_rows(
        (
            _entry("missing_player", 1999),
            _entry("missing_player", 1998),
            _entry("missing_season", 1999),
        ),
        loaded_season_years={2021},
        unresolved_reasons=REGULAR_UNRESOLVED_REASONS,
    )

    assert counts.out_of_scope == 3
    assert counts.out_of_scope_reasons == {"missing_player": 2, "missing_season": 1}


@pytest.mark.unit
def test_merge_out_of_scope_reasons_sums_pages_into_one_sorted_mapping() -> None:
    merged = merge_out_of_scope_reasons(
        [{"missing_season": 2}, {"missing_player": 1, "missing_season": 3}, {}]
    )

    assert merged == {"missing_player": 1, "missing_season": 5}
    assert list(merged) == ["missing_player", "missing_season"]


@pytest.mark.unit
def test_load_season_scope_returns_the_nba_years_present(session: Session) -> None:
    session.add_all(
        [
            Season(league="NBA", season_year=2024, label="2024"),
            Season(league="NBA", season_year=2025, label="2025"),
            Season(league="ABA", season_year=1975, label="1975"),
        ]
    )
    session.flush()

    assert load_season_scope(session) == frozenset({2024, 2025})


@pytest.mark.unit
def test_load_season_scope_refuses_an_unseeded_seasons_table(session: Session) -> None:
    with pytest.raises(EmptySeasonScopeError, match="backfill offline"):
        load_season_scope(session)
