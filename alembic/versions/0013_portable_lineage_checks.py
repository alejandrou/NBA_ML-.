"""Store portable cache keys as lineage and add totals checks (audit H-07, H-12).

`cache_path` held whatever path a loader happened to read: absolute Windows
paths with the OS user name on the player-page tables, relative backslash paths
on the box-score tables. This revision rewrites every value to the key of the
same file relative to the cache root (`basketball-reference/<file>.html.gz`)
and adds a `CHECK` that only such keys are stored. The rewrite keeps the file:
it strips everything up to and including the cache root `data/raw/html/`,
never recomputes a key from `source_url`. Every value that contains the root is
rewritten, including forward-slash relative paths that already match the key
grammar; values without it are left alone, so a downgrade followed by an
upgrade is safe.

It also adds four cheap checks to each of the four `totals` tables. Making
`core.players.basketball_reference_player_id` `NOT NULL` (the rest of H-12) is
left to a `shared` card: the app track's tests seed a player without one.

The upgrade **fails closed**. Before changing anything it counts, per table,
values that cannot be reduced to a key and rows that would violate each new
check, and raises listing every non-zero count. Every table is
locked first so nothing can arrive between the count and the change, and the
whole revision runs in one transaction: a failure leaves the database at `0012`.

The rewrite is SQL, so `created_at` and `updated_at` are not touched.

The downgrade drops the checks. It **cannot** restore the
original absolute paths, which were machine-specific; stored keys stay keys.

The check conditions are frozen here as literal text. `tests/unit/test_cache_key.py`
pins them to `nba_data.db.models.stats` and `nba_data.domain.cache_key`.

Revision ID: 0013_portable_lineage_checks
Revises: 0012_ml_predictions
Create Date: 2026-11-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_portable_lineage_checks"
down_revision: str | None = "0012_ml_predictions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CACHE_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*\.html\.gz$"
CACHE_KEY_CHECK = f"cache_path ~ '{CACHE_KEY_PATTERN}'"
CACHE_ROOT_MARKER = "data/raw/html/"

# Any value naming the cache root is rewritten: `\` becomes `/`, then everything
# up to the last cache root marker is dropped. This includes forward-slash paths
# such as `data/raw/html/basketball-reference/x.html.gz`, which already match the
# key grammar but are not keys. A value without the marker is kept as it is.
_NORMALIZED_PATH = r"replace(cache_path, '\', '/')"
_HAS_ROOT_MARKER = f"(strpos({_NORMALIZED_PATH}, '{CACHE_ROOT_MARKER}') > 0)"
_REWRITTEN_KEY = f"regexp_replace({_NORMALIZED_PATH}, '^.*{CACHE_ROOT_MARKER}', '')"
_CONVERTIBLE = (
    f"(CASE WHEN {_HAS_ROOT_MARKER} THEN {_REWRITTEN_KEY} ~ '{CACHE_KEY_PATTERN}' "
    f"ELSE {CACHE_KEY_CHECK} END)"
)

LINEAGE_TABLES = (
    "player_game_totals",
    "player_postseason_adj_shooting",
    "player_postseason_advanced",
    "player_postseason_pbp",
    "player_postseason_per_game",
    "player_postseason_per_minute",
    "player_postseason_per_poss",
    "player_postseason_shooting",
    "player_postseason_totals",
    "player_season_adj_shooting",
    "player_season_advanced",
    "player_season_pbp",
    "player_season_per_game",
    "player_season_per_minute",
    "player_season_per_poss",
    "player_season_shooting",
    "player_season_totals",
    "player_team_postseason_adj_shooting",
    "player_team_postseason_advanced",
    "player_team_postseason_pbp",
    "player_team_postseason_per_game",
    "player_team_postseason_per_minute",
    "player_team_postseason_per_poss",
    "player_team_postseason_shooting",
    "player_team_postseason_totals",
    "player_team_season_adj_shooting",
    "player_team_season_advanced",
    "player_team_season_pbp",
    "player_team_season_per_game",
    "player_team_season_per_minute",
    "player_team_season_per_poss",
    "player_team_season_roster",
    "player_team_season_shooting",
    "player_team_season_totals",
    "team_game_totals",
)

TOTALS_TABLES = (
    "player_season_totals",
    "player_team_season_totals",
    "player_postseason_totals",
    "player_team_postseason_totals",
)

TOTALS_CHECKS = {
    "non_negative": (
        "g >= 0 AND gs >= 0 AND mp >= 0 AND fg >= 0 AND fga >= 0 AND fg3 >= 0 "
        "AND fg3a >= 0 AND fg2 >= 0 AND fg2a >= 0 AND ft >= 0 AND fta >= 0 "
        "AND orb >= 0 AND drb >= 0 AND trb >= 0 AND ast >= 0 AND stl >= 0 "
        "AND blk >= 0 AND tov >= 0 AND pf >= 0 AND pts >= 0 AND tpl_dbl >= 0"
    ),
    "gs_le_g": "gs <= g",
    "makes_le_attempts": "fg <= fga AND fg2 <= fg2a AND fg3 <= fg3a AND ft <= fta",
    "pct_range": (
        "fg_pct BETWEEN 0 AND 1 AND fg2_pct BETWEEN 0 AND 1 "
        "AND fg3_pct BETWEEN 0 AND 1 AND ft_pct BETWEEN 0 AND 1 "
        "AND efg_pct BETWEEN 0 AND 1.5"
    ),
}


def cache_key_check_name(table: str) -> str:
    return f"ck_stats_{table}_cache_path_key"


def totals_check_name(table: str, suffix: str) -> str:
    return f"ck_stats_{table}_{suffix}"


def precondition_counts() -> list[tuple[str, str]]:
    """(label, SQL returning one count) for everything the upgrade refuses.

    A NULL check condition is not a violation, exactly as for a `CHECK`.
    """

    queries = [
        (
            f"stats.{table}: cache_path not reducible to a cache key",
            f"SELECT count(*) FROM stats.{table} WHERE NOT {_CONVERTIBLE}",
        )
        for table in LINEAGE_TABLES
    ]
    queries.extend(
        (
            f"stats.{table}: violates {totals_check_name(table, suffix)}",
            f"SELECT count(*) FROM stats.{table} WHERE NOT ({condition})",
        )
        for table in TOTALS_TABLES
        for suffix, condition in TOTALS_CHECKS.items()
    )
    return queries


def _refuse_on_violations_sql() -> str:
    lines = ["DO $body$", "DECLARE", "    n bigint;", "    problems text := '';", "BEGIN"]
    for label, query in precondition_counts():
        quoted_label = label.replace("'", "''")
        into_n = query.replace("SELECT count(*) FROM", "SELECT count(*) INTO n FROM", 1)
        lines.append(f"    {into_n};")
        lines.append(
            f"    IF n > 0 THEN problems := problems || '{quoted_label}: ' || n || '; '; END IF;"
        )
    lines.append("    IF problems <> '' THEN")
    lines.append("        RAISE EXCEPTION 'Refusing to apply 0013: %', problems;")
    lines.append("    END IF;")
    lines.append("END")
    lines.append("$body$")
    return "\n".join(lines)


def upgrade() -> None:
    tables = ", ".join(f"stats.{table}" for table in LINEAGE_TABLES)
    op.execute(f"LOCK TABLE {tables} IN ACCESS EXCLUSIVE MODE")
    op.execute(_refuse_on_violations_sql())

    for table in LINEAGE_TABLES:
        op.execute(
            f"UPDATE stats.{table} SET cache_path = {_REWRITTEN_KEY} "
            f"WHERE {_HAS_ROOT_MARKER}"
        )
        op.create_check_constraint(
            cache_key_check_name(table), table, CACHE_KEY_CHECK, schema="stats"
        )

    for table in TOTALS_TABLES:
        for suffix, condition in TOTALS_CHECKS.items():
            op.create_check_constraint(
                totals_check_name(table, suffix), table, condition, schema="stats"
            )


def downgrade() -> None:
    for table in reversed(TOTALS_TABLES):
        for suffix in reversed(TOTALS_CHECKS):
            op.drop_constraint(
                totals_check_name(table, suffix), table, type_="check", schema="stats"
            )
    for table in reversed(LINEAGE_TABLES):
        op.drop_constraint(cache_key_check_name(table), table, type_="check", schema="stats")
