---
name: scraping-pipeline
description: Use when modifying, creating, or reviewing Basketball Reference scraping, parsing, caching, normalization, or loading workflows.
---

# Scraping Pipeline Skill

Use this skill for any scraper, parser, cache, normalizer, or loader work.

Rules:

- Plan URLs before requesting anything.
- Check HTML cache first.
- Use the central rate-limited client.
- Save raw HTML compressed as `.html.gz`.
- Parse from HTML only.
- Parsers must not touch DB.
- Parsers must not make network requests.
- Normalize separately.
- Validate before loading.
- Load with idempotent upsert.
- Do not run scraping in tests.
- Do not run scraping in CI.
- Use fixture HTML for tests.
- Respect 10 requests/minute default.
- Never exceed 20 requests/minute.
- The gap between requests is a hard floor, not a default: it lives in
  `MINIMUM_SCRAPER_DELAY_SECONDS`, the settings validator rejects anything
  under it, and the client clamps to it. Never weaken either.
- Stop on HTTP 429. The client does this by default; `max_429_retries` is an
  opt-in, not a fallback.
- Do not duplicate page downloads.
- A single team-season page should feed roster, totals, and advanced parsers when possible.
