# Design Doc: Ledger v1

| | |
|---|---|
| **Status** | Accepted |
| **Author** | Gregory Temwa Odete |
| **Last updated** | 2026-10-11 |
| **Related** | [PRD](prd.md) · [ADRs](adr/README.md) · [Threat model](threat-model.md) · [Diagrams](diagrams/README.md) |

## 1. Context

The [PRD](prd.md) asks for a payments ledger that stays correct under concurrency, retries and crashes. This doc describes how. The core ideas fit in one sentence: **all money movement happens inside one SERIALIZABLE Postgres transaction that writes the entries, the idempotency record and the outbox event together**, and everything else (webhooks, reconciliation) reads from what that transaction committed.

## 2. System overview

See [C4 container diagram](diagrams/c4-container.md).

| Container | Tech | Responsibility |
|---|---|---|
| **API Gateway** | TypeScript, Fastify | Public edge. Authenticates API keys, rate-limits per key, validates requests, maps `Ledger-Version`, forwards to the core with a request ID and trace context. Holds no money state. |
| **Ledger Core** | Python, FastAPI, psycopg 3 | The only writer of ledger tables. Runs every money movement as one SERIALIZABLE transaction. |
| **Outbox Relay** | Python worker | Turns committed outbox events into webhook delivery rows and sends them, with signing, retries and dead-lettering. |
| **Reconciler** | Python CronJob | Read-only. Checks every invariant in the PRD and records a report. |
| **Dashboard** | Next.js | Merchant UI. Talks only to the public gateway, like any other client. |
| **SDK** | TypeScript | Typed client with automatic idempotency keys, retries and webhook verification. |
| **Postgres** | 17+ | Source of truth. |

The gateway and core are separate so that the public surface (auth, rate limits, versioning, docs) can evolve without touching the code that moves money, and so the core can stay small enough to reason about.

## 3. Data model

See [ERD](diagrams/erd.md). Key decisions:

- **Money is `bigint` minor units** ([ADR-0001](adr/0001-integer-minor-units.md)).
- **Entries are append-only** ([ADR-0002](adr/0002-immutable-entries.md)). The app's database role has no `UPDATE` or `DELETE` on `entries`, and a trigger rejects them anyway.
- **Double-entry is enforced by the database** ([ADR-0003](adr/0003-zero-sum-enforced-in-database.md)):
  - A deferred constraint trigger checks at commit that each transaction's debits equal its credits and that it has at least two entries.
  - Composite foreign keys `(account_id, currency) → accounts(id, currency)` and `(transaction_id, currency) → ledger_transactions(id, currency)` make it impossible to post an entry in the wrong currency.
- **Balances are cached on the account row** with `CHECK (allow_negative OR balance >= 0)`. The cache is updated in the same transaction as the entries, and the reconciler verifies it against the sum of entries (INV-3).
- **IDs** are UUIDv7 (time-ordered, good index locality), rendered in the API with Stripe-style prefixes: `acct_`, `txn_`, `hold_`, `evt_`, `we_` (webhook endpoint), `wd_` (webhook delivery).

### Account kinds

| Kind | Normal balance | Can go negative | Purpose |
|---|---|---|---|
| `user` | credit | no | Wallets the merchant creates for their users. |
| `external` | debit | yes | One per merchant and currency. The source of deposits and the sink of withdrawals. Its balance is the mirror image of all money inside the ledger. |
| `holds` | credit | no | One per merchant and currency. Holds funds that are authorized but not yet captured. |

Using a real `holds` account keeps holds inside double-entry: every balance is still explained by entries, and "available balance" needs no special calculation.

## 4. Core flows

### 4.1 Transfer
See [sequence diagram](diagrams/sequence-transfer.md).

Inside one SERIALIZABLE transaction:
1. Claim the idempotency key (§5).
2. Load both accounts; check same merchant, same currency, source ≠ destination, and sufficient funds.
3. Insert the `ledger_transactions` row and two `entries` (debit source, credit destination).
4. Update both cached balances.
5. Insert the `transfer.created` outbox event.
6. Store the response on the idempotency key.
7. Commit. The deferred zero-sum trigger runs here.

All business validation happens in step 2, before anything is written to the ledger. If it fails (e.g. `insufficient_funds`), the transaction stores the error response on the idempotency key and commits with no entries, so a retry gets the same answer. The `CHECK (allow_negative OR balance >= 0)` constraint is a backstop: if it ever fires, that is a bug, and it returns a 500 and raises an alert.

### 4.2 Holds
See [Hold state machine](diagrams/state-hold.md) and [ADR-0008](adr/0008-holds-as-state-machine.md).

| Operation | Entries | State change |
|---|---|---|
| Authorize | debit source, credit `holds` | → `authorized` |
| Capture `x` of `a` | debit `holds` `x`, credit destination `x`; if `x < a`, debit `holds` `a − x`, credit source `a − x` | `authorized` → `captured` |
| Void | debit `holds` `a`, credit source `a` | `authorized` → `voided` |
| Expire | same as void, run by a scheduled job | `authorized` → `expired` |

Every transition uses a conditional update (`WHERE status = 'authorized'`), so two concurrent captures can't both succeed even before SERIALIZABLE gets involved.

### 4.3 Refunds
A refund is a new transaction that reverses some or all of a transfer: debit the original destination, credit the original source. `ledger_transactions.reverses_transaction_id` links them. The sum of refunds is checked inside the same SERIALIZABLE transaction, so concurrent partial refunds can't over-refund (INV-8).

### 4.4 Events and webhooks
See [ADR-0006](adr/0006-transactional-outbox.md) and [ADR-0007](adr/0007-exactly-once-effects.md).

1. Money-moving transactions insert an `outbox_events` row in the same transaction. If the transaction commits, the event exists; if not, it doesn't (INV-6).
2. The relay claims unpublished events with `SELECT … FOR UPDATE SKIP LOCKED`, so several relay replicas can run without double-processing. For each subscribed endpoint it inserts a `webhook_deliveries` row with `ON CONFLICT (event_id, endpoint_id) DO NOTHING`, then marks the event published.
3. The dispatcher sends due deliveries:
   - Header `Ledger-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>`.
   - 10 s timeout. Any 2xx is success.
   - Retries with exponential backoff and jitter: about 1 m, 5 m, 30 m, 2 h, 6 h, 12 h, 24 h. After that the delivery is `dead` and can be replayed manually.
4. Consumers verify the signature, reject timestamps older than 5 minutes, and dedupe on the event `id`. That combination is what turns at-least-once delivery into exactly-once effects.

### 4.5 Reconciliation
A CronJob (every 15 minutes in production) runs read-only queries in a REPEATABLE READ snapshot and checks INV-1 to INV-8. It writes a `reconciliation_runs` row with the result, exports a `ledger_balance_drift` metric, and alerts if anything is non-zero. It never "fixes" data; a human follows the reconciliation-drift runbook instead (written in Week 9).

## 5. Idempotency

See [ADR-0005](adr/0005-idempotency-keys.md).

- Required on every money-moving `POST`. The SDK generates one automatically.
- Scoped by `(merchant_id, key)`. Stored with the method, path, a SHA-256 hash of the canonical request body, and the response.
- The key row is inserted **inside the same transaction** as the money movement, with `INSERT … ON CONFLICT DO NOTHING`. A concurrent request with the same key blocks on the unique index until the first commits. Under SERIALIZABLE, Postgres then aborts the waiter with a serialization failure (the row it conflicted with isn't in its snapshot); the retry loop re-runs it, it finds the stored response, and replays it. Exactly one effect, no `in_progress` state to clean up.
- A blocked waiter gives up after `lock_timeout` (2 s) and returns 409 `idempotency_key_in_use`; the client retries later and gets the replay.
- Same key, different body: 422 `idempotency_key_reused`.
- 5xx responses are never stored, so a retry after an infrastructure failure re-executes safely.

## 6. Concurrency model

See [ADR-0004](adr/0004-serializable-isolation-with-retries.md).

All writes run at **SERIALIZABLE**. Postgres then guarantees the result is the same as some serial order of transactions, which removes whole classes of bugs (lost updates, write skew on refund totals and hold captures) without hand-placed locks that someone will eventually forget.

The cost is serialization failures (SQLSTATE `40001`, plus deadlocks `40P01`). The core wraps each unit of work in a retry loop: up to 5 attempts, exponential backoff with full jitter, starting at 5 ms. The retry count is a metric. If attempts run out, the API returns 503 `ledger_contention`, which is retryable with the same idempotency key.

**Known risk: hot accounts.** Every deposit touches the merchant's `external` account row, so heavy deposit traffic serializes on it. Week 8 load tests will measure this. Mitigations, in order of preference: stop caching balances for `allow_negative` system accounts (derive them from entries), or shard the system account into N sub-accounts.

## 7. Failure analysis

What happens if a component dies at each point? Every row here becomes a test (unit, concurrency or chaos).

| # | Failure | Outcome | Why it's safe |
|---|---|---|---|
| F1 | Client's request never reaches the gateway | Nothing happened | Client retries with the same key. |
| F2 | Core crashes before commit | Transaction rolled back | Retry executes from scratch. |
| F3 | Core crashes **after commit, before responding** | Effect committed, client sees an error | Retry with the same key replays the stored response. No second effect. |
| F4 | Serialization failure | Transaction rolled back | Retried internally; if exhausted, 503, and the client retries. |
| F5 | Postgres restarts mid-transaction | Transaction rolled back | Same as F2. |
| F6 | Gateway ↔ core partition | Gateway returns 504 | The effect may or may not have happened; a retry with the key resolves it either way. |
| F7 | Relay crashes after inserting deliveries, before marking the event published | Event reprocessed | `ON CONFLICT DO NOTHING` prevents duplicate delivery rows. |
| F8 | Dispatcher crashes after the endpoint returned 2xx, before recording success | Webhook sent again | Consumer dedupes on event `id`. |
| F9 | Endpoint down for days | Delivery goes `dead` | Visible in the dashboard; manual replay. The event itself is never lost. |
| F10 | Two concurrent captures or refunds | One wins | Conditional updates plus SERIALIZABLE; the loser gets 409 or a clean business error. |

## 8. API design

- REST, JSON, resource-oriented URLs under `/v1`. OpenAPI 3.1 spec is generated from the gateway and published.
- Stripe-style error body:
  ```json
  { "error": { "type": "invalid_request_error", "code": "insufficient_funds",
               "message": "Account acct_… has insufficient funds.", "param": "amount",
               "request_id": "req_…" } }
  ```
- Cursor pagination (`limit`, `starting_after`), max 100 per page.
- Date-based API versions in a `Ledger-Version` header (e.g. `2026-10-01`), pinned per API key on first use.

| Resource | Endpoints |
|---|---|
| Accounts | `POST /v1/accounts`, `GET /v1/accounts/{id}`, `GET /v1/accounts`, `GET /v1/accounts/{id}/entries` |
| Transfers | `POST /v1/transfers`, `GET /v1/transfers/{id}`, `GET /v1/transfers` |
| Holds | `POST /v1/holds`, `POST /v1/holds/{id}/capture`, `POST /v1/holds/{id}/void`, `GET /v1/holds/{id}` |
| Refunds | `POST /v1/refunds`, `GET /v1/refunds/{id}` |
| Events | `GET /v1/events`, `GET /v1/events/{id}` |
| Webhooks | `POST /v1/webhook_endpoints`, `GET /v1/webhook_endpoints`, `DELETE /v1/webhook_endpoints/{id}`, `GET /v1/webhook_deliveries`, `POST /v1/webhook_deliveries/{id}/retry` |

## 9. Security

Summarized here; details in the [threat model](threat-model.md).

- API keys `sk_test_…` are high-entropy random secrets, stored as SHA-256 hashes with a visible prefix for identification.
- Every core query is scoped by `merchant_id`. Postgres row-level security is a planned defense-in-depth layer.
- The core is not publicly routable and only accepts requests carrying the gateway's internal service token.
- Separate database roles: `ledger_app` (no DDL, no UPDATE/DELETE on entries), `ledger_relay` (outbox and delivery tables only), `ledger_reconciler` (read-only), `ledger_migrator` (DDL, used only by migrations).
- Webhook URLs must be HTTPS in production and must not resolve to private, loopback or link-local addresses, checked at registration and again at send time to block DNS rebinding.

## 10. Observability

- OpenTelemetry traces from gateway → core → Postgres, with `request_id` and `merchant_id` as attributes.
- RED metrics per endpoint, plus `ledger_serialization_retries_total`, `ledger_outbox_lag_seconds`, `ledger_webhook_delivery_attempts_total`, `ledger_balance_drift`.
- Structured JSON logs; API keys and webhook secrets are redacted.
- SLOs: transfer availability 99.5%, transfer p99 < 150 ms, webhook delivery within 60 s for 99% of events.

## 11. Testing strategy

| Layer | Tooling | What it proves |
|---|---|---|
| Unit | pytest, Vitest | Pure logic: money math, signing, state transitions. |
| Property-based | Hypothesis stateful testing | Random operation sequences against an in-memory model never break an invariant. |
| Integration | pytest + testcontainers (real Postgres) | SQL, constraints and triggers behave as designed. |
| Concurrency | asyncio fan-out against real Postgres | Parallel transfers, same-key races, concurrent refunds and captures. |
| Contract | OpenAPI diff in CI | Gateway and core can't drift apart. |
| E2E | Playwright | Dashboard user journeys. |
| Load | k6 | Latency and throughput targets. |
| Chaos | Chaos Mesh, Toxiproxy on kind | Failure rows F2–F9 under real load, followed by an invariant check. |

## 12. Deployment

- **Local:** `docker compose` for day-to-day work; k3d for Kubernetes and chaos.
- **CI:** GitHub Actions; kind for the nightly chaos run.
- **Production demo:** gateway and dashboard on Vercel; core, relay and Postgres on Heroku; reconciliation via Heroku Scheduler.
- **One-off:** an Azure AKS chaos run provisioned with Terraform and destroyed the same day.

## 13. Alternatives considered

| Alternative | Why not |
|---|---|
| `SELECT … FOR UPDATE` row locks at READ COMMITTED | Works for simple transfers, but every new invariant (refund totals, hold captures) needs someone to remember the right lock in the right order. SERIALIZABLE makes the database do it. See ADR-0004. |
| Event sourcing with balances as projections | More moving parts for the same guarantees. Double-entry already is an append-only log. |
| A message broker (Kafka, RabbitMQ) for events | Adds a second system that has to agree with Postgres. The outbox gets the same guarantee with one database. |
| TigerBeetle as the ledger engine | Purpose-built and excellent, but the point of this project is to show the design, not delegate it. |
| Floats or `numeric` for money | Floats lose precision; `numeric` is correct but slower and invites fractional minor units. |

## 14. Open questions

1. Should hold expiry run in the reconciler's CronJob or its own job? Leaning towards its own, so a slow reconciliation never delays releasing funds.
2. Row-level security now or later? Leaning later (Week 9), once query patterns are stable.
