"""The standing manifest of the current-season refresh (F8-013).

Unlike the Stage 2 manifests (`game_season_manifest.py`), this kind lists no
URLs: an in-progress season's box scores depend on the schedule fetched in the
same run. The owner approves, once per season, a fixed rule with ceilings
instead (`docs/validation/CURRENT_SEASON_REFRESH.md`):

- the season schedule page, every run;
- the month pages the latest season snapshot links, as `current_season_planning`
  selects them for `--as-of`;
- the season's 30 team pages, only while they have no snapshot;
- the box scores of games with a score in the latest month snapshots and no
  archived box score.

Ceilings per run: 20 schedule pages, 30 team pages, 150 box scores, at most 10
requests/minute. A larger ceiling is refused. Approving the manifest never
authorizes a run: each run still needs `--owner-approved`,
`--execute-approved-manifest` and the owner's direct instruction (AGENTS.md).

The approval and policy checks are copied from F8-004's contract, which is left
unchanged (AGENTS.md: copy guard code, do not generalize it).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from nba_data.scraping.snapshot_cache import CURRENT_SEASON_END_YEAR

MANIFEST_KIND = "current_season_refresh"

MAX_SCHEDULE_PAGES_PER_RUN = 20
MAX_TEAM_PAGES_PER_RUN = 30
MAX_BOX_SCORES_PER_RUN = 150
MAX_DEFAULT_REQUESTS_PER_MINUTE = 10
MAX_ABSOLUTE_REQUESTS_PER_MINUTE = 20

SNAPSHOT_WRITE_TARGET = "SnapshotCache .html.gz"
ARCHIVE_WRITE_TARGET = "HtmlCache .html.gz"

STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"

DEFAULT_DRAFT_PATH = Path(
    f"reports/current-season/NBA_{CURRENT_SEASON_END_YEAR}_current-season-refresh.draft.json"
)


class CurrentSeasonManifestError(ValueError):
    """Raised when a current-season manifest is not safe to plan or execute."""


@dataclass(frozen=True)
class CurrentSeasonManifest:
    manifest_id: str
    status: str
    approved_at: str | None
    approval_basis: str | None
    season_end_year: int
    max_schedule_pages: int
    max_team_pages: int
    max_box_scores: int
    requests_per_minute: int
    max_requests_per_minute: int

    @property
    def approved(self) -> bool:
        return self.status == STATUS_APPROVED


def load_current_season_manifest(
    path: str | Path,
    *,
    require_approval: bool,
) -> CurrentSeasonManifest:
    """Load the manifest; a draft is refused when approval is required."""

    manifest_path = Path(path)
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"Manifest cannot be read: {manifest_path}"
        raise CurrentSeasonManifestError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Manifest JSON is invalid: {exc.msg}"
        raise CurrentSeasonManifestError(msg) from exc

    if not isinstance(raw_manifest, Mapping):
        msg = "manifest must be a JSON object"
        raise CurrentSeasonManifestError(msg)
    return validate_current_season_manifest(raw_manifest, require_approval=require_approval)


def validate_current_season_manifest(
    raw_manifest: Mapping[str, Any],
    *,
    require_approval: bool,
) -> CurrentSeasonManifest:
    manifest_id = _require_non_empty_str(raw_manifest, "manifest_id", "manifest")
    if raw_manifest.get("kind") != MANIFEST_KIND:
        msg = f"manifest.kind must be {MANIFEST_KIND!r}"
        raise CurrentSeasonManifestError(msg)
    if "entries" in raw_manifest:
        msg = "a current_season_refresh manifest approves a rule and lists no entries"
        raise CurrentSeasonManifestError(msg)
    status, approved_at, approval_basis = _validate_approval(
        raw_manifest, require_approval=require_approval
    )

    scope = _require_mapping(raw_manifest, "scope", "manifest")
    season_end_year = _require_int(scope, "season_end_year", "scope")
    if season_end_year != CURRENT_SEASON_END_YEAR:
        msg = (
            f"scope.season_end_year must be the current season {CURRENT_SEASON_END_YEAR}, "
            f"not {season_end_year}"
        )
        raise CurrentSeasonManifestError(msg)
    max_schedule_pages = _require_ceiling(
        scope, "max_schedule_pages_per_run", MAX_SCHEDULE_PAGES_PER_RUN
    )
    max_team_pages = _require_ceiling(scope, "max_team_pages_per_run", MAX_TEAM_PAGES_PER_RUN)
    max_box_scores = _require_ceiling(scope, "max_box_scores_per_run", MAX_BOX_SCORES_PER_RUN)

    policy = _require_mapping(raw_manifest, "acquisition_policy", "manifest")
    for flag in ("cache_first", "sequential", "stop_on_first_failure"):
        if policy.get(flag) is not True:
            msg = f"acquisition_policy.{flag} must be true"
            raise CurrentSeasonManifestError(msg)
    requests_per_minute = _require_int(policy, "requests_per_minute", "acquisition_policy")
    if requests_per_minute < 1 or requests_per_minute > MAX_DEFAULT_REQUESTS_PER_MINUTE:
        msg = (
            "acquisition_policy.requests_per_minute must be between 1 and "
            f"{MAX_DEFAULT_REQUESTS_PER_MINUTE}"
        )
        raise CurrentSeasonManifestError(msg)
    max_requests_per_minute = _require_int(policy, "max_requests_per_minute", "acquisition_policy")
    if not requests_per_minute <= max_requests_per_minute <= MAX_ABSOLUTE_REQUESTS_PER_MINUTE:
        msg = (
            "acquisition_policy.max_requests_per_minute must be >= requests_per_minute "
            f"and <= {MAX_ABSOLUTE_REQUESTS_PER_MINUTE}"
        )
        raise CurrentSeasonManifestError(msg)
    for field, expected in (
        ("snapshot_write_target", SNAPSHOT_WRITE_TARGET),
        ("archive_write_target", ARCHIVE_WRITE_TARGET),
    ):
        if _require_non_empty_str(policy, field, "acquisition_policy") != expected:
            msg = f"acquisition_policy.{field} must be {expected!r}"
            raise CurrentSeasonManifestError(msg)

    return CurrentSeasonManifest(
        manifest_id=manifest_id,
        status=status,
        approved_at=approved_at,
        approval_basis=approval_basis,
        season_end_year=season_end_year,
        max_schedule_pages=max_schedule_pages,
        max_team_pages=max_team_pages,
        max_box_scores=max_box_scores,
        requests_per_minute=requests_per_minute,
        max_requests_per_minute=max_requests_per_minute,
    )


def build_draft_current_season_manifest(drafted_at: datetime) -> dict[str, object]:
    """The draft the owner reviews and approves: the decided rule at its ceilings."""

    manifest: dict[str, object] = {
        "manifest_id": (
            f"F8-013-NBA_{CURRENT_SEASON_END_YEAR}-current-season-refresh-draft-{drafted_at:%Y%m%d}"
        ),
        "kind": MANIFEST_KIND,
        "status": STATUS_DRAFT,
        "approved_by_owner": False,
        "approved_at": None,
        "approval_basis": None,
        "scope": {
            "season_end_year": CURRENT_SEASON_END_YEAR,
            "max_schedule_pages_per_run": MAX_SCHEDULE_PAGES_PER_RUN,
            "max_team_pages_per_run": MAX_TEAM_PAGES_PER_RUN,
            "max_box_scores_per_run": MAX_BOX_SCORES_PER_RUN,
        },
        "rule": [
            "The season schedule page, every run.",
            "Month pages the latest season snapshot links: the month of --as-of, the next "
            "one, any earlier month whose latest snapshot shows a game dated before --as-of "
            "without a score, and any month never fetched.",
            "The season's 30 team pages, only while they have no snapshot.",
            "Box scores of games with a score in the latest month snapshots and no archived "
            "box score.",
        ],
        "acquisition_policy": {
            "cache_first": True,
            "sequential": True,
            "stop_on_first_failure": True,
            "requests_per_minute": MAX_DEFAULT_REQUESTS_PER_MINUTE,
            "max_requests_per_minute": MAX_ABSOLUTE_REQUESTS_PER_MINUTE,
            "snapshot_write_target": SNAPSHOT_WRITE_TARGET,
            "archive_write_target": ARCHIVE_WRITE_TARGET,
        },
        "drafted_at": drafted_at.isoformat(),
    }
    # The draft must load as a draft: never write what the contract refuses.
    validate_current_season_manifest(manifest, require_approval=False)
    return manifest


def write_draft_current_season_manifest(
    drafted_at: datetime,
    path: Path = DEFAULT_DRAFT_PATH,
) -> Path:
    """Write the draft, refusing to replace any file already at `path`."""

    manifest = build_draft_current_season_manifest(drafted_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        msg = f"{path} already exists; move it away or pass another path"
        raise CurrentSeasonManifestError(msg) from exc
    return path


def _validate_approval(
    raw_manifest: Mapping[str, Any],
    *,
    require_approval: bool,
) -> tuple[str, str | None, str | None]:
    status = _require_non_empty_str(raw_manifest, "status", "manifest")
    approved_by_owner = raw_manifest.get("approved_by_owner")
    if not require_approval and status not in (STATUS_DRAFT, STATUS_APPROVED):
        msg = "manifest.status must be 'draft' or 'approved'"
        raise CurrentSeasonManifestError(msg)

    if require_approval or status == STATUS_APPROVED:
        if status != STATUS_APPROVED:
            msg = "manifest.status must be 'approved'"
            raise CurrentSeasonManifestError(msg)
        if approved_by_owner is not True:
            msg = "manifest.approved_by_owner must be true"
            raise CurrentSeasonManifestError(msg)
        approved_at = _require_aware_timestamp(raw_manifest, "approved_at", "manifest")
        approval_basis = _require_non_empty_str(raw_manifest, "approval_basis", "manifest")
        return status, approved_at, approval_basis

    # A draft never claims an approval it does not have.
    if approved_by_owner is not False:
        msg = "a draft manifest must carry approved_by_owner: false"
        raise CurrentSeasonManifestError(msg)
    return status, None, None


def _require_ceiling(scope: Mapping[str, Any], field: str, maximum: int) -> int:
    value = _require_int(scope, field, "scope")
    if value < 1 or value > maximum:
        msg = f"scope.{field} must be between 1 and {maximum}"
        raise CurrentSeasonManifestError(msg)
    return value


def _require_aware_timestamp(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = _require_non_empty_str(mapping, field, context)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        msg = f"{context}.{field} must be an ISO-8601 timestamp"
        raise CurrentSeasonManifestError(msg) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        msg = f"{context}.{field} must carry a timezone"
        raise CurrentSeasonManifestError(msg)
    return value


def _require_mapping(mapping: Mapping[str, Any], field: str, context: str) -> Mapping[str, Any]:
    value = mapping.get(field)
    if not isinstance(value, Mapping):
        msg = f"{context}.{field} must be a JSON object"
        raise CurrentSeasonManifestError(msg)
    return value


def _require_non_empty_str(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        msg = f"{context}.{field} must be a non-empty string"
        raise CurrentSeasonManifestError(msg)
    return value.strip()


def _require_int(mapping: Mapping[str, Any], field: str, context: str) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{context}.{field} must be an integer"
        raise CurrentSeasonManifestError(msg)
    return value


__all__ = [
    "ARCHIVE_WRITE_TARGET",
    "DEFAULT_DRAFT_PATH",
    "MANIFEST_KIND",
    "MAX_ABSOLUTE_REQUESTS_PER_MINUTE",
    "MAX_BOX_SCORES_PER_RUN",
    "MAX_DEFAULT_REQUESTS_PER_MINUTE",
    "MAX_SCHEDULE_PAGES_PER_RUN",
    "MAX_TEAM_PAGES_PER_RUN",
    "SNAPSHOT_WRITE_TARGET",
    "STATUS_APPROVED",
    "STATUS_DRAFT",
    "CurrentSeasonManifest",
    "CurrentSeasonManifestError",
    "build_draft_current_season_manifest",
    "load_current_season_manifest",
    "validate_current_season_manifest",
    "write_draft_current_season_manifest",
]
