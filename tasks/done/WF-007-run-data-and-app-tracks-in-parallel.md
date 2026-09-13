---
id: WF-007
title: Run the data and app tracks in parallel
track: shared
areas:
  - documentation
  - testing
priority: 60
depends_on:
  - WF-006
read:
  - docs/decisions/0017-use-task-folder-lifecycle.md
  - scripts/validate_tasks.py
  - tests/unit/test_validate_tasks.py
validation:
  - uv run pytest tests/unit/test_validate_tasks.py tests/unit/test_claim_task.py
  - uv run python scripts/validate_tasks.py
  - uv run python scripts/validate_tasks.py --all-worktrees
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - git diff --check
critical_actions: []
---

# Goal

Let the `data` track (scraping, schema, migrations, features, ML) and the `app`
track (API and web) progress at the same time without losing any guarantee of
the task-folder lifecycle: the folder stays the status, Git and critical actions
stay gated, and the rules stay mechanically validated. Changes that cross from
one track to the other get an explicit channel.

# Evidence and current state

- ADR 0017 allows one card across `tasks/active/` and `tasks/review/`, enforced
  by `check_single_in_progress_card` in `scripts/validate_tasks.py`.
  `Start the next task.` leaves its work uncommitted on the branch, so the API
  and the data work cannot advance together.
- Alembic is a linear chain: two tracks each creating `0009_*` would split the
  head.
- `/api/v1/health/ready` requires the database to be at the head of the code in
  that checkout (`src/nba_data/api/services/readiness.py`).
- Pull requests are squash-merged (#47–#50), so "is the branch merged?" is a
  `gh` question, not an ancestry one.
- `COMANDOS.md` and `.local/` are ignored by Git.

# Human decisions or resources

- [x] Tracks: `data` = scraping, schema, migrations, features, ML; `app` = API
      and web, reading the database only; `shared` = workflow, CI,
      `pyproject.toml`/`uv.lock`, `AGENTS.md`, and every change that breaks the
      other track.
- [x] One card per track across `active/` and `review/`; a `shared` card needs
      both slots free and blocks both.
- [x] Two fixed worktrees bound through `.local/track`: this folder is `data`,
      `../Scraping nba-reference-app` is `app`.
- [x] Start fetches `origin` and branches from `origin/main`, stopping when the
      current `feature/*` branch is not merged.
- [x] Cross-track changes: handoff card in the consumer's `planning/` plus an
      entry in `tasks/CROSS_TRACK.md`; breaking changes go in a `shared` card.
- [x] Only `data` writes migrations; they reach `nba` only from merged
      `origin/main` with the owner's approval. Readiness is unchanged.
- [x] The predictor plan stays out of this card.

# Acceptance criteria

- Cards outside `done/` carry `track: data|app|shared`; areas and ID families
  are checked against the track; slots are one per track with `shared`
  exclusive; review cards declare `# Cross-track impact`; `tasks/CROSS_TRACK.md`
  and parked cards are validated.
- `scripts/validate_tasks.py --all-worktrees` joins in-progress cards and
  bindings across every worktree; without the flag nothing about CI changes.
- `scripts/claim_task.py` checks and occupies a slot in one exclusive operation
  across worktrees, proven by a deterministic interleaving test and by 20 real
  concurrent races per variant.
- `Park the current task.` and `Resume <TASK-ID>.` exist as a skill with an
  enumerated Git authorization, and are rehearsed end to end in a disposable
  repository.
- Skills, `AGENTS.md`, `.agents/index.md`, `tasks/README.md`, `README.md`, and a
  new ADR 0018 describe the same model; ADR 0017's single slot is superseded.
- Live cards carry their track; the repository tree validates.

# Scope

`scripts/validate_tasks.py`, new `scripts/claim_task.py`, their unit tests,
`tasks/TEMPLATE.md`, `tasks/CROSS_TRACK.md`, the `track` field of live cards,
`.agents/skills/` (start-task, git-control, plan-task, backlog-planning,
prepare-task, review, new park-resume), `.agents/index.md`, `AGENTS.md`,
`tasks/README.md`, `README.md`, `docs/decisions/0017-*` and new `0018-*`,
`docs/architecture/IMPACT_MAP.md`'s planning row, and the local `COMANDOS.md`.

# Out of scope

Creating the second worktree or `.local/track` files (after merge, on the
owner's instruction). The predictor plan, `docs/ml/`, and `F8-001`. Readiness,
Alembic, CI configuration, and any product code.

# Impact

Every workflow skill and every future card. `uv run pytest` keeps enforcing the
lifecycle through `test_repository_tasks_tree_is_valid`.

# Cross-track impact

- None.

# Implementation notes

- The claim lock is `<main worktree>/.local/task-slot.lock`, created with
  `O_CREAT | O_EXCL`; the claim never deletes a lock it did not create.
- The folders stay the only state: no persistent reservations.
- Resume merges `origin/main` into the parked branch rather than rebasing, so
  a pushed branch never needs a force-push; the squash merge discards the merge
  commit anyway.

# Durable knowledge updates

- `docs/decisions/0018-run-data-and-app-tracks-in-parallel.md` — new.
- `docs/decisions/0017-use-task-folder-lifecycle.md` — status updated.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_validate_tasks.py tests/unit/test_claim_task.py -q`
- Result: 84 passed (64 validator, 20 claim).

- Command: `uv run pytest tests/unit/test_claim_task.py -q`, five times in a row
- Result: 20 passed each run, 8.5–8.9 s. Each run includes 40 real two-process
  races.

- Command: mutation check (scratchpad): the claim with `O_EXCL` removed from the
  lock, driven through the test module's own race helper
- Result: 19 of 20 iterations ended with other than one card in progress, so the
  race test detects a missing lock.

- Command: `uv run python scripts/validate_tasks.py`
- Result: `Task validation passed.`

- Command: `uv run python scripts/validate_tasks.py --all-worktrees`
- Result: lists the single, unbound worktree holding WF-007; passed.

- Command: `uv run ruff check .` · `uv run mypy src/nba_data`
- Result: All checks passed · Success: no issues found in 70 source files.

- Command: `uv run pytest -m "not integration and not live" -q`
- Result: 999 passed, 28 deselected, 7 pre-existing warnings.

- Command: `git diff --check`
- Result: exit 0; LF→CRLF notices only.

- Command: validator against scratchpad copies of `tasks/` via `--tasks-root`
- Result: all five sad paths exit 1 with the expected error — two `data` cards
  in `active/`; `shared` beside `app`; an `app` card with `database-schema` in
  `backlog/`; an Open entry whose target is in `done/`; a parked card in
  `backlog/`. The unmodified copy passes.

- Command: Park/Resume rehearsal (scratchpad `rehearsal.sh`): a bare `origin`,
  a `data` clone plus an `app` worktree, squash merges through a third clone
- Result: `REHEARSAL PASSED`. Data and app tasks ran at once. Park committed
  code only and detached, carrying ` D backlog/F6-001`, `?? backlog/WF-001` and
  `?? planning/F6-001` uncommitted. The shared card was rejected while `data`
  was busy, then started in the parking folder, closed with the parked card's
  bookkeeping, and squash-merged. Resume's switch and `git merge origin/main`
  were clean. `claim_task.py --resume` succeeded while a concurrent shared claim
  from the `data` worktree got `busy`, then `rejected` by slot. The resumed
  branch diff against `origin/main` was only the app code, and it squash-merged
  with `main` still valid. Sad paths: Park refused with a staged code file, with
  a staged card file, and with a branch commit touching `tasks/`; Resume refused
  a branch commit touching `tasks/` without switching. In each case
  `git status --porcelain`, `HEAD`, the index and the `tasks/` tree were
  byte-identical before and after.

## Manual happy path

These are post-merge setup checks, not prerequisites that can be performed on
this branch before closing it. The pre-merge equivalents use disposable
worktrees in the offline tests; configuring the real app worktree remains a
separate owner instruction.

1. After merging, set up the worktrees as in `tasks/README.md`, "Working in
   parallel".
2. Run `uv run python scripts/validate_tasks.py --all-worktrees` from each
   folder.
3. In the `app` folder, say `Start the next task.`

Expected result: step 2 lists both worktrees with `track data` and `track app`.
Step 3 considers only `app` and `shared` backlog cards, never F4E-021 or F4E-033,
and claims through `scripts/claim_task.py`.

## Manual sad path

1. Create `.local/task-slot.lock` in the `data` folder with any content.
2. Run `uv run python scripts/claim_task.py F4E-033 --wait-seconds 1` there.
3. Delete the lock file.

Expected result: exit code 3, a `busy:` message naming the lock, the card still
in `tasks/backlog/`, and the lock file untouched until you delete it.

## Known limitations

- The rehearsal repository had no GitHub remote. A subsequent review exercised
  `gh pr list` against this repository: merged PR #50 was found for
  `feature/F6-017-correct-shipped-feature-guidance`, with base `main` and
  headRefOid `eee72be833d6085c867cf60801dfc4730a838eeb`; WF-007 returned no PR.
  This verifies the live query, not an end-to-end Start/Resume on GitHub.
- Park and Resume are agent procedures, not scripts. The rehearsal encodes the
  skill's steps in bash; only the claim is a single atomic program.
- Resume runs `git fetch origin` before its read-only preconditions rather than
  after them, so the checks read a fresh `origin/main`. Fetch updates Git
  metadata and remote-tracking refs, and may fetch tags; it leaves HEAD, the
  index, and working files unchanged.
- `--all-worktrees` finds slot violations after the fact; a hand move into
  `active/` still bypasses the lock.
- Card IDs cited in `# Cross-track impact` are found by the shape `ABC-123`, so a
  token such as `SHA-256` there would be reported as an unknown card.
- Area names outside the known tracks and neutral areas pass unchecked, as they
  did before.
- An orphaned lock blocks every claim until the owner deletes it.

## Follow-up review (2026-09-13)

- Re-ran the focused tests: 84 passed, including the concurrent claim races and
  the existing-lock check (busy, no card move, lock contents preserved).
- Re-ran the complete offline suite: 999 passed, 28 deselected, 7 warnings.
- Both task validators passed. There is still one unbound real worktree with
  WF-007 in review; the second worktree has not been configured.
- Ruff passed; mypy passed for all 70 source files; `git diff --check` passed.
- Tightened the agent's merged-branch rule: require a merged PR into `main`
  whose `headRefOid` matches local HEAD, and stop on an unavailable or
  inconclusive GitHub result. A historical PR sharing the branch name cannot
  approve newer local commits.
- Corrected the fetch description and the local `COMANDOS.md` descriptions of
  Start ordering and review fixes. That guide remains ignored by Git.
- No real task claim, Park/Resume, Git mutation, database operation, or worktree
  setup was performed during this follow-up review.
