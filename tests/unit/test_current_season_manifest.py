from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from nba_data.scraping.current_season_manifest import (
    CurrentSeasonManifestError,
    build_draft_current_season_manifest,
    load_current_season_manifest,
    validate_current_season_manifest,
    write_draft_current_season_manifest,
)

DRAFTED_AT = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def _approved() -> dict[str, Any]:
    manifest = copy.deepcopy(build_draft_current_season_manifest(DRAFTED_AT))
    manifest.update(
        status="approved",
        approved_by_owner=True,
        approved_at="2026-11-07T12:00:00+00:00",
        approval_basis="Owner approved the 2027 refresh rule.",
    )
    return manifest


@pytest.mark.unit
def test_the_draft_carries_the_decided_ceilings_and_loads_only_as_a_draft() -> None:
    draft = build_draft_current_season_manifest(DRAFTED_AT)

    manifest = validate_current_season_manifest(draft, require_approval=False)

    assert manifest.status == "draft"
    assert not manifest.approved
    assert manifest.season_end_year == 2027
    assert (manifest.max_schedule_pages, manifest.max_team_pages, manifest.max_box_scores) == (
        20,
        30,
        150,
    )
    assert manifest.requests_per_minute == 10
    with pytest.raises(CurrentSeasonManifestError, match="status must be 'approved'"):
        validate_current_season_manifest(draft, require_approval=True)


@pytest.mark.unit
def test_an_approved_manifest_loads_for_acquisition() -> None:
    manifest = validate_current_season_manifest(_approved(), require_approval=True)

    assert manifest.approved
    assert manifest.approval_basis == "Owner approved the 2027 refresh rule."


@pytest.mark.unit
def test_a_draft_claiming_approval_is_refused() -> None:
    draft = build_draft_current_season_manifest(DRAFTED_AT)
    draft["approved_by_owner"] = True

    with pytest.raises(CurrentSeasonManifestError, match="approved_by_owner: false"):
        validate_current_season_manifest(draft, require_approval=False)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda m: m["scope"].update(season_end_year=2026), "current season 2027"),
        (lambda m: m["scope"].update(season_end_year=2028), "current season 2027"),
        (lambda m: m["scope"].update(max_schedule_pages_per_run=21), "between 1 and 20"),
        (lambda m: m["scope"].update(max_team_pages_per_run=31), "between 1 and 30"),
        (lambda m: m["scope"].update(max_box_scores_per_run=151), "between 1 and 150"),
        (lambda m: m["scope"].update(max_box_scores_per_run=0), "between 1 and 150"),
        (lambda m: m["acquisition_policy"].update(requests_per_minute=11), "between 1 and 10"),
        (lambda m: m["acquisition_policy"].update(max_requests_per_minute=21), "<= 20"),
        (lambda m: m["acquisition_policy"].update(sequential=False), "sequential must be true"),
        (
            lambda m: m["acquisition_policy"].update(snapshot_write_target="HtmlCache .html.gz"),
            "snapshot_write_target",
        ),
        (lambda m: m.update(kind="season"), "kind must be 'current_season_refresh'"),
        (lambda m: m.update(entries=[]), "lists no entries"),
        (lambda m: m.update(approved_at="2026-11-07T12:00:00"), "must carry a timezone"),
        (lambda m: m.update(approved_by_owner=False), "approved_by_owner must be true"),
    ],
)
def test_unsafe_manifests_are_refused(change: Any, message: str) -> None:
    manifest = _approved()
    change(manifest)

    with pytest.raises(CurrentSeasonManifestError, match=message):
        validate_current_season_manifest(manifest, require_approval=True)


@pytest.mark.unit
def test_the_draft_writer_never_replaces_a_file(tmp_path: Path) -> None:
    path = tmp_path / "reports" / "draft.json"

    write_draft_current_season_manifest(DRAFTED_AT, path)
    loaded = load_current_season_manifest(path, require_approval=False)

    assert loaded.manifest_id == "F8-013-NBA_2027-current-season-refresh-draft-20261107"
    with pytest.raises(CurrentSeasonManifestError, match="already exists"):
        write_draft_current_season_manifest(DRAFTED_AT, path)


@pytest.mark.unit
def test_unreadable_manifests_are_refused(tmp_path: Path) -> None:
    with pytest.raises(CurrentSeasonManifestError, match="cannot be read"):
        load_current_season_manifest(tmp_path / "absent.json", require_approval=False)
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(CurrentSeasonManifestError, match="JSON is invalid"):
        load_current_season_manifest(invalid, require_approval=False)
    array = tmp_path / "array.json"
    array.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(CurrentSeasonManifestError, match="JSON object"):
        load_current_season_manifest(array, require_approval=False)
