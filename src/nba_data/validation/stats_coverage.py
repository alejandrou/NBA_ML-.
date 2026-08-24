"""Cache-derived official-stats coverage artifact (F4E-017).

Builds a deterministic, database-free JSON artifact stating the exact
`stats.*` natural keys the cached team-season and player pages imply. F4E-018
diffs this independent oracle against PostgreSQL to catch a missing or
unexpected row that report totals alone cannot see.

This module is intentionally pure: no database session, engine, ORM model, or
HTTP client import. Expectations come from parsed source rows plus small
source-semantic predicates (`is_multi_team_marker`, `is_did_not_play_placeholder`,
and friends) — never from a normalizer's final row-selection result, so a
normalizer defect cannot disappear from both the database and this oracle at
once. The normalizer is still run, but only to record disagreements as
evidence.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import uuid
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from nba_data.domain.team_codes import is_aggregate_only_team_code, is_multi_team_marker
from nba_data.scraping import player_page_cache
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import build_cached_html_inventory
from nba_data.scraping.normalizers.player_page import (
    is_did_not_play_placeholder,
    normalize_player_page_postseason,
    normalize_player_page_regular_season,
    parsed_team_code,
    season_end_year,
)
from nba_data.scraping.parsers.player_page import (
    SUPPORTED_PLAYER_PAGE_POSTSEASON_TABLES,
    SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES,
    parse_player_page_postseason,
    parse_player_page_regular_season,
)
from nba_data.scraping.parsers.team_season import (
    SUPPORTED_TEAM_SEASON_TABLES,
    parse_team_season_page,
)
from nba_data.scraping.player_page_cache import (
    PlayerCacheRootNotFoundError,
    discover_player_cache_entries,
    read_cached_gzip,
    required_html,
    resolve_player_cache_root,
)
from nba_data.validation.parser_contracts import PARSER_PRODUCERS, current_parser_version

SCHEMA_VERSION = 1

SeasonType = Literal["regular", "postseason"]

# Destination `stats.*` table for each source table, derived from the same
# parser table registries the parsers and their loaders already agree on —
# not restated as a hand-written list — so this module cannot silently drift
# from what the parsers actually produce. `test_stats_coverage_artifact.py`
# pins these against `validation.official_stats.STATS_TABLE_SPECS`.
REGULAR_TEAM_STINT_DESTINATIONS: Mapping[str, str] = MappingProxyType(
    {table: f"stats.player_team_season_{table}" for table in SUPPORTED_TEAM_SEASON_TABLES}
)
REGULAR_AGGREGATE_DESTINATIONS: Mapping[str, str] = MappingProxyType(
    {table: f"stats.player_season_{table}" for table in SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES}
)
POSTSEASON_AGGREGATE_DESTINATIONS: Mapping[str, str] = MappingProxyType(
    {table: f"stats.player_postseason_{table}" for table in SUPPORTED_PLAYER_PAGE_POSTSEASON_TABLES}
)
POSTSEASON_TEAM_STINT_DESTINATIONS: Mapping[str, str] = MappingProxyType(
    {table: f"stats.player_team_postseason_{table}" for table in SUPPORTED_PLAYER_PAGE_POSTSEASON_TABLES}
)

# Reasons `_select_full_season_row` (shared by both normalizers) can attach to
# an aggregate-row decision. Postseason `selection_entries` also carry
# "selected_real_team_postseason_row" for team-stint rows — including, for a
# single-team season, a *second* entry for the very row that was also chosen
# as the aggregate row — which is not an aggregate decision at all and must be
# excluded from this comparison rather than counted as "not selected".
_AGGREGATE_DECISION_REASONS = frozenset(
    {
        "selected_multi_team_aggregate",
        "selected_single_team_row",
        "ambiguous_multiple_real_team_rows",
        "no_supported_team_row",
        "did_not_play_season",
    }
)
_TEAM_ROW_FIELDS = ("team_abbreviation", "team_id", "team", "tm")


class StatsCoverageSchemaError(ValueError):
    """Raised when a stats-coverage artifact carries an unsupported schema_version."""


@dataclass(frozen=True)
class StatsCoverageTeamStint:
    team_code: str
    table: str

    def to_dict(self) -> dict[str, object]:
        return {"team_code": self.team_code, "table": self.table}


@dataclass(frozen=True)
class StatsCoverageDidNotPlay:
    regular: bool = False
    postseason: bool = False

    def to_dict(self) -> dict[str, object]:
        return {"regular": self.regular, "postseason": self.postseason}


@dataclass(frozen=True)
class StatsCoverageEntry:
    basketball_reference_player_id: str
    season_year: int
    regular_aggregate_tables: tuple[str, ...] = ()
    postseason_aggregate_tables: tuple[str, ...] = ()
    regular_team_stints: tuple[StatsCoverageTeamStint, ...] = ()
    postseason_team_stints: tuple[StatsCoverageTeamStint, ...] = ()
    did_not_play: StatsCoverageDidNotPlay = field(default_factory=StatsCoverageDidNotPlay)

    def to_dict(self) -> dict[str, object]:
        return {
            "basketball_reference_player_id": self.basketball_reference_player_id,
            "season_year": self.season_year,
            "regular_aggregate_tables": list(self.regular_aggregate_tables),
            "postseason_aggregate_tables": list(self.postseason_aggregate_tables),
            "regular_team_stints": [stint.to_dict() for stint in self.regular_team_stints],
            "postseason_team_stints": [stint.to_dict() for stint in self.postseason_team_stints],
            "did_not_play": self.did_not_play.to_dict(),
        }


@dataclass(frozen=True)
class StatsCoverageUnexplained:
    basketball_reference_player_id: str
    season_year: int
    season_type: SeasonType
    source_table: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "basketball_reference_player_id": self.basketball_reference_player_id,
            "season_year": self.season_year,
            "season_type": self.season_type,
            "source_table": self.source_table,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class StatsCoverageDisagreement:
    basketball_reference_player_id: str
    season_year: int
    season_type: SeasonType
    source_table: str
    classifier_selected: bool
    normalizer_selected: bool
    normalizer_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "basketball_reference_player_id": self.basketball_reference_player_id,
            "season_year": self.season_year,
            "season_type": self.season_type,
            "source_table": self.source_table,
            "classifier_selected": self.classifier_selected,
            "normalizer_selected": self.normalizer_selected,
            "normalizer_reason": self.normalizer_reason,
        }


@dataclass(frozen=True)
class StatsCoverageSourceIssue:
    cache_path: str
    status: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_path": self.cache_path,
            "status": self.status,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class StatsCoverageFingerprint:
    digest: str
    player_page_count: int
    team_page_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "digest": self.digest,
            "player_page_count": self.player_page_count,
            "team_page_count": self.team_page_count,
        }


@dataclass(frozen=True)
class StatsCoverageArtifact:
    cache_root: str
    parser_contracts: Mapping[str, str]
    cache_fingerprint: StatsCoverageFingerprint
    counts: Mapping[str, int]
    entries: tuple[StatsCoverageEntry, ...] = ()
    unexplained: tuple[StatsCoverageUnexplained, ...] = ()
    disagreements: tuple[StatsCoverageDisagreement, ...] = ()
    source_issues: tuple[StatsCoverageSourceIssue, ...] = ()
    schema_version: int = SCHEMA_VERSION

    @property
    def is_complete(self) -> bool:
        """Whether the artifact is a usable oracle: no unexplained seasons, no unreadable sources."""

        return not self.unexplained and not self.source_issues

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "cache_root": self.cache_root,
            "parser_contracts": dict(self.parser_contracts),
            "cache_fingerprint": self.cache_fingerprint.to_dict(),
            "counts": dict(self.counts),
            "entries": [entry.to_dict() for entry in self.entries],
            "unexplained": [item.to_dict() for item in self.unexplained],
            "disagreements": [item.to_dict() for item in self.disagreements],
            "source_issues": [item.to_dict() for item in self.source_issues],
        }


def build_stats_coverage_artifact(*, cache_root: str | Path) -> StatsCoverageArtifact:
    """Build the coverage artifact from a player-page and team-season cache root.

    Raises `PlayerCacheRootNotFoundError` if the root does not exist.
    """

    resolved_root = resolve_player_cache_root(Path(cache_root))
    cache = HtmlCache(resolved_root)

    player_entries = discover_player_cache_entries(resolved_root, player_identifier=None)
    discovered_paths = {path for path, _player_id, _url in player_entries}
    source_issues: list[StatsCoverageSourceIssue] = list(
        _scan_unreadable_player_source_issues(resolved_root, discovered_paths=discovered_paths)
    )

    team_inventory = build_cached_html_inventory(cache=cache)
    valid_team_entries = [entry for entry in team_inventory.entries if entry.status == "valid"]
    for entry in team_inventory.entries:
        # `invalid_or_unreadable` is unreadable/malformed content; `missing_metadata`
        # is a team-season-shaped filename whose team/season could not be parsed.
        # Both are malformed candidates, not merely uninteresting paths — unlike
        # `unsupported_path` (not team-season shaped at all, e.g. a player page)
        # and `duplicate` (a second valid candidate for an already-seen key),
        # neither of which indicates a problem with the source itself.
        if entry.status in ("invalid_or_unreadable", "missing_metadata"):
            source_issues.append(
                StatsCoverageSourceIssue(
                    cache_path=entry.cache_path,
                    status=entry.status,
                    error_message=entry.error_message,
                )
            )

    mutable_entries: dict[tuple[str, int], _MutableCoverageEntry] = {}
    unexplained: list[StatsCoverageUnexplained] = []
    disagreements: list[StatsCoverageDisagreement] = []
    fingerprint_rows: list[tuple[str, str]] = []

    for cache_path, player_id, _source_url in player_entries:
        html = required_html(cache_path)
        fingerprint_rows.append(
            (_relative_posix_path(cache_path, resolved_root), _digest_of_cached_file(cache_path))
        )

        regular_parsed = parse_player_page_regular_season(html)
        postseason_parsed = parse_player_page_postseason(html)

        if not _has_any_rows(regular_parsed) and not _has_any_rows(postseason_parsed):
            # Decoded as HTML and passed the doctype check, but every supported
            # table is empty across both season types — no real player page is
            # this bare (every player has at least one season row somewhere).
            # Treat it as unusable content (e.g. an error/interstitial page
            # cached under a real player filename) rather than silently
            # contributing zero expectations and staying `is_complete`.
            source_issues.append(
                StatsCoverageSourceIssue(
                    cache_path=str(cache_path),
                    status="invalid_or_unreadable",
                    error_message=(
                        "Cached player-page HTML decoded but contained no supported "
                        "stats tables; likely an error or interstitial page rather "
                        "than real player content."
                    ),
                )
            )
            continue

        regular_aggregate, regular_dnp, regular_unexplained = _classify_aggregate(
            regular_parsed,
            destinations=REGULAR_AGGREGATE_DESTINATIONS,
            player_id=player_id,
            season_type="regular",
        )
        postseason_aggregate, postseason_dnp, postseason_unexplained = _classify_aggregate(
            postseason_parsed,
            destinations=POSTSEASON_AGGREGATE_DESTINATIONS,
            player_id=player_id,
            season_type="postseason",
        )
        postseason_stints = _classify_team_stints(
            postseason_parsed, destinations=POSTSEASON_TEAM_STINT_DESTINATIONS
        )

        unexplained.extend(regular_unexplained)
        unexplained.extend(postseason_unexplained)

        seasons = (
            set(regular_aggregate)
            | regular_dnp
            | set(postseason_aggregate)
            | postseason_dnp
            | set(postseason_stints)
        )
        for year in seasons:
            entry = _entry_for(mutable_entries, player_id, year)
            entry.regular_aggregate |= regular_aggregate.get(year, set())
            entry.postseason_aggregate |= postseason_aggregate.get(year, set())
            entry.postseason_team_stints |= postseason_stints.get(year, set())
            entry.did_not_play_regular = entry.did_not_play_regular or year in regular_dnp
            entry.did_not_play_postseason = entry.did_not_play_postseason or year in postseason_dnp

        disagreements.extend(
            _compare_aggregate_with_normalizer(
                regular_parsed,
                aggregate=regular_aggregate,
                destinations=REGULAR_AGGREGATE_DESTINATIONS,
                player_id=player_id,
                season_type="regular",
                normalize=normalize_player_page_regular_season,
            )
        )
        disagreements.extend(
            _compare_aggregate_with_normalizer(
                postseason_parsed,
                aggregate=postseason_aggregate,
                destinations=POSTSEASON_AGGREGATE_DESTINATIONS,
                player_id=player_id,
                season_type="postseason",
                normalize=normalize_player_page_postseason,
            )
        )

    for entry in valid_team_entries:
        html = read_cached_gzip(Path(entry.cache_path))
        if html is None:
            # Already reported above via team_inventory's invalid_or_unreadable status.
            continue
        fingerprint_rows.append(
            (
                _relative_posix_path(Path(entry.cache_path), resolved_root),
                _digest_of_cached_file(Path(entry.cache_path)),
            )
        )

        parsed = parse_team_season_page(html)
        if not _has_any_rows(parsed):
            # Same reasoning as the player-page guard above: a cached
            # team-season page that decodes but yields zero rows across every
            # supported table is not real content, even though cache_inventory
            # classified it as `valid` (it only checks the doctype and the
            # approved-URL/filename metadata, not table content).
            source_issues.append(
                StatsCoverageSourceIssue(
                    cache_path=entry.cache_path,
                    status="invalid_or_unreadable",
                    error_message=(
                        "Cached team-season HTML decoded but contained no supported "
                        "stats tables; likely an error or interstitial page rather "
                        "than real team-season content."
                    ),
                )
            )
            continue
        assert entry.team_abbreviation is not None
        assert entry.season_end_year is not None
        by_player = _classify_team_season_page(
            parsed,
            page_team=entry.team_abbreviation,
            destinations=REGULAR_TEAM_STINT_DESTINATIONS,
        )
        for player_id, stints in by_player.items():
            coverage_entry = _entry_for(mutable_entries, player_id, entry.season_end_year)
            coverage_entry.regular_team_stints |= stints

    fingerprint_rows.sort(key=lambda row: row[0])
    fingerprint_source = "".join(f"{path}\n{digest}\n" for path, digest in fingerprint_rows)
    fingerprint = StatsCoverageFingerprint(
        digest=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
        player_page_count=len(player_entries),
        team_page_count=len(valid_team_entries),
    )

    final_entries = tuple(
        sorted(
            (entry.to_entry() for entry in mutable_entries.values()),
            key=lambda entry: (entry.basketball_reference_player_id, entry.season_year),
        )
    )
    final_unexplained = tuple(
        sorted(
            unexplained,
            key=lambda item: (
                item.basketball_reference_player_id,
                item.season_year,
                item.season_type,
                item.source_table,
            ),
        )
    )
    final_disagreements = tuple(
        sorted(
            disagreements,
            key=lambda item: (
                item.basketball_reference_player_id,
                item.season_year,
                item.season_type,
                item.source_table,
            ),
        )
    )
    final_source_issues = tuple(sorted(source_issues, key=lambda item: item.cache_path))

    counts = {
        "player_pages": len(player_entries),
        "team_pages": len(valid_team_entries),
        "entries": len(final_entries),
        "regular_aggregate_expectations": sum(len(e.regular_aggregate_tables) for e in final_entries),
        "postseason_aggregate_expectations": sum(len(e.postseason_aggregate_tables) for e in final_entries),
        "regular_team_stint_expectations": sum(len(e.regular_team_stints) for e in final_entries),
        "postseason_team_stint_expectations": sum(len(e.postseason_team_stints) for e in final_entries),
        "did_not_play_regular_seasons": sum(e.did_not_play.regular for e in final_entries),
        "did_not_play_postseason_seasons": sum(e.did_not_play.postseason for e in final_entries),
        "unexplained": len(final_unexplained),
        "disagreements": len(final_disagreements),
        "source_issues": len(final_source_issues),
    }

    return StatsCoverageArtifact(
        cache_root=str(resolved_root),
        parser_contracts={producer: current_parser_version(producer) for producer in PARSER_PRODUCERS},
        cache_fingerprint=fingerprint,
        counts=counts,
        entries=final_entries,
        unexplained=final_unexplained,
        disagreements=final_disagreements,
        source_issues=final_source_issues,
    )


def write_stats_coverage_artifact(artifact: StatsCoverageArtifact, path: str | Path) -> Path:
    """Write the artifact as JSON, atomically, regardless of whether it is complete."""

    final_path = Path(path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(artifact.to_dict(), indent=2, sort_keys=False) + "\n"

    temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(serialized, encoding="utf-8")
        os.replace(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return final_path


def parse_stats_coverage_artifact(data: Mapping[str, object]) -> StatsCoverageArtifact:
    """Reconstruct a `StatsCoverageArtifact` from its JSON-decoded dict form.

    Rejects any `schema_version` other than the one this module currently
    produces; F4E-018 must not silently compare against a shape it does not
    understand.
    """

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        msg = (
            f"Unsupported stats-coverage schema_version: {schema_version!r}; "
            f"this reader only understands {SCHEMA_VERSION}."
        )
        raise StatsCoverageSchemaError(msg)

    fingerprint_data = data["cache_fingerprint"]
    assert isinstance(fingerprint_data, Mapping)
    fingerprint = StatsCoverageFingerprint(
        digest=str(fingerprint_data["digest"]),
        player_page_count=int(fingerprint_data["player_page_count"]),  # type: ignore[arg-type]
        team_page_count=int(fingerprint_data["team_page_count"]),  # type: ignore[arg-type]
    )

    entries = tuple(_entry_from_dict(item) for item in data.get("entries", []))  # type: ignore[union-attr]
    unexplained = tuple(
        StatsCoverageUnexplained(
            basketball_reference_player_id=str(item["basketball_reference_player_id"]),
            season_year=int(item["season_year"]),  # type: ignore[arg-type]
            season_type=item["season_type"],  # type: ignore[arg-type]
            source_table=str(item["source_table"]),
            reason=str(item["reason"]),
        )
        for item in data.get("unexplained", [])  # type: ignore[union-attr]
    )
    disagreements = tuple(
        StatsCoverageDisagreement(
            basketball_reference_player_id=str(item["basketball_reference_player_id"]),
            season_year=int(item["season_year"]),  # type: ignore[arg-type]
            season_type=item["season_type"],  # type: ignore[arg-type]
            source_table=str(item["source_table"]),
            classifier_selected=bool(item["classifier_selected"]),
            normalizer_selected=bool(item["normalizer_selected"]),
            normalizer_reason=str(item["normalizer_reason"]),
        )
        for item in data.get("disagreements", [])  # type: ignore[union-attr]
    )
    source_issues = tuple(
        StatsCoverageSourceIssue(
            cache_path=str(item["cache_path"]),
            status=str(item["status"]),
            error_message=(str(item["error_message"]) if item.get("error_message") is not None else None),
        )
        for item in data.get("source_issues", [])  # type: ignore[union-attr]
    )

    return StatsCoverageArtifact(
        cache_root=str(data["cache_root"]),
        parser_contracts=dict(data.get("parser_contracts", {})),  # type: ignore[arg-type]
        cache_fingerprint=fingerprint,
        counts=dict(data.get("counts", {})),  # type: ignore[arg-type]
        entries=entries,
        unexplained=unexplained,
        disagreements=disagreements,
        source_issues=source_issues,
    )


def _entry_from_dict(item: Mapping[str, object]) -> StatsCoverageEntry:
    did_not_play_data = item.get("did_not_play", {})
    assert isinstance(did_not_play_data, Mapping)
    return StatsCoverageEntry(
        basketball_reference_player_id=str(item["basketball_reference_player_id"]),
        season_year=int(item["season_year"]),  # type: ignore[arg-type]
        regular_aggregate_tables=tuple(item.get("regular_aggregate_tables", [])),  # type: ignore[arg-type]
        postseason_aggregate_tables=tuple(item.get("postseason_aggregate_tables", [])),  # type: ignore[arg-type]
        regular_team_stints=tuple(
            StatsCoverageTeamStint(team_code=str(stint["team_code"]), table=str(stint["table"]))
            for stint in item.get("regular_team_stints", [])  # type: ignore[union-attr]
        ),
        postseason_team_stints=tuple(
            StatsCoverageTeamStint(team_code=str(stint["team_code"]), table=str(stint["table"]))
            for stint in item.get("postseason_team_stints", [])  # type: ignore[union-attr]
        ),
        did_not_play=StatsCoverageDidNotPlay(
            regular=bool(did_not_play_data.get("regular", False)),
            postseason=bool(did_not_play_data.get("postseason", False)),
        ),
    )


@dataclass
class _MutableCoverageEntry:
    basketball_reference_player_id: str
    season_year: int
    regular_aggregate: set[str] = field(default_factory=set)
    postseason_aggregate: set[str] = field(default_factory=set)
    regular_team_stints: set[tuple[str, str]] = field(default_factory=set)
    postseason_team_stints: set[tuple[str, str]] = field(default_factory=set)
    did_not_play_regular: bool = False
    did_not_play_postseason: bool = False

    def to_entry(self) -> StatsCoverageEntry:
        return StatsCoverageEntry(
            basketball_reference_player_id=self.basketball_reference_player_id,
            season_year=self.season_year,
            regular_aggregate_tables=tuple(sorted(self.regular_aggregate)),
            postseason_aggregate_tables=tuple(sorted(self.postseason_aggregate)),
            regular_team_stints=tuple(
                StatsCoverageTeamStint(team_code=team, table=table)
                for team, table in sorted(self.regular_team_stints)
            ),
            postseason_team_stints=tuple(
                StatsCoverageTeamStint(team_code=team, table=table)
                for team, table in sorted(self.postseason_team_stints)
            ),
            did_not_play=StatsCoverageDidNotPlay(
                regular=self.did_not_play_regular,
                postseason=self.did_not_play_postseason,
            ),
        )


def _entry_for(
    entries: dict[tuple[str, int], _MutableCoverageEntry], player_id: str, year: int
) -> _MutableCoverageEntry:
    key = (player_id, year)
    entry = entries.get(key)
    if entry is None:
        entry = _MutableCoverageEntry(basketball_reference_player_id=player_id, season_year=year)
        entries[key] = entry
    return entry


def _classify_aggregate(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    destinations: Mapping[str, str],
    player_id: str,
    season_type: SeasonType,
) -> tuple[dict[int, set[str]], set[int], list[StatsCoverageUnexplained]]:
    """Classify full-season aggregate expectations from parsed source rows.

    Independently re-derives the same selection rule the normalizer applies
    (a multi-team marker row, or exactly one real-team row, is the official
    full-season row) from parsed rows and the shared semantic predicates, so
    a bug in the normalizer's own selection call cannot silently agree with
    this oracle. Disagreements are still surfaced by `_compare_aggregate_with_normalizer`.
    """

    aggregate: dict[int, set[str]] = defaultdict(set)
    did_not_play: set[int] = set()
    unexplained: list[StatsCoverageUnexplained] = []

    for source_table, rows in parsed.items():
        destination = destinations.get(source_table)
        if destination is None:
            continue

        grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            year = season_end_year(row)
            if year is not None:
                grouped[year].append(row)

        for year, season_rows in grouped.items():
            marker_rows = [row for row in season_rows if is_multi_team_marker(parsed_team_code(row))]
            real_rows = [
                row
                for row in season_rows
                if parsed_team_code(row) is not None
                and not is_multi_team_marker(parsed_team_code(row))
                and not is_aggregate_only_team_code(parsed_team_code(row))
                and not is_did_not_play_placeholder(row)
            ]
            placeholder_rows = [row for row in season_rows if is_did_not_play_placeholder(row)]

            if marker_rows or len(real_rows) == 1:
                aggregate[year].add(destination)
            elif not real_rows and placeholder_rows:
                did_not_play.add(year)
            elif not real_rows:
                unexplained.append(
                    StatsCoverageUnexplained(
                        basketball_reference_player_id=player_id,
                        season_year=year,
                        season_type=season_type,
                        source_table=source_table,
                        reason="no_supported_team_row",
                    )
                )
            else:
                unexplained.append(
                    StatsCoverageUnexplained(
                        basketball_reference_player_id=player_id,
                        season_year=year,
                        season_type=season_type,
                        source_table=source_table,
                        reason="ambiguous_multiple_real_team_rows_without_marker",
                    )
                )

    return aggregate, did_not_play, unexplained


def _classify_team_stints(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    destinations: Mapping[str, str],
) -> dict[int, set[tuple[str, str]]]:
    """Classify per-team-stint expectations: every real-team row is its own stint."""

    stints: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for source_table, rows in parsed.items():
        destination = destinations.get(source_table)
        if destination is None:
            continue
        for row in rows:
            year = season_end_year(row)
            team = parsed_team_code(row)
            if year is None or team is None:
                continue
            if is_aggregate_only_team_code(team) or is_multi_team_marker(team):
                continue
            if is_did_not_play_placeholder(row):
                continue
            stints[year].add((team, destination))
    return stints


def _classify_team_season_page(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    page_team: str,
    destinations: Mapping[str, str],
) -> dict[str, set[tuple[str, str]]]:
    """Classify roster and team-stint expectations from one team-season page.

    Every row carrying a `basketball_reference_player_id` is a real player row
    on this team's page; team-season pages load real team rows only into
    `player_team_season_*` tables, so `TOT` (a team-totals summary row, not a
    player) never becomes an expectation here.
    """

    by_player: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for source_table, rows in parsed.items():
        destination = destinations.get(source_table)
        if destination is None:
            continue
        for row in rows:
            player_id = row.get("basketball_reference_player_id")
            if not player_id:
                continue
            team = _row_team_code(row, page_team)
            if is_aggregate_only_team_code(team) or is_multi_team_marker(team):
                continue
            by_player[player_id].add((team, destination))
    return by_player


def _row_team_code(row: Mapping[str, str], page_team: str) -> str:
    for key in _TEAM_ROW_FIELDS:
        value = row.get(key)
        if value and value.strip():
            return value.strip().upper()
    return page_team


def _compare_aggregate_with_normalizer(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    aggregate: dict[int, set[str]],
    destinations: Mapping[str, str],
    player_id: str,
    season_type: SeasonType,
    normalize,  # either normalize_player_page_regular_season or _postseason
) -> list[StatsCoverageDisagreement]:
    normalized = normalize(parsed, basketball_reference_player_id=player_id)
    disagreements: list[StatsCoverageDisagreement] = []
    for selection in normalized.selection_entries:
        if selection.season_year is None:
            continue
        if selection.reason not in _AGGREGATE_DECISION_REASONS:
            # Not an aggregate-row decision: e.g. a postseason team-stint
            # selection, an ignored TOT row, or an out-of-range skip. None of
            # these say anything about whether the aggregate table was
            # expected, so they are not comparison evidence for it.
            continue
        destination = destinations.get(selection.source_table)
        if destination is None:
            continue
        normalizer_selected = selection.status == "selected"
        classifier_selected = destination in aggregate.get(selection.season_year, set())
        if classifier_selected != normalizer_selected:
            disagreements.append(
                StatsCoverageDisagreement(
                    basketball_reference_player_id=player_id,
                    season_year=selection.season_year,
                    season_type=season_type,
                    source_table=selection.source_table,
                    classifier_selected=classifier_selected,
                    normalizer_selected=normalizer_selected,
                    normalizer_reason=selection.reason,
                )
            )
    return disagreements


def _scan_unreadable_player_source_issues(
    cache_root: Path, *, discovered_paths: set[Path]
) -> list[StatsCoverageSourceIssue]:
    """Report player-shaped cache candidates discovery silently dropped.

    A candidate matching the strict filename contract but missing from
    `discovered_paths` is unreadable/malformed content. A candidate that only
    matches the *loose* `players-...html-...html.gz` shape — e.g. an invalid
    player-id fragment or a non-hex/wrong-length digest — never reaches the
    strict regex at all, so it needs its own check; otherwise it stays
    invisible here while an equivalent team-season filename would be reported
    as `missing_metadata` by `cache_inventory`.
    """

    issues: list[StatsCoverageSourceIssue] = []
    for path in sorted(
        cache_root.rglob("*.html.gz"),
        key=lambda value: value.resolve(strict=False).as_posix().lower(),
    ):
        resolved = path.resolve(strict=False)
        if cache_root not in resolved.parents and resolved != cache_root:
            continue
        if "basketball-reference" not in resolved.parts:
            continue
        if resolved in discovered_paths:
            continue
        if player_page_cache._PLAYER_CACHE_FILE_RE.fullmatch(path.name) is not None:
            issues.append(
                StatsCoverageSourceIssue(
                    cache_path=str(resolved),
                    status="invalid_or_unreadable",
                    error_message="Cached player-page HTML file is unreadable or empty.",
                )
            )
        elif player_page_cache._PLAYER_CACHE_LIKE_FILE_RE.fullmatch(path.name) is not None:
            issues.append(
                StatsCoverageSourceIssue(
                    cache_path=str(resolved),
                    status="missing_metadata",
                    error_message=(
                        "Basketball Reference player-page cache path is missing a "
                        "valid player-id or digest segment."
                    ),
                )
            )
    return issues


def _relative_posix_path(path: Path, root: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _digest_of_cached_file(path: Path) -> str:
    """SHA-256 of the raw decompressed bytes, unstripped and untranslated.

    `read_cached_gzip`/`required_html` strip and validate the content for
    parsing purposes, and read in text mode, which applies universal-newline
    translation (CRLF/CR -> LF) — invisible to a text diff but not to a byte
    fingerprint. The fingerprint contract needs the literal decompressed
    bytes, so this reads and hashes in binary mode instead: both a
    trailing-whitespace-only edit and a line-ending-only edit to a cached file
    change the digest. Discovery has already proven this path decodes
    cleanly, so a fresh binary read here cannot fail.
    """

    with gzip.open(path, "rb") as file:
        raw_bytes = file.read()
    return hashlib.sha256(raw_bytes).hexdigest()


def _has_any_rows(parsed: Mapping[str, list[dict[str, str]]]) -> bool:
    return any(rows for rows in parsed.values())


__all__ = [
    "POSTSEASON_AGGREGATE_DESTINATIONS",
    "POSTSEASON_TEAM_STINT_DESTINATIONS",
    "REGULAR_AGGREGATE_DESTINATIONS",
    "REGULAR_TEAM_STINT_DESTINATIONS",
    "SCHEMA_VERSION",
    "PlayerCacheRootNotFoundError",
    "StatsCoverageArtifact",
    "StatsCoverageDidNotPlay",
    "StatsCoverageDisagreement",
    "StatsCoverageEntry",
    "StatsCoverageFingerprint",
    "StatsCoverageSchemaError",
    "StatsCoverageSourceIssue",
    "StatsCoverageTeamStint",
    "StatsCoverageUnexplained",
    "build_stats_coverage_artifact",
    "parse_stats_coverage_artifact",
    "write_stats_coverage_artifact",
]
