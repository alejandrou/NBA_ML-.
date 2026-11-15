"""The 0013 preflight: the revision's own refusal counts plus URL/key agreement.

A stub connection answers by statement shape. The real catalog and the
read-only connection are exercised in
`tests/integration/test_preflight_migration_data_postgres.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from scripts import preflight_migration_data
from sqlalchemy.sql.elements import TextClause

from nba_data.scraping.cache import HtmlCache

PLAYER_URL = "https://www.basketball-reference.com/players/a/abdulma02.html"
BOX_URL = "https://www.basketball-reference.com/boxscores/201410280NOP.html"
PLAYER_KEY = HtmlCache("root").cache_key_for_url(PLAYER_URL)
BOX_KEY = HtmlCache("root").cache_key_for_url(BOX_URL)
MIGRATION = preflight_migration_data._load_migration_0013()


@dataclass
class Answers:
    """Counts by refusal label; (source_url, cache_path) pairs by table."""

    counts: dict[str, int] = field(default_factory=dict)
    pairs: dict[str, list[tuple[str, str]]] = field(default_factory=dict)


class StubResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def scalar_one(self) -> object:
        return self.rows[0][0]

    def all(self) -> list[tuple[object, ...]]:
        return self.rows


class StubConnection:
    def __init__(self, answers: Answers) -> None:
        self.answers = answers
        self.label_by_query = {query: label for label, query in MIGRATION.precondition_counts()}
        self.statements: list[str] = []

    def execute(self, statement: TextClause, parameters: object = None) -> StubResult:
        sql = statement.text
        self.statements.append(sql)
        if sql in self.label_by_query:
            return StubResult([(self.answers.counts.get(self.label_by_query[sql], 0),)])
        if sql.startswith("SELECT DISTINCT source_url, cache_path FROM stats."):
            table = sql.split("FROM stats.", 1)[1].split()[0]
            return StubResult(list(self.answers.pairs.get(table, [])))
        raise AssertionError(f"unexpected statement: {sql!r}")


def _check(answers: Answers) -> tuple[preflight_migration_data.PreconditionReport, StubConnection]:
    connection = StubConnection(answers)
    return preflight_migration_data.check_0013_precondition(connection), connection


@pytest.mark.unit
def test_clean_data_in_both_legacy_formats_passes() -> None:
    report, connection = _check(
        Answers(
            pairs={
                "player_season_totals": [
                    (
                        PLAYER_URL,
                        "C:\\Users\\someone\\repo\\data\\raw\\html\\" + PLAYER_KEY.replace("/", "\\"),
                    )
                ],
                "player_game_totals": [(BOX_URL, "data\\raw\\html\\" + BOX_KEY.replace("/", "\\"))],
                "team_game_totals": [(BOX_URL, BOX_KEY)],
            }
        )
    )

    assert report.passed, report.blockers
    assert "3 distinct (source_url, cache_path) pairs compared" in report.observations
    assert all(statement.lstrip().startswith("SELECT") for statement in connection.statements)


@pytest.mark.unit
@pytest.mark.parametrize(
    "label",
    [
        "stats.player_season_totals: cache_path not reducible to a cache key",
        "stats.player_season_totals: violates ck_stats_player_season_totals_gs_le_g",
        "stats.player_team_postseason_totals: violates "
        "ck_stats_player_team_postseason_totals_pct_range",
    ],
)
def test_each_refusal_count_blocks_with_its_label_and_count(label: str) -> None:
    report, _ = _check(Answers(counts={label: 3}))

    assert not report.passed
    assert report.blockers == (f"{label}: 3",)


@pytest.mark.unit
def test_a_path_naming_a_different_file_than_its_url_blocks() -> None:
    wrong = "data\\raw\\html\\basketball-reference\\players-a-someoneelse.html-0000000000000000.html.gz"
    report, _ = _check(Answers(pairs={"player_season_totals": [(PLAYER_URL, wrong)]}))

    assert not report.passed
    (blocker,) = report.blockers
    assert blocker.startswith("stats.player_season_totals: 1 cache_path value(s) name a different")
    assert PLAYER_KEY in blocker


@pytest.mark.unit
@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("basketball-reference/x.html.gz", "basketball-reference/x.html.gz"),
        ("data\\raw\\html\\basketball-reference\\x.html.gz", "basketball-reference/x.html.gz"),
        (
            "C:\\Users\\u\\repo\\data\\raw\\html\\basketball-reference\\x.html.gz",
            "basketball-reference/x.html.gz",
        ),
        ("/home/u/repo/data/raw/html/basketball-reference/x.html.gz", "basketball-reference/x.html.gz"),
        # Already matches the key grammar, but still names the cache root.
        ("data/raw/html/basketball-reference/x.html.gz", "basketball-reference/x.html.gz"),
    ],
)
def test_the_key_0013_would_store(stored: str, expected: str) -> None:
    assert (
        preflight_migration_data.stored_key_after_0013(stored, marker=MIGRATION.CACHE_ROOT_MARKER)
        == expected
    )


@pytest.mark.unit
def test_a_forward_slash_root_path_passes_when_it_names_the_right_file() -> None:
    report, _ = _check(
        Answers(pairs={"player_season_totals": [(PLAYER_URL, "data/raw/html/" + PLAYER_KEY)]})
    )

    assert report.passed, report.blockers


@pytest.mark.unit
def test_0013_is_a_selectable_revision() -> None:
    assert "0013_portable_lineage_checks" in preflight_migration_data.CHECKS
