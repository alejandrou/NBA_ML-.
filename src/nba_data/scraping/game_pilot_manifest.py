"""The approved-manifest contract for the F8-001 per-game acquisition pilot.

A pilot manifest lists explicit Basketball Reference URLs of three page types —
league schedule, box score, and play-by-play — and records the owner's approval
of exactly those URLs. It is part of the live-scraping approval interlock: the
`acquire-game-pilot` command runs only an approved manifest, and only with
`--owner-approved` and `--execute-approved-manifest`.

A Basketball Reference game id is the game date, a `0`, and the home team code:
`202310240DEN` is Lakers at Nuggets on 2023-10-24.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nba_data.domain.team_codes import is_synthetic_team_code

BASE_URL = "https://www.basketball-reference.com"
PAGE_TYPE_LEAGUE_SCHEDULE = "league_schedule"
PAGE_TYPE_BOX_SCORE = "box_score"
PAGE_TYPE_PLAY_BY_PLAY = "play_by_play"
PAGE_TYPES = (PAGE_TYPE_LEAGUE_SCHEDULE, PAGE_TYPE_BOX_SCORE, PAGE_TYPE_PLAY_BY_PLAY)
GAME_PAGE_TYPES = (PAGE_TYPE_BOX_SCORE, PAGE_TYPE_PLAY_BY_PLAY)

MAX_PILOT_URLS = 100
MAX_DEFAULT_REQUESTS_PER_MINUTE = 10
MAX_ABSOLUTE_REQUESTS_PER_MINUTE = 20
WRITE_TARGET = "HtmlCache .html.gz"

MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

GAME_ID_RE = re.compile(r"(?P<date>[0-9]{8})0(?P<home>[A-Z]{3})")
_SCHEDULE_PATH_RE = re.compile(
    r"^/leagues/NBA_(?P<year>[0-9]{4})_games(?:-(?P<month>[a-z]+(?:-[0-9]{4})?))?\.html$"
)
_BOX_SCORE_PATH_RE = re.compile(rf"^/boxscores/(?P<game_id>{GAME_ID_RE.pattern})\.html$")
_PLAY_BY_PLAY_PATH_RE = re.compile(rf"^/boxscores/pbp/(?P<game_id>{GAME_ID_RE.pattern})\.html$")

# A season is played between these two dates. The windows of consecutive
# seasons overlap (the 2020 bubble ran into October 2020, and 2020-21 began in
# December 2020), so this is a sanity bound, never a way to derive the season.
_SEASON_WINDOW_START = (8, 1)
_SEASON_WINDOW_END = (10, 31)


class GamePilotManifestError(ValueError):
    """Raised when a pilot manifest is not safe to plan or execute."""


@dataclass(frozen=True)
class GamePilotManifestEntry:
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
class GamePilotManifest:
    manifest_id: str
    approved_at: str
    approval_basis: str
    requests_per_minute: int
    max_requests_per_minute: int
    entries: tuple[GamePilotManifestEntry, ...]

    @property
    def game_ids(self) -> tuple[str, ...]:
        """Distinct game ids in manifest order."""

        seen: dict[str, None] = {}
        for entry in self.entries:
            if entry.game_id is not None:
                seen.setdefault(entry.game_id, None)
        return tuple(seen)


def box_score_url(game_id: str) -> str:
    return f"{BASE_URL}/boxscores/{game_id}.html"


def play_by_play_url(game_id: str) -> str:
    return f"{BASE_URL}/boxscores/pbp/{game_id}.html"


def league_schedule_url(season_end_year: int, month: str | None = None) -> str:
    suffix = f"-{month}" if month else ""
    return f"{BASE_URL}/leagues/NBA_{season_end_year}_games{suffix}.html"


def parse_game_id(game_id: str) -> tuple[date, str]:
    """Return the game date and home team code a game id encodes."""

    match = GAME_ID_RE.fullmatch(game_id)
    if match is None:
        msg = f"Unsupported Basketball Reference game id: {game_id!r}"
        raise GamePilotManifestError(msg)
    try:
        game_date = datetime.strptime(match.group("date"), "%Y%m%d").date()
    except ValueError as exc:
        msg = f"Game id {game_id!r} does not start with a real date"
        raise GamePilotManifestError(msg) from exc
    return game_date, match.group("home")


def load_game_pilot_manifest(path: str | Path) -> GamePilotManifest:
    manifest_path = Path(path)
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"Manifest cannot be read: {manifest_path}"
        raise GamePilotManifestError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Manifest JSON is invalid: {exc.msg}"
        raise GamePilotManifestError(msg) from exc

    if not isinstance(raw_manifest, Mapping):
        msg = "manifest must be a JSON object"
        raise GamePilotManifestError(msg)
    return validate_game_pilot_manifest(raw_manifest)


def validate_game_pilot_manifest(raw_manifest: Mapping[str, Any]) -> GamePilotManifest:
    manifest_id = _require_non_empty_str(raw_manifest, "manifest_id", "manifest")
    status = _require_non_empty_str(raw_manifest, "status", "manifest")
    if status != "approved":
        msg = "manifest.status must be 'approved'"
        raise GamePilotManifestError(msg)
    if raw_manifest.get("approved_by_owner") is not True:
        msg = "manifest.approved_by_owner must be true"
        raise GamePilotManifestError(msg)
    approved_at = _require_aware_timestamp(raw_manifest, "approved_at", "manifest")
    approval_basis = _require_non_empty_str(raw_manifest, "approval_basis", "manifest")

    scope = _require_mapping(raw_manifest, "scope", "manifest")
    scope_page_types = _require_page_types(scope)
    max_urls = _require_int(scope, "max_urls", "scope")
    if max_urls < 1 or max_urls > MAX_PILOT_URLS:
        msg = f"scope.max_urls must be between 1 and {MAX_PILOT_URLS} for the pilot"
        raise GamePilotManifestError(msg)

    policy = _require_mapping(raw_manifest, "acquisition_policy", "manifest")
    for flag in ("cache_first", "sequential", "stop_on_first_failure"):
        if policy.get(flag) is not True:
            msg = f"acquisition_policy.{flag} must be true"
            raise GamePilotManifestError(msg)
    requests_per_minute = _require_int(policy, "requests_per_minute", "acquisition_policy")
    if requests_per_minute < 1 or requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = (
            "acquisition_policy.requests_per_minute must be between 1 and "
            f"{MAX_DEFAULT_REQUESTS_PER_MINUTE}"
        )
        raise GamePilotManifestError(msg)
    max_requests_per_minute = _require_int(policy, "max_requests_per_minute", "acquisition_policy")
    if not requests_per_minute <= max_requests_per_minute <= MAX_ABSOLUTE_REQUESTS_PER_MINUTE:
        msg = (
            "acquisition_policy.max_requests_per_minute must be >= requests_per_minute "
            f"and <= {MAX_ABSOLUTE_REQUESTS_PER_MINUTE}"
        )
        raise GamePilotManifestError(msg)
    if _require_non_empty_str(policy, "write_target", "acquisition_policy") != WRITE_TARGET:
        msg = f"acquisition_policy.write_target must be {WRITE_TARGET!r}"
        raise GamePilotManifestError(msg)

    raw_entries = raw_manifest.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        msg = "manifest.entries must be a non-empty JSON array"
        raise GamePilotManifestError(msg)
    if len(raw_entries) > max_urls:
        msg = "manifest.entries exceeds scope.max_urls"
        raise GamePilotManifestError(msg)

    entries = _validate_entries(raw_entries, scope_page_types=scope_page_types)
    return GamePilotManifest(
        manifest_id=manifest_id,
        approved_at=approved_at,
        approval_basis=approval_basis,
        requests_per_minute=requests_per_minute,
        max_requests_per_minute=max_requests_per_minute,
        entries=entries,
    )


def _validate_entries(
    raw_entries: list[object],
    *,
    scope_page_types: frozenset[str],
) -> tuple[GamePilotManifestEntry, ...]:
    seen_urls: set[str] = set()
    entries: list[GamePilotManifestEntry] = []

    for index, raw_entry in enumerate(raw_entries):
        context = f"entries[{index}]"
        if not isinstance(raw_entry, Mapping):
            msg = f"{context} must be a JSON object"
            raise GamePilotManifestError(msg)

        page_type = _require_non_empty_str(raw_entry, "page_type", context)
        if page_type not in PAGE_TYPES:
            msg = f"{context}.page_type must be one of {list(PAGE_TYPES)}"
            raise GamePilotManifestError(msg)
        if page_type not in scope_page_types:
            msg = f"{context}.page_type {page_type!r} is outside scope.page_types"
            raise GamePilotManifestError(msg)

        url = _require_non_empty_str(raw_entry, "url", context)
        if url in seen_urls:
            msg = f"{context}.url duplicates an earlier manifest entry"
            raise GamePilotManifestError(msg)
        seen_urls.add(url)

        season_end_year = _require_int(raw_entry, "season_end_year", context)
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
                _game_entry(
                    raw_entry,
                    page_type=page_type,
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
) -> GamePilotManifestEntry:
    match = _SCHEDULE_PATH_RE.fullmatch(path)
    if match is None:
        msg = f"{context}.url must be a Basketball Reference league schedule URL"
        raise GamePilotManifestError(msg)
    if int(match.group("year")) != season_end_year:
        msg = f"{context}.season_end_year must match the year in the URL"
        raise GamePilotManifestError(msg)

    url_month = match.group("month")
    if url_month is not None and url_month.split("-", maxsplit=1)[0] not in MONTHS:
        msg = f"{context}.url names an unknown month: {url_month!r}"
        raise GamePilotManifestError(msg)
    month = raw_entry.get("month")
    if month != url_month:
        msg = f"{context}.month must match the month in the URL ({url_month!r})"
        raise GamePilotManifestError(msg)

    return GamePilotManifestEntry(
        page_type=PAGE_TYPE_LEAGUE_SCHEDULE,
        url=url,
        season_end_year=season_end_year,
        reason=reason,
        month=url_month,
    )


def _game_entry(
    raw_entry: Mapping[str, Any],
    *,
    page_type: str,
    path: str,
    url: str,
    season_end_year: int,
    reason: str,
    context: str,
) -> GamePilotManifestEntry:
    pattern = _BOX_SCORE_PATH_RE if page_type == PAGE_TYPE_BOX_SCORE else _PLAY_BY_PLAY_PATH_RE
    match = pattern.fullmatch(path)
    if match is None:
        msg = f"{context}.url must be a Basketball Reference {page_type} URL"
        raise GamePilotManifestError(msg)

    game_id = _require_non_empty_str(raw_entry, "game_id", context)
    if game_id != match.group("game_id"):
        msg = f"{context}.game_id must match the game id in the URL"
        raise GamePilotManifestError(msg)

    try:
        game_date, home_code = parse_game_id(game_id)
    except GamePilotManifestError as exc:
        msg = f"{context}: {exc}"
        raise GamePilotManifestError(msg) from exc
    if is_synthetic_team_code(home_code):
        msg = f"{context}.game_id names {home_code}, which is a marker, not a team"
        raise GamePilotManifestError(msg)

    window_start = date(season_end_year - 1, *_SEASON_WINDOW_START)
    window_end = date(season_end_year, *_SEASON_WINDOW_END)
    if not window_start <= game_date <= window_end:
        msg = (
            f"{context}.game_id date {game_date.isoformat()} is outside the "
            f"{season_end_year} season window"
        )
        raise GamePilotManifestError(msg)

    return GamePilotManifestEntry(
        page_type=page_type,
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
        raise GamePilotManifestError(msg)
    return parsed.path


def _require_page_types(scope: Mapping[str, Any]) -> frozenset[str]:
    raw = scope.get("page_types")
    if not isinstance(raw, list) or not raw:
        msg = "scope.page_types must be a non-empty JSON array"
        raise GamePilotManifestError(msg)
    page_types = frozenset(raw)
    if not all(isinstance(value, str) for value in raw) or not page_types <= set(PAGE_TYPES):
        msg = f"scope.page_types must only name {list(PAGE_TYPES)}"
        raise GamePilotManifestError(msg)
    return page_types


def _require_aware_timestamp(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = _require_non_empty_str(mapping, field, context)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        msg = f"{context}.{field} must be an ISO-8601 timestamp"
        raise GamePilotManifestError(msg) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        msg = f"{context}.{field} must carry a timezone"
        raise GamePilotManifestError(msg)
    return value


def _require_mapping(mapping: Mapping[str, Any], field: str, context: str) -> Mapping[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, Mapping):
        msg = f"{context}.{field} must be a JSON object"
        raise GamePilotManifestError(msg)
    return value


def _require_non_empty_str(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        msg = f"{context}.{field} must be a non-empty string"
        raise GamePilotManifestError(msg)
    return value.strip()


def _require_int(mapping: Mapping[str, Any], field: str, context: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{context}.{field} must be an integer"
        raise GamePilotManifestError(msg)
    return value


__all__ = [
    "BASE_URL",
    "GAME_ID_RE",
    "GAME_PAGE_TYPES",
    "GamePilotManifest",
    "GamePilotManifestEntry",
    "GamePilotManifestError",
    "MAX_PILOT_URLS",
    "MONTHS",
    "PAGE_TYPES",
    "PAGE_TYPE_BOX_SCORE",
    "PAGE_TYPE_LEAGUE_SCHEDULE",
    "PAGE_TYPE_PLAY_BY_PLAY",
    "box_score_url",
    "league_schedule_url",
    "load_game_pilot_manifest",
    "parse_game_id",
    "play_by_play_url",
    "validate_game_pilot_manifest",
]
