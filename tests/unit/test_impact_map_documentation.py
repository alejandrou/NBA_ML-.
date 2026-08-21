"""Pin the `stats` table count documented in IMPACT_MAP.md to the models.

The count is parsed out of the document rather than restated here, so a
change to `src/nba_data/db/models/stats.py` that is not reflected in the
document fails this test instead of drifting silently again.
"""

from __future__ import annotations

import re
from pathlib import Path

import nba_data.db.models  # noqa: F401  (registers models on Base.metadata)
from nba_data.db.base import Base

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPACT_MAP_PATH = REPO_ROOT / "docs" / "architecture" / "IMPACT_MAP.md"

_SCHEMAS_LINE_PATTERN = re.compile(r"`stats` \((\d+) wide tables")


def _documented_stats_table_count() -> int:
    text = IMPACT_MAP_PATH.read_text(encoding="utf-8")
    match = _SCHEMAS_LINE_PATTERN.search(text)
    assert match is not None, (
        "IMPACT_MAP.md no longer has a `stats` (<N> wide tables ...) line for "
        "this test to parse; update the pattern or the document."
    )
    return int(match.group(1))


def test_impact_map_stats_table_count_matches_models() -> None:
    actual_count = sum(
        1 for table in Base.metadata.tables.values() if table.schema == "stats"
    )

    assert _documented_stats_table_count() == actual_count, (
        "IMPACT_MAP.md's documented `stats` table count has drifted from "
        "src/nba_data/db/models/stats.py; update the document."
    )
