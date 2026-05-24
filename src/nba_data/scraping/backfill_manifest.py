from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nba_data.scraping.cache import HtmlCache

SUPPORTED_PAGE_TYPE = "team_season"
MAX_INITIAL_TEAM_SEASON_URLS = 5
MAX_DEFAULT_REQUESTS_PER_MINUTE = 10
MAX_ABSOLUTE_REQUESTS_PER_MINUTE = 20
WRITE_TARGET = "HtmlCache .html.gz"

_TEAM_SEASON_PATH_RE = re.compile(r"^/teams/(?P<team>[A-Z]{3})/(?P<year>[0-9]{4})\.html$")


class ManifestValidationError(ValueError):
    """Raised when a raw HTML backfill manifest is not safe to plan."""


@dataclass(frozen=True)
class BackfillManifestEntry:
    page_type: str
    url: str
    team: str
    season_end_year: int


@dataclass(frozen=True)
class BackfillManifest:
    manifest_id: str
    status: str
    approved_by_owner: bool
    approved_at: str
    scope_page_type: str
    scope_max_urls: int
    requests_per_minute: int
    max_requests_per_minute: int
    write_target: str
    entries: tuple[BackfillManifestEntry, ...]


@dataclass(frozen=True)
class DryRunEntry:
    page_type: str
    url: str
    cache_path: str
    cache_status: str
    estimated_live_request_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "page_type": self.page_type,
            "url": self.url,
            "cache_path": self.cache_path,
            "cache_status": self.cache_status,
            "estimated_live_request_count": self.estimated_live_request_count,
        }


@dataclass(frozen=True)
class DryRunReport:
    manifest_id: str
    total_entries: int
    cache_hits: int
    cache_misses: int
    estimated_live_request_count: int
    entries: tuple[DryRunEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "total_entries": self.total_entries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "estimated_live_request_count": self.estimated_live_request_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_backfill_manifest(path: str | Path) -> BackfillManifest:
    manifest_path = Path(path)
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Manifest JSON is invalid: {exc.msg}"
        raise ManifestValidationError(msg) from exc

    if not isinstance(raw_manifest, Mapping):
        msg = "manifest must be a JSON object"
        raise ManifestValidationError(msg)

    return validate_backfill_manifest(raw_manifest)


def validate_backfill_manifest(raw_manifest: Mapping[str, Any]) -> BackfillManifest:
    manifest_id = _require_non_empty_str(raw_manifest, "manifest_id", "manifest")
    status = _require_non_empty_str(raw_manifest, "status", "manifest")
    if status != "approved":
        msg = "manifest.status must be 'approved' before dry-run planning"
        raise ManifestValidationError(msg)

    _require_true(raw_manifest, "approved_by_owner", "manifest")
    approved_at = _require_non_empty_str(raw_manifest, "approved_at", "manifest")

    scope = _require_mapping(raw_manifest, "scope", "manifest")
    scope_page_type = _require_non_empty_str(scope, "page_type", "scope")
    if scope_page_type != SUPPORTED_PAGE_TYPE:
        msg = "scope.page_type must be 'team_season'"
        raise ManifestValidationError(msg)
    scope_max_urls = _require_int(scope, "max_urls", "scope")
    if scope_max_urls < 1 or scope_max_urls > MAX_INITIAL_TEAM_SEASON_URLS:
        msg = "scope.max_urls must be between 1 and 5 for the initial pilot"
        raise ManifestValidationError(msg)

    policy = _require_mapping(raw_manifest, "acquisition_policy", "manifest")
    _require_true(policy, "cache_first", "acquisition_policy")
    _require_true(policy, "sequential", "acquisition_policy")
    requests_per_minute = _require_int(policy, "requests_per_minute", "acquisition_policy")
    if requests_per_minute < 1 or requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = "acquisition_policy.requests_per_minute must be between 1 and 10"
        raise ManifestValidationError(msg)
    max_requests_per_minute = _require_int(
        policy,
        "max_requests_per_minute",
        "acquisition_policy",
    )
    if (
        max_requests_per_minute < requests_per_minute
        or max_requests_per_minute > MAX_ABSOLUTE_REQUESTS_PER_MINUTE
    ):
        msg = "acquisition_policy.max_requests_per_minute must be >= requests_per_minute and <= 20"
        raise ManifestValidationError(msg)
    write_target = _require_non_empty_str(policy, "write_target", "acquisition_policy")
    if write_target != WRITE_TARGET:
        msg = "acquisition_policy.write_target must be 'HtmlCache .html.gz'"
        raise ManifestValidationError(msg)

    raw_entries = raw_manifest.get("entries")
    if not isinstance(raw_entries, list):
        msg = "manifest.entries must be a JSON array"
        raise ManifestValidationError(msg)
    if not raw_entries:
        msg = "manifest.entries must include at least one approved URL"
        raise ManifestValidationError(msg)
    if len(raw_entries) > scope_max_urls:
        msg = "manifest.entries exceeds scope.max_urls"
        raise ManifestValidationError(msg)

    entries = _validate_entries(raw_entries)
    return BackfillManifest(
        manifest_id=manifest_id,
        status=status,
        approved_by_owner=True,
        approved_at=approved_at,
        scope_page_type=scope_page_type,
        scope_max_urls=scope_max_urls,
        requests_per_minute=requests_per_minute,
        max_requests_per_minute=max_requests_per_minute,
        write_target=write_target,
        entries=entries,
    )


def dry_run_backfill_manifest(path: str | Path, *, cache: HtmlCache) -> DryRunReport:
    manifest = load_backfill_manifest(path)
    return build_dry_run_report(manifest, cache=cache)


def build_dry_run_report(manifest: BackfillManifest, *, cache: HtmlCache) -> DryRunReport:
    entries: list[DryRunEntry] = []
    cache_hits = 0
    cache_misses = 0

    for manifest_entry in manifest.entries:
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            cache_status = "hit"
            estimated_live_request_count = 0
            cache_hits += 1
        else:
            cache_status = "miss"
            estimated_live_request_count = 1
            cache_misses += 1

        entries.append(
            DryRunEntry(
                page_type=manifest_entry.page_type,
                url=manifest_entry.url,
                cache_path=str(cache_path),
                cache_status=cache_status,
                estimated_live_request_count=estimated_live_request_count,
            )
        )

    return DryRunReport(
        manifest_id=manifest.manifest_id,
        total_entries=len(entries),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        estimated_live_request_count=cache_misses,
        entries=tuple(entries),
    )


def _validate_entries(raw_entries: list[object]) -> tuple[BackfillManifestEntry, ...]:
    seen_urls: set[str] = set()
    entries: list[BackfillManifestEntry] = []

    for index, raw_entry in enumerate(raw_entries):
        context = f"entries[{index}]"
        if not isinstance(raw_entry, Mapping):
            msg = f"{context} must be a JSON object"
            raise ManifestValidationError(msg)

        page_type = _require_non_empty_str(raw_entry, "page_type", context)
        if page_type != SUPPORTED_PAGE_TYPE:
            msg = f"{context}.page_type must be 'team_season'"
            raise ManifestValidationError(msg)

        url = _require_non_empty_str(raw_entry, "url", context)
        if url in seen_urls:
            msg = f"{context}.url duplicates an earlier manifest entry"
            raise ManifestValidationError(msg)
        seen_urls.add(url)

        url_team, url_year = _parse_team_season_url(url, context)
        team = _require_non_empty_str(raw_entry, "team", context).upper()
        if team != url_team:
            msg = f"{context}.team must match the team in the URL"
            raise ManifestValidationError(msg)
        season_end_year = _require_int(raw_entry, "season_end_year", context)
        if season_end_year != url_year:
            msg = f"{context}.season_end_year must match the year in the URL"
            raise ManifestValidationError(msg)

        entries.append(
            BackfillManifestEntry(
                page_type=page_type,
                url=url,
                team=team,
                season_end_year=season_end_year,
            )
        )

    return tuple(entries)


def _parse_team_season_url(url: str, context: str) -> tuple[str, int]:
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
        msg = f"{context}.url must be an explicit Basketball Reference team-season URL"
        raise ManifestValidationError(msg)
    return match.group("team"), int(match.group("year"))


def _require_mapping(mapping: Mapping[str, Any], field: str, context: str) -> Mapping[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, Mapping):
        msg = f"{context}.{field} must be a JSON object"
        raise ManifestValidationError(msg)
    return value


def _require_non_empty_str(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        msg = f"{context}.{field} must be a non-empty string"
        raise ManifestValidationError(msg)
    return value.strip()


def _require_true(mapping: Mapping[str, Any], field: str, context: str) -> None:
    if mapping.get(field) is not True:
        msg = f"{context}.{field} must be true"
        raise ManifestValidationError(msg)


def _require_int(mapping: Mapping[str, Any], field: str, context: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{context}.{field} must be an integer"
        raise ManifestValidationError(msg)
    return value
