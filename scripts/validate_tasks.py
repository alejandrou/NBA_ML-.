"""Validate the `tasks/` folder lifecycle.

The folder a card sits in is its status. This script checks the invariants that
statement depends on, using only the standard library. Run it after moving a
card:

    uv run python scripts/validate_tasks.py

Exit code 0 means the tree is valid; 1 means it printed errors. It reads files
and nothing else: no network, no database, no writes.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

STAGES = ("planning", "backlog", "active", "review", "done")
IN_PROGRESS_STAGES = ("active", "review")
REQUIRED_KEYS = (
    "id",
    "title",
    "areas",
    "priority",
    "depends_on",
    "read",
    "validation",
    "critical_actions",
)
LIST_KEYS = ("areas", "depends_on", "read", "validation", "critical_actions")
FORBIDDEN_KEYS = (
    "status",
    "phase",
    "mode",
    "owner_approved",
    "requires_owner_approval",
    "approval_scope",
    "skills",
    "allowed_paths",
    "forbidden_paths",
)
HUMAN_DECISIONS_HEADING = "Human decisions or resources"

_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?P<rest>.*)$")
_ITEM_RE = re.compile(r"^ {2}- (?P<item>\S.*)$")
_HEADING_RE = re.compile(r"^#[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
_UNCHECKED_RE = re.compile(r"^-\s*\[ \]")
_CHECKED_RE = re.compile(r"^-\s*\[[xX]\]")
_NONE_RE = re.compile(r"^-?\s*none\.?$", re.IGNORECASE)


def parse_frontmatter(text: str, *, label: str) -> tuple[dict[str, object], list[str]]:
    """Parse the tiny controlled frontmatter subset used by task cards.

    Exactly three shapes are accepted::

        key: scalar
        key: []
        key:
          - item

    Everything else -- nested maps, inline lists with content, quoted or folded
    scalars, tabs, anchors, comments, indentation other than two spaces -- is
    reported as an error rather than guessed at. This is not a YAML parser and
    must never be used on anything but `tasks/**/*.md` frontmatter.

    Known limits: `key:` with no following items is indistinguishable from
    `key: []`, and a scalar containing `: ` is kept verbatim after the first
    colon.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, [f"{label}: file must open with a '---' frontmatter fence"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, [f"{label}: frontmatter fence is never closed"]

    fields: dict[str, object] = {}
    errors: list[str] = []
    current: str | None = None

    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            current = None
            continue
        item = _ITEM_RE.match(line)
        if item is not None:
            if current is None:
                errors.append(f"{label}:{number}: list item outside a list key: {line!r}")
                continue
            collected = fields[current]
            if isinstance(collected, list):
                collected.append(item.group("item").strip())
            continue
        match = _KEY_RE.match(line)
        if match is None:
            errors.append(f"{label}:{number}: unsupported frontmatter line: {line!r}")
            current = None
            continue
        key = match.group("key")
        rest = match.group("rest").strip()
        if key in fields:
            errors.append(f"{label}:{number}: duplicate frontmatter key {key!r}")
        if rest in ("", "[]"):
            fields[key] = []
            current = key if rest == "" else None
        else:
            fields[key] = rest
            current = None

    return fields, errors


def section_body(body: str, title: str) -> str | None:
    """Return the text under a level-1 '# title' heading, or None if absent.

    '## Automated validation' does not match: '#' must be followed by whitespace.
    """
    matches = list(_HEADING_RE.finditer(body))
    for index, match in enumerate(matches):
        if match.group("title").casefold() != title.casefold():
            continue
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        return body[match.end() : stop]
    return None


@dataclass(frozen=True)
class Card:
    """One task card, loaded from a lifecycle folder."""

    path: Path
    stage: str
    fields: dict[str, object]
    body: str

    @property
    def label(self) -> str:
        return f"{self.stage}/{self.path.name}"

    @property
    def card_id(self) -> str:
        value = self.fields.get("id")
        return value if isinstance(value, str) else ""

    def list_field(self, key: str) -> list[str]:
        value = self.fields.get(key)
        return [str(item) for item in value] if isinstance(value, list) else []


def load_cards(tasks_root: Path) -> tuple[list[Card], list[str]]:
    """Load every `*.md` directly inside the five lifecycle folders.

    `.gitkeep`, `tasks/README.md`, `tasks/TEMPLATE.md` and `tasks/manifests/`
    fall outside this glob and are therefore ignored without special-casing.
    """
    cards: list[Card] = []
    errors: list[str] = []
    for stage in STAGES:
        for path in sorted((tasks_root / stage).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            label = f"{stage}/{path.name}"
            fields, parse_errors = parse_frontmatter(text, label=label)
            errors.extend(parse_errors)
            marker = text.find("\n---", 3)
            body = text[marker + 4 :] if marker != -1 else ""
            cards.append(Card(path=path, stage=stage, fields=fields, body=body))
    return cards, errors


def check_lifecycle_folders(tasks_root: Path) -> list[str]:
    """Every lifecycle folder must exist, so the folder can be the status."""
    return [
        f"tasks/{stage}/: lifecycle folder is missing"
        for stage in STAGES
        if not (tasks_root / stage).is_dir()
    ]


def check_single_in_progress_card(cards: list[Card]) -> list[str]:
    """At most one card may exist across `active/` and `review/` combined."""
    in_progress = [card for card in cards if card.stage in IN_PROGRESS_STAGES]
    if len(in_progress) <= 1:
        return []
    names = ", ".join(card.label for card in in_progress)
    return [
        "at most one card may exist across tasks/active/ and tasks/review/; "
        f"found {len(in_progress)}: {names}"
    ]


def check_unique_ids_within_stage(cards: list[Card]) -> list[str]:
    """No two cards in the same folder may share an id."""
    grouped: dict[tuple[str, str], list[Card]] = defaultdict(list)
    for card in cards:
        if card.card_id:
            grouped[(card.stage, card.card_id)].append(card)
    return [
        f"tasks/{stage}/: duplicate card id {card_id!r} in "
        + ", ".join(card.path.name for card in group)
        for (stage, card_id), group in sorted(grouped.items())
        if len(group) > 1
    ]


def check_required_fields(cards: list[Card]) -> list[str]:
    """Required frontmatter keys are present and carry the expected shape."""
    errors: list[str] = []
    for card in cards:
        for key in REQUIRED_KEYS:
            if key not in card.fields:
                errors.append(f"{card.label}: missing required frontmatter key {key!r}")
        for key in LIST_KEYS:
            value = card.fields.get(key)
            if value is not None and not isinstance(value, list):
                errors.append(
                    f"{card.label}: {key!r} must be a list ('[]' or '  - item' lines)"
                )
        for key in ("id", "title"):
            value = card.fields.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{card.label}: {key!r} must be a non-empty scalar")
        priority = card.fields.get("priority")
        if priority is not None and not (
            isinstance(priority, str) and priority.strip().isdigit()
        ):
            errors.append(f"{card.label}: 'priority' must be a whole number, got {priority!r}")
    return errors


def check_dependencies_resolve(cards: list[Card]) -> list[str]:
    """Every `depends_on` entry must name a card that actually exists."""
    known = {card.card_id for card in cards if card.card_id}
    return [
        f"{card.label}: depends_on {dep!r} does not match any card id"
        for card in cards
        for dep in card.list_field("depends_on")
        if dep not in known
    ]


def check_forbidden_fields(cards: list[Card]) -> list[str]:
    """Cards carry no duplicated state: the folder is the status."""
    return [
        f"{card.label}: forbidden frontmatter key {key!r}; the folder is the status"
        for card in cards
        for key in FORBIDDEN_KEYS
        if key in card.fields
    ]


def check_backlog_decisions_resolved(cards: list[Card]) -> list[str]:
    """A backlog card may not carry an unresolved human decision.

    An absent section passes: no check may require a body section to exist,
    because historical cards in `tasks/done/` predate the current template.
    """
    errors: list[str] = []
    for card in (card for card in cards if card.stage == "backlog"):
        section = section_body(card.body, HUMAN_DECISIONS_HEADING)
        if section is None:
            continue
        in_bullet = False
        for raw in section.split("\n"):
            line = raw.strip()
            if not line:
                in_bullet = False
                continue
            if in_bullet and raw[:1].isspace():
                continue  # wrapped continuation of the bullet above
            in_bullet = line.startswith(("-", "*"))
            if _NONE_RE.match(line) or _CHECKED_RE.match(line):
                continue
            if _UNCHECKED_RE.match(line):
                errors.append(
                    f"{card.label}: unresolved human decision in "
                    f"{HUMAN_DECISIONS_HEADING!r}: {line!r}; "
                    "move the card back to tasks/planning/"
                )
            else:
                errors.append(
                    f"{card.label}: {HUMAN_DECISIONS_HEADING!r} must be '- None.' or "
                    f"resolved '- [x]' items in tasks/backlog/; found: {line!r}"
                )
    return errors


def check_active_dependencies_done(cards: list[Card]) -> list[str]:
    """The card being implemented must have every dependency completed."""
    stage_of = {card.card_id: card.stage for card in cards if card.card_id}
    errors: list[str] = []
    for card in (card for card in cards if card.stage == "active"):
        for dep in card.list_field("depends_on"):
            stage = stage_of.get(dep)
            if stage != "done":
                where = f"in tasks/{stage}/" if stage else "not found"
                errors.append(
                    f"{card.label}: dependency {dep!r} is {where}, not in tasks/done/"
                )
    return errors


def check_id_in_one_stage(cards: list[Card]) -> list[str]:
    """One card id lives in exactly one lifecycle folder."""
    stages_by_id: dict[str, set[str]] = defaultdict(set)
    for card in cards:
        if card.card_id:
            stages_by_id[card.card_id].add(card.stage)
    return [
        f"card id {card_id!r} appears in several lifecycle folders: "
        + ", ".join(f"tasks/{stage}/" for stage in sorted(stages))
        for card_id, stages in sorted(stages_by_id.items())
        if len(stages) > 1
    ]


def check_filename_matches_id(cards: list[Card]) -> list[str]:
    """Filename must be `<id>.md` or `<id>-<slug>.md`, case-insensitively."""
    errors: list[str] = []
    for card in cards:
        card_id = card.card_id
        if not card_id:
            continue
        stem = card.path.stem.casefold()
        folded = card_id.casefold()
        if stem != folded and not stem.startswith(f"{folded}-"):
            errors.append(
                f"{card.label}: filename must be '{card_id}.md' or '{card_id}-<slug>.md'"
            )
    return errors


def validate_tasks(tasks_root: Path) -> list[str]:
    """Return every task-lifecycle error. An empty list means the tree is valid."""
    folder_errors = check_lifecycle_folders(tasks_root)
    if folder_errors:
        return folder_errors
    cards, errors = load_cards(tasks_root)
    for check in (
        check_single_in_progress_card,
        check_unique_ids_within_stage,
        check_required_fields,
        check_dependencies_resolve,
        check_forbidden_fields,
        check_backlog_decisions_resolved,
        check_active_dependencies_done,
        check_id_in_one_stage,
        check_filename_matches_id,
    ):
        errors.extend(check(cards))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the tasks/ folder lifecycle.")
    parser.add_argument(
        "--tasks-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tasks",
        help="Path to the tasks/ directory (default: this repository's tasks/).",
    )
    args = parser.parse_args(argv)
    errors = validate_tasks(args.tasks_root)
    for error in errors:
        print(error)
    if errors:
        print(f"{len(errors)} task validation error(s).")
        return 1
    print("Task validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
