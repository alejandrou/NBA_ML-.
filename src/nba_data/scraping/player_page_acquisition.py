from __future__ import annotations

import gzip
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from nba_data.config.settings import Settings
from nba_data.db.models import Player, PlayerSeason, Season
from nba_data.domain.player_id import (
    PLAYER_ID_MAX_LENGTH,
    PLAYER_ID_MIN_LENGTH,
    PLAYER_ID_PATTERN,
)
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import RateLimitExceededError

BASE_URL = "https://www.basketball-reference.com"
PAGE_TYPE = "player_page"
PLAYER_PAGE_MAX_REQUESTS_PER_MINUTE = 10

_PLAYER_ID_RE = re.compile(rf"^{PLAYER_ID_PATTERN}$", re.IGNORECASE)


class PlayerPageAcquisitionConfigurationError(ValueError):
    """Raised when a controlled player-page acquisition cannot run safely."""


class PlayerPageCacheWriteError(RuntimeError):
    """Raised when a player-page cache write cannot complete safely."""


class PlayerPageAcquisitionStopped(RuntimeError):
    """Raised when player-page acquisition stops early with a partial report."""

    def __init__(self, message: str, report: PlayerPageAcquisitionReport) -> None:
        super().__init__(message)
        self.report = report


class PlayerPageAcquisitionClient(Protocol):
    def get(self, url: str, *, force_refresh: bool = False) -> str:
        """Return raw HTML for one URL."""


@dataclass(frozen=True)
class PlayerPageManifestEntry:
    player_id: str
    first_letter: str
    url: str
    matched_season_years: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "first_letter": self.first_letter,
            "url": self.url,
            "matched_season_years": list(self.matched_season_years),
        }


@dataclass(frozen=True)
class PlayerPageManifest:
    manifest_id: str
    total_players: int
    start_year: int | None
    end_year: int | None
    requested_player: str | None
    limit: int | None
    entries: tuple[PlayerPageManifestEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "total_players": self.total_players,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "requested_player": self.requested_player,
            "limit": self.limit,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class PlayerPageDryRunEntry:
    index: int
    player_id: str
    first_letter: str
    url: str
    cache_path: str
    cache_status: str
    estimated_fetch_count: int
    matched_season_years: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "player_id": self.player_id,
            "first_letter": self.first_letter,
            "url": self.url,
            "cache_path": self.cache_path,
            "cache_status": self.cache_status,
            "estimated_fetch_count": self.estimated_fetch_count,
            "matched_season_years": list(self.matched_season_years),
        }


@dataclass(frozen=True)
class PlayerPageDryRunReport:
    manifest_id: str
    total_players: int
    start_year: int | None
    end_year: int | None
    requested_player: str | None
    limit: int | None
    cache_hits: int
    missing_cache_entries: int
    estimated_fetch_count: int
    entries: tuple[PlayerPageDryRunEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "total_players": self.total_players,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "requested_player": self.requested_player,
            "limit": self.limit,
            "cache_hits": self.cache_hits,
            "missing_cache_entries": self.missing_cache_entries,
            "estimated_fetch_count": self.estimated_fetch_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class PlayerPageAcquisitionEntryResult:
    index: int
    player_id: str
    first_letter: str
    url: str
    cache_path: str
    status: str
    matched_season_years: tuple[int, ...]
    error_details: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "player_id": self.player_id,
            "first_letter": self.first_letter,
            "url": self.url,
            "cache_path": self.cache_path,
            "status": self.status,
            "matched_season_years": list(self.matched_season_years),
            "error_details": self.error_details,
        }


@dataclass(frozen=True)
class PlayerPageAcquisitionReport:
    manifest_id: str
    total_players: int
    start_year: int | None
    end_year: int | None
    requested_player: str | None
    limit: int | None
    processed_entries: int
    cache_hits: int
    fetched: int
    failures: int
    rate_limited: int
    live_request_count: int
    completed: bool
    stopped_reason: str | None
    stopped_at_entry: int | None
    entries: tuple[PlayerPageAcquisitionEntryResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "total_players": self.total_players,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "requested_player": self.requested_player,
            "limit": self.limit,
            "processed_entries": self.processed_entries,
            "cache_hits": self.cache_hits,
            "fetched": self.fetched,
            "failures": self.failures,
            "rate_limited": self.rate_limited,
            "live_request_count": self.live_request_count,
            "completed": self.completed,
            "stopped_reason": self.stopped_reason,
            "stopped_at_entry": self.stopped_at_entry,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def validate_player_page_acquisition_settings(settings: Settings) -> None:
    if settings.scraper_max_requests_per_minute > PLAYER_PAGE_MAX_REQUESTS_PER_MINUTE:
        msg = (
            "F4E-010 allows at most "
            f"{PLAYER_PAGE_MAX_REQUESTS_PER_MINUTE} requests/minute"
        )
        raise PlayerPageAcquisitionConfigurationError(msg)


def build_player_page_url(player_id: str) -> str:
    normalized = _normalize_player_id(player_id)
    return f"{BASE_URL}/players/{normalized[0]}/{normalized}.html"


def build_player_page_manifest(
    session: Session,
    *,
    limit: int | None = None,
    player: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> PlayerPageManifest:
    _validate_manifest_inputs(limit=limit, player=player, start_year=start_year, end_year=end_year)
    normalized_player = _normalize_player_id(player) if player is not None else None

    if start_year is None and end_year is None:
        entries = _build_unfiltered_entries(session, player=normalized_player)
    else:
        entries = _build_season_filtered_entries(
            session,
            player=normalized_player,
            start_year=start_year,
            end_year=end_year,
        )

    if limit is not None:
        entries = entries[:limit]

    manifest_id = (
        "player-pages"
        f"-player-{normalized_player or 'all'}"
        f"-start-{start_year if start_year is not None else 'all'}"
        f"-end-{end_year if end_year is not None else 'all'}"
        f"-limit-{limit if limit is not None else 'all'}"
    )
    return PlayerPageManifest(
        manifest_id=manifest_id,
        total_players=len(entries),
        start_year=start_year,
        end_year=end_year,
        requested_player=normalized_player,
        limit=limit,
        entries=tuple(entries),
    )


def build_player_page_dry_run_report(
    session: Session,
    *,
    cache: HtmlCache,
    limit: int | None = None,
    player: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> PlayerPageDryRunReport:
    manifest = build_player_page_manifest(
        session,
        limit=limit,
        player=player,
        start_year=start_year,
        end_year=end_year,
    )
    entries: list[PlayerPageDryRunEntry] = []
    cache_hits = 0
    missing_cache_entries = 0

    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            cache_status = "hit"
            estimated_fetch_count = 0
            cache_hits += 1
        else:
            cache_status = "missing"
            estimated_fetch_count = 1
            missing_cache_entries += 1

        entries.append(
            PlayerPageDryRunEntry(
                index=index,
                player_id=manifest_entry.player_id,
                first_letter=manifest_entry.first_letter,
                url=manifest_entry.url,
                cache_path=str(cache_path),
                cache_status=cache_status,
                estimated_fetch_count=estimated_fetch_count,
                matched_season_years=manifest_entry.matched_season_years,
            )
        )

    return PlayerPageDryRunReport(
        manifest_id=manifest.manifest_id,
        total_players=manifest.total_players,
        start_year=manifest.start_year,
        end_year=manifest.end_year,
        requested_player=manifest.requested_player,
        limit=manifest.limit,
        cache_hits=cache_hits,
        missing_cache_entries=missing_cache_entries,
        estimated_fetch_count=missing_cache_entries,
        entries=tuple(entries),
    )


def acquire_player_page_manifest(
    manifest: PlayerPageManifest,
    *,
    cache: HtmlCache,
    client: PlayerPageAcquisitionClient,
) -> PlayerPageAcquisitionReport:
    results: list[PlayerPageAcquisitionEntryResult] = []

    for index, manifest_entry in enumerate(manifest.entries, start=1):
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            results.append(
                PlayerPageAcquisitionEntryResult(
                    index=index,
                    player_id=manifest_entry.player_id,
                    first_letter=manifest_entry.first_letter,
                    url=manifest_entry.url,
                    cache_path=str(cache_path),
                    status="cache_hit",
                    matched_season_years=manifest_entry.matched_season_years,
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
                    entry=manifest_entry,
                    cache_path=cache_path,
                    status="rate_limited",
                    error_details=str(exc),
                )
            )
            report = _build_acquisition_report(
                manifest,
                results,
                completed=False,
                stopped_reason="rate_limited",
                stopped_at_entry=index,
            )
            msg = f"Player-page acquisition rate-limited at {manifest_entry.url}"
            raise PlayerPageAcquisitionStopped(msg, report) from exc
        except Exception as exc:
            results.append(
                _stopped_entry(
                    index=index,
                    entry=manifest_entry,
                    cache_path=cache_path,
                    status="failed",
                    error_details=str(exc),
                )
            )
            report = _build_acquisition_report(
                manifest,
                results,
                completed=False,
                stopped_reason="failed",
                stopped_at_entry=index,
            )
            msg = f"Player-page acquisition failed at {manifest_entry.url}"
            raise PlayerPageAcquisitionStopped(msg, report) from exc

        results.append(
            PlayerPageAcquisitionEntryResult(
                index=index,
                player_id=manifest_entry.player_id,
                first_letter=manifest_entry.first_letter,
                url=manifest_entry.url,
                cache_path=str(written_path),
                status="fetched",
                matched_season_years=manifest_entry.matched_season_years,
            )
        )

    return _build_acquisition_report(
        manifest,
        results,
        completed=True,
        stopped_reason=None,
        stopped_at_entry=None,
    )


def _build_unfiltered_entries(
    session: Session,
    *,
    player: str | None,
) -> list[PlayerPageManifestEntry]:
    # `basketball_reference_player_id` is nullable in the model, so the select
    # is typed as optional even with the `is_not(None)` filter; the None guard
    # below is what narrows it.
    statement: Select[tuple[str | None]] = (
        select(Player.basketball_reference_player_id)
        .where(Player.basketball_reference_player_id.is_not(None))
        .order_by(Player.basketball_reference_player_id.asc())
    )
    if player is not None:
        statement = statement.where(Player.basketball_reference_player_id == player)

    player_ids = [
        _normalize_player_id(player_id)
        for player_id in session.scalars(statement)
        if player_id is not None
    ]
    return [
        PlayerPageManifestEntry(
            player_id=player_id,
            first_letter=player_id[0],
            url=build_player_page_url(player_id),
            matched_season_years=(),
        )
        for player_id in player_ids
    ]


def _build_season_filtered_entries(
    session: Session,
    *,
    player: str | None,
    start_year: int | None,
    end_year: int | None,
) -> list[PlayerPageManifestEntry]:
    statement = (
        select(Player.basketball_reference_player_id, Season.season_year)
        .join(PlayerSeason, PlayerSeason.player_id == Player.id)
        .join(Season, Season.id == PlayerSeason.season_id)
        .where(Player.basketball_reference_player_id.is_not(None))
        .order_by(Player.basketball_reference_player_id.asc(), Season.season_year.asc())
    )
    if player is not None:
        statement = statement.where(Player.basketball_reference_player_id == player)
    if start_year is not None:
        statement = statement.where(Season.season_year >= start_year)
    if end_year is not None:
        statement = statement.where(Season.season_year <= end_year)

    season_years_by_player: dict[str, list[int]] = {}
    for player_id, season_year in session.execute(statement):
        normalized = _normalize_player_id(player_id)
        season_years_by_player.setdefault(normalized, []).append(season_year)

    return [
        PlayerPageManifestEntry(
            player_id=player_id,
            first_letter=player_id[0],
            url=build_player_page_url(player_id),
            matched_season_years=tuple(sorted(set(season_years))),
        )
        for player_id, season_years in season_years_by_player.items()
    ]


def _validate_manifest_inputs(
    *,
    limit: int | None,
    player: str | None,
    start_year: int | None,
    end_year: int | None,
) -> None:
    if limit is not None and limit <= 0:
        msg = "limit must be a positive integer"
        raise PlayerPageAcquisitionConfigurationError(msg)
    if player is not None and not player.strip():
        msg = "player must be a non-empty basketball_reference_player_id"
        raise PlayerPageAcquisitionConfigurationError(msg)
    if start_year is not None and end_year is not None and start_year > end_year:
        msg = "start_year must be less than or equal to end_year"
        raise PlayerPageAcquisitionConfigurationError(msg)


def _normalize_player_id(player_id: str | None) -> str:
    if player_id is None or not player_id.strip():
        msg = "basketball_reference_player_id is required"
        raise PlayerPageAcquisitionConfigurationError(msg)
    normalized = player_id.strip().lower()
    if not _PLAYER_ID_RE.fullmatch(normalized):
        msg = f"Unsupported basketball_reference_player_id: {player_id!r}"
        raise PlayerPageAcquisitionConfigurationError(msg)
    return normalized


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
        raise PlayerPageCacheWriteError(msg)

    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(f".{final_path.name}.{uuid.uuid4().hex}.tmp")

    try:
        with gzip.open(temp_path, "wt", encoding="utf-8", newline="") as file:
            file.write(html)
        with gzip.open(temp_path, "rt", encoding="utf-8", newline="") as file:
            if file.read() != html:
                msg = f"Cache write verification failed for {final_path}"
                raise PlayerPageCacheWriteError(msg)
        if final_path.exists():
            msg = f"Refusing to overwrite existing cache file: {final_path}"
            raise PlayerPageCacheWriteError(msg)
        os.replace(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return final_path


def _stopped_entry(
    *,
    index: int,
    entry: PlayerPageManifestEntry,
    cache_path: Path,
    status: str,
    error_details: str,
) -> PlayerPageAcquisitionEntryResult:
    return PlayerPageAcquisitionEntryResult(
        index=index,
        player_id=entry.player_id,
        first_letter=entry.first_letter,
        url=entry.url,
        cache_path=str(cache_path),
        status=status,
        matched_season_years=entry.matched_season_years,
        error_details=error_details,
    )


def _build_acquisition_report(
    manifest: PlayerPageManifest,
    results: list[PlayerPageAcquisitionEntryResult],
    *,
    completed: bool,
    stopped_reason: str | None,
    stopped_at_entry: int | None,
) -> PlayerPageAcquisitionReport:
    return PlayerPageAcquisitionReport(
        manifest_id=manifest.manifest_id,
        total_players=manifest.total_players,
        start_year=manifest.start_year,
        end_year=manifest.end_year,
        requested_player=manifest.requested_player,
        limit=manifest.limit,
        processed_entries=len(results),
        cache_hits=sum(result.status == "cache_hit" for result in results),
        fetched=sum(result.status == "fetched" for result in results),
        failures=sum(result.status == "failed" for result in results),
        rate_limited=sum(result.status == "rate_limited" for result in results),
        live_request_count=sum(
            result.status in {"fetched", "failed", "rate_limited"} for result in results
        ),
        completed=completed,
        stopped_reason=stopped_reason,
        stopped_at_entry=stopped_at_entry,
        entries=tuple(results),
    )


__all__ = [
    "PAGE_TYPE",
    "PLAYER_ID_MAX_LENGTH",
    "PLAYER_ID_MIN_LENGTH",
    "PLAYER_ID_PATTERN",
    "PLAYER_PAGE_MAX_REQUESTS_PER_MINUTE",
    "PlayerPageAcquisitionClient",
    "PlayerPageAcquisitionConfigurationError",
    "PlayerPageAcquisitionEntryResult",
    "PlayerPageAcquisitionReport",
    "PlayerPageAcquisitionStopped",
    "PlayerPageDryRunEntry",
    "PlayerPageDryRunReport",
    "PlayerPageManifest",
    "PlayerPageManifestEntry",
    "build_player_page_dry_run_report",
    "build_player_page_manifest",
    "build_player_page_url",
    "acquire_player_page_manifest",
    "validate_player_page_acquisition_settings",
]
