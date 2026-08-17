---
id: F4E-027
title: Extract the shared player-page backfill helpers into their own module
areas:
  - scraping
  - testing
priority: 40
depends_on:
  - F4E-022
read:
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
validation:
  - uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Give the two player-page backfills a shared module for the cache discovery and
input validation they both use, so the postseason backfill stops importing
private names out of the regular-season one.

# Evidence and current state

`src/nba_data/scraping/offline_player_postseason_stats_backfill.py:12-19` imports
six names from its sibling, **three of them private**:

```python
from nba_data.scraping.offline_player_stats_backfill import (
    PlayerCacheDiscoveryStatus,
    _discover_player_cache_entries,
    _required_html,
    _validate_inputs,
    discovery_status_for,
    resolve_player_cache_root,
)
```

The reuse is right — both backfills discover the same cache files, accept the
same `limit` / `player` / `start_year` / `end_year` filters, and read the same
gzip payloads. What is wrong is where the shared code lives. The leading
underscore says "private to this module" and the import says otherwise, so the
regular-season module cannot change any of the three without silently changing
the postseason one, and neither file's name suggests it owns the cache-discovery
contract.

The discovery half is also where `F4E-012` found a real defect (the cache
discovery contract), which is the concrete reason this code deserves a named home
and its own tests rather than being a private detail of whichever module happened
to need it first.

# Human decisions or resources

- None.

# Acceptance criteria

- A new module — `src/nba_data/scraping/player_page_backfill_common.py` or a name
  that reads as well — owns `PlayerCacheDiscoveryStatus`,
  `PlayerCacheRootNotFoundError`, `resolve_player_cache_root`,
  `discovery_status_for`, the cache-file pattern, the discovery function, the
  gzip read helper, and the shared input validation.
- The names it exports are **public**: no caller imports an underscore-prefixed
  name across module boundaries anywhere in `src/`. A grep for
  `import.*_discover_player_cache_entries` and its two siblings returns only
  their definition module.
- Both backfill modules import from the new module. Neither imports from the
  other.
- Behavior is **byte-identical**: the same files are discovered in the same order,
  the same `source_url` is derived, the same validation errors are raised with the
  same messages, and the same `discovery_status` values are reported. This is a
  move, not a redesign.
- The parser-version constants stay where they are. Each backfill owns its own
  lineage label and its own comment history — `player-page-parser-v4` and
  `player-page-postseason-parser-v4` are not shared state.
- The report dataclasses stay in their own modules. They differ by design; only
  discovery and validation are shared.
- Tests covering discovery and validation move to a module named after the new
  home, and the two backfill test modules keep only what is specific to them.
  Total assertions do not shrink.
- The full offline suite passes with the same test count.

# Scope

`src/nba_data/scraping/offline_player_stats_backfill.py`,
`src/nba_data/scraping/offline_player_postseason_stats_backfill.py`, the new
module, and the corresponding test modules. Import lines in
`src/nba_data/cli/main.py:27-34` if the moved names are referenced there.

# Out of scope

`offline_stats_backfill.py` (team-season), which discovers a different cache
shape — folding it in is a larger question and this card does not open it. The
report shapes and their `to_dict` duplication: `F4E-016` owns report
consolidation. Any change to normalization, selection, loading, or lineage. Any
new behavior at all.

# Impact

Two modules and their tests. No CLI surface, no report field, no database write,
and no parser version changes. `docs/architecture/IMPACT_MAP.md` may name these
modules and should still be accurate afterwards.

# Implementation notes

**Do not start before `F4E-022` is in `tasks/done/`.** It edits both files —
including the exact import block above and both parser-version constants — and
this card would conflict with it line for line.

Move first, then adjust. A commit that only relocates code, with the tests still
passing, is much easier to review than one that relocates and improves at once.
If something looks worth improving on the way past, note it and leave it.

`F4E-012` fixed the cache discovery contract and `F4E-022` changed selection
around it; read those cards' `# Review evidence` in `tasks/done/` before touching
the discovery helper, so a behavior they established is not undone by a tidy-up.

# Durable knowledge updates

- `docs/architecture/IMPACT_MAP.md` — update the player-page backfill entry to
  name the module that now owns cache discovery.

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
