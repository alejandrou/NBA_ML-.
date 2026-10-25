"""The manifest contract for the Stage 2 per-season game acquisition (F8-004).

A season manifest lists one season's Basketball Reference URLs of one page
type — league schedule pages or box scores — and records the owner's approval
of exactly those URLs. It is part of the live-scraping approval interlock: the
`acquire-game-season` command runs only an approved manifest, and only with
`--owner-approved` and `--execute-approved-manifest`.

The planner (`game_season_planning.py`) writes drafts: `status: draft`,
`approved_by_owner: false`. A draft loads for planning and dry runs and is
refused by the acquire command. The owner approves a manifest by copying it into
`tasks/manifests/` with the approval fields filled in (F8-006).

This contract is a copy of the F8-001 pilot's (`game_pilot_manifest.py`) with
its own ceiling and messages; the pilot's contract is left unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nba_data.domain.team_codes import is_synthetic_team_code
from nba_data.scraping.game_pilot_manifest import (
    GAME_ID_RE,
    MONTHS,
    PAGE_TYPE_BOX_SCORE,
    PAGE_TYPE_LEAGUE_SCHEDULE,
    GamePilotManifestError,
    parse_game_id,
)

SEASON_PAGE_TYPES = (PAGE_TYPE_LEAGUE_SCHEDULE, PAGE_TYPE_BOX_SCORE)
STAGE_2_SEASON_END_YEARS = tuple(range(2015, 2027))
"""2014-15 to 2025-26: the seasons Stage 2 acquires (`docs/ml/PREDICTOR_PLAN.md`)."""

MAX_SEASON_URLS = 1400
MAX_DEFAULT_REQUESTS_PER_MINUTE = 10
MAX_ABSOLUTE_REQUESTS_PER_MINUTE = 20
WRITE_TARGET = "HtmlCache .html.gz"

STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"

_SCHEDULE_PATH_PREFIX = "/leagues/NBA_"

# A season is played between these two dates. The windows of consecutive
# seasons overlap (the 2020 bubble ran into October 2020, and 2020-21 began in
# December 2020), so this is a sanity bound, never a way to derive the season.
_SEASON_WINDOW_START = (8, 1)
_SEASON_WINDOW_END = (10, 31)


class GameSeasonManifestError(ValueError):
    """Raised when a season manifest is not safe to plan or execute."""


@dataclass(frozen=True)
class GameSeasonManifestEntry:
    page_type: str
    url: str
    season_end_year: int
    reason: str
    game_id: str | None = None
    month: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "page_type": self.page_type,
            "url": self.url,
            "season_end_year": self.season_end_year,
            "game_id": self.game_id,
            "month": self.month,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GameSeasonManifest:
    manifest_id: str
    status: str
    approved_at: str | None
    approval_basis: str | None
    season_end_year: int
    page_type: str
    requests_per_minute: int
    max_requests_per_minute: int
    entries: tuple[GameSeasonManifestEntry, ...]

    @property
    def approved(self) -> bool:
        return self.status == STATUS_APPROVED


def load_game_season_manifest(
    path: str | Path,
    *,
    require_approval: bool,
) -> GameSeasonManifest:
    """Load a season manifest; a draft is refused when approval is required."""

    manifest_path = Path(path)
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"Manifest cannot be read: {manifest_path}"
        raise GameSeasonManifestError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Manifest JSON is invalid: {exc.msg}"
        raise GameSeasonManifestError(msg) from exc

    if not isinstance(raw_manifest, Mapping):
        msg = "manifest must be a JSON object"
        raise GameSeasonManifestError(msg)
    return validate_game_season_manifest(raw_manifest, require_approval=require_approval)


def validate_game_season_manifest(
    raw_manifest: Mapping[str, Any],
    *,
    require_approval: bool,
) -> GameSeasonManifest:
    manifest_id = _require_non_empty_str(raw_manifest, "manifest_id", "manifest")
    status, approved_at, approval_basis = _validate_approval(
        raw_manifest, require_approval=require_approval
    )

    scope = _require_mapping(raw_manifest, "scope", "manifest")
    season_end_year = _require_int(scope, "season_end_year", "scope")
    if season_end_year not in STAGE_2_SEASON_END_YEARS:
        msg = (
            f"scope.season_end_year must be a Stage 2 season "
            f"({STAGE_2_SEASON_END_YEARS[0]}-{STAGE_2_SEASON_END_YEARS[-1]})"
        )
        raise GameSeasonManifestError(msg)
    page_type = _require_non_empty_str(scope, "page_type", "scope")
    if page_type not in SEASON_PAGE_TYPES:
        msg = f"scope.page_type must be one of {list(SEASON_PAGE_TYPES)}"
        raise GameSeasonManifestError(msg)
    max_urls = _require_int(scope, "max_urls", "scope")
    if max_urls < 1 or max_urls > MAX_SEASON_URLS:
        msg = f"scope.max_urls must be between 1 and {MAX_SEASON_URLS} for one season"
        raise GameSeasonManifestError(msg)

    policy = _require_mapping(raw_manifest, "acquisition_policy", "manifest")
    for flag in ("cache_first", "sequential", "stop_on_first_failure"):
        if policy.get(flag) is not True:
            msg = f"acquisition_policy.{flag} must be true"
            raise GameSeasonManifestError(msg)
    requests_per_minute = _require_int(policy, "requests_per_minute", "acquisition_policy")
    if requests_per_minute < 1 or requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = (
            "acquisition_policy.requests_per_minute must be between 1 and "
            f"{MAX_DEFAULT_REQUESTS_PER_MINUTE}"
        )
        raise GameSeasonManifestError(msg)
    max_requests_per_minute = _require_int(policy, "max_requests_per_minute", "acquisition_policy")
    if not requests_per_minute <= max_requests_per_minute <= MAX_ABSOLUTE_REQUESTS_PER_MINUTE:
        msg = (
            "acquisition_policy.max_requests_per_minute must be >= requests_per_minute "
            f"and <= {MAX_ABSOLUTE_REQUESTS_PER_MINUTE}"
        )
        raise GameSeasonManifestError(msg)
    if _require_non_empty_str(policy, "write_target", "acquisition_policy") != WRITE_TARGET:
        msg = f"acquisition_policy.write_target must be {WRITE_TARGET!r}"
        raise GameSeasonManifestError(msg)

    raw_entries = raw_manifest.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        msg = "manifest.entries must be a non-empty JSON array"
        raise GameSeasonManifestError(msg)
    if len(raw_entries) > max_urls:
        msg = "manifest.entries exceeds scope.max_urls"
        raise GameSeasonManifestError(msg)

    entries = _validate_entries(raw_entries, season_end_year=season_end_year, page_type=page_type)
    return GameSeasonManifest(
        manifest_id=manifest_id,
        status=status,
        approved_at=approved_at,
        approval_basis=approval_basis,
        season_end_year=season_end_year,
        page_type=page_type,
        requests_per_minute=requests_per_minute,
        max_requests_per_minute=max_requests_per_minute,
        entries=entries,
    )


def _validate_approval(
    raw_manifest: Mapping[str, Any],
    *,
    require_approval: bool,
) -> tuple[str, str | None, str | None]:
    status = _require_non_empty_str(raw_manifest, "status", "manifest")
    approved_by_owner = raw_manifest.get("approved_by_owner")
    if not require_approval and status not in (STATUS_DRAFT, STATUS_APPROVED):
        msg = "manifest.status must be 'draft' or 'approved'"
        raise GameSeasonManifestError(msg)

    if require_approval or status == STATUS_APPROVED:
        if status != STATUS_APPROVED:
            msg = "manifest.status must be 'approved'"
            raise GameSeasonManifestError(msg)
        if approved_by_owner is not True:
            msg = "manifest.approved_by_owner must be true"
            raise GameSeasonManifestError(msg)
        approved_at = _require_aware_timestamp(raw_manifest, "approved_at", "manifest")
        approval_basis = _require_non_empty_str(raw_manifest, "approval_basis", "manifest")
        return status, approved_at, approval_basis

    # A draft never claims an approval it does not have.
    if approved_by_owner is not False:
        msg = "a draft manifest must carry approved_by_owner: false"
        raise GameSeasonManifestError(msg)
    return status, None, None


def _validate_entries(
    raw_entries: list[object],
    *,
    season_end_year: int,
    page_type: str,
) -> tuple[GameSeasonManifestEntry, ...]:
    seen_urls: set[str] = set()
    entries: list[GameSeasonManifestEntry] = []

    for index, raw_entry in enumerate(raw_entries):
        context = f"entries[{index}]"
        if not isinstance(raw_entry, Mapping):
            msg = f"{context} must be a JSON object"
            raise GameSeasonManifestError(msg)

        entry_page_type = _require_non_empty_str(raw_entry, "page_type", context)
        if entry_page_type != page_type:
            msg = f"{context}.page_type must be the manifest's page type {page_type!r}"
            raise GameSeasonManifestError(msg)

        url = _require_non_empty_str(raw_entry, "url", context)
        if url in seen_urls:
            msg = f"{context}.url duplicates an earlier manifest entry"
            raise GameSeasonManifestError(msg)
        seen_urls.add(url)

        entry_season = _require_int(raw_entry, "season_end_year", context)
        if entry_season != season_end_year:
            msg = f"{context}.season_end_year must be the manifest's season {season_end_year}"
            raise GameSeasonManifestError(msg)
        reason = _require_non_empty_str(raw_entry, "reason", context)
        path = _require_basketball_reference_path(url, context)

        if page_type == PAGE_TYPE_LEAGUE_SCHEDULE:
            entries.append(
                _schedule_entry(
                    raw_entry,
                    path=path,
                    url=url,
                    season_end_year=season_end_year,
                    reason=reason,
                    context=context,
                )
            )
        else:
            entries.append(
                _box_score_entry(
                    raw_entry,
                    path=path,
                    url=url,
                    season_end_year=season_end_year,
                    reason=reason,
                    context=context,
                )
            )

    return tuple(entries)


def _schedule_entry(
    raw_entry: Mapping[str, Any],
    *,
    path: str,
    url: str,
    season_end_year: int,
    reason: str,
    context: str,
) -> GameSeasonManifestEntry:
    url_month = _schedule_path_month(path, season_end_year, context)
    month = raw_entry.get("month")
    if month != url_month:
        msg = f"{context}.month must match the month in the URL ({url_month!r})"
        raise GameSeasonManifestError(msg)

    return GameSeasonManifestEntry(
        page_type=PAGE_TYPE_LEAGUE_SCHEDULE,
        url=url,
        season_end_year=season_end_year,
        reason=reason,
        month=url_month,
    )


def _schedule_path_month(path: str, season_end_year: int, context: str) -> str | None:
    """The month a schedule URL names, or None for the season page."""

    prefix = f"{_SCHEDULE_PATH_PREFIX}{season_end_year}_games"
    if not path.startswith(prefix) or not path.endswith(".html"):
        msg = f"{context}.url must be a {season_end_year} Basketball Reference league schedule URL"
        raise GameSeasonManifestError(msg)
    suffix = path[len(prefix) : -len(".html")]
    if not suffix:
        return None
    month = suffix.removeprefix("-")
    if suffix == month or not is_schedule_month(month):
        msg = f"{context}.url names an unknown month: {suffix!r}"
        raise GameSeasonManifestError(msg)
    return month


def is_schedule_month(month: str) -> bool:
    """A schedule month slug: a month name, optionally with a four-digit year."""

    name, _, year = month.partition("-")
    return name in MONTHS and (not year or (len(year) == 4 and year.isdigit()))


def _box_score_entry(
    raw_entry: Mapping[str, Any],
    *,
    path: str,
    url: str,
    season_end_year: int,
    reason: str,
    context: str,
) -> GameSeasonManifestEntry:
    game_id = _require_non_empty_str(raw_entry, "game_id", context)
    if path != f"/boxscores/{game_id}.html" or GAME_ID_RE.fullmatch(game_id) is None:
        msg = f"{context}.url must be the Basketball Reference box_score URL of its game_id"
        raise GameSeasonManifestError(msg)

    try:
        game_date, home_code = parse_game_id(game_id)
    except GamePilotManifestError as exc:
        msg = f"{context}: {exc}"
        raise GameSeasonManifestError(msg) from exc
    if is_synthetic_team_code(home_code):
        msg = f"{context}.game_id names {home_code}, which is a marker, not a team"
        raise GameSeasonManifestError(msg)

    window_start = date(season_end_year - 1, *_SEASON_WINDOW_START)
    window_end = date(season_end_year, *_SEASON_WINDOW_END)
    if not window_start <= game_date <= window_end:
        msg = (
            f"{context}.game_id date {game_date.isoformat()} is outside the "
            f"{season_end_year} season window"
        )
        raise GameSeasonManifestError(msg)

    return GameSeasonManifestEntry(
        page_type=PAGE_TYPE_BOX_SCORE,
        url=url,
        season_end_year=season_end_year,
        reason=reason,
        game_id=game_id,
    )


def _require_basketball_reference_path(url: str, context: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.basketball-reference.com"
        or parsed.query
        or parsed.fragment
        or parsed.params
    ):
        msg = f"{context}.url must be an explicit https://www.basketball-reference.com URL"
        raise GameSeasonManifestError(msg)
    return parsed.path


def _require_aware_timestamp(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = _require_non_empty_str(mapping, field, context)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        msg = f"{context}.{field} must be an ISO-8601 timestamp"
        raise GameSeasonManifestError(msg) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        msg = f"{context}.{field} must carry a timezone"
        raise GameSeasonManifestError(msg)
    return value


def _require_mapping(mapping: Mapping[str, Any], field: str, context: str) -> Mapping[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, Mapping):
        msg = f"{context}.{field} must be a JSON object"
        raise GameSeasonManifestError(msg)
    return value


def _require_non_empty_str(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        msg = f"{context}.{field} must be a non-empty string"
        raise GameSeasonManifestError(msg)
    return value.strip()


def _require_int(mapping: Mapping[str, Any], field: str, context: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{context}.{field} must be an integer"
        raise GameSeasonManifestError(msg)
    return value


__all__ = [
    "MAX_ABSOLUTE_REQUESTS_PER_MINUTE",
    "MAX_DEFAULT_REQUESTS_PER_MINUTE",
    "MAX_SEASON_URLS",
    "SEASON_PAGE_TYPES",
    "STAGE_2_SEASON_END_YEARS",
    "STATUS_APPROVED",
    "STATUS_DRAFT",
    "WRITE_TARGET",
    "GameSeasonManifest",
    "GameSeasonManifestEntry",
    "GameSeasonManifestError",
    "is_schedule_month",
    "load_game_season_manifest",
    "validate_game_season_manifest",
]
