"""The stored `cache_path` key: grammar, derivation, and the 0013 pins.

The key grammar lives in `nba_data.domain.cache_key` and is enforced twice: by
`require_cache_key` before every lineage write, and by a `CHECK` on every
lineage table. Revision `0013` freezes the same pattern and the totals checks as
literal text; these tests pin all copies together so they cannot drift.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from nba_data.db import models as _models  # noqa: F401 - registers every table
from nba_data.db.base import Base
from nba_data.db.models import stats as stats_models
from nba_data.domain.cache_key import (
    CACHE_KEY_PATTERN,
    InvalidCacheKeyError,
    is_cache_key,
    require_cache_key,
)
from nba_data.scraping.cache import HtmlCache, relative_cache_key

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_FILE = REPO_ROOT / "alembic" / "versions" / "0013_portable_lineage_checks.py"
BOX_SCORE_URL = "https://www.basketball-reference.com/boxscores/201410280NOP.html"


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0013_under_test", MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    [
        "basketball-reference/boxscores-201410280nop.html-3ab33cd3ff459e0f.html.gz",
        "basketball-reference/players-a-abdulma02.html-82dd3fd413cd9608.html.gz",
        "fixture.html.gz",
        "basketball-reference/Fixture_2.html.gz",
        "a/b/c.html.gz",
    ],
)
def test_valid_keys(key: str) -> None:
    assert is_cache_key(key)
    assert require_cache_key(key) == key


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "C:\\Users\\someone\\data\\raw\\html\\basketball-reference\\x.html.gz",
        "C:/Users/someone/x.html.gz",
        "data\\raw\\html\\basketball-reference\\x.html.gz",
        "/abs/x.html.gz",
        "../x.html.gz",
        "a/../x.html.gz",
        "./x.html.gz",
        "a/./x.html.gz",
        "a//x.html.gz",
        ".hidden.html.gz",
        "x.html",
        "x.html.gz/",
        "a b.html.gz",
        "",
    ],
)
def test_invalid_keys_are_rejected(value: str) -> None:
    assert not is_cache_key(value)
    with pytest.raises(InvalidCacheKeyError):
        require_cache_key(value)


@pytest.mark.unit
def test_key_of_a_url_is_relative_even_under_an_absolute_root(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    assert cache.root_dir.is_absolute()

    key = cache.cache_key_for_url(BOX_SCORE_URL)

    assert key == "basketball-reference/boxscores-201410280nop.html-3ab33cd3ff459e0f.html.gz"
    assert cache.root_dir / key == cache.path_for_url(BOX_SCORE_URL)


@pytest.mark.unit
def test_key_is_the_file_actually_read_not_the_canonical_key_of_a_url(tmp_path: Path) -> None:
    """An explicit `.html.gz` under the root keeps its own name, whatever its URL."""

    root = tmp_path / "cache"

    assert relative_cache_key(root / "fixture.html.gz", root) == "fixture.html.gz"
    assert relative_cache_key(root / "basketball-reference" / "fixture.html.gz", root) == (
        "basketball-reference/fixture.html.gz"
    )


@pytest.mark.unit
def test_relative_and_absolute_inputs_give_the_same_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    relative_root = Path("data") / "raw" / "html"
    relative_file = relative_root / "basketball-reference" / "x.html.gz"
    absolute_root = relative_root.resolve()

    assert relative_cache_key(relative_file.resolve(), relative_root) == (
        "basketball-reference/x.html.gz"
    )
    assert relative_cache_key(relative_file, absolute_root) == "basketball-reference/x.html.gz"


@pytest.mark.unit
@pytest.mark.parametrize("outside", ["elsewhere/x.html.gz", "cache/../x.html.gz", "cache"])
def test_a_path_outside_the_root_is_refused(tmp_path: Path, outside: str) -> None:
    with pytest.raises(InvalidCacheKeyError):
        relative_cache_key(tmp_path / outside, tmp_path / "cache")


@pytest.mark.unit
@pytest.mark.parametrize("name", ["basketball-reference/page.html", "a b.html.gz"])
def test_a_file_under_the_root_with_an_unsupported_name_is_refused(
    tmp_path: Path, name: str
) -> None:
    root = tmp_path / "cache"
    with pytest.raises(InvalidCacheKeyError):
        relative_cache_key(root / name, root)


@pytest.mark.unit
def test_migration_freezes_the_same_key_pattern_and_totals_checks() -> None:
    migration = _migration()

    assert migration.CACHE_KEY_PATTERN == CACHE_KEY_PATTERN
    assert migration.CACHE_KEY_CHECK == stats_models.CACHE_KEY_CHECK
    assert migration.TOTALS_CHECKS == stats_models.TOTALS_CHECKS


@pytest.mark.unit
def test_migration_covers_every_lineage_table_and_every_totals_table() -> None:
    migration = _migration()
    stats_tables = [table for table in Base.metadata.tables.values() if table.schema == "stats"]
    lineage_tables = {table.name for table in stats_tables if "cache_path" in table.c}
    totals_tables = {
        table.name
        for table in stats_tables
        if issubclass(_mapped_class(table.name), stats_models._TotalsColumnsMixin)
    }

    assert set(migration.LINEAGE_TABLES) == lineage_tables
    assert len(migration.LINEAGE_TABLES) == len(lineage_tables) == 35
    assert set(migration.TOTALS_TABLES) == totals_tables
    assert len(totals_tables) == 4


@pytest.mark.unit
def test_models_declare_the_constraints_the_migration_creates() -> None:
    migration = _migration()
    declared = {
        (table.name, constraint.name): str(getattr(constraint, "sqltext", ""))
        for table in Base.metadata.tables.values()
        if table.schema == "stats"
        for constraint in table.constraints
        if constraint.name
    }

    for table in migration.LINEAGE_TABLES:
        name = migration.cache_key_check_name(table)
        assert declared[(table, name)] == migration.CACHE_KEY_CHECK
    for table in migration.TOTALS_TABLES:
        for suffix, condition in migration.TOTALS_CHECKS.items():
            assert declared[(table, migration.totals_check_name(table, suffix))] == condition


def _mapped_class(table_name: str) -> type:
    for mapper in Base.registry.mappers:
        if mapper.local_table.name == table_name and mapper.local_table.schema == "stats":
            return mapper.class_
    raise AssertionError(f"no mapped class for stats.{table_name}")
