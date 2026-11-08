"""One gated, bounded refresh of the current season (F8-013).

Runs the approved rule of a `current_season_refresh` manifest through the
central Basketball Reference client, in a fixed order:

    season page -> month pages -> team pages -> box scores

Each phase is planned (`current_season_planning.py`) from the snapshots the
previous phases just wrote. Schedule and team pages go only through
`SnapshotCache.write`; box scores, which never change once played, only through
`write_html_to_cache_safely` into the archive cache.

Sequential; the client spaces requests at least six seconds apart. The run stops
at the first 429 (reporting the `Retry-After` it asked for), at the first
failure, or when a phase's plan exceeds its ceiling. `max_fetches` ends the run
cleanly after that many live requests. Rerunning resumes: box scores are
cache-first, and schedule pages are new snapshots.

The guards are copied from F8-004's (`game_season_acquisition.py`), which is
left unchanged.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from nba_data.config.settings import MINIMUM_SCRAPER_DELAY_SECONDS, Settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_writer import validate_html_for_cache, write_html_to_cache_safely
from nba_data.scraping.client import (
    FetchResult,
    RateLimitExceededError,
    RequestBudgetExhaustedError,
)
from nba_data.scraping.current_season_manifest import (
    MAX_DEFAULT_REQUESTS_PER_MINUTE,
    CurrentSeasonManifest,
)
from nba_data.scraping.current_season_planning import (
    PHASE_BOX_SCORE,
    PHASE_MONTH,
    PHASE_SEASON,
    PHASE_TEAM,
    CurrentSeasonPlanningError,
    PlannedPage,
    plan_box_scores,
    plan_month_pages,
    plan_season_page,
    plan_team_pages,
    require_as_of_in_season,
    validate_schedule_page,
)
from nba_data.scraping.snapshot_cache import SnapshotCache

PLACEHOLDER_USER_AGENT = str(Settings.model_fields["scraper_user_agent"].default)
_PLACEHOLDER_CONTACT_DOMAIN = "example.com"

STOPPED_RATE_LIMITED = "rate_limited"
STOPPED_FAILED = "failed"
STOPPED_MAX_FETCHES = "max_fetches"
STOPPED_PLAN_REFUSED = "plan_refused"


class CurrentSeasonAcquisitionConfigurationError(ValueError):
    """Raised when the refresh cannot run safely with these settings or arguments."""


class CurrentSeasonAcquisitionStopped(RuntimeError):
    """Raised when the refresh stops on a 429, a failure or a refused plan, with a report."""

    def __init__(self, message: str, report: CurrentSeasonRefreshReport) -> None:
        super().__init__(message)
        self.report = report


class CurrentSeasonAcquisitionClient(Protocol):
    @property
    def request_count(self) -> int:
        """HTTP requests attempted so far, retries included."""

    def fetch(self, url: str, *, force_refresh: bool = False) -> FetchResult:
        """Return raw HTML for one URL plus the provenance of the fetch."""


@dataclass(frozen=True)
class CurrentSeasonRefreshEntryResult:
    index: int
    phase: str
    url: str
    month: str | None
    team: str | None
    game_id: str | None
    status: str
    requests: int
    path: str | None = None
    http_status: int | None = None
    fetched_at: str | None = None
    bytes: int | None = None
    elapsed_seconds: float | None = None
    error_details: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "phase": self.phase,
            "url": self.url,
            "month": self.month,
            "team": self.team,
            "game_id": self.game_id,
            "status": self.status,
            "requests": self.requests,
            "path": self.path,
            "http_status": self.http_status,
            "fetched_at": self.fetched_at,
            "bytes": self.bytes,
            "elapsed_seconds": self.elapsed_seconds,
            "error_details": self.error_details,
        }


@dataclass(frozen=True)
class CurrentSeasonRefreshReport:
    manifest_id: str
    season_end_year: int
    as_of: str
    max_fetches: int | None
    planned: dict[str, int | None]
    cache_hits: int
    fetched: int
    failures: int
    rate_limited: int
    live_request_count: int
    fetched_bytes: int
    wall_seconds: float
    completed: bool
    stopped_reason: str | None
    stopped_at_phase: str | None
    stopped_at_url: str | None
    retry_after_seconds: float | None
    error_details: str | None
    entries: tuple[CurrentSeasonRefreshEntryResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "season_end_year": self.season_end_year,
            "as_of": self.as_of,
            "max_fetches": self.max_fetches,
            "planned": dict(self.planned),
            "cache_hits": self.cache_hits,
            "fetched": self.fetched,
            "failures": self.failures,
            "rate_limited": self.rate_limited,
            "live_request_count": self.live_request_count,
            "fetched_bytes": self.fetched_bytes,
            "wall_seconds": self.wall_seconds,
            "completed": self.completed,
            "stopped_reason": self.stopped_reason,
            "stopped_at_phase": self.stopped_at_phase,
            "stopped_at_url": self.stopped_at_url,
            "retry_after_seconds": self.retry_after_seconds,
            "error_details": self.error_details,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class CurrentSeasonDryRunReport:
    manifest_id: str
    status: str
    season_end_year: int
    as_of: str
    ceilings: dict[str, int]
    season_page: PlannedPage
    season_page_snapshotted: bool
    month_pages: tuple[PlannedPage, ...] | None
    team_pages: tuple[PlannedPage, ...] | None
    box_scores: tuple[PlannedPage, ...]
    estimated_fetch_count: int
    estimated_minimum_seconds: float
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        def pages(planned: tuple[PlannedPage, ...] | None) -> list[dict[str, object]] | None:
            return None if planned is None else [page.to_dict() for page in planned]

        return {
            "manifest_id": self.manifest_id,
            "status": self.status,
            "season_end_year": self.season_end_year,
            "as_of": self.as_of,
            "ceilings": dict(self.ceilings),
            "season_page_snapshotted": self.season_page_snapshotted,
            "planned": {
                PHASE_SEASON: 1,
                PHASE_MONTH: None if self.month_pages is None else len(self.month_pages),
                PHASE_TEAM: None if self.team_pages is None else len(self.team_pages),
                PHASE_BOX_SCORE: len(self.box_scores),
            },
            "estimated_fetch_count": self.estimated_fetch_count,
            "estimated_minimum_seconds": self.estimated_minimum_seconds,
            "notes": list(self.notes),
            "season_page": self.season_page.to_dict(),
            "month_pages": pages(self.month_pages),
            "team_pages": pages(self.team_pages),
            "box_scores": pages(self.box_scores),
        }


def validate_current_season_acquisition_settings(settings: Settings) -> None:
    user_agent = settings.scraper_user_agent.strip()
    if user_agent == PLACEHOLDER_USER_AGENT or _PLACEHOLDER_CONTACT_DOMAIN in user_agent.lower():
        msg = (
            "SCRAPER_USER_AGENT is the placeholder; set a real contact before "
            "running a current-season refresh"
        )
        raise CurrentSeasonAcquisitionConfigurationError(msg)
    if settings.scraper_max_requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = (
            "The current-season refresh allows at most "
            f"{MAX_DEFAULT_REQUESTS_PER_MINUTE} requests/minute"
        )
        raise CurrentSeasonAcquisitionConfigurationError(msg)


def validate_settings_within_manifest_policy(
    settings: Settings,
    manifest: CurrentSeasonManifest,
) -> None:
    """The manifest's approved pace is a ceiling the configured pace must respect."""

    if settings.scraper_max_requests_per_minute > manifest.requests_per_minute:
        msg = (
            f"SCRAPER_MAX_REQUESTS_PER_MINUTE={settings.scraper_max_requests_per_minute} "
            f"exceeds the {manifest.requests_per_minute} requests/minute the manifest approves"
        )
        raise CurrentSeasonAcquisitionConfigurationError(msg)


def build_current_season_dry_run_report(
    manifest: CurrentSeasonManifest,
    *,
    as_of: date,
    snapshots: SnapshotCache,
    archive: HtmlCache,
    settings: Settings,
) -> CurrentSeasonDryRunReport:
    """The plan from the latest snapshots; offline. Box scores count only scores already seen.

    Raises `CurrentSeasonPlanningError` when a ceiling would be exceeded.
    """

    require_as_of_in_season(as_of, manifest.season_end_year)
    season_page = plan_season_page(manifest.season_end_year)
    snapshotted = snapshots.latest(season_page.url) is not None
    month_pages = plan_month_pages(manifest, snapshots=snapshots, as_of=as_of)
    team_pages = plan_team_pages(manifest, snapshots=snapshots)
    box_scores = plan_box_scores(manifest, snapshots=snapshots, archive=archive)

    notes: list[str] = [
        "Box scores count only scores already in the latest month snapshots; the run "
        "re-plans them from the month pages it fetches.",
    ]
    if month_pages is None:
        notes.append("The season page has no snapshot yet: month pages are planned after it.")
    if team_pages is None:
        notes.append(
            "Some linked month pages have no snapshot yet: team pages are planned after them."
        )

    fetches = 1 + len(month_pages or ()) + len(team_pages or ()) + len(box_scores)
    return CurrentSeasonDryRunReport(
        manifest_id=manifest.manifest_id,
        status=manifest.status,
        season_end_year=manifest.season_end_year,
        as_of=as_of.isoformat(),
        ceilings=_ceilings(manifest),
        season_page=season_page,
        season_page_snapshotted=snapshotted,
        month_pages=month_pages,
        team_pages=team_pages,
        box_scores=box_scores,
        estimated_fetch_count=fetches,
        estimated_minimum_seconds=max(fetches - 1, 0)
        * _request_spacing_seconds(settings, manifest),
        notes=tuple(notes),
    )


def refresh_current_season(
    manifest: CurrentSeasonManifest,
    *,
    as_of: date,
    snapshots: SnapshotCache,
    archive: HtmlCache,
    client: CurrentSeasonAcquisitionClient,
    max_fetches: int | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> CurrentSeasonRefreshReport:
    """Run one refresh; stop cleanly once `max_fetches` live requests are spent.

    Raises `CurrentSeasonAcquisitionStopped`, carrying the partial report, on a
    429, any failure, or a phase whose plan exceeds its ceiling.
    """

    if not manifest.approved:
        msg = "Only an approved current-season manifest can be acquired"
        raise CurrentSeasonAcquisitionConfigurationError(msg)
    if max_fetches is not None and max_fetches < 1:
        msg = "max_fetches must be at least 1"
        raise CurrentSeasonAcquisitionConfigurationError(msg)
    try:
        require_as_of_in_season(as_of, manifest.season_end_year)
    except CurrentSeasonPlanningError as exc:
        raise CurrentSeasonAcquisitionConfigurationError(str(exc)) from exc

    run = _Run(
        manifest=manifest,
        as_of=as_of,
        snapshots=snapshots,
        archive=archive,
        client=client,
        max_fetches=max_fetches,
        clock=clock,
    )
    try:
        run.execute()
    except _StopRun as stop:
        report = run.report(stop)
        if stop.reason == STOPPED_MAX_FETCHES:
            return report
        msg = f"Current-season refresh stopped ({stop.reason}) at {stop.url or stop.phase}"
        raise CurrentSeasonAcquisitionStopped(msg, report) from stop.__cause__
    return run.report(None)


class _StopRun(Exception):
    def __init__(
        self,
        reason: str,
        *,
        phase: str,
        url: str | None,
        details: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.phase = phase
        self.url = url
        self.details = details
        self.retry_after_seconds = retry_after_seconds


@dataclass
class _Run:
    manifest: CurrentSeasonManifest
    as_of: date
    snapshots: SnapshotCache
    archive: HtmlCache
    client: CurrentSeasonAcquisitionClient
    max_fetches: int | None
    clock: Callable[[], float]
    results: list[CurrentSeasonRefreshEntryResult] = field(default_factory=list)
    planned: dict[str, int | None] = field(
        default_factory=lambda: {
            PHASE_SEASON: None,
            PHASE_MONTH: None,
            PHASE_TEAM: None,
            PHASE_BOX_SCORE: None,
        }
    )
    live_requests: int = 0
    started_at: float = 0.0

    def execute(self) -> None:
        self.started_at = self.clock()

        self.planned[PHASE_SEASON] = 1
        self._fetch(plan_season_page(self.manifest.season_end_year))

        months = self._plan(
            PHASE_MONTH,
            lambda: plan_month_pages(self.manifest, snapshots=self.snapshots, as_of=self.as_of),
        )
        for page in months:
            self._fetch(page)

        teams = self._plan(
            PHASE_TEAM, lambda: plan_team_pages(self.manifest, snapshots=self.snapshots)
        )
        for page in teams:
            self._fetch(page)

        box_scores = self._plan(
            PHASE_BOX_SCORE,
            lambda: plan_box_scores(self.manifest, snapshots=self.snapshots, archive=self.archive),
        )
        for page in box_scores:
            self._fetch(page)

    def _plan(
        self,
        phase: str,
        planner: Callable[[], tuple[PlannedPage, ...] | None],
    ) -> tuple[PlannedPage, ...]:
        try:
            planned = planner()
        except Exception as exc:
            raise _StopRun(STOPPED_PLAN_REFUSED, phase=phase, url=None, details=str(exc)) from exc
        if planned is None:
            # The earlier phases always leave the snapshots this phase needs.
            msg = f"The {phase} phase found no snapshot to plan from after the earlier phases"
            raise _StopRun(STOPPED_PLAN_REFUSED, phase=phase, url=None, details=msg)
        self.planned[phase] = len(planned)
        return planned

    def _fetch(self, page: PlannedPage) -> None:
        index = len(self.results) + 1
        if page.phase == PHASE_BOX_SCORE and self.archive.exists(page.url):
            self.results.append(self._result(index, page, "cache_hit", 0))
            return

        if self.max_fetches is not None and self.live_requests >= self.max_fetches:
            raise _StopRun(STOPPED_MAX_FETCHES, phase=page.phase, url=page.url)

        requests_before = self.client.request_count
        fetch_started_at = self.clock()
        try:
            fetched = self.client.fetch(page.url, force_refresh=False)
            validate_html_for_cache(fetched.html)
            if page.phase in (PHASE_SEASON, PHASE_MONTH):
                validate_schedule_page(fetched.html, page.url)
            if fetched.metadata is None:
                msg = f"The client returned {page.url} without fetch metadata"
                raise ValueError(msg)
            if page.phase == PHASE_BOX_SCORE:
                path = write_html_to_cache_safely(
                    self.archive, page.url, fetched.html, metadata=fetched.metadata
                )
            else:
                path = self.snapshots.write(page.url, fetched.html, fetched.metadata)
        except RequestBudgetExhaustedError as exc:
            self._stopped(index, page, STOPPED_MAX_FETCHES, requests_before, fetch_started_at, exc)
            raise _StopRun(
                STOPPED_MAX_FETCHES, phase=page.phase, url=page.url, details=str(exc)
            ) from exc
        except RateLimitExceededError as exc:
            self._stopped(index, page, STOPPED_RATE_LIMITED, requests_before, fetch_started_at, exc)
            raise _StopRun(
                STOPPED_RATE_LIMITED,
                phase=page.phase,
                url=page.url,
                details=str(exc),
                retry_after_seconds=exc.retry_after_seconds,
            ) from exc
        except Exception as exc:
            self._stopped(index, page, STOPPED_FAILED, requests_before, fetch_started_at, exc)
            raise _StopRun(
                STOPPED_FAILED, phase=page.phase, url=page.url, details=str(exc)
            ) from exc

        requests = self.client.request_count - requests_before
        self.live_requests += requests
        metadata = fetched.metadata
        self.results.append(
            CurrentSeasonRefreshEntryResult(
                index=index,
                phase=page.phase,
                url=page.url,
                month=page.month,
                team=page.team,
                game_id=page.game_id,
                status="fetched",
                requests=requests,
                path=str(path),
                http_status=metadata.http_status,
                fetched_at=metadata.fetched_at.isoformat(),
                bytes=len(fetched.html.encode("utf-8")),
                elapsed_seconds=round(self.clock() - fetch_started_at, 3),
            )
        )

    def _stopped(
        self,
        index: int,
        page: PlannedPage,
        status: str,
        requests_before: int,
        fetch_started_at: float,
        exc: Exception,
    ) -> None:
        requests = self.client.request_count - requests_before
        self.live_requests += requests
        self.results.append(
            self._result(
                index,
                page,
                status,
                requests,
                elapsed_seconds=round(self.clock() - fetch_started_at, 3),
                error_details=str(exc),
            )
        )

    @staticmethod
    def _result(
        index: int,
        page: PlannedPage,
        status: str,
        requests: int,
        *,
        elapsed_seconds: float | None = None,
        error_details: str | None = None,
    ) -> CurrentSeasonRefreshEntryResult:
        return CurrentSeasonRefreshEntryResult(
            index=index,
            phase=page.phase,
            url=page.url,
            month=page.month,
            team=page.team,
            game_id=page.game_id,
            status=status,
            requests=requests,
            elapsed_seconds=elapsed_seconds,
            error_details=error_details,
        )

    def report(self, stop: _StopRun | None) -> CurrentSeasonRefreshReport:
        fetched = [result for result in self.results if result.status == "fetched"]
        return CurrentSeasonRefreshReport(
            manifest_id=self.manifest.manifest_id,
            season_end_year=self.manifest.season_end_year,
            as_of=self.as_of.isoformat(),
            max_fetches=self.max_fetches,
            planned=dict(self.planned),
            cache_hits=sum(result.status == "cache_hit" for result in self.results),
            fetched=len(fetched),
            failures=sum(result.status == STOPPED_FAILED for result in self.results),
            rate_limited=sum(result.status == STOPPED_RATE_LIMITED for result in self.results),
            live_request_count=self.live_requests,
            fetched_bytes=sum(result.bytes or 0 for result in fetched),
            wall_seconds=round(self.clock() - self.started_at, 3),
            completed=stop is None,
            stopped_reason=None if stop is None else stop.reason,
            stopped_at_phase=None if stop is None else stop.phase,
            stopped_at_url=None if stop is None else stop.url,
            retry_after_seconds=None if stop is None else stop.retry_after_seconds,
            error_details=None if stop is None else stop.details,
            entries=tuple(self.results),
        )


def _ceilings(manifest: CurrentSeasonManifest) -> dict[str, int]:
    return {
        "schedule_pages": manifest.max_schedule_pages,
        "team_pages": manifest.max_team_pages,
        "box_scores": manifest.max_box_scores,
        "requests_per_minute": manifest.requests_per_minute,
    }


def _request_spacing_seconds(settings: Settings, manifest: CurrentSeasonManifest) -> float:
    """The slower of the configured pace and the pace the manifest approves."""

    rpm_delay = 60.0 / min(settings.scraper_max_requests_per_minute, 20)
    manifest_delay = 60.0 / manifest.requests_per_minute
    return max(
        settings.scraper_min_delay_seconds,
        rpm_delay,
        manifest_delay,
        MINIMUM_SCRAPER_DELAY_SECONDS,
    )


__all__ = [
    "PLACEHOLDER_USER_AGENT",
    "STOPPED_FAILED",
    "STOPPED_MAX_FETCHES",
    "STOPPED_PLAN_REFUSED",
    "STOPPED_RATE_LIMITED",
    "CurrentSeasonAcquisitionClient",
    "CurrentSeasonAcquisitionConfigurationError",
    "CurrentSeasonAcquisitionStopped",
    "CurrentSeasonDryRunReport",
    "CurrentSeasonRefreshEntryResult",
    "CurrentSeasonRefreshReport",
    "build_current_season_dry_run_report",
    "refresh_current_season",
    "validate_current_season_acquisition_settings",
    "validate_settings_within_manifest_policy",
]
