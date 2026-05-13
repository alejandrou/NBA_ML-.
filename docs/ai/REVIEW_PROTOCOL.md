# Review Protocol

A task cannot be marked done until review passes.

Review result must be one of:

- `approved`
- `changes_requested`
- `blocked`

## Checklist

- Acceptance criteria met.
- Tests pass.
- Ruff passes.
- No live scraping.
- No network tests.
- No secrets.
- No `.env` committed.
- No `data/raw` committed.
- No new Peewee code.
- No `player_name` as stable key.
- No `TOT` treated as a real team.
- Parsers remain pure.
- DB changes have migration or migration note.
- Docs updated.
- Learning changelog updated.
- Feature-list updated.
- Progress history updated.
