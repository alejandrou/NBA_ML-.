"""Recount player-page normalized candidates straight from the local HTML cache.

This script answers exactly one question and refuses to imply more: **how many
normalized candidate rows does the player-page normalizer emit from the cache,
and for every input row it does not turn into a candidate, why not?**

It measures *candidates, not persisted rows*. Whether a candidate becomes a row
in `stats.*` also depends on `core.seasons`, `core.players`, and
`core.player_seasons` — all database state this script deliberately never opens.
Proving that candidates land is the future rebuild-and-diff card's job.

Enumeration is done by globbing the cache for `players-*.html.gz` rather than by
reusing the backfill's discovery helper, so that a discovery-side filename
contract regression shows up as a page-count mismatch instead of silently
shrinking the measurement.

Usage:
    uv run python scripts/recount_player_page_candidates.py
    uv run python scripts/recount_player_page_candidates.py --limit 25
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from nba_data.config.settings import get_settings
from nba_data.scraping.normalizers.player_page import (
    PlayerPageNormalizationResult,
    normalize_player_page_postseason,
    normalize_player_page_regular_season,
)
from nba_data.scraping.parsers.player_page import (
    parse_player_page_postseason,
    parse_player_page_regular_season,
)

# The player-page archive as acquired. Stated so that a regression to the old
# 2,515-page discovery contract is visible in the report rather than silent.
EXPECTED_PLAYER_PAGES = 2551

PLAYER_CACHE_GLOB = "players-*.html.gz"
_PLAYER_CACHE_FILE_RE = re.compile(
    r"^players-(?P<initial>[a-z])-(?P<player_id>[a-z0-9]+)\.html-[0-9a-f]{16}\.html\.gz$",
    re.IGNORECASE,
)

_MEASURES = (
    "normalized candidate rows emitted by the player-page normalizer from cached "
    "HTML; NOT persisted database rows, and NOT a claim that any candidate "
    "resolves to a core.player_seasons grain"
)

_PER_ROW_SKIP_REASONS = frozenset({"invalid_season_row", "missing_team_code"})
_RANGE_SKIP_REASONS = frozenset({"before_start_year", "after_end_year"})
_TOT_SKIP_REASON = "ignored_tot_rows"
_STINT_SELECT_REASON = "selected_real_team_postseason_row"
_SYNTHETIC_AGGREGATE_REASON = "selected_multi_team_aggregate"
_AGGREGATE_SELECT_REASONS = frozenset({_SYNTHETIC_AGGREGATE_REASON, "selected_single_team_row"})
_AGGREGATE_SKIP_REASONS = frozenset({"no_supported_team_row", "ambiguous_multiple_real_team_rows"})


def _nested_counter() -> defaultdict[str, defaultdict[str, Counter[str]]]:
    return defaultdict(lambda: defaultdict(Counter))


@dataclass
class ScopeTally:
    """Per-scope ledger: what was emitted, what was dropped, and whether it balances."""

    scope: str
    candidates: defaultdict[str, defaultdict[str, Counter[str]]] = field(default_factory=_nested_counter)
    not_emitted: defaultdict[str, defaultdict[str, Counter[str]]] = field(default_factory=_nested_counter)
    season_group_outcomes: defaultdict[str, defaultdict[str, Counter[str]]] = field(
        default_factory=_nested_counter
    )
    input_rows: Counter[str] = field(default_factory=Counter)
    contributing_input_rows: Counter[str] = field(default_factory=Counter)
    dropped_input_rows: Counter[str] = field(default_factory=Counter)
    anomalies: list[str] = field(default_factory=list)

    def record_input_rows(self, parsed: Mapping[str, list[dict[str, str]]]) -> None:
        for source_table, parsed_rows in parsed.items():
            self.input_rows[source_table] += len(parsed_rows)

    def add_candidate(self, source_table: str, season: str, stat_scope: str) -> None:
        self.candidates[source_table][season][stat_scope] += 1

    def add_drop(self, source_table: str, season: str, reason: str, count: int) -> None:
        if count <= 0:
            return
        self.not_emitted[source_table][season][reason] += count
        self.dropped_input_rows[source_table] += count

    def to_dict(self) -> dict[str, object]:
        input_total = sum(self.input_rows.values())
        contributing_total = sum(self.contributing_input_rows.values())
        dropped_total = sum(self.dropped_input_rows.values())
        unattributed = input_total - contributing_total - dropped_total
        return {
            "scope": self.scope,
            "candidate_totals_by_stat_scope": _sum_leaf_counters(self.candidates),
            "candidates_by_source_table_and_season": _dump_nested(self.candidates),
            "not_emitted_totals_by_reason": _sum_leaf_counters(self.not_emitted),
            "not_emitted_by_source_table_and_season": _dump_nested(self.not_emitted),
            "season_group_outcomes_by_source_table_and_season": _dump_nested(self.season_group_outcomes),
            "season_group_outcome_totals": _sum_leaf_counters(self.season_group_outcomes),
            "reconciliation": {
                "input_rows_parsed": input_total,
                "input_rows_producing_at_least_one_candidate": contributing_total,
                "input_rows_not_emitted_with_a_reason": dropped_total,
                "input_rows_unattributed": unattributed,
                "balanced": unattributed == 0 and not self.anomalies,
                "input_rows_by_source_table": dict(sorted(self.input_rows.items())),
            },
            "anomalies": self.anomalies,
        }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cache_root = args.cache_root or (get_settings().scraper_cache_dir / "basketball-reference")
    cache_root = cache_root.resolve(strict=False)
    if not cache_root.is_dir():
        print(f"Player-page cache root does not exist: {cache_root}", file=sys.stderr)
        return 1

    started = perf_counter()
    pages = _enumerate_player_pages(cache_root)
    pages_enumerated = len(pages)
    if args.limit is not None:
        pages = pages[: args.limit]

    regular = ScopeTally("regular_season")
    postseason = ScopeTally("postseason")
    unreadable_pages: list[dict[str, str]] = []
    unparseable_filenames: list[str] = []

    for index, path in enumerate(pages, start=1):
        match = _PLAYER_CACHE_FILE_RE.fullmatch(path.name)
        if match is None:
            unparseable_filenames.append(path.name)
            continue
        player_id = match.group("player_id").lower()

        html = _read_cached_gzip(path)
        if html is None:
            unreadable_pages.append({"cache_path": str(path), "reason": "unreadable_or_empty"})
            continue

        try:
            parsed_regular = parse_player_page_regular_season(html)
            regular.record_input_rows(parsed_regular)
            _tally_regular_season(
                regular,
                normalize_player_page_regular_season(
                    parsed_regular, basketball_reference_player_id=player_id
                ),
            )

            parsed_postseason = parse_player_page_postseason(html)
            postseason.record_input_rows(parsed_postseason)
            _tally_postseason(
                postseason,
                normalize_player_page_postseason(
                    parsed_postseason, basketball_reference_player_id=player_id
                ),
            )
        except Exception as exc:  # noqa: BLE001 - one bad page must not lose the run
            unreadable_pages.append({"cache_path": str(path), "reason": f"failed: {exc}"})
            continue

        if args.progress and index % 250 == 0:
            print(f"  ... {index}/{len(pages)} pages", file=sys.stderr)

    report = {
        "measures": _MEASURES,
        "measures_persisted_rows": False,
        "claims_grain_resolution": False,
        "reads_database": False,
        "cache_root": str(cache_root),
        "cache_glob": PLAYER_CACHE_GLOB,
        "enumeration_method": "direct cache glob, not the backfill discovery helper",
        "player_pages_enumerated": pages_enumerated,
        "player_pages_expected": EXPECTED_PLAYER_PAGES,
        "player_pages_match_expected": pages_enumerated == EXPECTED_PLAYER_PAGES,
        "player_pages_processed": len(pages) - len(unreadable_pages) - len(unparseable_filenames),
        "player_pages_limit_applied": args.limit,
        "unparseable_cache_filenames": unparseable_filenames,
        "unreadable_or_failed_pages": unreadable_pages,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "scopes": {
            "regular_season": regular.to_dict(),
            "postseason": postseason.to_dict(),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    _print_summary(report)
    return 0


def _tally_regular_season(tally: ScopeTally, result: PlayerPageNormalizationResult) -> None:
    """Attribute every parsed regular-season row to a candidate or to a named reason.

    The aggregate-only path emits at most one candidate per season group, so a
    selected entry covering N rows contributes one candidate and N-1 rows that
    lost the full-season selection.
    """

    for entry in result.selection_entries:
        season = _season_key(entry.season_year)
        if entry.status == "selected":
            tally.add_candidate(entry.source_table, season, "player_season_aggregate")
            tally.contributing_input_rows[entry.source_table] += 1
            tally.season_group_outcomes[entry.source_table][season][entry.reason] += 1
            tally.add_drop(
                entry.source_table,
                season,
                "superseded_by_full_season_selection",
                entry.row_count - 1,
            )
            continue

        tally.add_drop(entry.source_table, season, entry.reason, entry.row_count)
        if entry.reason not in _RANGE_SKIP_REASONS and entry.reason != "ignored_invalid_or_unsupported_rows":
            tally.season_group_outcomes[entry.source_table][season][entry.reason] += 1


def _tally_postseason(tally: ScopeTally, result: PlayerPageNormalizationResult) -> None:
    """Attribute every parsed postseason row to a candidate or to a named reason.

    The postseason path is not one-candidate-per-row: a real-team row can be
    emitted twice (once as the season aggregate, once as its own team stint), so
    rows are reconciled by *which input rows contributed at least one candidate*
    rather than by counting emitted candidates.
    """

    group_size: dict[tuple[str, str], int] = {}
    group_tot: Counter[tuple[str, str]] = Counter()
    group_stints: Counter[tuple[str, str]] = Counter()
    group_synthetic_aggregate: set[tuple[str, str]] = set()

    for entry in result.selection_entries:
        season = _season_key(entry.season_year)
        key = (entry.source_table, season)

        if entry.reason in _PER_ROW_SKIP_REASONS or entry.reason in _RANGE_SKIP_REASONS:
            tally.add_drop(entry.source_table, season, entry.reason, entry.row_count)
            continue

        if entry.reason == _TOT_SKIP_REASON:
            group_tot[key] += entry.row_count
            tally.add_drop(entry.source_table, season, _TOT_SKIP_REASON, entry.row_count)
            continue

        if entry.reason == _STINT_SELECT_REASON:
            tally.add_candidate(entry.source_table, season, "player_team_postseason")
            tally.contributing_input_rows[entry.source_table] += 1
            group_stints[key] += 1
            continue

        if entry.reason in _AGGREGATE_SELECT_REASONS:
            tally.add_candidate(entry.source_table, season, "player_postseason_aggregate")
            group_size[key] = entry.row_count
            tally.season_group_outcomes[entry.source_table][season][entry.reason] += 1
            if entry.reason == _SYNTHETIC_AGGREGATE_REASON:
                # A synthetic marker row is its own input row; a single real-team
                # row is already counted as the stint it also produces.
                tally.contributing_input_rows[entry.source_table] += 1
                group_synthetic_aggregate.add(key)
            continue

        if entry.reason in _AGGREGATE_SKIP_REASONS:
            group_size[key] = entry.row_count
            tally.season_group_outcomes[entry.source_table][season][entry.reason] += 1
            continue

        tally.anomalies.append(f"unrecognized postseason selection reason: {entry.reason!r}")

    for key, size in group_size.items():
        source_table, season = key
        accounted = group_tot[key] + group_stints[key] + (1 if key in group_synthetic_aggregate else 0)
        residual = size - accounted
        if residual < 0:
            tally.anomalies.append(
                f"postseason group {source_table}/{season} over-accounted by {-residual} row(s)"
            )
            continue
        tally.add_drop(source_table, season, "superseded_multi_team_marker_row", residual)


def _enumerate_player_pages(cache_root: Path) -> list[Path]:
    return sorted(cache_root.rglob(PLAYER_CACHE_GLOB), key=lambda path: path.as_posix().lower())


def _read_cached_gzip(path: Path) -> str | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as file:
            html = file.read()
    except OSError:
        return None
    cleaned = html.strip()
    return cleaned if cleaned else None


def _season_key(season_year: int | None) -> str:
    return "unknown" if season_year is None else str(season_year)


def _dump_nested(nested: Mapping[str, Mapping[str, Counter[str]]]) -> dict[str, dict[str, dict[str, int]]]:
    return {
        source_table: {
            season: dict(sorted(counter.items()))
            for season, counter in sorted(seasons.items())
        }
        for source_table, seasons in sorted(nested.items())
    }


def _sum_leaf_counters(nested: Mapping[str, Mapping[str, Counter[str]]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for seasons in nested.values():
        for counter in seasons.values():
            totals.update(counter)
    return dict(sorted(totals.items()))


def _print_summary(report: dict[str, object]) -> None:
    print(f"Measures: {report['measures']}.")
    print(f"Cache root: {report['cache_root']}")
    print(
        f"Player pages enumerated: {report['player_pages_enumerated']} "
        f"(expected {report['player_pages_expected']}; "
        f"match={report['player_pages_match_expected']})"
    )
    scopes: dict[str, dict[str, object]] = report["scopes"]  # type: ignore[assignment]
    for scope_name, scope in scopes.items():
        reconciliation: dict[str, object] = scope["reconciliation"]  # type: ignore[assignment]
        print(f"\n[{scope_name}]")
        print(f"  candidates: {scope['candidate_totals_by_stat_scope']}")
        print(f"  not emitted: {scope['not_emitted_totals_by_reason']}")
        print(f"  reconciliation: {reconciliation}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
        help="Player-page cache root. Defaults to <scraper_cache_dir>/basketball-reference.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/player_page_candidate_recount.json"),
        help="Where to write the JSON breakdown.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N pages. For smoke-testing the script, not for evidence.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print progress to stderr every 250 pages.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
