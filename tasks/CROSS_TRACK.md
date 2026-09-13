# Cross-track handoffs

Changes that cross from one track to the other. The `data` track owns scraping,
schema, migrations, features, and ML; the `app` track owns the API and the web
frontend and only reads the database. `scripts/validate_tasks.py` checks this
file.

A card declares what it changes for the other track in its `# Cross-track impact`
section before it moves to `tasks/review/`. When that section is not `- None.`:

- **additive** — the other track can adopt the change when it chooses: a new
  column, table, or endpoint. The producing card creates a handoff card in the
  consumer track's `tasks/planning/` and records an entry under Open pointing at
  it. When `git-control` closes the handoff card, its entry moves to Log.
- **breaking** — the other track stops working until it adapts. That is `shared`
  work: the change ships in a `shared` card, which blocks both tracks, and its
  entry goes straight to Log, with target `none` or the card that adapts.

One entry per line, nothing else under the two sections:

```text
- YYYY-MM-DD | <SOURCE-ID> (<track>) -> <TARGET-ID> (<track>) | additive | <summary>
- YYYY-MM-DD | <SOURCE-ID> (shared) -> none | breaking | <summary>
```

Open holds only additive entries whose target card is not in `tasks/done/`.
Breaking entries appear only in Log. Every id must be a real card, written with
that card's own track.

## Open

## Log
