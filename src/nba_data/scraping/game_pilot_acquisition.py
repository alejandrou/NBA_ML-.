"""Controlled, measured cache acquisition for the F8-001 per-game pilot.

Runs one approved pilot manifest (`game_pilot_manifest.py`) through the central
Basketball Reference client: cache-first, sequential, never overwriting, and
stopping at the first 429 or failure with a partial report. Every entry records
what the pilot has to measure — HTTP requests, bytes, and wall time.
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
from nba_data.scraping.client import FetchResult, RateLimitExceededError
from nba_data.scraping.game_pilot_manifest import (
    MAX_DEFAULT_REQUESTS_PER_MINUTE,
    GamePilotManifest,
    GamePilotManifestEntry,
)


class GamePilotAcquisitionConfigurationError(ValueError):
    """Raised when the pilot acquisition cannot run safely with these settings."""


class GamePilotAcquisitionStopped(RuntimeError):
    """Raised when the pilot acquisition stops early with a partial report."""

    def __init__(self, message: str, report: GamePilotAcquisitionReport) -> None:
        super().__init__(message)
        self.report = report


class GamePilotAcquisitionClient(Protocol):
    @property
    def request_count(self) -> int:
        """HTTP requests attempted so far, retries included."""

    def fetch(self, url: str, *, force_refresh: bool = False) -> FetchResult:
        """Return raw HTML for one URL plus the provenance of the fetch."""


@dataclass(frozen=True)
class GamePilotDryRunEntry:
    index: int
    page_type: str
    url: str
    season_end_year: int
    game_id: str | None
    cache_path: str
    cache_status: str
    estimated_fetch_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "page_type": self.page_type,
            "url": self.url,
            "season_end_year": self.season_end_year,
            "game_id": self.game_id,
            "cache_path": self.cache_path,
            "cache_status": self.cache_status,
            "estimated_fetch_count": self.estimated_fetch_count,
        }


@dataclass(frozen=True)
class GamePilotDryRunReport:
    manifest_id: str
    total_entries: int
    games: int
    cache_hits: int
    missing_cache_entries: int
    estimated_fetch_count: int
    estimated_minimum_seconds: float
    entries: tuple[GamePilotDryRunEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "total_entries": self.total_entries,
            "games": self.games,
            "cache_hits": self.cache_hits,
            "missing_cache_entries": self.missing_cache_entries,
            "estimated_fetch_count": self.estimated_fetch_count,
            "estimated_minimum_seconds": self.estimated_minimum_seconds,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class GamePilotAcquisitionEntryResult:
    index: int
    page_type: str
    url: str
    season_end_year: int
    game_id: str | None
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
            "season_end_year": self.season_end_year,
            "game_id": self.game_id,
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
class GamePilotAcquisitionReport:
    manifest_id: str
    total_entries: int
    processed_entries: int
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
    entries: tuple[GamePilotAcquisitionEntryResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "total_entries": self.total_entries,
            "processed_entries": self.processed_entries,
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


def validate_game_pilot_acquisition_settings(settings: Settings) -> None:
    if settings.scraper_max_requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = f"The F8-001 pilot allows at most {MAX_DEFAULT_REQUESTS_PER_MINUTE} requests/minute"
        raise GamePilotAcquisitionConfigurationError(msg)


def validate_settings_within_manifest_policy(
    settings: Settings,
    manifest: GamePilotManifest,
) -> None:
    """The manifest's approved pace is a ceiling the configured pace must respect."""

    if settings.scraper_max_requests_per_minute > manifest.requests_per_minute:
        msg = (
            f"SCRAPER_MAX_REQUESTS_PER_MINUTE={settings.scraper_max_requests_per_minute} "
            f"exceeds the {manifest.requests_per_minute} requests/minute the manifest approves"
        )
        raise GamePilotAcquisitionConfigurationError(msg)


def build_game_pilot_dry_run_report(
    manifest: GamePilotManifest,
    *,
    cache: HtmlCache,
    settings: Settings,
) -> GamePilotDryRunReport:
    entries: list[GamePilotDryRunEntry] = []
    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        hit = cache_path.exists()
        entries.append(
            GamePilotDryRunEntry(
                index=index,
                page_type=manifest_entry.page_type,
                url=manifest_entry.url,
                season_end_year=manifest_entry.season_end_year,
                game_id=manifest_entry.game_id,
                cache_path=str(cache_path),
                cache_status="hit" if hit else "missing",
                estimated_fetch_count=0 if hit else 1,
            )
        )

    missing = sum(entry.estimated_fetch_count for entry in entries)
    return GamePilotDryRunReport(
        manifest_id=manifest.manifest_id,
        total_entries=len(entries),
        games=len(manifest.game_ids),
        cache_hits=len(entries) - missing,
        missing_cache_entries=missing,
        estimated_fetch_count=missing,
        estimated_minimum_seconds=max(missing - 1, 0) * _request_spacing_seconds(settings),
        entries=tuple(entries),
    )


def acquire_game_pilot_manifest(
    manifest: GamePilotManifest,
    *,
    cache: HtmlCache,
    client: GamePilotAcquisitionClient,
    clock: Callable[[], float] = time.monotonic,
) -> GamePilotAcquisitionReport:
    results: list[GamePilotAcquisitionEntryResult] = []
    started_at = clock()

    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            results.append(_cache_hit_result(index, manifest_entry, cache_path))
            continue

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
        except RateLimitExceededError as exc:
            results.append(
                _stopped_result(
                    index,
                    manifest_entry,
                    cache_path,
                    status="rate_limited",
                    requests=client.request_count - requests_before,
                    elapsed_seconds=clock() - fetch_started_at,
                    error_details=str(exc),
                )
            )
            report = _build_report(
                manifest,
                results,
                wall_seconds=clock() - started_at,
                stopped_reason="rate_limited",
                stopped_at_entry=index,
            )
            msg = f"Game pilot acquisition rate-limited at {manifest_entry.url}"
            raise GamePilotAcquisitionStopped(msg, report) from exc
        except Exception as exc:
            results.append(
                _stopped_result(
                    index,
                    manifest_entry,
                    cache_path,
                    status="failed",
                    requests=client.request_count - requests_before,
                    elapsed_seconds=clock() - fetch_started_at,
                    error_details=str(exc),
                )
            )
            report = _build_report(
                manifest,
                results,
                wall_seconds=clock() - started_at,
                stopped_reason="failed",
                stopped_at_entry=index,
            )
            msg = f"Game pilot acquisition failed at {manifest_entry.url}"
            raise GamePilotAcquisitionStopped(msg, report) from exc

        metadata = fetch_result.metadata
        results.append(
            GamePilotAcquisitionEntryResult(
                index=index,
                page_type=manifest_entry.page_type,
                url=manifest_entry.url,
                season_end_year=manifest_entry.season_end_year,
                game_id=manifest_entry.game_id,
                cache_path=str(written_path),
                status="fetched",
                requests=client.request_count - requests_before,
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
        wall_seconds=clock() - started_at,
        stopped_reason=None,
        stopped_at_entry=None,
    )


def _request_spacing_seconds(settings: Settings) -> float:
    rpm_delay = 60.0 / min(settings.scraper_max_requests_per_minute, 20)
    return max(settings.scraper_min_delay_seconds, rpm_delay, MINIMUM_SCRAPER_DELAY_SECONDS)


def _cache_hit_result(
    index: int,
    entry: GamePilotManifestEntry,
    cache_path: Path,
) -> GamePilotAcquisitionEntryResult:
    return GamePilotAcquisitionEntryResult(
        index=index,
        page_type=entry.page_type,
        url=entry.url,
        season_end_year=entry.season_end_year,
        game_id=entry.game_id,
        cache_path=str(cache_path),
        status="cache_hit",
        requests=0,
    )


def _stopped_result(
    index: int,
    entry: GamePilotManifestEntry,
    cache_path: Path,
    *,
    status: str,
    requests: int,
    elapsed_seconds: float,
    error_details: str,
) -> GamePilotAcquisitionEntryResult:
    return GamePilotAcquisitionEntryResult(
        index=index,
        page_type=entry.page_type,
        url=entry.url,
        season_end_year=entry.season_end_year,
        game_id=entry.game_id,
        cache_path=str(cache_path),
        status=status,
        requests=requests,
        elapsed_seconds=round(elapsed_seconds, 3),
        error_details=error_details,
    )


def _build_report(
    manifest: GamePilotManifest,
    results: list[GamePilotAcquisitionEntryResult],
    *,
    wall_seconds: float,
    stopped_reason: str | None,
    stopped_at_entry: int | None,
) -> GamePilotAcquisitionReport:
    fetched = [result for result in results if result.status == "fetched"]
    return GamePilotAcquisitionReport(
        manifest_id=manifest.manifest_id,
        total_entries=len(manifest.entries),
        processed_entries=len(results),
        cache_hits=sum(result.status == "cache_hit" for result in results),
        fetched=len(fetched),
        failures=sum(result.status == "failed" for result in results),
        rate_limited=sum(result.status == "rate_limited" for result in results),
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
    "GamePilotAcquisitionClient",
    "GamePilotAcquisitionConfigurationError",
    "GamePilotAcquisitionEntryResult",
    "GamePilotAcquisitionReport",
    "GamePilotAcquisitionStopped",
    "GamePilotDryRunEntry",
    "GamePilotDryRunReport",
    "acquire_game_pilot_manifest",
    "build_game_pilot_dry_run_report",
    "validate_game_pilot_acquisition_settings",
    "validate_settings_within_manifest_policy",
]
