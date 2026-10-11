# Ledger

A double-entry payments ledger with a Stripe-style API: accounts, transfers, holds, refunds and signed webhooks.

Built to show that money is never created, lost or double-spent, even under concurrency, retries and pods being killed mid-transfer.

## Components

| Component | Stack | Purpose |
|---|---|---|
| `services/ledger-core` | Python, FastAPI, Postgres | Double-entry core: SERIALIZABLE transactions, idempotency keys, transactional outbox |
| `services/gateway` | TypeScript, Fastify | Public API: auth, rate limiting, validation, versioning |
| `apps/dashboard` | TypeScript, Next.js | Merchant dashboard |
| `packages/sdk` | TypeScript | `@temwa/ledger` client published to npm |
| `infra/` | Helm, k3d/kind, Chaos Mesh, Terraform | Deployment, reconciliation cron, chaos tests |

## Status

🚧 Early development. See [ROADMAP.md](ROADMAP.md).
