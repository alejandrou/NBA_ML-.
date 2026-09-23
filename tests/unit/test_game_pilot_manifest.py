from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from nba_data.scraping.game_pilot_manifest import (
    GamePilotManifestError,
    box_score_url,
    league_schedule_url,
    load_game_pilot_manifest,
    parse_game_id,
    play_by_play_url,
    validate_game_pilot_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULE_URL = "https://www.basketball-reference.com/leagues/NBA_2024_games.html"
MONTH_URL = "https://www.basketball-reference.com/leagues/NBA_2020_games-october-2020.html"
BOX_URL = "https://www.basketball-reference.com/boxscores/202310240DEN.html"
PBP_URL = "https://www.basketball-reference.com/boxscores/pbp/202310240DEN.html"


def _raw_manifest() -> dict[str, Any]:
    return {
        "manifest_id": "f8-001-test",
        "status": "approved",
        "approved_by_owner": True,
        "approved_at": "2026-09-23T12:00:00Z",
        "approval_basis": "Test fixture approval.",
        "scope": {
            "page_types": ["league_schedule", "box_score", "play_by_play"],
            "max_urls": 4,
        },
        "acquisition_policy": {
            "cache_first": True,
            "sequential": True,
            "stop_on_first_failure": True,
            "requests_per_minute": 10,
            "max_requests_per_minute": 20,
            "write_target": "HtmlCache .html.gz",
        },
        "entries": [
            {
                "page_type": "league_schedule",
                "url": SCHEDULE_URL,
                "season_end_year": 2024,
                "month": None,
                "reason": "Season index page.",
            },
            {
                "page_type": "league_schedule",
                "url": MONTH_URL,
                "season_end_year": 2020,
                "month": "october-2020",
                "reason": "The bubble's second October.",
            },
            {
                "page_type": "box_score",
                "url": BOX_URL,
                "season_end_year": 2024,
                "game_id": "202310240DEN",
                "reason": "Opening night.",
            },
            {
                "page_type": "play_by_play",
                "url": PBP_URL,
                "season_end_year": 2024,
                "game_id": "202310240DEN",
                "reason": "Opening night.",
            },
        ],
    }


def _with(path: str, value: object) -> dict[str, Any]:
    """Return a valid manifest with one dotted path replaced, or deleted for `...`."""

    raw = copy.deepcopy(_raw_manifest())
    target: Any = raw
    keys = path.split(".")
    for key in keys[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    last = keys[-1]
    if isinstance(target, list):
        target[int(last)] = value
    elif value is ...:
        del target[last]
    else:
        target[last] = value
    return raw


@pytest.mark.unit
def test_a_valid_manifest_loads_every_entry_in_order() -> None:
    manifest = validate_game_pilot_manifest(_raw_manifest())

    assert manifest.manifest_id == "f8-001-test"
    assert manifest.requests_per_minute == 10
    assert [entry.page_type for entry in manifest.entries] == [
        "league_schedule",
        "league_schedule",
        "box_score",
        "play_by_play",
    ]
    assert manifest.entries[0].month is None
    assert manifest.entries[1].month == "october-2020"
    assert manifest.game_ids == ("202310240DEN",)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("status", "draft", "status must be 'approved'"),
        ("approved_by_owner", False, "approved_by_owner must be true"),
        ("approved_by_owner", "true", "approved_by_owner must be true"),
        ("approved_by_owner", ..., "approved_by_owner must be true"),
        ("approved_at", ..., "approved_at must be a non-empty string"),
        ("approved_at", "yesterday", "ISO-8601"),
        ("approved_at", "2026-09-23T12:00:00", "must carry a timezone"),
        ("approval_basis", " ", "approval_basis must be a non-empty string"),
        ("scope.page_types", [], "page_types must be a non-empty JSON array"),
        ("scope.page_types", ["team_season"], "page_types must only name"),
        ("scope.max_urls", 0, "max_urls must be between 1 and 100"),
        ("scope.max_urls", 101, "max_urls must be between 1 and 100"),
        ("acquisition_policy.cache_first", False, "cache_first must be true"),
        ("acquisition_policy.sequential", False, "sequential must be true"),
        ("acquisition_policy.stop_on_first_failure", ..., "stop_on_first_failure must be true"),
        ("acquisition_policy.requests_per_minute", 0, "between 1 and 10"),
        ("acquisition_policy.requests_per_minute", 11, "between 1 and 10"),
        ("acquisition_policy.requests_per_minute", True, "must be an integer"),
        ("acquisition_policy.max_requests_per_minute", 9, "max_requests_per_minute must be >="),
        ("acquisition_policy.max_requests_per_minute", 21, "max_requests_per_minute must be >="),
        ("acquisition_policy.write_target", "postgres", "write_target must be"),
        ("entries", [], "entries must be a non-empty JSON array"),
        ("entries", {}, "entries must be a non-empty JSON array"),
        ("entries.0", "https://example.com", "entries[0] must be a JSON object"),
    ],
)
def test_manifest_level_rejections(path: str, value: object, message: str) -> None:
    with pytest.raises(GamePilotManifestError, match=message.replace("[", r"\[")):
        validate_game_pilot_manifest(_with(path, value))


@pytest.mark.unit
def test_entries_beyond_max_urls_are_rejected() -> None:
    with pytest.raises(GamePilotManifestError, match="exceeds scope.max_urls"):
        validate_game_pilot_manifest(_with("scope.max_urls", 3))


@pytest.mark.unit
def test_a_page_type_outside_the_scope_is_rejected() -> None:
    raw = _with("scope.page_types", ["league_schedule", "box_score"])

    with pytest.raises(GamePilotManifestError, match=r"entries\[3\].*outside scope.page_types"):
        validate_game_pilot_manifest(raw)


@pytest.mark.unit
def test_a_duplicate_url_is_rejected() -> None:
    raw = _with("entries.3.url", BOX_URL)
    raw["entries"][3]["page_type"] = "box_score"

    with pytest.raises(GamePilotManifestError, match="duplicates an earlier manifest entry"):
        validate_game_pilot_manifest(raw)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("index", "field", "value", "message"),
    [
        (2, "page_type", "team_season", "page_type must be one of"),
        (2, "reason", "", "reason must be a non-empty string"),
        (2, "season_end_year", "2024", "season_end_year must be an integer"),
        (2, "url", "http://www.basketball-reference.com/boxscores/202310240DEN.html", "explicit"),
        (2, "url", "https://basketball-reference.com/boxscores/202310240DEN.html", "explicit"),
        (2, "url", "https://www.example.com/boxscores/202310240DEN.html", "explicit"),
        (2, "url", BOX_URL + "?x=1", "explicit"),
        (2, "url", BOX_URL + "#line_score", "explicit"),
        (2, "url", PBP_URL, "box_score URL"),
        (3, "url", BOX_URL.replace("DEN", "den"), "play_by_play URL"),
        (2, "game_id", "202310240LAL", "game_id must match"),
        (2, "game_id", ..., "game_id must be a non-empty string"),
        (
            0,
            "url",
            "https://www.basketball-reference.com/leagues/NBA_2024.html",
            "league schedule URL",
        ),
        (0, "season_end_year", 2023, "season_end_year must match the year"),
        (0, "month", "october", "month must match the month in the URL"),
        (1, "month", None, "month must match the month in the URL"),
        (
            1,
            "url",
            "https://www.basketball-reference.com/leagues/NBA_2020_games-smarch.html",
            "unknown month",
        ),
    ],
)
def test_entry_level_rejections(index: int, field: str, value: object, message: str) -> None:
    with pytest.raises(GamePilotManifestError, match=message):
        validate_game_pilot_manifest(_with(f"entries.{index}.{field}", value))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("game_id", "season_end_year", "message"),
    [
        ("202302300DEN", 2023, "real date"),
        ("202310240TOT", 2024, "marker, not a team"),
        ("202307150DEN", 2024, "outside the 2024 season window"),
        ("202311010DEN", 2023, "outside the 2023 season window"),
    ],
)
def test_game_ids_must_encode_a_real_in_season_date_and_a_real_team(
    game_id: str,
    season_end_year: int,
    message: str,
) -> None:
    raw = _raw_manifest()
    raw["entries"][2].update(
        url=box_score_url(game_id),
        game_id=game_id,
        season_end_year=season_end_year,
    )

    with pytest.raises(GamePilotManifestError, match=message):
        validate_game_pilot_manifest(raw)


@pytest.mark.unit
def test_the_2020_bubble_finals_fit_the_2020_season_window() -> None:
    raw = _raw_manifest()
    raw["entries"][2].update(
        url=box_score_url("202010110LAL"),
        game_id="202010110LAL",
        season_end_year=2020,
    )

    manifest = validate_game_pilot_manifest(raw)

    assert manifest.game_ids == ("202010110LAL", "202310240DEN")


@pytest.mark.unit
def test_url_builders_produce_urls_the_contract_accepts() -> None:
    assert box_score_url("202310240DEN") == BOX_URL
    assert play_by_play_url("202310240DEN") == PBP_URL
    assert league_schedule_url(2024) == SCHEDULE_URL
    assert league_schedule_url(2020, "october-2020") == MONTH_URL
    assert parse_game_id("202310240DEN") == (date(2023, 10, 24), "DEN")


@pytest.mark.unit
@pytest.mark.parametrize("game_id", ["20231024DEN", "202310241DEN", "202310240DE", "x02310240DEN"])
def test_parse_game_id_rejects_malformed_ids(game_id: str) -> None:
    with pytest.raises(GamePilotManifestError, match="Unsupported"):
        parse_game_id(game_id)


@pytest.mark.unit
def test_load_reports_invalid_json_non_objects_and_missing_files(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")

    with pytest.raises(GamePilotManifestError, match="JSON is invalid"):
        load_game_pilot_manifest(broken)
    with pytest.raises(GamePilotManifestError, match="must be a JSON object"):
        load_game_pilot_manifest(array)
    with pytest.raises(GamePilotManifestError, match="cannot be read"):
        load_game_pilot_manifest(tmp_path / "missing.json")


@pytest.mark.unit
def test_load_reads_a_manifest_file(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_raw_manifest()), encoding="utf-8")

    assert load_game_pilot_manifest(path).manifest_id == "f8-001-test"


@pytest.mark.unit
def test_every_committed_f8_001_manifest_satisfies_the_contract() -> None:
    paths = sorted((REPO_ROOT / "tasks" / "manifests").glob("F8-001-*.json"))

    for path in paths:
        manifest = load_game_pilot_manifest(path)
        assert manifest.manifest_id == path.stem
