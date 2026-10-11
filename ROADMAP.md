# Roadmap

10 weeks at 10–20 hrs/week. Each week ends with a "done when" check.

## Core design rules (each becomes an ADR)

1. Money is stored as integers in minor units. Never floats.
2. Entries are immutable. Refunds are reversing transactions.
3. Every transaction's entries sum to zero, enforced by a deferred constraint trigger.
4. SERIALIZABLE isolation with bounded, jittered retries on SQLSTATE `40001`/`40P01`.
5. Idempotency keys scoped per merchant, storing request hash and response, written in the same transaction as the ledger write. Same key + different body → 422; a concurrent same-key request waits and replays the result, or gets 409 if it waits longer than 2 s.
6. Transactional outbox; relay uses `FOR UPDATE SKIP LOCKED`.
7. Exactly-once effects = at-least-once delivery + idempotent consumers (dedupe on event ID).
8. Holds: authorize → capture (partial/full) → void → expire, as an explicit state machine.

## Week 0: Design before code ✅
- PRD, design doc, first 6 ADRs, STRIDE threat model
- C4 L1 + L2, ERD, transfer sequence diagram, Hold state machine
- GitHub Project board with a milestone per week

**Done when:** someone could build the system from the docs alone.

## Week 1: Foundations
- Monorepo (pnpm workspaces + uv), docker compose (Postgres, core, gateway), pre-commit
- CI: lint, type-check, test for both languages on every PR
- Health endpoints, structured logging, first Alembic migration

**Done when:** an empty PR runs a green pipeline in under 5 minutes.

## Week 2: Double-entry core
- Accounts, transfers, entries, balances; zero-sum trigger; non-negative balance constraint
- Unit tests + Hypothesis stateful tests against an in-memory model

**Done when:** 10,000+ random operation sequences run with no invariant violated.

## Week 3: Concurrency and idempotency
- SERIALIZABLE + retry decorator with retry-rate metrics
- Idempotency-key middleware and table
- Holds and refunds
- 500 parallel transfers on shared accounts; 100 concurrent same-key requests → exactly one effect

**Done when:** concurrency tests pass 50 runs in a row in CI.

## Week 4: Events and webhooks
- Outbox relay, webhook endpoints, HMAC-SHA256 with timestamp
- Exponential backoff, dead-letter state, replay endpoint
- Test consumer that dedupes on event ID

**Done when:** killing the worker mid-send produces duplicate deliveries but exactly one effect.

## Week 5: API gateway
- API-key auth, per-key rate limiting, Zod validation, Stripe-style errors, `Ledger-Version` header
- Public OpenAPI spec + hosted docs
- Contract test: CI fails if core OpenAPI drifts from gateway types

**Done when:** full flow works via curl through the gateway with trace IDs end to end.

## Week 6: SDK and dashboard (part 1)
- `@temwa/ledger`: typed resources, auto idempotency keys, retries, `webhooks.verify()`
- Changesets + npm publish v0.1.0 with provenance
- Dashboard: API-key login, accounts, balances, transactions list

**Done when:** `npm i @temwa/ledger` works and the quickstart takes under 2 minutes.

## Week 7: Dashboard (part 2) and reconciliation
- Transaction detail, holds, webhook delivery log with replay
- Playwright E2E + axe accessibility checks
- Reconciliation CronJob: per-currency zero-sum, balance cache = sum of entries, one outbox event per committed transaction; report + alert on drift

**Done when:** a deliberately corrupted balance is caught.

## Week 8: Kubernetes, chaos and load
- Helm charts, k3d/kind setup
- Chaos under k6 load: kill core pods, kill outbox worker, latency/partition to Postgres, restart Postgres
- Invariant checker after each run: zero drift, no lost events, no double effects
- Nightly CI chaos job + badge; k6 thresholds, publish throughput and p50/p99

**Done when:** nightly chaos run is green with a results table in the README.

## Week 9: Production and observability
- OTel collector, Grafana dashboard (throughput, retry rate, outbox lag, balance drift)
- SLOs and alerts
- Deploy: `api.ledger.temwa.dev` (gateway), `ledger.temwa.dev` (dashboard), core + worker + Postgres + Scheduler on Heroku
- Sandbox mode: seeded demo data, nightly reset, strict rate limits
- One-off Azure AKS chaos run via Terraform, then destroy the same day
- Verify Heroku dyno hours fit the $13/month credit

**Done when:** live demo works and Azure resources are deleted.

## Week 10: Storytelling
- Postmortem of a real bug found by chaos tests
- Runbooks, final diagrams, README badges, architecture GIF, 3-minute demo video
- Case study on temwa.dev

**Done when:** a recruiter gets it in 30 seconds and a senior engineer finds depth in 10 minutes.

## Diagram checklist
- [ ] C4 L1 Context
- [ ] C4 L2 Containers
- [ ] C4 L3 Components (ledger core)
- [ ] ERD
- [ ] Domain model
- [ ] Sequences: transfer, idempotent retry, hold capture, refund, webhook delivery, outbox relay
- [ ] State machines: Hold, Transfer, WebhookDelivery
- [ ] Deployment: local, production, Azure AKS
- [ ] CI/CD pipeline
- [ ] Threat model data-flow diagram

## Cut order if behind
1. Azure AKS run
2. Datadog/Grafana polish (keep OTel traces)
3. Dashboard extras (keep transactions list and webhook log)

Never cut: property tests, concurrency tests, outbox, reconciliation, chaos suite.
