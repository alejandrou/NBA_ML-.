"""Season-scope classification shared by both player-page stats producers.

A cached player page carries a player's whole career, so the cache spans season
end years the archive does not load. A row for a season absent from
`core.seasons` can never resolve a grain, and counting it as unresolved makes a
clean rebuild look failed. Both producers therefore classify each unresolved
loader entry by season scope before reacting to its loader reason.

The scope is read from the database, so an empty `core.seasons` would classify
every row as out of scope and turn a misordered run — the player-page backfills
before `backfill offline` — into a silent success. `load_season_scope` refuses
that case instead.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from nba_data.db.repositories.queries.seasons import get_season_years
from nba_data.scraping.loaders.player_page_stats import PlayerPageStatsLoadEntry

# Loader reasons that mean "this row resolved no grain". The postseason
# producer resolves two extra grains, so it carries the two extra reasons.
REGULAR_UNRESOLVED_REASONS = frozenset(
    {"missing_player", "missing_season", "missing_player_season"}
)
POSTSEASON_UNRESOLVED_REASONS = REGULAR_UNRESOLVED_REASONS | {
    "missing_team_season",
    "missing_player_team_season",
}

_EMPTY_SCOPE_MESSAGE = (
    "core.seasons holds no NBA season, so every cached row would count as "
    "out of scope and the run would report success without loading anything. "
    "Run `nba-data backfill offline` before the player-page stats backfills."
)


class EmptySeasonScopeError(ValueError):
    """Raised when `core.seasons` holds no NBA season to scope a run against."""


@dataclass(frozen=True)
class UnresolvedRowCounts:
    """Unresolved loader rows split by whether the archive loads their season."""

    in_scope: int = 0
    out_of_scope: int = 0
    out_of_scope_reasons: Mapping[str, int] = field(default_factory=dict)


def load_season_scope(session: Session) -> frozenset[int]:
    """Return the NBA season years the archive loads, refusing an empty scope."""

    loaded_season_years = get_season_years(session)
    if not loaded_season_years:
        raise EmptySeasonScopeError(_EMPTY_SCOPE_MESSAGE)
    return loaded_season_years


def classify_unresolved_rows(
    entries: tuple[PlayerPageStatsLoadEntry, ...],
    *,
    loaded_season_years: Collection[int],
    unresolved_reasons: Collection[str],
) -> UnresolvedRowCounts:
    """Split unresolved loader entries into in-scope and out-of-scope counts."""

    in_scope = 0
    out_of_scope_reasons: Counter[str] = Counter()
    for entry in entries:
        if entry.reason not in unresolved_reasons:
            continue
        is_out_of_scope = (
            entry.season_year is not None and entry.season_year not in loaded_season_years
        )
        if is_out_of_scope:
            out_of_scope_reasons[entry.reason] += 1
        else:
            in_scope += 1
    return UnresolvedRowCounts(
        in_scope=in_scope,
        out_of_scope=sum(out_of_scope_reasons.values()),
        out_of_scope_reasons=dict(sorted(out_of_scope_reasons.items())),
    )


def merge_out_of_scope_reasons(
    reason_counts: Collection[Mapping[str, int]],
) -> dict[str, int]:
    """Sum per-page out-of-scope reason counts into one report-level mapping."""

    merged: Counter[str] = Counter()
    for counts in reason_counts:
        merged.update(counts)
    return dict(sorted(merged.items()))


__all__ = [
    "POSTSEASON_UNRESOLVED_REASONS",
    "REGULAR_UNRESOLVED_REASONS",
    "EmptySeasonScopeError",
    "UnresolvedRowCounts",
    "classify_unresolved_rows",
    "load_season_scope",
    "merge_out_of_scope_reasons",
]
