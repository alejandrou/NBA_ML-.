from __future__ import annotations

import gzip
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from nba_data.domain.team_codes import is_synthetic_team_code
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.normalizers.team_season import normalize_team_season_page
from nba_data.scraping.parsers.team_season import parse_team_season_page
from nba_data.validation.team_season import DataQualityIssue, validate_normalized_team_season_rows

_TEAM_SEASON_PATH_RE = re.compile(r"^/teams/(?P<team>[A-Z]{3})/(?P<year>[0-9]{4})\.html$")
_TEAM_ABBREVIATION_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class OfflineTeamSeasonSource:
    source_type: Literal["url", "path"]
    team_abbreviation: str
    season_year: int
    url: str | None = None
    path: Path | None = None

    @classmethod
    def from_url(cls, url: str) -> OfflineTeamSeasonSource:
        team, year = _parse_team_season_url(url)
        return cls(
            source_type="url",
            team_abbreviation=team,
            season_year=year,
            url=url,
        )

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        team_abbreviation: str,
        season_year: int,
    ) -> OfflineTeamSeasonSource:
        cached_path = Path(path)
        _validate_gzip_path_name(cached_path)
        return cls(
            source_type="path",
            team_abbreviation=_normalize_team_abbreviation(team_abbreviation),
            season_year=_normalize_season_year(season_year),
            path=cached_path,
        )


@dataclass(frozen=True)
class OfflineTeamSeasonSourceContext:
    source_type: str
    team_abbreviation: str
    season_year: int
    cache_path: str | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "team_abbreviation": self.team_abbreviation,
            "season_year": self.season_year,
            "url": self.url,
            "cache_path": self.cache_path,
        }


@dataclass(frozen=True)
class OfflineTeamSeasonEntryResult:
    source: OfflineTeamSeasonSourceContext
    status: Literal["validated", "failed"]
    parsed_row_count: int = 0
    normalized_rows: tuple[dict[str, Any], ...] = ()
    quarantined_rows: tuple[dict[str, Any], ...] = ()
    validation_issues: tuple[DataQualityIssue, ...] = ()
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source.to_dict(),
            "status": self.status,
            "parsed_row_count": self.parsed_row_count,
            "validated_row_count": len(self.normalized_rows),
            "quarantined_row_count": len(self.quarantined_rows),
            "normalized_rows": list(self.normalized_rows),
            "quarantined_rows": list(self.quarantined_rows),
            "validation_issues": [_issue_to_dict(issue) for issue in self.validation_issues],
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class OfflineTeamSeasonProcessingReport:
    total_inputs: int
    validated_entries: int
    failed_entries: int
    validated_row_count: int
    entries: tuple[OfflineTeamSeasonEntryResult, ...]

    @property
    def validated_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            row
            for entry in self.entries
            if entry.status == "validated"
            for row in entry.normalized_rows
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "total_inputs": self.total_inputs,
            "validated_entries": self.validated_entries,
            "failed_entries": self.failed_entries,
            "validated_row_count": self.validated_row_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def process_offline_team_season_sources(
    sources: Iterable[OfflineTeamSeasonSource],
    *,
    cache: HtmlCache,
    max_workers: int = 1,
    required_tables: set[str] | None = None,
    require_stable_player_id: bool = True,
) -> OfflineTeamSeasonProcessingReport:
    if max_workers < 1:
        msg = "max_workers must be at least 1"
        raise ValueError(msg)

    source_tuple = tuple(sources)
    worker = partial(
        _process_one_source,
        cache=cache,
        required_tables=required_tables,
        require_stable_player_id=require_stable_player_id,
    )

    if max_workers == 1:
        entries = tuple(worker(source) for source in source_tuple)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            entries = tuple(executor.map(worker, source_tuple))

    return _build_report(entries)


def _process_one_source(
    source: OfflineTeamSeasonSource,
    *,
    cache: HtmlCache,
    required_tables: set[str] | None,
    require_stable_player_id: bool,
) -> OfflineTeamSeasonEntryResult:
    context = _fallback_context(source)
    try:
        context, cache_path = _resolve_source_context(source, cache)
        html = _read_cached_gzip(cache_path)
        parsed = parse_team_season_page(html)
        normalized_rows = normalize_team_season_page(
            parsed,
            team_abbreviation=context.team_abbreviation,
            season_year=context.season_year,
        )
        validation_issues = validate_normalized_team_season_rows(
            normalized_rows,
            required_tables=required_tables,
            require_stable_player_id=require_stable_player_id,
        )
        if validation_issues:
            return OfflineTeamSeasonEntryResult(
                source=context,
                status="failed",
                parsed_row_count=len(normalized_rows),
                quarantined_rows=tuple(normalized_rows),
                validation_issues=tuple(validation_issues),
                error_message=(
                    f"Validation failed for cached team-season HTML with "
                    f"{len(validation_issues)} issue(s)."
                ),
            )

        return OfflineTeamSeasonEntryResult(
            source=context,
            status="validated",
            parsed_row_count=len(normalized_rows),
            normalized_rows=tuple(normalized_rows),
        )
    except Exception as exc:
        return OfflineTeamSeasonEntryResult(
            source=context,
            status="failed",
            error_message=str(exc),
        )


def _resolve_source_context(
    source: OfflineTeamSeasonSource,
    cache: HtmlCache,
) -> tuple[OfflineTeamSeasonSourceContext, Path]:
    if source.source_type == "url":
        if source.url is None:
            msg = "URL source requires source.url"
            raise ValueError(msg)
        team, year = _parse_team_season_url(source.url)
        source_team = _normalize_team_abbreviation(source.team_abbreviation)
        source_year = _normalize_season_year(source.season_year)
        if source_team != team or source_year != year:
            msg = "URL source metadata must match the team-season URL"
            raise ValueError(msg)
        cache_path = cache.path_for_url(source.url)
        return (
            OfflineTeamSeasonSourceContext(
                source_type="url",
                team_abbreviation=team,
                season_year=year,
                url=source.url,
                cache_path=str(cache_path),
            ),
            cache_path,
        )

    if source.source_type == "path":
        if source.path is None:
            msg = "Path source requires source.path"
            raise ValueError(msg)
        team = _normalize_team_abbreviation(source.team_abbreviation)
        year = _normalize_season_year(source.season_year)
        cache_path = _resolve_explicit_cache_path(source.path, cache.root_dir)
        return (
            OfflineTeamSeasonSourceContext(
                source_type="path",
                team_abbreviation=team,
                season_year=year,
                cache_path=str(cache_path),
            ),
            cache_path,
        )

    msg = "source.source_type must be 'url' or 'path'"
    raise ValueError(msg)


def _resolve_explicit_cache_path(path: Path, cache_root: str | Path) -> Path:
    _validate_gzip_path_name(path)
    root = Path(cache_root).resolve(strict=False)

    direct = path.resolve(strict=False)
    if _is_under_root(direct, root):
        return direct

    if not path.is_absolute():
        under_root = (Path(cache_root) / path).resolve(strict=False)
        if _is_under_root(under_root, root):
            return under_root

    msg = f"Explicit cached HTML path must stay under cache root: {path}"
    raise ValueError(msg)


def _read_cached_gzip(path: Path) -> str:
    if not path.exists():
        msg = f"Cached HTML file not found: {path}"
        raise FileNotFoundError(msg)
    if not path.is_file():
        msg = f"Cached HTML path is not a file: {path}"
        raise FileNotFoundError(msg)
    with gzip.open(path, "rt", encoding="utf-8") as file:
        return file.read()


def _build_report(
    entries: tuple[OfflineTeamSeasonEntryResult, ...],
) -> OfflineTeamSeasonProcessingReport:
    return OfflineTeamSeasonProcessingReport(
        total_inputs=len(entries),
        validated_entries=sum(entry.status == "validated" for entry in entries),
        failed_entries=sum(entry.status == "failed" for entry in entries),
        validated_row_count=sum(len(entry.normalized_rows) for entry in entries),
        entries=entries,
    )


def _fallback_context(source: OfflineTeamSeasonSource) -> OfflineTeamSeasonSourceContext:
    return OfflineTeamSeasonSourceContext(
        source_type=source.source_type,
        team_abbreviation=source.team_abbreviation,
        season_year=source.season_year,
        url=source.url,
        cache_path=str(source.path) if source.path is not None else None,
    )


def _parse_team_season_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    match = _TEAM_SEASON_PATH_RE.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or host != "basketball-reference.com"
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        msg = "source.url must be an explicit Basketball Reference team-season URL"
        raise ValueError(msg)

    team = _normalize_team_abbreviation(match.group("team"))
    return team, int(match.group("year"))


def _normalize_team_abbreviation(team_abbreviation: str) -> str:
    team = team_abbreviation.strip().upper()
    if _TEAM_ABBREVIATION_RE.fullmatch(team) is None:
        msg = "team_abbreviation must be a three-letter team code"
        raise ValueError(msg)
    if is_synthetic_team_code(team):
        msg = f"{team} is an aggregate marker, not a real team"
        raise ValueError(msg)
    return team


def _normalize_season_year(season_year: int) -> int:
    if isinstance(season_year, bool) or not isinstance(season_year, int) or season_year < 1:
        msg = "season_year must be a positive integer"
        raise ValueError(msg)
    return season_year


def _validate_gzip_path_name(path: Path) -> None:
    if not path.name.endswith(".html.gz"):
        msg = "Explicit cached HTML path must end in .html.gz"
        raise ValueError(msg)


def _is_under_root(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _issue_to_dict(issue: DataQualityIssue) -> dict[str, object]:
    return {
        "code": issue.code,
        "message": issue.message,
        "row_index": issue.row_index,
        "source_table": issue.source_table,
    }
