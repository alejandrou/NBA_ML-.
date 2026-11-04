"""Seasons of the Stage 3 protocol, by end year.

Test 2026, calibration and selection 2025, rolling validation 2020 to 2024.
Season 2015 is history only: it feeds the features and Elo, but its games start
from cold ratings, so they are neither training rows nor validation targets.
"""

from __future__ import annotations

from dataclasses import dataclass

FIRST_HISTORY_SEASON = 2015
FIRST_TRAINING_SEASON = 2016
VALIDATION_SEASONS = (2020, 2021, 2022, 2023, 2024)
CALIBRATION_SEASON = 2024
SELECTION_SEASON = 2025
TEST_SEASON = 2026


@dataclass(frozen=True)
class TrainingWindow:
    name: str
    # `None` is every available season.
    seasons: int | None


WINDOWS = (
    TrainingWindow("last_3", 3),
    TrainingWindow("last_5", 5),
    TrainingWindow("all", None),
)


def training_seasons(target_season: int, window: TrainingWindow) -> tuple[int, ...]:
    """The training rows' seasons for `target_season`: strictly earlier, oldest first."""

    available = tuple(range(FIRST_TRAINING_SEASON, target_season))
    if not available:
        raise ValueError(f"season {target_season} has no earlier training season")
    return available if window.seasons is None else available[-window.seasons :]


def history_start(target_season: int, window: TrainingWindow) -> int:
    """The first season a model's own memory may read; only Elo keeps one.

    A limited window starts with its first training season; `all` reaches back
    to 2015, where every team's rating begins.
    """

    if window.seasons is None:
        return FIRST_HISTORY_SEASON
    return training_seasons(target_season, window)[0]
