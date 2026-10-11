# C4 Level 1: System Context

Who uses Ledger, and what it talks to.

```mermaid
C4Context
  title System Context: Ledger

  Person(dev, "Merchant developer", "Builds the merchant's product on the Ledger API and SDK.")
  Person(operator, "Merchant operator", "Looks up balances and transactions, replays failed webhooks.")
  Person(sre, "Platform operator", "Runs Ledger: reconciliation, alerts, runbooks.")

  System(ledger, "Ledger", "Double-entry payments ledger with a Stripe-style API: accounts, transfers, holds, refunds, signed webhooks.")

  System_Ext(merchantApp, "Merchant backend", "The merchant's own service. Calls the API (usually via the SDK) and receives webhooks.")
  System_Ext(npm, "npm registry", "Hosts the @temwa/ledger SDK.")
  System_Ext(obs, "Observability stack", "Traces, metrics, logs, error tracking, alerts.")

  Rel(dev, merchantApp, "Builds")
  Rel(dev, npm, "Installs SDK from")
  Rel(merchantApp, ledger, "Moves money, reads balances", "HTTPS, JSON")
  Rel(ledger, merchantApp, "Sends signed events", "HTTPS webhooks")
  Rel(operator, ledger, "Uses dashboard", "HTTPS")
  Rel(ledger, obs, "Exports telemetry", "OTLP")
  Rel(sre, obs, "Watches dashboards, gets alerts")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Notes

- The webhook consumer is part of the merchant backend. It is the thing that must dedupe events by `id` ([ADR-0007](../adr/0007-exactly-once-effects.md)).
- No real money enters or leaves. The `external` system account stands in for the outside world.
