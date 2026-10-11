# Product Requirements: Ledger

| | |
|---|---|
| **Status** | Accepted |
| **Owner** | Gregory Temwa Odete |
| **Last updated** | 2026-10-11 |
| **Related** | [Design doc](design-doc.md) · [ADRs](adr/README.md) · [Threat model](threat-model.md) |

## 1. Problem

Every product that moves money (wallets, marketplaces, payroll, lending) needs a ledger. Most teams start with a `balance` column and an `UPDATE balance = balance - :amount`. That works until it doesn't:

- Two concurrent requests read the same balance and both succeed, so money is spent twice.
- A client times out and retries, and the transfer runs twice.
- The process crashes after the database commit but before a webhook is sent, so downstream systems never hear about it.
- Nobody can answer "why is this balance what it is?" because history was overwritten.

Ledger is a payments ledger service with a Stripe-style API that makes these failures impossible by construction and proves it with tests.

## 2. Goals

1. **Correctness first.** Money is never created, destroyed or double-spent, under any interleaving of concurrent requests, retries or crashes.
2. **Auditability.** Every balance can be explained by an immutable list of entries.
3. **Safe retries.** Any money-moving request can be retried any number of times with the same idempotency key and produce exactly one effect.
4. **Reliable notifications.** Every committed money movement produces exactly one event, delivered to subscribers at least once, with a signature they can verify.
5. **Developer experience.** A developer can install the SDK and move money in a sandbox in under 2 minutes.

## 3. Non-goals (v1)

- Real money, card networks, bank rails or payouts to real accounts.
- Foreign exchange or transactions that mix currencies.
- KYC, AML, fraud scoring or dispute handling.
- Multi-region active-active deployment.
- Strictly ordered webhook delivery. Consumers must tolerate reordering.
- Multiple captures per hold (one capture, partial or full, per hold).

## 4. Personas

| Persona | Needs |
|---|---|
| **Merchant developer** | Integrates via the REST API or the TypeScript SDK. Wants clear errors, safe retries and webhooks they can trust. |
| **Merchant operator** | Uses the dashboard to look up balances and transactions and to replay failed webhooks. |
| **Webhook consumer** | A service owned by the merchant that receives events and must apply each one exactly once. |
| **Platform operator (SRE)** | Runs Ledger. Needs reconciliation reports, alerts, runbooks and dashboards. |

## 5. User stories and acceptance criteria

### Accounts
- **US-1** As a merchant developer, I can create an account with a currency so I can hold balances for my users.
  - Currency is an ISO 4217 code and cannot change after creation.
  - New accounts start at a balance of 0.
  - Each merchant automatically has one `external` system account per currency, used to bring money into and out of the ledger.
- **US-2** As a merchant developer, I can read an account's balance and list its entries, newest first, with cursor pagination.

### Transfers
- **US-3** As a merchant developer, I can transfer an amount between two of my accounts in the same currency.
  - Amount is a positive integer in minor units (e.g. cents).
  - The transfer fails with `insufficient_funds` if the source account would go negative, unless it is an `external` system account.
  - Accounts belonging to another merchant are invisible (404).
- **US-4** As a merchant developer, I can retry any money-moving request with the same `Idempotency-Key` and get the original response, with no second effect.
  - The same key with a different request body returns 422 `idempotency_key_reused`.
  - Keys expire after 24 hours.

### Holds
- **US-5** As a merchant developer, I can place a hold (authorize) on funds so they can't be spent elsewhere.
- **US-6** I can capture a hold, fully or partially, to a destination account. Any uncaptured remainder is released back to the source.
- **US-7** I can void a hold, releasing all funds. Holds expire automatically after their `expires_at` (default 7 days).

### Refunds
- **US-8** As a merchant developer, I can refund a transfer fully or partially. The total refunded can never exceed the original amount.

### Events and webhooks
- **US-9** As a merchant developer, I can register a webhook endpoint and choose which event types it receives.
- **US-10** As a webhook consumer, every event I receive carries a unique `id` and an HMAC signature with a timestamp, so I can verify it and deduplicate it.
- **US-11** As a merchant operator, I can see every delivery attempt for an event and manually replay one that failed.

### Operations
- **US-12** As a platform operator, a scheduled reconciliation job verifies the ledger's invariants and alerts on any drift.
- **US-13** As a platform operator, I can trace a single request from the gateway through the core to the database.

## 6. Invariants

These must hold at all times. Each is checked by tests and by the reconciliation job.

| ID | Invariant |
|---|---|
| **INV-1** | For every ledger transaction, total debits equal total credits. |
| **INV-2** | Per merchant and currency, the sum of all entries is zero. |
| **INV-3** | Every account's cached balance equals the sum of its entries. |
| **INV-4** | No non-system account has a negative balance. |
| **INV-5** | Entries are never updated or deleted. |
| **INV-6** | Every committed money movement has exactly one outbox event. |
| **INV-7** | An idempotency key produces at most one money movement. |
| **INV-8** | A transfer's total refunds never exceed its amount; a hold's captured plus released amount equals its authorized amount once it is closed. |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Correctness | Zero invariant violations across property, concurrency and chaos test suites. |
| Latency | `POST /v1/transfers` p99 < 150 ms at 200 req/s on uncontended accounts (CI kind cluster). Contended-account results are reported separately. |
| Durability | A 2xx response means the effect is durably committed (`synchronous_commit = on`). |
| Webhooks | When the endpoint is healthy, 99% of events are delivered within 60 s of commit. |
| Availability (demo) | 99.5% monthly for the public sandbox. |
| Security | API keys stored hashed; tenant isolation on every query; webhook URLs validated against SSRF. See [threat model](threat-model.md). |
| Operability | Structured JSON logs with request IDs, OpenTelemetry traces, RED metrics, runbooks for every alert. |

## 8. Success metrics (portfolio)

- Nightly chaos suite green for 14 consecutive days.
- Published SDK on npm with a working quickstart.
- Public load-test numbers and a written postmortem of at least one bug found by the chaos suite.
