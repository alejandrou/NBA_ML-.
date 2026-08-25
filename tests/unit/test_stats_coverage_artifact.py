from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

import pytest

import nba_data.validation.stats_coverage as stats_coverage
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.player_page_cache import PlayerCacheRootNotFoundError
from nba_data.validation.official_stats import STATS_TABLE_SPECS
from nba_data.validation.stats_coverage import (
    POSTSEASON_AGGREGATE_DESTINATIONS,
    POSTSEASON_TEAM_STINT_DESTINATIONS,
    REGULAR_AGGREGATE_DESTINATIONS,
    REGULAR_TEAM_STINT_DESTINATIONS,
    SCHEMA_VERSION,
    StatsCoverageSchemaError,
    StatsCoverageShapeError,
    build_stats_coverage_artifact,
    compute_cache_fingerprint,
    parse_stats_coverage_artifact,
    write_stats_coverage_artifact,
)

HARDEN_REGULAR = Path("tests/fixtures/html/player_page_harden_regular_season.html").read_text(
    encoding="utf-8"
)
HARDEN_POSTSEASON = Path("tests/fixtures/html/player_page_harden_postseason.html").read_text(
    encoding="utf-8"
)
BROWN_POSTSEASON = Path("tests/fixtures/html/player_page_brown_postseason.html").read_text(
    encoding="utf-8"
)
MILLER_DID_NOT_PLAY = Path("tests/fixtures/html/player_page_miller_did_not_play.html").read_text(
    encoding="utf-8"
)
MCGRATH_DID_NOT_PLAY = Path("tests/fixtures/html/player_page_mcgrath_did_not_play.html").read_text(
    encoding="utf-8"
)
SHORT_ID_CENTURY_ROLLOVER = Path(
    "tests/fixtures/html/player_page_short_id_regular_season.html"
).read_text(encoding="utf-8")
FIVE_TEAM_SEASON = Path("tests/fixtures/html/player_page_five_team_regular_season.html").read_text(
    encoding="utf-8"
)
TEAM_SEASON_BOS_2000 = Path("tests/fixtures/html/team_season_coverage_bos_2000.html").read_text(
    encoding="utf-8"
)

BOS_2000_URL = "https://www.basketball-reference.com/teams/BOS/2000.html"


def _write_player_page(cache: HtmlCache, player_id: str, html: str) -> Path:
    url = f"https://www.basketball-reference.com/players/{player_id[0]}/{player_id}.html"
    path = cache.path_for_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)
    return path


def _write_team_season_page(cache: HtmlCache, html: str) -> Path:
    path = cache.path_for_url(BOS_2000_URL)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)
    return path


def _merge_tables(*htmls: str) -> str:
    """Concatenate the `<table>`/comment content of several player-page fixtures.

    Real Basketball Reference player pages carry regular and postseason tables
    on the *same* page, but these fixtures were authored one page at a time.
    This stitches their bodies together into one page for tests that need
    both season types (or two different seasons) present at once.
    """

    bodies: list[str] = []
    for html in htmls:
        start = html.index("<body>") + len("<body>")
        end = html.index("</body>")
        bodies.append(html[start:end])
    return "<!doctype html><html><body>" + "\n".join(bodies) + "</body></html>"


def _is_type_checking_guard(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _executable_import_nodes(body: list[ast.stmt]) -> list[ast.Import | ast.ImportFrom]:
    """Imports that actually run, skipping `if TYPE_CHECKING:` bodies.

    A plain `ast.walk` would count a `TYPE_CHECKING`-guarded import as reachable
    even though it never executes — exactly the gap that let the real
    `player_page_cache` -> `player_page_acquisition` -> SQLAlchemy chain hide
    behind this module's own clean top-level import list. This only recurses
    into constructs that always run: it does not enter `if TYPE_CHECKING:` (the
    only guard used in this codebase to defer an import), so it stays a
    reasonable proxy for "does importing this module actually execute this".
    """

    nodes: list[ast.Import | ast.ImportFrom] = []
    for node in body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            nodes.append(node)
        elif isinstance(node, ast.If) and _is_type_checking_guard(node.test):
            continue
        else:
            for field in ("body", "orelse", "finalbody"):
                child_body = getattr(node, field, None)
                if child_body:
                    nodes.extend(_executable_import_nodes(child_body))
    return nodes


def _module_imports(module_name: str, *, src_root: Path) -> set[str]:
    """Return the module/package names one module actually imports at runtime."""

    path = src_root / Path(*module_name.split(".")).with_suffix(".py")
    if not path.exists():
        path = src_root / Path(*module_name.split(".")) / "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    names: set[str] = set()
    for node in _executable_import_nodes(tree.body):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif node.module is not None:
            # `from . import x` / `from .y import z` (level > 0) never occurs in this
            # codebase (every import is absolute), so relative imports are out of scope.
            names.add(node.module)
    return names


def _transitive_imports(module_name: str, *, src_root: Path) -> tuple[set[str], set[str]]:
    """BFS the `nba_data.*` import graph reachable from `module_name` (inclusive).

    Returns `(nba_data modules visited, every import name seen anywhere in that
    graph)` — the second set is what a purity check must scan, since a
    forbidden import (`sqlalchemy`, `httpx`, ...) is a leaf, never itself
    something to recurse into.
    """

    visited_modules: set[str] = set()
    all_imports: set[str] = set()
    queue = [module_name]
    while queue:
        current = queue.pop()
        if current in visited_modules:
            continue
        visited_modules.add(current)
        imports = _module_imports(current, src_root=src_root)
        all_imports.update(imports)
        for name in imports:
            if name.startswith("nba_data.") or name == "nba_data":
                # A submodule import (`import nba_data.a.b`) also runs every
                # ancestor package's `__init__.py`, so walk those too.
                parts = name.split(".")
                for depth in range(2, len(parts) + 1):
                    ancestor = ".".join(parts[:depth])
                    if ancestor not in visited_modules:
                        queue.append(ancestor)
    return visited_modules, all_imports


@pytest.mark.unit
def test_stats_coverage_has_no_database_or_network_import_anywhere_in_its_dependency_graph() -> None:
    """A regression test for a real bug: `stats_coverage` importing `player_page_cache`,
    which imported `player_page_acquisition`, which imported SQLAlchemy, ORM models,
    and the scraping HTTP client — two hops away from `stats_coverage.py`'s own
    source, so a check of only its direct imports missed it. This walks the whole
    reachable `nba_data.*` import graph instead of just one module's own imports.
    """

    # stats_coverage.__file__ is `.../src/nba_data/validation/stats_coverage.py`;
    # parents[2] is `src/`, the root each `nba_data.*` dotted name resolves against.
    src_root = Path(stats_coverage.__file__).resolve().parents[2]
    assert (src_root / "nba_data").is_dir()
    visited_modules, all_imports = _transitive_imports(
        "nba_data.validation.stats_coverage", src_root=src_root
    )

    forbidden_prefixes = ("nba_data.db",)
    forbidden_exact = {"sqlalchemy", "httpx"}
    violations = {
        name
        for name in all_imports
        if name in forbidden_exact or any(name.startswith(f"{p}.") or name == p for p in forbidden_prefixes)
    }
    assert violations == set()

    # Sanity: the BFS actually reached a real, non-trivial slice of the codebase,
    # so an empty `violations` set is not just an artifact of an empty walk. And
    # confirm `player_page_cache` no longer reaches `player_page_acquisition` at
    # all — that edge was the real bug; it should be gone, not merely "clean".
    assert "nba_data.scraping.player_page_cache" in visited_modules
    assert "nba_data.scraping.normalizers.player_page" in visited_modules
    assert "nba_data.scraping.player_page_acquisition" not in visited_modules


@pytest.mark.unit
def test_stats_coverage_module_has_no_database_or_network_imports() -> None:
    source = Path(stats_coverage.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_names.add(node.module)

    for forbidden in ("sqlalchemy", "httpx", "nba_data.db"):
        assert not any(name == forbidden or name.startswith(f"{forbidden}.") for name in imported_names), (
            forbidden,
            imported_names,
        )
    for forbidden_substring in ("BasketballReferenceClient", "import requests", ".commit(", ".rollback("):
        assert forbidden_substring not in source


@pytest.mark.unit
def test_destination_table_maps_match_official_stats_specs() -> None:
    regular_team_stint = {s.full_name for s in STATS_TABLE_SPECS if s.season_type == "regular" and s.family == "team_stint"}
    regular_aggregate = {s.full_name for s in STATS_TABLE_SPECS if s.season_type == "regular" and s.family == "aggregate"}
    postseason_aggregate = {s.full_name for s in STATS_TABLE_SPECS if s.season_type == "postseason" and s.family == "aggregate"}
    postseason_team_stint = {s.full_name for s in STATS_TABLE_SPECS if s.season_type == "postseason" and s.family == "team_stint"}

    assert set(REGULAR_TEAM_STINT_DESTINATIONS.values()) == regular_team_stint
    assert set(REGULAR_AGGREGATE_DESTINATIONS.values()) == regular_aggregate
    assert set(POSTSEASON_AGGREGATE_DESTINATIONS.values()) == postseason_aggregate
    assert set(POSTSEASON_TEAM_STINT_DESTINATIONS.values()) == postseason_team_stint
    assert len(STATS_TABLE_SPECS) == 33


@pytest.mark.unit
def test_build_stats_coverage_artifact_refuses_a_missing_cache_root(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(PlayerCacheRootNotFoundError):
        build_stats_coverage_artifact(cache_root=missing)


@pytest.mark.unit
def test_content_that_does_not_look_like_html_is_reported_not_silently_accepted(
    tmp_path: Path,
) -> None:
    """Regression test: a decoded-but-non-HTML player page used to pass discovery
    silently (any non-empty text was accepted), yielding a complete-looking
    artifact with zero entries instead of a reported, build-failing source issue.
    """

    cache = HtmlCache(tmp_path / "cache")
    garbage_path = _write_player_page(cache, "hardeja01", "just some plain text, not a page")

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert len(artifact.source_issues) == 1
    assert artifact.source_issues[0].cache_path == str(garbage_path.resolve())


@pytest.mark.unit
def test_invalid_utf8_content_is_reported_rather_than_raising(tmp_path: Path) -> None:
    """Regression test: a gzip stream that decompresses to invalid UTF-8 used to
    raise `UnicodeDecodeError` out of discovery before any artifact was written,
    instead of being treated like any other unreadable candidate.
    """

    cache = HtmlCache(tmp_path / "cache")
    url = "https://www.basketball-reference.com/players/h/hardeja01.html"
    path = cache.path_for_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as file:
        file.write(b"\xff\xfe\x00not valid utf-8")

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert len(artifact.source_issues) == 1
    assert artifact.source_issues[0].cache_path == str(path.resolve())


@pytest.mark.unit
def test_truncated_player_gzip_file_is_reported_not_raised(tmp_path: Path) -> None:
    """Regression test: a gzip stream truncated mid-stream (the trailing CRC/ISIZE
    bytes cut off) raises `EOFError`, not `OSError` or `UnicodeDecodeError` -- so
    it slipped past `read_cached_gzip`'s except clause and crashed the whole
    build before any diagnostic artifact could be written.
    """

    cache = HtmlCache(tmp_path / "cache")
    url = "https://www.basketball-reference.com/players/h/hardeja01.html"
    path = cache.path_for_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    compressed = gzip.compress(HARDEN_REGULAR.encode("utf-8"))
    path.write_bytes(compressed[: len(compressed) - 8])

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert len(artifact.source_issues) == 1
    assert artifact.source_issues[0].cache_path == str(path.resolve())


@pytest.mark.unit
def test_html_error_page_with_no_stats_tables_is_reported_not_silently_complete(
    tmp_path: Path,
) -> None:
    """Regression test: content that passes the doctype/html-prefix check but
    carries none of the supported stats tables (e.g. a cached error or
    interstitial page) used to be accepted as a legitimate, zero-expectation
    page for both player and team sources -- `is_complete=True` with a page
    counted, zero entries, and zero source issues.
    """

    error_page = "<!doctype html><html><body><h1>Page Not Found</h1></body></html>"
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "hardeja01", error_page)
    _write_team_season_page(cache, error_page)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert len(artifact.source_issues) == 2
    assert {issue.status for issue in artifact.source_issues} == {"invalid_or_unreadable"}


@pytest.mark.unit
def test_player_cache_filename_with_a_malformed_digest_is_reported_as_missing_metadata(
    tmp_path: Path,
) -> None:
    """Regression test: the source-issue scanner used the same strict filename
    regex as discovery, so a player-shaped filename with a malformed digest
    segment (not 16 hex characters) matched neither the strict regex nor
    anything else, and vanished from the scan entirely -- while an equivalent
    malformed team-season filename was reported as `missing_metadata`.
    """

    cache = HtmlCache(tmp_path / "cache")
    path = (
        cache.root_dir / "basketball-reference" / "players-h-hardeja01.html-not-a-valid-digest.html.gz"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(HARDEN_REGULAR)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert [issue.status for issue in artifact.source_issues] == ["missing_metadata"]


@pytest.mark.unit
def test_team_season_page_with_a_malformed_filename_is_reported_as_missing_metadata(
    tmp_path: Path,
) -> None:
    """A team-season-shaped filename (`teams-...`) whose team/season the strict
    cache-inventory regex cannot parse is `missing_metadata`: malformed, not
    merely a different kind of file, so it must fail the build too.
    """

    cache = HtmlCache(tmp_path / "cache")
    path = cache.root_dir / "basketball-reference" / "teams-boss-2000.html-0123456789abcdef.html.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(TEAM_SEASON_BOS_2000)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert [issue.status for issue in artifact.source_issues] == ["missing_metadata"]


@pytest.mark.unit
def test_multi_team_trade_yields_regular_aggregate_expectations_for_every_table(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "hardeja01", HARDEN_REGULAR)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    assert len(artifact.entries) == 1
    entry = artifact.entries[0]
    assert entry.basketball_reference_player_id == "hardeja01"
    assert entry.season_year == 2021
    assert set(entry.regular_aggregate_tables) == set(REGULAR_AGGREGATE_DESTINATIONS.values())
    assert entry.regular_team_stints == ()
    assert entry.did_not_play.regular is False


@pytest.mark.unit
def test_a_row_with_no_team_code_and_no_did_not_play_marker_is_unexplained_not_selected(
    tmp_path: Path,
) -> None:
    """Regression test: a row that is neither a real team row, a multi-team
    marker, `TOT`, nor a recognized did-not-play placeholder (no team-code
    field at all, and an `age` value that is not the placeholder marker) used
    to still count as a "real" row, so a single such row created a false
    `stats.player_season_totals` expectation instead of `unexplained`.
    """

    html = (
        "<!doctype html><html><body>"
        '<table id="totals_stats"><thead><tr>'
        '<th data-stat="season">Season</th><th data-stat="age">Age</th>'
        "</tr></thead><tbody>"
        '<tr><th data-stat="season">2015-16</th><td data-stat="age">30</td></tr>'
        "</tbody></table></body></html>"
    )
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "noteamp01", html)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    assert len(artifact.unexplained) == 1
    assert artifact.unexplained[0].reason == "no_supported_team_row"


@pytest.mark.unit
def test_five_team_marker_season_yields_aggregate_expectation(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "vaughja01", FIVE_TEAM_SEASON)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    entry = artifact.entries[0]
    assert entry.season_year == 2020
    assert "stats.player_season_totals" in entry.regular_aggregate_tables


@pytest.mark.unit
def test_short_player_id_and_century_rollover_season_are_both_handled(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "qizh01", SHORT_ID_CENTURY_ROLLOVER)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    entry = artifact.entries[0]
    assert entry.basketball_reference_player_id == "qizh01"
    # `1999-00` ends in 2000, not 1900.
    assert entry.season_year == 2000
    assert entry.regular_aggregate_tables == ("stats.player_season_totals",)


@pytest.mark.unit
@pytest.mark.parametrize(
    "reason",
    (
        "Did not play -",
        "Did not play - injury",
        "Did not play - retired",
    ),
)
def test_did_not_play_reason_strings_suppress_only_the_matching_aggregate(
    tmp_path: Path, reason: str
) -> None:
    html = MCGRATH_DID_NOT_PLAY.replace("Did not play - other pro league", reason)
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "mcgrada01", html)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    entry = artifact.entries[0]
    assert entry.season_year == 2013
    assert entry.regular_aggregate_tables == ()
    assert entry.did_not_play.regular is True
    assert entry.did_not_play.postseason is False


@pytest.mark.unit
def test_did_not_play_placeholder_does_not_erase_a_real_row_sharing_its_season(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "millemi01", MILLER_DID_NOT_PLAY)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    entry = artifact.entries[0]
    assert entry.season_year == 2004
    assert set(entry.regular_aggregate_tables) == set(REGULAR_AGGREGATE_DESTINATIONS.values())
    assert entry.did_not_play.regular is False


@pytest.mark.unit
def test_player_season_carries_regular_and_postseason_expectations_together(
    tmp_path: Path,
) -> None:
    combined = _merge_tables(HARDEN_REGULAR, HARDEN_POSTSEASON)
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "hardeja01", combined)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    assert len(artifact.entries) == 1
    entry = artifact.entries[0]
    assert entry.season_year == 2021
    assert entry.regular_aggregate_tables != ()
    assert entry.postseason_aggregate_tables != ()
    assert ("BRK", "stats.player_team_postseason_per_game") in [
        (stint.team_code, stint.table) for stint in entry.postseason_team_stints
    ]
    assert artifact.disagreements == ()


@pytest.mark.unit
def test_regular_did_not_play_coexists_with_real_postseason_expectations(
    tmp_path: Path,
) -> None:
    postseason_same_season = BROWN_POSTSEASON.replace("2023-24", "2012-13")
    combined = _merge_tables(MCGRATH_DID_NOT_PLAY, postseason_same_season)
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "mcgrada01", combined)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    assert len(artifact.entries) == 1
    entry = artifact.entries[0]
    assert entry.season_year == 2013
    assert entry.did_not_play.regular is True
    assert entry.regular_aggregate_tables == ()
    assert entry.postseason_aggregate_tables != ()
    assert entry.postseason_team_stints != ()
    assert artifact.disagreements == ()


@pytest.mark.unit
def test_single_team_postseason_stint_does_not_produce_false_disagreements(
    tmp_path: Path,
) -> None:
    """Regression test: for a single-team postseason, the normalizer emits two
    `status="selected"` entries per table for the same row — one for the
    aggregate decision (`selected_single_team_row`) and one for the team-stint
    row (`selected_real_team_postseason_row`). The latter was compared against
    the aggregate-expectation map as if it were an aggregate signal, and since
    the classifier correctly expects the aggregate table for a single real
    team, every one of the checked-in Brown fixture's three tables produced a
    false disagreement.
    """

    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "brownja02", BROWN_POSTSEASON)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    assert artifact.disagreements == ()
    entry = artifact.entries[0]
    assert entry.postseason_aggregate_tables != ()


@pytest.mark.unit
def test_regular_team_season_page_yields_roster_and_team_stint_expectations_and_ignores_team_totals(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_team_season_page(cache, TEAM_SEASON_BOS_2000)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert artifact.is_complete
    assert len(artifact.entries) == 1
    entry = artifact.entries[0]
    assert entry.basketball_reference_player_id == "piercpa01"
    assert entry.season_year == 2000
    stints = {(stint.team_code, stint.table) for stint in entry.regular_team_stints}
    assert stints == {
        ("BOS", "stats.player_team_season_roster"),
        ("BOS", "stats.player_team_season_totals"),
    }


@pytest.mark.unit
def test_tot_never_becomes_an_expectation_on_either_page_kind(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_team_season_page(cache, TEAM_SEASON_BOS_2000)
    _write_player_page(cache, "hardeja01", HARDEN_REGULAR)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    for entry in artifact.entries:
        assert entry.basketball_reference_player_id != "TOT"
        for stint in (*entry.regular_team_stints, *entry.postseason_team_stints):
            assert stint.team_code != "TOT"


@pytest.mark.unit
def test_unexplained_season_is_reported_and_still_writes_the_artifact(tmp_path: Path) -> None:
    # Two real team rows sharing a season, no multi-team marker: ambiguous.
    html = (
        "<!doctype html><html><body>"
        '<table id="totals_stats"><thead><tr>'
        '<th data-stat="season">Season</th><th data-stat="team_id">Tm</th>'
        '</tr></thead><tbody>'
        '<tr><th data-stat="season">2015-16</th><td data-stat="team_id">DAL</td></tr>'
        '<tr><th data-stat="season">2015-16</th><td data-stat="team_id">MIA</td></tr>'
        "</tbody></table></body></html>"
    )
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "ambigpl01", html)
    output_path = tmp_path / "coverage.json"

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)
    write_stats_coverage_artifact(artifact, output_path)

    assert not artifact.is_complete
    assert len(artifact.unexplained) == 1
    assert artifact.unexplained[0].reason == "ambiguous_multiple_real_team_rows_without_marker"
    assert output_path.exists()
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["unexplained"][0]["reason"] == "ambiguous_multiple_real_team_rows_without_marker"


@pytest.mark.unit
def test_unreadable_candidates_of_either_page_kind_are_reported_and_fail_the_build(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path / "cache")

    # A player-shaped filename that discovery's own gzip read will reject.
    corrupt_player_path = _write_player_page(cache, "hardeja01", HARDEN_REGULAR)
    corrupt_player_path.write_bytes(b"not a gzip stream")

    # A team-shaped filename cache_inventory itself classifies as unreadable.
    corrupt_team_path = _write_team_season_page(cache, TEAM_SEASON_BOS_2000)
    corrupt_team_path.write_bytes(b"not a gzip stream")

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)

    assert not artifact.is_complete
    assert artifact.entries == ()
    statuses = {issue.status for issue in artifact.source_issues}
    assert statuses == {"invalid_or_unreadable"}
    reported_paths = {issue.cache_path for issue in artifact.source_issues}
    assert str(corrupt_player_path.resolve()) in reported_paths
    assert any(corrupt_team_path.name in path for path in reported_paths)


@pytest.mark.unit
def test_fingerprint_is_stable_and_reacts_to_html_and_path_changes(tmp_path: Path) -> None:
    cache_a = HtmlCache(tmp_path / "cache_a")
    _write_player_page(cache_a, "hardeja01", HARDEN_REGULAR)
    _write_team_season_page(cache_a, TEAM_SEASON_BOS_2000)

    first = build_stats_coverage_artifact(cache_root=cache_a.root_dir)
    second = build_stats_coverage_artifact(cache_root=cache_a.root_dir)
    assert first.cache_fingerprint.digest == second.cache_fingerprint.digest
    assert first.cache_fingerprint.player_page_count == 1
    assert first.cache_fingerprint.team_page_count == 1

    cache_b = HtmlCache(tmp_path / "cache_b")
    _write_player_page(cache_b, "hardeja01", HARDEN_REGULAR.replace("1083", "1084"))
    _write_team_season_page(cache_b, TEAM_SEASON_BOS_2000)
    third = build_stats_coverage_artifact(cache_root=cache_b.root_dir)
    assert third.cache_fingerprint.digest != first.cache_fingerprint.digest


@pytest.mark.unit
def test_fingerprint_reacts_to_a_trailing_newline_the_semantic_artifact_ignores(
    tmp_path: Path,
) -> None:
    """Regression test: `read_cached_gzip`/`required_html` strip whitespace for
    parsing purposes, and the fingerprint used to hash that already-stripped
    string — so a cached file that changed only by a trailing newline produced
    an identical digest, even though the artifact's contract is "SHA-256 of the
    decompressed HTML", not of some normalized form of it.
    """

    cache_a = HtmlCache(tmp_path / "cache_a")
    _write_player_page(cache_a, "hardeja01", HARDEN_REGULAR)
    first = build_stats_coverage_artifact(cache_root=cache_a.root_dir)

    cache_b = HtmlCache(tmp_path / "cache_b")
    _write_player_page(cache_b, "hardeja01", HARDEN_REGULAR + "\n\n   \n")
    second = build_stats_coverage_artifact(cache_root=cache_b.root_dir)

    # The semantic artifact is unaffected (whitespace-only difference)...
    assert first.entries == second.entries
    # ...but the fingerprint, which must reflect the literal decompressed
    # bytes, is not.
    assert first.cache_fingerprint.digest != second.cache_fingerprint.digest


@pytest.mark.unit
def test_fingerprint_reacts_to_line_ending_changes_not_just_content(tmp_path: Path) -> None:
    """Regression test: the fingerprint used to hash a text-mode read of the
    decompressed content, which applies universal-newline translation
    (CRLF/CR -> LF) invisibly. Two cached files differing only by line ending
    therefore produced the same digest, even though the artifact's stated
    contract is "SHA-256 of the decompressed HTML" -- the literal bytes, not
    a newline-normalized form of them. Writes raw bytes directly (bypassing
    any platform-dependent text-mode translation on write) so both variants'
    on-disk content is exactly controlled.
    """

    url = "https://www.basketball-reference.com/players/h/hardeja01.html"

    cache_a = HtmlCache(tmp_path / "cache_a")
    path_a = cache_a.path_for_url(url)
    path_a.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path_a, "wb") as file:
        file.write(HARDEN_REGULAR.encode("utf-8"))
    first = build_stats_coverage_artifact(cache_root=cache_a.root_dir)

    cache_b = HtmlCache(tmp_path / "cache_b")
    path_b = cache_b.path_for_url(url)
    path_b.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path_b, "wb") as file:
        file.write(HARDEN_REGULAR.replace("\n", "\r\n").encode("utf-8"))
    second = build_stats_coverage_artifact(cache_root=cache_b.root_dir)

    # Parsing sees identical logical content (universal newlines on read)...
    assert first.entries == second.entries
    # ...but the fingerprint, which must reflect the literal decompressed
    # bytes, is not.
    assert first.cache_fingerprint.digest != second.cache_fingerprint.digest


@pytest.mark.unit
def test_compute_cache_fingerprint_matches_the_build_path_for_a_non_empty_cache(tmp_path: Path) -> None:
    """`compute_cache_fingerprint` (the F4E-018 freshness-recompute path) must
    agree with the fingerprint `build_stats_coverage_artifact` embeds, over a
    cache that actually has player *and* team pages in it -- not just the
    degenerate empty-cache case, where both paths trivially produce the hash
    of zero rows and a divergence in either discovery loop would go unnoticed.
    """

    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "hardeja01", HARDEN_REGULAR)
    _write_team_season_page(cache, TEAM_SEASON_BOS_2000)

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)
    recomputed = compute_cache_fingerprint(cache.root_dir)

    assert recomputed == artifact.cache_fingerprint
    assert artifact.cache_fingerprint.player_page_count > 0
    assert artifact.cache_fingerprint.team_page_count > 0


@pytest.mark.unit
def test_write_then_parse_round_trips_the_artifact(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "hardeja01", HARDEN_REGULAR)
    output_path = tmp_path / "coverage.json"

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)
    write_stats_coverage_artifact(artifact, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    parsed = parse_stats_coverage_artifact(data)
    assert parsed.entries == artifact.entries
    assert parsed.cache_fingerprint == artifact.cache_fingerprint


@pytest.mark.unit
def test_parse_stats_coverage_artifact_rejects_an_unknown_schema_version() -> None:
    with pytest.raises(StatsCoverageSchemaError):
        parse_stats_coverage_artifact({"schema_version": 2})


def _minimal_artifact_dict(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "cache_root": "/fake",
        "parser_contracts": {},
        "cache_fingerprint": {"digest": "0" * 64, "player_page_count": 0, "team_page_count": 0},
        "counts": {},
        "entries": entries,
        "unexplained": [],
        "disagreements": [],
        "source_issues": [],
    }


@pytest.mark.unit
def test_parse_stats_coverage_artifact_rejects_a_non_string_table_name() -> None:
    """Regression test: `regular_aggregate_tables` used to be cast straight into a
    tuple with no per-element check, so a mixed-type list like
    `["stats.player_season_totals", 1]` was accepted as-is and only blew up later
    as a bare `TypeError` when the comparator tried to `sorted()` the mismatched
    key tuples -- instead of failing cleanly with `coverage_artifact_invalid`.
    """

    artifact = _minimal_artifact_dict(
        [
            {
                "basketball_reference_player_id": "brownja02",
                "season_year": 2024,
                "regular_aggregate_tables": ["stats.player_season_totals", 1],
            }
        ]
    )
    with pytest.raises(StatsCoverageShapeError):
        parse_stats_coverage_artifact(artifact)


@pytest.mark.unit
def test_parse_stats_coverage_artifact_rejects_a_non_string_team_stint_field() -> None:
    artifact = _minimal_artifact_dict(
        [
            {
                "basketball_reference_player_id": "brownja02",
                "season_year": 2024,
                "regular_team_stints": [{"team_code": "BOS", "table": 1}],
            }
        ]
    )
    with pytest.raises(StatsCoverageShapeError):
        parse_stats_coverage_artifact(artifact)


@pytest.mark.unit
def test_write_stats_coverage_artifact_is_atomic_and_leaves_no_temp_file(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_player_page(cache, "hardeja01", HARDEN_REGULAR)
    output_path = tmp_path / "reports" / "coverage.json"

    artifact = build_stats_coverage_artifact(cache_root=cache.root_dir)
    written_path = write_stats_coverage_artifact(artifact, output_path)

    assert written_path == output_path
    assert output_path.exists()
    leftover_temp_files = list(output_path.parent.glob(".*.tmp"))
    assert leftover_temp_files == []
