---
name: data-quality
description: Use when adding validations, tests, checks, fixtures, or data quality gates for scraped NBA data.
---

# Data Quality Skill

Check:

- expected row counts when known;
- nullability;
- numeric ranges;
- duplicate keys;
- natural keys;
- old seasons with missing columns;
- missing because unavailable vs not scraped vs parse error;
- `TOT` is not a real team;
- no network calls in tests;
- no generated metrics mixed with official stats.
