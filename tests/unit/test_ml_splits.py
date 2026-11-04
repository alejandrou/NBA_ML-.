"""The Stage 3 seasons: nothing later than the target, 2015 only as history."""

from __future__ import annotations

import pytest

from nba_data.ml.splits import (
    FIRST_HISTORY_SEASON,
    FIRST_TRAINING_SEASON,
    SELECTION_SEASON,
    TEST_SEASON,
    VALIDATION_SEASONS,
    WINDOWS,
    TrainingWindow,
    history_start,
    training_seasons,
)

LAST_3, LAST_5, EVERY_SEASON = WINDOWS
TARGETS = (*VALIDATION_SEASONS, SELECTION_SEASON, TEST_SEASON)


def test_the_validation_selection_and_test_seasons_never_overlap() -> None:
    assert VALIDATION_SEASONS == (2020, 2021, 2022, 2023, 2024)
    assert (SELECTION_SEASON, TEST_SEASON) == (2025, 2026)


@pytest.mark.parametrize("window", WINDOWS, ids=lambda window: window.name)
@pytest.mark.parametrize("target", TARGETS)
def test_training_is_strictly_before_the_target_and_never_reads_2015(
    target: int, window: TrainingWindow
) -> None:
    seasons = training_seasons(target, window)

    assert seasons
    assert max(seasons) == target - 1
    assert FIRST_HISTORY_SEASON not in seasons
    assert list(seasons) == sorted(set(seasons))


def test_the_windows_keep_the_last_seasons() -> None:
    assert training_seasons(2024, LAST_3) == (2021, 2022, 2023)
    assert training_seasons(2024, LAST_5) == (2019, 2020, 2021, 2022, 2023)
    assert training_seasons(2024, EVERY_SEASON) == tuple(range(2016, 2024))


def test_a_window_longer_than_the_available_seasons_uses_what_exists() -> None:
    assert training_seasons(2020, LAST_5) == (2016, 2017, 2018, 2019)


def test_a_season_with_no_earlier_training_season_fails() -> None:
    with pytest.raises(ValueError, match="no earlier training season"):
        training_seasons(FIRST_TRAINING_SEASON, EVERY_SEASON)


def test_only_the_all_seasons_window_reaches_back_to_where_elo_begins() -> None:
    assert history_start(2024, EVERY_SEASON) == FIRST_HISTORY_SEASON
    assert history_start(2024, LAST_3) == 2021
