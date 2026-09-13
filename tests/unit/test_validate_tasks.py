"""Focused tests for the task lifecycle validator."""

from pathlib import Path

import pytest
from scripts import validate_tasks as validator
from scripts.validate_tasks import (
    NEUTRAL_AREAS,
    STAGES,
    Worktree,
    check_active_dependencies_done,
    check_areas_match_track,
    check_backlog_decisions_resolved,
    check_cross_track_log,
    check_dependencies_resolve,
    check_filename_matches_id,
    check_forbidden_fields,
    check_id_family_matches_track,
    check_id_in_one_stage,
    check_lifecycle_folders,
    check_parked_cards,
    check_required_fields,
    check_review_cross_track_impact,
    check_track_field,
    check_track_slots,
    check_unique_ids_within_stage,
    check_worktree_bindings,
    load_cards,
    main,
    parse_cross_track_log,
    parse_frontmatter,
    read_track_binding,
    section_body,
    validate_tasks,
    validate_worktrees,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FRONTMATTER = """---
id: {card_id}
title: {title}
track: {track}
areas:
{areas}
priority: {priority}
depends_on: {depends_on}
read: []
validation: []
critical_actions: []
---
"""

EMPTY_LOG = "# Cross-track handoffs\n\nPurpose.\n\n## Open\n\n## Log\n"


def _tasks_root(tmp_path: Path, name: str = "tasks") -> Path:
    root = tmp_path / name
    for stage in STAGES:
        (root / stage).mkdir(parents=True)
    (root / "CROSS_TRACK.md").write_text(EMPTY_LOG, encoding="utf-8")
    return root


def _frontmatter(
    card_id: str,
    *,
    title: str = "A card",
    track: str = "shared",
    areas: tuple[str, ...] = ("documentation",),
    depends_on: str = "[]",
    priority: str = "50",
) -> str:
    return FRONTMATTER.format(
        card_id=card_id,
        title=title,
        track=track,
        areas="\n".join(f"  - {area}" for area in areas),
        depends_on=depends_on,
        priority=priority,
    )


def _write_card(
    root: Path,
    stage: str,
    card_id: str,
    *,
    filename: str | None = None,
    depends_on: str = "[]",
    priority: str = "50",
    title: str = "A card",
    track: str = "shared",
    areas: tuple[str, ...] = ("documentation",),
    body: str = "",
    frontmatter: str | None = None,
) -> Path:
    path = root / stage / (filename or f"{card_id}.md")
    text = (
        frontmatter
        if frontmatter is not None
        else _frontmatter(
            card_id,
            title=title,
            track=track,
            areas=areas,
            depends_on=depends_on,
            priority=priority,
        )
    )
    path.write_text(text + body, encoding="utf-8")
    return path


def _cards(root: Path):
    cards, errors = load_cards(root)
    assert errors == []
    return cards


def _write_log(root: Path, *, open_lines: str = "", log_lines: str = "") -> None:
    (root / "CROSS_TRACK.md").write_text(
        f"# Cross-track handoffs\n\n## Open\n\n{open_lines}\n## Log\n\n{log_lines}",
        encoding="utf-8",
    )


def _entries(root: Path):
    entries, errors = parse_cross_track_log((root / "CROSS_TRACK.md").read_text(encoding="utf-8"))
    assert errors == []
    return entries


# --- parser -----------------------------------------------------------------


@pytest.mark.unit
def test_parse_frontmatter_reads_the_three_supported_shapes():
    fields, errors = parse_frontmatter(
        "---\nid: XX-001\nread: []\nareas:\n  - api\n  - testing\n---\nbody\n",
        label="planning/XX-001.md",
    )
    assert errors == []
    assert fields == {"id": "XX-001", "read": [], "areas": ["api", "testing"]}


@pytest.mark.unit
def test_parse_frontmatter_requires_an_opening_fence():
    _, errors = parse_frontmatter("id: XX-001\n", label="planning/XX-001.md")
    assert errors == ["planning/XX-001.md: file must open with a '---' frontmatter fence"]


@pytest.mark.unit
def test_parse_frontmatter_requires_a_closing_fence():
    _, errors = parse_frontmatter("---\nid: XX-001\n", label="planning/XX-001.md")
    assert errors == ["planning/XX-001.md: frontmatter fence is never closed"]


@pytest.mark.unit
def test_parse_frontmatter_reports_unsupported_lines_instead_of_guessing():
    _, errors = parse_frontmatter(
        "---\nid: XX-001\nnested:\n  child:\n    deep: 1\n---\n",
        label="planning/XX-001.md",
    )
    assert any("unsupported frontmatter line" in error for error in errors)


@pytest.mark.unit
def test_parse_frontmatter_reports_a_list_item_without_a_key():
    _, errors = parse_frontmatter("---\n  - orphan\n---\n", label="planning/XX-001.md")
    assert errors == ["planning/XX-001.md:2: list item outside a list key: '  - orphan'"]


@pytest.mark.unit
def test_parse_frontmatter_reports_duplicate_keys():
    _, errors = parse_frontmatter(
        "---\nid: XX-001\nid: XX-002\n---\n", label="planning/XX-001.md"
    )
    assert errors == ["planning/XX-001.md:3: duplicate frontmatter key 'id'"]


@pytest.mark.unit
def test_section_body_matches_level_one_headings_only():
    body = "\n# Goal\nship it\n\n# Review evidence\n\n## Automated validation\n- Command:\n"
    assert section_body(body, "Goal").strip() == "ship it"
    assert section_body(body, "Automated validation") is None
    assert section_body(body, "Absent heading") is None


# --- checks -----------------------------------------------------------------


@pytest.mark.unit
def test_check_lifecycle_folders_reports_every_missing_folder(tmp_path: Path):
    root = _tasks_root(tmp_path)
    assert check_lifecycle_folders(root) == []
    (root / "planning").rmdir()
    assert check_lifecycle_folders(root) == ["tasks/planning/: lifecycle folder is missing"]


@pytest.mark.unit
def test_check_unique_ids_within_stage_reports_one_error_per_duplicate(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001", filename="XX-001.md")
    _write_card(root, "backlog", "XX-001", filename="XX-001-copy.md")
    errors = check_unique_ids_within_stage(_cards(root))
    assert len(errors) == 1
    assert "duplicate card id 'XX-001'" in errors[0]


@pytest.mark.unit
def test_check_required_fields_reports_missing_keys_and_bad_shapes(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "planning", "XX-001")
    assert check_required_fields(_cards(root)) == []
    _write_card(
        root,
        "planning",
        "XX-002",
        frontmatter="---\nid: XX-002\ntitle: T\nareas: api\npriority: high\n---\n",
    )
    errors = "\n".join(check_required_fields(_cards(root)))
    assert "missing required frontmatter key 'depends_on'" in errors
    assert "'areas' must be a list" in errors
    assert "'priority' must be a whole number" in errors


@pytest.mark.unit
def test_check_dependencies_resolve_rejects_unknown_ids(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "done", "XX-001")
    _write_card(root, "backlog", "XX-002", depends_on="\n  - XX-001")
    assert check_dependencies_resolve(_cards(root)) == []
    _write_card(root, "backlog", "XX-003", depends_on="\n  - XX-404")
    errors = check_dependencies_resolve(_cards(root))
    assert errors == [
        "backlog/XX-003.md: depends_on 'XX-404' does not match any card id"
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    [
        "status",
        "phase",
        "mode",
        "owner_approved",
        "requires_owner_approval",
        "approval_scope",
        "skills",
        "allowed_paths",
        "forbidden_paths",
    ],
)
def test_check_forbidden_fields_rejects_every_banned_key(tmp_path: Path, key: str):
    root = _tasks_root(tmp_path)
    _write_card(
        root,
        "backlog",
        "XX-001",
        frontmatter=_frontmatter("XX-001").replace("---\nid:", f"---\n{key}: something\nid:"),
    )
    errors = check_forbidden_fields(_cards(root))
    assert errors == [
        f"backlog/XX-001.md: forbidden frontmatter key {key!r}; the folder is the status"
    ]


@pytest.mark.unit
def test_check_backlog_decisions_resolved_accepts_none_checked_and_absent(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001", body="\n# Human decisions or resources\n\n- None.\n")
    _write_card(
        root,
        "backlog",
        "XX-002",
        body="\n# Human decisions or resources\n\n- [x] Owner picked PostgreSQL.\n",
    )
    _write_card(root, "backlog", "XX-003", body="\n# Goal\n\nNo decisions section at all.\n")
    assert check_backlog_decisions_resolved(_cards(root)) == []


@pytest.mark.unit
def test_check_backlog_decisions_resolved_rejects_an_open_checkbox(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(
        root,
        "backlog",
        "XX-001",
        body="\n# Human decisions or resources\n\n- [ ] Which cache root?\n",
    )
    errors = check_backlog_decisions_resolved(_cards(root))
    assert len(errors) == 1
    assert "unresolved human decision" in errors[0]
    assert "move the card back to tasks/planning/" in errors[0]


@pytest.mark.unit
def test_check_backlog_decisions_resolved_reports_a_wrapped_bullet_once(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(
        root,
        "backlog",
        "XX-001",
        body=(
            "\n# Human decisions or resources\n\n"
            "- [ ] Which cache root did the failing run use, and can you paste\n"
            "      the report it produced? That decides which fix applies.\n"
        ),
    )
    errors = check_backlog_decisions_resolved(_cards(root))
    assert len(errors) == 1
    assert "unresolved human decision" in errors[0]


@pytest.mark.unit
def test_check_backlog_decisions_resolved_ignores_planning_cards(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(
        root,
        "planning",
        "XX-001",
        body="\n# Human decisions or resources\n\n- [ ] Still open, and that is fine.\n",
    )
    assert check_backlog_decisions_resolved(_cards(root)) == []


@pytest.mark.unit
def test_check_active_dependencies_done_requires_dependencies_in_done(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001")
    _write_card(root, "active", "XX-002", depends_on="\n  - XX-001")
    errors = check_active_dependencies_done(_cards(root))
    assert errors == [
        "active/XX-002.md: dependency 'XX-001' is in tasks/backlog/, not in tasks/done/"
    ]


@pytest.mark.unit
def test_check_active_dependencies_done_passes_when_dependency_is_done(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "done", "XX-001")
    _write_card(root, "active", "XX-002", depends_on="\n  - XX-001")
    assert check_active_dependencies_done(_cards(root)) == []


@pytest.mark.unit
def test_check_id_in_one_stage_reports_a_card_left_in_two_folders(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "planning", "XX-001")
    _write_card(root, "backlog", "XX-001")
    errors = check_id_in_one_stage(_cards(root))
    assert len(errors) == 1
    assert "tasks/backlog/, tasks/planning/" in errors[0]


@pytest.mark.unit
def test_check_filename_matches_id_allows_a_slug_but_not_an_unrelated_name(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "planning", "XX-001", filename="XX-001-diagnose-the-thing.md")
    _write_card(root, "backlog", "XX-002", filename="XX-002.md")
    assert check_filename_matches_id(_cards(root)) == []
    _write_card(root, "backlog", "XX-003", filename="unrelated-name.md")
    errors = check_filename_matches_id(_cards(root))
    assert errors == [
        "backlog/unrelated-name.md: filename must be 'XX-003.md' or 'XX-003-<slug>.md'"
    ]


# --- tracks and slots -------------------------------------------------------


@pytest.mark.unit
def test_check_track_slots_allows_one_card_per_track(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "active", "XX-001", track="data")
    _write_card(root, "review", "XX-002", track="app")
    _write_card(root, "backlog", "XX-003", track="data")
    assert check_track_slots(_cards(root)) == []


@pytest.mark.unit
def test_check_track_slots_rejects_two_cards_in_the_same_track(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "active", "XX-001", track="data")
    _write_card(root, "review", "XX-002", track="data")
    _write_card(root, "active", "XX-003", track="app")
    errors = check_track_slots(_cards(root))
    assert len(errors) == 1
    assert "track 'data' may hold one card" in errors[0]
    assert "active/XX-001.md" in errors[0]
    assert "review/XX-002.md" in errors[0]
    assert "XX-003" not in errors[0]


@pytest.mark.unit
@pytest.mark.parametrize("other_track", ["data", "app", "shared"])
def test_check_track_slots_rejects_a_shared_card_next_to_any_other(
    tmp_path: Path, other_track: str
):
    root = _tasks_root(tmp_path)
    _write_card(root, "active", "XX-001", track="shared")
    _write_card(root, "review", "XX-002", track=other_track)
    errors = check_track_slots(_cards(root))
    assert len(errors) == 1
    assert "a shared card must be the only card" in errors[0]


@pytest.mark.unit
def test_check_track_slots_counts_a_missing_or_invalid_track_as_shared(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "active", "XX-001", track="data")
    _write_card(root, "review", "XX-002", track="frontend")
    errors = check_track_slots(_cards(root))
    assert len(errors) == 1
    assert "a shared card must be the only card" in errors[0]
    assert "(frontend)" in errors[0]


@pytest.mark.unit
def test_check_track_field_requires_a_valid_track_outside_done(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "planning", "XX-001", track="data")
    _write_card(root, "backlog", "XX-002", track="frontend")
    _write_card(
        root,
        "active",
        "XX-003",
        frontmatter=_frontmatter("XX-003").replace("track: shared\n", ""),
    )
    _write_card(
        root,
        "done",
        "XX-004",
        frontmatter=_frontmatter("XX-004").replace("track: shared\n", ""),
    )
    errors = check_track_field(_cards(root))
    assert errors == [
        "backlog/XX-002.md: 'track' must be one of data, app, shared; got 'frontend'",
        "active/XX-003.md: missing required frontmatter key 'track'",
    ]


@pytest.mark.unit
def test_check_areas_match_track_rejects_the_other_tracks_areas(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001", track="app", areas=("api", "database-schema"))
    _write_card(root, "review", "XX-002", track="data", areas=("scraping", "web"))
    errors = check_areas_match_track(_cards(root))
    assert errors == [
        "backlog/XX-001.md: area 'database-schema' belongs to track 'data', not 'app'; "
        "split the card or mark it 'shared'",
        "review/XX-002.md: area 'web' belongs to track 'app', not 'data'; "
        "split the card or mark it 'shared'",
    ]


@pytest.mark.unit
def test_check_areas_match_track_exempts_planning_shared_and_neutral_areas(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "planning", "XX-001", track="app", areas=("planning", "api", "ml"))
    _write_card(root, "active", "XX-002", track="shared", areas=("api", "database-schema"))
    _write_card(root, "backlog", "XX-003", track="data", areas=("ml", *NEUTRAL_AREAS))
    _write_card(root, "backlog", "XX-004", track="app", areas=("web", *NEUTRAL_AREAS))
    assert check_areas_match_track(_cards(root)) == []


@pytest.mark.unit
def test_check_id_family_matches_track(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "F4E-001", track="data")
    _write_card(root, "backlog", "F6-001", track="app")
    _write_card(root, "backlog", "F8-001", track="app")
    _write_card(root, "planning", "WF-001", track="data")
    _write_card(root, "backlog", "F5-001", track="shared")
    _write_card(root, "backlog", "XX-001", track="app")
    _write_card(root, "done", "F7-001", track="data")
    errors = check_id_family_matches_track(_cards(root))
    assert errors == [
        "planning/WF-001.md: id family 'WF' belongs to track 'shared', not 'data'",
        "backlog/F8-001.md: id family 'F8' belongs to track 'data', not 'app'",
    ]


# --- cross-track impact and log ---------------------------------------------


@pytest.mark.unit
def test_parse_cross_track_log_reads_both_entry_shapes():
    entries, errors = parse_cross_track_log(
        "# Cross-track handoffs\n\n"
        "- 2026-01-01 | XX-000 (data) -> none | breaking | prose above sections is ignored\n\n"
        "## Open\n\n"
        "- 2026-10-01 | F8-003 (data) -> F6-021 (app) | additive | new column\n\n"
        "## Log\n\n"
        "- 2026-10-02 | F5-009 (shared) -> none | breaking | renamed a table\n"
    )
    assert errors == []
    assert [(e.section, e.source, e.target, e.kind) for e in entries] == [
        ("Open", "F8-003", "F6-021", "additive"),
        ("Log", "F5-009", None, "breaking"),
    ]
    assert entries[0].target_track == "app"
    assert entries[1].line_number == 11


@pytest.mark.unit
def test_parse_cross_track_log_reports_malformed_structure():
    _, errors = parse_cross_track_log(
        "## Open\n\n"
        "- 2026-10-01 F8-003 -> F6-021 additive\n"
        "- 2026-02-30 | F8-003 (data) -> F6-021 (app) | additive | not a date\n\n"
        "## Opne\n\n"
        "- 2026-10-01 | F8-003 (data) -> F6-021 (app) | additive | hidden\n"
    )
    assert errors == [
        "tasks/CROSS_TRACK.md:3: unsupported line in '## Open': "
        "'- 2026-10-01 F8-003 -> F6-021 additive'",
        "tasks/CROSS_TRACK.md:4: '2026-02-30' is not a real date",
        "tasks/CROSS_TRACK.md:6: unexpected section '## Opne'; "
        "only '## Open' and '## Log' are allowed",
        "tasks/CROSS_TRACK.md: missing '## Log' section",
    ]


@pytest.mark.unit
def test_check_cross_track_log_accepts_a_valid_log(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "review", "F8-003", track="data")
    _write_card(root, "planning", "F6-021", track="app")
    _write_card(root, "done", "F5-009", track="shared")
    _write_card(root, "done", "F6-020", track="app")
    _write_log(
        root,
        open_lines="- 2026-10-01 | F8-003 (data) -> F6-021 (app) | additive | new column\n",
        log_lines=(
            "- 2026-09-01 | F5-009 (shared) -> none | breaking | renamed a table\n"
            "- 2026-09-02 | F5-009 (shared) -> F6-020 (app) | additive | adopted\n"
        ),
    )
    assert check_cross_track_log(_cards(root), _entries(root)) == []


@pytest.mark.unit
def test_check_cross_track_log_enforces_where_entries_belong(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "review", "F8-003", track="data")
    _write_card(root, "done", "F6-020", track="app")
    _write_card(root, "done", "F5-009", track="shared")
    _write_log(
        root,
        open_lines=(
            "- 2026-10-01 | F8-003 (data) -> F6-020 (app) | additive | target already done\n"
            "- 2026-10-01 | F8-003 (data) -> none | additive | no target\n"
            "- 2026-10-01 | F5-009 (shared) -> none | breaking | breaking in open\n"
        ),
        log_lines=(
            "- 2026-10-01 | F8-003 (data) -> none | breaking | not from a shared card\n"
            "- 2026-10-01 | F8-003 (app) -> F6-404 (app) | renaming | wrong track, id, kind\n"
        ),
    )
    errors = check_cross_track_log(_cards(root), _entries(root))
    assert errors == [
        "tasks/CROSS_TRACK.md:5: target F6-020 is in tasks/done/; move the entry to '## Log'",
        "tasks/CROSS_TRACK.md:6: an open handoff needs a target card, not 'none'",
        "tasks/CROSS_TRACK.md:7: a breaking entry belongs in '## Log', not '## Open'",
        "tasks/CROSS_TRACK.md:11: a breaking change must come from a shared card",
        "tasks/CROSS_TRACK.md:12: F8-003 is track 'data', not 'app'",
        "tasks/CROSS_TRACK.md:12: 'F6-404' does not match any card id",
        "tasks/CROSS_TRACK.md:12: kind 'renaming' must be one of additive, breaking",
    ]


@pytest.mark.unit
def test_check_review_cross_track_impact_accepts_none_and_a_logged_impact(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "review", "F8-003", track="data", body="\n# Cross-track impact\n\n- None.\n")
    _write_card(
        root,
        "review",
        "F6-001",
        track="app",
        body=(
            "\n# Cross-track impact\n\n"
            "- Needs a player index from the data track; handoff card\n"
            "  F4E-050 records it.\n"
        ),
    )
    _write_card(root, "planning", "F4E-050", track="data")
    _write_log(root, open_lines="- 2026-10-01 | F6-001 (app) -> F4E-050 (data) | additive | index\n")
    assert check_review_cross_track_impact(_cards(root), _entries(root)) == []


@pytest.mark.unit
def test_check_review_cross_track_impact_reports_every_defect(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "review", "XX-001", body="\n# Impact\n\nNo cross-track section.\n")
    _write_card(root, "review", "XX-002", body="\n# Cross-track impact\n\n- None.\n- Also a column.\n")
    _write_card(root, "review", "XX-003", body="\n# Cross-track impact\n\nProse instead.\n")
    _write_card(root, "review", "XX-004", body="\n# Cross-track impact\n\n- Adds XX-404.\n")
    _write_card(root, "backlog", "XX-005", body="\n# Cross-track impact\n\nNot in review.\n")
    errors = check_review_cross_track_impact(_cards(root), [])
    assert errors == [
        "review/XX-001.md: missing '# Cross-track impact' section; "
        "write '- None.' or one bullet per impact",
        "review/XX-002.md: '# Cross-track impact' cannot mix '- None.' with impacts",
        "review/XX-003.md: '# Cross-track impact' must hold only bullets; found: 'Prose instead.'",
        "review/XX-003.md: '# Cross-track impact' is empty; write '- None.' or one bullet per impact",
        "review/XX-004.md: '# Cross-track impact' cites 'XX-404', which matches no card id",
        "review/XX-004.md: declares a cross-track impact, but tasks/CROSS_TRACK.md "
        "has no entry from XX-004",
    ]


# --- parked cards -----------------------------------------------------------


def _parked_body(
    *, branch: str = "feature/F6-001-a-card", waiting_on: str = "WF-001", resumed: str = ""
) -> str:
    lines = [
        "",
        "# Implementation notes",
        "",
        "Some notes.",
        "",
        "## Parked",
        "",
        f"- Branch: {branch}",
        f"- Waiting on: {waiting_on}",
        "- Parked: 2026-09-13",
        "- Reason: needs a dependency bump.",
    ]
    if resumed:
        lines.append(f"- Resumed: {resumed}")
    return "\n".join([*lines, "", "## Later notes", "", "- Branch: ignored", "", "# Durable knowledge updates", ""])


@pytest.mark.unit
def test_check_parked_cards_accepts_a_card_waiting_in_planning(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "WF-001", track="shared")
    _write_card(
        root, "planning", "F6-001", track="app", depends_on="\n  - WF-001", body=_parked_body()
    )
    assert check_parked_cards(_cards(root)) == []


@pytest.mark.unit
def test_check_parked_cards_reports_a_promoted_or_miswired_card(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "WF-001", track="shared")
    _write_card(root, "backlog", "F4E-001", track="data")
    _write_card(
        root,
        "backlog",
        "F6-001",
        track="app",
        depends_on="\n  - F4E-001",
        body=_parked_body(branch="feature/F6-002-other", waiting_on="WF-001, F4E-001, WF-404"),
    )
    errors = check_parked_cards(_cards(root))
    assert errors == [
        "backlog/F6-001.md: a parked card stays in tasks/planning/ until 'Resume F6-001.' claims it",
        "backlog/F6-001.md: parked branch 'feature/F6-002-other' must start with 'feature/F6-001-'",
        "backlog/F6-001.md: parked waiting on 'WF-001', which is not in depends_on",
        "backlog/F6-001.md: parked waiting on 'F4E-001', which is track 'data', not 'shared'",
        "backlog/F6-001.md: parked waiting on 'WF-404', which matches no card id",
    ]


@pytest.mark.unit
def test_check_parked_cards_requires_branch_and_waiting_on(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(
        root,
        "planning",
        "F6-001",
        track="app",
        body="\n# Implementation notes\n\n## Parked\n\n- Reason: forgot the fields.\n",
    )
    errors = check_parked_cards(_cards(root))
    assert errors == [
        "planning/F6-001.md: '## Parked' is missing '- Branch: feature/F6-001-<slug>'",
        "planning/F6-001.md: '## Parked' is missing '- Waiting on: <IDs>'",
    ]


@pytest.mark.unit
def test_check_parked_cards_frees_a_resumed_card(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "done", "WF-001", track="shared")
    _write_card(
        root,
        "active",
        "F6-001",
        track="app",
        depends_on="\n  - WF-001",
        body=_parked_body(resumed="2026-09-20"),
    )
    _write_card(
        root, "review", "F6-002", track="app", body=_parked_body(branch="x", resumed="soon")
    )
    errors = check_parked_cards(_cards(root))
    assert errors == ["review/F6-002.md: '- Resumed:' must be a YYYY-MM-DD date; got 'soon'"]


@pytest.mark.unit
def test_check_parked_cards_ignores_a_parked_heading_outside_implementation_notes(
    tmp_path: Path,
):
    root = _tasks_root(tmp_path)
    _write_card(
        root, "backlog", "F6-001", track="app", body="\n# Goal\n\n## Parked\n\n- Branch: x\n"
    )
    assert check_parked_cards(_cards(root)) == []


# --- worktrees --------------------------------------------------------------


def _worktree(tmp_path: Path, name: str, binding: str | None) -> Path:
    root = tmp_path / name
    _tasks_root(root)
    if binding is not None:
        (root / ".local").mkdir()
        (root / ".local" / "track").write_text(f"{binding}\n", encoding="utf-8")
    return root


@pytest.mark.unit
def test_validate_worktrees_accepts_one_card_per_bound_track(tmp_path: Path):
    data = _worktree(tmp_path, "data-wt", "data")
    app = _worktree(tmp_path, "app-wt", "app")
    _write_card(data / "tasks", "active", "F4E-001", track="data")
    _write_card(app / "tasks", "review", "F6-001", track="app")
    _write_card(app / "tasks", "backlog", "F6-002", track="app")
    worktrees, errors = validate_worktrees([data, app])
    assert errors == []
    assert [(w.binding, [c.label for c in w.cards]) for w in worktrees] == [
        ("data", ["data-wt:active/F4E-001.md"]),
        ("app", ["app-wt:review/F6-001.md"]),
    ]


@pytest.mark.unit
def test_validate_worktrees_joins_slots_across_worktrees(tmp_path: Path):
    data = _worktree(tmp_path, "data-wt", "data")
    app = _worktree(tmp_path, "app-wt", "app")
    _write_card(data / "tasks", "active", "WF-001", track="shared")
    _write_card(app / "tasks", "active", "F6-001", track="app")
    _, errors = validate_worktrees([data, app])
    assert len(errors) == 1
    assert "a shared card must be the only card" in errors[0]
    assert "data-wt:active/WF-001.md" in errors[0]
    assert "app-wt:active/F6-001.md" in errors[0]


@pytest.mark.unit
def test_check_worktree_bindings_reports_each_misconfiguration(tmp_path: Path):
    data = _worktree(tmp_path, "data-wt", "data")
    also_data = _worktree(tmp_path, "also-data-wt", "data")
    invalid = _worktree(tmp_path, "invalid-wt", "shared")
    unbound = _worktree(tmp_path, "unbound-wt", None)
    _write_card(data / "tasks", "active", "F6-001", track="app")
    _write_card(unbound / "tasks", "active", "F4E-001", track="data")
    worktrees = [validator.load_worktree(root)[0] for root in (data, also_data, invalid, unbound)]
    errors = check_worktree_bindings(worktrees)
    assert errors == [
        "data-wt:active/F6-001.md: a 'app' card is in progress in a worktree bound to 'data'",
        f"{invalid}: .local/track must read 'data' or 'app'; got 'shared'",
        f"track 'data' is bound to several worktrees: {data}, {also_data}",
    ]


@pytest.mark.unit
def test_check_worktree_bindings_accepts_a_single_unbound_checkout():
    assert check_worktree_bindings([Worktree(root=Path("repo"), binding=None, cards=())]) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"data\n", "data"),
        (b"\xef\xbb\xbfapp\r\n", "app"),
        ("data\r\n".encode("utf-16"), "data"),
        (b"  \n", None),
    ],
)
def test_read_track_binding_tolerates_editor_encodings(tmp_path: Path, raw: bytes, expected):
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local" / "track").write_bytes(raw)
    assert read_track_binding(tmp_path) == expected


@pytest.mark.unit
def test_read_track_binding_is_none_without_a_file(tmp_path: Path):
    assert read_track_binding(tmp_path) is None


@pytest.mark.unit
def test_main_all_worktrees_prints_bindings_and_joins_slots(tmp_path: Path, monkeypatch, capsys):
    data = _worktree(tmp_path, "data-wt", "data")
    app = _worktree(tmp_path, "app-wt", "app")
    monkeypatch.setattr(validator, "list_worktrees", lambda start: [data, app])

    assert main(["--tasks-root", str(data / "tasks"), "--all-worktrees"]) == 0
    out = capsys.readouterr().out
    assert f"worktree {data}: track data; in progress: none" in out
    assert f"worktree {app}: track app; in progress: none" in out

    _write_card(data / "tasks", "active", "F4E-001", track="data")
    _write_card(app / "tasks", "active", "F4E-002", track="data")
    assert main(["--tasks-root", str(data / "tasks")]) == 0
    capsys.readouterr()
    assert main(["--tasks-root", str(data / "tasks"), "--all-worktrees"]) == 1
    out = capsys.readouterr().out
    assert "track 'data' may hold one card" in out
    assert "a 'data' card is in progress in a worktree bound to 'app'" in out


# --- aggregator and CLI -----------------------------------------------------


@pytest.mark.unit
def test_load_cards_ignores_non_card_files(tmp_path: Path):
    root = _tasks_root(tmp_path)
    (root / "planning" / ".gitkeep").write_text("", encoding="utf-8")
    (root / "README.md").write_text("# Tasks\n", encoding="utf-8")
    (root / "manifests").mkdir()
    (root / "manifests" / "approved.json").write_text("{}", encoding="utf-8")
    _write_card(root, "planning", "XX-001")
    cards, errors = load_cards(root)
    assert errors == []
    assert [card.label for card in cards] == ["planning/XX-001.md"]


@pytest.mark.unit
def test_validate_tasks_returns_early_when_a_folder_is_missing(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001", depends_on="\n  - XX-404")
    (root / "review").rmdir()
    assert validate_tasks(root) == ["tasks/review/: lifecycle folder is missing"]


@pytest.mark.unit
def test_validate_tasks_requires_the_cross_track_log(tmp_path: Path):
    root = _tasks_root(tmp_path)
    (root / "CROSS_TRACK.md").unlink()
    assert validate_tasks(root) == ["tasks/CROSS_TRACK.md: cross-track log is missing"]


@pytest.mark.unit
def test_main_returns_zero_on_a_valid_tree_and_one_on_errors(tmp_path: Path, capsys):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001")
    assert main(["--tasks-root", str(root)]) == 0
    assert "Task validation passed." in capsys.readouterr().out

    _write_card(root, "active", "XX-002", track="data")
    _write_card(root, "active", "XX-003", track="data")
    assert main(["--tasks-root", str(root)]) == 1
    assert "track 'data' may hold one card" in capsys.readouterr().out


@pytest.mark.unit
def test_repository_tasks_tree_is_valid():
    """The real `tasks/` tree must always pass, so `uv run pytest` enforces it."""
    assert validate_tasks(REPO_ROOT / "tasks") == []
