"""The two path dimensions that pick an official statistics table family.

A leaf module like `team_codes`: the query repositories, the API schemas, and
the routers all name these values, so none of them may own them.
"""

from enum import StrEnum


class SeasonType(StrEnum):
    REGULAR = "regular"
    POSTSEASON = "postseason"


class StatFamily(StrEnum):
    """The table suffix of each family, verbatim: `adj_shooting` is `*_adj_shooting`."""

    TOTALS = "totals"
    PER_GAME = "per_game"
    PER_MINUTE = "per_minute"
    PER_POSS = "per_poss"
    ADVANCED = "advanced"
    SHOOTING = "shooting"
    ADJ_SHOOTING = "adj_shooting"
    PBP = "pbp"


__all__ = ["SeasonType", "StatFamily"]
