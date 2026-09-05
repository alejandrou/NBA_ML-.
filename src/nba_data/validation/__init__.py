"""Data quality checks for normalized NBA data.

Submodule attributes are resolved lazily (PEP 562) rather than imported at
package-init time. `stats_coverage.py` (and any submodule it depends on, such
as `team_season.py`) is a pure, database-free module by design; if this
package eagerly imported `official_stats`/`offline_database` here, merely
importing `nba_data.validation.stats_coverage` would pull SQLAlchemy and the
ORM models into `sys.modules` anyway, since Python always runs a package's
`__init__.py` before any of its submodules. Lazy resolution keeps that cost
paid only by code that actually touches the heavier submodules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nba_data.validation.official_stats import (
        OfficialStatsValidationIssue,
        OfficialStatsValidationReport,
        validate_official_stats,
    )
    from nba_data.validation.offline_database import (
        DEFAULT_PHASE_4D_TABLE_COUNTS,
        OfflineDatabaseValidationExpectations,
        OfflineDatabaseValidationIssue,
        OfflineDatabaseValidationReport,
        validate_offline_database,
    )
    from nba_data.validation.stats_coverage import (
        SCHEMA_VERSION as STATS_COVERAGE_SCHEMA_VERSION,
    )
    from nba_data.validation.stats_coverage import (
        StatsCoverageArtifact,
        StatsCoverageDisagreement,
        StatsCoverageEntry,
        StatsCoverageSchemaError,
        StatsCoverageShapeError,
        StatsCoverageSourceIssue,
        StatsCoverageTeamStint,
        StatsCoverageUnexplained,
        build_stats_coverage_artifact,
        compute_cache_fingerprint,
        parse_stats_coverage_artifact,
        write_stats_coverage_artifact,
    )
    from nba_data.validation.team_season import (
        DataQualityIssue,
        TeamSeasonDataQualityError,
        assert_valid_normalized_team_season_rows,
        validate_normalized_team_season_rows,
    )

__all__ = [
    "DEFAULT_PHASE_4D_TABLE_COUNTS",
    "STATS_COVERAGE_SCHEMA_VERSION",
    "DataQualityIssue",
    "OfflineDatabaseValidationExpectations",
    "OfflineDatabaseValidationIssue",
    "OfflineDatabaseValidationReport",
    "OfficialStatsValidationIssue",
    "OfficialStatsValidationReport",
    "StatsCoverageArtifact",
    "StatsCoverageDisagreement",
    "StatsCoverageEntry",
    "StatsCoverageSchemaError",
    "StatsCoverageShapeError",
    "StatsCoverageSourceIssue",
    "StatsCoverageTeamStint",
    "StatsCoverageUnexplained",
    "TeamSeasonDataQualityError",
    "assert_valid_normalized_team_season_rows",
    "build_stats_coverage_artifact",
    "compute_cache_fingerprint",
    "parse_stats_coverage_artifact",
    "validate_offline_database",
    "validate_official_stats",
    "validate_normalized_team_season_rows",
    "write_stats_coverage_artifact",
]

_ATTRIBUTE_SOURCE_MODULES = {
    "DEFAULT_PHASE_4D_TABLE_COUNTS": "nba_data.validation.offline_database",
    "OfflineDatabaseValidationExpectations": "nba_data.validation.offline_database",
    "OfflineDatabaseValidationIssue": "nba_data.validation.offline_database",
    "OfflineDatabaseValidationReport": "nba_data.validation.offline_database",
    "validate_offline_database": "nba_data.validation.offline_database",
    "OfficialStatsValidationIssue": "nba_data.validation.official_stats",
    "OfficialStatsValidationReport": "nba_data.validation.official_stats",
    "validate_official_stats": "nba_data.validation.official_stats",
    "StatsCoverageArtifact": "nba_data.validation.stats_coverage",
    "StatsCoverageDisagreement": "nba_data.validation.stats_coverage",
    "StatsCoverageEntry": "nba_data.validation.stats_coverage",
    "StatsCoverageSchemaError": "nba_data.validation.stats_coverage",
    "StatsCoverageShapeError": "nba_data.validation.stats_coverage",
    "StatsCoverageSourceIssue": "nba_data.validation.stats_coverage",
    "StatsCoverageTeamStint": "nba_data.validation.stats_coverage",
    "StatsCoverageUnexplained": "nba_data.validation.stats_coverage",
    "build_stats_coverage_artifact": "nba_data.validation.stats_coverage",
    "compute_cache_fingerprint": "nba_data.validation.stats_coverage",
    "parse_stats_coverage_artifact": "nba_data.validation.stats_coverage",
    "write_stats_coverage_artifact": "nba_data.validation.stats_coverage",
    "DataQualityIssue": "nba_data.validation.team_season",
    "TeamSeasonDataQualityError": "nba_data.validation.team_season",
    "assert_valid_normalized_team_season_rows": "nba_data.validation.team_season",
    "validate_normalized_team_season_rows": "nba_data.validation.team_season",
}
_ATTRIBUTE_SOURCE_NAMES = {
    "STATS_COVERAGE_SCHEMA_VERSION": ("nba_data.validation.stats_coverage", "SCHEMA_VERSION"),
}


def __getattr__(name: str) -> object:
    import importlib

    if name in _ATTRIBUTE_SOURCE_NAMES:
        source_module, real_name = _ATTRIBUTE_SOURCE_NAMES[name]
        return getattr(importlib.import_module(source_module), real_name)
    module_name = _ATTRIBUTE_SOURCE_MODULES.get(name)
    if module_name is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    return sorted(__all__)
