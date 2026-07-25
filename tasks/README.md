# Tasks

The folder a card sits in **is** its status. Cards carry no `status` field.

```text
backlog/ → active/ → review/ → done/
```

- **`backlog/`** — planned, ready-to-start cards. This is the living roadmap; there is no separate roadmap document.
- **`active/`** — the one task being implemented. At most one file.
- **`review/`** — the one task awaiting your testing. At most one file.
- **`done/`** — completed cards, kept as lightweight history. Not loaded by default.

At most one card may exist across `active/` and `review/` combined.

`manifests/` is **not** part of the lifecycle. It holds approved live-acquisition
manifests consumed by the scraping code and its tests. Leave it alone.

Start a card with `Start the next task.` and see `AGENTS.md` for what that
authorizes. Only you can move a card from `review/` to `done/`.

`TEMPLATE.md` is the card format.
