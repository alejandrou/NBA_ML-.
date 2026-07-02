# Architecture Invariants

These rules are stable unless the owner explicitly approves a change.

## Core Rules

- Do not write to the database unless the task explicitly asks for it.
- Do not run live scraping unless the owner explicitly requests it.
- Do not run backfills unless the owner explicitly requests it and the command
  uses the approved flags.
- Do not apply migrations unless the owner explicitly requests it.
- Do not run acquisition, refresh cache, or contact Basketball Reference
  outside the central rate-limited client.
- Keep raw scraped data separate from generated metrics.
- Do not treat `TOT` as a real team.
- Do not insert `TOT`, `2TM`, `3TM`, or `4TM` into `core.teams` or
  `core.team_seasons`.
- Do not insert synthetic team codes into `core.player_team_seasons`.
- Do not load synthetic team codes into `stats.player_team_season_*`.
- Do not load synthetic team codes into `stats.player_team_postseason_*`.
- `source_team_code` on `stats.player_season_*` is metadata only and must not
  be modeled as a foreign key.
- `source_team_code` on `stats.player_postseason_*` is metadata only and must
  not be modeled as a foreign key.
- Do not store generated or derived stats in `stats`.
- Keep regular-season and postseason stats in separate stat table families.
- Do not use `player_name` as a stable primary key.
- Do not add API, frontend, OVR, ranking, similarity, or ML work outside an
  approved phase.

## State And Scope Sources

- `tasks/feature-list.json` holds feature and task state.
- `docs/roadmap/CURRENT_PHASE.md` holds the current phase state.
- `progress/current.md` holds the operational summary for the active task.
- `progress/review.md` holds review state and findings.
- `specs/phases/*.md` are the phase contracts and scope gates.
- `specs/features/*.md` are the primary task contracts.

## Change Discipline

- Keep changes small and reviewable.
- Do not refactor unrelated code while solving a task.
- Do not broaden scope when the spec is already sufficient.
- Prefer documentation updates over code churn when the task is documentary.
- Preserve the existing separation between raw data, core identity, stats, and
  future generated features.
