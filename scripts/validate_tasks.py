"""Validate the `tasks/` folder lifecycle.

The folder a card sits in is its status. This script checks the invariants that
statement depends on, using only the standard library. Run it after moving a
card:

    uv run python scripts/validate_tasks.py
    uv run python scripts/validate_tasks.py --all-worktrees

Exit code 0 means the tree is valid; 1 means it printed errors. It reads files
and nothing else: no network, no database, no writes. `--all-worktrees` also
runs `git worktree list --porcelain`, which only reads.

`--all-worktrees` detects, after the fact, slots that a manual move took
without `scripts/claim_task.py`. It does not replace that script's lock.
"""

from __future__ import annotations

import argparse
import codecs
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
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

# Tracks. `data` and `app` each own one in-progress slot; `shared` needs both.
TRACKS = ("data", "app", "shared")
BOUND_TRACKS = ("data", "app")
AREA_TRACKS = {
    "scraping": "data",
    "database-schema": "data",
    "data-quality": "data",
    "ml": "data",
    "api": "app",
    "web": "app",
}
NEUTRAL_AREAS = ("database-read", "testing", "documentation", "planning", "review")
ID_FAMILY_TRACKS = {
    "F4E": "data",
    "F5": "data",
    "F8": "data",
    "F6": "app",
    "F7": "app",
    "WF": "shared",
}
TRACK_BINDING_PATH = Path(".local") / "track"

CROSS_TRACK_FILENAME = "CROSS_TRACK.md"
CROSS_TRACK_HEADING = "Cross-track impact"
CROSS_TRACK_SECTIONS = ("Open", "Log")
CROSS_TRACK_KINDS = ("additive", "breaking")

IMPLEMENTATION_NOTES_HEADING = "Implementation notes"

_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?P<rest>.*)$")
_ITEM_RE = re.compile(r"^ {2}- (?P<item>\S.*)$")
_HEADING_RE = re.compile(r"^#[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
_UNCHECKED_RE = re.compile(r"^-\s*\[ \]")
_CHECKED_RE = re.compile(r"^-\s*\[[xX]\]")
_NONE_RE = re.compile(r"^-?\s*none\.?$", re.IGNORECASE)
_CARD_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]*-\d{3}\b")
_SUBHEADING_RE = re.compile(r"^## (?P<title>.+?)[ \t]*$")
_PARKED_RE = re.compile(r"^## Parked[ \t]*$", re.MULTILINE)
_NEXT_SUBHEADING_RE = re.compile(r"^## ", re.MULTILINE)
_PARKED_FIELD_RE = re.compile(r"^- (?P<key>Branch|Waiting on|Resumed):[ \t]*(?P<value>.*?)[ \t]*$")
_ENTRY_RE = re.compile(
    r"^- (?P<date>\d{4}-\d{2}-\d{2})"
    r" \| (?P<source>\S+) \((?P<source_track>[a-z]+)\)"
    r" -> (?:none|(?P<target>\S+) \((?P<target_track>[a-z]+)\))"
    r" \| (?P<kind>[a-z]+)"
    r" \| (?P<summary>\S.*)$"
)


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
    """One task card, loaded from a lifecycle folder.

    `origin` names the worktree the card was read from when several are
    compared; it is empty for a single `tasks/` tree.
    """

    path: Path
    stage: str
    fields: dict[str, object]
    body: str
    origin: str = ""

    @property
    def label(self) -> str:
        label = f"{self.stage}/{self.path.name}"
        return f"{self.origin}:{label}" if self.origin else label

    @property
    def card_id(self) -> str:
        value = self.fields.get("id")
        return value if isinstance(value, str) else ""

    @property
    def track(self) -> str:
        value = self.fields.get("track")
        return value if isinstance(value, str) else ""

    def list_field(self, key: str) -> list[str]:
        value = self.fields.get(key)
        return [str(item) for item in value] if isinstance(value, list) else []


def load_cards(
    tasks_root: Path, *, stages: tuple[str, ...] = STAGES, origin: str = ""
) -> tuple[list[Card], list[str]]:
    """Load every `*.md` directly inside the given lifecycle folders.

    `.gitkeep`, `tasks/README.md`, `tasks/TEMPLATE.md`, `tasks/CROSS_TRACK.md`
    and `tasks/manifests/` fall outside this glob and are therefore ignored
    without special-casing.
    """
    cards: list[Card] = []
    errors: list[str] = []
    for stage in stages:
        for path in sorted((tasks_root / stage).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            label = f"{stage}/{path.name}"
            if origin:
                label = f"{origin}:{label}"
            fields, parse_errors = parse_frontmatter(text, label=label)
            errors.extend(parse_errors)
            marker = text.find("\n---", 3)
            body = text[marker + 4 :] if marker != -1 else ""
            cards.append(Card(path=path, stage=stage, fields=fields, body=body, origin=origin))
    return cards, errors


def check_lifecycle_folders(tasks_root: Path) -> list[str]:
    """Every lifecycle folder must exist, so the folder can be the status."""
    return [
        f"tasks/{stage}/: lifecycle folder is missing"
        for stage in STAGES
        if not (tasks_root / stage).is_dir()
    ]


def check_track_slots(cards: list[Card]) -> list[str]:
    """One in-progress card per track; a `shared` card must be the only one.

    Only cards in `active/` and `review/` count. A missing or invalid track
    counts as `shared`, the conservative reading. The check is pure, so
    `claim_task.py` applies it to the in-progress cards of every worktree plus
    the candidate before moving anything.
    """
    in_progress = [card for card in cards if card.stage in IN_PROGRESS_STAGES]
    if len(in_progress) <= 1:
        return []
    if any(card.track not in BOUND_TRACKS for card in in_progress):
        names = ", ".join(f"{card.label} ({card.track or 'no track'})" for card in in_progress)
        return [
            "a shared card must be the only card across tasks/active/ and tasks/review/ "
            f"(a missing or invalid track counts as shared); found {len(in_progress)}: {names}"
        ]
    errors: list[str] = []
    for track in BOUND_TRACKS:
        group = [card for card in in_progress if card.track == track]
        if len(group) > 1:
            names = ", ".join(card.label for card in group)
            errors.append(
                f"track {track!r} may hold one card across tasks/active/ and tasks/review/; "
                f"found {len(group)}: {names}"
            )
    return errors


def check_track_field(cards: list[Card]) -> list[str]:
    """Every card outside `done/` names its track; history is exempt."""
    errors: list[str] = []
    for card in cards:
        if card.stage == "done":
            continue
        if "track" not in card.fields:
            errors.append(f"{card.label}: missing required frontmatter key 'track'")
        elif card.track not in TRACKS:
            errors.append(
                f"{card.label}: 'track' must be one of {', '.join(TRACKS)}; "
                f"got {card.fields['track']!r}"
            )
    return errors


def check_areas_match_track(cards: list[Card]) -> list[str]:
    """A `data` or `app` card that is ready or in progress stays in its track's areas.

    `planning/` may mix areas until `prepare-task` splits the card or marks it
    `shared`. `shared` cards are unrestricted, neutral areas fit every track, and
    a missing or invalid track is `check_track_field`'s to report.
    """
    errors: list[str] = []
    for card in cards:
        if card.stage not in ("backlog", *IN_PROGRESS_STAGES) or card.track not in BOUND_TRACKS:
            continue
        for area in card.list_field("areas"):
            owner = AREA_TRACKS.get(area)
            if owner is not None and owner != card.track:
                errors.append(
                    f"{card.label}: area {area!r} belongs to track {owner!r}, not "
                    f"{card.track!r}; split the card or mark it 'shared'"
                )
    return errors


def id_family(card_id: str) -> str:
    """`F4E-021` -> `F4E`."""
    return card_id.split("-", 1)[0].upper()


def check_id_family_matches_track(cards: list[Card]) -> list[str]:
    """A `data` or `app` card uses an ID family of its own track.

    `shared` cards may use any family, and unknown families pass.
    """
    errors: list[str] = []
    for card in cards:
        if card.stage == "done" or card.track not in BOUND_TRACKS or not card.card_id:
            continue
        family = id_family(card.card_id)
        owner = ID_FAMILY_TRACKS.get(family)
        if owner is not None and owner != card.track:
            errors.append(
                f"{card.label}: id family {family!r} belongs to track {owner!r}, "
                f"not {card.track!r}"
            )
    return errors


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


# --- parked cards -------------------------------------------------------------


def parked_section(card: Card) -> str | None:
    """Return the '## Parked' block inside '# Implementation notes', or None."""
    notes = section_body(card.body, IMPLEMENTATION_NOTES_HEADING)
    if notes is None:
        return None
    match = _PARKED_RE.search(notes)
    if match is None:
        return None
    rest = notes[match.end() :]
    stop = _NEXT_SUBHEADING_RE.search(rest)
    return rest[: stop.start()] if stop else rest


def parked_fields(section: str) -> dict[str, str]:
    """Read `- Branch:`, `- Waiting on:` and `- Resumed:` from a '## Parked' block."""
    fields: dict[str, str] = {}
    for line in section.split("\n"):
        match = _PARKED_FIELD_RE.match(line.strip())
        if match is not None:
            fields.setdefault(match.group("key"), match.group("value"))
    return fields


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == 10


def check_parked_cards(cards: list[Card]) -> list[str]:
    """A parked card waits in `planning/` for the shared cards it names.

    Until `- Resumed: <date>` is added, the card must sit in `planning/`, its
    branch must be its own `feature/<ID>-...`, and every `Waiting on` id must
    exist, be a `shared` card, and appear in `depends_on`. This is what stops
    `prepare-task`, or a manual move, from promoting it without `Resume`.
    """
    by_id = {card.card_id: card for card in cards if card.card_id}
    errors: list[str] = []
    for card in cards:
        section = parked_section(card)
        if section is None:
            continue
        fields = parked_fields(section)
        if "Resumed" in fields:
            if not _is_iso_date(fields["Resumed"]):
                errors.append(
                    f"{card.label}: '- Resumed:' must be a YYYY-MM-DD date; "
                    f"got {fields['Resumed']!r}"
                )
            continue
        if card.stage != "planning":
            errors.append(
                f"{card.label}: a parked card stays in tasks/planning/ until "
                f"'Resume {card.card_id or '<TASK-ID>'}.' claims it"
            )
        branch = fields.get("Branch", "")
        expected = f"feature/{card.card_id}-"
        if not branch:
            errors.append(f"{card.label}: '## Parked' is missing '- Branch: {expected}<slug>'")
        elif not branch.casefold().startswith(expected.casefold()):
            errors.append(
                f"{card.label}: parked branch {branch!r} must start with {expected!r}"
            )
        waiting = [item.strip() for item in fields.get("Waiting on", "").split(",")]
        waiting = [item for item in waiting if item]
        if not waiting:
            errors.append(f"{card.label}: '## Parked' is missing '- Waiting on: <IDs>'")
        depends_on = set(card.list_field("depends_on"))
        for dep in waiting:
            blocker = by_id.get(dep)
            if blocker is None:
                errors.append(f"{card.label}: parked waiting on {dep!r}, which matches no card id")
                continue
            if dep not in depends_on:
                errors.append(f"{card.label}: parked waiting on {dep!r}, which is not in depends_on")
            if blocker.track != "shared":
                errors.append(
                    f"{card.label}: parked waiting on {dep!r}, which is track "
                    f"{blocker.track or 'unset'!r}, not 'shared'"
                )
    return errors


# --- cross-track log ----------------------------------------------------------


@dataclass(frozen=True)
class CrossTrackEntry:
    """One line of `tasks/CROSS_TRACK.md`."""

    section: str
    line_number: int
    date: str
    source: str
    source_track: str
    target: str | None
    target_track: str | None
    kind: str
    summary: str


def parse_cross_track_log(text: str) -> tuple[list[CrossTrackEntry], list[str]]:
    """Parse the '## Open' and '## Log' sections of `tasks/CROSS_TRACK.md`.

    Every non-blank line inside those sections must be one entry::

        - 2026-10-01 | F8-003 (data) -> F6-021 (app) | additive | summary
        - 2026-10-01 | F5-009 (shared) -> none | breaking | summary

    Text above the first section is free prose. Any other '## ' heading is an
    error, so an entry cannot escape the checks by sitting under a misspelt one.
    """
    label = f"tasks/{CROSS_TRACK_FILENAME}"
    entries: list[CrossTrackEntry] = []
    errors: list[str] = []
    seen: set[str] = set()
    section: str | None = None
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.rstrip()
        heading = _SUBHEADING_RE.match(line)
        if heading is not None:
            title = heading.group("title")
            if title not in CROSS_TRACK_SECTIONS:
                errors.append(
                    f"{label}:{number}: unexpected section {line!r}; "
                    "only '## Open' and '## Log' are allowed"
                )
                section = None
                continue
            if title in seen:
                errors.append(f"{label}:{number}: duplicate section {line!r}")
            seen.add(title)
            section = title
            continue
        if section is None or not line.strip():
            continue
        match = _ENTRY_RE.match(line)
        if match is None:
            errors.append(f"{label}:{number}: unsupported line in '## {section}': {line!r}")
            continue
        if not _is_iso_date(match.group("date")):
            errors.append(f"{label}:{number}: {match.group('date')!r} is not a real date")
            continue
        entries.append(
            CrossTrackEntry(
                section=section,
                line_number=number,
                date=match.group("date"),
                source=match.group("source"),
                source_track=match.group("source_track"),
                target=match.group("target"),
                target_track=match.group("target_track"),
                kind=match.group("kind"),
                summary=match.group("summary"),
            )
        )
    errors.extend(
        f"{label}: missing '## {title}' section"
        for title in CROSS_TRACK_SECTIONS
        if title not in seen
    )
    return entries, errors


def check_cross_track_log(cards: list[Card], entries: list[CrossTrackEntry]) -> list[str]:
    """Entries name real cards with their real tracks, and each sits where it belongs.

    `## Open` holds only `additive` handoffs whose target card is not done yet.
    A `breaking` change ships in a `shared` card and is recorded in `## Log`.
    """
    by_id = {card.card_id: card for card in cards if card.card_id}
    errors: list[str] = []
    for entry in entries:
        where = f"tasks/{CROSS_TRACK_FILENAME}:{entry.line_number}"
        for card_id, track in ((entry.source, entry.source_track), (entry.target, entry.target_track)):
            if card_id is None:
                continue
            if track not in TRACKS:
                errors.append(f"{where}: track {track!r} must be one of {', '.join(TRACKS)}")
            card = by_id.get(card_id)
            if card is None:
                errors.append(f"{where}: {card_id!r} does not match any card id")
            elif card.track in TRACKS and card.track != track:
                errors.append(f"{where}: {card_id} is track {card.track!r}, not {track!r}")
        if entry.kind not in CROSS_TRACK_KINDS:
            errors.append(
                f"{where}: kind {entry.kind!r} must be one of {', '.join(CROSS_TRACK_KINDS)}"
            )
        elif entry.kind == "breaking":
            if entry.section != "Log":
                errors.append(f"{where}: a breaking entry belongs in '## Log', not '## Open'")
            if entry.source_track != "shared":
                errors.append(f"{where}: a breaking change must come from a shared card")
        elif entry.section == "Open":
            target = by_id.get(entry.target) if entry.target else None
            if entry.target is None:
                errors.append(f"{where}: an open handoff needs a target card, not 'none'")
            elif target is not None and target.stage == "done":
                errors.append(
                    f"{where}: target {entry.target} is in tasks/done/; move the entry to '## Log'"
                )
    return errors


def _section_bullets(section: str) -> tuple[list[str], list[str]]:
    """Split a body section into bullet lines and stray non-bullet lines."""
    bullets: list[str] = []
    stray: list[str] = []
    in_bullet = False
    for raw in section.split("\n"):
        line = raw.strip()
        if not line:
            in_bullet = False
            continue
        if in_bullet and raw[:1].isspace():
            continue  # wrapped continuation of the bullet above
        in_bullet = line.startswith("-")
        (bullets if in_bullet else stray).append(line)
    return bullets, stray


def check_review_cross_track_impact(
    cards: list[Card], entries: list[CrossTrackEntry]
) -> list[str]:
    """A card in `review/` declares what it changes for the other track.

    '# Cross-track impact' is '- None.' or one bullet per impact. The ids it
    cites must exist, and a declared impact must be recorded in
    `tasks/CROSS_TRACK.md` under the card's id.
    """
    known = {card.card_id for card in cards if card.card_id}
    logged = {entry.source for entry in entries}
    errors: list[str] = []
    for card in (card for card in cards if card.stage == "review"):
        section = section_body(card.body, CROSS_TRACK_HEADING)
        if section is None:
            errors.append(
                f"{card.label}: missing '# {CROSS_TRACK_HEADING}' section; "
                "write '- None.' or one bullet per impact"
            )
            continue
        bullets, stray = _section_bullets(section)
        if stray:
            errors.append(
                f"{card.label}: '# {CROSS_TRACK_HEADING}' must hold only bullets; "
                f"found: {stray[0]!r}"
            )
        if not bullets:
            errors.append(
                f"{card.label}: '# {CROSS_TRACK_HEADING}' is empty; "
                "write '- None.' or one bullet per impact"
            )
            continue
        if any(_NONE_RE.match(bullet) for bullet in bullets):
            if len(bullets) > 1:
                errors.append(
                    f"{card.label}: '# {CROSS_TRACK_HEADING}' cannot mix '- None.' with impacts"
                )
            continue
        for cited in sorted(set(_CARD_ID_RE.findall(section))):
            if cited not in known:
                errors.append(
                    f"{card.label}: '# {CROSS_TRACK_HEADING}' cites {cited!r}, "
                    "which matches no card id"
                )
        if card.card_id not in logged:
            errors.append(
                f"{card.label}: declares a cross-track impact, but "
                f"tasks/{CROSS_TRACK_FILENAME} has no entry from {card.card_id or 'this card'}"
            )
    return errors


# --- worktrees ----------------------------------------------------------------


class WorktreeError(RuntimeError):
    """`git worktree list` could not be read."""


@dataclass(frozen=True)
class Worktree:
    """A worktree's track binding and its in-progress cards."""

    root: Path
    binding: str | None
    cards: tuple[Card, ...]


def list_worktrees(start: Path) -> list[Path]:
    """Return every worktree of the repository containing `start`, main worktree first.

    Runs `git worktree list --porcelain`, which only reads.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "worktree", "list", "--porcelain"],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise WorktreeError(f"cannot run git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise WorktreeError(f"git worktree list failed in {start}: {detail}")
    return [
        Path(line.removeprefix("worktree "))
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]


def read_track_binding(root: Path) -> str | None:
    """Return the stripped content of `<root>/.local/track`, or None when unbound.

    Tolerates the byte-order marks PowerShell writes. Validity is left to the
    caller, so an invalid value can be reported rather than hidden.
    """
    try:
        raw = (root / TRACK_BINDING_PATH).read_bytes()
    except FileNotFoundError:
        return None
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    return text.strip() or None


def load_worktree(root: Path) -> tuple[Worktree, list[str]]:
    """Read one worktree's binding and the cards in its `active/` and `review/`."""
    cards, errors = load_cards(root / "tasks", stages=IN_PROGRESS_STAGES, origin=root.name)
    return Worktree(root=root, binding=read_track_binding(root), cards=tuple(cards)), errors


def check_worktree_bindings(worktrees: list[Worktree]) -> list[str]:
    """Bindings are `data` or `app`, one worktree per track, holding only fitting cards.

    An unbound worktree passes, so a single unconfigured checkout stays valid.
    """
    errors: list[str] = []
    bound: dict[str, list[Worktree]] = defaultdict(list)
    for worktree in worktrees:
        if worktree.binding is None:
            continue
        if worktree.binding not in BOUND_TRACKS:
            errors.append(
                f"{worktree.root}: {TRACK_BINDING_PATH.as_posix()} must read 'data' or 'app'; "
                f"got {worktree.binding!r}"
            )
            continue
        bound[worktree.binding].append(worktree)
        for card in worktree.cards:
            if card.track in BOUND_TRACKS and card.track != worktree.binding:
                errors.append(
                    f"{card.label}: a {card.track!r} card is in progress in a worktree "
                    f"bound to {worktree.binding!r}"
                )
    for track, group in sorted(bound.items()):
        if len(group) > 1:
            roots = ", ".join(str(worktree.root) for worktree in group)
            errors.append(f"track {track!r} is bound to several worktrees: {roots}")
    return errors


def validate_worktrees(roots: list[Path]) -> tuple[list[Worktree], list[str]]:
    """Apply the slot and binding checks across the in-progress cards of every worktree."""
    worktrees: list[Worktree] = []
    errors: list[str] = []
    for root in roots:
        worktree, load_errors = load_worktree(root)
        worktrees.append(worktree)
        errors.extend(load_errors)
    cards = [card for worktree in worktrees for card in worktree.cards]
    errors.extend(check_track_slots(cards))
    errors.extend(check_worktree_bindings(worktrees))
    return worktrees, errors


# --- aggregate ----------------------------------------------------------------


def validate_tasks(tasks_root: Path) -> list[str]:
    """Return every task-lifecycle error. An empty list means the tree is valid."""
    folder_errors = check_lifecycle_folders(tasks_root)
    if folder_errors:
        return folder_errors
    cards, errors = load_cards(tasks_root)
    for check in (
        check_track_slots,
        check_track_field,
        check_areas_match_track,
        check_id_family_matches_track,
        check_unique_ids_within_stage,
        check_required_fields,
        check_dependencies_resolve,
        check_forbidden_fields,
        check_backlog_decisions_resolved,
        check_active_dependencies_done,
        check_id_in_one_stage,
        check_filename_matches_id,
        check_parked_cards,
    ):
        errors.extend(check(cards))

    log_path = tasks_root / CROSS_TRACK_FILENAME
    entries: list[CrossTrackEntry] = []
    if log_path.is_file():
        entries, log_errors = parse_cross_track_log(log_path.read_text(encoding="utf-8"))
        errors.extend(log_errors)
    else:
        errors.append(f"tasks/{CROSS_TRACK_FILENAME}: cross-track log is missing")
    errors.extend(check_cross_track_log(cards, entries))
    errors.extend(check_review_cross_track_impact(cards, entries))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the tasks/ folder lifecycle.")
    parser.add_argument(
        "--tasks-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tasks",
        help="Path to the tasks/ directory (default: this repository's tasks/).",
    )
    parser.add_argument(
        "--all-worktrees",
        action="store_true",
        help=(
            "Also check slots and track bindings across every Git worktree of the "
            "repository holding --tasks-root (runs `git worktree list --porcelain`)."
        ),
    )
    args = parser.parse_args(argv)
    errors = validate_tasks(args.tasks_root)
    if args.all_worktrees:
        try:
            roots = list_worktrees(args.tasks_root.resolve().parent)
        except WorktreeError as exc:
            errors.append(f"--all-worktrees: {exc}")
        else:
            worktrees, worktree_errors = validate_worktrees(roots)
            errors.extend(worktree_errors)
            for worktree in worktrees:
                cards = ", ".join(card.label for card in worktree.cards) or "none"
                print(
                    f"worktree {worktree.root}: track {worktree.binding or 'unbound'}; "
                    f"in progress: {cards}"
                )
    for error in errors:
        print(error)
    if errors:
        print(f"{len(errors)} task validation error(s).")
        return 1
    print("Task validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
