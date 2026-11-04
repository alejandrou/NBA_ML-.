"""Which finished games an evaluation must find, season by season.

The counts and quarantines are those of the F8-006 and F8-018 loads
(`docs/validation/GAME_DATASET_ACQUISITION.md`). A season that does not match
exactly stops the evaluation: scoring a partial season would still produce a
result, and a misleading one.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from nba_data.ml.team_games import GAME_TYPE_CUP_FINAL, GAME_TYPE_REGULAR_SEASON, TeamGameRecord


@dataclass(frozen=True)
class SeasonInventory:
    # Regular-season games the league played.
    regular_season: int
    cup_finals: int = 0
    # Regular-season source errors, documented and never loaded.
    quarantined: tuple[str, ...] = ()

    @property
    def usable_regular_season(self) -> int:
        return self.regular_season - len(self.quarantined)


GAME_INVENTORY: Mapping[int, SeasonInventory] = {
    2015: SeasonInventory(1230),
    2016: SeasonInventory(1230),
    2017: SeasonInventory(1230, quarantined=("201703250LAC",)),
    2018: SeasonInventory(1230, quarantined=("201711110UTA", "201711240DEN", "201712040NOP")),
    2019: SeasonInventory(1230),
    2020: SeasonInventory(1059),
    2021: SeasonInventory(1080),
    2022: SeasonInventory(1230),
    2023: SeasonInventory(1230, quarantined=("202212250DEN", "202303020GSW")),
    2024: SeasonInventory(1230, cup_finals=1, quarantined=("202311210PHI",)),
    2025: SeasonInventory(1230, cup_finals=1),
    2026: SeasonInventory(1230, cup_finals=1),
}


def inventory_problems(
    games: Iterable[TeamGameRecord],
    seasons: Iterable[int],
    inventory: Mapping[int, SeasonInventory],
) -> list[str]:
    """Every way `games` differ from the inventory; empty when they match.

    Only a game with both final scores counts, so a blank result is a missing game.
    """

    games = list(games)
    scored = [game for game in games if game.home.pts is not None and game.away.pts is not None]
    found = Counter((game.season_year, game.game_type) for game in scored)
    ids = {game.game_id for game in games}
    problems = []
    for season in seasons:
        expected = inventory.get(season)
        if expected is None:
            problems.append(f"season {season} has no inventory")
            continue
        for label, game_type, count in (
            ("regular-season", GAME_TYPE_REGULAR_SEASON, expected.usable_regular_season),
            ("Cup final", GAME_TYPE_CUP_FINAL, expected.cup_finals),
        ):
            if found[season, game_type] != count:
                problems.append(
                    f"season {season}: {found[season, game_type]} scored {label} games, "
                    f"expected {count}"
                )
        loaded = sorted(ids.intersection(expected.quarantined))
        if loaded:
            problems.append(f"season {season}: quarantined games are loaded: {loaded}")
    return problems
