# ADR-0003: Enforce double-entry in the database, not just the app

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

The core rule of double-entry bookkeeping is that every transaction's debits equal its credits (PRD INV-1). If only application code enforces it, a single bug, a hand-written migration or a future service that writes to the database directly can create or destroy money.

## Decision

The database itself rejects any transaction that breaks the rules:

1. **Zero sum.** A `CONSTRAINT TRIGGER … DEFERRABLE INITIALLY DEFERRED AFTER INSERT ON entries` checks, at commit time, that for the affected `transaction_id`:
   - `sum(debits) = sum(credits)`, and
   - there are at least two entries.

   Deferring the check to commit lets the app insert entries one at a time while still guaranteeing the final state balances.
2. **Single currency per transaction.** `ledger_transactions` has a `currency` column, and entries carry `currency` too, with composite foreign keys:
   - `(transaction_id, currency) → ledger_transactions(id, currency)`
   - `(account_id, currency) → accounts(id, currency)`

   An entry can therefore only post to an account in the transaction's currency. No trigger needed.
3. **No overdrafts.** `accounts` has `CHECK (allow_negative OR balance >= 0)`.

## Consequences

- An unbalanced or cross-currency transaction cannot be committed by any client, including a buggy one.
- The constraint trigger costs one aggregate query per entry at commit. With two to four entries per transaction this is negligible; it will show up in load tests if not.
- Integration tests must run against real Postgres (testcontainers), since these rules don't exist in mocks.

## Alternatives considered

- **App-level validation only:** rejected, see Context.
- **Store each transaction as one row with `debit_account`, `credit_account`, `amount`:** balanced by construction, but can't express a capture-with-release (four legs) as one transaction. Rejected.
