"""Controlled, resumable cache acquisition of one Stage 2 season manifest (F8-004).

Runs one approved season manifest (`game_season_manifest.py`) through the
central Basketball Reference client: cache-first, sequential, never
overwriting, and stopping at the first 429 or failure with a partial report.
`max_fetches` ends a batch cleanly after that many live requests; rerunning the
same manifest resumes from the cache, because cache hits cost nothing.

A copy of the F8-001 pilot's loop (`game_pilot_acquisition.py`), which is left
unchanged, with the batch limit and a stricter settings guard: this command
refuses the placeholder user agent.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nba_data.config.settings import MINIMUM_SCRAPER_DELAY_SECONDS, Settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_writer import validate_html_for_cache, write_html_to_cache_safely
from nba_data.scraping.client import (
    FetchResult,
    RateLimitExceededError,
    RequestBudgetExhaustedError,
)
from nba_data.scraping.game_season_manifest import (
    MAX_DEFAULT_REQUESTS_PER_MINUTE,
    GameSeasonManifest,
    GameSeasonManifestEntry,
)

PLACEHOLDER_USER_AGENT = str(Settings.model_fields["scraper_user_agent"].default)
_PLACEHOLDER_CONTACT_DOMAIN = "example.com"

STOPPED_RATE_LIMITED = "rate_limited"
STOPPED_FAILED = "failed"
STOPPED_MAX_FETCHES = "max_fetches"


class GameSeasonAcquisitionConfigurationError(ValueError):
    """Raised when the season acquisition cannot run safely with these settings."""


class GameSeasonAcquisitionStopped(RuntimeError):
    """Raised when the season acquisition stops on a 429 or a failure, with a partial report."""

    def __init__(self, message: str, report: GameSeasonAcquisitionReport) -> None:
        super().__init__(message)
        self.report = report


class GameSeasonAcquisitionClient(Protocol):
    @property
    def request_count(self) -> int:
        """HTTP requests attempted so far, retries included."""

    def fetch(self, url: str, *, force_refresh: bool = False) -> FetchResult:
        """Return raw HTML for one URL plus the provenance of the fetch.

        A client built with a request budget raises `RequestBudgetExhaustedError`
        before any attempt, retries included, that would exceed it.
        """


@dataclass(frozen=True)
class GameSeasonDryRunEntry:
    index: int
    page_type: str
    url: str
    game_id: str | None
    month: str | None
    cache_path: str
    cache_status: str
    estimated_fetch_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "page_type": self.page_type,
            "url": self.url,
            "game_id": self.game_id,
            "month": self.month,
            "cache_path": self.cache_path,
            "cache_status": self.cache_status,
            "estimated_fetch_count": self.estimated_fetch_count,
        }


@dataclass(frozen=True)
class GameSeasonDryRunReport:
    manifest_id: str
    status: str
    season_end_year: int
    page_type: str
    total_entries: int
    cache_hits: int
    missing_cache_entries: int
    estimated_fetch_count: int
    estimated_minimum_seconds: float
    entries: tuple[GameSeasonDryRunEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "status": self.status,
            "season_end_year": self.season_end_year,
            "page_type": self.page_type,
            "total_entries": self.total_entries,
            "cache_hits": self.cache_hits,
            "missing_cache_entries": self.missing_cache_entries,
            "estimated_fetch_count": self.estimated_fetch_count,
            "estimated_minimum_seconds": self.estimated_minimum_seconds,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class GameSeasonAcquisitionEntryResult:
    index: int
    page_type: str
    url: str
    game_id: str | None
    month: str | None
    cache_path: str
    status: str
    requests: int
    http_status: int | None = None
    fetched_at: str | None = None
    bytes: int | None = None
    compressed_bytes: int | None = None
    elapsed_seconds: float | None = None
    error_details: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "page_type": self.page_type,
            "url": self.url,
            "game_id": self.game_id,
            "month": self.month,
            "cache_path": self.cache_path,
            "status": self.status,
            "requests": self.requests,
            "http_status": self.http_status,
            "fetched_at": self.fetched_at,
            "bytes": self.bytes,
            "compressed_bytes": self.compressed_bytes,
            "elapsed_seconds": self.elapsed_seconds,
            "error_details": self.error_details,
        }


@dataclass(frozen=True)
class GameSeasonAcquisitionReport:
    manifest_id: str
    season_end_year: int
    page_type: str
    max_fetches: int | None
    total_entries: int
    processed_entries: int
    remaining_entries: int
    cache_hits: int
    fetched: int
    failures: int
    rate_limited: int
    live_request_count: int
    fetched_bytes: int
    fetched_compressed_bytes: int
    wall_seconds: float
    completed: bool
    stopped_reason: str | None
    stopped_at_entry: int | None
    entries: tuple[GameSeasonAcquisitionEntryResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "season_end_year": self.season_end_year,
            "page_type": self.page_type,
            "max_fetches": self.max_fetches,
            "total_entries": self.total_entries,
            "processed_entries": self.processed_entries,
            "remaining_entries": self.remaining_entries,
            "cache_hits": self.cache_hits,
            "fetched": self.fetched,
            "failures": self.failures,
            "rate_limited": self.rate_limited,
            "live_request_count": self.live_request_count,
            "fetched_bytes": self.fetched_bytes,
            "fetched_compressed_bytes": self.fetched_compressed_bytes,
            "wall_seconds": self.wall_seconds,
            "completed": self.completed,
            "stopped_reason": self.stopped_reason,
            "stopped_at_entry": self.stopped_at_entry,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def validate_game_season_acquisition_settings(settings: Settings) -> None:
    user_agent = settings.scraper_user_agent.strip()
    if user_agent == PLACEHOLDER_USER_AGENT or _PLACEHOLDER_CONTACT_DOMAIN in user_agent.lower():
        msg = (
            "SCRAPER_USER_AGENT is the placeholder; set a real contact before "
            "running a Stage 2 season acquisition"
        )
        raise GameSeasonAcquisitionConfigurationError(msg)
    if settings.scraper_max_requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = (
            "The Stage 2 season acquisition allows at most "
            f"{MAX_DEFAULT_REQUESTS_PER_MINUTE} requests/minute"
        )
        raise GameSeasonAcquisitionConfigurationError(msg)


def validate_settings_within_manifest_policy(
    settings: Settings,
    manifest: GameSeasonManifest,
) -> None:
    """The manifest's approved pace is a ceiling the configured pace must respect."""

    if settings.scraper_max_requests_per_minute > manifest.requests_per_minute:
        msg = (
            f"SCRAPER_MAX_REQUESTS_PER_MINUTE={settings.scraper_max_requests_per_minute} "
            f"exceeds the {manifest.requests_per_minute} requests/minute the manifest approves"
        )
        raise GameSeasonAcquisitionConfigurationError(msg)


def build_game_season_dry_run_report(
    manifest: GameSeasonManifest,
    *,
    cache: HtmlCache,
    settings: Settings,
) -> GameSeasonDryRunReport:
    entries: list[GameSeasonDryRunEntry] = []
    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        hit = cache_path.exists()
        entries.append(
            GameSeasonDryRunEntry(
                index=index,
                page_type=manifest_entry.page_type,
                url=manifest_entry.url,
                game_id=manifest_entry.game_id,
                month=manifest_entry.month,
                cache_path=str(cache_path),
                cache_status="hit" if hit else "missing",
                estimated_fetch_count=0 if hit else 1,
            )
        )

    missing = sum(entry.estimated_fetch_count for entry in entries)
    return GameSeasonDryRunReport(
        manifest_id=manifest.manifest_id,
        status=manifest.status,
        season_end_year=manifest.season_end_year,
        page_type=manifest.page_type,
        total_entries=len(entries),
        cache_hits=len(entries) - missing,
        missing_cache_entries=missing,
        estimated_fetch_count=missing,
        estimated_minimum_seconds=max(missing - 1, 0)
        * _request_spacing_seconds(settings, manifest),
        entries=tuple(entries),
    )


def acquire_game_season_manifest(
    manifest: GameSeasonManifest,
    *,
    cache: HtmlCache,
    client: GameSeasonAcquisitionClient,
    max_fetches: int | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> GameSeasonAcquisitionReport:
    """Acquire the manifest's missing pages; stop cleanly once `max_fetches` requests are spent.

    The limit is checked before each page here, and before each HTTP attempt,
    retries included, by a client built with `max_requests=max_fetches`; a page
    whose retries would exceed it is left uncached for the next run. Cache hits
    cost nothing and never count toward it.
    """

    if not manifest.approved:
        msg = "Only an approved season manifest can be acquired"
        raise GameSeasonAcquisitionConfigurationError(msg)
    if max_fetches is not None and max_fetches < 1:
        msg = "max_fetches must be at least 1"
        raise GameSeasonAcquisitionConfigurationError(msg)

    results: list[GameSeasonAcquisitionEntryResult] = []
    started_at = clock()
    live_requests = 0

    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            results.append(_cache_hit_result(index, manifest_entry, cache_path))
            continue

        if max_fetches is not None and live_requests >= max_fetches:
            return _build_report(
                manifest,
                results,
                max_fetches=max_fetches,
                wall_seconds=clock() - started_at,
                stopped_reason=STOPPED_MAX_FETCHES,
                stopped_at_entry=index,
            )

        requests_before = client.request_count
        fetch_started_at = clock()
        try:
            fetch_result = client.fetch(manifest_entry.url, force_refresh=False)
            validate_html_for_cache(fetch_result.html)
            written_path = write_html_to_cache_safely(
                cache,
                manifest_entry.url,
                fetch_result.html,
                metadata=fetch_result.metadata,
            )
        except RequestBudgetExhaustedError as exc:
            results.append(
                _stopped_result(
                    index,
                    manifest_entry,
                    cache_path,
                    status=STOPPED_MAX_FETCHES,
                    requests=client.request_count - requests_before,
                    elapsed_seconds=clock() - fetch_started_at,
                    error_details=str(exc),
                )
            )
            return _build_report(
                manifest,
                results,
                max_fetches=max_fetches,
                wall_seconds=clock() - started_at,
                stopped_reason=STOPPED_MAX_FETCHES,
                stopped_at_entry=index,
            )
        except RateLimitExceededError as exc:
            results.append(
                _stopped_result(
                    index,
                    manifest_entry,
                    cache_path,
                    status=STOPPED_RATE_LIMITED,
                    requests=client.request_count - requests_before,
                    elapsed_seconds=clock() - fetch_started_at,
                    error_details=str(exc),
                )
            )
            report = _build_report(
                manifest,
                results,
                max_fetches=max_fetches,
                wall_seconds=clock() - started_at,
                stopped_reason=STOPPED_RATE_LIMITED,
                stopped_at_entry=index,
            )
            msg = f"Game season acquisition rate-limited at {manifest_entry.url}"
            raise GameSeasonAcquisitionStopped(msg, report) from exc
        except Exception as exc:
            results.append(
                _stopped_result(
                    index,
                    manifest_entry,
                    cache_path,
                    status=STOPPED_FAILED,
                    requests=client.request_count - requests_before,
                    elapsed_seconds=clock() - fetch_started_at,
                    error_details=str(exc),
                )
            )
            report = _build_report(
                manifest,
                results,
                max_fetches=max_fetches,
                wall_seconds=clock() - started_at,
                stopped_reason=STOPPED_FAILED,
                stopped_at_entry=index,
            )
            msg = f"Game season acquisition failed at {manifest_entry.url}"
            raise GameSeasonAcquisitionStopped(msg, report) from exc

        requests = client.request_count - requests_before
        live_requests += requests
        metadata = fetch_result.metadata
        results.append(
            GameSeasonAcquisitionEntryResult(
                index=index,
                page_type=manifest_entry.page_type,
                url=manifest_entry.url,
                game_id=manifest_entry.game_id,
                month=manifest_entry.month,
                cache_path=str(written_path),
                status="fetched",
                requests=requests,
                http_status=metadata.http_status if metadata is not None else None,
                fetched_at=metadata.fetched_at.isoformat() if metadata is not None else None,
                bytes=len(fetch_result.html.encode("utf-8")),
                compressed_bytes=written_path.stat().st_size,
                elapsed_seconds=round(clock() - fetch_started_at, 3),
            )
        )

    return _build_report(
        manifest,
        results,
        max_fetches=max_fetches,
        wall_seconds=clock() - started_at,
        stopped_reason=None,
        stopped_at_entry=None,
    )


def _request_spacing_seconds(settings: Settings, manifest: GameSeasonManifest) -> float:
    """The slower of the configured pace and the pace the manifest approves."""

    rpm_delay = 60.0 / min(settings.scraper_max_requests_per_minute, 20)
    manifest_delay = 60.0 / manifest.requests_per_minute
    return max(
        settings.scraper_min_delay_seconds,
        rpm_delay,
        manifest_delay,
        MINIMUM_SCRAPER_DELAY_SECONDS,
    )


def _cache_hit_result(
    index: int,
    entry: GameSeasonManifestEntry,
    cache_path: Path,
) -> GameSeasonAcquisitionEntryResult:
    return GameSeasonAcquisitionEntryResult(
        index=index,
        page_type=entry.page_type,
        url=entry.url,
        game_id=entry.game_id,
        month=entry.month,
        cache_path=str(cache_path),
        status="cache_hit",
        requests=0,
    )


def _stopped_result(
    index: int,
    entry: GameSeasonManifestEntry,
    cache_path: Path,
    *,
    status: str,
    requests: int,
    elapsed_seconds: float,
    error_details: str,
) -> GameSeasonAcquisitionEntryResult:
    return GameSeasonAcquisitionEntryResult(
        index=index,
        page_type=entry.page_type,
        url=entry.url,
        game_id=entry.game_id,
        month=entry.month,
        cache_path=str(cache_path),
        status=status,
        requests=requests,
        elapsed_seconds=round(elapsed_seconds, 3),
        error_details=error_details,
    )


def _build_report(
    manifest: GameSeasonManifest,
    results: list[GameSeasonAcquisitionEntryResult],
    *,
    max_fetches: int | None,
    wall_seconds: float,
    stopped_reason: str | None,
    stopped_at_entry: int | None,
) -> GameSeasonAcquisitionReport:
    fetched = [result for result in results if result.status == "fetched"]
    return GameSeasonAcquisitionReport(
        manifest_id=manifest.manifest_id,
        season_end_year=manifest.season_end_year,
        page_type=manifest.page_type,
        max_fetches=max_fetches,
        total_entries=len(manifest.entries),
        processed_entries=len(results),
        remaining_entries=sum(result.status not in ("cache_hit", "fetched") for result in results)
        + len(manifest.entries)
        - len(results),
        cache_hits=sum(result.status == "cache_hit" for result in results),
        fetched=len(fetched),
        failures=sum(result.status == STOPPED_FAILED for result in results),
        rate_limited=sum(result.status == STOPPED_RATE_LIMITED for result in results),
        live_request_count=sum(result.requests for result in results),
        fetched_bytes=sum(result.bytes or 0 for result in fetched),
        fetched_compressed_bytes=sum(result.compressed_bytes or 0 for result in fetched),
        wall_seconds=round(wall_seconds, 3),
        completed=stopped_reason is None,
        stopped_reason=stopped_reason,
        stopped_at_entry=stopped_at_entry,
        entries=tuple(results),
    )


__all__ = [
    "PLACEHOLDER_USER_AGENT",
    "STOPPED_FAILED",
    "STOPPED_MAX_FETCHES",
    "STOPPED_RATE_LIMITED",
    "GameSeasonAcquisitionClient",
    "GameSeasonAcquisitionConfigurationError",
    "GameSeasonAcquisitionEntryResult",
    "GameSeasonAcquisitionReport",
    "GameSeasonAcquisitionStopped",
    "GameSeasonDryRunEntry",
    "GameSeasonDryRunReport",
    "acquire_game_season_manifest",
    "build_game_season_dry_run_report",
    "validate_game_season_acquisition_settings",
    "validate_settings_within_manifest_policy",
]
