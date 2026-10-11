# C4 Level 2: Containers

The deployable pieces inside Ledger and how they talk.

```mermaid
C4Container
  title Containers: Ledger

  Person(operator, "Merchant operator")
  System_Ext(merchantApp, "Merchant backend", "Uses the @temwa/ledger SDK. Hosts a webhook endpoint.")

  System_Boundary(ledger, "Ledger") {
    Container(dashboard, "Dashboard", "Next.js", "Merchant UI. A normal API client of the gateway.")
    Container(gateway, "API Gateway", "TypeScript, Fastify", "Auth, rate limits, validation, API versioning, OpenAPI docs.")
    Container(core, "Ledger Core", "Python, FastAPI", "The only writer of ledger tables. SERIALIZABLE transactions, idempotency, outbox.")
    Container(relay, "Outbox Relay", "Python worker", "Fans events out to deliveries, signs and sends webhooks, retries.")
    Container(recon, "Reconciler", "Python CronJob", "Read-only invariant checks, drift report.")
    ContainerDb(db, "Postgres", "Postgres 17+", "Accounts, entries, holds, idempotency keys, outbox, deliveries.")
  }

  Rel(operator, dashboard, "Uses", "HTTPS")
  Rel(dashboard, gateway, "Calls", "HTTPS, JSON")
  Rel(merchantApp, gateway, "Calls", "HTTPS, JSON, API key")
  Rel(gateway, core, "Forwards authenticated requests", "HTTP, JSON, traceparent")
  Rel(core, db, "Reads and writes", "SQL, SERIALIZABLE")
  Rel(relay, db, "Claims events, records deliveries", "SQL, SKIP LOCKED")
  Rel(relay, merchantApp, "Sends signed webhooks", "HTTPS")
  Rel(recon, db, "Checks invariants", "SQL, REPEATABLE READ, read-only")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Notes

| Container | Scales by | State |
|---|---|---|
| Gateway | Horizontal, stateless | Rate-limit counters (in-memory per instance in v1) |
| Core | Horizontal, stateless | None; all state in Postgres |
| Relay | Horizontal; `SKIP LOCKED` lets replicas share work | None |
| Reconciler | One run at a time (advisory lock) | Writes `reconciliation_runs` only |
| Postgres | Vertical (single primary in v1) | Source of truth |

Component-level detail for the core (C4 Level 3) is added in Week 2, once the module boundaries exist in code.
