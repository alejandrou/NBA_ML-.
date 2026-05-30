from __future__ import annotations

import gzip
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nba_data.config.settings import Settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import RateLimitExceededError
from nba_data.scraping.nba_team_season_manifest import (
    EXPECTED_MANIFEST_URLS,
    MANIFEST_ID,
    SEASON_END_YEAR,
    SEASON_START_YEAR,
    NbaTeamSeasonManifest,
    build_nba_team_season_manifest,
)

PHASE_4D_MAX_REQUESTS_PER_MINUTE = 12


class NbaTeamSeasonAcquisitionConfigurationError(ValueError):
    """Raised when controlled acquisition is not safe to start."""


class NbaTeamSeasonCacheWriteError(RuntimeError):
    """Raised when a cache write cannot be completed safely."""


class NbaTeamSeasonAcquisitionStopped(RuntimeError):
    """Raised when acquisition stops early with a partial report."""

    def __init__(self, message: str, report: NbaTeamSeasonAcquisitionReport) -> None:
        super().__init__(message)
        self.report = report


class NbaTeamSeasonAcquisitionClient(Protocol):
    def get(self, url: str, *, force_refresh: bool = False) -> str:
        """Return raw HTML for one URL."""


@dataclass(frozen=True)
class NbaTeamSeasonAcquisitionEntryResult:
    index: int
    team: str
    season_end_year: int
    url: str
    cache_path: str
    status: str
    error_details: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "team": self.team,
            "season_end_year": self.season_end_year,
            "url": self.url,
            "cache_path": self.cache_path,
            "status": self.status,
            "error_details": self.error_details,
        }


@dataclass(frozen=True)
class NbaTeamSeasonAcquisitionReport:
    manifest_id: str
    season_start_year: int
    season_end_year: int
    total_urls: int
    processed_entries: int
    cache_hits: int
    fetched: int
    skipped_entries: int
    failed: int
    rate_limited: int
    live_request_count: int
    completed: bool
    stopped_reason: str | None
    stopped_at_entry: int | None
    entries: tuple[NbaTeamSeasonAcquisitionEntryResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "season_start_year": self.season_start_year,
            "season_end_year": self.season_end_year,
            "total_urls": self.total_urls,
            "processed_entries": self.processed_entries,
            "cache_hits": self.cache_hits,
            "fetched": self.fetched,
            "skipped_entries": self.skipped_entries,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "live_request_count": self.live_request_count,
            "completed": self.completed,
            "stopped_reason": self.stopped_reason,
            "stopped_at_entry": self.stopped_at_entry,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def validate_phase_4d_acquisition_settings(settings: Settings) -> None:
    if settings.scraper_max_requests_per_minute > PHASE_4D_MAX_REQUESTS_PER_MINUTE:
        msg = (
            "F4D-ACQ-LIVE-001 allows at most "
            f"{PHASE_4D_MAX_REQUESTS_PER_MINUTE} requests/minute"
        )
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)


def build_verified_nba_team_season_acquisition_manifest(
    *,
    start_year: int = SEASON_START_YEAR,
    end_year: int = SEASON_END_YEAR,
) -> NbaTeamSeasonManifest:
    validate_nba_team_season_year_range(start_year=start_year, end_year=end_year)
    full_manifest = build_nba_team_season_manifest()
    validate_nba_team_season_acquisition_manifest(full_manifest)

    if start_year == SEASON_START_YEAR and end_year == SEASON_END_YEAR:
        return full_manifest

    entries = tuple(
        entry
        for entry in full_manifest.entries
        if start_year <= entry.season_end_year <= end_year
    )
    filtered_manifest = NbaTeamSeasonManifest(
        manifest_id=full_manifest.manifest_id,
        season_start_year=start_year,
        season_end_year=end_year,
        total_urls=len(entries),
        unique_urls=len({entry.url for entry in entries}),
        entries=entries,
    )
    validate_nba_team_season_acquisition_manifest(
        filtered_manifest,
        require_full_manifest=False,
    )
    return filtered_manifest


def validate_nba_team_season_year_range(*, start_year: int, end_year: int) -> None:
    if start_year > end_year:
        msg = "START_YEAR must be less than or equal to END_YEAR"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if start_year < SEASON_START_YEAR or end_year > SEASON_END_YEAR:
        msg = (
            "F4D-ACQ-LIVE-001 currently supports only Basketball Reference season "
            f"end years {SEASON_START_YEAR}-{SEASON_END_YEAR}; earlier seasons need "
            "a reviewed historical catalog expansion"
        )
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)


def validate_nba_team_season_acquisition_manifest(
    manifest: NbaTeamSeasonManifest,
    *,
    require_full_manifest: bool = True,
) -> None:
    if manifest.manifest_id != MANIFEST_ID:
        msg = f"Expected manifest_id {MANIFEST_ID!r}, got {manifest.manifest_id!r}"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if require_full_manifest and manifest.total_urls != EXPECTED_MANIFEST_URLS:
        msg = f"Expected {EXPECTED_MANIFEST_URLS} manifest entries, got {manifest.total_urls}"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if require_full_manifest and manifest.unique_urls != EXPECTED_MANIFEST_URLS:
        msg = f"Expected {EXPECTED_MANIFEST_URLS} unique URLs, got {manifest.unique_urls}"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if require_full_manifest and len(manifest.entries) != EXPECTED_MANIFEST_URLS:
        msg = f"Expected {EXPECTED_MANIFEST_URLS} manifest entries, got {len(manifest.entries)}"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if manifest.total_urls != len(manifest.entries):
        msg = "manifest.total_urls must match the number of entries"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if manifest.unique_urls != len({entry.url for entry in manifest.entries}):
        msg = "manifest.unique_urls must match the number of distinct entry URLs"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    if not manifest.entries:
        msg = "Manifest year range produced no eligible NBA team-season URLs"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)
    validate_nba_team_season_year_range(
        start_year=manifest.season_start_year,
        end_year=manifest.season_end_year,
    )

    seen_urls: set[str] = set()
    for entry in manifest.entries:
        if entry.url in seen_urls:
            msg = f"Duplicate manifest URL: {entry.url}"
            raise NbaTeamSeasonAcquisitionConfigurationError(msg)
        seen_urls.add(entry.url)
        if entry.page_type != "team_season":
            msg = f"Unsupported manifest page_type: {entry.page_type}"
            raise NbaTeamSeasonAcquisitionConfigurationError(msg)
        if not manifest.season_start_year <= entry.season_end_year <= manifest.season_end_year:
            msg = f"Entry year {entry.season_end_year} is outside the requested range"
            raise NbaTeamSeasonAcquisitionConfigurationError(msg)
        expected_url = f"https://www.basketball-reference.com/teams/{entry.team}/{entry.season_end_year}.html"
        if entry.url != expected_url:
            msg = f"Unsupported manifest URL: {entry.url}"
            raise NbaTeamSeasonAcquisitionConfigurationError(msg)


def run_nba_team_season_acquisition(
    *,
    cache: HtmlCache,
    client: NbaTeamSeasonAcquisitionClient,
) -> NbaTeamSeasonAcquisitionReport:
    manifest = build_verified_nba_team_season_acquisition_manifest()
    return acquire_nba_team_season_manifest(manifest, cache=cache, client=client)


def acquire_nba_team_season_manifest(
    manifest: NbaTeamSeasonManifest,
    *,
    cache: HtmlCache,
    client: NbaTeamSeasonAcquisitionClient,
) -> NbaTeamSeasonAcquisitionReport:
    validate_nba_team_season_acquisition_manifest(manifest, require_full_manifest=False)
    results: list[NbaTeamSeasonAcquisitionEntryResult] = []

    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            results.append(
                NbaTeamSeasonAcquisitionEntryResult(
                    index=index,
                    team=manifest_entry.team,
                    season_end_year=manifest_entry.season_end_year,
                    url=manifest_entry.url,
                    cache_path=str(cache_path),
                    status="cache_hit",
                )
            )
            continue

        try:
            html = client.get(manifest_entry.url, force_refresh=False)
            _validate_html_for_cache(html)
            written_path = _write_html_to_cache_safely(cache, manifest_entry.url, html)
        except RateLimitExceededError as exc:
            results.append(
                _stopped_entry(
                    index=index,
                    team=manifest_entry.team,
                    season_end_year=manifest_entry.season_end_year,
                    url=manifest_entry.url,
                    cache_path=cache_path,
                    status="rate_limited",
                    error_details=str(exc),
                )
            )
            report = _build_report(
                manifest,
                results,
                completed=False,
                stopped_reason="rate_limited",
                stopped_at_entry=index,
            )
            msg = f"NBA team-season acquisition rate-limited at {manifest_entry.url}"
            raise NbaTeamSeasonAcquisitionStopped(msg, report) from exc
        except Exception as exc:
            results.append(
                _stopped_entry(
                    index=index,
                    team=manifest_entry.team,
                    season_end_year=manifest_entry.season_end_year,
                    url=manifest_entry.url,
                    cache_path=cache_path,
                    status="failed",
                    error_details=str(exc),
                )
            )
            report = _build_report(
                manifest,
                results,
                completed=False,
                stopped_reason="failed",
                stopped_at_entry=index,
            )
            msg = f"NBA team-season acquisition failed at {manifest_entry.url}"
            raise NbaTeamSeasonAcquisitionStopped(msg, report) from exc

        results.append(
            NbaTeamSeasonAcquisitionEntryResult(
                index=index,
                team=manifest_entry.team,
                season_end_year=manifest_entry.season_end_year,
                url=manifest_entry.url,
                cache_path=str(written_path),
                status="fetched",
            )
        )

    return _build_report(
        manifest,
        results,
        completed=True,
        stopped_reason=None,
        stopped_at_entry=None,
    )


def _validate_html_for_cache(html: str) -> None:
    if not isinstance(html, str) or not html.strip():
        msg = "Fetched content is empty and will not be cached"
        raise ValueError(msg)

    lowered = html.lstrip().lower()
    if not (lowered.startswith("<!doctype html") or lowered.startswith("<html")):
        msg = "Fetched content does not look like an HTML document"
        raise ValueError(msg)


def _write_html_to_cache_safely(cache: HtmlCache, url: str, html: str) -> Path:
    final_path = cache.path_for_url(url)
    if final_path.exists():
        msg = f"Refusing to overwrite existing cache file: {final_path}"
        raise NbaTeamSeasonCacheWriteError(msg)

    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")

    try:
        with gzip.open(temp_path, "wt", encoding="utf-8", newline="") as file:
            file.write(html)
        with gzip.open(temp_path, "rt", encoding="utf-8", newline="") as file:
            if file.read() != html:
                msg = f"Cache write verification failed for {final_path}"
                raise NbaTeamSeasonCacheWriteError(msg)
        if final_path.exists():
            msg = f"Refusing to overwrite existing cache file: {final_path}"
            raise NbaTeamSeasonCacheWriteError(msg)
        os.replace(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return final_path


def _stopped_entry(
    *,
    index: int,
    team: str,
    season_end_year: int,
    url: str,
    cache_path: Path,
    status: str,
    error_details: str,
) -> NbaTeamSeasonAcquisitionEntryResult:
    return NbaTeamSeasonAcquisitionEntryResult(
        index=index,
        team=team,
        season_end_year=season_end_year,
        url=url,
        cache_path=str(cache_path),
        status=status,
        error_details=error_details,
    )


def _build_report(
    manifest: NbaTeamSeasonManifest,
    results: list[NbaTeamSeasonAcquisitionEntryResult],
    *,
    completed: bool,
    stopped_reason: str | None,
    stopped_at_entry: int | None,
) -> NbaTeamSeasonAcquisitionReport:
    return NbaTeamSeasonAcquisitionReport(
        manifest_id=manifest.manifest_id,
        season_start_year=manifest.season_start_year,
        season_end_year=manifest.season_end_year,
        total_urls=manifest.total_urls,
        processed_entries=len(results),
        cache_hits=sum(result.status == "cache_hit" for result in results),
        fetched=sum(result.status == "fetched" for result in results),
        skipped_entries=sum(result.status == "skipped" for result in results),
        failed=sum(result.status == "failed" for result in results),
        rate_limited=sum(result.status == "rate_limited" for result in results),
        live_request_count=sum(
            result.status in {"fetched", "failed", "rate_limited"} for result in results
        ),
        completed=completed,
        stopped_reason=stopped_reason,
        stopped_at_entry=stopped_at_entry,
        entries=tuple(results),
    )
