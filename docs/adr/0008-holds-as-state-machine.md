# ADR-0008: Holds as an explicit state machine backed by a holds account

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

A hold (authorization) reserves funds for a later capture, like a hotel or fuel-pump pre-authorization. Two common designs:

1. A "reserved" amount column subtracted from the balance to get "available". Simple, but reserved money isn't in the ledger, so INV-3 ("balance = sum of entries") no longer explains available balance.
2. Move the funds into a dedicated account. Everything stays double-entry.

Holds also have a lifecycle with races: capture vs. void, capture vs. expiry, two captures.

## Decision

- Each merchant has a `holds` system account per currency.
- Holds move through an explicit state machine (see [diagram](../diagrams/state-hold.md)):

  | From | Event | To | Entries |
  |---|---|---|---|
  | — | authorize(a) | `authorized` | source → holds: a |
  | `authorized` | capture(x ≤ a) | `captured` | holds → destination: x; holds → source: a − x (if > 0) |
  | `authorized` | void | `voided` | holds → source: a |
  | `authorized` | expire (job, at `expires_at`) | `expired` | holds → source: a |

- `captured`, `voided` and `expired` are terminal. One capture per hold.
- Each transition is a conditional update `UPDATE holds SET status = :to WHERE id = :id AND status = 'authorized'`, inside the same SERIALIZABLE transaction as the entries. Zero rows updated means another transition won; the API returns 409 `hold_not_authorized` with the current status.
- `expires_at` defaults to 7 days, maximum 30 days.
- Allowed transitions live in one table in code, and a property test checks that no sequence of operations reaches an undefined transition.

## Consequences

- Available balance is just the account balance; no special maths anywhere.
- The `holds` account balance always equals the sum of open (`authorized`) holds, which the reconciler checks.
- A hold that is never captured, voided or expired would lock funds forever, so the expiry job is part of the correctness story and is monitored.

## Alternatives considered

- **Reserved-amount column:** rejected, see Context.
- **Multiple partial captures:** useful for split shipments, but complicates the state machine. Deferred.
