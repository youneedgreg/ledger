# ADR-0004: SERIALIZABLE isolation with bounded, jittered retries

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

Concurrent requests touch the same rows: two transfers from one account, two partial refunds of one transfer, a capture racing a void. At Postgres's default READ COMMITTED level these produce lost updates and write skew, e.g. two refunds that each check "total refunded + mine ≤ amount" against the same stale total and both succeed.

The classic fix is `SELECT … FOR UPDATE` on the right rows in a consistent order. That works, but every new invariant needs someone to remember which rows to lock and in what order, and a forgotten lock is a silent money bug.

## Decision

- Every write transaction in the core runs at `SERIALIZABLE`.
- A single `run_in_transaction` helper owns the retry policy:
  - Retries on SQLSTATE `40001` (serialization failure) and `40P01` (deadlock).
  - Up to 5 attempts, exponential backoff with full jitter, base 5 ms, cap 200 ms.
  - The whole unit of work is re-run from the start, including reads, so decisions are never made on stale data.
  - Emits `ledger_serialization_retries_total` and a span event per retry.
- If attempts run out, the API returns 503 with code `ledger_contention`. It is safe to retry with the same idempotency key.
- Conditional updates (`UPDATE holds … WHERE status = 'authorized'`) are still used for state transitions, as a cheap first line of defence and to give clear errors.
- Read-only endpoints use READ COMMITTED; the reconciler uses REPEATABLE READ for a consistent snapshot.

## Consequences

- Correctness doesn't depend on getting lock order right, so new features are safer to add.
- Contended workloads see retries and higher tail latency. Hot accounts (see design doc §6) are the main risk and are measured in Week 8.
- Transactions must stay short and must never call external services, or retries become expensive and unsafe. Webhooks go through the outbox for exactly this reason.

## Alternatives considered

- **READ COMMITTED + `FOR UPDATE`:** faster under contention but fragile to maintain. Kept as a fallback if load tests show SERIALIZABLE can't meet the latency target.
- **Optimistic concurrency with a `version` column:** solves lost updates on one row but not write skew across rows (refund totals). Rejected as the primary mechanism.
- **Single-writer queue per account:** strong, but adds infrastructure and latency. Rejected for v1.
