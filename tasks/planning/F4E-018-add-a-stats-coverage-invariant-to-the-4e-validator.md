---
id: F4E-018
title: Add a stats coverage invariant to the Phase 4E validator
areas:
  - planning
  - data-quality
  - database-read
  - testing
priority: 65
depends_on:
  - F4E-017
read:
  - src/nba_data/validation/official_stats.py
  - src/nba_data/validation/offline_database.py
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
validation: []
critical_actions: []
---

# Goal

Make the archive's row loss visible. Add a permanent invariant that asserts
`core.player_seasons` and the `stats.*` families agree with the cache-derived
coverage classification from F4E-017, so a dropped row fails validation instead
of disappearing silently.

# Evidence and current state

## Nothing checks stats coverage today

[`_orphan_issues`](../../src/nba_data/validation/offline_database.py#L296) — the Phase
4D core validator — checks only core-to-core parentage:
`orphan_team_aliases_team`, `orphan_team_seasons_team`,
`orphan_team_seasons_season`, `orphan_player_seasons_player`, and the rest. It
**never reads any `stats.*` table**. So a `core.player_seasons` row with no
corresponding stats rows is not an orphan by its definition, and passes.

The Phase 4E validator in
[official_stats.py](../../src/nba_data/validation/official_stats.py) checks table and
column presence, constraints, duplicate grains, generated-metric naming, and the
backfill report — but has no rule of the form "this player-season should have
stats and does not."

The consequence is the audit's central finding: rows are dropped and the loss is
invisible at query time. F4E-013 explains one mechanism (a season resolving to
1900 never gets a `core.seasons` row, so `_resolve_player_season_id` fails
silently); this card ensures the *next* mechanism is caught without another
audit.

## Why it belongs in the Phase 4E validator

The invariant reads `stats.*`. The Phase 4D core validator deliberately does not,
and giving it a stats dependency would blur the phase boundary that
`OFFICIAL_STATS_SCHEMA.md` maintains. It belongs beside the other Phase 4E
reflection checks.

## Why this is in planning and not backlog

The artifact this card consumes is not specified well enough to build against.
Two concrete gaps, both of which must close in F4E-017 first:

1. **One mutually exclusive class per season loses information this card needs.**
   An earlier revision of F4E-017 assigned each season exactly one of four
   classes. Most playoff seasons carry both regular-season and postseason stats,
   so a season labelled "regular-season present" could not also express its
   expected postseason rows — and the postseason rule below would have nothing to
   check against. F4E-017 now records four **independent** dimensions instead.
   This card depends on that revision.
2. **The team-stint rule needs exact natural keys.** Checking stint coverage
   requires the artifact to enumerate `(player_id, season_year, team_code, table)`,
   not a per-season summary. Equally, the artifact's path, `schema_version`, cache
   digest, freshness rule, and the CLI option that supplies it are all still open
   in F4E-017.
3. **F4E-017 may not supply stint expectations at all.** Regular-season stints
   originate on team pages, which that card does not currently read; whether it
   traverses them is one of its open questions. If the answer is no, the stint
   rule below has no input and must be dropped rather than silently pass. This
   card cannot specify a rule over a dimension whose existence is undecided.

This card returns to backlog when F4E-017's open questions are answered, and
must adopt the same answers rather than inventing a parallel interface.

# Human decisions or resources

- [x] The invariant applies no numeric tolerance. A missing row is a failure
      regardless of how few there are.
- [ ] Adopt F4E-017's resolved artifact interface verbatim — path, schema
      version, digest, and the required-versus-optional CLI behavior. Proposal
      carried from F4E-017: when no artifact is supplied, emit a named
      "coverage not evaluated" issue and continue, so a missing artifact can
      never look like a pass.
- [ ] **Resolve how freshness is checked without requiring the cache.** Earlier
      revisions of this card asserted both that the cache digest is recomputed
      and must match, and that validation must not require the cache. Those
      cannot both hold: recomputing a digest over the cache requires the cache.
      Proposal — verify the digest **when a cache path is supplied**, failing on
      mismatch; when it is not, consume the artifact on trust and emit a named
      `coverage_freshness_unverified` issue. Validation then still runs against a
      database-only deployment, and an unverified artifact is never silently
      treated as a verified one. Confirm or replace this; do not leave both
      statements standing.

# Acceptance criteria

- A new check in `run_official_stats_validation` compares persisted coverage
  against the F4E-017 artifact and emits issues with stable codes.
- **Separate rules**, each reported distinctly rather than collapsed into one
  count, and each reading its own dimension of the artifact:
  - regular-season aggregate coverage, keyed `(player_id, season_year, table)`,
  - postseason aggregate coverage, keyed the same way and evaluated
    **independently** of whether regular-season stats exist,
  - team-stint coverage, keyed `(player_id, season_year, team_code, table)` —
    only if F4E-017 resolves to supply this dimension; if it does not, this rule
    is dropped and its absence is stated, not left to pass vacuously,
  - did-not-play seasons, which must have no stats rows **of the season type the
    marker applies to**. A regular-season placeholder prohibits regular-season
    rows and says nothing about postseason rows.
- **Each rule compares set equality, not a count or a subset test.** Keys in the
  artifact and absent from the database are *missing*; keys in the database and
  absent from the artifact are *unexpected*. Both are failures and both are
  reported under their own code. A subset test would pass an archive that
  invented rows, and a count comparison would pass one that lost a row and gained
  a different one.
- The artifact's `schema_version` is validated; an unknown version is a named
  issue and the check does not run on a guess.
- Any season recorded **unexplained** by F4E-017 fails.
- The nine genuinely postseason-only seasons pass, and `milleol01` 2003-04 —
  which carries a placeholder *and* real regular-season stats — fails against
  today's database and passes once F4E-022 has landed and the archive is rebuilt.
- **No tolerance parameter and no allowlist** live in this check; the only
  permitted exceptions are F4E-017's schema-validated exceptions file entries,
  and each one applied is named in the report.
- Issue context enumerates the offending natural keys, capped for report size,
  with a total count alongside — a bare count is not actionable.
- `validate official-stats` exits non-zero when the invariant fails.
- Tests cover: a fully covered archive passing; a dropped regular-season row
  failing; a dropped postseason row failing; a valid postseason-only season
  passing; a regular-season did-not-play season **with postseason rows** passing,
  and the same season with stray *regular-season* rows failing; an unexpected key
  with no artifact entry failing; and an unexplained season failing.

# Scope

- `src/nba_data/validation/official_stats.py` — the new check, its issue codes,
  and the validation summary counters.
- `src/nba_data/cli/main.py` — the `validate official-stats` option that supplies
  the coverage artifact, its exit-code branch, and the not-evaluated path when no
  artifact is given. Without this the check has no way to receive its input.
- The classification artifact reader, shared with F4E-017: schema-version check,
  digest recomputation, and the typed entry shape.
- `tests/unit/` for the invariant, including the schema-version and stale-digest
  paths.

# Out of scope

`src/nba_data/validation/offline_database.py`, which stays core-only. Repairing
any row the invariant flags — that is the future rebuild-and-diff and in-place
remediation cards. Building the classification itself, which is F4E-017. The
report reconciliation, which is F4E-016.

# Impact

`validate official-stats` gains a failure mode it did not have, so the command
will start failing against the current database until the archive is repaired.
That is the intended outcome: the invariant is what makes the defect visible.
The validation report shape gains counters, so anything parsing it must tolerate
new keys.

# Implementation notes

Expect this to fail on first run against the existing target database. Do not
weaken the rule to make it pass; record the failure as the baseline that the
rebuild-and-diff card diffs against.

Keep the check reflection-driven and read-only, matching the surrounding Phase 4E
checks. It must not write, and it must not *require* the cache at validation
time — consume the JSON classification artifact F4E-017 produces. The digest
question above is what makes "not required" and "verified fresh" compatible:
the cache is optional input that upgrades the check, never a precondition for
running it.

The set-equality requirement is the one most likely to be softened during
implementation, because the *unexpected keys* half will fire on the current
database before the *missing keys* half is satisfied. Resist that. An archive
that contains rows the cache does not justify is exactly as wrong as one missing
rows the cache does justify, and the audit that prompted this work found both
shapes.

# Durable knowledge updates

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — record the coverage invariant as
  a standing guarantee of the stats schema, and that Phase 4D validation remains
  core-only by design.
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — document the new failure
  mode and what to do about it.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
