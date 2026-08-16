---
id: F4E-020
title: Decide the fate of the raw schema
areas:
  - planning
  - data-quality
  - database-schema
  - scraping
  - documentation
priority: 40
depends_on: []
read:
  - src/nba_data/db/models/raw.py
  - src/nba_data/scraping/cache.py
  - docs/architecture/IMPACT_MAP.md
  - docs/decisions/0003-cache-raw-html.md
validation: []
critical_actions:
  - Applying any migration from this card to a persistent or shared database requires explicit owner approval; authoring a reversible revision does not.
  - Populating raw.raw_pages requires a cache-read backfill against real data and explicit owner approval.
  - Never edit migration 0001_initial_raw_core.py; supersede it with a new reversible revision that drops what 0001 created.
---

# Goal

Decide what the three `raw` schema tables are for — populate them, drop them, or
document them as reserved. The decision is **not uniform across the three**, and
that asymmetry is the substance of the question.

# Evidence and current state

## All three tables exist and none is ever written

[`src/nba_data/db/models/raw.py`](../../src/nba_data/db/models/raw.py) declares
`raw.raw_pages`, `raw.scraper_runs`, and `raw.scraper_requests`, all created by
migration `0001`. Searching `src/nba_data/` for `RawPage`, `ScraperRun`, and
`ScraperRequest` finds **no writer and no reader outside the model module and
the package `__init__`**. Three tables, fully modeled, entirely inert.

## The asymmetry: one is recoverable, two are not

**`raw.raw_pages` is partly recoverable.** Its columns are `url`, `source`,
`cache_path`, `content_hash`, `http_status`, `fetched_at`, `parser_version`,
`status`, `error`. The 3,326 files in `data/raw/html/basketball-reference/`
carry the path and the content, so `cache_path` and `content_hash` are free.

**`url` is not recovered by inverting the filename.**
[`cache.py:41-44`](../../src/nba_data/scraping/cache.py#L41-L44) builds the name
from a slug and `digest[:16]` — a **truncated** SHA-256 of the URL:

```python
digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
slug = _safe_part(f"{parsed.path}-{parsed.query}".strip("-"))[:80]
candidate = self.root_dir / host_dir / f"{slug}-{digest[:16]}.html.gz"
```

A truncated hash is not reversible, and the slug is lossy too — `_safe_part`
lowercases and collapses every non-alphanumeric run to `-`. URLs are
reconstructible today only because every cached file matches one of two known
templates, `/teams/{CODE}/{YEAR}.html` and `/players/{i}/{id}.html`, so the slug
can be re-expanded by rule and the digest used to *confirm* the guess. That works,
but it is template-matching, not decoding, and it silently fails for any file
that does not match a known template. A backfill must verify each reconstructed
URL by recomputing the digest, and must report — not skip — any file it cannot
reconstruct.

`http_status` and `fetched_at` are not recoverable at all; see question 2.

**`raw.scraper_runs` and `raw.scraper_requests` are not.** They record what
happened during a fetch: run grouping, `run_type`, `config_json`, per-request
`http_status`, `cache_hit`, `requested_at`, and error text. None of that
survives in the cache — the files are the *outcome*, not the transcript. For
scrapes already performed, the information is simply gone. Any backfill would be
manufacturing plausible values, which is worse than an empty table because it
looks like provenance.

## The proposed split

- **`raw_pages`** — recoverable, but the filesystem cache plus the JSON reports
  in `reports/` remain the source of truth for v1. **Do not populate now.** The
  open question is whether it earns population later or is dropped.
- **`scraper_runs` / `scraper_requests`** — **never backfill for past scrapes**.
  Populate going forward, when the live scraper next runs, or drop them.

# Human decisions or resources

- [ ] **1. Does `raw.raw_pages` get populated at all in v1?** It is recoverable
      from cache, but nothing reads it and the cache already answers every
      question it would. Populate, drop, or document as reserved.
- [ ] **2. If it is populated, what is the rule for `http_status` and
      `fetched_at`** on rows reconstructed from cache — NULL, filesystem mtime,
      or a sentinel? A NULL means "unknown"; an mtime means "when this file was
      written", which is not when the page was fetched. Choose one and say so in
      the schema documentation.

      **Note that "unknown" is not the default and must be written
      deliberately.** `fetched_at` carries `server_default=func.now()` at
      [raw.py:26-28](../../src/nba_data/db/models/raw.py#L26-L28), so an insert
      that simply omits the column gets the time of the *backfill* — the most
      misleading of the three options, and the one a naive implementation
      produces silently. Choosing NULL therefore means passing NULL explicitly,
      or dropping the server default in the same revision. Say which.
- [ ] **3. Do `scraper_runs` / `scraper_requests` stay?** Confirm they are never
      backfilled for past scrapes. Then decide: keep them and wire the live
      scraper to write them going forward, or drop both tables, accepting that
      run provenance starts whenever it is reinstated. A drop is authored as a
      **new** Alembic revision that reverses `0001`; migration `0001` itself is
      never edited. An earlier revision of this card said "drop both tables and
      their migration", which would have rewritten applied history.
- [ ] **4. If they stay unpopulated, where is that recorded** so the next audit
      does not re-file them as missing data? A comment in the model is not
      enough; this needs a line in a durable document.
- [ ] **5. Does dropping anything need a migration and a `pg_dump` first?** The
      tables are empty today, so a drop is cheap — but confirm emptiness against
      the real database before assuming it.

# Acceptance criteria

To be finalised once the decisions above are made. At minimum:

- Each of the three tables has a stated disposition — populated, reserved, or
  dropped — recorded in a durable document rather than inferred from the model.
- If anything is dropped, a **new** Alembic revision does it and the models go
  with it. Migration `0001_initial_raw_core.py` is left untouched, and the new
  revision has a working `downgrade` that recreates what it dropped.
- If `raw_pages` is populated, the `fetched_at` rule from question 2 is
  implemented explicitly rather than left to the server default, with a test
  asserting a reconstructed row carries the intended value.
- If anything is reserved, the reservation states what would populate it and
  when, so it is a plan rather than an accident.
- `docs/decisions/0003-cache-raw-html.md` reflects the outcome, since it is the
  ADR that made the filesystem cache authoritative.

# Scope

To be defined. Expected to touch `src/nba_data/db/models/raw.py`,
`docs/architecture/IMPACT_MAP.md`, `docs/decisions/0003-cache-raw-html.md`, and —
only if something is dropped or populated — an Alembic migration and a loader.

# Out of scope

Changing the filesystem cache layout, which `IMPACT_MAP.md` protects. Live
scraping. Any decision about `core` or `stats` schemas.

# Impact

Potentially a schema migration and the scraper's write path. If `raw_pages` is
populated, the future rebuild-and-diff card must populate it too, or the diff
will show a
spurious difference.

# Implementation notes

Answer question 3 first. If the run tables are dropped, question 1 gets simpler,
because `raw_pages` alone is a cache index rather than a provenance schema, and
the case for it is weaker.

Resist the symmetry instinct. These three tables were designed together, but
they are not recoverable together, and treating them uniformly is how a
fabricated `fetched_at` ends up in a provenance table.

# Durable knowledge updates

- `docs/decisions/0003-cache-raw-html.md` — record the raw-schema disposition.
- `docs/architecture/IMPACT_MAP.md` — record whether the database indexes the
  cache or the cache stands alone.

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
