---
name: review
description: Use when reviewing a diff, a task's completeness, or a pull request; inspects work against acceptance criteria and prepares it for the user's manual testing without marking anything done.
---

## Workflow

1. Read the active card and inspect the diff (`git diff`, plus `git diff --cached`
   if anything is staged).
2. Compare the change against the card's acceptance criteria and scope, one
   criterion at a time.
3. Run or verify the card's `validation:` commands. Report real output, not
   assumptions.
4. Report findings ordered by severity, with file and rationale.
5. Fix ordinary implementation defects in place. Anything larger becomes a new
   backlog card, not scope creep.
6. Write the card's `# Review evidence`: commands and results, numbered manual
   happy-path and sad-path steps with expected results, known limitations.
7. If the work is complete, move the card to `tasks/review/` and stop.

Load the relevant domain skill alongside this one for API, database, scraping, or
schema checks.

## Check for

Scope creep beyond the card · offline-test boundaries (no network, no shared
database) · secrets or `.env` content · `data/` or `reports/` artifacts in the
diff · domain invariants (`TOT` is not a real team, `player_name` is not a stable
key) · raw / core / stats / features separation · the live-scraping approval gate
still intact · unrelated refactoring.

## Documentation changes

Keep documents concise, avoid duplicating architecture across files, preserve
useful history, and update inbound cross-references when a file moves or is
deleted.

## Boundaries

Do not perform broad refactors or implement substantial new work during review.

**Never move a card to `tasks/done/`.** Only the user authorizes `review → done`,
by saying so explicitly. Reporting that a task looks complete is not the same as
closing it.
