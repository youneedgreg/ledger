# ADR-0001: Store money as integer minor units

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

Money must add up exactly. Binary floating point can't represent most decimal fractions (`0.1 + 0.2 != 0.3`), and rounding errors compound across millions of entries. Postgres `numeric` is exact but allows fractional minor units (half a cent) that have no meaning, is slower to aggregate, and maps awkwardly to JSON and JavaScript.

## Decision

- Every amount is a `bigint` in the currency's minor unit (cents for USD, tambala for MWK).
- The API accepts and returns amounts as JSON integers plus an ISO 4217 `currency` code, e.g. `{"amount": 1050, "currency": "usd"}` for $10.50.
- `CHECK (amount > 0)` on entries; direction is a separate `debit`/`credit` column.
- Zero-decimal currencies (e.g. JPY) use the major unit as the minor unit. The minor-unit exponent comes from a static ISO 4217 table, used only for display.
- The SDK types amounts as `number` and rejects non-integers and values above `Number.MAX_SAFE_INTEGER` (≈ 9 × 10¹⁵).

## Consequences

- Sums are exact and fast.
- Clients must format amounts for display themselves (the dashboard does this with the exponent table).
- `bigint` caps a single balance at about 9.2 × 10¹⁸ minor units, far beyond anything this system will see.

## Alternatives considered

- **Floats:** rejected, inexact.
- **`numeric(19,4)`:** exact, but permits meaningless fractions and is slower. Rejected.
- **Amounts as strings in JSON:** avoids JS precision limits but is clumsier for every client. Safe-integer validation in the SDK is enough at our scale.
