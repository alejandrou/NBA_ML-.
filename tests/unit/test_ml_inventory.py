"""The game inventory: complete seasons pass, anything else is named."""

from __future__ import annotations

from datetime import date

import pytest

from nba_data.ml.inventory import GAME_INVENTORY, SeasonInventory, inventory_problems
from nba_data.ml.team_games import TeamBox, TeamGameRecord


def _game(game_id: str, game_type: str = "regular_season", pts: int | None = 100) -> TeamGameRecord:
    box = TeamBox("AAA", pts, 14400, 40, 85, 12, 18, 22, 10, 33, 13)
    return TeamGameRecord(game_id, 2024, date(2024, 1, 1), game_type, "final", False, box, box)


def test_the_inventory_is_the_loaded_dataset() -> None:
    assert sum(season.regular_season + season.cup_finals for season in GAME_INVENTORY.values()) == (
        14442
    )
    assert sum(season.usable_regular_season for season in GAME_INVENTORY.values()) == 14432
    assert sum(len(season.quarantined) for season in GAME_INVENTORY.values()) == 7


def test_a_complete_season_with_its_quarantine_has_no_problems() -> None:
    inventory = {2024: SeasonInventory(3, cup_finals=1, quarantined=("q",))}
    games = [_game("a"), _game("b"), _game("cup", "cup_final")]

    assert inventory_problems(games, [2024], inventory) == []


@pytest.mark.parametrize(
    ("games", "expected"),
    (
        ([_game("a")], "1 scored regular-season games, expected 2"),
        ([_game("a"), _game("b"), _game("c")], "3 scored regular-season games, expected 2"),
        ([_game("a"), _game("b", pts=None)], "1 scored regular-season games, expected 2"),
        ([], "0 scored regular-season games, expected 2"),
    ),
)
def test_a_season_that_differs_is_named(games: list[TeamGameRecord], expected: str) -> None:
    problems = inventory_problems(games, [2024], {2024: SeasonInventory(2)})

    assert problems == [f"season 2024: {expected}"]


def test_a_missing_cup_final_is_a_problem() -> None:
    problems = inventory_problems([_game("a")], [2024], {2024: SeasonInventory(1, cup_finals=1)})

    assert problems == ["season 2024: 0 scored Cup final games, expected 1"]


def test_a_loaded_quarantined_game_is_a_problem_even_if_the_count_matches() -> None:
    problems = inventory_problems(
        [_game("q")], [2024], {2024: SeasonInventory(2, quarantined=("q",))}
    )

    assert problems == ["season 2024: quarantined games are loaded: ['q']"]


def test_a_season_with_no_inventory_is_a_problem() -> None:
    assert inventory_problems([], [2030], {}) == ["season 2030 has no inventory"]
