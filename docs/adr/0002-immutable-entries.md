# ADR-0002: Entries are append-only; corrections are reversing transactions

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

A ledger's value is that every balance can be explained. If entries can be edited or deleted, history can be rewritten, accidentally or maliciously, and no audit is trustworthy.

## Decision

- `entries` and `ledger_transactions` are insert-only.
- Refunds, voids and corrections are new transactions that reverse the original, linked with `reverses_transaction_id`.
- Enforced in three layers:
  1. The application never issues `UPDATE` or `DELETE` on these tables.
  2. The `ledger_app` database role is not granted `UPDATE` or `DELETE` on them.
  3. A `BEFORE UPDATE OR DELETE` trigger raises an exception, so even a superuser mistake fails loudly.

## Consequences

- Full audit trail: any balance at any point in time can be recomputed from entries.
- Tables only grow. Partitioning `entries` by month is the planned answer if size ever matters; for this project it won't.
- Mutable state (hold status, cached balances, delivery status) lives in separate tables whose correctness the reconciler verifies against the entries.

## Alternatives considered

- **Soft deletes (`deleted_at`):** still lets history change meaning. Rejected.
- **Application-only enforcement:** one bad migration or manual query away from breaking. Rejected in favour of defence in depth.
