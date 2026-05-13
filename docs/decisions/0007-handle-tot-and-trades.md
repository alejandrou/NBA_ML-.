# ADR 0007 - Handle TOT and Trades

## Status

Accepted

## Context

Basketball Reference uses `TOT` for aggregate player-season rows after trades.

## Decision

Do not model `TOT` as a team. Treat it as an official player-season aggregate.

## Consequences

Future stats tables must separate player-season totals from player-team-season totals.

## Alternatives Considered

- Store `TOT` as a team: creates false team relationships.
- Drop `TOT`: loses official season aggregate data.
