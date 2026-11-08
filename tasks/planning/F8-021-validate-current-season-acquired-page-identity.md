---
id: F8-021
title: Validate current-season acquired page identity
track: data
areas:
  - planning
  - scraping
  - data-quality
  - testing
priority: 86
depends_on:
  - F8-013
read:
  - src/nba_data/scraping/current_season_acquisition.py
  - src/nba_data/scraping/cache_writer.py
  - src/nba_data/scraping/parsers/box_score.py
  - src/nba_data/scraping/parsers/team_season.py
validation: []
critical_actions:
  - None. Offline fixtures only; no live requests or deletion or replacement of real cache files.
---

# Goal

Prevent an HTTP 200 error or challenge page from satisfying current-season
team-page or box-score coverage permanently.

# Evidence and current state

- F8-013 checks only the HTML document prefix for team pages and box scores.
  A 200 HTML error page can be cached and reported as fetched successfully.
- Team pages with any snapshot are never requested again; archived box scores
  are also skipped. A bad response can therefore prevent automatic recovery.
- F8-013 review added schedule parsing and season-date checks before publishing
  schedule snapshots, but team and box-score content needs its own contract.

# Human decisions or resources

- Determine minimal reliable team/season and game identity evidence from
  existing cached fixtures and parser contracts. Optional stats must not become
  prerequisites for acquiring otherwise valid raw pages.
- Specify a non-destructive diagnostic and recovery procedure for existing bad
  cache entries. Never silently overwrite immutable archives.

# Acceptance criteria

- Specify offline validation commands before promotion.
- Team and box-score responses are checked for page type and requested identity
  before publication; error pages and wrong-identity responses stop the run.
- Tests use realistic cached fixture bodies for successful acquisitions and
  cover HTTP 200 error HTML, wrong identity, and successful rerun after refusal.
- Approval flags, pacing, ceilings, and cache immutability remain intact.

# Scope

Current-season acquisition content validation, offline tests, and recovery docs.
No changes to older acquisition commands, live requests, or real cache cleanup.

# Cross-track impact

- None.
