"""Neutral domain vocabulary shared by scraping, validation, and the database.

Modules here describe what a value *means* in basketball terms. They import
nothing from `nba_data.scraping`, `nba_data.validation`, or `nba_data.db`, so
every layer can depend on them without creating a new layering edge.
"""

from nba_data.domain.team_codes import (
    AGGREGATE_ONLY_TEAM_CODE,
    MARKER_SUFFIX,
    MIN_MULTI_TEAM_COUNT,
    is_aggregate_only_team_code,
    is_multi_team_marker,
    is_synthetic_team_code,
    multi_team_count,
    multi_team_marker_sql,
    normalize_team_code,
    reject_synthetic_team_code_sql,
    synthetic_team_code_sql,
)

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
