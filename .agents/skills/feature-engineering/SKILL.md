---
name: feature-engineering
description: Use when designing or implementing generated metrics, player OVR, rankings, similarity, or future ML features.
---

# Feature Engineering Skill

Rules:

- Generated metrics go in `features`.
- Official scraped stats stay in `stats`.
- Every formula must have `formula_version`.
- OVR v0 is simple and explainable.
- Do not apply era adjustment in v0.
- Support missing metrics.
- Do not penalize unavailable historical metrics automatically.
- Avoid data leakage.
- Add `as_of` fields when relevant.
