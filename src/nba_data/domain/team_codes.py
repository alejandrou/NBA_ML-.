"""Semantics of Basketball Reference team codes.

Two kinds of value appear where a team code is expected but no team exists:

* **Multi-team markers** — `2TM`, `3TM`, `4TM`, `5TM`, and so on. Basketball
  Reference writes these in the team cell of a player's *full-season* row after
  a trade, where the number is the count of teams the player appeared for. The
  set is open-ended: the cached archive already contains a `5TM` season, and
  nothing stops a future page carrying `6TM`. The rule is therefore
  "numeric team count of at least two", never a fixed enumeration.
* **`TOT`** — the team-page totals marker. It is *not* a team-count marker and
  keeps its own distinct handling: ADR 0007 ignores it for supported stats.

Both are synthetic: neither may ever create a `core.teams`, `core.team_aliases`,
`core.team_seasons`, or `stats.player_team_season_*` row. What a layer *does*
with a multi-team marker still differs by layer — it is a valid aggregate
`source_team_code` and an invalid team-stint `team_abbreviation`.

This module imports nothing from `scraping/`, `validation/`, or `db/`: all three
depend on it, so it stays a leaf.

**The SQL form.** A check constraint cannot call Python, so the rule is
necessarily expressed twice; the `*_sql` helpers generate the second form from
the same constants rather than restating it by hand, and `test_team_codes.py`
drives both through a real engine to assert they agree.

Portable SQL has neither regular expressions nor `translate`, so "is a run of
digits" is expressed by deleting every digit and checking what is left:

    <n>TM  ⟺  value ends in `TM`
              AND deleting all digits leaves exactly `TM`
              AND the first character is a digit that reaches the count floor

The middle condition is what makes the pair exact. If the whole value reduces to
`TM` then it holds one `T` and one `M` and no other letters; if it also *ends*
in `TM` then those are the final two characters, so everything before them is
digits. That covers a count of any length, so — unlike an expression that
enumerates digit positions — the SQL form needs no arbitrary bound and stays
exact even if a constrained column is later widened.
"""

from __future__ import annotations

import re

AGGREGATE_ONLY_TEAM_CODE = "TOT"
"""The team-page totals marker. Distinct from a multi-team marker."""

MIN_MULTI_TEAM_COUNT = 2
"""A one-team season is a real stint and a zero-team season is nonsense."""

MARKER_SUFFIX = "TM"
"""What a team count is followed by."""

# A count marker is digits followed by `TM`, with no leading zero: `02TM` is
# malformed, not two teams. The count itself is checked against
# MIN_MULTI_TEAM_COUNT, so `0TM` and `1TM` are rejected as well.
_MULTI_TEAM_MARKER_RE = re.compile(rf"(?P<count>[1-9][0-9]*){MARKER_SUFFIX}")

_DIGITS = tuple(str(digit) for digit in range(10))


def normalize_team_code(value: object) -> str | None:
    """Return the comparable form of a team code, or None when it is empty."""

    if value is None:
        return None
    normalized = str(value).strip().upper()
    return normalized or None


def multi_team_count(value: object) -> int | None:
    """Return the team count a multi-team marker carries, or None."""

    code = normalize_team_code(value)
    if code is None:
        return None
    match = _MULTI_TEAM_MARKER_RE.fullmatch(code)
    if match is None:
        return None
    count = int(match.group("count"))
    if count < MIN_MULTI_TEAM_COUNT:
        return None
    return count


def is_multi_team_marker(value: object) -> bool:
    """Whether the value is a numeric team-count marker of at least two teams."""

    return multi_team_count(value) is not None


def is_aggregate_only_team_code(value: object) -> bool:
    """Whether the value is `TOT`, which is not a multi-team marker."""

    return normalize_team_code(value) == AGGREGATE_ONLY_TEAM_CODE


def is_synthetic_team_code(value: object) -> bool:
    """Whether the value is a marker rather than a team: `TOT` or `<n>TM`."""

    return is_aggregate_only_team_code(value) or is_multi_team_marker(value)


def multi_team_marker_sql(column: str) -> str:
    """Return a portable SQL predicate matching `is_multi_team_marker`.

    Emitted for check constraints, which cannot call Python. Uses only `upper`,
    `trim`, `length`, `substr`, `replace`, `LIKE` and `IN`, so it behaves
    identically on PostgreSQL and on the SQLite databases the offline tests
    build. It is exact for a count of any length — see the module docstring for
    why the digit-stripping form is used instead of enumerating digits.
    """

    normalized = _normalized_sql(column)
    suffix_length = len(MARKER_SUFFIX)
    first_character = f"substr({normalized}, 1, 1)"
    conditions = (
        # The value ends in `TM`...
        f"{normalized} LIKE '%{MARKER_SUFFIX}'",
        # ...and every other character is a digit.
        f"{_strip_digits_sql(normalized)} = '{MARKER_SUFFIX}'",
        # A one-digit count must already reach the floor; a longer count always
        # clears it, and only a leading zero is out.
        "("
        f"(length({normalized}) = {suffix_length + 1}"
        f" AND {first_character} IN ({_digit_list_sql(MIN_MULTI_TEAM_COUNT)}))"
        f" OR (length({normalized}) > {suffix_length + 1}"
        f" AND {first_character} IN ({_digit_list_sql(1)}))"
        ")",
    )
    return "(" + " AND ".join(conditions) + ")"


def synthetic_team_code_sql(column: str) -> str:
    """Return a portable SQL predicate matching `is_synthetic_team_code`."""

    marker = multi_team_marker_sql(column)
    return f"({_normalized_sql(column)} = '{AGGREGATE_ONLY_TEAM_CODE}' OR {marker})"


def reject_synthetic_team_code_sql(column: str, *, nullable: bool) -> str:
    """Return the check-constraint condition allowing only real team codes.

    Shared by `db/models/core.py` and the Alembic revision that installs the
    constraints, so the mapped metadata and the migrated database cannot drift.
    """

    condition = f"NOT {synthetic_team_code_sql(column)}"
    if nullable:
        return f"{column} IS NULL OR {condition}"
    return condition


def _normalized_sql(column: str) -> str:
    return f"upper(trim({column}))"


def _digit_list_sql(minimum: int) -> str:
    return ", ".join(f"'{digit}'" for digit in _DIGITS[minimum:])


def _strip_digits_sql(expression: str) -> str:
    """Return SQL deleting every digit from `expression`.

    `translate` is not portable and neither is a regular expression, so this
    nests one `replace` per digit. Ten of them is the whole cost.
    """

    stripped = expression
    for digit in _DIGITS:
        stripped = f"replace({stripped}, '{digit}', '')"
    return stripped


__all__ = [
    "AGGREGATE_ONLY_TEAM_CODE",
    "MARKER_SUFFIX",
    "MIN_MULTI_TEAM_COUNT",
    "is_aggregate_only_team_code",
    "is_multi_team_marker",
    "is_synthetic_team_code",
    "multi_team_count",
    "multi_team_marker_sql",
    "normalize_team_code",
    "reject_synthetic_team_code_sql",
    "synthetic_team_code_sql",
]
