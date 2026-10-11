# ADR-0005: Idempotency keys stored in the same transaction as the effect

- **Status:** Accepted
- **Date:** 2026-10-11

## Context

Networks fail. A client that sends `POST /v1/transfers` and gets a timeout can't know whether the transfer happened. Without idempotency, retrying risks a double transfer; not retrying risks a missing one.

Common designs store the key in a separate step before doing the work, with an `in_progress` state and recovery logic for keys left behind by crashes. That complexity exists because the work usually includes external calls. Ours doesn't: all side effects are database writes, and external notifications go through the outbox.

## Decision

- `Idempotency-Key` is **required** on every money-moving `POST`. The SDK generates a UUIDv4 if the caller doesn't pass one.
- Table `idempotency_keys`, primary key `(merchant_id, key)`, storing method, path, `request_hash` (SHA-256 of the canonical JSON body), response status and body, `created_at`, `expires_at` (24 h).
- The key is inserted **inside the same SERIALIZABLE transaction** as the money movement and its outbox event. Therefore:
  - If the transaction commits, the effect and the stored response exist together. A retry finds the key and replays the response.
  - If it rolls back, neither exists. A retry executes from scratch.
  - A concurrent request with the same key blocks on the unique index (`INSERT … ON CONFLICT DO NOTHING`) until the first commits. Postgres then aborts it with a serialization failure, because the conflicting row isn't in its snapshot. The [ADR-0004](0004-serializable-isolation-with-retries.md) retry loop re-runs it with a fresh snapshot, it finds the stored response, and replays it.
  - The wait is capped by `SET LOCAL lock_timeout = '2s'`; on timeout the API returns 409 `idempotency_key_in_use` and the client retries.
- Same key with a different `request_hash` → 422 `idempotency_key_reused`.
- 4xx business errors (e.g. `insufficient_funds`) are stored, so retries get the same answer. 5xx errors are not stored.
- An hourly job deletes expired keys. This is the only DELETE in the system and touches no ledger tables.

## Consequences

- Exactly one effect per key (PRD INV-7), without an `in_progress` state or crash-recovery code.
- Waiting requests briefly hold a database connection. Bounded by `lock_timeout` and the connection pool size.
- The rule "no external calls inside the transaction" becomes load-bearing and is called out in code review.

## Alternatives considered

- **Separate key-claim transaction with `in_progress` status (Stripe-style recovery points):** needed when work includes external API calls. Unnecessary here, and more code to get wrong.
- **Optional keys:** leaves the safe path opt-in. Rejected; the SDK removes the friction.
- **Redis for key storage:** a second datastore that can disagree with Postgres about whether the effect happened. Rejected.
