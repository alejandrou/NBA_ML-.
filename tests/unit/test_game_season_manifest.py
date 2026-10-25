from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from nba_data.scraping.game_pilot_manifest import MAX_PILOT_URLS
from nba_data.scraping.game_season_manifest import (
    MAX_SEASON_URLS,
    GameSeasonManifestError,
    load_game_season_manifest,
    validate_game_season_manifest,
)

BASE = "https://www.basketball-reference.com"


def _box(game_id: str, season_end_year: int = 2024) -> dict[str, object]:
    return {
        "page_type": "box_score",
        "url": f"{BASE}/boxscores/{game_id}.html",
        "season_end_year": season_end_year,
        "game_id": game_id,
        "reason": "Regular-season game.",
    }


def _schedule(month: str | None, season_end_year: int = 2024) -> dict[str, object]:
    suffix = f"-{month}" if month else ""
    return {
        "page_type": "league_schedule",
        "url": f"{BASE}/leagues/NBA_{season_end_year}_games{suffix}.html",
        "season_end_year": season_end_year,
        "month": month,
        "reason": "Schedule page.",
    }


def _raw(
    *,
    page_type: str = "box_score",
    entries: list[dict[str, object]] | None = None,
    season_end_year: int = 2024,
) -> dict[str, Any]:
    entries = entries if entries is not None else [_box("202310240DEN"), _box("202404140IND")]
    return {
        "manifest_id": "F8-004-test",
        "status": "approved",
        "approved_by_owner": True,
        "approved_at": "2026-10-25T12:00:00Z",
        "approval_basis": "Test fixture approval.",
        "scope": {
            "season_end_year": season_end_year,
            "page_type": page_type,
            "max_urls": max(len(entries), 1),
        },
        "acquisition_policy": {
            "cache_first": True,
            "sequential": True,
            "stop_on_first_failure": True,
            "requests_per_minute": 10,
            "max_requests_per_minute": 20,
            "write_target": "HtmlCache .html.gz",
        },
        "entries": entries,
    }


def _draft(**kwargs: Any) -> dict[str, Any]:
    raw = _raw(**kwargs)
    raw.update(status="draft", approved_by_owner=False, approved_at=None, approval_basis=None)
    return raw


@pytest.mark.unit
def test_an_approved_box_score_manifest_loads(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_raw()), encoding="utf-8")

    manifest = load_game_season_manifest(path, require_approval=True)

    assert manifest.approved is True
    assert manifest.season_end_year == 2024
    assert manifest.page_type == "box_score"
    assert [entry.game_id for entry in manifest.entries] == ["202310240DEN", "202404140IND"]


@pytest.mark.unit
def test_a_schedule_manifest_takes_the_season_page_and_both_2019_20_octobers() -> None:
    entries = [
        _schedule(None, 2020),
        _schedule("october-2019", 2020),
        _schedule("october-2020", 2020),
    ]

    manifest = validate_game_season_manifest(
        _raw(page_type="league_schedule", entries=entries, season_end_year=2020),
        require_approval=True,
    )

    assert [entry.month for entry in manifest.entries] == [None, "october-2019", "october-2020"]


@pytest.mark.unit
def test_a_draft_loads_only_when_approval_is_not_required() -> None:
    draft = validate_game_season_manifest(_draft(), require_approval=False)
    assert draft.approved is False
    assert draft.approved_at is None

    with pytest.raises(GameSeasonManifestError, match="status must be 'approved'"):
        validate_game_season_manifest(_draft(), require_approval=True)


@pytest.mark.unit
def test_a_ceiling_of_1400_urls_per_season_while_the_pilot_keeps_100() -> None:
    assert MAX_SEASON_URLS == 1400
    assert MAX_PILOT_URLS == 100
    raw = _raw()
    raw["scope"]["max_urls"] = 1401

    with pytest.raises(GameSeasonManifestError, match="between 1 and 1400 for one season"):
        validate_game_season_manifest(raw, require_approval=True)


def _set(path: tuple[str, ...], value: object) -> Callable[[dict[str, Any]], None]:
    def mutate(raw: dict[str, Any]) -> None:
        target = raw
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_set(("status",), "pending"), "status must be 'approved'"),
        (_set(("approved_by_owner",), "yes"), "approved_by_owner must be true"),
        (_set(("approved_at",), "2026-10-25T12:00:00"), "approved_at must carry a timezone"),
        (_set(("approval_basis",), " "), "approval_basis must be a non-empty string"),
        (_set(("scope", "season_end_year"), 2027), "must be a Stage 2 season"),
        (_set(("scope", "page_type"), "play_by_play"), "scope.page_type must be one of"),
        (_set(("scope", "max_urls"), 1), "entries exceeds scope.max_urls"),
        (_set(("acquisition_policy", "sequential"), False), "sequential must be true"),
        (_set(("acquisition_policy", "requests_per_minute"), 11), "between 1 and 10"),
        (_set(("acquisition_policy", "write_target"), "disk"), "write_target must be"),
        (_set(("entries",), []), "entries must be a non-empty JSON array"),
    ],
)
def test_an_unsafe_manifest_is_refused(
    mutate: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    raw = _raw()
    mutate(raw)

    with pytest.raises(GameSeasonManifestError, match=message):
        validate_game_season_manifest(raw, require_approval=True)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "approved_by_owner", "message"),
    [
        ("draft", True, "draft manifest must carry approved_by_owner: false"),
        ("pending", False, "status must be 'draft' or 'approved'"),
    ],
)
def test_a_draft_never_claims_an_approval(
    status: str,
    approved_by_owner: bool,
    message: str,
) -> None:
    raw = _draft()
    raw.update(status=status, approved_by_owner=approved_by_owner)

    with pytest.raises(GameSeasonManifestError, match=message):
        validate_game_season_manifest(raw, require_approval=False)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (_box("202310240DEN", season_end_year=2025), "must be the manifest's season 2024"),
        (_schedule("may"), "page_type must be the manifest's page type"),
        (
            {**_box("202310240DEN"), "url": f"{BASE}/boxscores/pbp/202310240DEN.html"},
            "box_score URL of its game_id",
        ),
        (
            {**_box("202310240DEN"), "url": f"{BASE}/boxscores/202310240DEN.html?x=1"},
            "explicit https://www.basketball-reference.com URL",
        ),
        (_box("202210240DEN"), "outside the 2024 season window"),
        (_box("202310240TOT"), "marker, not a team"),
        (_box("202302300DEN"), "does not start with a real date"),
    ],
)
def test_an_unsafe_box_score_entry_is_refused(entry: dict[str, object], message: str) -> None:
    with pytest.raises(GameSeasonManifestError, match=message):
        validate_game_season_manifest(_raw(entries=[entry]), require_approval=True)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (_schedule("may", season_end_year=2025), "must be the manifest's season 2024"),
        ({**_schedule("may"), "url": f"{BASE}/leagues/NBA_2025_games-may.html"}, "2024 Basketball"),
        ({**_schedule("may"), "url": f"{BASE}/leagues/NBA_2024_games-maybe.html"}, "unknown month"),
        ({**_schedule("may"), "url": f"{BASE}/leagues/NBA_2024_gamesmay.html"}, "unknown month"),
        ({**_schedule("may"), "month": "june"}, "month must match the month in the URL"),
    ],
)
def test_an_unsafe_schedule_entry_is_refused(entry: dict[str, object], message: str) -> None:
    raw = _raw(page_type="league_schedule", entries=[entry])

    with pytest.raises(GameSeasonManifestError, match=message):
        validate_game_season_manifest(raw, require_approval=True)


@pytest.mark.unit
def test_a_duplicate_url_is_refused() -> None:
    raw = _raw(entries=[_box("202310240DEN"), _box("202310240DEN")])

    with pytest.raises(GameSeasonManifestError, match="duplicates an earlier manifest entry"):
        validate_game_season_manifest(raw, require_approval=True)


@pytest.mark.unit
def test_an_unreadable_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(GameSeasonManifestError, match="cannot be read"):
        load_game_season_manifest(tmp_path / "absent.json", require_approval=False)
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(GameSeasonManifestError, match="JSON is invalid"):
        load_game_season_manifest(path, require_approval=False)
