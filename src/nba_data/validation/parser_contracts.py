"""Registry of `stats.*.parser_version` identifiers.

Every one of the 33 `stats` tables carries a required `parser_version` lineage
column. This module is the single source of truth for which identifiers are
known, which producer wrote them, and which is current for each producer. It
must stay declarative and import-safe: no database access, no cache access, and
no import of any backfill module. Backfill modules import this registry, never
the reverse.

`validate_official_stats` (`nba_data.validation.official_stats`) is the
enforcement boundary: it fails a report on any `parser_version` value that is
absent from `PARSER_CONTRACTS` (`unknown_parser_version`) or present but not
current (`stale_parser_version`). Writers keep accepting a free-form
`--parser-version` for offline experiments and historical reproductions; only
validation judges the result.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ParserProducer = Literal[
    "team_season",
    "player_page_regular",
    "player_page_postseason",
]
PARSER_PRODUCERS: tuple[ParserProducer, ...] = (
    "team_season",
    "player_page_regular",
    "player_page_postseason",
)

ParserVersionStatus = Literal["current", "stale", "unknown"]


@dataclass(frozen=True)
class ParserContract:
    """One known `parser_version` identifier and what it means.

    `generation` groups identifiers that represent the same round of parsing
    fixes across producers, even though regular and postseason player-page
    processing keep separate stored identifiers: their selectors and
    destinations differ (regular writes aggregate rows only, postseason writes
    aggregate and team-stint rows), so one shared string would incorrectly
    promise they can never diverge.
    """

    identifier: str
    producer: ParserProducer
    generation: int
    is_current: bool
    introduced_by: str
    description: str


PARSER_CONTRACTS: tuple[ParserContract, ...] = (
    ParserContract(
        identifier="team-season-parser-v1",
        producer="team_season",
        generation=1,
        is_current=True,
        introduced_by="F4E-006",
        description="Initial team-season page parser, selector, and loader.",
    ),
    ParserContract(
        identifier="player-page-parser-v1",
        producer="player_page_regular",
        generation=1,
        is_current=False,
        introduced_by="F4E-007",
        description="Initial regular-season player-page parser, selector, and loader.",
    ),
    ParserContract(
        identifier="player-page-parser-v2",
        producer="player_page_regular",
        generation=2,
        is_current=False,
        introduced_by="F4E-013",
        description=(
            "Fixed the `YYYY-YY` century rollover in `_season_end_year`. Rows "
            "written under v1 carry the wrong `season_year` for "
            "century-crossing labels such as `1999-00`."
        ),
    ),
    ParserContract(
        identifier="player-page-parser-v3",
        producer="player_page_regular",
        generation=3,
        is_current=False,
        introduced_by="F4E-014",
        description=(
            "Treats any multi-team marker semantically instead of the fixed "
            "`{2TM, 3TM, 4TM}` list. Rows written under v1 or v2 are missing "
            "the full-season aggregate for a season whose marker fell outside "
            "that list, such as `5TM`."
        ),
    ),
    ParserContract(
        identifier="player-page-parser-v4",
        producer="player_page_regular",
        generation=4,
        is_current=True,
        introduced_by="F4E-022",
        description=(
            "Excludes `Did not play - ...` placeholder rows from full-season "
            "selection, recovering real rows that share their season and "
            "preventing placeholder values from reaching the stats loader."
        ),
    ),
    ParserContract(
        identifier="player-page-postseason-parser-v1",
        producer="player_page_postseason",
        generation=1,
        is_current=False,
        introduced_by="F4E-008",
        description="Initial postseason player-page parser, selector, and loader.",
    ),
    ParserContract(
        identifier="player-page-postseason-parser-v2",
        producer="player_page_postseason",
        generation=2,
        is_current=False,
        introduced_by="F4E-013",
        description="Fixes the `YYYY-YY` century rollover, tracking the regular-season lineage.",
    ),
    ParserContract(
        identifier="player-page-postseason-parser-v3",
        producer="player_page_postseason",
        generation=3,
        is_current=False,
        introduced_by="F4E-014",
        description="Treats any multi-team marker semantically, tracking the regular-season lineage.",
    ),
    ParserContract(
        identifier="player-page-postseason-parser-v4",
        producer="player_page_postseason",
        generation=4,
        is_current=True,
        introduced_by="F4E-022",
        description=(
            "Keeps `Did not play - ...` placeholder rows out of full-season "
            "selection, matching the regular-season parser lineage."
        ),
    ),
)

PARSER_CONTRACTS_BY_IDENTIFIER: Mapping[str, ParserContract] = {
    contract.identifier: contract for contract in PARSER_CONTRACTS
}

CURRENT_PARSER_CONTRACTS: Mapping[ParserProducer, ParserContract] = {
    contract.producer: contract for contract in PARSER_CONTRACTS if contract.is_current
}


def current_parser_version(producer: ParserProducer) -> str:
    """Return the identifier a producer should stamp on rows it writes today."""

    return CURRENT_PARSER_CONTRACTS[producer].identifier


def classify_parser_version(value: object) -> ParserVersionStatus:
    """Classify a stored `parser_version` value against the registry.

    `None` and blank strings classify as `unknown`, same as any identifier the
    registry has never seen. Matching is on the exact stored string.
    """

    if not isinstance(value, str) or not value.strip():
        return "unknown"

    contract = PARSER_CONTRACTS_BY_IDENTIFIER.get(value)
    if contract is None:
        return "unknown"
    return "current" if contract.is_current else "stale"


__all__ = [
    "CURRENT_PARSER_CONTRACTS",
    "PARSER_CONTRACTS",
    "PARSER_CONTRACTS_BY_IDENTIFIER",
    "PARSER_PRODUCERS",
    "ParserContract",
    "ParserProducer",
    "ParserVersionStatus",
    "classify_parser_version",
    "current_parser_version",
]
