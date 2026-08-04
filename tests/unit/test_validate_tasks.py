"""Focused tests for the task lifecycle validator."""

from pathlib import Path

import pytest
from scripts.validate_tasks import (
    STAGES,
    check_active_dependencies_done,
    check_backlog_decisions_resolved,
    check_dependencies_resolve,
    check_filename_matches_id,
    check_forbidden_fields,
    check_id_in_one_stage,
    check_lifecycle_folders,
    check_required_fields,
    check_single_in_progress_card,
    check_unique_ids_within_stage,
    load_cards,
    main,
    parse_frontmatter,
    section_body,
    validate_tasks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FRONTMATTER = """---
id: {card_id}
title: {title}
areas:
  - documentation
priority: {priority}
depends_on: {depends_on}
read: []
validation: []
critical_actions: []
---
"""


def _tasks_root(tmp_path: Path) -> Path:
    root = tmp_path / "tasks"
    for stage in STAGES:
        (root / stage).mkdir(parents=True)
    return root


def _write_card(
    root: Path,
    stage: str,
    card_id: str,
    *,
    filename: str | None = None,
    depends_on: str = "[]",
    priority: str = "50",
    title: str = "A card",
    body: str = "",
    frontmatter: str | None = None,
) -> Path:
    path = root / stage / (filename or f"{card_id}.md")
    text = frontmatter if frontmatter is not None else FRONTMATTER.format(
        card_id=card_id, title=title, depends_on=depends_on, priority=priority
    )
    path.write_text(text + body, encoding="utf-8")
    return path


def _cards(root: Path):
    cards, errors = load_cards(root)
    assert errors == []
    return cards


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
def test_check_single_in_progress_card_allows_one_and_rejects_two(tmp_path: Path):
    root = _tasks_root(tmp_path)
    _write_card(root, "active", "XX-001")
    assert check_single_in_progress_card(_cards(root)) == []
    _write_card(root, "review", "XX-002")
    errors = check_single_in_progress_card(_cards(root))
    assert len(errors) == 1
    assert "at most one card" in errors[0]
    assert "active/XX-001.md" in errors[0]
    assert "review/XX-002.md" in errors[0]


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
        frontmatter=FRONTMATTER.format(
            card_id="XX-001", title="A card", depends_on="[]", priority="50"
        ).replace("---\nid:", f"---\n{key}: something\nid:"),
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
def test_main_returns_zero_on_a_valid_tree_and_one_on_errors(tmp_path: Path, capsys):
    root = _tasks_root(tmp_path)
    _write_card(root, "backlog", "XX-001")
    assert main(["--tasks-root", str(root)]) == 0
    assert "Task validation passed." in capsys.readouterr().out

    _write_card(root, "active", "XX-002")
    _write_card(root, "review", "XX-003")
    assert main(["--tasks-root", str(root)]) == 1
    assert "at most one card" in capsys.readouterr().out


@pytest.mark.unit
def test_repository_tasks_tree_is_valid():
    """The real `tasks/` tree must always pass, so `uv run pytest` enforces it."""
    assert validate_tasks(REPO_ROOT / "tasks") == []
