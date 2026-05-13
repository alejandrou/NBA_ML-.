# Codex GitHub Action

Phase 1 adds a normal CI workflow only. It does not add an action that modifies
code automatically.

Future automation may ask Codex to review pull requests, but it must follow the
same repository rules:

- no live scraping;
- no secrets;
- no new Peewee;
- rate limiter respected;
- parser purity;
- docs updated;
- human review before merge.
