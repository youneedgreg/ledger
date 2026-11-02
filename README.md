# Ledger

[![CI](https://github.com/youneedgreg/ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/youneedgreg/ledger/actions/workflows/ci.yml)
[![CodeQL](https://github.com/youneedgreg/ledger/actions/workflows/codeql.yml/badge.svg)](https://github.com/youneedgreg/ledger/actions/workflows/codeql.yml)

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

## Local development

Requires Docker, [uv](https://docs.astral.sh/uv/) and pnpm.

```bash
cp .env.example .env   # then replace each value: openssl rand -hex 32
docker compose up -d --build
curl http://127.0.0.1:3000/healthz
```

`docker compose` starts Postgres, applies migrations, sets the database role passwords, then starts the core and the gateway. Only the gateway and Postgres are published to the host, and only on `127.0.0.1`. If port 3000 or 5432 is taken, set `LEDGER_GATEWAY_PORT` or `LEDGER_POSTGRES_PORT` in `.env`.

Run the tests:

```bash
uv run --package ledger-core pytest services/ledger-core   # integration tests start a real Postgres in Docker
pnpm install && pnpm test
```

Install the git hooks once after cloning. They run ruff, mypy, ESLint, tsc and gitleaks on commit, check the commit message format, and run the unit tests on push:

```bash
uv sync --all-packages && uv run pre-commit install
```

## Documentation

- [PRD](docs/prd.md): goals, user stories and the invariants Ledger must never break
- [Design doc](docs/design-doc.md): architecture, data model, concurrency model and failure analysis
- [ADRs](docs/adr/README.md): why each major decision was made
- [Threat model](docs/threat-model.md): STRIDE analysis
- [Diagrams](docs/diagrams/README.md): C4, ERD, sequence and state diagrams
